"""Helper per leggere XML con namespace e decodificare testo."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET


def _local(tag: str) -> str:
    """Nome del tag senza namespace: '{http://...}title' -> 'title'."""
    return tag.rsplit("}", 1)[-1]


def _text(elem: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(elem.itertext())).strip()


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")
