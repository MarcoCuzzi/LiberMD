"""Risultato di una conversione HTML -> Markdown."""
from __future__ import annotations

from dataclasses import dataclass, field

from .blocks import join_blocks


@dataclass
class ConversionResult:
    markdown: str
    first_heading: str   # testo del primo titolo (h1-h6), senza formattazione
    first_text: str      # testo del primo paragrafo (per titoli di ripiego)
    has_images: bool
    blocks: list = field(default_factory=list)    # (tipo, testo, profondita' citazione)
    anchors: dict = field(default_factory=dict)   # id HTML -> indice del blocco che inizia li'

    def slice(self, start: int, end: int) -> str:
        """Markdown dei blocchi [start, end): serve a spezzare un file in piu' capitoli."""
        return join_blocks(self.blocks[start:end])
