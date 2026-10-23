"""Risultato di una conversione HTML -> Markdown."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConversionResult:
    markdown: str
    first_heading: str   # testo del primo titolo (h1-h6), senza formattazione
    first_text: str      # testo del primo paragrafo (per titoli di ripiego)
    has_images: bool
