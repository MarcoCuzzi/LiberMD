"""
engine_reader.py - Legge un file EPUB e lo trasforma in un oggetto Book.

Punto di ingresso:

    from engine.readers.engine_reader import read_epub

    book = read_epub(Path("libro.epub"), progress=print)
    meta = read_epub_metadata(Path("libro.epub"))     # solo titolo, autori, editore

Si occupa dello ZIP, del descrittore .opf (metadati e ordine delle sezioni), delle immagini
e dei titoli dei capitoli. Se un file dell'EPUB contiene piu' capitoli (es. Project Gutenberg),
lo spezza usando il sommario dell'EPUB (toc.ncx o nav.xhtml). La conversione HTML -> Markdown e' in engine_converter.py.
"""
from __future__ import annotations

import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from ..text_safety.sanitizer import plain_title, sanitize_filename, truncate_words
from ..engine_book_models import Book, BookMetadata, Chapter
from ..engine_converter import ConversionResult, html_to_markdown
from ..engine_results import EpubError, ProgressCallback


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
OPS_NS = "http://www.idpf.org/2007/ops"
_BLOCK_OPEN = re.compile(r"<(h[1-6]|p|div|section|li)\b", re.I)


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


def _read_toc(z: zipfile.ZipFile, opf_root: ET.Element, opf_dir: str, index: _ZipIndex) -> dict[str, list[str]]:
    """Sommario dell'EPUB: per ogni file, gli identificatori (#...) dove iniziano le voci."""
    nav = ncx = None
    for elem in opf_root.iter():
        if _local(elem.tag) != "item" or not elem.attrib.get("href"):
            continue
        href = posixpath.normpath(posixpath.join(opf_dir, unquote(elem.attrib["href"])))
        if "nav" in elem.attrib.get("properties", "").split():
            nav = href
        elif elem.attrib.get("media-type") == "application/x-dtbncx+xml":
            ncx = href

    for path in (nav, ncx):  # EPUB3 prima, poi EPUB2
        real = index.find(path) if path else None
        if not real:
            continue
        try:
            root = ET.fromstring(z.read(real))
        except ET.ParseError:
            continue
        if path == nav:  # solo il sommario, non landmarks/page-list
            navs = [e for e in root.iter() if _local(e.tag) == "nav"]
            scope = [e for e in navs if "toc" in e.attrib.get(f"{{{OPS_NS}}}type", "").split()] or navs[:1]
            links = [a.attrib["href"] for n in scope for a in n.iter() if _local(a.tag) == "a" and a.attrib.get("href")]
        else:
            maps = [e for e in root.iter() if _local(e.tag) == "navMap"]
            links = [c.attrib["src"] for m in maps for c in m.iter() if _local(c.tag) == "content" and c.attrib.get("src")]

        toc: dict[str, list[str]] = {}
        base = posixpath.dirname(real)
        for link in links:
            file, _, frag = unquote(link).partition("#")
            target = index.find(posixpath.normpath(posixpath.join(base, file))) if file else None
            if target and frag:
                toc.setdefault(target, []).append(frag)
        if toc:
            return toc
    return {}


def _split_html(html: str, fragments: list[str]) -> list[str]:
    """Spezza l'HTML di un file nei punti dove iniziano le voci del sommario."""
    cuts = set()
    for frag in fragments:
        m = re.search(r"<(\w+)\b[^<>]*?\s(?:id|name)\s*=\s*[\"']%s[\"']" % re.escape(frag), html)
        if not m:
            continue
        pos = m.start()
        if m.group(1).lower() in ("a", "span"):  # ancora dentro un titolo/paragrafo: taglia prima di quello
            opens = list(_BLOCK_OPEN.finditer(html, 0, pos))
            if opens and html.rfind("</" + opens[-1].group(1), 0, pos) < opens[-1].start():
                pos = opens[-1].start()
        cuts.add(pos)
    bounds = [0] + sorted(c for c in cuts if c > 0) + [len(html)]
    return [html[a:b] for a, b in zip(bounds, bounds[1:])]


def _heading_only(markdown: str) -> bool:
    lines = [ln for ln in markdown.splitlines() if ln.strip()]
    return bool(lines) and all(ln.lstrip().startswith("#") for ln in lines)


def _merge_heading_only(results: list[ConversionResult]) -> list[ConversionResult]:
    """Un pezzo fatto solo di titoli (es. 'ETYMOLOGY' + sottotitolo) si unisce al pezzo successivo."""
    merged: list[ConversionResult] = []
    carry: Optional[ConversionResult] = None
    for i, r in enumerate(results):
        if carry:
            r = ConversionResult(carry.markdown + "\n\n" + r.markdown, carry.first_heading or r.first_heading,
                                 carry.first_text or r.first_text, carry.has_images or r.has_images)
            carry = None
        if _heading_only(r.markdown) and i < len(results) - 1:
            carry = r
        else:
            merged.append(r)
    return merged


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


def _open_epub(epub_path: Path) -> zipfile.ZipFile:
    """Apre l'EPUB (che e' uno ZIP) o solleva un errore leggibile."""
    if not epub_path.is_file():
        raise EpubError(f"File '{epub_path}' non trovato.")
    try:
        return zipfile.ZipFile(epub_path)
    except zipfile.BadZipFile:
        raise EpubError("Il file non e' un EPUB valido (archivio ZIP non leggibile).")


def read_epub_metadata(epub_path: Path) -> BookMetadata:
    """Legge SOLO i metadati (titolo, autori, editore), senza convertire nulla."""
    with _open_epub(epub_path) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        opf_root = ET.fromstring(z.read(_find_opf(z, names)))
        return _read_metadata(opf_root, fallback_title=epub_path.stem)


def read_epub(epub_path: Path, progress: ProgressCallback = lambda msg: None) -> Book:
    warnings: list[str] = []
    z = _open_epub(epub_path)

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
        toc = _read_toc(z, opf_root, opf_dir, index)
        progress(f"Conversione di {len(spine)} sezioni...")

        chapters: list[Chapter] = []
        skipped = 0
        for entry in spine:
            real = index.find(entry)
            if real is None:
                warnings.append(f"Sezione non trovata nello ZIP: {entry}")
                continue
            resolver = _make_resolver(posixpath.dirname(real), index, path_to_name)
            html = _decode(z.read(real))
            pieces = _split_html(html, toc[real]) if real in toc else [html]
            results = [html_to_markdown(piece, resolver) for piece in pieces]
            results = _merge_heading_only([r for r in results if r.markdown.strip()])

            if not results:  # pagina davvero vuota
                skipped += 1
                continue

            for result in results:
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
