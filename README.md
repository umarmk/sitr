# sitr

*sitr* (Arabic ستر — to veil, to shield) is a privacy boundary that sits between people's
messages and AI models. Text goes in, personal data is taken out, only the cleaned text
reaches a model, and the reply comes back with the personal data restored for the human
who needs it.

It ships with a small reference assistant for an employee-services desk (salary
certificates, NOC letters, leave, IT access) to show the boundary doing real work. The
assistant only ever sees cleaned text. Offline mode is the default and needs no keys, no
network and no accounts.

## Quick start

With [uv](https://docs.astral.sh/uv/) (recommended; Python 3.12+ is fetched automatically if missing):

```bash
uv sync
uv run pytest
```

Without uv, on an existing Python 3.12+:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest ruff
pytest
```

Either way the name-detection model is installed as an ordinary dependency; there is no
separate download step.

Run commands (`sitr run`, `sitr serve`) land in the next PRs; see the docs below for the
design.

## Documentation

- [Specification](docs/SPEC.md) — scope, requirements, refusal conditions, acceptance tests, limitations
- [Architecture](docs/ARCHITECTURE.md) — data flow, modules, configuration, threat notes
- [Decision records](docs/adr/) — why each significant choice was made

sitr is not a compliance product and makes no compliance claims. All sample data is synthetic.
