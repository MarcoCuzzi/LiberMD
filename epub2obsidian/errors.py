"""Errori "attesi" dell'applicazione."""


class EpubError(Exception):
    """Errore "atteso" (file mancante, EPUB non valido...): si mostra solo il messaggio."""
