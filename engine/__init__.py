"""
engine - Motore di conversione EPUB -> Markdown.

Dall'esterno basta importare da qui:

    from engine import convert, EpubError

I dettagli di ogni parte sono nei file della cartella (vedi engine_pipeline.py).
"""
from .engine_book_models import BookMetadata
from .engine_log import log_error
from .engine_pipeline import convert
from .readers.engine_reader import read_epub_metadata
from .engine_results import ConvertReport, EpubError

__all__ = ["convert", "read_epub_metadata", "BookMetadata", "ConvertReport", "EpubError", "log_error"]
