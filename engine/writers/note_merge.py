"""
note_merge.py - Rigenera una copia di lavoro SENZA perdere le note dell'utente.

Allineamento a livello di singole frasi (sentence-level diff): anche se due paragrafi prima
staccati vengono fusi in uno solo (o viceversa), le evidenziazioni (==testo==) e i wikilink
([[nota]]) vengono riconosciuti e trapiantati nella frase corrispondente del nuovo testo.

Punti di ingresso:

    merge_single_chapter(vecchio_testo, nuovo_markdown, ctx, bars)      un capitolo per file
    merge_sections_grouped(vecchio_testo, sezioni, bars, file_ctx)      piu' sezioni per file

Non scrive su disco: riceve testo e restituisce testo.
"""
from __future__ import annotations

import difflib
import re
from typing import Optional

from book_design.nav import BARS_ALL, BARS_NONE, NavContext, Section, frontmatter, nav_bar

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
# Le parentesi quadre del callout vanno escapate, altrimenti [!libermd-nav]
# verrebbe letto come classe di caratteri (un solo carattere tra quelli elencati).
_NAV_BAR_RE = re.compile(r"^> \[!libermd-nav\].*?$\n?", re.MULTILINE)
_WARNING_RE = re.compile(r"^> \[!warning\] Copia originale\n> [^\n]+\n\n?", re.MULTILINE)
_SECTION_HEAD_RE = re.compile(r"^# \d+ - [^\n]*\n*")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…:;»”\"'\)\]])\s+(?=[A-ZÀ-ÖØ-ß0-9\"'«“\(\[])")
_HIGHLIGHT_RE = re.compile(r"==(.+?)==")
# [[nota]] e [[nota|alias]]: si tiene l'alias, se c'e', altrimenti il nome della nota
_WIKILINK_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")


# ----------------------------------------------------------------------------
# Preparazione del testo
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
    sentences = []
    for line in text.splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        if line_str.startswith(("-", "*", ">", "#", "|", "```")):
            sentences.append(line_str)
            continue
        parts = _SENTENCE_SPLIT_RE.split(line_str)
        sentences.extend([p.strip() for p in parts if p.strip()])
    return sentences


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


def _join_sentences(sentences: list[str], base_para: str) -> str:
    """Rimette insieme le frasi: a capo per liste/citazioni/titoli, con spazio per i paragrafi."""
    return "\n".join(sentences) if base_para.startswith(("-", ">", "#")) else " ".join(sentences)


# ----------------------------------------------------------------------------
# Un capitolo per file
# ----------------------------------------------------------------------------

def _align_paragraph_sentences(base_para: str, user_text: str) -> str:
    """Trova le frasi del paragrafo nuovo dentro il testo utente pregresso e ricompone
    il paragrafo conservando evidenziazioni e link."""
    base_sents = _split_into_sentences(base_para)
    user_sents = _split_into_sentences(user_text)

    if not user_sents or not base_sents:
        return base_para

    clean_base = [_strip_markdown_decorations(s) for s in base_sents]
    clean_user = [_strip_markdown_decorations(s) for s in user_sents]

    matcher = difflib.SequenceMatcher(None, clean_base, clean_user)
    if sum(b.size for b in matcher.get_matching_blocks()) == 0:
        return base_para

    merged_sents = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("equal", "replace", "insert"):
            merged_sents.extend(user_sents[j1:j2])
        elif tag == "delete":
            merged_sents.extend(base_sents[i1:i2])

    return _join_sentences(merged_sents, base_para)


def merge_single_chapter(existing_text: str, new_markdown: str, ctx: NavContext, bars: str) -> str:
    """Fonde il capitolo singolo lavorando a livello di frasi per garantire il trapianto delle annotazioni."""
    user_body = _extract_user_body(existing_text)
    new_paras = [p.strip() for p in new_markdown.split("\n\n") if p.strip()]

    final_body = "\n\n".join(_align_paragraph_sentences(p, user_body) for p in new_paras)
    bar = nav_bar(ctx)
    bottom = f"\n\n{bar}" if bars == BARS_ALL else ""
    return f"{frontmatter(ctx)}\n{bar}\n\n{final_body}{bottom}\n"


# ----------------------------------------------------------------------------
# Piu' sezioni per file
# ----------------------------------------------------------------------------

def merge_sections_grouped(existing_text: str, sections: list[Section], bars: str,
                           file_ctx: Optional[NavContext]) -> str:
    """Fonde le sezioni raggruppate allineando le frasi del testo utente pregresso."""
    first = sections[0].ctx
    user_paras = _collect_reading_paragraphs(existing_text)
    user_sents = _split_into_sentences("\n\n".join(user_paras))
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

            # Si cerca solo in una finestra vicina al punto gia' raggiunto nel vecchio testo
            window_end = min(total_user_sents, user_cursor + len(base_sents) + 20)
            candidate_clean = clean_user_sents[user_cursor:window_end]
            candidate_raw = user_sents[user_cursor:window_end]

            matcher = difflib.SequenceMatcher(None, clean_base_sents, candidate_clean)
            merged_sents = []
            advance = 0

            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag in ("equal", "replace", "insert"):
                    merged_sents.extend(candidate_raw[j1:j2])
                    advance = max(advance, j2)
                elif tag == "delete":
                    merged_sents.extend(base_sents[i1:i2])

            user_cursor += advance
            merged_paras.append(_join_sentences(merged_sents, p))

        merged_body = "\n\n".join(merged_paras)
        bar = nav_bar(section.ctx)
        top = f"{bar}\n\n" if bars != BARS_NONE else ""
        bottom = f"\n\n{bar}" if bars == BARS_ALL else ""
        blocks.append(f"# {section.heading}\n\n{top}{merged_body}{bottom}")

    return f"{frontmatter(first)}\n{head}" + "\n\n---\n\n".join(blocks) + "\n"
