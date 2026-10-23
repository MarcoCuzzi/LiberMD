"""Lettura del descrittore OPF: percorso, metadati e spine (ordine dei capitoli)."""
from __future__ import annotations

import posixpath
import xml.etree.ElementTree as ET
import zipfile
from urllib.parse import unquote

from ...errors import EpubError
from ...models import BookMetadata
from .xmlutils import _local, _text


def find_opf(z: zipfile.ZipFile, names: list[str]) -> str:
    if "META-INF/container.xml" in names:
        root = ET.fromstring(z.read("META-INF/container.xml"))
        for elem in root.iter():
            if _local(elem.tag) == "rootfile" and elem.attrib.get("full-path"):
                return elem.attrib["full-path"]
    for name in names:  # ripiego
        if name.endswith(".opf"):
            return name
    raise EpubError("Nessun descrittore .opf trovato nell'EPUB.")


def read_metadata(opf_root: ET.Element, fallback_title: str) -> BookMetadata:
    meta = BookMetadata()
    for container in opf_root.iter():
        if _local(container.tag) != "metadata":
            continue
        for elem in container:
            name, value = _local(elem.tag), _text(elem)
            if not value:
                continue
            if name == "title" and not meta.title:
                meta.title = value
            elif name == "creator":
                meta.authors.append(value)
            elif name == "publisher" and not meta.publisher:
                meta.publisher = value
        break
    meta.title = meta.title or fallback_title
    return meta


def read_spine(opf_root: ET.Element, opf_dir: str) -> list[str]:
    manifest = {}
    for elem in opf_root.iter():
        if _local(elem.tag) == "item" and "id" in elem.attrib and "href" in elem.attrib:
            manifest[elem.attrib["id"]] = elem.attrib["href"]

    spine = []
    for elem in opf_root.iter():
        if _local(elem.tag) == "itemref" and elem.attrib.get("idref") in manifest:
            href = unquote(manifest[elem.attrib["idref"]]).split("#")[0]
            spine.append(posixpath.normpath(posixpath.join(opf_dir, href)))
    return spine
