"""Model interface and both implementations.

`RuleBasedModel` is offline mode. `OpenRouterModel` is AI mode: one POST to an
OpenAI-compatible gateway over stdlib urllib, key from the environment. Whatever implements
`Model` only ever receives masked text, and nothing in this module logs anything.
"""

from __future__ import annotations

import http.client
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from sitr import assistant
from sitr.config import Config, Destination, ModelConfig

UNKNOWN = "unknown"
API_KEY_ENV = "OPENROUTER_API_KEY"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class ModelOutput:
    request_type: str  # a key of config.request_types, or UNKNOWN
    missing_items: list[str]
    draft_reply: str


class ModelError(Exception):
    """The model could not be reached or did not answer (network, timeout, HTTP error)."""


class InvalidModelOutput(Exception):
    """The model answered, but not with the JSON object it was asked for."""


class Model(Protocol):
    def complete(self, masked_text: str) -> ModelOutput: ...


def ai_available() -> bool:
    """True when this machine can run AI mode at all (a key is present)."""
    return bool(os.environ.get(API_KEY_ENV))


class RuleBasedModel:
    def __init__(self, config: Config) -> None:
        self.config = config

    def complete(self, masked_text: str) -> ModelOutput:
        rt = assistant.classify(masked_text, self.config)
        if rt is None:
            return ModelOutput(UNKNOWN, [], "")
        missing = assistant.missing_items(masked_text, rt)
        return ModelOutput(rt.key, missing, assistant.draft(masked_text, rt, missing, self.config))


class OpenRouterModel:
    def __init__(
        self,
        destination: Destination,
        model_config: ModelConfig,
        *,
        api_key: str | None,
        base_url: str | None = None,
    ) -> None:
        self.destination = destination
        self.model_config = model_config
        self.api_key = api_key
        self.base_url = base_url or OPENROUTER_BASE_URL

    def complete(self, masked_text: str) -> ModelOutput:
        if not self.api_key:
            raise ModelError(f"{API_KEY_ENV} is not set")
        payload = {
            "model": self.destination.model,
            "temperature": self.model_config.temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self.model_config.system_prompt},
                {"role": "user", "content": masked_text},
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                # Recommended by OpenRouter for attribution; carry no data.
                "HTTP-Referer": "https://github.com/umarmk/sitr",
                "X-Title": "sitr",
            },
            method="POST",
        )
        # Error messages below are static on purpose: they end up in results and audit records.
        try:
            with urllib.request.urlopen(request, timeout=self.model_config.timeout_seconds) as resp:
                body = json.load(resp)
        except urllib.error.HTTPError as e:
            raise ModelError(f"model request failed with HTTP {e.code}") from e
        except (OSError, http.client.HTTPException) as e:  # unreachable, timeout, truncated
            raise ModelError("model request failed") from e
        except ValueError as e:
            raise ModelError("model response was not JSON") from e
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ModelError("model response had no content") from e
        return _parse(content)


def _parse(content: object) -> ModelOutput:
    """Turn the model's text into a ModelOutput. Shape checking happens in the boundary."""
    if not isinstance(content, str):
        raise InvalidModelOutput("content is not text")
    text = content.strip()
    if text.startswith("```"):  # tolerate a fenced block despite the JSON-only instruction
        text = text.strip("`").removeprefix("json").strip()
    try:
        obj = json.loads(text)
    except ValueError as e:
        raise InvalidModelOutput("content is not JSON") from e
    if not isinstance(obj, dict):
        raise InvalidModelOutput("content is not a JSON object")
    return ModelOutput(obj.get("request_type"), obj.get("missing_items"), obj.get("draft_reply"))
