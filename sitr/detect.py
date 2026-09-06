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

_PATTERNS = {
    # 784-YYYY-NNNNNNN-N, separators optional. Format only, no checksum.
    EID: re.compile(r"\b784[- ]?\d{4}[- ]?\d{7}[- ]?\d\b"),
    # UAE mobiles: +971 / 00971 / 971 (optionally followed by "(0)") or a leading 0, then 5x
    # and seven digits, separators optional.
    PHONE: re.compile(
        r"(?<!\d)(?:(?:\+|00)?971[\s-]?(?:\(0\)[\s-]?)?|0)5\d[\s-]?\d{3}[\s-]?\d{4}(?!\d)"
    ),
    EMAIL: re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}


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


def detect(text: str) -> list[Span]:
    """All personal-data spans in `text`, sorted by position, non-overlapping."""
    found = [
        Span(category, m.start(), m.end(), m.group())
        for category, rx in _PATTERNS.items()
        for m in rx.finditer(text)
    ]
    found += [
        Span(NAME, ent.start_char, ent.end_char, ent.text)
        for ent in _nlp()(text).ents
        # spaCy tags sentence-initial common nouns ("Salary ...") as PERSON; a name has a
        # proper noun in it.
        if ent.label_ == "PERSON" and any(t.pos_ == "PROPN" for t in ent)
    ]
    chosen: list[Span] = []
    for span in sorted(found, key=lambda s: (s.start - s.end, PRIORITY[s.category], s.start)):
        if all(span.end <= c.start or span.start >= c.end for c in chosen):
            chosen.append(span)
    return sorted(chosen, key=lambda s: s.start)


def contains_eid(text: str) -> bool:
    return _PATTERNS[EID].search(text) is not None
