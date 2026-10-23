"""Nota indice (MOC) del libro: frontmatter YAML + elenco dei capitoli."""
from __future__ import annotations

from ...models import BookMetadata, Chapter
from ...naming import clean_alias
from ...textutils import yaml_str


def render_index(meta: BookMetadata, chapters: list[Chapter], stems: list[str]) -> str:
    """L'indice (MOC) e' l'UNICO file che contiene i metadati del libro."""
    lines = ["---", f"titolo: {yaml_str(meta.title)}"]
    if meta.authors:
        lines.append("autore:")
        lines += [f"  - {yaml_str(a)}" for a in meta.authors]
    if meta.publisher:
        lines.append(f"editore: {yaml_str(meta.publisher)}")
    lines += ["tags:", "  - tipo/libro", "  - stato/da-leggere", "---", "", f"# {meta.title}", ""]

    if meta.authors:
        lines.append(f"**Autore:** {', '.join(meta.authors)}  ")
    if meta.publisher:
        lines.append(f"**Editore:** {meta.publisher}  ")
    if meta.authors or meta.publisher:
        lines.append("")

    lines += ["## Indice dei capitoli", ""]
    for stem, chapter in zip(stems, chapters):
        lines.append(f"- [[{stem}|{clean_alias(chapter.title) or stem}]]")
    return "\n".join(lines) + "\n"
