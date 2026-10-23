"""MarkdownConverter: converte (X)HTML in Markdown (solo libreria standard).

Il testo corrente viene accumulato in `buf` e "chiuso" in un blocco (`_flush`)
a ogni tag di blocco. Cosi' gli spazi si normalizzano per paragrafo e i prefissi
(citazioni, elenchi) si applicano una volta sola.

Le parti separate vivono in file propri:
    inline.py  -> grassetto/corsivo e spazi      blocks.py -> unione dei blocchi
    tables.py  -> tabelle (TableMixin)
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Callable, Optional

from ..textutils import plain_title
from .blocks import join_blocks
from .constants import BLOCK_TAGS, HEADINGS, IGNORED, MARKERS
from .inline import render_inline, tidy
from .result import ConversionResult
from .tables import TableMixin


class MarkdownConverter(TableMixin, HTMLParser):

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
            self.buf.append(data)

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
        text = tidy(render_inline(self.buf))
        self.buf = []
        if not text:
            return

        if self.heading_level:
            plain = text.replace("\n", " ")
            if not self.first_heading:
                self.first_heading = plain_title(plain)
            self._add("h", f"{'#' * self.heading_level} {plain}", 0)
            return

        lines = text.split("\n")
        plain = " ".join(lines)
        if not self.first_text and not plain.startswith("!["):
            self.first_text = plain

        kind, first, rest = "p", "", ""
        if self.li_stack:
            top = self.li_stack[-1]
            if top["marker"] is not None:
                kind, first, rest = "li", top["marker"], top["content_indent"]
                top["marker"] = None
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

    # ----------------------------------------------------------- risultato

    def result(self) -> ConversionResult:
        self._flush()
        return ConversionResult(join_blocks(self.blocks), self.first_heading, self.first_text, self.has_images)
