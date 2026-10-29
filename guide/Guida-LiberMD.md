Guida al Segnalibro Mobile in LiberMD

Quando leggi un libro in Markdown (specialmente con file lunghi o capitoli accorpati), l'indice con le caselle di spunta ti permette di tracciare le macro-sezioni completate, ma riaprendo la nota si perde inevitabilmente la posizione esatta dello scroll verticale.

Il Segnalibro Mobile risolve questo limite: posiziona un elemento visivo chiaro e compatto sotto l'ultimo paragrafo letto e ti permette di ritrovarlo all'istante tramite il motore di ricerca di Obsidian.

1. Come inserire il segnalibro

Quando decidi di interrompere la sessione di lettura, vai a capo sotto l'ultimo paragrafo letto e scrivi:

![[bookmark]]


Nel testo comparirà subito l'immagine del segnalibro (formato compatto 250x250) seguita dalla riga di stato:

Lettura interrotta qui #segnalibro

2. Come ritrovare il punto esatto

Quando riapri Obsidian per riprendere la lettura:

Apri la barra di ricerca rapida:

Windows / Linux: Ctrl + F (nella nota corrente) oppure Ctrl + Shift + F (in tutto il Vault)

macOS: Cmd + F oppure Cmd + Shift + F

Cerca il tag:

#segnalibro


Fai clic sul risultato trovato: Obsidian aprirà la nota ed eseguirà lo scroll verticale automatico direttamente sul segnalibro.

Suggerimento (più libri in contemporanea):

Se stai leggendo più libri nello stesso Vault, puoi isolare la ricerca digitando il nome del file o del libro, ad esempio:

file:"01 - Epitteto" #segnalibro

3. Il flusso di lettura

Il metodo funziona spostando il segnalibro esattamente come faresti con un nastro di stoffa in un libro cartaceo:

Trova: cerca #segnalibro e salta al punto di lettura.

Rimuovi: cancella o taglia (Ctrl + X) la riga ![[bookmark]].

Leggi: procedi con la lettura del testo.

Riponi: quando decidi di fermarti, scrivi o incolla (Ctrl + V) di nuovo ![[bookmark]] sotto l'ultimo paragrafo letto.

4. Personalizzazione

Tutte le risorse del segnalibro si trovano nella sottocartella bookmarks/ all'interno della cartella di questo libro:

Modificare immagine o dimensioni: apri il file bookmarks/bookmark.md. Puoi sostituire il file immagine indicato (scegliendo tra le alternative presenti nella cartella) oppure cambiare le proporzioni 250x250.

Modelli e dettagli: consulta bookmarks/info_bookmarks.md per visualizzare le istruzioni aggiuntive e la galleria delle opzioni disponibili.