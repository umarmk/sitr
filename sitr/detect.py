"""Find personal data in text. Regex for structured identifiers, spaCy PERSON for names.

One entry point, `detect`, is used by masking and by both re-checks, so a new category is
one pattern here and nowhere else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

EID, PHONE, EMAIL, NAME = "EID", "PHONE", "EMAIL", "NAME"

# When spans overlap, the longest wins so nothing is left half-masked (a phone number inside
# an email address); equal lengths go to the more specific pattern.
PRIORITY = {EID: 0, PHONE: 1, EMAIL: 2, NAME: 3}

# The UAE country code as people type it: +971, 00971 or 971, optionally followed by "(0)".
_UAE = r"(?:\+|00)?971[\s-]?(?:\(0\)[\s-]?)?"
_PATTERNS = {
    # 784-YYYY-NNNNNNN-N, separators optional. Format only, on purpose: a checksum would just
    # teach sitr to ignore mistyped IDs, and a mistyped ID is still personal data.
    EID: re.compile(r"\b784[- ]?\d{4}[- ]?\d{7}[- ]?\d\b"),
    PHONE: re.compile(
        r"(?<!\d)(?:"
        # UAE mobile (5x + 7 digits) or landline (area code 2/3/4/6/7/9 + 7 digits)
        rf"(?:{_UAE}|0)(?:5\d|[2-4679])[\s-]?\d{{3}}[\s-]?\d{{4}}"
        # any other international number: + or 00, country code, an optional parenthesised
        # area code or trunk zero, then 7-12 digits
        r"|(?:\+|00)\d{1,3}[\s-]?(?:\(\d{1,4}\)[\s-]?)?\d(?:[\s-]?\d){6,11}"
        r")(?!\d)"
    ),
    EMAIL: re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}
# Arabic-Indic (U+0660..) and Extended Arabic-Indic (U+06F0..) digits map onto ASCII one to
# one, so offsets found on the normalised copy are valid on the original text.
DIGITS = {0x0660 + i: str(i) for i in range(10)} | {0x06F0 + i: str(i) for i in range(10)}


@dataclass(frozen=True)
class Span:
    category: str
    start: int
    end: int
    text: str


@lru_cache(maxsize=1)
def _nlp():
    import spacy  # imported here so the ~1 s model load happens once, on first use

    return spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])


def warm() -> None:
    """Load the name model now rather than on the first request; `sitr serve` calls this."""
    _nlp()


def _not_name(token) -> bool:
    """A possessive 's or anything with a digit: spaCy glues these onto PERSON entities."""
    return token.lower_ in ("'s", "’s") or any(c.isdigit() for c in token.text)


def _names(text: str) -> list[Span]:
    spans = []
    for ent in _nlp()(text).ents:
        # spaCy tags sentence-initial common nouns ("Salary ...") as PERSON; a name has a
        # proper noun in it.
        if ent.label_ != "PERSON" or not any(t.pos_ == "PROPN" for t in ent):
            continue
        tokens = list(ent)
        while tokens and _not_name(tokens[-1]):
            tokens.pop()
        while tokens and _not_name(tokens[0]):
            tokens.pop(0)
        if tokens:
            start, end = tokens[0].idx, tokens[-1].idx + len(tokens[-1])
            spans.append(Span(NAME, start, end, text[start:end]))
    return spans


def detect(text: str) -> list[Span]:
    """All personal-data spans in `text`, sorted by position, non-overlapping."""
    ascii_digits = text.translate(DIGITS)
    found = [
        Span(category, m.start(), m.end(), text[m.start() : m.end()])
        for category, rx in _PATTERNS.items()
        for m in rx.finditer(ascii_digits)
    ]
    found += _names(text)
    chosen: list[Span] = []
    # An EID always wins: it must never end up inside a reversible placeholder.
    order = sorted(
        found, key=lambda s: (s.category != EID, s.start - s.end, PRIORITY[s.category], s.start)
    )
    for span in order:
        if all(span.end <= c.start or span.start >= c.end for c in chosen):
            chosen.append(span)
    return sorted(chosen, key=lambda s: s.start)


def contains_eid(text: str) -> bool:
    return _PATTERNS[EID].search(text.translate(DIGITS)) is not None
