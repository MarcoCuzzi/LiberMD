"""
index_page.py - La pagina dell'indice del libro.

    render_index(...)           testo Markdown dell'indice (metadati, capitoli, strumenti)
    extract_checked_boxes(...)  quali caselle "letto" l'utente aveva gia' spuntato
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from book_design.nav import CSS_CLASS

from ..text_safety.sanitizer import clean_alias, escape_text

if TYPE_CHECKING:
    from engine.engine_book_models import BookMetadata, Chapter


def yaml_str(value: str) -> str:
    """Stringa tra virgolette valida in YAML (JSON e' un sottoinsieme di YAML)."""
    return json.dumps(value, ensure_ascii=False)


def render_index(meta: BookMetadata, chapters: list[Chapter], targets: list[str],
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


def extract_checked_boxes(index_content: str) -> set[int]:
    checked = set()
    i = 0
    for line in index_content.splitlines():
        if line.strip().startswith("- ["):
            if line.strip().startswith("- [x]") or line.strip().startswith("- [X]"):
                checked.add(i)
            i += 1
    return checked
