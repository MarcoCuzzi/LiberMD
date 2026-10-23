"""Test dei link esterni, degli ancoraggi e del sommario (nav.xhtml / toc.ncx).

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
from epub2obsidian.textutils import plain_title

CONTAINER = ('<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
             '<rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>')

CHAPTERS = ('<html><body><h1>Titolo generico</h1><p>Uno. Vedi <a href="https://example.com">sito</a>.</p>'
            '<h2 id="due">Altro titolo</h2><p>Due.</p></body></html>')

NAV = ('<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body>'
       '<nav epub:type="toc"><ol>'
       '<li><a href="c1.xhtml">Prima parte</a></li>'
       '<li><a href="c1.xhtml#due">Seconda parte</a></li>'
       '</ol></nav></body></html>')

NCX = ('<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap>'
       '<navPoint id="p1"><navLabel><text>Inizio</text></navLabel><content src="c1.xhtml"/>'
       '<navPoint id="p2"><navLabel><text>Fine</text></navLabel><content src="c1.xhtml#due"/></navPoint>'
       '</navPoint></navMap></ncx>')


def opf(manifest: str, spine_attrs: str = "") -> str:
    return ('<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<dc:title>Libro</dc:title></metadata>'
            f'<manifest>{manifest}</manifest><spine{spine_attrs}><itemref idref="a"/></spine></package>')


def convert(files: dict) -> dict:
    """Crea un EPUB con i file dati, lo converte e restituisce {nome nota: contenuto}."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with zipfile.ZipFile(tmp / "libro.epub", "w") as z:
            z.writestr("META-INF/container.xml", CONTAINER)
            for name, content in files.items():
                z.writestr(name, content)
        out = convert_epub(tmp / "libro.epub", tmp)
        return {p.name: p.read_text(encoding="utf-8") for p in out.glob("*.md")}


class ExternalLinkTest(unittest.TestCase):
    def md(self, html, resolver=None):
        return html_to_markdown(html, resolver).markdown

    def test_http_and_mailto(self):
        self.assertEqual(self.md('<p>Vedi <a href="https://example.com/a">il sito</a>.</p>'),
                         "Vedi [il sito](https://example.com/a).")
        self.assertEqual(self.md('<p><a href="mailto:a@b.it">scrivi</a></p>'), "[scrivi](mailto:a@b.it)")

    def test_internal_link_stays_plain_text(self):
        self.assertEqual(self.md('<p>Come nel <a href="cap2.xhtml#x">capitolo</a>.</p>'), "Come nel capitolo.")

    def test_spaces_stay_outside_the_link(self):
        self.assertEqual(self.md('<p>a<a href="http://x.org"> link </a>b</p>'), "a [link](http://x.org) b")

    def test_parentheses_in_url_are_escaped(self):
        self.assertEqual(self.md('<p><a href="https://it.wikipedia.org/wiki/Foo_(bar)">x</a></p>'),
                         "[x](https://it.wikipedia.org/wiki/Foo_%28bar%29)")

    def test_link_and_bold_nest(self):
        self.assertEqual(self.md('<p><b><a href="http://x.org">t</a></b></p>'), "**[t](http://x.org)**")
        self.assertEqual(self.md('<p><a href="http://x.org"><b>t</b></a></p>'), "[**t**](http://x.org)")

    def test_square_brackets_in_text_are_escaped(self):
        self.assertEqual(self.md('<p><a href="http://x.org">[1]</a></p>'), "[\\[1\\]](http://x.org)")

    def test_heading_link_is_plain(self):
        self.assertEqual(self.md('<h1><a href="http://x.org">Titolo</a></h1>'), "# Titolo")

    def test_image_inside_link(self):
        self.assertEqual(self.md('<a href="http://x.org"><img src="a.png" alt="A"/></a>', lambda s: "a.png"),
                         "[![A](media/a.png)](http://x.org)")

    def test_link_in_table_cell(self):
        md = self.md('<table><tr><th>A</th><th>B</th></tr>'
                     '<tr><td><a href="http://x.org">x</a></td><td>2</td></tr></table>')
        self.assertIn("| [x](http://x.org) | 2 |", md)

    def test_unbalanced_anchor_does_not_break_following_text(self):
        self.assertEqual(self.md('<p><a id="p5"/>Testo <b>forte</b></p>'), "Testo **forte**")

    def test_plain_title_unwraps_links(self):
        self.assertEqual(plain_title("[testo](http://x.org) e **forte**"), "testo e forte")


class AnchorTest(unittest.TestCase):
    def test_anchor_points_to_next_block(self):
        r = html_to_markdown('<h1>A</h1><h2 id="x">B</h2><p id="y">c</p><div id="z"><p>d</p></div>')
        self.assertEqual((r.anchors["x"], r.anchors["y"], r.anchors["z"]), (1, 2, 3))

    def test_slice(self):
        r = html_to_markdown('<h1>A</h1><h2 id="x">B</h2><p>c</p>')
        self.assertEqual(r.slice(r.anchors["x"], len(r.blocks)), "## B\n\nc")


class TocTest(unittest.TestCase):
    def check_split(self, notes, first, second):
        self.assertEqual(sorted(notes), ["00 - Indice.md", f"01 - {first}.md", f"02 - {second}.md"])
        one, two = notes[f"01 - {first}.md"], notes[f"02 - {second}.md"]
        self.assertIn("Uno.", one)
        self.assertIn("[sito](https://example.com)", one)
        self.assertNotIn("Due.", one)
        self.assertIn("## Altro titolo", two)
        self.assertIn("Due.", two)
        self.assertIn(f"[[01 - {first}|{first}]]", notes["00 - Indice.md"])

    def test_epub3_nav_titles_and_split(self):
        manifest = ('<item id="n" href="nav.xhtml" properties="nav" media-type="application/xhtml+xml"/>'
                    '<item id="a" href="c1.xhtml" media-type="application/xhtml+xml"/>')
        notes = convert({"OEBPS/content.opf": opf(manifest), "OEBPS/nav.xhtml": NAV, "OEBPS/c1.xhtml": CHAPTERS})
        self.check_split(notes, "Prima parte", "Seconda parte")

    def test_epub2_ncx_titles_and_split(self):
        manifest = ('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
                    '<item id="a" href="c1.xhtml" media-type="application/xhtml+xml"/>')
        notes = convert({"OEBPS/content.opf": opf(manifest, ' toc="ncx"'),
                         "OEBPS/toc.ncx": NCX, "OEBPS/c1.xhtml": CHAPTERS})
        self.check_split(notes, "Inizio", "Fine")

    def test_unknown_fragment_does_not_split(self):
        ncx = NCX.replace("c1.xhtml#due", "c1.xhtml#non-esiste")
        manifest = ('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
                    '<item id="a" href="c1.xhtml" media-type="application/xhtml+xml"/>')
        notes = convert({"OEBPS/content.opf": opf(manifest, ' toc="ncx"'),
                         "OEBPS/toc.ncx": ncx, "OEBPS/c1.xhtml": CHAPTERS})
        self.assertEqual(sorted(notes), ["00 - Indice.md", "01 - Inizio.md"])
        self.assertIn("Due.", notes["01 - Inizio.md"])

    def test_broken_nav_falls_back_to_ncx(self):
        manifest = ('<item id="n" href="nav.xhtml" properties="nav" media-type="application/xhtml+xml"/>'
                    '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
                    '<item id="a" href="c1.xhtml" media-type="application/xhtml+xml"/>')
        notes = convert({"OEBPS/content.opf": opf(manifest, ' toc="ncx"'),
                         "OEBPS/nav.xhtml": "<html><body><nav>&nbsp;</body>",
                         "OEBPS/toc.ncx": NCX, "OEBPS/c1.xhtml": CHAPTERS})
        self.check_split(notes, "Inizio", "Fine")

    def test_without_toc_titles_come_from_content(self):
        manifest = '<item id="a" href="c1.xhtml" media-type="application/xhtml+xml"/>'
        notes = convert({"OEBPS/content.opf": opf(manifest), "OEBPS/c1.xhtml": CHAPTERS})
        self.assertEqual(sorted(notes), ["00 - Indice.md", "01 - Titolo generico.md"])


if __name__ == "__main__":
    unittest.main()
