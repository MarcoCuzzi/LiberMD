"""
cli.py - Interfaccia a riga di comando (CLI) per il motore di conversione.

Si occupa solo di leggere i comandi dalla console, di fare le domande all'utente e di
mostrare i risultati: tutto il lavoro vero e' nella cartella engine/.

Di solito non si lancia direttamente: si avvia il programma da LiberMD.py.

Prima di convertire, il programma mostra titolo, autore ed editore trovati nel libro e
chiede se confermarli (Invio) o cambiarli. Le domande si saltano con le opzioni qui sotto
(per i dati che passi da riga di comando non chiede nulla) oppure con -y.

Uso:
    python LiberMD.py libro.epub
    python LiberMD.py libro.epub -o /percorso/del/vault
    python LiberMD.py libro.epub --titolo "Il mio titolo" --autore "Nome Cognome"
    python LiberMD.py libro.epub --autore "Primo Autore" --autore "Secondo Autore"
    python LiberMD.py libro.epub --tag saggio --tag "da leggere"      # tag su tutte le pagine
    python LiberMD.py libro.epub -y            # nessuna domanda: usa i dati trovati nel libro
    python LiberMD.py libro.epub --navigazione uri   # Precedente/Successivo fuori dal grafo
    python LiberMD.py libro.epub --senza-originali   # niente cartella originali/ ne' collegamenti
    python LiberMD.py libro.epub --raggruppa 3       # 3 capitoli per file, ognuno come sezione
    python LiberMD.py libro.epub --raggruppa tutto   # tutto il libro in un solo file
    python LiberMD.py libro.epub -q
    python LiberMD.py libro.epub --force       # rigenera anche le copie di lavoro (perdi le tue note!)
"""
import argparse
import sys
from pathlib import Path
from typing import Optional

from engine import EpubError, convert, log_error, read_epub_metadata


def _split_tags(values: list[str]) -> list[str]:
    """--tag si puo' ripetere e accetta anche piu' tag separati da virgola."""
    return [tag.strip() for value in values for tag in value.split(",") if tag.strip()]


def _split_authors(text: str) -> list[str]:
    """Piu' autori si separano con il punto e virgola (la virgola e' in 'Cognome, Nome')."""
    return [a.strip() for a in text.split(";") if a.strip()]


def _parse_group(value: str) -> Optional[int]:
    """--raggruppa: un numero (1, 2, 3...) oppure "tutto" (= 0). None se non e' valido."""
    value = value.strip().lower()
    if value in ("tutto", "tutti"):
        return 0
    return int(value) if value.isdigit() and int(value) >= 1 else None


def _ask(label: str, default: str, empty: str = "non trovato") -> str:
    """Domanda con valore proposto: Invio lo conferma, '-' lo svuota, altro lo sostituisce."""
    answer = input(f"  {label} [{default or empty}]: ").strip()
    if not answer:
        return default
    return "" if answer == "-" else answer


def main(argv: Optional[list[str]] = None, prog: str = "LiberMD",
         version: Optional[str] = None) -> int:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=f"{prog} - converte un EPUB in note Markdown per Obsidian "
                    f"(originali + copie di lavoro con i collegamenti).",
    )
    if version:
        parser.add_argument("--version", action="version", version=f"{prog} {version}")
    parser.add_argument("epub", type=Path, help="file .epub da convertire")
    parser.add_argument("-o", "--out", type=Path, default=Path("."),
                        help="cartella in cui creare la cartella del libro (default: cartella corrente)")
    parser.add_argument("--titolo", dest="title", default=None,
                        help="titolo del libro (default: quello trovato nell'EPUB)")
    parser.add_argument("--autore", dest="author", action="append", default=None,
                        help="autore del libro; ripeti l'opzione per piu' autori")
    parser.add_argument("--editore", dest="publisher", default=None,
                        help="editore del libro (default: quello trovato nell'EPUB)")
    parser.add_argument("--tag", action="append", default=[],
                        help="tag da mettere su tutte le pagine; ripeti l'opzione o separali con la virgola")
    parser.add_argument("--navigazione", dest="nav", choices=["link", "uri"], default="link",
                        help="come sono fatti i link Precedente/Successivo: 'link' = collegamenti di "
                             "Obsidian [[...]] (compaiono nel grafo, default); 'uri' = indirizzi "
                             "obsidian://... (NON compaiono nel grafo)")
    parser.add_argument("--vault", default=None,
                        help="nome del vault per i link con --navigazione uri (default: la cartella "
                             "del vault che contiene il libro)")
    parser.add_argument("--senza-originali", dest="no_originals", action="store_true",
                        help="non creare gli originali e nemmeno i collegamenti verso di essi")
    parser.add_argument("--raggruppa", default="1", metavar="N|tutto",
                        help="quanti capitoli mettere in ogni file (default 1: un capitolo per file); "
                             "con 2 o piu' ogni capitolo diventa una sezione con il suo titoletto; "
                             "'tutto' = tutto il libro in un solo file")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="non fare domande: usa i dati trovati nel libro e le opzioni indicate")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="non mostrare l'avanzamento, solo il risultato finale")
    parser.add_argument("--force", action="store_true",
                        help="rigenera anche le copie di lavoro gia' esistenti (sovrascrive le tue note)")
    args = parser.parse_args(argv)
    group_size = _parse_group(args.raggruppa)
    if group_size is None:
        parser.error("--raggruppa vuole un numero (1, 2, 3...) oppure 'tutto'")

    progress = None if args.quiet else (lambda msg: print(f"--> {msg}"))

    # --- Dati del libro: quelli trovati nell'EPUB, corretti con le opzioni e con le domande
    try:
        meta = read_epub_metadata(args.epub)
    except EpubError as exc:
        log_error(args.epub.name, str(exc))
        print(f"[!] ERRORE: {exc}", file=sys.stderr)
        return 1

    if args.title is not None:
        meta.title = args.title.strip()
    if args.author:
        meta.authors = [a for value in args.author for a in _split_authors(value)]
    if args.publisher is not None:
        meta.publisher = args.publisher.strip()
    tags = _split_tags(args.tag)

    # Si fanno domande solo se c'e' qualcuno davanti alla console e per i dati non indicati.
    if not args.yes and sys.stdin.isatty():
        missing = [args.title is None, not args.author, args.publisher is None, not args.tag]
        if any(missing):
            print("Dati del libro (Invio = conferma, scrivi per cambiare, - per lasciare vuoto):")
            try:
                if args.title is None:
                    meta.title = _ask("Titolo", meta.title)
                if not args.author:
                    current = "; ".join(meta.authors)
                    answer = _ask("Autore (piu' autori: separali con ;)", current)
                    if answer != current:
                        meta.authors = _split_authors(answer)
                if args.publisher is None:
                    meta.publisher = _ask("Editore", meta.publisher)
                if not args.tag:
                    tags = _split_tags([_ask("Tag per tutte le pagine (separati da virgola)", "",
                                             empty="nessuno")])
            except (EOFError, KeyboardInterrupt):
                print("\nOperazione annullata.")
                return 1
            print()

    try:
        report = convert(args.epub, args.out, on_progress=progress,
                         overwrite_working=args.force, metadata=meta, tags=tags,
                         nav_uri=(args.nav == "uri"), vault_name=args.vault,
                         with_originals=not args.no_originals, group_size=group_size)
    except EpubError as exc:
        print(f"[!] ERRORE: {exc}", file=sys.stderr)
        return 1

    for warning in report.warnings:
        print(f"[!] Attenzione: {warning}")
    print(f"\n[OK] {report.title}")
    print(f"     Autore:  {'; '.join(report.authors) or '(non indicato)'}")
    print(f"     Editore: {report.publisher or '(non indicato)'}")
    if report.tags:
        print(f"     Tag:     {', '.join(report.tags)}")
    print(f"     {report.chapters} capitoli, {report.images} immagini, "
          f"{report.skipped_pages} pagine vuote saltate")
    if report.files != report.chapters:
        print(f"     Raggruppati in {report.files} {'file' if report.files != 1 else 'solo file'} per versione")
    print(f"     Copie di lavoro: {report.out_dir.resolve()}")
    if report.originals_dir is not None:
        print(f"     Originali:       {report.originals_dir.resolve()}")
    if report.style_path is not None:
        if report.style_in_vault:
            print(f"     Stile: {report.style_path}")
            print("            -> attivalo in Obsidian: Impostazioni > Aspetto > Frammenti CSS > LiberMD")
        else:
            print(f"     Stile: {report.style_path}")
            print("            -> copialo in <tuo vault>/.obsidian/snippets/ e attivalo in "
                  "Impostazioni > Aspetto > Frammenti CSS")
    if report.kept_existing:
        print(f"     {report.kept_existing} file di lavoro gia' esistenti lasciati intatti "
              f"(usa --force per rigenerarli)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
