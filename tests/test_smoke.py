"""Test di fumo: crea un EPUB minimo e controlla che la conversione produca note collegate.

Esegui con:  python -m unittest discover tests
"""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epub2obsidian.html2md import html_to_markdown
from epub2obsidian.pipeline import convert_epub

CONTAINER = ('<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
             '<rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>')
OPF = ('<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
       '<dc:title>Libro di prova</dc:title><dc:creator>Mario Rossi</dc:creator></metadata>'
       '<manifest><item id="a" href="c1.xhtml"/><item id="b" href="c2.xhtml"/></manifest>'
       '<spine><itemref idref="a"/><itemref idref="b"/></spine></package>')


def make_epub(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("META-INF/container.xml", CONTAINER)
        z.writestr("OEBPS/content.opf", OPF)
        z.writestr("OEBPS/c1.xhtml", "<html><body><h1>Uno</h1><p>Testo <b>forte</b>.</p></body></html>")
        z.writestr("OEBPS/c2.xhtml", "<html><body><h1>Due</h1><p>Altro.</p></body></html>")


class HtmlToMarkdownTest(unittest.TestCase):
    def test_bold_and_heading(self):
        r = html_to_markdown("<h1>Titolo</h1><p>a <b>b</b></p>")
        self.assertEqual(r.markdown, "# Titolo\n\na **b**")
        self.assertEqual(r.first_heading, "Titolo")

    def test_table(self):
        r = html_to_markdown("<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>")
        self.assertIn("| A | B |", r.markdown)
        self.assertIn("| --- | --- |", r.markdown)


class PipelineTest(unittest.TestCase):
    def test_converts_and_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            make_epub(tmp / "libro.epub")
            out = convert_epub(tmp / "libro.epub", tmp)
            names = sorted(p.name for p in out.glob("*.md"))
            self.assertEqual(names, ["00 - Indice.md", "01 - Uno.md", "02 - Due.md"])
            first = (out / "01 - Uno.md").read_text(encoding="utf-8")
            self.assertIn("[[02 - Due|Successivo →]]", first)
            index = (out / "00 - Indice.md").read_text(encoding="utf-8")
            self.assertIn("[[01 - Uno|Uno]]", index)


if __name__ == "__main__":
    unittest.main()
