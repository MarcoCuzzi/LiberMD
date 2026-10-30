"""
vault.py - Tutto cio' che riguarda il vault di Obsidian.

    find_vault_root(cartella)   risale le cartelle finche' trova .obsidian/
    install_style(cartella)     mette LiberMD.css in .obsidian/snippets/ (o accanto al libro)
    make_uri_maker(...)         costruisce i link obsidian://open?... per la navigazione "uri"
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote

from book_design.nav import CSS_FILE_NAME, CSS_TEXT

from .naming import ORIGINALS_DIR


def find_vault_root(start: Path) -> Optional[Path]:
    for folder in [start, *start.parents]:
        if (folder / ".obsidian").is_dir():
            return folder
    return None


def install_style(out_dir: Path) -> tuple[Path, bool]:
    """Ritorna (percorso del file di stile, True se e' dentro il vault)."""
    root = find_vault_root(out_dir.resolve())
    if root is not None:
        target_dir, in_vault = root / ".obsidian" / "snippets", True
        target_dir.mkdir(parents=True, exist_ok=True)
    else:
        target_dir, in_vault = out_dir, False
    path = target_dir / CSS_FILE_NAME
    if not path.exists():
        path.write_text(CSS_TEXT, encoding="utf-8")
    return path, in_vault


def make_uri_maker(out_dir: Path, vault_name: Optional[str], orig_stems: set[str]) -> Callable[[str], str]:
    root = find_vault_root(out_dir.resolve())
    prefix = ""
    if root is not None:
        vault_name = vault_name or root.name
        rel = out_dir.resolve().relative_to(root).as_posix()
        prefix = "" if rel == "." else rel + "/"

    def to_url(target: str) -> str:
        stem, hash_sign, heading = target.partition("#")
        folder = f"{ORIGINALS_DIR}/" if ("/" not in stem and stem in orig_stems) else ""
        query = f"vault={quote(vault_name, safe='')}&" if vault_name else ""
        return f"obsidian://open?{query}file={quote(prefix + folder + stem + hash_sign + heading, safe='')}"

    return to_url
