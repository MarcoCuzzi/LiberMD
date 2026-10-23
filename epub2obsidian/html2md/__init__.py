"""Convertitore HTML -> Markdown. Punto d'ingresso: `html_to_markdown`."""
from __future__ import annotations

from .converter import MarkdownConverter
from .result import ConversionResult

__all__ = ["html_to_markdown", "MarkdownConverter", "ConversionResult"]


def html_to_markdown(html: str, resolve_image=None) -> ConversionResult:
    parser = MarkdownConverter(resolve_image)
    parser.feed(html)
    parser.close()
    return parser.result()
