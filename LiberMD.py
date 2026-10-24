"""
LiberMD.py - Punto di partenza del programma.

E' l'unico file che si lancia. Non contiene logica: decide solo quale interfaccia
avviare. Tutto il lavoro vero e' negli altri file:

    LiberMD.py -> cli.py -> engine/ -> writer.py -> nav.py
                                |            |
                                +------------+--> sanitizer.py
                                (engine e writer usano entrambi il sanificatore)

Uso:
    python LiberMD.py libro.epub
    python LiberMD.py libro.epub -o /percorso/del/vault
    python LiberMD.py --help
    python LiberMD.py --version
"""
import sys
from typing import Optional

APP_NAME = "LiberMD"
APP_VERSION = "0.1.0"


def run(argv: Optional[list[str]] = None) -> int:
    """Avvia il programma. Ritorna il codice di uscita (0 = tutto ok)."""
    from cli import main as cli_main

    args = sys.argv[1:] if argv is None else argv

    # Nessun argomento: per ora mostriamo l'aiuto.
    # In futuro, qui si aprira' l'interfaccia grafica (gui.py).
    if not args:
        args = ["--help"]

    return cli_main(args, prog=APP_NAME, version=APP_VERSION)


if __name__ == "__main__":
    sys.exit(run())
