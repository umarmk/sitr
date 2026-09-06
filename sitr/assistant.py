"""Rule-based request handling on masked text: classify by keywords, list missing items, draft.

Everything it matches against and every sentence it writes comes from config.yaml.
"""

from __future__ import annotations

from sitr.config import Config, RequestType


def classify(text: str, config: Config) -> RequestType | None:
    scores = {
        key: sum(1 for rx in rt.keywords if rx.search(text))
        for key, rt in config.request_types.items()
    }
    best = max(scores, key=scores.__getitem__)  # ponytail: ties go to config order
    return config.request_types[best] if scores[best] > 0 else None


def missing_items(text: str, rt: RequestType) -> list[str]:
    return [item for item, cues in rt.required.items() if not any(rx.search(text) for rx in cues)]


def draft(text: str, rt: RequestType, missing: list[str], config: Config) -> str:
    d = config.drafts
    # The model only ever sees placeholders; the greeting is restored to a real name later.
    greeting = d["greeting_named"] if "[NAME_1]" in text else d["greeting_anonymous"]
    if missing:
        items = ", ".join(item.replace("_", " ") for item in missing)
        body = d["body_missing"].format(label=rt.label, items=items)
    else:
        body = d["body_complete"].format(label=rt.label)
    return f"{greeting}\n\n{body}\n\n{d['sign_off']}"
