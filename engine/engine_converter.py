"""
engine_converter.py - Converte (X)HTML in Markdown, usando solo la libreria standard.

Punto di ingresso:

    from engine.engine_converter import html_to_markdown

    risultato = html_to_markdown(html, resolve_image)
    risultato.markdown        il testo convertito
    risultato.first_heading   primo titolo trovato (per dare un nome al capitolo)

Il testo del libro e' trattato come TESTO: i caratteri speciali di Markdown/Obsidian
vengono neutralizzati da sanitizer.py. Il Markdown generato qui (**, ![](), ecc.) no.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable, Optional

from .text_safety.sanitizer import escape_line_start, escape_text, plain_title


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
_FN_TYPES = {"footnote", "endnote", "rearnote"}
_REF_TYPES = {"noteref", "doc-noteref"}


def _normalize_fn_key(key: str) -> str:
    """Pulisce l'identificatore per Obsidian [^id]."""
    clean = re.sub(r"[^\w\-.]", "", key.strip("#"))
    return clean or "fn"


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

        # Note a pie' di pagina
        self.in_sup = False
        self.current_a: Optional[dict] = None
        self.fn_capturing_id: Optional[str] = None
        self.fn_depth = 0
        self.footnotes: dict[str, list[str]] = {}

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
        elem_id = attrs.get("id") or attrs.get("name")
        epub_type = attrs.get("epub:type", "").lower()
        cls = attrs.get("class", "").lower()

        # Rilevamento inizio blocco nota a pie' di pagina
        is_fn_container = (
            any(t in epub_type for t in _FN_TYPES) or
            any(c in cls for c in ("footnote", "endnote")) or
            (tag == "aside" and bool(elem_id))
        )
        if is_fn_container and elem_id and not self.fn_capturing_id:
            self._flush()
            self.fn_capturing_id = _normalize_fn_key(elem_id)
            self.fn_depth = 1
            self.footnotes.setdefault(self.fn_capturing_id, [])
            return
        elif self.fn_capturing_id:
            self.fn_depth += 1

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
        elif tag == "sup":
            self.in_sup = True
        elif tag == "a":
            href = attrs.get("href", "")
            is_ref = (
                any(t in epub_type for t in _REF_TYPES) or
                "noteref" in cls or
                "footnote" in cls or
                (self.in_sup and href.startswith("#"))
            )
            self.current_a = {
                "href": href,
                "is_ref": is_ref,
                "text": []
            }
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

        if self.fn_capturing_id:
            self.fn_depth -= 1
            if self.fn_depth == 0:
                self._flush()
                self.fn_capturing_id = None
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
        elif tag == "sup":
            self.in_sup = False
        elif tag == "a":
            if self.current_a:
                text = "".join(self.current_a["text"]).strip()
                href = self.current_a["href"]
                if self.current_a["is_ref"] and href.startswith("#"):
                    target_id = _normalize_fn_key(href)
                    self.buf.append(f"[^{target_id}]")
                elif href.startswith("#") and text.isdigit():
                    target_id = _normalize_fn_key(href)
                    self.buf.append(f"[^{target_id}]")
                else:
                    self.buf.append(escape_text(text) if not self.code_depth else text)
                self.current_a = None
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
            if self.current_a is not None:
                self.current_a["text"].append(data)
                return
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

        if self.fn_capturing_id:
            clean_note = re.sub(r"\s*\\?[↩\^]\s*$", "", text).strip()
            if clean_note:
                self.footnotes[self.fn_capturing_id].append(clean_note)
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

        if self.footnotes:
            fn_lines = ["\n\n---"]
            for fn_id, paragraphs in self.footnotes.items():
                if not paragraphs:
                    continue
                first = paragraphs[0]
                rest = paragraphs[1:]
                fn_lines.append(f"[^{fn_id}]: {first}")
                for p in rest:
                    fn_lines.append(f"    {p}")
            parts.append("\n".join(fn_lines))

        return "".join(parts).strip()

    def result(self) -> ConversionResult:
        self._flush()
        return ConversionResult(self._join(), self.first_heading, self.first_text, self.has_images)


def html_to_markdown(html: str, resolve_image=None) -> ConversionResult:
    parser = MarkdownConverter(resolve_image)
    parser.feed(html)
    parser.close()
    return parser.result()