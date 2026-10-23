# epub2obsidian — guida per chi lavora sul codice (persone e AI)

Converte un EPUB in una cartella di note Markdown per Obsidian, con link
precedente/successivo tra i capitoli e un indice (MOC) con i metadati.

```
python epub_to_obsidian.py libro.epub -o /percorso/vault
python -m epub2obsidian libro.epub
python -m unittest discover tests
```

Solo libreria standard, Python 3.9+. Nessuna dipendenza da installare.

## Flusso

```
EPUB --readers/epub--> Book --writers/obsidian--> cartella di note .md
            (HTML dei capitoli passa da html2md)
```

`Book` (in `models.py`) è l'unico contratto tra lettori e scrittori.

## Mappa dei file (dove mettere mano)

| Voglio cambiare...                              | File                                   |
|-------------------------------------------------|----------------------------------------|
| Struttura dati (Book, Chapter, metadati)        | `models.py`                            |
| Nomi di note/immagini, alias dei link           | `naming.py`                            |
| Escape YAML, titolo "pulito"                    | `textutils.py`                         |
| Grassetto/corsivo, link esterni, spazi          | `html2md/inline.py`                    |
| Separatori tra paragrafi, liste, citazioni      | `html2md/blocks.py`                    |
| Tabelle HTML -> Markdown                        | `html2md/tables.py`                    |
| Tag HTML gestiti, marcatori Markdown            | `html2md/constants.py`                 |
| Titoli, liste, immagini, codice, citazioni      | `html2md/converter.py`                 |
| Come si trova il file OPF / metadati / spine    | `readers/epub/opf.py`                  |
| Estrazione e percorsi delle immagini            | `readers/epub/media.py`                |
| Ricerca file nello ZIP, decodifica testo        | `readers/epub/zipindex.py`, `xmlutils.py` |
| Sommario (nav.xhtml / toc.ncx), capitoli divisi | `readers/epub/toc.py`                  |
| Scelta titolo capitolo, pagine vuote            | `readers/epub/reader.py`               |
| Frontmatter e indice del libro                  | `writers/obsidian/index_note.py`       |
| Barra di navigazione di ogni capitolo           | `writers/obsidian/chapter_note.py`     |
| Cartelle/file scritti su disco                  | `writers/obsidian/writer.py`           |
| Nome della nota indice                          | `writers/obsidian/constants.py`        |
| Opzioni da riga di comando                      | `cli.py`                               |
| Quale lettore + scrittore si usano              | `pipeline.py`                          |

## Regole

- Un file = una responsabilità. Se un file supera ~250 righe, spezzalo.
- `html2md/inline.py` e `html2md/blocks.py` sono funzioni pure: nessuno stato, facili da testare.
- `converter.py` è l'unico posto con lo stato del parser; `tables.py` è un mixin che usa quello stato.
- Un lettore non deve conoscere Obsidian; uno scrittore non deve conoscere l'EPUB.
- Errori "attesi" (file mancante, EPUB non valido): solleva `EpubError`, la CLI mostra solo il messaggio.
- I nomi dei file delle note devono restare sicuri per i `[[wikilink]]`: passa sempre da `naming.sanitize_name`.

## Aggiungere un formato

- Nuovo input (es. PDF): crea `readers/pdf/` con `read_pdf(path) -> Book`, poi sceglilo in `pipeline.py`.
- Nuovo output (es. Logseq): crea `writers/logseq/` con `write_logseq(book, out_dir)`.
