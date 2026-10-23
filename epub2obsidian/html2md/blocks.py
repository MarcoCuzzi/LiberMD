"""Unione dei blocchi (paragrafi, liste, citazioni...) nel Markdown finale.

Ogni blocco e' una tupla (tipo, testo, profondita' citazione).
Funzione pura: decide solo i separatori tra un blocco e l'altro.
"""
from __future__ import annotations


def join_blocks(blocks: list[tuple[str, str, int]]) -> str:
    parts: list[str] = []
    prev_kind, prev_quote = None, 0
    for kind, text, quote in blocks:
        if prev_kind is not None:
            if kind == "li" and prev_kind in ("li", "lic"):
                sep = "\n"                                   # elementi di lista attaccati
            elif quote > 0 and prev_quote > 0:
                sep = "\n" + ("> " * min(quote, prev_quote)).rstrip() + "\n"  # citazione continua
            else:
                sep = "\n\n"
            parts.append(sep)
        parts.append(text)
        prev_kind, prev_quote = kind, quote
    return "".join(parts).strip()
