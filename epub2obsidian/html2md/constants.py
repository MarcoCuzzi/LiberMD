"""Tag HTML e marcatori Markdown usati dal convertitore."""

HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
IGNORED = {"script", "style", "head", "title"}
BLOCK_TAGS = {
    "p", "div", "section", "article", "aside", "header", "footer", "main", "nav",
    "figure", "figcaption", "address", "center", "dl", "dt", "dd", "details", "summary",
}
MARKERS = {
    "b": "**", "strong": "**",
    "i": "*", "em": "*",
    "s": "~~", "strike": "~~", "del": "~~",
    "code": "`",
}
# Solo questi collegamenti diventano [testo](url); quelli interni all'EPUB restano testo semplice.
EXTERNAL_LINKS = ("http://", "https://", "mailto:")
