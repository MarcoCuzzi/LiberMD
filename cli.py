"""
cli.py - Interfaccia a riga di comando (CLI) per il motore di conversione.

Si occupa solo di leggere i comandi dalla console e di mostrare i risultati:
tutto il lavoro vero e' in engine.py.

Di solito non si lancia direttamente: si avvia il programma da LiberMD.py.

Uso:
    python LiberMD.py libro.epub
    python LiberMD.py libro.epub -o /percorso/del/vault
    python LiberMD.py libro.epub -q
    python LiberMD.py libro.epub --no-lock     # originali NON in sola lettura
    python LiberMD.py libro.epub --force       # rigenera anche le copie di lavoro (perdi le tue note!)
"""
import argparse
import sys
from pathlib import Path
from typing import Optional

from engine import EpubError, convert


def main(argv: Optional[list[str]] = None, prog: str = "LiberMD",
         version: Optional[str] = None) -> int:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=f"{prog} - converte un EPUB in note Markdown per Obsidian "
                    f"(originali in sola lettura + copie di lavoro con i collegamenti).",
    )
    if version:
        parser.add_argument("--version", action="version", version=f"{prog} {version}")
    parser.add_argument("epub", type=Path, help="file .epub da convertire")
    parser.add_argument("-o", "--out", type=Path, default=Path("."),
                        help="cartella in cui creare la cartella del libro (default: cartella corrente)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="non mostrare l'avanzamento, solo il risultato finale")
    parser.add_argument("--no-lock", action="store_true",
                        help="non mettere in sola lettura i file della cartella originali/")
    parser.add_argument("--force", action="store_true",
                        help="rigenera anche le copie di lavoro gia' esistenti (sovrascrive le tue note)")
    args = parser.parse_args(argv)

    progress = None if args.quiet else (lambda msg: print(f"--> {msg}"))

    try:
        report = convert(args.epub, args.out, on_progress=progress,
                         lock_originals=not args.no_lock, overwrite_working=args.force)
    except EpubError as exc:
        print(f"[!] ERRORE: {exc}", file=sys.stderr)
        return 1

    for warning in report.warnings:
        print(f"[!] Attenzione: {warning}")
    print(f"\n[OK] {report.title}")
    print(f"     Autore:  {', '.join(report.authors) or '(non indicato)'}")
    print(f"     Editore: {report.publisher or '(non indicato)'}")
    print(f"     {report.chapters} capitoli, {report.images} immagini, "
          f"{report.skipped_pages} pagine vuote saltate")
    print(f"     Copie di lavoro: {report.out_dir.resolve()}")
    print(f"     Originali:       {report.originals_dir.resolve()}"
          f"{'' if args.no_lock else '  (sola lettura)'}")
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
