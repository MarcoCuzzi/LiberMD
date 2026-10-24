"""
engine - Motore di conversione EPUB -> Markdown.

Dall'esterno basta importare da qui:

    from engine import convert, EpubError

I dettagli di ogni parte sono nei file della cartella (vedi engine_pipeline.py).
"""
from .engine_pipeline import convert
from .engine_results import ConvertReport, EpubError

__all__ = ["convert", "ConvertReport", "EpubError"]
