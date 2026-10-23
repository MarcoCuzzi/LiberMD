"""Estrazione delle immagini e risoluzione dei loro percorsi dentro i capitoli."""
from __future__ import annotations

import posixpath
import zipfile
from typing import Optional
from urllib.parse import unquote

from ...naming import sanitize_filename
from .zipindex import _ZipIndex

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")


def extract_media(z: zipfile.ZipFile, names: list[str]) -> tuple[dict[str, bytes], dict[str, str]]:
    """Estrae le immagini con nomi sicuri e UNICI (due 'fig1.png' in cartelle diverse non si sovrascrivono)."""
    media: dict[str, bytes] = {}
    path_to_name: dict[str, str] = {}
    used: set[str] = set()
    for zip_path in names:
        if not zip_path.lower().endswith(IMAGE_EXTENSIONS):
            continue
        name = sanitize_filename(zip_path)
        stem, ext = posixpath.splitext(name)
        candidate, n = name, 2
        while candidate.lower() in used:
            candidate = f"{stem}-{n}{ext}"
            n += 1
        used.add(candidate.lower())
        media[candidate] = z.read(zip_path)
        path_to_name[zip_path] = candidate
    return media, path_to_name


def make_resolver(chapter_dir: str, index: _ZipIndex, path_to_name: dict[str, str]):
    def resolve(src: str) -> Optional[str]:
        if src.lower().startswith(("data:", "http:", "https:")):
            return None
        rel = unquote(src.split("#")[0].split("?")[0])
        found = index.find(posixpath.normpath(posixpath.join(chapter_dir, rel)))
        return path_to_name.get(found) if found else None
    return resolve
