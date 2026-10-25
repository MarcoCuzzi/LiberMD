"""
engine_log.py - Registro delle conversioni: cosa e' successo, cosa e' andato storto.

Scrive in due posti, sempre in formato Markdown (leggibile in Obsidian):

    log/LiberMD-log.md           registro GLOBALE nella cartella del programma. Una riga per
                                 evento; resta sempre sotto MAX_LINES righe (le piu' vecchie
                                 vengono eliminate).
    <libro>/LiberMD - Log.md     resoconto dell'ULTIMA conversione di quel libro. Si puo'
                                 cancellare senza conseguenze.

Il log non deve MAI far fallire una conversione: ogni errore di scrittura viene ignorato.
Questo file non importa nulla dal resto del motore (solo il sanificatore di testo).
"""
from __future__ import annotations

import time
import traceback
from pathlib import Path
from typing import Callable, Optional

from .engine_results import ConvertReport, EpubError
from .text_safety.sanitizer import escape_text

MAX_LINES = 400                                              # righe tenute nel registro globale
LOG_DIR = Path(__file__).resolve().parents[1] / "log"        # <cartella del programma>/log
GLOBAL_LOG = LOG_DIR / "LiberMD-log.md"
BOOK_LOG_NAME = "LiberMD - Log.md"
_MAX_LEN = 300                                               # lunghezza massima di una riga di log


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _one_line(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= _MAX_LEN else text[:_MAX_LEN - 1] + "…"


def _append_global(lines: list[str]) -> None:
    """Aggiunge righe al registro globale, tenendo solo le ultime MAX_LINES."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            old = GLOBAL_LOG.read_text(encoding="utf-8").splitlines() if GLOBAL_LOG.exists() else []
        except UnicodeError:   # file rovinato: si riparte da zero
            old = []
        GLOBAL_LOG.write_text("\n".join((old + lines)[-MAX_LINES:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def log_error(source: str, message: str) -> None:
    """Segna un errore nel registro globale (per gli errori che avvengono fuori da convert())."""
    _append_global([f"- {_now()} [ERRORE] {_one_line(source)}: {_one_line(message)}"])


class RunLog:
    """Raccoglie i messaggi di UNA conversione e, alla fine, li scrive nei due registri."""

    def __init__(self, epub_name: str, out_dir: Path, options: str):
        self.epub_name = epub_name
        self.out_dir = out_dir
        self.options = options
        self.started = time.monotonic()
        self.steps: list[tuple[str, str]] = []     # (ora, messaggio)

    def wrap(self, callback: Optional[Callable[[str], None]]) -> Callable[[str], None]:
        """Ritorna una funzione di avanzamento che registra il messaggio e poi lo gira a 'callback'."""
        def progress(msg: str) -> None:
            self.steps.append((time.strftime("%H:%M:%S"), msg))
            if callback:
                callback(msg)
        return progress

    # ------------------------------------------------------------------ esiti
    def finished(self, report: ConvertReport) -> None:
        summary = (f"{report.chapters} capitoli, {report.images} immagini, "
                   f"{report.skipped_pages} pagine vuote saltate -> {report.out_dir}")
        lines = self._global_steps()
        lines += [f"- {_now()} [AVVISO] {self.epub_name}: {_one_line(w)}" for w in report.warnings]
        lines.append(f"- {_now()} [OK] {self.epub_name}: {_one_line(summary)}")
        _append_global(lines)

        body = [
            "- **Esito:** OK",
            *self._header(),
            f"- **Libro:** {escape_text(report.title)}",
            f"- **Autori:** {escape_text('; '.join(report.authors) or '(non indicato)')}",
            f"- **Capitoli:** {report.chapters} (immagini: {report.images}, "
            f"pagine vuote saltate: {report.skipped_pages})",
            f"- **File per versione:** {report.files}",
            f"- **File di lavoro gia' esistenti lasciati intatti:** {report.kept_existing}",
        ]
        if report.warnings:
            body += ["", f"## Avvisi ({len(report.warnings)})", ""]
            body += [f"- {escape_text(_one_line(w))}" for w in report.warnings]
        self._write_book(body)

    def failed(self, exc: BaseException) -> None:
        message = f"{type(exc).__name__}: {exc}"
        lines = self._global_steps()
        lines.append(f"- {_now()} [ERRORE] {self.epub_name}: {_one_line(message)}")
        if not isinstance(exc, EpubError):  # errore imprevisto: si salva anche dove e' successo
            tb = traceback.extract_tb(exc.__traceback__)[-3:]
            lines += [f"- {_now()} [TRACCIA] {_one_line(f'{Path(f.filename).name}:{f.lineno} in {f.name}')}"
                      for f in tb]
        _append_global(lines)

        body = ["- **Esito:** ERRORE", *self._header(), "", "## Errore", "",
                f"- {escape_text(_one_line(message))}"]
        self._write_book(body)

    # ----------------------------------------------------------------- interni
    def _global_steps(self) -> list[str]:
        return [f"- {_now()} [INFO] {self.epub_name}: {_one_line(msg)}" for _, msg in self.steps]

    def _header(self) -> list[str]:
        return [
            f"- **Data:** {_now()}",
            f"- **Durata:** {time.monotonic() - self.started:.1f} s",
            f"- **File EPUB:** {escape_text(self.epub_name)}",
            f"- **Opzioni:** {self.options}",
        ]

    def _write_book(self, body: list[str]) -> None:
        """Scrive il resoconto nella cartella del libro (solo se la cartella esiste gia')."""
        if not self.out_dir.is_dir():
            return
        text = ["# Log di conversione", "",
                "Resoconto dell'ultima conversione di questo libro. Si puo' cancellare senza problemi.", ""]
        text += body
        text += ["", "## Passaggi", ""]
        text += [f"- {t} {escape_text(_one_line(msg))}" for t, msg in self.steps]
        try:
            (self.out_dir / BOOK_LOG_NAME).write_text("\n".join(text) + "\n", encoding="utf-8")
        except OSError:
            pass

