"""
nav.py - Maschera di navigazione: da' a ogni capitolo l'aspetto di una pagina di libro.

Riceve il testo di un capitolo e lo "veste":

    ---
    cssclasses: [libermd, libermd-copia]     <- dice a Obsidian quale stile usare
    libro: [[00 - Indice - Titolo del libro|Titolo del libro]]  <- a quale libro appartiene la pagina
    tags: [...]                              <- "tipo/pagina" (+ "tipo/originale") e i tag scelti dall'utente
    ---
    > [!libermd-nav] <- Precedente · Indice · Originale · Successivo ->

    ...testo del capitolo...

    > [!libermd-nav] <- Precedente · Indice · Originale · Successivo ->

La barra di navigazione e' un "callout" di Obsidian, quindi anche SENZA lo stile
installato appare come un riquadro con i collegamenti. Con lo stile (LiberMD.css)
diventa una barra sottile e la pagina prende l'aspetto di un libro.

Due versioni di ogni capitolo:
    COPIA      la versione dell'utente: avanti/indietro tra le copie + link all'ORIGINALE
    ORIGINALE  il testo intatto: avanti/indietro tra gli originali + link alla COPIA,
               con in piu' un avviso in cima ("questo e' l'originale, scrivi nella copia")

Questo file non sa come si chiamano i file su disco: riceve i nomi gia' pronti
(NavContext) e produce solo testo. Di nomi e cartelle si occupa writer.py.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Optional

from engine.text_safety.sanitizer import clean_alias

COPY = "copia"
ORIGINAL = "originale"

CSS_CLASS = "libermd"
NAV_CALLOUT = "libermd-nav"
NOTICE_CALLOUT = "warning"          # tipo predefinito di Obsidian: ha gia' colore e icona anche senza stile
CSS_FILE_NAME = "LiberMD.css"
PAGE_TAG = "tipo/pagina"            # tag di tutte le pagine dei capitoli (NON dell'indice): per filtrare il grafo
ORIGINAL_TAG = "tipo/originale"     # tag che distingue le pagine originali (per filtrarle)

# Quante barre di navigazione mettere (opzione --barre)
BARS_ALL = "tutte"       # sopra e sotto ogni sezione
BARS_ONE = "una"         # solo sopra ogni sezione
BARS_NONE = "nessuna"    # nessuna barra tra le sezioni: una sola in cima al file (Indice, Originale, file vicini)
BARS_CHOICES = (BARS_ALL, BARS_ONE, BARS_NONE)


@dataclass
class NavContext:
    kind: str                    # COPY oppure ORIGINAL
    index_stem: str              # nome (senza .md) dell'indice
    prev_stem: Optional[str]     # capitolo precedente, della STESSA versione (None se e' il primo)
    next_stem: Optional[str]     # capitolo successivo, della STESSA versione (None se e' l'ultimo)
    other_stem: Optional[str]    # lo stesso capitolo nell'ALTRA versione (None se non ci sono originali)
    book_title: str = ""          # titolo del libro (testo del collegamento all'indice)
    tags: tuple[str, ...] = ()   # tag scelti dall'utente, uguali su tutte le pagine
    to_url: Optional[Callable[[str], str]] = None
                                 # se presente, "Precedente" e "Successivo" diventano link obsidian://
                                 # (nome della nota -> indirizzo) invece di [[collegamenti]]: cosi' NON
                                 # compaiono nel grafo di Obsidian


def _step_link(ctx: NavContext, stem: str, label: str) -> str:
    """Collegamento a un capitolo vicino: [[nota]] (appare nel grafo) oppure obsidian:// (non appare)."""
    if ctx.to_url is not None:
        return f"[{label}]({ctx.to_url(stem)})"
    return f"[[{stem}|{label}]]"


def nav_bar(ctx: NavContext, compact: bool = False) -> str:
    """La riga di navigazione, scritta come callout di Obsidian.
    `compact`: senza Precedente/Successivo quando non ci sono (barra di un file unico)."""
    prev_link = _step_link(ctx, ctx.prev_stem, "← Precedente") if ctx.prev_stem else "← Inizio"
    next_link = _step_link(ctx, ctx.next_stem, "Successivo →") if ctx.next_stem else "Fine →"
    parts = [prev_link, f"[[{ctx.index_stem}|Indice]]"]
    if compact and not ctx.prev_stem:
        parts = parts[1:]
    if ctx.other_stem:                     # senza originali non c'e' il collegamento all'altra versione
        other_label = "La mia copia" if ctx.kind == ORIGINAL else "Originale"
        parts.append(f"[[{ctx.other_stem}|{other_label}]]")
    if not (compact and not ctx.next_stem):
        parts.append(next_link)
    return f"> [!{NAV_CALLOUT}] " + " · ".join(parts)


def original_notice(ctx: NavContext) -> str:
    """Avviso in cima agli ORIGINALI: ricorda di scrivere le note nella copia di lavoro."""
    copy_file = (ctx.other_stem or "").partition("#")[0]      # il file, senza il titoletto
    return (f"> [!{NOTICE_CALLOUT}] Copia originale\n"
            f"> Questo è il testo intatto del libro. Le tue note vanno nella "
            f"[[{copy_file}|tua copia]].\n\n")


def _yaml(value: str) -> str:
    """Stringa tra virgolette valida in YAML."""
    return json.dumps(value, ensure_ascii=False)


def frontmatter(ctx: NavContext) -> str:
    """Proprieta' della pagina: stile (copie e originali si distinguono), libro di appartenenza, tag."""
    alias = clean_alias(ctx.book_title)
    book = f"[[{ctx.index_stem}|{alias}]]" if alias else f"[[{ctx.index_stem}]]"
    lines = ["---", "cssclasses:", f"  - {CSS_CLASS}", f"  - {CSS_CLASS}-{ctx.kind}",
             f"libro: {_yaml(book)}"]
    tags = [PAGE_TAG] + ([ORIGINAL_TAG] if ctx.kind == ORIGINAL else [])
    tags += [t for t in ctx.tags if t not in (PAGE_TAG, ORIGINAL_TAG)]
    lines.append("tags:")
    lines += [f"  - {_yaml(t)}" for t in tags]
    lines.append("---")
    return "\n".join(lines) + "\n"


def dress(markdown: str, ctx: NavContext, bars: str = BARS_ALL) -> str:
    """Testo di un capitolo -> contenuto completo del file.
    Con un capitolo per file la barra in cima serve sempre: "nessuna" vale come "una"."""
    bar = nav_bar(ctx)
    notice = original_notice(ctx) if ctx.kind == ORIGINAL else ""
    bottom = f"\n\n{bar}" if bars == BARS_ALL else ""
    return f"{frontmatter(ctx)}\n{bar}\n\n{notice}{markdown}{bottom}\n"


# ----------------------------------------------------------------------------
# Stile "libro" (frammento CSS di Obsidian)
# ----------------------------------------------------------------------------

CSS_TEXT = """\
/* LiberMD - stile "libro" per le note dei libri convertiti.

   Come attivarlo:
   Obsidian > Impostazioni > Aspetto > Frammenti CSS > attiva "LiberMD".
   (Il file deve stare in <tua cartella Obsidian>/.obsidian/snippets/)

   Per regolarlo basta cambiare i valori qui sotto. */

.libermd {
  --libermd-font: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif;
  --libermd-size: 1.1em;
  --libermd-line: 1.75;
  --file-line-width: 40rem;          /* larghezza della colonna di testo */
}

/* ---- Testo ---------------------------------------------------------- */

.markdown-preview-view.libermd {
  font-family: var(--libermd-font);
  font-size: var(--libermd-size);
  line-height: var(--libermd-line);
}
.markdown-source-view.libermd .cm-content {
  font-family: var(--libermd-font);
  line-height: var(--libermd-line);
}

.markdown-preview-view.libermd p {
  text-align: justify;
  hyphens: auto;
  margin-block: 0 0.9em;
}

/* ---- Titoli --------------------------------------------------------- */

.markdown-preview-view.libermd h1 {
  text-align: center;
  font-size: 1.9em;
  margin: 1.2em 0 1em;
}
.markdown-preview-view.libermd h2,
.markdown-preview-view.libermd h3 {
  margin-top: 1.6em;
}

/* ---- Citazioni e immagini ------------------------------------------- */

.markdown-preview-view.libermd blockquote {
  font-style: italic;
  border-left: 3px solid var(--interactive-accent);
  padding-left: 1em;
}
.markdown-preview-view.libermd img {
  display: block;
  margin: 1em auto;
  max-width: 100%;
}

/* ---- Barra di navigazione (in alto e in basso) ---------------------- */

.libermd .callout[data-callout="libermd-nav"] {
  background: transparent;
  border: none;
  border-top: 1px solid var(--background-modifier-border);
  border-bottom: 1px solid var(--background-modifier-border);
  border-radius: 0;
  margin: 1em 0;
  padding: 0.5em 0;
}
.libermd .callout[data-callout="libermd-nav"] .callout-icon {
  display: none;
}
.libermd .callout[data-callout="libermd-nav"] .callout-title {
  justify-content: center;
  gap: 0.4em;
  font-family: var(--font-interface);
  font-size: 0.85em;
  font-weight: 500;
}

/* ---- Gli ORIGINALI si riconoscono a colpo d'occhio ------------------- */

.markdown-preview-view.libermd-originale {
  background-color: var(--background-secondary);
}
.libermd-originale .callout[data-callout="libermd-nav"] {
  border-color: var(--color-orange, #d08a2e);
}
.libermd-originale .callout[data-callout="warning"] {
  --callout-color: 230, 180, 0;           /* giallo ambra */
}

/* ---- Segnalibri transclusi (nasconde titolo e bordi) ----------------- */

.internal-embed:has(.no-embed-header) {
  border: none !important;
  background: transparent !important;
  padding: 0 !important;
  margin: 1.2em 0 !important;
}

.internal-embed:has(.no-embed-header) .embed-title {
  display: none !important;
}
"""


@dataclass
class Section:
    """Un capitolo dentro un file che ne contiene piu' d'uno."""
    heading: str        # titoletto della sezione (testo, senza i #)
    markdown: str       # testo del capitolo
    ctx: NavContext     # navigazione di QUESTA sezione (i nomi possono contenere "#titoletto")


def dress_sections(sections: list[Section], bars: str = BARS_ALL,
                   file_ctx: Optional[NavContext] = None) -> str:
    """
    Piu' capitoli nello stesso file: ognuno con il suo titoletto e, secondo `bars`, la sua barra di
    navigazione (sopra e sotto / solo sopra / nessuna), separati da una riga. Proprieta' e avviso
    compaiono una sola volta, in cima.
    Con bars="nessuna" l'unica barra e' quella in cima al file (`file_ctx`: Indice, versione
    opposta e, se il libro e' in piu' file, file precedente e successivo).
    """
    first = sections[0].ctx
    notice = original_notice(first) if first.kind == ORIGINAL else ""
    head = f"{nav_bar(file_ctx, compact=True)}\n\n" if bars == BARS_NONE and file_ctx else ""
    blocks = []
    for section in sections:
        bar = nav_bar(section.ctx)
        top = f"{bar}\n\n" if bars != BARS_NONE else ""
        bottom = f"\n\n{bar}" if bars == BARS_ALL else ""
        blocks.append(f"# {section.heading}\n\n{top}{section.markdown}{bottom}")
    return f"{frontmatter(first)}\n{head}{notice}" + "\n\n---\n\n".join(blocks) + "\n"