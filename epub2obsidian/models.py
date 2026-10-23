"""Modello dati comune, indipendente dal formato di input e di output.

Lettori (EPUB, domani PDF...) PRODUCONO un `Book`; scrittori (Obsidian...) lo CONSUMANO.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BookMetadata:
    title: str = ""
    authors: list[str] = field(default_factory=list)
    publisher: str = ""


@dataclass
class Chapter:
    title: str
    markdown: str


@dataclass
class Book:
    metadata: BookMetadata
    chapters: list[Chapter]
    media: dict[str, bytes]  # nome file sicuro -> contenuto
