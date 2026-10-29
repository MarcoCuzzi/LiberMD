"""
merge.py - Fonde le sezioni troppo piccole in sezioni di lettura piu' grandi.

Un EPUB nato da una scansione OCR ha una "sezione" per ogni pagina di carta (1400 pagine = 1400
capitoli, senza titoli veri). Qui le pagine vicine si uniscono finche' la sezione raggiunge una
dimensione ragionevole.

    chapters, message = merge_chapters(chapters, merge_min)

    merge_min   None = automatico (agisce solo se il libro sembra una scansione a pagine)
                0    = non fondere mai
                N    = fondi finche' ogni sezione ha almeno N caratteri

Regole:
    - una sezione con un VERO titolo (h1-h6) inizia sempre una sezione nuova, a meno che quella
      precedente sia ancora minuscola (meno di un quarto della soglia);
    - se l'ultima frase di una pagina continua nella successiva (niente punto, e la pagina dopo
      comincia con la minuscola) le due parti si saldano nello stesso paragrafo;
    - una sezione senza titolo vero si chiama "Pagine 12-19" (i titoli ricavati dal testo OCR
      sono rumore: testate correnti, numeri di pagina).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Optional

from ..engine_book_models import Chapter

AUTO_TARGET_CHARS = 12000        # circa 6-8 pagine di libro: una seduta di lettura
AUTO_MIN_SECTIONS = 100          # sotto questo numero il libro non sembra una scansione a pagine
AUTO_MEDIAN_CHARS = 2500         # ...e le sezioni devono essere piccole
_SENTENCE_END = tuple(".!?\u2026:;\u00bb\u201d\"')]")


def looks_like_page_scan(chapters: list[Chapter]) -> bool:
    """Tante sezioni, quasi tutte piccole e senza un vero titolo: e' una scansione, non un libro."""
    if len(chapters) < AUTO_MIN_SECTIONS:
        return False
    sizes = sorted(len(c.markdown) for c in chapters)
    untitled = sum(1 for c in chapters if not c.has_heading) / len(chapters)
    return sizes[len(sizes) // 2] < AUTO_MEDIAN_CHARS and untitled >= 0.5


def _join(a: str, b: str) -> str:
    """Unisce due testi; se la frase continua dall'uno all'altro, resta nello stesso paragrafo."""
    a, b = a.rstrip(), b.lstrip()
    last_line = a.rsplit("\n", 1)[-1]
    mid_sentence = (bool(a) and bool(b) and a[-1] not in _SENTENCE_END
                    and last_line[:1] not in ("#", ">", "-", "|", "!")
                    and not last_line[:1].isdigit() and b[0].islower())
    return a + (" " if mid_sentence else "\n\n") + b


def _name(ch: Chapter) -> Chapter:
    """Le sezioni senza vero titolo prendono il nome dalle pagine che contengono."""
    if ch.has_heading or not ch.first_page:
        return ch
    title = (f"Pagina {ch.first_page}" if ch.first_page == ch.last_page
             else f"Pagine {ch.first_page}-{ch.last_page}")
    return replace(ch, title=title)


def merge_chapters(chapters: list[Chapter], merge_min: Optional[int]) -> tuple[list[Chapter], Optional[str]]:
    """Ritorna (capitoli, messaggio per il registro o None se non e' cambiato nulla)."""
    if merge_min == 0 or len(chapters) < 2:
        return chapters, None
    automatic = merge_min is None
    if automatic:
        if not looks_like_page_scan(chapters):
            return chapters, None
        merge_min = AUTO_TARGET_CHARS

    merged: list[Chapter] = []
    for ch in chapters:
        cur = merged[-1] if merged else None
        if cur is not None:
            size = len(cur.markdown)
            starts_new = size >= merge_min or (ch.has_heading and size >= merge_min // 4)
            if not starts_new:
                merged[-1] = Chapter(
                    title=cur.title if cur.has_heading or not ch.has_heading else ch.title,
                    markdown=_join(cur.markdown, ch.markdown),
                    has_heading=cur.has_heading or ch.has_heading,
                    first_page=cur.first_page, last_page=ch.last_page)
                continue
        merged.append(ch)

    merged = [_name(ch) for ch in merged]
    how = "automatica (il libro sembra una scansione a pagine)" if automatic else f"soglia {merge_min} caratteri"
    return merged, f"Sezioni fuse: {len(chapters)} -> {len(merged)} ({how})"
