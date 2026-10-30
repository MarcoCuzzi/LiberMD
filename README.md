LiberMDConverte un file EPUB in note Markdown collegate tra loro, ottimizzate per leggere, navigare e annotare i libri in Obsidian.Versione 0.1.0 · Zero dipendenze esterne (solo libreria standard Python) · Interfaccia in italiano.IndiceCosa faRequisiti e avvioUso rapidoCosa viene creatoTutte le opzioniLe funzioni in dettaglioEsempi prontiConsigli per ObsidianRigenerare un libroLimiti notiCome è fatto il programmaCosa faLegge l'EPUB ed estrae capitoli, immagini e metadati (titolo, autori, editore).Per ogni capitolo crea due versioni: l'originale (testo intatto) e la copia di lavoro (dove inserire le tue annotazioni ed evidenziazioni).Crea un indice con metadati, collegamenti ai capitoli e caselle di spunta per tracciare l'avanzamento.Aggiunge a ogni pagina una barra di navigazione (Precedente · Indice · Originale · Successivo), le proprietà YAML (frontmatter) e i tag.Installa automaticamente uno stile "libro" (LiberMD.css) negli snippet di Obsidian.Integra il sistema di Segnalibri Mobili visivi con immagini e ricerca rapida tramite tag #segnalibro.Di default compatta tutto il libro in un file solo con sezioni titolate, ma supporta anche la suddivisione capitolo per capitolo o a gruppi.Protezione delle note: non sovrascrive mai le copie di lavoro modificate, a meno che non venga specificato esplicitamente --force.Requisiti e avvioPython 3.9 o superiore. Utilizza esclusivamente moduli della libreria standard.Nessuna libreria di terze parti richiesta (pip non serve).python LiberMD.py --help        # su Linux/macOS: python3 LiberMD.py --help
python LiberMD.py --version
Lanciato senza argomenti, mostra l'aiuto della riga di comando.Uso rapido# Salva il libro convertito nella cartella predefinita tests/results/
python LiberMD.py libro.epub

# Salva direttamente dentro il tuo vault di Obsidian
python LiberMD.py libro.epub -o "/percorso/del/tuo/vault"
Il programma esamina l'EPUB e propone titolo, autore ed editore rilevati.Premi Invio per confermare oppure digita il valore corretto.Seleziona eventuali tag da associare a tutte le pagine del libro.Converte il testo, estrae le immagini e copia guide e segnalibri.Per eseguire la conversione automatica senza domande a video, usa il flag -y.Cosa viene creatoAll'interno della cartella di destinazione indicata con -o (default: tests/results/), il programma genera una cartella con il nome dell'EPUB.Struttura predefinita (file unico: --raggruppa tutto)nome-del-libro/
├── 00 - Indice - Titolo del libro.md     indice con metadati, checklist e link
├── 01 - Titolo del libro.md              copia di lavoro (testo intero diviso in sezioni)
├── Guida-LiberMD.md                      guida al metodo di lettura e segnalibri
├── bookmarks/                            segnalibri e guide grafiche
│   ├── bookmark.md                       nota base da includere come collegamneto Obsidian
│   ├── info_bookmarks.md                 galleria e modelli pronti al copia-incolla
│   ├── Ambrosia-Gialla.webp
│   ├── Bandiera-Rossa.webp
│   └── Bandiera-Verde.webp
├── media/                                immagini estratte dall'EPUB
├── originali/                            testo intatto di riserva
│   └── OR - 01 - Titolo del libro.md
└── LiberMD - Log.md                      registro dell'ultima conversione
Struttura a file singoli (--raggruppa 1)nome-del-libro/
├── 00 - Indice - Titolo del libro.md
├── 01 - Primo capitolo.md
├── 02 - Secondo capitolo.md
├── ...
├── bookmarks/
├── media/
├── originali/
│   ├── OR - 01 - Primo capitolo.md
│   └── ...
└── LiberMD - Log.md
Se la cartella di destinazione fa parte di un vault di Obsidian (ha una cartella .obsidian/ a monte), LiberMD.css viene installato direttamente in .obsidian/snippets/.Tutte le opzioniOpzioneDescrizioneDefaultEPUBPercorso del file .epub da convertire (obbligatorio)-o, --out CARTELLACartella di destinazionetests/results--titolo TITOLOTitolo del libroquello estratto dall'EPUB--autore AUTOREAutore del libro (ripetibile per più autori)quelli estratti dall'EPUB--editore EDITOREEditorequello estratto dall'EPUB--tag TAGTag globali (ripetibile o separati da virgola)nessuno--raggruppa N|tuttoModalità file: tutto (file unico), 1 (un capitolo per file), N (N capitoli per file)tutto--senza-originaliNon crea la cartella originali/ né i collegamenti ad essadisattivato (crea originali)--navigazione link|uriFormato link: link (wikilink Obsidian [[...]]) o uri (obsidian://..., non compare nel grafo)link--vault NOMENome del vault per link uricartella vault rilevata--barre tutte|una|nessunaBarre di navigazione tra sezioni: sopra e sotto, solo sopra, o solo in cimatutte--unisci auto|no|NFusione pagine corte/OCR: auto, no, o soglia minima caratteri (es. 12000)auto-y, --yesNon fare domande a videointerattivo-q, --quietNon stampare l'avanzamento dettagliatodettagliato--forceSovrascrive anche le copie di lavoro esistenti (elimina le annotazioni)disattivatoLe funzioni in dettaglioPulizia del testo e note a piè di paginaIl convertitore tratta il contenuto del libro come testo: caratteri speciali Markdown o Obsidian (*, _, [, ], #, $, ==, %%) vengono neutralizzati con barre rovesciate (\), evitando formattazioni indesiderate.Note a piè di pagina: i riferimenti e i blocchi nota standard (come epub:type="footnote", classi CSS footnote/noteref, o collegamenti da sup) vengono convertiti nella sintassi di Obsidian [^id], raccolti e ordinati a fondo pagina.Navigazione e GrafoI pulsanti di navigazione ← Precedente e Successivo → consentono di sfogliare il libro sequenzialmente.Impostando --navigazione uri, i link di navigazione vengono scritti come indirizzi URI di Obsidian invece di Wikilink. In questo modo le connessioni sequenziali fra capitoli non appaiono nel grafo globale, mantenendolo pulito e dedicato solo ai collegamenti concettuali.Segnalibri Visivi MobiliAll'interno di ogni cartella libro viene copiata la directory bookmarks/. È possibile inserire un segnalibro sotto l'ultimo paragrafo letto:Tramite transclusione dinamica: ![[bookmarks/bookmark]]Tramite nastro o callout compatto con una delle immagini fornite (Bandiera-Rossa.webp, Bandiera-Verde.webp, Ambrosia-Gialla.webp).Cercando il tag #segnalibro con la ricerca globale di Obsidian (Ctrl+Shift+F), si atterra all'istante sull'ultimo punto letto.Esempi pronti# Conversione predefinita interattiva (un unico file)
python LiberMD.py libro.epub

# Conversione diretta nel vault senza prompt interattivi
python LiberMD.py saggio.epub -o "~/Obsidian/Vault" -y

# Suddivisione in un file Markdown per ciascun capitolo
python LiberMD.py romanzo.epub -o "~/Obsidian/Vault" --raggruppa 1 -y

# Esclusione delle frecce di navigazione dal grafo di Obsidian
python LiberMD.py libro.epub -o "~/Obsidian/Vault" --raggruppa 1 --navigazione uri -y

# Fusione manuale di pagine OCR corte fino a 15.000 caratteri per sezione
python LiberMD.py scansione.epub --unisci 15000 -y

# Forzatura riscrittura totale (sovrascrive anche le copie di lavoro)
python LiberMD.py libro.epub --force -y
Consigli per ObsidianAttivazione dello stile:Vai in Impostazioni → Aspetto → Frammenti CSS e attiva lo snippet LiberMD. Se il libro è stato convertito fuori dal vault, copia LiberMD.css nella cartella .obsidian/snippets/ del tuo vault.Filtri nel Grafo:Per escludere le pagine libro dal grafo concettuale o isolare le sole copie di lavoro, usa i filtri di ricerca del grafo:-tag:#tipo/originale: nasconde le copie di riserva originali.-tag:#tipo/pagina: nasconde tutte le pagine del testo, lasciando visibili solo gli indici e le tue note concettuali.Nascondere le proprietà in lettura:In Impostazioni → Editor → Mostra proprietà nei documenti, seleziona Nascosto per non visualizzare i blocchi frontmatter YAML in cima ai capitoli.Limiti notiI link interni generici non legati a note a piè di pagina (es. rimandi interni arbitrari a ID HTML specifici) vengono convertiti in testo semplice.I capitoli corrispondono alle unità spine dell'EPUB (o alle sezioni delimitate da ID nel sommario TOC/NAV). Documenti privi di indice o con strutture HTML anomale potrebbero richiedere l'opzione --unisci.Tag HTML specifici non mappabili direttamente in Markdown standard (come <sub> o <sup> non legati a note) restano rappresentati come tag HTML.Come è fatto il programmaL'architettura è modulare e disaccoppiata:LiberMD.py                 Punto di ingresso da riga di comando
ui/
└── cli.py                 Gestione argomenti, interfaccia interattiva e log di avanzamento
book_design/
└── nav.py                 Barre di navigazione (callout), frontmatter YAML e CSS 'LiberMD'
engine/
├── __init__.py            Punto di esportazione per uso come libreria Python
├── engine_pipeline.py     Coordinamento convert(): lettura, fusione e generazione
├── engine_book_models.py  Modelli dati: Book, Chapter, BookMetadata
├── engine_converter.py    Parser HTML -> Markdown, gestione blocchi, tabelle e note 
├── engine_log.py          Gestione log globale (log/) e locale (nella cartella libro)
├── engine_results.py      Report finale (ConvertReport) ed eccezioni (EpubError)
├── readers/
│   ├── engine_reader.py   Unpack EPUB, lettura opf/spine, risoluzione media e split TOC
│   └── merge.py           Fusione euristica per scansioni OCR e sezioni frammentate
├── text_safety/
│   └── sanitizer.py       Escape caratteri critici Markdown/Obsidian, slug e tag
└── writers/
    └── writer.py          Scrittura su disco: indici, copie di lavoro, originali e asset
guide/
├── Guida-LiberMD.md       Documentazione operativa al metodo di lettura
└── bookmarks/             Asset grafici (.webp) e note dei segnalibri visivi
Uso come libreria Pythonfrom pathlib import Path
from engine import convert, read_epub_metadata

# Lettura metadati senza conversione
meta = read_epub_metadata(Path("libro.epub"))
print(meta.title, meta.authors)

# Conversione
report = convert(
    "libro.epub",
    out_base="~/Obsidian/Vault",
    tags=["saggistica", "filosofia"],
    group_size=0,           # tutto in un unico file
    with_originals=True
)
print(f"Convertiti {report.chapters} capitoli in: {report.out_dir}")
