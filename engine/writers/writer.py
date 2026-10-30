"""
writer.py - Coordinatore: scrive o aggiorna un libro su disco.

Riceve un libro gia' convertito (oggetto Book) e lancia i passaggi nell'ordine giusto.
Il lavoro vero e' nei moduli accanto a questo file:

    naming.py        nomi dei file e raggruppamento dei capitoli in pagine
    disk.py          backup, originali, immagini, guide
    vault.py         vault di Obsidian: stile CSS e link obsidian://
    index_page.py    pagina dell'indice (e caselle gia' spuntate)
    note_merge.py    fusione frase per frase per non perdere le note dell'utente

Gli originali in `originali/` vengono sempre rigenerati in modo pulito e fedele all'EPUB.
Le copie di lavoro esistenti vengono aggiornate integrando le note (salvo overwrite_working).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from book_design.nav import (
    BARS_ALL,
    COPY,
    ORIGINAL,
    NavContext,
    Section,
    dress,
    dress_sections,
)
from ..text_safety.sanitizer import section_heading
from .disk import (
    backup_existing_working_files,
    copy_guides_and_bookmarks,
    write_media,
    write_original,
)
from .index_page import extract_checked_boxes, render_index
from .naming import ORIGINALS_DIR, index_name, original_name, plan_pages  # ORIGINALS_DIR: usato da engine_pipeline
from .note_merge import merge_sections_grouped, merge_single_chapter
from .vault import install_style, make_uri_maker

if TYPE_CHECKING:
    from engine.engine_book_models import Book


@dataclass
class WriteResult:
    kept_existing: int      # file di lavoro aggiornati integrando le note preesistenti
    style_path: Path        # dove si trova (o e' stato messo) il file di stile
    style_in_vault: bool    # True se e' nella cartella .obsidian/snippets/ del vault
    files: int              # quanti file di testo (per versione) contiene la cartella del libro


def write_book(book: Book, out_dir: Path, overwrite_working: bool = False,
               tags: tuple[str, ...] | list[str] = (), nav_uri: bool = False,
               vault_name: Optional[str] = None, with_originals: bool = True,
               group_size: int = 0, bars: str = BARS_ALL) -> WriteResult:
    tags = tuple(tags)
    title = book.metadata.title
    index_stem = index_name(title)
    out_dir.mkdir(parents=True, exist_ok=True)

    backup_existing_working_files(out_dir)

    originals_dir = out_dir / ORIGINALS_DIR
    if with_originals:
        originals_dir.mkdir(exist_ok=True)

    write_media(book, out_dir)

    total = len(book.chapters)
    grouped = group_size != 1
    pages = plan_pages(book, group_size)
    width = max(2, len(str(total)))
    headings = [section_heading(n, width, ch.title) for n, ch in enumerate(book.chapters, 1)]

    copy_targets = [""] * total
    orig_targets = [""] * total
    for page in pages:
        for i in page.chapters:
            suffix = f"#{headings[i]}" if grouped else ""
            copy_targets[i] = page.stem + suffix
            orig_targets[i] = f"{ORIGINALS_DIR}/{original_name(page.stem)}{suffix}"

    orig_stems_set = {original_name(p.stem) for p in pages}
    to_url = make_uri_maker(out_dir, vault_name, orig_stems_set) if nav_uri else None

    def make_ctx(kind: str, i: int) -> NavContext:
        mine, other = (orig_targets, copy_targets) if kind == ORIGINAL else (copy_targets, orig_targets)
        idx_target = f"../{index_stem}" if kind == ORIGINAL else index_stem
        return NavContext(kind, idx_target, mine[i - 1] if i > 0 else None,
                          mine[i + 1] if i < total - 1 else None,
                          other[i] if (kind == ORIGINAL or with_originals) else None,
                          book_title=title, tags=tags, to_url=to_url)

    def file_ctx(kind: str, k: int) -> NavContext:
        mine = [f"{ORIGINALS_DIR}/{original_name(p.stem)}" if kind == ORIGINAL else p.stem for p in pages]
        other = [p.stem if kind == ORIGINAL else f"{ORIGINALS_DIR}/{original_name(p.stem)}" for p in pages]
        idx_target = f"../{index_stem}" if kind == ORIGINAL else index_stem
        return NavContext(kind, idx_target, mine[k - 1] if k > 0 else None,
                          mine[k + 1] if k < len(pages) - 1 else None,
                          other[k] if (kind == ORIGINAL or with_originals) else None,
                          book_title=title, tags=tags, to_url=to_url)

    kept = 0
    for k, page in enumerate(pages):
        if with_originals:
            texts_orig = [book.chapters[i].markdown.replace("](media/", "](../media/") for i in page.chapters]
            if grouped:
                content_orig = dress_sections(
                    [Section(headings[i], t, make_ctx(ORIGINAL, i)) for i, t in zip(page.chapters, texts_orig)],
                    bars, file_ctx(ORIGINAL, k))
            else:
                content_orig = dress(texts_orig[0], make_ctx(ORIGINAL, page.chapters[0]), bars)
            write_original(originals_dir / f"{original_name(page.stem)}.md", content_orig)

        file_path = out_dir / f"{page.stem}.md"
        sections_gen = [Section(headings[i], book.chapters[i].markdown, make_ctx(COPY, i)) for i in page.chapters]

        if file_path.exists() and not overwrite_working:
            old_content = file_path.read_text(encoding="utf-8")
            if grouped:
                final_content = merge_sections_grouped(old_content, sections_gen, bars, file_ctx(COPY, k))
            else:
                final_content = merge_single_chapter(old_content, sections_gen[0].markdown,
                                                     make_ctx(COPY, page.chapters[0]), bars)
            kept += 1
        else:
            if grouped:
                final_content = dress_sections(sections_gen, bars, file_ctx(COPY, k))
            else:
                final_content = dress(sections_gen[0].markdown, make_ctx(COPY, page.chapters[0]), bars)

        file_path.write_text(final_content, encoding="utf-8")

    index_path = out_dir / f"{index_stem}.md"
    checked = set()
    if index_path.exists() and not overwrite_working:
        checked = extract_checked_boxes(index_path.read_text(encoding="utf-8"))
        kept += 1

    index_content = render_index(book.metadata, book.chapters, copy_targets, orig_targets,
                                 tags, with_originals, checklist=grouped and len(pages) == 1,
                                 checked_indices=checked)
    index_path.write_text(index_content, encoding="utf-8")

    style_path, in_vault = install_style(out_dir)
    copy_guides_and_bookmarks(out_dir)

    return WriteResult(kept_existing=kept, style_path=style_path, style_in_vault=in_vault, files=len(pages))
