"""The boundary itself.

validate -> detect -> mask -> policy -> re-check outgoing -> model -> validate output
-> restore known placeholders -> re-check reply -> audit. Any stage may raise Refusal;
`process` turns that into a handed-to-person result and still writes the audit record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sitr import audit
from sitr import policy as policies
from sitr.config import Config, Policy, load_config, load_policy
from sitr.detect import contains_eid, detect
from sitr.mask import EID_PLACEHOLDER, PLACEHOLDER_RE, Masker, restore
from sitr.model import UNKNOWN, Model, ModelError, ModelOutput, RuleBasedModel
from sitr.refusal import Refusal

_ARABIC = re.compile(r"[\u0600-\u06FF]")  # Arabic script block
MODES = ("offline", "ai")


@dataclass
class Result:
    decision: str  # "drafted" | "handed_to_person"
    reason: str | None
    reason_detail: str | None
    mode: str
    destination: dict
    request_type: str | None
    missing_items: list[str]
    draft_reply: str | None
    outgoing_text: str | None  # exactly what the model saw; None if nothing was sent
    counts: dict[str, int]
    needs_review: bool
    audit: dict


def _validate(text: str, config: Config) -> None:
    if not text.strip():
        raise Refusal("empty", "the message is empty")
    if len(text) > config.input_max_chars:
        raise Refusal("too_long", f"the message exceeds {config.input_max_chars} characters")
    letters = [c for c in text if c.isalpha()]
    non_ascii = sum(not c.isascii() for c in letters)
    if _ARABIC.search(text) or (letters and non_ascii / len(letters) > 0.2):
        raise Refusal("non_english", "the message does not look like English")
    for rx in config.manipulation_patterns:
        if rx.search(text):
            raise Refusal(
                "suspected_manipulation",
                "the message looks like an attempt to steer the assistant",
            )
    if PLACEHOLDER_RE.search(text) or EID_PLACEHOLDER in text:
        # A literal placeholder in the input would be restored into real data on the way back.
        raise Refusal("suspected_manipulation", "the message contains reserved placeholder tokens")


def _mask(text: str) -> tuple[str, Masker]:
    masker = Masker()
    masked = masker.apply(text, detect(text))
    # ponytail: spaCy sometimes only recognises a name once its neighbours are masked.
    # Two extra passes catch that; anything still left is caught by the outgoing re-check.
    for _ in range(2):
        more = detect(masked)
        if not more:
            break
        masked = masker.apply(masked, more)
    return masked, masker


def _check_output(out: ModelOutput, config: Config) -> None:
    """The model is outside the trust boundary: check shape and values before use."""
    well_formed = (
        isinstance(out, ModelOutput)
        and isinstance(out.request_type, str)
        and isinstance(out.missing_items, list)
        and all(isinstance(item, str) for item in out.missing_items)
        and isinstance(out.draft_reply, str)
    )
    if not well_formed:
        raise Refusal("model_output_invalid", "the model returned a malformed answer")
    if out.request_type == UNKNOWN:
        raise Refusal("unrecognised_request", "the request does not match a known type")
    if out.request_type not in config.request_types:
        raise Refusal(
            "model_output_invalid", "the model returned a request type outside the known set"
        )


def process(
    text: str,
    *,
    mode: str = "offline",
    destination: str | None = None,
    model: Model | None = None,
    config: Config | None = None,
    policy: Policy | None = None,
) -> Result:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    config = config or load_config()
    if mode == "ai":
        # Policy is consulted only when text may leave the machine; offline never needs it.
        policy = policy or load_policy()
        dest_view = policies.describe(policy, destination)
    else:
        dest_view = policies.view(policies.OFFLINE)

    counts: dict[str, int] = {}
    outgoing = request_type = draft_reply = None
    missing: list[str] = []
    needs_review = False
    try:
        _validate(text, config)
        masked, masker = _mask(text)
        counts = dict(masker.counts)
        if mode == "ai":
            policies.resolve(policy, destination)
        if detect(masked):
            raise Refusal(
                "outgoing_recheck_failed", "personal data survived masking; nothing was sent"
            )
        if model is None:
            if mode == "ai":
                # ponytail: the real model lands in the next PR; until then AI mode says so
                raise Refusal("model_unavailable", "no AI model is configured")
            model = RuleBasedModel(config)
        outgoing = masked
        try:
            out = model.complete(masked)
        except ModelError as e:  # ModelError messages are static; they never carry text
            raise Refusal("model_unavailable", str(e)) from e
        _check_output(out, config)
        request_type, missing = out.request_type, list(out.missing_items)
        draft_reply, unknown = restore(out.draft_reply, masker.mapping)
        needs_review = bool(unknown)
        if contains_eid(draft_reply):
            draft_reply = None
            raise Refusal("outgoing_recheck_failed", "the reply contained an Emirates ID")
        decision, reason, detail = "drafted", None, None
    except Refusal as r:
        decision, reason, detail = "handed_to_person", r.reason, r.detail

    rec = audit.record(
        mode=mode,
        destination=dest_view,
        counts=counts,
        request_type=request_type,
        decision=decision,
        refusal_reason=reason,
    )
    return Result(
        decision=decision,
        reason=reason,
        reason_detail=detail,
        mode=mode,
        destination=dest_view,
        request_type=request_type,
        missing_items=missing,
        draft_reply=draft_reply,
        outgoing_text=outgoing,
        counts=counts,
        needs_review=needs_review,
        audit=rec,
    )
