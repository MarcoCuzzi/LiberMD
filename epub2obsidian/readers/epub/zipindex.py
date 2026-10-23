"""Ricerca tollerante dei file dentro lo ZIP dell'EPUB."""
from __future__ import annotations

import posixpath
from typing import Optional


class _ZipIndex:
    """Ricerca tollerante dei file nello ZIP (maiuscole/minuscole, percorsi imprecisi)."""

    def __init__(self, names: list[str]):
        self.names = set(names)
        self.lower = {n.lower(): n for n in names}
        self.by_basename: dict[str, str] = {}
        for n in names:
            self.by_basename.setdefault(posixpath.basename(n).lower(), n)

    def find(self, path: str) -> Optional[str]:
        if path in self.names:
            return path
        if path.lower() in self.lower:
            return self.lower[path.lower()]
        return self.by_basename.get(posixpath.basename(path).lower())
