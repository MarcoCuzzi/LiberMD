"""
naming.py - Come si chiamano i file del libro e come i capitoli si raggruppano in pagine.

    index_name(titolo)     nome dell'indice
    original_name(stem)    nome dell'originale che corrisponde a una copia di lavoro
    plan_pages(book, n)    decide quali capitoli finiscono in quale file (Page)

Non scrive nulla su disco: restituisce solo nomi e liste.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..text_safety.sanitizer import sanitize_name

if TYPE_CHECKING:
    from engine.engine_book_models import Book

INDEX_PREFIX = "00 - Indice"
ORIGINALS_DIR = "originali"
ORIGINAL_PREFIX = "OR - "


@dataclass
class Page:
    stem: str               # nome del file senza .md
    chapters: list[int]     # indici dei capitoli contenuti nel file


def index_name(title: str) -> str:
    """Nome (senza .md) dell'indice: contiene il titolo per essere univoco."""
    return f"{INDEX_PREFIX} - {sanitize_name(title)}"


def original_name(stem: str) -> str:
    """Nome (senza .md) dell'originale che corrisponde a una copia di lavoro."""
    return ORIGINAL_PREFIX + stem


def plan_pages(book: Book, group_size: int) -> list[Page]:
    chapters = book.chapters
    total = len(chapters)
    book_slug = sanitize_name(book.metadata.title, max_len=30)
    if group_size == 1:
        width = max(2, len(str(total)))
        pages = []
        for n, ch in enumerate(chapters, 1):
            ch_title = sanitize_name(ch.title, max_len=40)
            stem = f"{n:0{width}d} - {book_slug} - {ch_title}"
            pages.append(Page(stem, [n - 1]))
        return pages
    size = total if group_size == 0 else group_size
    chunks = [list(range(start, min(start + size, total))) for start in range(0, total, size)]
    if len(chunks) == 1:
        return [Page(f"01 - {sanitize_name(book.metadata.title)}", chunks[0])]
    width = max(2, len(str(len(chunks))))
    pages = []
    for k, idx in enumerate(chunks, 1):
        first, last = idx[0] + 1, idx[-1] + 1
        span = f"{first}-{last}" if first != last else f"{first}"
        first_title = sanitize_name(chapters[idx[0]].title, max_len=35)
        pages.append(Page(f"{k:0{width}d} - {book_slug} - {first_title} ({span})", idx))
    return pages
