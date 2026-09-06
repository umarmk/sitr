# ADR 0003 — spaCy for names, regex for structured identifiers

**Status:** accepted · 2026-09-06

**Context.** Emirates IDs, UAE mobiles and emails have fixed formats. Names do not.
The install must need no separate model download or account.

**Decision.** Regex detectors for EID, phone and email. spaCy `en_core_web_sm` (`PERSON`
entities) for names, pinned as a direct-URL wheel dependency in `pyproject.toml` so it
arrives with `uv sync`. All detectors sit behind one `detect(text)` function used by
masking and by both re-checks, so adding a category is one function.

**Consequences.** Install is ~60 MB heavier and the model loads once per process (~1 s):
when `sitr serve` starts, or on the first `sitr run`.
Name precision is stated as a limitation, not measured. Rejected: capitalisation
heuristics (poor recall, many false positives), transformer NER (too heavy for the
install constraint).
