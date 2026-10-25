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

from dataclasses import replace
from pathlib import Path
from typing import Iterable, Optional, Union

from .text_safety.sanitizer import clean_tags, sanitize_name
from .writers.writer import ORIGINALS_DIR, write_book
from .engine_book_models import BookMetadata
from .engine_log import RunLog
from .readers.engine_reader import read_epub
from .engine_results import ConvertReport, ProgressCallback


def convert(
    epub_path: Union[str, Path],
    out_base: Union[str, Path] = ".",
    on_progress: Optional[ProgressCallback] = None,
    overwrite_working: bool = False,
    metadata: Optional[BookMetadata] = None,
    tags: Optional[Iterable[str]] = None,
    nav_uri: bool = False,
    vault_name: Optional[str] = None,
    with_originals: bool = True,
    group_size: int = 1,
) -> ConvertReport:
    """
    Converte un EPUB in una cartella con due versioni dei capitoli.

    epub_path          file .epub da convertire
    out_base           cartella in cui creare la cartella del libro
    on_progress        funzione chiamata con un messaggio di testo a ogni fase (opzionale)
    overwrite_working  se True, rigenera anche le copie di lavoro gia' esistenti
                       (ATTENZIONE: perderesti le tue note). Di default restano intatte.
    metadata           titolo/autori/editore da usare al posto di quelli trovati nell'EPUB (opzionale)
    tags               tag da aggiungere a tutte le pagine del libro (opzionale)
    nav_uri            se True, "Precedente" e "Successivo" sono link obsidian:// invece di
                       [[collegamenti]]: non compaiono nel grafo di Obsidian
    vault_name         nome del vault da usare in quei link (default: la cartella del vault
                       che contiene il libro)
    with_originals     se False, non crea la cartella originali/ ne' i collegamenti agli originali
    group_size         capitoli per file: 1 = uno per file (default), N = N capitoli per file, ognuno
                       come sezione con il suo titoletto; 0 = tutto il libro in un solo file

    Solleva EpubError se il file non e' leggibile o non contiene testo.
    """
    if group_size < 0:
        raise ValueError("group_size deve essere 1, 2, 3... oppure 0 (tutto in un file)")
    epub_path = Path(epub_path)
    out_dir = Path(out_base) / sanitize_name(epub_path.stem)
    options = (f"raggruppa={'tutto' if group_size == 0 else group_size}, "
               f"originali={'si' if with_originals else 'no'}, "
               f"navigazione={'uri' if nav_uri else 'link'}, rigenera={'si' if overwrite_working else 'no'}")
    log = RunLog(epub_path.name, out_dir, options)   # registro: vedi engine_log.py
    progress = log.wrap(on_progress)

    try:
        progress(f"Lettura di {epub_path.name}")
        book = read_epub(epub_path, progress)
        if metadata is not None:
            book.metadata = replace(metadata, title=metadata.title.strip() or epub_path.stem)
        page_tags, dropped = clean_tags(tags or [])
        for text in dropped:
            book.warnings.append(f"Tag scartato (non valido per Obsidian): {text}")

        progress(f"Scrittura di {len(book.chapters)} capitoli (originali + copie di lavoro) in {out_dir}")
        written = write_book(book, out_dir, overwrite_working, page_tags, nav_uri, vault_name,
                              with_originals, group_size)
        if nav_uri and not written.style_in_vault:
            book.warnings.append(
                "La cartella del libro non e' dentro un vault di Obsidian: i link Precedente/Successivo "
                "usano solo il nome della nota" + ("" if vault_name else " e non il nome del vault (usa --vault)") + ".")

        meta = book.metadata
        report = ConvertReport(
            out_dir=out_dir,
            originals_dir=out_dir / ORIGINALS_DIR if with_originals else None,
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
            tags=page_tags,
            files=written.files,
        )
    except Exception as exc:   # anche gli errori imprevisti finiscono nel registro
        log.failed(exc)
        raise
    log.finished(report)
    return report
