# ADR 0006 — Audit record as one JSON line through `logging`

**Status:** accepted · 2026-09-06

**Context.** Every request needs an audit record that says what happened without ever
containing the data. "No personal data in logs" must be tested, not promised.

**Decision.** `sitr/audit.py` builds a record (`request_id`, `timestamp`, `mode`,
`destination{provider,region,approved}`, `categories{NAME:n,…}`, `request_type`,
`decision`, `refusal_reason`, `needs_review`) and emits it as one JSON line via the standard `logging`
module. The same record is embedded in the returned result. Message text and the
placeholder mapping are never fields.

**Consequences.** The no-PII test captures all log output with `caplog` and asserts that
none of the synthetic values appear — one test covers every log line the system emits.
Operators route the sink with ordinary logging configuration. Rejected: a bespoke
`audit.jsonl` writer (a second sink to test and document).
