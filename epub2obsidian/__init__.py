"""epub2obsidian - converte un EPUB in note Markdown collegate per Obsidian.

Mappa dei moduli (leggi AGENTS.md per i dettagli):
    models, errors, naming, textutils   base comune
    html2md/                            HTML -> Markdown
    readers/epub/                       EPUB -> Book
    writers/obsidian/                   Book -> cartella Obsidian
    pipeline, cli                       collegano tutto
"""
from .models import Book, BookMetadata, Chapter
from .pipeline import convert_epub

__all__ = ["Book", "BookMetadata", "Chapter", "convert_epub"]
