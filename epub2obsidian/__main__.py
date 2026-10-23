"""Permette `python -m epub2obsidian libro.epub`."""
import sys

from .cli import main

sys.exit(main())
