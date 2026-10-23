"""Scrittore Book -> cartella Obsidian (note .md, indice, cartella media)."""
from __future__ import annotations

from pathlib import Path

from ...models import Book
from ...naming import sanitize_name
from .chapter_note import render_chapter
from .constants import INDEX_STEM
from .index_note import render_index


def write_obsidian(book: Book, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    if book.media:
        media_dir = out_dir / "media"
        media_dir.mkdir(exist_ok=True)
        for name, data in book.media.items():
            (media_dir / name).write_bytes(data)

    total = len(book.chapters)
    width = max(2, len(str(total)))
    stems = [f"{i:0{width}d} - {sanitize_name(ch.title)}" for i, ch in enumerate(book.chapters, 1)]

    for i, (stem, chapter) in enumerate(zip(stems, book.chapters)):
        content = render_chapter(chapter.markdown, stems, i)
        (out_dir / f"{stem}.md").write_text(content, encoding="utf-8")

    (out_dir / f"{INDEX_STEM}.md").write_text(
        render_index(book.metadata, book.chapters, stems), encoding="utf-8"
    )
