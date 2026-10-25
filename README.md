# LiberMD

Converte un file **EPUB** in **note Markdown collegate tra loro**, per leggere e annotare i libri in
[Obsidian](https://obsidian.md).

Versione 0.1.0 · Nessuna libreria da installare · Tutta l'interfaccia è in italiano.

---

## Indice

1. [Cosa fa](#cosa-fa)
2. [Requisiti e avvio](#requisiti-e-avvio)
3. [Uso rapido](#uso-rapido)
4. [Cosa viene creato](#cosa-viene-creato)
5. [Tutte le opzioni](#tutte-le-opzioni)
6. [Le funzioni in dettaglio](#le-funzioni-in-dettaglio)
7. [Esempi pronti](#esempi-pronti)
8. [Consigli per Obsidian](#consigli-per-obsidian)
9. [Rigenerare un libro](#rigenerare-un-libro)
10. [Limiti noti](#limiti-noti)
11. [Come è fatto il programma](#come-è-fatto-il-programma)

---

## Cosa fa

- Legge l'EPUB e ne ricava **capitoli**, **immagini** e **dati del libro** (titolo, autori, editore).
- Per ogni capitolo crea **due versioni**: l'**originale** (testo intatto) e la **copia di lavoro**, dove
  scrivi le tue note.
- Crea un **indice** con i dati del libro e un collegamento a ogni capitolo.
- Aggiunge a ogni pagina una **barra di navigazione** (Precedente · Indice · Originale · Successivo),
  le **proprietà** e i **tag**.
- Installa uno **stile "libro"** per Obsidian.
- Ti lascia decidere come deve essere fatto il risultato: capitoli raggruppati in un file solo,
  originali sì o no, link che compaiono o no nel grafo, dati del libro corretti a mano, tag tuoi.

Non cancella e non sovrascrive mai le tue note: le copie di lavoro già esistenti restano come sono,
a meno che tu non lo chieda con `--force`.

---

## Requisiti e avvio

- **Python 3.9 o superiore**. Il programma usa solo la libreria standard di Python.
  Scritto per 3.9+, provato con Python 3.12 su Linux.
- Nessuna installazione: scarica la cartella del programma e lancia `LiberMD.py`.

```
python LiberMD.py --help        # su Linux e macOS di solito: python3
python LiberMD.py --version
```

Lanciato senza argomenti, mostra l'aiuto.

---

## Uso rapido

```
python LiberMD.py libro.epub
python LiberMD.py libro.epub -o "C:\Percorso\del\mio\vault"
```

1. Il programma legge l'EPUB e ti mostra titolo, autore ed editore che ha trovato.
2. Per ciascuno premi **Invio** per confermare, oppure scrivi il valore giusto.
3. Ti chiede anche quali **tag** mettere su tutte le pagine (puoi lasciare vuoto).
4. Converte il libro e scrive il riepilogo con le cartelle create.

Per non rispondere a nessuna domanda usa `-y`.

---

## Cosa viene creato

Dentro la cartella indicata con `-o` (se manca, la cartella corrente) il programma crea una cartella
con il **nome del file EPUB**:

```
nome-del-libro/
├── 00 - Indice - Titolo del libro.md     indice con i dati e i collegamenti ai capitoli
├── 01 - Primo capitolo.md                copie di lavoro: le tue note vanno qui
├── 02 - Secondo capitolo.md
├── ...
├── media/                                immagini del libro
├── originali/                            testo intatto di ogni capitolo
│   ├── OR - 01 - Primo capitolo.md
│   └── ...
└── LiberMD.css                           stile (vedi sotto dove viene messo)
```

- **Lo stile `LiberMD.css`**: se la cartella del libro sta dentro un vault di Obsidian (cioè in una cartella
  che ha `.obsidian` sopra di sé), il file viene messo in `.obsidian/snippets/`. Altrimenti resta
  accanto al libro e va copiato a mano in `<tuo vault>/.obsidian/snippets/`. Poi si attiva in Obsidian da
  *Impostazioni → Aspetto → Frammenti CSS*.
- Con `--raggruppa` i capitoli si uniscono in meno file; con `--senza-originali` la cartella `originali/` non
  esiste. Vedi sotto.

---

## Tutte le opzioni

```
python LiberMD.py EPUB [opzioni]
```

| Opzione | Cosa fa | Default |
|---|---|---|
| `EPUB` | File `.epub` da convertire (obbligatorio) | |
| `-o`, `--out CARTELLA` | Cartella in cui creare la cartella del libro | cartella corrente |
| `--titolo TITOLO` | Titolo del libro | quello trovato nell'EPUB |
| `--autore AUTORE` | Autore; ripeti l'opzione per più autori | quelli trovati nell'EPUB |
| `--editore EDITORE` | Editore | quello trovato nell'EPUB |
| `--tag TAG` | Tag da mettere su tutte le pagine; ripeti l'opzione o separali con la virgola | nessuno |
| `--raggruppa N` oppure `--raggruppa tutto` | Capitoli per file: `1` = uno per file, `3` = tre per file, `tutto` = tutto il libro in un solo file | `1` |
| `--senza-originali` | Non crea gli originali né i collegamenti verso di essi | originali presenti |
| `--navigazione link` oppure `--navigazione uri` | Come sono fatti i link Precedente/Successivo (vedi sotto) | `link` |
| `--vault NOME` | Nome del vault da usare nei link con `--navigazione uri` | cartella del vault che contiene il libro |
| `-y`, `--yes` | Non fa domande: usa i dati del libro e le opzioni indicate | chiede conferma |
| `-q`, `--quiet` | Non mostra l'avanzamento, solo il risultato finale | mostra l'avanzamento |
| `--force` | Rigenera anche le copie di lavoro già esistenti (**sovrascrive le tue note**) | non le tocca |
| `-h`, `--help` | Mostra l'aiuto | |
| `--version` | Mostra la versione | |

Le opzioni si combinano liberamente.

**Codici di uscita**: `0` tutto ok, `1` errore (file non trovato, EPUB non valido, operazione annullata),
`2` opzioni sbagliate.

---

## Le funzioni in dettaglio

### Dati del libro: titolo, autore, editore

Il programma legge i dati dall'EPUB, che spesso sono incompleti o sporchi (autori scritti "Cognome, Nome",
sottotitoli attaccati al titolo, campi vuoti). Per questo prima di convertire li mostra e ti lascia
correggerli:

```
Dati del libro (Invio = conferma, scrivi per cambiare, - per lasciare vuoto):
  Titolo [Il mio libro]:
  Autore (più autori: separali con ;) [Mario Rossi]:
  Editore [Editore X]:
  Tag per tutte le pagine (separati da virgola) [nessuno]:
```

- **Invio** conferma il valore proposto, un testo lo sostituisce, **`-`** lo lascia vuoto.
- Più autori si separano con il **punto e virgola**, perché la virgola è già usata in "Cognome, Nome".
- Le domande si fanno **solo per i dati che non hai già dato con un'opzione**. Se li dai tutti, non chiede nulla.
- Con `-y`, o se il programma è lanciato senza una console davanti (per esempio da uno script), non fa
  mai domande.
- Il nome della cartella del libro resta quello del file EPUB anche se cambi il titolo.

### Tag e proprietà

Ogni pagina ha delle proprietà nell'intestazione (il "frontmatter"), usate da Obsidian per ricerca,
grafo e stile.

| Pagina | Tag automatici | Altro |
|---|---|---|
| Indice | `tipo/libro`, `stato/da-leggere` | titolo, autore, editore |
| Copia di lavoro | `tipo/pagina` | `libro` |
| Originale | `tipo/pagina`, `tipo/originale` | `libro` |

- `libro` è un collegamento all'indice, con il titolo come testo: ogni pagina "sa" a quale libro appartiene.
- I **tag che scegli tu** (`--tag`) si aggiungono a **tutte** le pagine, indice compreso.
- Il tag `tipo/pagina` è su tutte le pagine tranne l'indice: serve a filtrare il grafo (vedi sotto).
- I tag vengono **ripuliti** per Obsidian: senza `#`, gli spazi diventano `-`, restano lettere, numeri,
  `_`, `-` e `/` (per i tag annidati, come `libri/filosofia`). Un tag fatto solo di numeri non è valido
  per Obsidian: viene scartato e il programma ti avvisa. I doppioni spariscono.
- I tag stanno nel frontmatter, non nel testo, così il testo del libro non viene toccato.

### Originali e copie di lavoro

- Gli **originali** (cartella `originali/`, nomi che iniziano con `OR - `) contengono il testo intatto. In
  cima hanno un avviso ("Copia originale") che rimanda alla copia di lavoro.
- Gli originali **non sono bloccati**: si possono modificare, ma si **rigenerano ogni volta** che rilanci il
  programma, quindi un errore si ripara in pochi secondi.
- Le **copie di lavoro** partono uguali agli originali. Sono tue: il programma **non le riscrive mai**
  se esistono già (così le tue note sono al sicuro), a meno di `--force`. Anche l'**indice** è una copia di
  lavoro, e vale la stessa regola.
- **`--senza-originali`**: non crea la cartella `originali/` e toglie ogni collegamento ad essi (dalla barra
  di navigazione, dall'indice e dai tag). Non cancella gli originali che ci fossero già da una conversione
  precedente.

### Navigazione fra i capitoli

In cima e in fondo a ogni pagina c'è una barra:

```
← Precedente · Indice · Originale · Successivo →
```

Nel primo capitolo al posto di "Precedente" c'è "Inizio", nell'ultimo al posto di "Successivo" c'è "Fine".
Nelle pagine originali il collegamento "Originale" diventa "La mia copia".

**`--navigazione link`** (predefinito): Precedente e Successivo sono collegamenti normali di Obsidian
(`[[...]]`). Funzionano con l'anteprima al passaggio del mouse e con i backlink e si aggiornano se
rinomini un file, ma **compaiono nel grafo**.

**`--navigazione uri`**: Precedente e Successivo sono indirizzi `obsidian://open?...` e **non compaiono nel
grafo**. Gli svantaggi:

- cliccando, Obsidian passa dal sistema operativo e può comparire una richiesta di conferma;
- niente anteprima al passaggio del mouse né backlink;
- se rinomini un capitolo i link che lo raggiungono si rompono senza avvisi;
- non funzionano in un sito pubblicato (per esempio con Quartz).

Il nome del vault e il percorso delle note vengono ricavati dalla cartella del vault che contiene il
libro. Se il libro non è dentro un vault il programma ti avvisa e i link usano solo il nome della nota;
con `--vault "Nome del vault"` indichi tu il nome.

I collegamenti all'Indice e a Originale/La mia copia restano sempre normali: è giusto che il grafo mostri a
quale libro appartiene un capitolo e quale originale corrisponde a quale copia.

### Raggruppare i capitoli

Di norma ogni capitolo è un file. Con `--raggruppa` puoi unirne di più nello stesso file, per avere meno
note nel grafo o per leggere di seguito.

```
python LiberMD.py libro.epub --raggruppa 3        # tre capitoli per file
python LiberMD.py libro.epub --raggruppa tutto    # tutto il libro in un solo file
```

Come è fatto un file con più capitoli:

- Ogni capitolo è una **sezione** con un titoletto di primo livello, per esempio `# 03 - Titolo del capitolo`.
  Il numero rende il titoletto unico anche se due capitoli hanno lo stesso titolo. Il titoletto c'è
  **sempre**, anche se il capitolo ha già il suo titolo: li vedrai uno dopo l'altro.
- Fra una sezione e l'altra c'è una **riga divisoria**.
- Ogni sezione ha la **propria barra di navigazione** (sopra e sotto), e Precedente, Successivo e Originale
  portano alla sezione giusta, anche dentro lo stesso file (`[[file#titoletto]]`).
- Proprietà, tag e avviso degli originali compaiono una volta sola, in cima al file.
- L'indice elenca ogni **sezione** con il collegamento diretto.
- Gli originali si raggruppano allo stesso modo, a meno di `--senza-originali`.
- Nel titoletto vengono tolti o sostituiti i caratteri che Obsidian non accetta nei collegamenti ai titoletti
  (`:` diventa ` - `, spariscono `#`, `|`, `^`, `[`, `]`, `*`, `_` e simili).

**Nomi dei file raggruppati**

| Modo | Esempio di nome |
|---|---|
| un capitolo per file (predefinito) | `01 - Titolo del capitolo` |
| N capitoli per file | `01 - Titolo del primo capitolo (1-3)`, `02 - Titolo (4-6)`, ... |
| un solo file | `01 - Titolo del libro` |

Se il numero richiesto è maggiore dei capitoli del libro, il risultato è un file unico.

### Dove sono arrivato: le caselle nell'indice

Quando **tutto il libro sta in un solo file**, l'indice diventa un elenco con **caselle da spuntare**:

```
- [ ] Prefazione · originale
- [ ] Capitolo Uno · originale
```

Spunti una sezione quando l'hai letta; la prima casella vuota è il punto da cui riprendere. Lo stato sta
nella nota, quindi viaggia con la sincronizzazione delle note. L'indice non viene riscritto se rilanci il
programma, quindi le caselle spuntate restano (con `--force` si perdono).

Tiene traccia della sezione, non del paragrafo.

### Lo stile "libro"

`LiberMD.css` dà alle pagine un aspetto da libro e colora la barra di navigazione. Funziona solo sulle pagine
del libro, grazie alla proprietà `cssclasses` che il programma mette in cima a ogni pagina (senza di
essa lo stile si applicherebbe a tutte le note del vault).

- Gli originali si riconoscono dalla barra di navigazione arancione e dall'avviso giallo.
- Il file di stile **non viene mai sovrascritto**, nemmeno con `--force`, perché potresti averlo
  personalizzato. Per averne una versione nuova, cancella il vecchio e rilancia il programma.
- Se non attivi il frammento in Obsidian, le pagine funzionano lo stesso, solo senza lo stile.

### Cosa succede al testo del libro

Viene convertito in Markdown: titoli, paragrafi, grassetto, corsivo, barrato, elenchi (anche annidati e
numerati), citazioni, blocchi di codice e codice in linea, tabelle, righe orizzontali, a capo e immagini
(copiate nella cartella `media/`).

- Il testo è trattato come **testo**: i caratteri che Markdown o Obsidian interpreterebbero (`#`, `[[ ]]`,
  `$`, `==`, `%%` e simili) vengono neutralizzati, così per esempio un "#1" non diventa un tag e un "[1]" non
  diventa un collegamento.
- Il **titolo di un capitolo** è il primo titolo che contiene; se non ne ha, le prime parole del testo
  (massimo 60 caratteri); altrimenti "Senza titolo".
- Le **pagine vuote** vengono saltate e contate nel riepilogo.
- I nomi dei file vengono ripuliti dai caratteri non ammessi dal sistema operativo.
- L'EPUB è letto in modo tollerante: maiuscole e minuscole nei percorsi, codifiche di ripiego, ordine
  delle sezioni vuoto, titoli di ripiego.

---

## Esempi pronti

```
# Conversione standard in un vault, con le domande
python LiberMD.py libro.epub -o "C:\Vault\Libri"

# Nessuna domanda, tutto automatico
python LiberMD.py libro.epub -o "C:\Vault\Libri" -y

# I dati dell'EPUB sono sbagliati: li indico io
python LiberMD.py libro.epub --titolo "Opere complete" --autore "Epitteto" --editore "Mondadori" -y

# Due autori e dei tag
python LiberMD.py libro.epub --autore "Primo Autore" --autore "Secondo Autore" --tag saggio --tag "da leggere"

# Libro letto di seguito, in un file solo, con le caselle per ritrovare il punto
python LiberMD.py libro.epub --raggruppa tutto

# Come sopra, senza gli originali (meno file e meno collegamenti)
python LiberMD.py libro.epub --raggruppa tutto --senza-originali

# Libro con moltissime pagine piccole: cinque capitoli per file
python LiberMD.py libro.epub --raggruppa 5

# Grafo più pulito: Precedente/Successivo non compaiono nel grafo
python LiberMD.py libro.epub --navigazione uri

# Come sopra, indicando il nome del vault
python LiberMD.py libro.epub --navigazione uri --vault "Il mio vault"

# Rigenera anche le copie di lavoro (perdi le note scritte in quelle esistenti!)
python LiberMD.py libro.epub --force
```

---

## Consigli per Obsidian

**Attivare lo stile.** *Impostazioni → Aspetto → Frammenti CSS*, poi accendi `LiberMD`. Se hai appena
modificato il file, usa l'icona di aggiornamento accanto alla cartella dei frammenti. L'icona della cartella
apre direttamente quella dei frammenti nel gestore file.

**Il grafo.** Ogni capitolo punta all'indice, e con molte pagine il grafo diventa un gomitolo. Nelle
impostazioni del grafo scrivi nel campo di ricerca:

```
tag:#tipo/pagina                          tutte le pagine dei capitoli, senza l'indice
tag:#tipo/pagina -tag:#tipo/originale     solo le copie di lavoro
tag:#tipo/pagina tag:#tipo/originale      solo gli originali
```

Scrivi il tag per intero: `tag:#pagina` non troverebbe `tipo/pagina`.

**Anteprima al passaggio del mouse.** Con il plugin di base "Anteprima pagina" attivo, tenendo premuto
Ctrl (Cmd su Mac) e passando sopra il collegamento "Originale" vedi l'originale in un riquadro. Non
funziona con i link della modalità `uri`.

**Nascondere le proprietà.** *Impostazioni → Editor → Mostra proprietà nei documenti* → "Nascosto". Le
proprietà restano, ma non occupano spazio in cima alle pagine.

**Cambiare il colore dell'avviso.** Nel file `LiberMD.css`, nella regola
`.libermd-originale .callout[data-callout="warning"]`, modifica il valore di `--callout-color`
(tre numeri: rosso, verde, blu).

---

## Rigenerare un libro

- **Libro nuovo, nessuna nota scritta**: cancella la cartella del libro e rilancia il programma.
- **Hai già scritto note**: le copie di lavoro e l'indice non vengono riscritti, quindi i nuovi tag, le nuove
  proprietà e i nuovi nomi non compaiono. Puoi convertire in un'altra cartella e riportare a mano le note, oppure
  usare `--force` sapendo che sovrascrive le copie e l'indice. Gli **originali** si aggiornano sempre.
- **Cambi modalità** (per esempio da un capitolo per file a `--raggruppa tutto`) nella stessa cartella: i
  file della modalità precedente restano accanto ai nuovi, perché il programma non cancella nulla. Per
  cambiare modalità conviene una cartella nuova.
- **Stile aggiornato**: cancella `LiberMD.css` e rilancia.

---

## Limiti noti

- I **link presenti nel testo del libro** (sia esterni sia interni) diventano testo semplice: l'indirizzo
  si perde. Note a piè di pagina e rimandi fra capitoli non diventano collegamenti.
- I **capitoli** sono le sezioni dell'EPUB, non il suo sommario ufficiale. Un capitolo diviso dall'editore in più
  file XHTML diventa più capitoli, e certi libri hanno molte pagine minuscole: in quel caso aiuta `--raggruppa`.
- Apici e pedici (`<sup>`, `<sub>`) restano scritti in HTML.
- Nello stesso vault, i **capitoli** di libri diversi possono avere lo stesso nome (`01 - Introduzione`).
  Indice e proprietà `libro` hanno nomi unici, i capitoli no, e Obsidian potrebbe confondere i collegamenti
  tra libri diversi.
- Nella modalità `--navigazione uri`, il collegamento a un titoletto di una sezione dipende da come Obsidian
  interpreta l'indirizzo: se non funziona, usa `--navigazione link`.
- Non ci sono test automatici: il programma è stato provato con EPUB di prova.

---

## Come è fatto il programma

Il codice è diviso in file piccoli, ciascuno con un compito. Ognuno ha in cima un commento che spiega cosa
fa.

```
LiberMD.py            punto di partenza: l'unico file che si lancia
cli.py                riga di comando: opzioni, domande, riepilogo
engine/               il motore di conversione
├── __init__.py            cosa si può importare dall'esterno (convert, read_epub_metadata, ...)
├── engine_pipeline.py     convert(): coordina lettura e scrittura
├── engine_reader.py       EPUB → libro (ZIP, metadati, ordine delle sezioni, immagini, titoli)
├── engine_converter.py    HTML → Markdown
├── engine_book_models.py  le schede dati: Book, Chapter, BookMetadata
└── engine_results.py      ConvertReport (esito), EpubError (errori attesi)
writer.py             scrive su disco: indice, originali, copie di lavoro, immagini, stile
nav.py                barra di navigazione, proprietà, avviso, sezioni e stile "libro"
sanitizer.py          rende sicuri testi, nomi di file, tag e titoletti
```

Il motore non stampa nulla e non legge nulla da tastiera: riceve parametri e restituisce un risultato.
Per questo si può usare anche da altri programmi:

```python
from pathlib import Path
from engine import convert, read_epub_metadata, EpubError

meta = read_epub_metadata(Path("libro.epub"))        # solo titolo, autori, editore
report = convert("libro.epub", out_base="vault", tags=["saggio"], group_size=0)
print(report.out_dir, report.chapters)
```
