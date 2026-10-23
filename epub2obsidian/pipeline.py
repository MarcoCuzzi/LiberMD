"""Pipeline completa: legge un EPUB e scrive la cartella Obsidian.

Per aggiungere un formato nuovo: scegli qui un altro lettore/scrittore.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .naming import sanitize_name
from .readers.epub import read_epub
from .writers.obsidian import write_obsidian

log = logging.getLogger("epub_to_obsidian")


def convert_epub(epub_path: Path, out_base: Path) -> Path:
    log.info("--> [1/3] Lettura di %s", epub_path)
    book = read_epub(epub_path)
    meta = book.metadata
    log.info("    Titolo: %s", meta.title)
    log.info("    Autore: %s", ", ".join(meta.authors) or "(non indicato)")
    log.info("    Editore: %s", meta.publisher or "(non indicato)")
    log.info("--> [2/3] %d capitoli, %d immagini", len(book.chapters), len(book.media))

    out_dir = out_base / sanitize_name(epub_path.stem)
    log.info("--> [3/3] Scrittura in %s", out_dir)
    write_obsidian(book, out_dir)
    return out_dir
