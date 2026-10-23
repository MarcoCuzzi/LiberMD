"""Nota di un capitolo: navigazione precedente/indice/successivo + testo."""
from __future__ import annotations

from .constants import INDEX_STEM


def render_chapter(markdown: str, stems: list[str], i: int) -> str:
    """Contenuto del file del capitolo `i` (stems = nomi di tutte le note, in ordine)."""
    total = len(stems)
    prev_link = f"[[{stems[i - 1]}|← Precedente]]" if i > 0 else "← Inizio"
    next_link = f"[[{stems[i + 1]}|Successivo →]]" if i < total - 1 else "Fine →"
    nav = f"{prev_link} | [[{INDEX_STEM}|Indice]] | {next_link}"
    return f"{nav}\n\n---\n\n{markdown}\n\n---\n\n{nav}\n"
