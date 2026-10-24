"""
sanitizer.py - Tratta il testo dell'EPUB come TESTO, mai come comandi.

Un libro puo' contenere caratteri che Markdown o Obsidian interpreterebbero:

    [1]  [[2]]  [3](x)  [^4]  [!nota]     -> link, wikilink, note a piedi pagina, callout
    #capitolo  #1                         -> tag di Obsidian (e titoli a inizio riga)
    *  _  ~~  ==  %%  `                   -> corsivo/grassetto, barrato, evidenziato,
                                             commenti di Obsidian, codice
    $5 ... $10                            -> formule matematiche
    <b>  &copy;                           -> HTML ed entita' scritte come testo
    1.  -  >  ---   (a inizio riga)       -> elenchi, citazioni, linee orizzontali

La regola e' una sola: davanti a ogni carattere "pericoloso" si mette una barra
rovesciata (\\). Obsidian la nasconde e mostra il carattere cosi' com'e'.

Il modulo non dipende da nient'altro: contiene solo funzioni pure su stringhe.

    escape_text(frammento)    per ogni pezzo di testo dentro una riga
    escape_line_start(riga)   per l'inizio di ogni riga
    unescape(testo)           per tornare al testo originale (titoli)
    plain_title(markdown)     titolo "vero" ricavato da un testo Markdown

    sanitize_name(titolo)     nome sicuro per un file di nota (e per i [[link]])
    sanitize_filename(nome)   nome sicuro per un'immagine
    clean_alias(testo)        alias sicuro per [[nota|alias]]
    truncate_words(testo, n)  accorcia senza spezzare l'ultima parola
"""
from __future__ import annotations

import posixpath
import re

# Un solo passaggio sul testo: ogni gruppo e' una "casistica" da trattare in modo specifico.
_INLINE = re.compile(
    r"""
      (?P<always>[\\\[\]*`$^<])        # barra, parentesi quadre, asterisco, apice inverso, $, ^, <
    | (?P<pair>%{2,}|={2,}|~{2,})      # %% commento, == evidenziato, ~~ barrato
    | (?P<hash>(?<!\w)\#)              # # NON attaccato a una parola: tag e titoli
    | (?P<under>_)                     # _ (valutato a mano: ok dentro una parola)
    | (?P<entity>&(?=\#?\w+;))         # &copy; scritto come testo
    """,
    re.VERBOSE,
)


def _escape_match(match: re.Match) -> str:
    group, text = match.lastgroup, match.group()
    if group == "under":
        s, i = match.string, match.start()
        before = s[i - 1] if i > 0 else ""
        after = s[i + 1] if i + 1 < len(s) else ""
        if before.isalnum() and after.isalnum():
            return text  # snake_case: dentro una parola non e' corsivo
        return "\\_"
    return "".join("\\" + ch for ch in text)  # ogni carattere della casistica


def escape_text(text: str) -> str:
    """Rende sicuro un frammento di testo da inserire dentro una riga Markdown."""
    return _INLINE.sub(_escape_match, text)


# Casistiche valide solo a inizio riga (dopo i caratteri gia' sistemati da escape_text).
_LINE_START_RULES = [
    (re.compile(r"^(\s*)(\d{1,9})([.)])(?=\s|$)"), r"\1\2\\\3"),   # "1. " / "1) "  -> elenco numerato
    (re.compile(r"^(\s*)([-+])(?=\s|$)"), r"\1\\\2"),              # "- " / "+ "    -> elenco puntato
    (re.compile(r"^(\s*)>"), r"\1\\>"),                            # ">"            -> citazione
    (re.compile(r"^(\s*)-(?=(?:\s*-){2,}\s*$)"), r"\1\\-"),        # "---"          -> linea orizzontale
]


def escape_line_start(line: str) -> str:
    """Neutralizza le sintassi che Markdown riconosce solo all'inizio di una riga."""
    for pattern, replacement in _LINE_START_RULES:
        line = pattern.sub(replacement, line, count=1)
    return line


_BACKSLASH_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")


def unescape(text: str) -> str:
    """Inverso di escape_text/escape_line_start: toglie la barra davanti alla punteggiatura."""
    return _BACKSLASH_ESCAPE.sub(r"\1", text)


# ----------------------------------------------------------------------------
# Titoli
# ----------------------------------------------------------------------------

def plain_title(text: str) -> str:
    """
    Dal testo Markdown ricava un titolo "vero": toglie immagini, tag HTML ed enfasi
    generati dal convertitore, poi le barre di escape messe dal sanificatore.
    """
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)   # immagini generate (quelle nel testo sono escapate)
    text = re.sub(r"<[^>]+>", "", text)                    # <sup> ecc. generati
    text = re.sub(r"(?<!\\)[*`~]", "", text)               # marcatori generati, non quelli escapati
    return re.sub(r"\s+", " ", unescape(text)).strip()


# ----------------------------------------------------------------------------
# Nomi di file e alias dei link
# ----------------------------------------------------------------------------

# Caratteri vietati nei nomi file o che darebbero problemi a Obsidian.
_FORBIDDEN_NAME_CHARS = re.compile(r'[\\/*?:"<>|#^\[\]\x00-\x1f]')


def truncate_words(text: str, limit: int) -> str:
    """Accorcia a `limit` caratteri senza spezzare l'ultima parola."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut and text[limit] != " ":
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:.-")


def sanitize_name(name: str, max_len: int = 60) -> str:
    """Nome sicuro per un file di nota."""
    name = _FORBIDDEN_NAME_CHARS.sub("", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return truncate_words(name, max_len).strip(" .") or "Senza titolo"


def sanitize_filename(name: str) -> str:
    """Nome sicuro per un'immagine: niente spazi, niente caratteri strani."""
    stem, ext = posixpath.splitext(posixpath.basename(name))
    stem = re.sub(r"[^\w\-.]+", "_", stem).strip("._") or "img"
    return stem + ext.lower()


def clean_alias(text: str) -> str:
    """Testo sicuro da usare come alias in [[nota|alias]]."""
    return re.sub(r"\s+", " ", re.sub(r"[\[\]|#^]", " ", text)).strip()
