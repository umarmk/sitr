"""Command line: `sitr run`, `sitr templates`, `sitr serve`. A thin wrapper over process().

Exit codes for `run`: 0 drafted, 1 handed to a person, 2 usage or configuration error.
Audit lines go to stderr so `--json` output on stdout stays machine-readable.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict

from sitr.boundary import MODES, Result, process
from sitr.config import ConfigError, load_config


def _cmd_templates(_: argparse.Namespace) -> int:
    for t in load_config().templates:
        print(f"{t.id:22} {t.title}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    if args.template:
        match = [t.text for t in load_config().templates if t.id == args.template]
        if not match:
            print(f"unknown template: {args.template} (see `sitr templates`)", file=sys.stderr)
            return 2
        text = match[0]
    elif args.text is not None:
        text = args.text
    else:
        # Bytes, not text: a stray invalid byte becomes U+FFFD instead of a traceback.
        text = sys.stdin.buffer.read().decode("utf-8", "replace")
    result = process(text, mode=args.mode, destination=args.destination)
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        _print_human(result)
    return 0 if result.decision == "drafted" else 1


def _print_human(r: Result) -> None:
    d = r.destination
    reason = f" ({r.reason}: {r.reason_detail})" if r.reason else ""
    print(f"decision      {r.decision}{reason}")
    print(f"request type  {r.request_type or '-'}")
    print(f"missing       {', '.join(r.missing_items) or '-'}")
    approved = "approved" if d["approved"] else "NOT approved"
    print(f"destination   {d['name']} · {d['provider']} · {d['region']} · {approved}")
    print(f"detected      {', '.join(f'{k} {v}' for k, v in sorted(r.counts.items())) or '-'}")
    if r.needs_review:
        print("needs review  yes (the reply contained placeholders sitr does not know)")
    if r.outgoing_text is not None:
        print("\n--- what the model saw ---")
        print(r.outgoing_text)
    if r.draft_reply is not None:
        print("\n--- draft reply (restored, for a person to review) ---")
        print(r.draft_reply)


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn  # imported here so `sitr run` never pays for it

    uvicorn.run("sitr.web:app", host=args.host, port=args.port, log_level="info")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sitr", description="A privacy boundary between people's messages and AI models."
    )
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="process one message and print the result")
    run.add_argument("text", nargs="?", help="the message; omit to read stdin or use --template")
    run.add_argument("--template", help="use an example request by id (see `sitr templates`)")
    run.add_argument("--mode", choices=MODES, default="offline")
    run.add_argument("--destination", help="policy destination for AI mode (default: policy.yaml)")
    run.add_argument("--json", action="store_true", help="print the full result as JSON")
    run.set_defaults(func=_cmd_run)

    sub.add_parser("templates", help="list example requests").set_defaults(func=_cmd_templates)

    serve = sub.add_parser("serve", help="start the local web UI")
    serve.add_argument(
        "--host", default="127.0.0.1", help="bind address; pass 0.0.0.0 only to expose deliberately"
    )
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=_cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")  # audit -> stderr
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as e:
        print(f"configuration error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
