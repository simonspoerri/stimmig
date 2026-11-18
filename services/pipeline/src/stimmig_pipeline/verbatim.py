"""Quote check: an extracted claim is only kept if its quote appears in the source text.

The comparison ignores whitespace, typographic quote and dash variants and soft
hyphens – things that differ between a PDF extract and what a model echoes
back – but nothing else.
"""

import re
import unicodedata

_REPLACEMENTS = [
    (re.compile("­"), ""),  # soft hyphen
    (re.compile('[«»„“”"]'), '"'),
    (re.compile("[‹›‚‘’']"), "'"),
    (re.compile("[‐‑‒–—]"), "-"),
    (re.compile(r"\s+"), " "),
]


def normalize_for_quote_match(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    for pattern, replacement in _REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text.strip()


def is_verbatim(quote: str, source: str) -> bool:
    needle = normalize_for_quote_match(quote)
    return bool(needle) and needle in normalize_for_quote_match(source)
