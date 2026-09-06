# ADR 0005 — YAML configuration, split into policy and behaviour

**Status:** accepted · 2026-09-06

**Context.** The destination policy must be configuration, not code. Model parameters,
prompts, request types and templates should also be editable without touching Python.

**Decision.** Two files at the project root, parsed with `yaml.safe_load` into
dataclasses by `sitr/config.py`:

- `policy.yaml` — destinations only (name, provider, region, approved, model). A
  security control; short, reviewable in ten seconds.
- `config.yaml` — input cap, model timeout/temperature/system prompt, request types with
  keywords and required items, example templates, manipulation patterns.

**Consequences.** One dependency (`pyyaml`) in exchange for comments and readability.
The split makes "what may go where" auditable separately from "how it behaves" and is
the seam for per-unit policy packs later. Rejected: TOML (no comments in arrays of
tables read poorly), JSON (no comments).
