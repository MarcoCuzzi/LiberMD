"""Gestione delle tabelle HTML -> tabelle Markdown (mixin di MarkdownConverter).

Usa lo stato del convertitore: self.buf, self.rows, self.row, self.in_cell,
self.table_depth e i metodi self._flush() / self._add().
"""
from __future__ import annotations

from .inline import render_inline, tidy


class TableMixin:
    def _start_table(self) -> None:
        if self.table_depth == 0:
            self._flush()
            self.rows, self.row = [], None
        self.table_depth += 1

    def _start_cell(self) -> None:
        if self.table_depth == 1:
            if self.in_cell:      # <td> precedente non chiuso
                self._end_cell()
            if self.row is None:
                self.row = []
            self.in_cell = True
            self.buf = []

    def _end_cell(self) -> None:
        if self.table_depth == 1 and self.in_cell:
            text = tidy(render_inline(self.buf))
            text = text.replace("\n", " ").replace("|", "\\|")
            self.buf = []
            self.in_cell = False
            self.row.append(text)

    def _end_row(self) -> None:
        if self.table_depth == 1:
            self._end_cell()
            if self.row is not None:
                self.rows.append(self.row)
                self.row = None

    def _end_table(self) -> None:
        if self.table_depth == 0:
            return
        if self.table_depth == 1:
            self._end_row()
        self.table_depth -= 1
        if self.table_depth > 0:
            return
        rows = [r for r in self.rows if any(r)]
        self.rows = []
        if not rows:
            return
        ncols = max(len(r) for r in rows)
        if ncols == 1:  # tabella usata solo per l'impaginazione: testo normale
            for r in rows:
                self._add("p", r[0], 0)
            return
        rows = [r + [""] * (ncols - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * ncols) + " |"]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        self._add("table", "\n".join(lines), 0)
