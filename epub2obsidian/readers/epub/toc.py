"""Sommario del libro (EPUB3 nav.xhtml / EPUB2 toc.ncx): titoli e punti di divisione dei capitoli.

Il sommario dice come l'autore ha diviso il libro: puo' dare un titolo migliore del primo
<h1> di un file, e puo' indicare piu' capitoli dentro lo stesso file (voci con #frammento).
"""
from __future__ import annotations

import posixpath
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from typing import Optional
from urllib.parse import unquote

from ...html2md.result import ConversionResult
from .opf import read_manifest
from .xmlutils import _local, _text
from .zipindex import _ZipIndex

NCX_MEDIA_TYPE = "application/x-dtbncx+xml"
OPS_TYPE = "{http://www.idpf.org/2007/ops}type"


@dataclass
class TocEntry:
    title: str
    path: str       # percorso reale del file nello ZIP
    fragment: str   # id di destinazione dentro il file ("" = inizio del file)


def read_toc(z: zipfile.ZipFile, index: _ZipIndex, opf_root: ET.Element, opf_dir: str) -> list[TocEntry]:
    """Voci del sommario in ordine di lettura: prima EPUB3 (nav), poi EPUB2 (ncx).

    Lista vuota se il sommario manca o non e' leggibile: il libro si converte comunque.
    """
    manifest = read_manifest(opf_root)
    spine_toc = next((e.attrib.get("toc") for e in opf_root.iter() if _local(e.tag) == "spine"), None)
    sources = [(_parse_nav, item) for item in manifest.values()
               if "nav" in item.get("properties", "").split()]
    sources += [(_parse_ncx, item) for key, item in manifest.items()
                if item.get("media-type") == NCX_MEDIA_TYPE or key == spine_toc]

    for parse, item in sources:
        href = unquote(item["href"]).split("#")[0]
        real = index.find(posixpath.normpath(posixpath.join(opf_dir, href)))
        if real is None:
            continue
        try:
            root = ET.fromstring(z.read(real))
        except ET.ParseError:
            continue
        entries = parse(root, posixpath.dirname(real), index)
        if entries:
            return entries
    return []


def group_by_file(entries: list[TocEntry]) -> dict[str, list[TocEntry]]:
    grouped: dict[str, list[TocEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.path, []).append(entry)
    return grouped


def split_chapters(result: ConversionResult, entries: list[TocEntry]) -> list[tuple[Optional[str], str]]:
    """Divide il contenuto di un file nei capitoli indicati dal sommario.

    Restituisce coppie (titolo dal sommario o None, markdown). Senza voci utili: un solo pezzo.
    """
    points: list[tuple[int, str]] = []
    for entry in entries:
        start = result.anchors.get(entry.fragment) if entry.fragment else 0
        if start is None and not points:
            start = 0   # id non trovato: la voce da' comunque il nome al file
        if start is not None:
            points.append((start, entry.title))
    points.sort(key=lambda p: p[0])

    unique: list[tuple[int, Optional[str]]] = []
    for start, title in points:
        if not unique or start != unique[-1][0]:
            unique.append((start, title))
    if not unique:
        return [(None, result.markdown)]
    if unique[0][0] > 0:
        unique.insert(0, (0, None))   # testo prima della prima voce: resta un pezzo a se'

    ends = [start for start, _ in unique[1:]] + [len(result.blocks)]
    return [(title, result.slice(start, end)) for (start, title), end in zip(unique, ends)]


def _entry(title: str, href: str, base_dir: str, index: _ZipIndex) -> Optional[TocEntry]:
    path, _, fragment = href.partition("#")
    if not title or not path or "://" in path or path.lower().startswith("mailto:"):
        return None
    real = index.find(posixpath.normpath(posixpath.join(base_dir, unquote(path))))
    return TocEntry(title, real, unquote(fragment)) if real else None


def _parse_nav(root: ET.Element, base_dir: str, index: _ZipIndex) -> list[TocEntry]:
    navs = [e for e in root.iter() if _local(e.tag) == "nav"]
    toc = next((n for n in navs if "toc" in n.attrib.get(OPS_TYPE, "").split()), navs[0] if navs else None)
    if toc is None:
        return []
    entries = []
    for a in toc.iter():
        if _local(a.tag) == "a" and a.attrib.get("href"):
            entry = _entry(_text(a), a.attrib["href"], base_dir, index)
            if entry:
                entries.append(entry)
    return entries


def _parse_ncx(root: ET.Element, base_dir: str, index: _ZipIndex) -> list[TocEntry]:
    entries = []
    for point in root.iter():
        if _local(point.tag) != "navPoint":
            continue
        title = src = ""
        for child in point:   # solo figli diretti: i navPoint annidati hanno la loro voce
            name = _local(child.tag)
            if name == "navLabel" and not title:
                title = _text(child)
            elif name == "content" and not src:
                src = child.attrib.get("src", "")
        entry = _entry(title, src, base_dir, index)
        if entry:
            entries.append(entry)
    return entries
