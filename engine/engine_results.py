"""
engine_results.py - Cio' che il motore restituisce o segnala: esito ed errori.

    ConvertReport     il riepilogo finale di convert(), pronto da mostrare in un'interfaccia
    EpubError         errore "atteso" (file mancante, EPUB non valido...) con messaggio leggibile
    ProgressCallback  tipo della funzione che riceve i messaggi di avanzamento

I dati del libro (Book, Chapter, BookMetadata) sono in engine_book_models.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


@dataclass
class ConvertReport:
    """Risultato di convert(): tutto cio' che un'interfaccia puo' voler mostrare."""
    out_dir: Path
    originals_dir: Optional[Path]       # None se si e' scelto "senza originali"
    title: str
    authors: list[str]
    publisher: str
    chapters: int
    images: int
    skipped_pages: int
    warnings: list[str]
    kept_existing: int = 0     # file di lavoro gia' presenti, lasciati intatti
    style_path: Optional[Path] = None   # file di stile LiberMD.css
    style_in_vault: bool = False        # True se e' gia' nella cartella .obsidian/snippets/
    tags: list[str] = field(default_factory=list)   # tag aggiunti a tutte le pagine
    files: int = 0                      # file di testo creati per ogni versione (originali / copie)


class EpubError(Exception):
    """Errore "atteso" (file mancante, EPUB non valido...). Il messaggio e' leggibile."""


ProgressCallback = Callable[[str], None]
