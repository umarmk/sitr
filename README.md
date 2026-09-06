# sitr

*sitr* (Arabic ستر — to veil, to shield) is a privacy boundary that sits between people's
messages and AI models. Text goes in, personal data is taken out, only the cleaned text
reaches a model, and the reply comes back with the personal data restored for the human
who needs it.

It ships with a small reference assistant for an employee-services desk (salary
certificates, NOC letters, leave, IT access) to show the boundary doing real work. The
assistant only ever sees cleaned text. That is the point: it does its job without ever
seeing anyone's personal data.

**Offline mode is the complete product.** It needs no API key, no account, no network and
no separate model download. AI mode is optional; it exists to show that the same boundary
holds when a real model is behind it, and nobody has to run it to evaluate the project.

## What happens to a message

```mermaid
flowchart LR
    A[Employee text] --> B[Validate]
    B --> C[Detect personal data]
    C --> D[Mask]
    D --> E[Check destination policy]
    E --> F[Re-check outgoing text]
    F --> G{Mode}
    G -->|offline| H[Rule-based assistant]
    G -->|ai| I[Approved model<br/>sees placeholders only]
    H --> J[Validate answer]
    I --> J
    J --> K[Restore known placeholders]
    K --> L[Re-check reply]
    L --> M[Draft for a person + audit record]
```

1. **Validate.** Empty, oversized, non-English, suspicious, or placeholder-containing input
   is handed to a person with the reason stated. sitr never crashes and never guesses.
2. **Detect.** Emirates ID numbers, UAE mobile numbers and email addresses by pattern;
   personal names with a small statistical model that installs as an ordinary dependency.
3. **Mask.** Names, emails and phones become `[NAME_1]`, `[EMAIL_1]`, `[PHONE_1]` with a
   mapping held in memory for this request only. Emirates IDs become `[EID_MASKED]` and
   are never stored, mapped or restored.
4. **Check policy.** In AI mode the destination must be declared and approved in
   `policy.yaml`. Anything else is refused before any text moves.
5. **Re-check.** Every detector runs again on the outgoing text. If anything is found, the
   request is refused and nothing is sent.
6. **Answer.** Offline, a rule-based assistant classifies the request, lists what is
   missing and drafts a reply. In AI mode a model does the same from the masked text.
7. **Validate the answer.** It must be well-formed and name a known request type.
8. **Restore.** Only placeholders from this request's own mapping are put back. Anything
   else stays literal and the result is flagged for review.
9. **Re-check the reply** for Emirates IDs before it is shown.
10. **Audit.** One JSON line per request: categories and counts, destination, decision,
    reason. Never the text, never the mapping.

| Never leaves the boundary | Leaves only in AI mode | In the audit record |
|---|---|---|
| Raw text, the placeholder mapping, Emirates ID values | The masked text, to the one approved destination in `policy.yaml` | Counts per category, destination (provider, region, approved), request type, decision, reason |

## Quick start

With [uv](https://docs.astral.sh/uv/). Python 3.12+ is fetched automatically if missing.

```bash
git clone https://github.com/umarmk/sitr && cd sitr
uv sync                                        # everything, including the name model
uv run pytest -q                               # the whole suite; nothing touches the network
uv run sitr templates                          # example requests (all people fictional)
uv run sitr run --template salary-certificate  # one request, offline
uv run sitr serve                              # web UI at http://127.0.0.1:8000
```

Without uv, on an existing Python 3.12+:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest ruff httpx2
pytest -q
sitr serve
```

### What a run looks like

<!-- example:start -->
```
$ uv run sitr run --template salary-certificate
sitr.audit {"request_id":"…","timestamp":"…","mode":"offline","destination":{"name":"offline","provider":"local","region":"local","approved":true},"categories":{"NAME":1,"EID":1,"PHONE":1,"EMAIL":1},"request_type":"salary_certificate","decision":"drafted","refusal_reason":null}
decision      drafted
request type  salary_certificate
missing       -
destination   offline · local · local · approved
detected      EID 1, EMAIL 1, NAME 1, PHONE 1

--- what the model saw ---
Hello, my name is [NAME_1] and I work in the finance team. I need a salary certificate addressed to Emirates NBD for a car loan. My Emirates ID is [EID_MASKED]. Please call me on [PHONE_1] or email [EMAIL_1] if you need anything else.

--- draft reply (restored, for a person to review) ---
Dear Sarah Mitchell,

Thank you for your salary certificate request. We have everything we need and will process it shortly.

Kind regards,
Employee Services
```
<!-- example:end -->

The first line is the audit record, written to stderr. The draft is restored for the
person who will review and send it; the model never saw the name.

`sitr run` also accepts free text as an argument or on stdin, `--json` for the full
result, and exits `0` when a draft was produced, `1` when the request was handed to a
person, `2` on a usage error.

## The web UI

`uv run sitr serve` binds to `127.0.0.1:8000` by default. Pass `--host 0.0.0.0` only if
you mean to expose it.

The page offers the two modes, the example requests as templates, and free text. Every
result shows the decision, the destination (provider, region, approved or not), the
request type and missing items, the personal-data counts, **the exact text the model saw**,
the restored draft, and the audit record. AI mode is shown disabled, with the reason, on a
machine that cannot run it. No secret ever reaches the browser: the server reports only a
boolean for "AI available", and there is no key field in the page.

The API behind it is three endpoints, documented at `/docs`: `GET /api/capabilities`,
`GET /api/templates`, `POST /api/process`.

| A drafted request | A refusal, handed to a person |
|---|---|
| ![The salary-certificate template processed offline: the masked text the model saw, the restored draft, and the audit record](docs/screenshot-drafted.png) | ![The manipulation-attempt template refused as suspected_manipulation, with the reason and an audit record](docs/screenshot-refusal.png) |

## AI mode (optional)

AI mode sends the masked text, and only the masked text, to one destination declared in
`policy.yaml`, through [OpenRouter](https://openrouter.ai/). It reads one secret from the
environment and nothing else.

```bash
cp .env.example .env            # put OPENROUTER_API_KEY in it; .env is gitignored
uv run --env-file .env sitr serve
uv run --env-file .env sitr run --mode ai --template noc-letter
```

The default destination in `policy.yaml` names a free-tier model, so trying AI mode costs
nothing beyond a key. Change `destinations[].model` to any OpenRouter model ID.

To see the policy refuse, ask for the destination that is declared but not approved:

```bash
uv run --env-file .env sitr run --mode ai --destination example-unapproved --template leave
# decision      handed_to_person (destination_not_approved: destination 'example-unapproved' (ExampleCloud, EU) is not approved)
```

Nothing was sent; the audit record says so.

## Configuration

Nothing behavioural is hardcoded. Two YAML files at the project root:

- **`policy.yaml`** — what may go where. Each destination has a name, provider, region,
  `approved: true|false` (a real boolean; a quoted string is rejected at load), and the
  model ID. Undeclared destinations are refused. Offline mode never reads this file.
- **`config.yaml`** — how the assistant behaves: the input cap, model timeout and
  temperature, the system prompt, the four request types with their keywords and
  required-item cues, the sentences the offline assistant writes, the manipulation
  patterns, and the example templates. Every keyword and cue is a case-insensitive
  regular expression.

`OPENROUTER_API_KEY` is the only environment variable. See `.env.example`.

## When sitr says no

Each refusal is handed to a person with the reason stated, and still produces an audit record.

| Reason | Trigger |
|---|---|
| `empty`, `too_long` | Blank input, or more than the configured cap (4,000 characters) |
| `non_english` | Arabic script, or mostly non-ASCII letters |
| `suspected_manipulation` | Instruction-like phrases ("ignore previous instructions"), or literal placeholder tokens in the input |
| `unrecognised_request` | No known request type matched |
| `destination_not_approved` | AI mode with a destination that is undeclared or `approved: false` |
| `outgoing_recheck_failed` | Personal data survived masking, or an Emirates ID appeared in the reply |
| `model_unavailable` | No key, or the gateway could not be reached or errored |
| `model_output_invalid` | The model did not return a well-formed JSON answer with a known request type |

## Tests and CI

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

The suite runs without a network connection and covers, among other things:

- the offline flow end to end, with names restored and the Emirates ID masked;
- **no personal data in logs or audit records**, asserted over captured log output;
- the outgoing re-check refusing when masking is deliberately broken;
- every refusal reason;
- a lossless mask-and-restore round trip, and the Emirates ID never being restorable;
- the policy refusing undeclared and unapproved destinations;
- AI mode against an in-process fake gateway: only placeholders leave, the key never
  appears in any output, and HTTP, JSON and closed-set failures are refused, not raised;
- the web endpoints and the CLI.

CI runs the same commands on Python 3.12 and 3.14 for every pull request. `main` is
PR-only.

## Project layout

```
sitr/
  boundary.py    process(): the orchestration above
  detect.py      regex + spaCy detectors behind one detect()
  mask.py        placeholders, per-request mapping, restore()
  policy.py      destination resolution and refusal
  model.py       Model protocol, RuleBasedModel (offline), OpenRouterModel (AI)
  assistant.py   keyword classification, missing items, drafts (all from config)
  audit.py       one JSON line per request via logging
  config.py      policy.yaml / config.yaml loaders
  refusal.py     the one exception that hands a request to a person
  cli.py         sitr run | templates | serve
  web.py         FastAPI app; static/index.html is the page
policy.yaml, config.yaml
tests/           pytest; fake gateway for AI mode
docs/            SPEC.md, ARCHITECTURE.md, adr/
```

## Limitations

Stated, not hidden:

- Name detection is a small statistical model (`en_core_web_sm`). It misses lowercase or
  uncommon names and can flag non-names. Precision is not measured.
- Phone detection covers UAE mobile formats; landlines and foreign numbers are not detected.
- Emirates ID detection is format-based, with no checksum.
- The manipulation check is a keyword heuristic, not a classifier.
- English only. The language check is a script heuristic.
- The outgoing re-check reuses the same detectors as masking. It catches masking faults,
  not formats the detectors do not know.
- The placeholder mapping lives in process memory for one request. There is no retention
  policy because there is nothing retained.

## With more time

A recorded mode that replays real model responses without keys; Arabic-script names and
Arabic-Indic digits; a placeholder store behind a secrets manager with retention rules; a
measured detection-quality set; per-business-unit policy packs; rate and spend limits for
a hosted instance.

## Documentation

- [Specification](docs/SPEC.md) — scope, requirements, refusal conditions, acceptance tests
- [Architecture](docs/ARCHITECTURE.md) — data flow, modules, configuration, trust boundaries
- [Decision records](docs/adr/) — why each significant choice was made

sitr is not a compliance product and makes no compliance claims. It is one technical
control that supports data minimisation. All sample data is synthetic; no real people, ever.
