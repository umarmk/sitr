"""Model interface. RuleBasedModel is offline mode; a real model plugs in behind the same Protocol.

Whatever implements `Model` only ever receives masked text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sitr import assistant
from sitr.config import Config

UNKNOWN = "unknown"


@dataclass(frozen=True)
class ModelOutput:
    request_type: str  # a key of config.request_types, or UNKNOWN
    missing_items: list[str]
    draft_reply: str


class ModelError(Exception):
    """The model could not produce a usable answer (network, timeout, malformed response)."""


class Model(Protocol):
    def complete(self, masked_text: str) -> ModelOutput: ...


class RuleBasedModel:
    def __init__(self, config: Config) -> None:
        self.config = config

    def complete(self, masked_text: str) -> ModelOutput:
        rt = assistant.classify(masked_text, self.config)
        if rt is None:
            return ModelOutput(UNKNOWN, [], "")
        missing = assistant.missing_items(masked_text, rt)
        return ModelOutput(rt.key, missing, assistant.draft(masked_text, rt, missing, self.config))
