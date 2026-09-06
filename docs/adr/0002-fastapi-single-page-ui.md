# ADR 0002 — FastAPI with a single static HTML page, CLI alongside

**Status:** accepted · 2026-09-06

**Context.** A minimal UI is wanted for demos, but visual polish is not assessed and time
is a few hours. Input validation must live at the trust boundary.

**Decision.** FastAPI + uvicorn serving one `static/index.html` with vanilla JS. No
frontend build, no framework. Server binds `127.0.0.1` by default. A CLI (`sitr run`,
`sitr templates`, `sitr serve`) wraps the same `process()` function so the project is
usable and testable without a browser. Secrets never reach the browser: no key field,
`/api/capabilities` returns booleans only.

**Consequences.** Two well-known dependencies buy pydantic validation of the size cap and
mode enum, plus `/docs`. Rejected: stdlib `http.server` (hand-rolled validation),
Streamlit/Gradio (heavy install, notebook look).
