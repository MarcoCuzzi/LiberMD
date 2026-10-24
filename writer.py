"""
writer.py - Scrive un libro su disco come cartella con DUE versioni dei capitoli.

Riceve un libro gia' convertito (oggetto Book, definito in engine.py) e decide
come salvarlo: nomi dei file, cartelle, cosa sovrascrivere. Non sa nulla di EPUB
e non converte nulla. L'aspetto delle pagine (barre di navigazione, stile) e' di nav.py.

    Libro/
      00 - Indice.md               indice con i metadati e i collegamenti (modificabile)
      01 - Titolo.md  ...          copie di LAVORO: quelle su cui scrivi
      originali/
        OR - 01 - Titolo.md  ...   ORIGINALI: il testo intatto (sola lettura)
      media/                       immagini, condivise dalle due versioni

Il nome dell'originale e' sempre "OR - " + nome della copia di lavoro.

Regole di scrittura:
    - gli ORIGINALI si rigenerano sempre (sono identici) e si possono bloccare in sola lettura;
    - le copie di LAVORO gia' esistenti NON si toccano (potrebbero contenere le tue note),
      a meno che non si chieda esplicitamente di sovrascriverle;
    - lo STILE (LiberMD.css) non si sovrascrive se esiste: potresti averlo personalizzato.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from nav import COPY, CSS_CLASS, CSS_FILE_NAME, CSS_TEXT, ORIGINAL, NavContext, dress
from sanitizer import clean_alias, escape_text, sanitize_name

if TYPE_CHECKING:  # solo per i tipi: a runtime eviterebbe un import circolare con engine.py
    from engine import Book, BookMetadata, Chapter

INDEX_NAME = "00 - Indice"
ORIGINALS_DIR = "originali"
ORIGINAL_PREFIX = "OR - "


@dataclass
class WriteResult:
    kept_existing: int      # file di lavoro gia' presenti, lasciati intatti
    style_path: Path        # dove si trova (o e' stato messo) il file di stile
    style_in_vault: bool    # True se e' nella cartella .obsidian/snippets/ del vault


def yaml_str(value: str) -> str:
    """Stringa tra virgolette valida in YAML (JSON e' un sottoinsieme di YAML)."""
    return json.dumps(value, ensure_ascii=False)


def original_name(stem: str) -> str:
    """Nome (senza .md) dell'originale che corrisponde a una copia di lavoro."""
    return ORIGINAL_PREFIX + stem


# ----------------------------------------------------------------------------
# Contenuto dell'indice
# ----------------------------------------------------------------------------

def _render_index(meta: BookMetadata, chapters: list[Chapter], stems: list[str]) -> str:
    """L'indice e' l'UNICO file con i metadati del libro, ed e' il punto di ritorno
    sia dalle copie sia dagli originali."""
    lines = ["---", f"titolo: {yaml_str(meta.title)}"]
    if meta.authors:
        lines.append("autore:")
        lines += [f"  - {yaml_str(a)}" for a in meta.authors]
    if meta.publisher:
        lines.append(f"editore: {yaml_str(meta.publisher)}")
    lines += ["tags:", "  - tipo/libro", "  - stato/da-leggere",
              "cssclasses:", f"  - {CSS_CLASS}", "---", "", f"# {escape_text(meta.title)}", ""]

    if meta.authors:
        lines.append(f"**Autore:** {escape_text(', '.join(meta.authors))}  ")
    if meta.publisher:
        lines.append(f"**Editore:** {escape_text(meta.publisher)}  ")
    if meta.authors or meta.publisher:
        lines.append("")

    lines += ["## Indice dei capitoli", ""]
    for stem, chapter in zip(stems, chapters):
        alias = clean_alias(chapter.title) or stem
        lines.append(f"- [[{stem}|{alias}]] · [[{original_name(stem)}|originale]]")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------
# Scrittura su disco
# ----------------------------------------------------------------------------

def _write_original(path: Path, text: str, lock: bool) -> None:
    """Scrive un originale. Gli originali si possono sempre rigenerare: sono identici."""
    if path.exists():
        os.chmod(path, 0o644)      # sblocca, altrimenti non si potrebbe riscrivere
    path.write_text(text, encoding="utf-8")
    if lock:
        os.chmod(path, 0o444)      # sola lettura


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


def write_book(book: Book, out_dir: Path, lock_originals: bool = True,
               overwrite_working: bool = False) -> WriteResult:
    """Scrive originali + copie di lavoro + indice + immagini + stile."""
    originals_dir = out_dir / ORIGINALS_DIR
    originals_dir.mkdir(parents=True, exist_ok=True)

    if book.media:
        media_dir = out_dir / "media"
        media_dir.mkdir(exist_ok=True)
        for name, data in book.media.items():
            (media_dir / name).write_bytes(data)

    total = len(book.chapters)
    width = max(2, len(str(total)))
    stems = [f"{i:0{width}d} - {sanitize_name(ch.title)}" for i, ch in enumerate(book.chapters, 1)]
    orig_stems = [original_name(s) for s in stems]

    def neighbour(names: list[str], i: int) -> tuple[Optional[str], Optional[str]]:
        return (names[i - 1] if i > 0 else None, names[i + 1] if i < total - 1 else None)

    kept = 0
    for i, chapter in enumerate(book.chapters):
        # Originale: l'originale sta in una sottocartella, quindi le immagini sono in ../media/
        prev_o, next_o = neighbour(orig_stems, i)
        original_ctx = NavContext(ORIGINAL, INDEX_NAME, prev_o, next_o, other_stem=stems[i])
        original_md = chapter.markdown.replace("](media/", "](../media/")
        _write_original(originals_dir / f"{orig_stems[i]}.md",
                        dress(original_md, original_ctx), lock_originals)

        # Copia di lavoro
        prev_c, next_c = neighbour(stems, i)
        copy_ctx = NavContext(COPY, INDEX_NAME, prev_c, next_c, other_stem=orig_stems[i])
        kept += _write_working(out_dir / f"{stems[i]}.md",
                               dress(chapter.markdown, copy_ctx), overwrite_working)

    kept += _write_working(out_dir / f"{INDEX_NAME}.md",
                           _render_index(book.metadata, book.chapters, stems),
                           overwrite_working)

    style_path, in_vault = _install_style(out_dir)
    return WriteResult(kept_existing=kept, style_path=style_path, style_in_vault=in_vault)
