"""Piccole utilita' sul testo: YAML e titoli."""
from __future__ import annotations

import json
import re


def yaml_str(value: str) -> str:
    """Stringa tra virgolette valida in YAML (JSON e' un sottoinsieme di YAML)."""
    return json.dumps(value, ensure_ascii=False)


def plain_title(text: str) -> str:
    """Toglie dal testo Markdown immagini, tag HTML ed enfasi, per ricavarne un titolo."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[*`~]", "", text)
    return re.sub(r"\s+", " ", text).strip()
