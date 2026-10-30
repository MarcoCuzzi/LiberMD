"""
writer.py - Scrive o aggiorna un libro su disco con gestione copie originali e di lavoro.

Riceve un libro gia' convertito (oggetto Book) e si occupa di salvarlo su disco:
- Crea automaticamente un backup timestampato in `backup/` prima di ogni aggiornamento.
- Allineamento a livello di singole frasi / periodi (sentence-level diff):
  anche se due paragrafi prima staccati vengono fusi in uno solo (o viceversa),
  le evidenziazioni (==testo==) e i wikilink ([[nota]]) vengono riconosciuti e trapiantati
  esattamente nella frase unificata, senza perdere ne' la nuova impaginazione ne' le tue note.
- Gli originali in `originali/` vengono sempre rigenerati in modo pulito e fedele all'EPUB.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional
from urllib.parse import quote

from book_design.nav import (
    BARS_ALL,
    BARS_NONE,
    COPY,
    CSS_CLASS,
    CSS_FILE_NAME,
    CSS_TEXT,
    ORIGINAL,
    NavContext,
    Section,
    dress,
    dress_sections,
    frontmatter,
    nav_bar,
)
from ..text_safety.sanitizer import clean_alias, escape_text, sanitize_name, section_heading

if TYPE_CHECKING:
    from engine.engine_book_models import Book, BookMetadata, Chapter

INDEX_PREFIX = "00 - Indice"
ORIGINALS_DIR = "originali"
ORIGINAL_PREFIX = "OR - "
BACKUP_DIR_NAME = "backup"
GUIDE_DIR_SRC = Path(__file__).resolve().parents[2] / "guide"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
# FIX: le parentesi quadre del callout vanno escapate, altrimenti [!libermd-nav]
# viene letto come classe di caratteri (un solo carattere tra quelli elencati).
_NAV_BAR_RE = re.compile(r"^> \[!libermd-nav\].*?$\n?", re.MULTILINE)
_WARNING_RE = re.compile(r"^> \[!warning\] Copia originale\n> [^\n]+\n\n?", re.MULTILINE)
_SECTION_HEAD_RE = re.compile(r"^# \d+ - [^\n]*\n*")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…:;»”\"'\)\]])\s+(?=[A-ZÀ-ÖØ-ß0-9\"'«“\(\[])")

# FIX: il vecchio pattern conteneva \vert{} / \Vert{} (residuo LaTeX) che in Python
# causava "bad escape \V". Qui riconosciamo [[nota]] e [[nota|alias]] e teniamo l'alias.
_HIGHLIGHT_RE = re.compile(r"==(.+?)==")
_WIKILINK_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")


@dataclass
class WriteResult:
    kept_existing: int      # file di lavoro aggiornati integrando le note preesistenti
    style_path: Path        # dove si trova (o e' stato messo) il file di stile
    style_in_vault: bool    # True se e' nella cartella .obsidian/snippets/ del vault
    files: int              # quanti file di testo (per versione) contiene la cartella del libro


def yaml_str(value: str) -> str:
    """Stringa tra virgolette valida in YAML (JSON e' un sottoinsieme di YAML)."""
    return json.dumps(value, ensure_ascii=False)


def index_name(title: str) -> str:
    """Nome (senza .md) dell'indice: contiene il titolo per essere univoco."""
    return f"{INDEX_PREFIX} - {sanitize_name(title)}"


def original_name(stem: str) -> str:
    """Nome (senza .md) dell'originale che corrisponde a una copia di lavoro."""
    return ORIGINAL_PREFIX + stem


# ----------------------------------------------------------------------------
# Backup preventivo
# ----------------------------------------------------------------------------

def _backup_existing_working_files(out_dir: Path) -> Optional[Path]:
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


# ----------------------------------------------------------------------------
# Allineamento e Diff Merge a livello di Frasi / Periodi
# ----------------------------------------------------------------------------

def _extract_user_body(content: str) -> str:
    """Isola il puro corpo del testo rimuovendo frontmatter e barre di navigazione."""
    text = _FRONTMATTER_RE.sub("", content)
    text = _NAV_BAR_RE.sub("", text)
    text = _WARNING_RE.sub("", text)
    return text.strip()


def _strip_markdown_decorations(text: str) -> str:
    """Rimuove marcatori di evidenziazione e wikilink per facilitare l'allineamento fuzzy."""
    t = _HIGHLIGHT_RE.sub(r"\1", text)
    t = _WIKILINK_RE.sub(r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def _split_into_sentences(text: str) -> list[str]:
    """Divide un testo o paragrafo in frasi conservando i delimitatori."""
    lines = text.splitlines()
    sentences = []
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        if line_str.startswith(("-", "*", ">", "#", "|", "```")):
            sentences.append(line_str)
            continue
        parts = _SENTENCE_SPLIT_RE.split(line_str)
        sentences.extend([p.strip() for p in parts if p.strip()])
    return sentences


def _align_paragraph_sentences(base_para: str, user_text: str) -> str:
    """Estrae le frasi che compongono il paragrafo della nuova base, trova le corrispondenze
    all'interno del testo utente pregresso e ricompone il paragrafo conservando evidenziazioni e link."""
    base_sents = _split_into_sentences(base_para)
    user_sents = _split_into_sentences(user_text)

    if not user_sents or not base_sents:
        return base_para

    clean_base = [_strip_markdown_decorations(s) for s in base_sents]
    clean_user = [_strip_markdown_decorations(s) for s in user_sents]

    matcher = difflib.SequenceMatcher(None, clean_base, clean_user)
    blocks = matcher.get_matching_blocks()
    total_matched = sum(b.size for b in blocks)
    if total_matched == 0:
        return base_para

    merged_sents = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("equal", "replace"):
            merged_sents.extend(user_sents[j1:j2])
        elif tag == "delete":
            merged_sents.extend(base_sents[i1:i2])
        elif tag == "insert":
            merged_sents.extend(user_sents[j1:j2])

    return " ".join(merged_sents) if not base_para.startswith(("-", ">", "#")) else "\n".join(merged_sents)


def _collect_reading_paragraphs(content: str) -> list[str]:
    """Estrae l'elenco sequenziale di tutti i paragrafi del vecchio file escludendo frontmatter e intestazioni."""
    raw = _extract_user_body(content)
    cleaned_lines = []
    for line in raw.splitlines():
        if _SECTION_HEAD_RE.match(line) or (line.startswith("# ") and not line.startswith("## ")):
            continue
        if line.strip() == "---":
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _merge_single_chapter(existing_text: str, new_markdown: str, ctx: NavContext, bars: str) -> str:
    """Fonde il capitolo singolo lavorando a livello di frasi per garantire il trapianto delle annotazioni."""
    user_body = _extract_user_body(existing_text)
    new_paras = [p.strip() for p in new_markdown.split("\n\n") if p.strip()]

    merged_paras = []
    for p in new_paras:
        merged_paras.append(_align_paragraph_sentences(p, user_body))

    final_body = "\n\n".join(merged_paras)
    bar = nav_bar(ctx)
    bottom = f"\n\n{bar}" if bars == BARS_ALL else ""
    return f"{frontmatter(ctx)}\n{bar}\n\n{final_body}{bottom}\n"


def _merge_sections_grouped(existing_text: str, sections: list[Section], bars: str,
                            file_ctx: Optional[NavContext]) -> str:
    """Fonde le sezioni raggruppate allineando le frasi del testo utente pregresso."""
    first = sections[0].ctx
    user_paras = _collect_reading_paragraphs(existing_text)
    user_full_text = "\n\n".join(user_paras)
    user_sents = _split_into_sentences(user_full_text)
    clean_user_sents = [_strip_markdown_decorations(s) for s in user_sents]

    head = f"{nav_bar(file_ctx, compact=True)}\n\n" if bars == BARS_NONE and file_ctx else ""
    blocks = []
    user_cursor = 0
    total_user_sents = len(user_sents)

    for section in sections:
        sec_paras = [p.strip() for p in section.markdown.split("\n\n") if p.strip()]
        if not sec_paras:
            blocks.append(f"# {section.heading}\n\n")
            continue

        merged_paras = []
        for p in sec_paras:
            base_sents = _split_into_sentences(p)
            clean_base_sents = [_strip_markdown_decorations(s) for s in base_sents]

            window_end = min(total_user_sents, user_cursor + len(base_sents) + 20)
            candidate_clean = clean_user_sents[user_cursor:window_end]
            candidate_raw = user_sents[user_cursor:window_end]

            matcher = difflib.SequenceMatcher(None, clean_base_sents, candidate_clean)
            merged_sents = []
            advance = 0

            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag in ("equal", "replace"):
                    merged_sents.extend(candidate_raw[j1:j2])
                    advance = max(advance, j2)
                elif tag == "delete":
                    merged_sents.extend(base_sents[i1:i2])
                elif tag == "insert":
                    merged_sents.extend(candidate_raw[j1:j2])
                    advance = max(advance, j2)

            user_cursor += advance
            merged_paras.append(" ".join(merged_sents) if not p.startswith(("-", ">", "#")) else "\n".join(merged_sents))

        merged_body = "\n\n".join(merged_paras)
        bar = nav_bar(section.ctx)
        top = f"{bar}\n\n" if bars != BARS_NONE else ""
        bottom = f"\n\n{bar}" if bars == BARS_ALL else ""
        blocks.append(f"# {section.heading}\n\n{top}{merged_body}{bottom}")

    return f"{frontmatter(first)}\n{head}" + "\n\n---\n\n".join(blocks) + "\n"


# ----------------------------------------------------------------------------
# Contenuto dell'indice
# ----------------------------------------------------------------------------

def _render_index(meta: BookMetadata, chapters: list[Chapter], targets: list[str],
                  orig_targets: list[str], tags: tuple[str, ...] = (),
                  with_originals: bool = True, checklist: bool = False,
                  checked_indices: Optional[set[int]] = None) -> str:
    checked = checked_indices or set()
    lines = ["---", f"titolo: {yaml_str(meta.title)}"]
    if meta.authors:
        lines.append("autore:")
        lines += [f"  - {yaml_str(a)}" for a in meta.authors]
    if meta.publisher:
        lines.append(f"editore: {yaml_str(meta.publisher)}")
    base_tags = ["tipo/libro", "stato/da-leggere"]
    extra_tags = [t for t in tags if t not in base_tags]
    lines += ["tags:", *[f"  - {t}" for t in base_tags], *[f"  - {yaml_str(t)}" for t in extra_tags],
              "cssclasses:", f"  - {CSS_CLASS}", "---", "", f"# {escape_text(meta.title)}", ""]

    if meta.authors:
        lines.append(f"**Autore:** {escape_text(', '.join(meta.authors))}  ")
    if meta.publisher:
        lines.append(f"**Editore:** {escape_text(meta.publisher)}  ")
    if meta.authors or meta.publisher:
        lines.append("")

    lines += ["## Indice dei capitoli", ""]
    if checklist:
        lines += ["Spunta ogni sezione quando l'hai letta: la prima casella vuota è dove riprendere.", ""]
    for i, chapter in enumerate(chapters):
        alias = clean_alias(chapter.title) or targets[i]
        original_link = f" · [[{orig_targets[i]}|originale]]" if with_originals else ""
        box = ("[x] " if i in checked else "[ ] ") if checklist else ""
        lines.append(f"- {box}[[{targets[i]}|{alias}]]{original_link}")

    lines += ["", "---", "## Strumenti di lettura", ""]
    lines.append("- [[Guida-LiberMD|Guida alla lettura]]")
    lines.append("- [[bookmarks/info_bookmarks|Istruzioni Segnalibri]]")
    return "\n".join(lines) + "\n"


def _extract_checked_boxes(index_content: str) -> set[int]:
    checked = set()
    i = 0
    for line in index_content.splitlines():
        if line.strip().startswith("- ["):
            if line.strip().startswith("- [x]") or line.strip().startswith("- [X]"):
                checked.add(i)
            i += 1
    return checked


# ----------------------------------------------------------------------------
# Scrittura su disco
# ----------------------------------------------------------------------------

def _write_original(path: Path, text: str) -> None:
    if path.exists():
        os.chmod(path, 0o644)
    path.write_text(text, encoding="utf-8")


def _find_vault_root(start: Path) -> Optional[Path]:
    for folder in [start, *start.parents]:
        if (folder / ".obsidian").is_dir():
            return folder
    return None


def _install_style(out_dir: Path) -> tuple[Path, bool]:
    root = _find_vault_root(out_dir.resolve())
    if root is not None:
        target_dir, in_vault = root / ".obsidian" / "snippets", True
        target_dir.mkdir(parents=True, exist_ok=True)
    else:
        target_dir, in_vault = out_dir, False
    path = target_dir / CSS_FILE_NAME
    if not path.exists():
        path.write_text(CSS_TEXT, encoding="utf-8")
    return path, in_vault


def _copy_guides_and_bookmarks(out_dir: Path) -> None:
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


@dataclass
class _Page:
    stem: str
    chapters: list[int]


def _plan_pages(book: Book, group_size: int) -> list[_Page]:
    chapters = book.chapters
    total = len(chapters)
    book_slug = sanitize_name(book.metadata.title, max_len=30)
    if group_size == 1:
        width = max(2, len(str(total)))
        pages = []
        for n, ch in enumerate(chapters, 1):
            ch_title = sanitize_name(ch.title, max_len=40)
            stem = f"{n:0{width}d} - {book_slug} - {ch_title}"
            pages.append(_Page(stem, [n - 1]))
        return pages
    size = total if group_size == 0 else group_size
    chunks = [list(range(start, min(start + size, total))) for start in range(0, total, size)]
    if len(chunks) == 1:
        return [_Page(f"01 - {sanitize_name(book.metadata.title)}", chunks[0])]
    width = max(2, len(str(len(chunks))))
    pages = []
    for k, idx in enumerate(chunks, 1):
        first, last = idx[0] + 1, idx[-1] + 1
        span = f"{first}-{last}" if first != last else f"{first}"
        first_title = sanitize_name(chapters[idx[0]].title, max_len=35)
        pages.append(_Page(f"{k:0{width}d} - {book_slug} - {first_title} ({span})", idx))
    return pages


def _make_uri_maker(out_dir: Path, vault_name: Optional[str], orig_stems: set[str]) -> Callable[[str], str]:
    root = _find_vault_root(out_dir.resolve())
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


def write_book(book: Book, out_dir: Path, overwrite_working: bool = False,
               tags: tuple[str, ...] | list[str] = (), nav_uri: bool = False,
               vault_name: Optional[str] = None, with_originals: bool = True,
               group_size: int = 0, bars: str = BARS_ALL) -> WriteResult:
    tags = tuple(tags)
    title = book.metadata.title
    index_stem = index_name(title)
    out_dir.mkdir(parents=True, exist_ok=True)

    _backup_existing_working_files(out_dir)

    originals_dir = out_dir / ORIGINALS_DIR
    if with_originals:
        originals_dir.mkdir(exist_ok=True)

    if book.media:
        media_dir = out_dir / "media"
        media_dir.mkdir(exist_ok=True)
        for name, data in book.media.items():
            (media_dir / name).write_bytes(data)

    total = len(book.chapters)
    grouped = group_size != 1
    pages = _plan_pages(book, group_size)
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
    to_url = _make_uri_maker(out_dir, vault_name, orig_stems_set) if nav_uri else None

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
            _write_original(originals_dir / f"{original_name(page.stem)}.md", content_orig)

        file_path = out_dir / f"{page.stem}.md"
        sections_gen = [Section(headings[i], book.chapters[i].markdown, make_ctx(COPY, i)) for i in page.chapters]

        if file_path.exists() and not overwrite_working:
            old_content = file_path.read_text(encoding="utf-8")
            if grouped:
                final_content = _merge_sections_grouped(old_content, sections_gen, bars, file_ctx(COPY, k))
            else:
                final_content = _merge_single_chapter(old_content, sections_gen[0].markdown,
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
        checked = _extract_checked_boxes(index_path.read_text(encoding="utf-8"))
        kept += 1

    index_content = _render_index(book.metadata, book.chapters, copy_targets, orig_targets,
                                  tags, with_originals, checklist=grouped and len(pages) == 1,
                                  checked_indices=checked)
    index_path.write_text(index_content, encoding="utf-8")

    style_path, in_vault = _install_style(out_dir)
    _copy_guides_and_bookmarks(out_dir)

    return WriteResult(kept_existing=kept, style_path=style_path, style_in_vault=in_vault, files=len(pages))