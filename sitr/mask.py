"""Replace detected spans with placeholders; restore only what this request's own mapping knows.

Names, emails and phones get numbered placeholders and a reversible mapping. Emirates IDs
become a fixed token and are never stored anywhere.
"""

from __future__ import annotations

import re
from collections import Counter

from sitr.detect import EID, Span

EID_PLACEHOLDER = "[EID_MASKED]"
PLACEHOLDER_RE = re.compile(r"\[(?:NAME|EMAIL|PHONE)_\d+\]")


class Masker:
    """Per-request state. `apply` may be called more than once; numbering continues."""

    def __init__(self) -> None:
        self.mapping: dict[str, str] = {}  # placeholder -> original; EIDs never enter
        self.counts: Counter[str] = Counter()
        self._by_value: dict[tuple[str, str], str] = {}  # same value -> same placeholder
        self._seq: Counter[str] = Counter()

    def apply(self, text: str, spans: list[Span]) -> str:
        out: list[str] = []
        pos = 0
        for span in spans:  # sorted and non-overlapping, per detect()
            out.append(text[pos : span.start])
            out.append(self._placeholder(span))
            pos = span.end
        out.append(text[pos:])
        return "".join(out)

    def _placeholder(self, span: Span) -> str:
        self.counts[span.category] += 1
        if span.category == EID:
            return EID_PLACEHOLDER
        key = (span.category, span.text.strip().lower())
        if key not in self._by_value:
            self._seq[span.category] += 1
            self._by_value[key] = f"[{span.category}_{self._seq[span.category]}]"
            self.mapping[self._by_value[key]] = span.text
        return self._by_value[key]


def restore(text: str, mapping: dict[str, str]) -> tuple[str, list[str]]:
    """Restore known placeholders. Unknown ones stay literal and are returned for review."""
    unknown: list[str] = []

    def sub(m: re.Match[str]) -> str:
        token = m.group()
        if token in mapping:
            return mapping[token]
        unknown.append(token)
        return token

    return PLACEHOLDER_RE.sub(sub, text), unknown
