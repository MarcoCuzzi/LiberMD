#!/usr/bin/env python3
"""Launcher: `python epub_to_obsidian.py libro.epub [-o cartella]` (come prima)."""
import sys

from epub2obsidian.cli import main

if __name__ == "__main__":
    sys.exit(main())
