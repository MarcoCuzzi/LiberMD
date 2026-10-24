"""
nav.py - Maschera di navigazione: da' a ogni capitolo l'aspetto di una pagina di libro.

Riceve il testo di un capitolo e lo "veste":

    ---
    cssclasses: [libermd, libermd-copia]     <- dice a Obsidian quale stile usare
    ---
    > [!libermd-nav] <- Precedente · Indice · Originale · Successivo ->

    ...testo del capitolo...

    > [!libermd-nav] <- Precedente · Indice · Originale · Successivo ->

La barra di navigazione e' un "callout" di Obsidian, quindi anche SENZA lo stile
installato appare come un riquadro con i collegamenti. Con lo stile (LiberMD.css)
diventa una barra sottile e la pagina prende l'aspetto di un libro.

Due versioni di ogni capitolo:
    COPIA      la versione dell'utente: avanti/indietro tra le copie + link all'ORIGINALE
    ORIGINALE  il testo intatto: avanti/indietro tra gli originali + link alla COPIA

Questo file non sa come si chiamano i file su disco: riceve i nomi gia' pronti
(NavContext) e produce solo testo. Di nomi e cartelle si occupa writer.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

COPY = "copia"
ORIGINAL = "originale"

CSS_CLASS = "libermd"
NAV_CALLOUT = "libermd-nav"
CSS_FILE_NAME = "LiberMD.css"


@dataclass
class NavContext:
    kind: str                    # COPY oppure ORIGINAL
    index_stem: str              # nome (senza .md) dell'indice
    prev_stem: Optional[str]     # capitolo precedente, della STESSA versione (None se e' il primo)
    next_stem: Optional[str]     # capitolo successivo, della STESSA versione (None se e' l'ultimo)
    other_stem: str              # lo stesso capitolo nell'ALTRA versione


def nav_bar(ctx: NavContext) -> str:
    """La riga di navigazione, scritta come callout di Obsidian."""
    prev_link = f"[[{ctx.prev_stem}|← Precedente]]" if ctx.prev_stem else "← Inizio"
    next_link = f"[[{ctx.next_stem}|Successivo →]]" if ctx.next_stem else "Fine →"
    index_link = f"[[{ctx.index_stem}|Indice]]"
    other_label = "La mia copia" if ctx.kind == ORIGINAL else "Originale"
    other_link = f"[[{ctx.other_stem}|{other_label}]]"
    return f"> [!{NAV_CALLOUT}] {prev_link} · {index_link} · {other_link} · {next_link}"


def frontmatter(kind: str) -> str:
    """Proprieta' che attivano lo stile; 'kind' permette di distinguere copie e originali."""
    return f"---\ncssclasses:\n  - {CSS_CLASS}\n  - {CSS_CLASS}-{kind}\n---\n"


def dress(markdown: str, ctx: NavContext) -> str:
    """Testo di un capitolo -> contenuto completo del file."""
    bar = nav_bar(ctx)
    return f"{frontmatter(ctx.kind)}\n{bar}\n\n{markdown}\n\n{bar}\n"


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
"""
