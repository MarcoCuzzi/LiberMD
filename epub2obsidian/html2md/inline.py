"""Testo "inline": unisce i frammenti con grassetto/corsivo e normalizza gli spazi.

Funzioni pure (nessuno stato): facili da testare da sole.
"""
from __future__ import annotations

import re


def render_inline(tokens: list) -> str:
    """Unisce i frammenti applicando grassetto/corsivo senza rompere il Markdown."""
    out: list = []
    stack: list[tuple[int, str]] = []
    for tok in tokens:
        if isinstance(tok, str):
            out.append(tok)
        elif tok[0] == "open":
            stack.append((len(out), tok[1]))
            out.append(tok)
        else:  # close
            marker = tok[1]
            for k in range(len(stack) - 1, -1, -1):
                if stack[k][1] == marker:
                    break
            else:
                continue  # chiusura senza apertura: ignorata
            i = stack[k][0]
            del stack[k:]
            inner = "".join(x for x in out[i + 1:] if isinstance(x, str))
            core = inner.strip()
            if core:
                lead = inner[: len(inner) - len(inner.lstrip())]
                trail = inner[len(inner.rstrip()):]
                replacement = f"{lead}{marker}{core}{marker}{trail}"  # spazi FUORI dai marcatori
            else:
                replacement = inner  # tag vuoto: niente "****"
            out[i:] = [replacement]
    return "".join(x for x in out if isinstance(x, str))


def tidy(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = text.strip()
    return re.sub(r"\n{2,}", "\n", text)
