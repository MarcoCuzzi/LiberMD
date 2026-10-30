"""
disk.py - Operazioni "pratiche" sul disco: backup, originali, immagini, guide.

Qui non c'e' logica sul contenuto delle pagine: solo copiare, creare cartelle e scrivere file.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from engine.engine_book_models import Book

BACKUP_DIR_NAME = "backup"
GUIDE_DIR_SRC = Path(__file__).resolve().parents[2] / "guide"


def backup_existing_working_files(out_dir: Path) -> Optional[Path]:
    """Crea una cartella di backup timestampata dentro <cartella_libro>/backup/"""
    existing_md = [
        f for f in out_dir.glob("*.md")
        if f.is_file() and not f.name.startswith("LiberMD - Log")
    ]
    if not existing_md:
        return None

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_target = out_dir / BACKUP_DIR_NAME / timestamp
    backup_target.mkdir(parents=True, exist_ok=True)

    for md_file in existing_md:
        shutil.copy2(md_file, backup_target / md_file.name)

    return backup_target


def write_original(path: Path, text: str) -> None:
    """Scrive un originale (rendendolo scrivibile se era stato bloccato)."""
    if path.exists():
        os.chmod(path, 0o644)
    path.write_text(text, encoding="utf-8")


def write_media(book: Book, out_dir: Path) -> None:
    """Salva le immagini estratte dall'EPUB in <cartella_libro>/media/."""
    if not book.media:
        return
    media_dir = out_dir / "media"
    media_dir.mkdir(exist_ok=True)
    for name, data in book.media.items():
        (media_dir / name).write_bytes(data)


def copy_guides_and_bookmarks(out_dir: Path) -> None:
    """Copia la guida e i segnalibri nella cartella del libro (senza sovrascrivere)."""
    if not GUIDE_DIR_SRC.is_dir():
        return
    guide_file = GUIDE_DIR_SRC / "Guida-LiberMD.md"
    if guide_file.is_file():
        dst_guide = out_dir / "Guida-LiberMD.md"
        if not dst_guide.exists():
            shutil.copy2(guide_file, dst_guide)
    bm_src_dir = GUIDE_DIR_SRC / "bookmarks"
    if bm_src_dir.is_dir():
        dst_bm_dir = out_dir / "bookmarks"
        if not dst_bm_dir.exists():
            shutil.copytree(bm_src_dir, dst_bm_dir)
