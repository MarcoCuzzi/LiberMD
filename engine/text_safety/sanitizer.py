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
    clean_heading(testo)      testo sicuro per un'ancora [[nota#titoletto]]
    section_heading(n, w, t)  titoletto di una sezione (es. "03 - Titolo"), a cui si puo' puntare con [[nota#titoletto]]
    clean_tag(testo)          tag valido per Obsidian (senza # e senza spazi)
    clean_tags(lista)         ripulisce una lista di tag: (validi senza doppioni, scartati)
    truncate_words(testo, n)  accorcia senza spezzare l'ultima parola
"""
from __future__ import annotations

import html
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
    text = re.sub(r"<[^>]+>", "", text)                # <sup> ecc. generati
    text = re.sub(r"(?<!\\)[*`~]", "", text)           # marcatori generati, non quelli escapati
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
    name = html.unescape(name)
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
    text = html.unescape(text)
    return re.sub(r"\s+", " ", re.sub(r"[\[\]|#^]", " ", text)).strip()


# ----------------------------------------------------------------------------
# Tag
# ----------------------------------------------------------------------------

_TAG_FORBIDDEN = re.compile(r"[^\w/-]+")


def clean_tag(text: str) -> str:
    """
    Tag valido per Obsidian: niente '#', niente spazi (diventano '-'), solo lettere,
    numeri, '_', '-' e '/' (per i tag annidati, es. 'libri/saggi').
    Ritorna "" se non resta un tag valido (vuoto o senza nemmeno una lettera).
    """
    tag = text.strip().lstrip("#").strip()
    tag = re.sub(r"\s+", "-", tag)
    tag = _TAG_FORBIDDEN.sub("", tag)
    tag = re.sub(r"/{2,}", "/", tag).strip("/-")
    return tag if re.search(r"[^\W\d_]", tag) else ""


def clean_tags(tags) -> tuple[list[str], list[str]]:
    """Ripulisce una lista di tag. Ritorna (tag validi senza doppioni, testi scartati)."""
    good: list[str] = []
    dropped: list[str] = []
    for raw in tags:
        tag = clean_tag(raw)
        if not tag:
            if raw.strip():
                dropped.append(raw.strip())
        elif tag.lower() not in {g.lower() for g in good}:
            good.append(tag)
    return good, dropped


# ----------------------------------------------------------------------------
# Titoletti delle sezioni (quando piu' capitoli stanno nello stesso file)
# ----------------------------------------------------------------------------

_HEADING_FORBIDDEN = re.compile(r'[\[\]|#^/\\*_~`$<>:]|%%|==')


def clean_heading(text: str) -> str:
    """
    Testo sicuro per un titoletto a cui punta un collegamento [[nota#titoletto]]:
    Obsidian non accetta caratteri strutturali (# | ^ / [ ] \\) e formattazioni inline (* _ ~ ` $ == < >).
    Decodifica le entita' HTML e rimuove tag residui per mantenere identita' esatta tra link e intestazione.
    """
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s*:\s*", " - ", text)
    text = _HEADING_FORBIDDEN.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip(" .-_,;")


def section_heading(number: int, width: int, title: str) -> str:
    """Titoletto di una sezione: numero capitolo + titolo ripulito e troncato senza spezzare parole."""
    cleaned = clean_heading(title)
    short = truncate_words(cleaned, 80).strip(" .-_,;")
    return f"{number:0{width}d} - {short or 'Senza titolo'}"