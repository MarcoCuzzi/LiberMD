"""
engine.py - Motore di conversione EPUB -> Markdown (note per Obsidian).

Il motore NON stampa nulla, NON legge input e NON chiude il programma: riceve dei
parametri e restituisce un risultato. Cosi' lo si puo' usare da qualsiasi interfaccia
(riga di comando, grafica, API web) senza modificarlo.

Punto di ingresso:

    from engine import convert, EpubError

    report = convert("libro.epub", out_base="vault", on_progress=print)
    print(report.out_dir, report.chapters)

Struttura del file:

    1. MODELLO        Book / Chapter / BookMetadata / ConvertReport
    2. UTILITA'       plain_title
    3. CONVERTITORE   HTML -> Markdown (solo libreria standard)
    4. LETTORE        EPUB -> Book
    5. CONVERT        la funzione pubblica che collega le parti

Gli altri file:

    sanitizer.py      rende sicuro il testo (caratteri speciali) e i nomi dei file
    writer.py         scrive il libro su disco: originali + copie di lavoro
    nav.py            maschera di navigazione: barre avanti/indietro/originale e stile "libro"
    cli.py            interfaccia a riga di comando
"""
from __future__ import annotations

import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Optional, Union
from urllib.parse import unquote

from sanitizer import (
    escape_line_start,
    escape_text,
    sanitize_filename,
    sanitize_name,
    truncate_words,
    unescape,
)
from writer import ORIGINALS_DIR, write_book


# ============================================================================
# 1. MODELLO
# ============================================================================

@dataclass
class BookMetadata:
    title: str = ""
    authors: list[str] = field(default_factory=list)
    publisher: str = ""


@dataclass
class Chapter:
    title: str
    markdown: str


@dataclass
class Book:
    metadata: BookMetadata
    chapters: list[Chapter]
    media: dict[str, bytes]                       # nome file sicuro -> contenuto
    skipped_pages: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class ConvertReport:
    """Risultato di convert(): tutto cio' che un'interfaccia puo' voler mostrare."""
    out_dir: Path
    originals_dir: Path
    title: str
    authors: list[str]
    publisher: str
    chapters: int
    images: int
    skipped_pages: int
    warnings: list[str]
    kept_existing: int = 0     # file di lavoro gia' presenti, lasciati intatti
    style_path: Optional[Path] = None   # file di stile LiberMD.css
    style_in_vault: bool = False        # True se e' gia' nella cartella .obsidian/snippets/


class EpubError(Exception):
    """Errore "atteso" (file mancante, EPUB non valido...). Il messaggio e' leggibile."""


ProgressCallback = Callable[[str], None]


# ============================================================================
# 2. UTILITA'
# ============================================================================

def plain_title(text: str) -> str:
    """
    Dal testo Markdown ricava un titolo "vero": toglie immagini, tag HTML ed enfasi
    generati dal convertitore, poi le barre di escape messe dal sanificatore.
    """
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)   # immagini generate (quelle nel testo sono escapate)
    text = re.sub(r"<[^>]+>", "", text)                    # <sup> ecc. generati
    text = re.sub(r"(?<!\\)[*`~]", "", text)               # marcatori generati, non quelli escapati
    return re.sub(r"\s+", " ", unescape(text)).strip()


# ============================================================================
# 3. CONVERTITORE HTML -> MARKDOWN
# ============================================================================

HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
IGNORED = {"script", "style", "head", "title"}
BLOCK_TAGS = {
    "p", "div", "section", "article", "aside", "header", "footer", "main", "nav",
    "figure", "figcaption", "address", "center", "dl", "dt", "dd", "details", "summary",
}
MARKERS = {
    "b": "**", "strong": "**",
    "i": "*", "em": "*",
    "s": "~~", "strike": "~~", "del": "~~",
    "code": "`",
}


@dataclass
class ConversionResult:
    markdown: str
    first_heading: str   # testo del primo titolo (h1-h6), senza formattazione
    first_text: str      # testo del primo paragrafo (per titoli di ripiego)
    has_images: bool


class MarkdownConverter(HTMLParser):
    """
    Converte (X)HTML in Markdown.

    Il testo corrente si accumula in `buf` e viene "chiuso" in un blocco (`_flush`)
    a ogni tag di blocco. Cosi' gli spazi si normalizzano per paragrafo e i prefissi
    (citazioni, elenchi) si applicano una volta sola.
    """

    def __init__(self, resolve_image: Optional[Callable[[str], Optional[str]]] = None):
        super().__init__(convert_charrefs=True)
        self.resolve_image = resolve_image or (lambda src: None)

        self.blocks: list[tuple[str, str, int]] = []  # (tipo, testo, profondita' citazione)
        self.buf: list = []                            # str oppure ("open"|"close", marcatore)

        self.ignore_depth = 0
        self.heading_level = 0
        self.quote_depth = 0
        self.list_stack: list[dict] = []
        self.li_stack: list[dict] = []
        self.new_list = False
        self.code_depth = 0                            # dentro <code>: il testo NON va escapato

        self.in_pre = False
        self.pre_buf: list[str] = []

        self.table_depth = 0
        self.rows: list[list[str]] = []
        self.row: Optional[list[str]] = None
        self.in_cell = False

        self.first_heading = ""
        self.first_text = ""
        self.has_images = False

    # ------------------------------------------------------------------ tag

    def handle_starttag(self, tag, attrs):
        if tag in IGNORED:
            self.ignore_depth += 1
            return
        if self.ignore_depth:
            return
        attrs = dict(attrs)

        if self.in_pre:
            if tag == "br":
                self.pre_buf.append("\n")
            return

        if tag in HEADINGS:
            self._flush()
            self.heading_level = int(tag[1])
        elif tag in ("ul", "ol"):
            self._flush()
            start = 0
            if tag == "ol":
                try:
                    start = int(attrs.get("start", 1)) - 1
                except ValueError:
                    start = 0
            indent = self.li_stack[-1]["content_indent"] if self.li_stack else ""
            if not self.list_stack:
                self.new_list = True  # il primo elemento sara' separato dal testo precedente
            self.list_stack.append({"ordered": tag == "ol", "n": start, "indent": indent})
        elif tag == "li":
            self._flush()
            depth = len(self.list_stack)
            # <li> non chiusi (HTML "vecchio stile"): chiudi quelli dello stesso livello
            while self.li_stack and self.li_stack[-1]["depth"] >= depth:
                self.li_stack.pop()
            if self.list_stack:
                lst = self.list_stack[-1]
                lst["n"] += 1
                marker = f"{lst['n']}. " if lst["ordered"] else "- "
                base = lst["indent"]
            else:
                marker, base = "- ", ""
            self.li_stack.append({
                "depth": depth,
                "marker": base + marker,                       # None dopo il primo uso
                "content_indent": base + " " * len(marker),
            })
        elif tag == "blockquote":
            self._flush()
            self.quote_depth += 1
        elif tag == "pre":
            self._flush()
            self.in_pre = True
            self.pre_buf = []
        elif tag == "hr":
            self._flush()
            self._add("hr", "---", 0)
        elif tag == "br":
            self.buf.append("\n")
        elif tag == "table":
            self._start_table()
        elif tag == "tr":
            if self.table_depth == 1:
                self.row = []
        elif tag in ("td", "th"):
            self._start_cell()
        elif tag in BLOCK_TAGS:
            self._flush()
        elif tag in MARKERS:
            if not self.heading_level:
                self.buf.append(("open", MARKERS[tag]))
                if tag == "code":
                    self.code_depth += 1
        elif tag in ("sup", "sub"):
            self.buf.append(f"<{tag}>")
        elif tag in ("img", "image"):
            self._image(attrs)

    def handle_endtag(self, tag):
        if tag in IGNORED:
            self.ignore_depth = max(0, self.ignore_depth - 1)
            return
        if self.ignore_depth:
            return

        if self.in_pre:
            if tag == "pre":
                self._end_pre()
            return

        if tag in HEADINGS:
            self._flush()
            self.heading_level = 0
        elif tag in ("ul", "ol"):
            self._flush()
            depth = len(self.list_stack)
            while self.li_stack and self.li_stack[-1]["depth"] >= depth:
                self.li_stack.pop()
            if self.list_stack:
                self.list_stack.pop()
        elif tag == "li":
            self._flush()
            if self.li_stack:
                self.li_stack.pop()
        elif tag == "blockquote":
            self._flush()
            self.quote_depth = max(0, self.quote_depth - 1)
        elif tag in ("td", "th"):
            self._end_cell()
        elif tag == "tr":
            self._end_row()
        elif tag == "table":
            self._end_table()
        elif tag in BLOCK_TAGS:
            self._flush()
        elif tag in MARKERS:
            if not self.heading_level:
                self.buf.append(("close", MARKERS[tag]))
                if tag == "code":
                    self.code_depth = max(0, self.code_depth - 1)
        elif tag in ("sup", "sub"):
            self.buf.append(f"</{tag}>")

    def handle_data(self, data):
        if self.ignore_depth:
            return
        if self.in_pre:
            self.pre_buf.append(data)
            return
        data = data.replace("\xad", "").replace("\u200b", "")  # trattino morbido, spazio zero
        data = re.sub(r"\s+", " ", data)  # gli a capo del sorgente HTML NON sono a capo
        if data:
            # Il testo e' TESTO: i caratteri speciali di Markdown/Obsidian vengono neutralizzati.
            # (Il Markdown generato dal convertitore, es. ** o ![](), non passa di qui.)
            self.buf.append(data if self.code_depth else escape_text(data))

    # ----------------------------------------------------------- inline

    @staticmethod
    def _render_inline(tokens: list) -> str:
        """Unisce i frammenti applicando grassetto/corsivo senza rompere il Markdown."""
        out: list = []
        stack: list[tuple[int, str]] = []
        for tok in tokens:
            if isinstance(tok, str):
                out.append(tok)
            elif tok[0] == "open":
                stack.append((len(out), tok[1]))
                out.append(tok)
            else:  # close
                marker = tok[1]
                for k in range(len(stack) - 1, -1, -1):
                    if stack[k][1] == marker:
                        break
                else:
                    continue  # chiusura senza apertura: ignorata
                i = stack[k][0]
                del stack[k:]
                inner = "".join(x for x in out[i + 1:] if isinstance(x, str))
                core = inner.strip()
                if core:
                    lead = inner[: len(inner) - len(inner.lstrip())]
                    trail = inner[len(inner.rstrip()):]
                    fence = marker
                    if marker == "`" and "`" in core:  # codice che contiene apici inversi
                        fence, core = "``", f" {core} "
                    replacement = f"{lead}{fence}{core}{fence}{trail}"  # spazi FUORI dai marcatori
                else:
                    replacement = inner  # tag vuoto: niente "****"
                out[i:] = [replacement]
        return "".join(x for x in out if isinstance(x, str))

    @staticmethod
    def _tidy(text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" ?\n ?", "\n", text)
        text = text.strip()
        return re.sub(r"\n{2,}", "\n", text)

    def _image(self, attrs: dict) -> None:
        src = attrs.get("src") or attrs.get("xlink:href") or attrs.get("href") or ""
        if not src:
            return
        name = self.resolve_image(src)
        if not name:
            return
        alt = re.sub(r"[\[\]|\r\n]+", " ", attrs.get("alt", "")).strip()
        self.has_images = True
        self.buf.append(f"![{alt}](media/{name})")

    # ----------------------------------------------------------- blocchi

    def _add(self, kind: str, text: str, quote_depth: Optional[int] = None) -> None:
        if self.in_cell:
            return
        self.blocks.append((kind, text, self.quote_depth if quote_depth is None else quote_depth))

    def _flush(self) -> None:
        """Chiude il blocco di testo corrente e lo aggiunge all'output."""
        if self.in_cell:
            self.buf.append(" ")
            return
        text = self._tidy(self._render_inline(self.buf))
        self.buf = []
        if not text:
            return

        if self.heading_level:
            plain = text.replace("\n", " ")
            if not self.first_heading:
                self.first_heading = plain_title(plain)
            self._add("h", f"{'#' * self.heading_level} {plain}", 0)
            return

        lines = [escape_line_start(line) for line in text.split("\n")]
        plain = " ".join(lines)
        if not self.first_text and not plain.startswith("!["):
            self.first_text = plain

        kind, first, rest = "p", "", ""
        if self.li_stack:
            top = self.li_stack[-1]
            if top["marker"] is not None:
                kind, first, rest = "li", top["marker"], top["content_indent"]
                top["marker"] = None
                if self.new_list:
                    kind, self.new_list = "lis", False  # primo elemento di una lista nuova
            else:  # secondo paragrafo dentro lo stesso elemento di lista
                kind, first, rest = "lic", top["content_indent"], top["content_indent"]

        quote = "> " * self.quote_depth
        out = []
        for i, line in enumerate(lines):
            prefix = first if i == 0 else rest
            hard_break = "  " if i < len(lines) - 1 else ""
            out.append(f"{quote}{prefix}{line}{hard_break}")
        self._add(kind, "\n".join(out))

    def _end_pre(self) -> None:
        self.in_pre = False
        code = "".join(self.pre_buf).strip("\n")
        self.pre_buf = []
        if not code.strip():
            return
        if self.in_cell:
            self.buf.append(" " + code.replace("\n", " ") + " ")
            return
        fence = "```"
        while fence in code:
            fence += "`"
        self._add("code", f"{fence}\n{code}\n{fence}", 0)

    # ----------------------------------------------------------- tabelle

    def _start_table(self) -> None:
        if self.table_depth == 0:
            self._flush()
            self.rows, self.row = [], None
        self.table_depth += 1

    def _start_cell(self) -> None:
        if self.table_depth == 1:
            if self.in_cell:      # <td> precedente non chiuso
                self._end_cell()
            if self.row is None:
                self.row = []
            self.in_cell = True
            self.buf = []

    def _end_cell(self) -> None:
        if self.table_depth == 1 and self.in_cell:
            text = self._tidy(self._render_inline(self.buf))
            text = text.replace("\n", " ").replace("|", "\\|")
            self.buf = []
            self.in_cell = False
            self.row.append(text)

    def _end_row(self) -> None:
        if self.table_depth == 1:
            self._end_cell()
            if self.row is not None:
                self.rows.append(self.row)
                self.row = None

    def _end_table(self) -> None:
        if self.table_depth == 0:
            return
        if self.table_depth == 1:
            self._end_row()
        self.table_depth -= 1
        if self.table_depth > 0:
            return
        rows = [r for r in self.rows if any(r)]
        self.rows = []
        if not rows:
            return
        ncols = max(len(r) for r in rows)
        if ncols == 1:  # tabella usata solo per l'impaginazione: testo normale
            for r in rows:
                self._add("p", r[0], 0)
            return
        rows = [r + [""] * (ncols - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * ncols) + " |"]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        self._add("table", "\n".join(lines), 0)

    # ----------------------------------------------------------- risultato

    def _join(self) -> str:
        parts: list[str] = []
        prev_kind, prev_quote = None, 0
        for kind, text, quote in self.blocks:
            if prev_kind is not None:
                if kind == "li" and prev_kind in ("li", "lis", "lic"):
                    sep = "\n"                                   # elementi di lista attaccati
                elif quote > 0 and prev_quote > 0:
                    sep = "\n" + ("> " * min(quote, prev_quote)).rstrip() + "\n"  # citazione continua
                else:
                    sep = "\n\n"
                parts.append(sep)
            parts.append(text)
            prev_kind, prev_quote = kind, quote
        return "".join(parts).strip()

    def result(self) -> ConversionResult:
        self._flush()
        return ConversionResult(self._join(), self.first_heading, self.first_text, self.has_images)


def html_to_markdown(html: str, resolve_image=None) -> ConversionResult:
    parser = MarkdownConverter(resolve_image)
    parser.feed(html)
    parser.close()
    return parser.result()


# ============================================================================
# 4. LETTORE EPUB -> Book
# ============================================================================

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")


def _local(tag: str) -> str:
    """Nome del tag senza namespace: '{http://...}title' -> 'title'."""
    return tag.rsplit("}", 1)[-1]


def _text(elem: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(elem.itertext())).strip()


class _ZipIndex:
    """Ricerca tollerante dei file nello ZIP (maiuscole/minuscole, percorsi imprecisi)."""

    def __init__(self, names: list[str]):
        self.names = set(names)
        self.lower = {n.lower(): n for n in names}
        self.by_basename: dict[str, str] = {}
        for n in names:
            self.by_basename.setdefault(posixpath.basename(n).lower(), n)

    def find(self, path: str) -> Optional[str]:
        if path in self.names:
            return path
        if path.lower() in self.lower:
            return self.lower[path.lower()]
        return self.by_basename.get(posixpath.basename(path).lower())


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _find_opf(z: zipfile.ZipFile, names: list[str]) -> str:
    if "META-INF/container.xml" in names:
        root = ET.fromstring(z.read("META-INF/container.xml"))
        for elem in root.iter():
            if _local(elem.tag) == "rootfile" and elem.attrib.get("full-path"):
                return elem.attrib["full-path"]
    for name in names:  # ripiego
        if name.endswith(".opf"):
            return name
    raise EpubError("Nessun descrittore .opf trovato nell'EPUB.")


def _read_metadata(opf_root: ET.Element, fallback_title: str) -> BookMetadata:
    meta = BookMetadata()
    for container in opf_root.iter():
        if _local(container.tag) != "metadata":
            continue
        for elem in container:
            name, value = _local(elem.tag), _text(elem)
            if not value:
                continue
            if name == "title" and not meta.title:
                meta.title = value
            elif name == "creator":
                meta.authors.append(value)
            elif name == "publisher" and not meta.publisher:
                meta.publisher = value
        break
    meta.title = meta.title or fallback_title
    return meta


def _read_spine(opf_root: ET.Element, opf_dir: str) -> list[str]:
    manifest = {}
    for elem in opf_root.iter():
        if _local(elem.tag) == "item" and "id" in elem.attrib and "href" in elem.attrib:
            manifest[elem.attrib["id"]] = elem.attrib["href"]

    spine = []
    for elem in opf_root.iter():
        if _local(elem.tag) == "itemref" and elem.attrib.get("idref") in manifest:
            href = unquote(manifest[elem.attrib["idref"]]).split("#")[0]
            spine.append(posixpath.normpath(posixpath.join(opf_dir, href)))
    return spine


def _extract_media(z: zipfile.ZipFile, names: list[str]) -> tuple[dict[str, bytes], dict[str, str]]:
    """Estrae le immagini con nomi sicuri e UNICI (due 'fig1.png' in cartelle diverse non si sovrascrivono)."""
    media: dict[str, bytes] = {}
    path_to_name: dict[str, str] = {}
    used: set[str] = set()
    for zip_path in names:
        if not zip_path.lower().endswith(IMAGE_EXTENSIONS):
            continue
        name = sanitize_filename(zip_path)
        stem, ext = posixpath.splitext(name)
        candidate, n = name, 2
        while candidate.lower() in used:
            candidate = f"{stem}-{n}{ext}"
            n += 1
        used.add(candidate.lower())
        media[candidate] = z.read(zip_path)
        path_to_name[zip_path] = candidate
    return media, path_to_name


def _make_resolver(chapter_dir: str, index: _ZipIndex, path_to_name: dict[str, str]):
    def resolve(src: str) -> Optional[str]:
        if src.lower().startswith(("data:", "http:", "https:")):
            return None
        rel = unquote(src.split("#")[0].split("?")[0])
        found = index.find(posixpath.normpath(posixpath.join(chapter_dir, rel)))
        return path_to_name.get(found) if found else None
    return resolve


def read_epub(epub_path: Path, progress: ProgressCallback = lambda msg: None) -> Book:
    if not epub_path.is_file():
        raise EpubError(f"File '{epub_path}' non trovato.")

    warnings: list[str] = []
    try:
        z = zipfile.ZipFile(epub_path)
    except zipfile.BadZipFile:
        raise EpubError("Il file non e' un EPUB valido (archivio ZIP non leggibile).")

    with z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        index = _ZipIndex(names)

        opf_path = _find_opf(z, names)
        opf_dir = posixpath.dirname(opf_path)
        opf_root = ET.fromstring(z.read(opf_path))
        progress(f"Descrittore trovato: {opf_path}")

        metadata = _read_metadata(opf_root, fallback_title=epub_path.stem)
        spine = _read_spine(opf_root, opf_dir)
        if not spine:
            warnings.append("Spine vuota: uso tutti i file HTML in ordine alfabetico.")
            spine = sorted(n for n in names if n.lower().endswith((".xhtml", ".html", ".htm")))

        media, path_to_name = _extract_media(z, names)
        progress(f"Conversione di {len(spine)} sezioni...")

        chapters: list[Chapter] = []
        skipped = 0
        for entry in spine:
            real = index.find(entry)
            if real is None:
                warnings.append(f"Sezione non trovata nello ZIP: {entry}")
                continue
            resolver = _make_resolver(posixpath.dirname(real), index, path_to_name)
            result = html_to_markdown(_decode(z.read(real)), resolver)

            if not result.markdown.strip():  # pagina davvero vuota
                skipped += 1
                continue

            n = len(chapters) + 1
            if result.first_heading:
                title = result.first_heading
            elif result.first_text:
                title = truncate_words(plain_title(result.first_text), 60)
            elif result.has_images:
                title = "Copertina" if n == 1 else f"Immagine {n}"
            else:
                title = f"Sezione {n}"
            chapters.append(Chapter(title=title or f"Sezione {n}", markdown=result.markdown))

    if not chapters:
        raise EpubError("Nessun contenuto estratto. Il libro potrebbe avere DRM o essere solo immagini.")
    return Book(metadata=metadata, chapters=chapters, media=media,
                skipped_pages=skipped, warnings=warnings)


# ============================================================================
# 5. CONVERT - la funzione pubblica
# ============================================================================

def convert(
    epub_path: Union[str, Path],
    out_base: Union[str, Path] = ".",
    on_progress: Optional[ProgressCallback] = None,
    lock_originals: bool = True,
    overwrite_working: bool = False,
) -> ConvertReport:
    """
    Converte un EPUB in una cartella con due versioni dei capitoli.

    epub_path          file .epub da convertire
    out_base           cartella in cui creare la cartella del libro
    on_progress        funzione chiamata con un messaggio di testo a ogni fase (opzionale)
    lock_originals     se True, i file in originali/ vengono messi in sola lettura
    overwrite_working  se True, rigenera anche le copie di lavoro gia' esistenti
                       (ATTENZIONE: perderesti le tue note). Di default restano intatte.

    Solleva EpubError se il file non e' leggibile o non contiene testo.
    """
    progress = on_progress or (lambda msg: None)
    epub_path = Path(epub_path)

    progress(f"Lettura di {epub_path.name}")
    book = read_epub(epub_path, progress)

    out_dir = Path(out_base) / sanitize_name(epub_path.stem)
    progress(f"Scrittura di {len(book.chapters)} capitoli (originali + copie di lavoro) in {out_dir}")
    written = write_book(book, out_dir, lock_originals, overwrite_working)

    meta = book.metadata
    return ConvertReport(
        out_dir=out_dir,
        originals_dir=out_dir / ORIGINALS_DIR,
        title=meta.title,
        authors=meta.authors,
        publisher=meta.publisher,
        chapters=len(book.chapters),
        images=len(book.media),
        skipped_pages=book.skipped_pages,
        warnings=book.warnings,
        kept_existing=written.kept_existing,
        style_path=written.style_path,
        style_in_vault=written.style_in_vault,
    )
