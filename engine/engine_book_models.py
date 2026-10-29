"""
engine_book_models.py - Le "schede" che descrivono un libro gia' letto.

Non contiene logica: solo i contenitori di dati che i vari file si passano.

    BookMetadata   titolo, autori, editore
    Chapter        un capitolo: titolo + testo Markdown
    Book           il libro intero: metadati, capitoli, immagini

Le usano il lettore (engine_reader.py, che crea il Book) e il writer (writer.py,
che lo scrive su disco). L'esito della conversione e gli errori sono in engine_results.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BookMetadata:
    title: str = ""
    authors: list[str] = field(default_factory=list)
    publisher: str = ""


@dataclass
class Chapter:
    title: str
    markdown: str
    has_heading: bool = True      # False: il titolo e' ricavato dal testo (tipico delle scansioni OCR)
    first_page: int = 0           # numero della sezione dell'EPUB da cui nasce (serve a nominare le fusioni)
    last_page: int = 0


@dataclass
class Book:
    metadata: BookMetadata
    chapters: list[Chapter]
    media: dict[str, bytes]                       # nome file sicuro -> contenuto
    skipped_pages: int = 0
    warnings: list[str] = field(default_factory=list)
