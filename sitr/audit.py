"""One JSON audit line per request through `logging`.

Categories, counts, destination and decision. Never the text, never the mapping.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

log = logging.getLogger("sitr.audit")


def record(
    *,
    mode: str,
    destination: dict,
    counts: dict[str, int],
    request_type: str | None,
    decision: str,
    refusal_reason: str | None,
) -> dict:
    rec = {
        "request_id": uuid.uuid4().hex,
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "mode": mode,
        "destination": destination,
        "categories": dict(counts),
        "request_type": request_type,
        "decision": decision,
        "refusal_reason": refusal_reason,
    }
    log.info(json.dumps(rec, separators=(",", ":")))
    return rec
