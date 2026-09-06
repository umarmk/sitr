# ADR 0001 — Python ≥ 3.12 with uv

**Status:** accepted · 2026-09-06

**Context.** The assessment requires that a stranger can run the project out of the box.
Reproducibility and a one-command install matter more than language choice.

**Decision.** Python with `requires-python = ">=3.12"`, `.python-version` pinned to 3.12,
`uv` as the package manager, `uv.lock` committed. `pip install -e .` documented as the
no-uv fallback. Wheels for every dependency were verified for 3.12–3.14 before pinning.

**Consequences.** `uv sync` fetches a matching interpreter if none is present, so the
install story holds on a clean machine. CI tests the lowest and highest supported
versions. Contributors need `uv`; the fallback covers those who refuse it.
