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


def _rx(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def _load_yaml(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"{path}: not found") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")
    return data


@cache
def load_policy(path: Path = DEFAULT_POLICY) -> Policy:
    data = _load_yaml(path)
    try:
        destinations = {
            d["name"]: Destination(
                d["name"], d["provider"], d["region"], bool(d["approved"]), d["model"]
            )
            for d in data["destinations"]
        }
        return Policy(destinations, data["default_destination"])
    except (KeyError, TypeError) as e:
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
        return Config(
            input_max_chars=int(data["input_max_chars"]),
            model=ModelConfig(
                float(m["timeout_seconds"]), float(m["temperature"]), m["system_prompt"]
            ),
            request_types=request_types,
            templates=[Template(t["id"], t["title"], t["text"]) for t in data["templates"]],
            manipulation_patterns=_rx(data["manipulation_patterns"]),
            drafts=dict(data["drafts"]),
        )
    except (KeyError, TypeError, re.error) as e:
        raise ConfigError(f"{path}: malformed config ({e!r})") from e
