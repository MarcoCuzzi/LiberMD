"""
writer.py - Scrive un libro su disco come cartella con DUE versioni dei capitoli.

Riceve un libro gia' convertito (oggetto Book, definito in
engine/engine_book_models.py) e decide
come salvarlo: nomi dei file, cartelle, cosa sovrascrivere. Non sa nulla di EPUB
e non converte nulla. L'aspetto delle pagine (barre di navigazione, stile) e' di nav.py.

    Libro/
      00 - Indice - Titolo.md      indice con i metadati e i collegamenti (modificabile)
      01 - Titolo.md  ...          copie di LAVORO: quelle su cui scrivi
      originali/
        OR - 01 - Titolo.md  ...   ORIGINALI: il testo intatto (con un avviso in cima)
      media/                       immagini, condivise dalle due versioni

Il nome dell'originale e' sempre "OR - " + nome della copia di lavoro.

Regole di scrittura:
    - gli ORIGINALI si rigenerano sempre (sono identici) e NON sono bloccati: se ne rovini
      uno, basta rilanciare il programma;
    - con "senza originali" la cartella originali/ non viene creata e spariscono tutti i collegamenti
      agli originali; quelli gia' presenti da conversioni precedenti non vengono cancellati;
    - le copie di LAVORO gia' esistenti NON si toccano (potrebbero contenere le tue note),
      a meno che non si chieda esplicitamente di sovrascriverle;
    - lo STILE (LiberMD.css) non si sovrascrive se esiste: potresti averlo personalizzato.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional
from urllib.parse import quote

from book_design.nav import (COPY, CSS_CLASS, CSS_FILE_NAME, CSS_TEXT, ORIGINAL, NavContext, Section, dress,
                 dress_sections)
from ..text_safety.sanitizer import clean_alias, escape_text, sanitize_name, section_heading

if TYPE_CHECKING:  # solo per i tipi: a runtime eviterebbe un import circolare con il motore (engine/)
    from engine.engine_book_models import Book, BookMetadata, Chapter

INDEX_PREFIX = "00 - Indice"
ORIGINALS_DIR = "originali"
ORIGINAL_PREFIX = "OR - "


@dataclass
class WriteResult:
    kept_existing: int      # file di lavoro gia' presenti, lasciati intatti
    style_path: Path        # dove si trova (o e' stato messo) il file di stile
    style_in_vault: bool    # True se e' nella cartella .obsidian/snippets/ del vault
    files: int              # quanti file di testo (per versione) contiene la cartella del libro


def yaml_str(value: str) -> str:
    """Stringa tra virgolette valida in YAML (JSON e' un sottoinsieme di YAML)."""
    return json.dumps(value, ensure_ascii=False)


def index_name(title: str) -> str:
    """Nome (senza .md) dell'indice: contiene il titolo, cosi' e' unico anche con piu' libri."""
    return f"{INDEX_PREFIX} - {sanitize_name(title)}"


def original_name(stem: str) -> str:
    """Nome (senza .md) dell'originale che corrisponde a una copia di lavoro."""
    return ORIGINAL_PREFIX + stem


# ----------------------------------------------------------------------------
# Contenuto dell'indice
# ----------------------------------------------------------------------------

def _render_index(meta: BookMetadata, chapters: list[Chapter], targets: list[str],
                  orig_targets: list[str], tags: tuple[str, ...] = (),
                  with_originals: bool = True, checklist: bool = False) -> str:
    """L'indice e' l'UNICO file con i metadati del libro, ed e' il punto di ritorno
    sia dalle copie sia dagli originali."""
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
        # PROVA: con tutto il libro in un file l'indice serve anche a ricordare dove si e' arrivati
        lines += ["Spunta ogni sezione quando l'hai letta: la prima casella vuota è dove riprendere.", ""]
    for i, chapter in enumerate(chapters):       # "targets" sono "file" oppure "file#titoletto"
        alias = clean_alias(chapter.title) or targets[i]
        original_link = f" · [[{orig_targets[i]}|originale]]" if with_originals else ""
        box = "[ ] " if checklist else ""
        lines.append(f"- {box}[[{targets[i]}|{alias}]]{original_link}")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------
# Scrittura su disco
# ----------------------------------------------------------------------------

def _write_original(path: Path, text: str) -> None:
    """Scrive un originale. Gli originali si possono sempre rigenerare: sono identici."""
    if path.exists():
        os.chmod(path, 0o644)      # sblocca i file messi in sola lettura da versioni precedenti
    path.write_text(text, encoding="utf-8")


def _write_working(path: Path, text: str, overwrite: bool) -> bool:
    """Scrive una copia di lavoro. Se esiste gia' NON la tocca (potrebbe contenere le tue note).
    Ritorna True se il file e' stato lasciato com'era."""
    if path.exists() and not overwrite:
        return True
    path.write_text(text, encoding="utf-8")
    return False


def _find_vault_root(start: Path) -> Optional[Path]:
    """Risale le cartelle cercando quella che contiene .obsidian (la radice del vault)."""
    for folder in [start, *start.parents]:
        if (folder / ".obsidian").is_dir():
            return folder
    return None


def _install_style(out_dir: Path) -> tuple[Path, bool]:
    """
    Mette LiberMD.css dove Obsidian lo trova (.obsidian/snippets/), se la cartella
    del libro sta dentro un vault. Altrimenti lo lascia accanto al libro.
    Non sovrascrive un file gia' esistente: potresti averlo personalizzato.
    """
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


@dataclass
class _Page:
    """Un file di testo della cartella del libro e i capitoli (posizioni da 0) che contiene."""
    stem: str
    chapters: list[int]


def _plan_pages(book: Book, group_size: int) -> list[_Page]:
    """
    Decide quanti file creare e come si chiamano.
      group_size 1  un capitolo per file:   "01 - Titolo"
      group_size N  N capitoli per file:    "01 - Titolo del primo (1-3)"
      group_size 0  tutto in un solo file:  "01 - Titolo del libro"
    """
    chapters = book.chapters
    total = len(chapters)
    if group_size == 1:
        width = max(2, len(str(total)))
        return [_Page(f"{n:0{width}d} - {sanitize_name(ch.title)}", [n - 1])
                for n, ch in enumerate(chapters, 1)]

    size = total if group_size == 0 else group_size
    chunks = [list(range(start, min(start + size, total))) for start in range(0, total, size)]
    if len(chunks) == 1:
        return [_Page(f"01 - {sanitize_name(book.metadata.title)}", chunks[0])]
    width = max(2, len(str(len(chunks))))
    pages = []
    for k, idx in enumerate(chunks, 1):
        first, last = idx[0] + 1, idx[-1] + 1
        span = f"{first}-{last}" if first != last else f"{first}"
        pages.append(_Page(f"{k:0{width}d} - {sanitize_name(chapters[idx[0]].title)} ({span})", idx))
    return pages


def _make_uri_maker(out_dir: Path, vault_name: Optional[str],
                    orig_stems: set[str]) -> Callable[[str], str]:
    """
    Costruisce la funzione "nome della nota -> indirizzo obsidian://open?...".
    Il nome puo' contenere un titoletto ("file#titoletto"): l'indirizzo punta a quella sezione.
    Se la cartella del libro sta dentro un vault, l'indirizzo contiene il nome del vault e il
    percorso della nota (cosi' funziona anche con piu' libri); altrimenti solo il nome della nota.
    """
    root = _find_vault_root(out_dir.resolve())
    prefix = ""
    if root is not None:
        vault_name = vault_name or root.name
        rel = out_dir.resolve().relative_to(root).as_posix()
        prefix = "" if rel == "." else rel + "/"

    def to_url(target: str) -> str:
        stem, hash_sign, heading = target.partition("#")
        folder = f"{ORIGINALS_DIR}/" if stem in orig_stems else ""
        query = f"vault={quote(vault_name, safe='')}&" if vault_name else ""
        return f"obsidian://open?{query}file={quote(prefix + folder + stem + hash_sign + heading, safe='')}"

    return to_url


def write_book(book: Book, out_dir: Path, overwrite_working: bool = False,
               tags: tuple[str, ...] | list[str] = (), nav_uri: bool = False,
               vault_name: Optional[str] = None, with_originals: bool = True,
               group_size: int = 0) -> WriteResult:
    """Scrive originali + copie di lavoro + indice + immagini + stile.
    `tags` (gia' ripuliti) vengono aggiunti a tutte le pagine.
    `nav_uri`: i link Precedente/Successivo sono indirizzi obsidian:// (non compaiono nel grafo).
    `with_originals`: se False non si scrivono gli originali e non c'e' nessun collegamento ad essi.
    `group_size`: capitoli per file (0 = tutto in un solo file, default; 1 = uno per file); con piu' capitoli
    per file ognuno e' una sezione con il suo titoletto e i collegamenti puntano alla sezione."""
    tags = tuple(tags)
    title = book.metadata.title
    index_stem = index_name(title)
    out_dir.mkdir(parents=True, exist_ok=True)
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

    # Dove si trova ogni capitolo, come si scrive in un collegamento: "file" oppure "file#titoletto"
    copy_targets = [""] * total
    orig_targets = [""] * total
    for page in pages:
        for i in page.chapters:
            suffix = f"#{headings[i]}" if grouped else ""
            copy_targets[i] = page.stem + suffix
            orig_targets[i] = original_name(page.stem) + suffix

    to_url = (_make_uri_maker(out_dir, vault_name, {original_name(p.stem) for p in pages})
              if nav_uri else None)

    def make_ctx(kind: str, i: int) -> NavContext:
        mine, other = (orig_targets, copy_targets) if kind == ORIGINAL else (copy_targets, orig_targets)
        return NavContext(
            kind, index_stem,
            prev_stem=mine[i - 1] if i > 0 else None,
            next_stem=mine[i + 1] if i < total - 1 else None,
            other_stem=other[i] if (kind == ORIGINAL or with_originals) else None,
            book_title=title, tags=tags, to_url=to_url)

    kept = 0
    for page in pages:
        for kind in ([ORIGINAL] if with_originals else []) + [COPY]:
            texts = []
            for i in page.chapters:
                text = book.chapters[i].markdown
                if kind == ORIGINAL:
                    # l'originale sta in una sottocartella, quindi le immagini sono in ../media/
                    text = text.replace("](media/", "](../media/")
                texts.append(text)

            if grouped:
                content = dress_sections([Section(headings[i], text, make_ctx(kind, i))
                                          for i, text in zip(page.chapters, texts)])
            else:
                content = dress(texts[0], make_ctx(kind, page.chapters[0]))

            if kind == ORIGINAL:
                _write_original(originals_dir / f"{original_name(page.stem)}.md", content)
            else:
                kept += _write_working(out_dir / f"{page.stem}.md", content, overwrite_working)

    kept += _write_working(out_dir / f"{index_stem}.md",
                           _render_index(book.metadata, book.chapters, copy_targets, orig_targets,
                                         tags, with_originals,
                                         checklist=grouped and len(pages) == 1),
                           overwrite_working)

    style_path, in_vault = _install_style(out_dir)
    return WriteResult(kept_existing=kept, style_path=style_path, style_in_vault=in_vault,
                       files=len(pages))
