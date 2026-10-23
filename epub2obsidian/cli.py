"""Interfaccia a riga di comando."""
from __future__ import annotations

import argparse
import logging
import zipfile
from pathlib import Path
from typing import Optional

from .errors import EpubError
from .pipeline import convert_epub

log = logging.getLogger("epub_to_obsidian")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Converte un EPUB in note Markdown per Obsidian.")
    parser.add_argument("epub", type=Path, help="file .epub da convertire")
    parser.add_argument("-o", "--out", type=Path, default=Path("."),
                        help="cartella in cui creare la cartella del libro (default: cartella corrente)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        out_dir = convert_epub(args.epub, args.out)
    except (EpubError, zipfile.BadZipFile) as exc:
        log.error("[!] ERRORE: %s", exc)
        return 1
    log.info("\n[OK] Fatto! Cartella creata: %s", out_dir.resolve())
    return 0
