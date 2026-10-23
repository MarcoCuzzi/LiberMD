"""Pulizia di nomi: note, immagini, alias dei link."""
from __future__ import annotations

import posixpath
import re

# Caratteri vietati nei nomi file o che rompono i [[wikilink]] di Obsidian.
_FORBIDDEN_NAME_CHARS = re.compile(r'[\\/*?:"<>|#^\[\]\x00-\x1f]')


def sanitize_name(name: str, max_len: int = 60) -> str:
    """Nome sicuro per una nota (e quindi per i [[link]])."""
    name = _FORBIDDEN_NAME_CHARS.sub("", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:max_len].strip(" .") or "Senza titolo"


def sanitize_filename(name: str) -> str:
    """Nome sicuro per un'immagine: niente spazi, niente caratteri strani."""
    stem, ext = posixpath.splitext(posixpath.basename(name))
    stem = re.sub(r"[^\w\-.]+", "_", stem).strip("._") or "img"
    return stem + ext.lower()


def clean_alias(text: str) -> str:
    """Testo sicuro da usare come alias in [[nota|alias]]."""
    return re.sub(r"\s+", " ", re.sub(r"[\[\]|#^]", " ", text)).strip()
