"""
engine_pipeline.py - Il motore di conversione EPUB -> Markdown (note per Obsidian).

Il motore NON stampa nulla, NON legge input e NON chiude il programma: riceve dei
parametri e restituisce un risultato. Cosi' lo si puo' usare da qualsiasi interfaccia
(riga di comando, grafica, API web) senza modificarlo.

Punto di ingresso (disponibile anche come "from engine import convert"):

    from engine import convert, EpubError

    report = convert("libro.epub", out_base="vault", on_progress=print)
    print(report.out_dir, report.chapters)

Questo file e' solo il coordinatore: lancia i passaggi nell'ordine giusto.

    engine_reader.py       EPUB -> Book
    engine_converter.py    HTML -> Markdown (usato dal lettore)
    engine_book_models.py  le schede dati: Book / Chapter / BookMetadata
    engine_results.py      ConvertReport / EpubError / ProgressCallback

Gli altri file del programma (fuori dalla cartella engine/):

    sanitizer.py      rende sicuro il testo (caratteri speciali) e i nomi dei file
    writer.py         scrive il libro su disco: originali + copie di lavoro
    nav.py            maschera di navigazione: barre avanti/indietro/originale e stile "libro"
    cli.py            interfaccia a riga di comando
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from sanitizer import sanitize_name
from writer import ORIGINALS_DIR, write_book
from .engine_reader import read_epub
from .engine_results import ConvertReport, ProgressCallback


def convert(
    epub_path: Union[str, Path],
    out_base: Union[str, Path] = ".",
    on_progress: Optional[ProgressCallback] = None,
    overwrite_working: bool = False,
) -> ConvertReport:
    """
    Converte un EPUB in una cartella con due versioni dei capitoli.

    epub_path          file .epub da convertire
    out_base           cartella in cui creare la cartella del libro
    on_progress        funzione chiamata con un messaggio di testo a ogni fase (opzionale)
    overwrite_working  se True, rigenera anche le copie di lavoro gia' esistenti
                       (ATTENZIONE: perderesti le tue note). Di default restano intatte.

    Solleva EpubError se il file non e' leggibile o non contiene testo.
    """
    progress = on_progress or (lambda msg: None)
    epub_path = Path(epub_path)

    progress(f"Lettura di {epub_path.name}")
    book = read_epub(epub_path, progress)

    out_dir = Path(out_base) / sanitize_name(epub_path.stem)
    progress(f"Scrittura di {len(book.chapters)} capitoli (originali + copie di lavoro) in {out_dir}")
    written = write_book(book, out_dir, overwrite_working)

    meta = book.metadata
    return ConvertReport(
        out_dir=out_dir,
        originals_dir=out_dir / ORIGINALS_DIR,
        title=meta.title,
        authors=meta.authors,
        publisher=meta.publisher,
        chapters=len(book.chapters),
        images=len(book.media),
        skipped_pages=book.skipped_pages,
        warnings=book.warnings,
        kept_existing=written.kept_existing,
        style_path=written.style_path,
        style_in_vault=written.style_in_vault,
    )
