"""Load policy.yaml (what may go where) and config.yaml (how the assistant behaves).

Both are parsed once per path and turned into frozen dataclasses so the rest of the code
never touches raw dicts. Every keyword and cue is a case-insensitive regex.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "policy.yaml"
DEFAULT_CONFIG = ROOT / "config.yaml"


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Destination:
    name: str
    provider: str
    region: str
    approved: bool
    model: str


@dataclass(frozen=True)
class Policy:
    destinations: dict[str, Destination]
    default_destination: str


@dataclass(frozen=True)
class ModelConfig:
    timeout_seconds: float
    temperature: float
    system_prompt: str


@dataclass(frozen=True)
class RequestType:
    key: str
    label: str
    keywords: list[re.Pattern[str]]
    # item -> cue patterns; an item with no cue hit in the message is reported as missing
    required: dict[str, list[re.Pattern[str]]]


@dataclass(frozen=True)
class Template:
    id: str
    title: str
    text: str


@dataclass(frozen=True)
class Config:
    input_max_chars: int
    model: ModelConfig
    request_types: dict[str, RequestType]
    templates: list[Template]
    manipulation_patterns: list[re.Pattern[str]]
    drafts: dict[str, str]


# Every sentence the rule-based assistant writes; validated at load so a typo in config.yaml
# fails at startup, not in the middle of a request.
DRAFT_KEYS = ("greeting_named", "greeting_anonymous", "body_complete", "body_missing", "sign_off")
# Anything a malformed YAML value can raise while being turned into a dataclass.
_MALFORMED = (KeyError, TypeError, ValueError, AttributeError, IndexError, re.error)


def _rx(patterns: object) -> list[re.Pattern[str]]:
    if not isinstance(patterns, list):  # a bare string would compile per character
        raise TypeError(f"expected a list of patterns, got {type(patterns).__name__}")
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def _load_yaml(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError(f"{path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")
    return data


@cache
def load_policy(path: Path = DEFAULT_POLICY) -> Policy:
    data = _load_yaml(path)
    try:
        destinations = {}
        for d in data["destinations"]:
            if not isinstance(d["approved"], bool):  # a quoted "false" would coerce to True
                raise ConfigError(
                    f"{path}: destination '{d['name']}' has approved={d['approved']!r}; "
                    "it must be the YAML boolean true or false"
                )
            destinations[d["name"]] = Destination(
                d["name"], d["provider"], d["region"], d["approved"], d["model"]
            )
        if data["default_destination"] not in destinations:
            raise ConfigError(f"{path}: default_destination is not a declared destination")
        return Policy(destinations, data["default_destination"])
    except ConfigError:
        raise
    except _MALFORMED as e:
        raise ConfigError(f"{path}: malformed policy ({e!r})") from e


@cache
def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    data = _load_yaml(path)
    try:
        m = data["model"]
        request_types = {
            key: RequestType(
                key,
                rt["label"],
                _rx(rt["keywords"]),
                {item: _rx(cues) for item, cues in rt["required"].items()},
            )
            for key, rt in data["request_types"].items()
        }
        if not request_types:
            raise ConfigError(f"{path}: request_types must declare at least one type")
        drafts = {k: data["drafts"][k] for k in DRAFT_KEYS}
        for sentence in drafts.values():
            sentence.format(label="", items="")  # an unknown {field} fails here, not mid-request
        return Config(
            input_max_chars=int(data["input_max_chars"]),
            model=ModelConfig(
                float(m["timeout_seconds"]), float(m["temperature"]), m["system_prompt"]
            ),
            request_types=request_types,
            templates=[Template(t["id"], t["title"], t["text"]) for t in data["templates"]],
            manipulation_patterns=_rx(data["manipulation_patterns"]),
            drafts=drafts,
        )
    except ConfigError:
        raise
    except _MALFORMED as e:
        raise ConfigError(f"{path}: malformed config ({e!r})") from e
