"""Lettore EPUB -> Book: orchestra OPF, spine, sommario, immagini e conversione dei capitoli."""
from __future__ import annotations

import logging
import posixpath
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from ...errors import EpubError
from ...html2md import html_to_markdown
from ...html2md.result import ConversionResult
from ...models import Book, Chapter
from ...textutils import plain_title
from .media import extract_media, make_resolver
from .opf import find_opf, read_metadata, read_spine
from .toc import group_by_file, read_toc, split_chapters
from .xmlutils import _decode
from .zipindex import _ZipIndex

log = logging.getLogger("epub_to_obsidian")


def _fallback_title(result: ConversionResult, n: int) -> str:
    """Titolo ricavato dal contenuto, quando il sommario non ne da' uno."""
    if result.first_heading:
        title = result.first_heading
    elif result.first_text:
        title = plain_title(result.first_text)[:60].rstrip()
    elif result.has_images:
        title = "Copertina" if n == 1 else f"Immagine {n}"
    else:
        title = f"Sezione {n}"
    return title or f"Sezione {n}"


def read_epub(epub_path: Path) -> Book:
    if not epub_path.is_file():
        raise EpubError(f"File '{epub_path}' non trovato.")

    with zipfile.ZipFile(epub_path) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        index = _ZipIndex(names)
        log.info("    %d elementi nell'EPUB.", len(names))

        opf_path = find_opf(z, names)
        opf_dir = posixpath.dirname(opf_path)
        opf_root = ET.fromstring(z.read(opf_path))
        log.info("    Descrittore: %s", opf_path)

        metadata = read_metadata(opf_root, fallback_title=epub_path.stem)
        spine = read_spine(opf_root, opf_dir)
        if not spine:
            log.info("    [!] Spine vuota: uso tutti i file HTML in ordine alfabetico.")
            spine = sorted(n for n in names if n.lower().endswith((".xhtml", ".html", ".htm")))

        toc_entries = read_toc(z, index, opf_root, opf_dir)
        toc = group_by_file(toc_entries)
        if toc_entries:
            log.info("    Sommario: %d voci.", len(toc_entries))
        else:
            log.info("    Sommario non trovato: i titoli vengono dal contenuto dei capitoli.")

        media, path_to_name = extract_media(z, names)

        chapters: list[Chapter] = []
        skipped = 0
        for entry in spine:
            real = index.find(entry)
            if real is None:
                log.info("    [!] Sezione non trovata nello ZIP: %s", entry)
                continue
            resolver = make_resolver(posixpath.dirname(real), index, path_to_name)
            result = html_to_markdown(_decode(z.read(real)), resolver)

            if not result.markdown.strip():  # pagina davvero vuota
                skipped += 1
                continue

            for toc_title, markdown in split_chapters(result, toc.get(real, [])):
                if not markdown.strip():
                    continue
                title = toc_title or _fallback_title(result, len(chapters) + 1)
                chapters.append(Chapter(title=title, markdown=markdown))

    if not chapters:
        raise EpubError("Nessun contenuto estratto. Il libro potrebbe avere DRM o essere solo immagini.")
    if skipped:
        log.info("    %d pagine vuote saltate.", skipped)
    return Book(metadata=metadata, chapters=chapters, media=media)
