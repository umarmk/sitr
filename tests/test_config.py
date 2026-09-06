"""The shipped policy.yaml and config.yaml load; malformed files are rejected at load time."""

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from sitr.config import DEFAULT_CONFIG, ConfigError, load_config, load_policy


def test_shipped_policy_loads() -> None:
    policy = load_policy()
    assert policy.default_destination in policy.destinations
    assert any(d.approved for d in policy.destinations.values())
    assert any(not d.approved for d in policy.destinations.values())


def test_shipped_config_loads() -> None:
    config = load_config()
    assert set(config.request_types) == {"salary_certificate", "noc_letter", "leave", "it_access"}
    assert config.input_max_chars == 4000
    ids = [t.id for t in config.templates]
    assert ids and len(ids) == len(set(ids))
    assert "[NAME_1]" in config.model.system_prompt


def test_policy_rejects_quoted_booleans(tmp_path: Path) -> None:
    bad = tmp_path / "policy.yaml"
    bad.write_text(
        "default_destination: x\n"
        'destinations:\n  - {name: x, provider: p, region: r, approved: "false", model: m}\n'
    )
    with pytest.raises(ConfigError, match="approved"):
        load_policy(bad)


@pytest.mark.parametrize("name", ["openrouter/free", "x" * 65, "with space"])
def test_policy_rejects_names_the_api_could_not_select(tmp_path: Path, name: str) -> None:
    bad = tmp_path / "policy.yaml"
    bad.write_text(
        f"default_destination: '{name}'\n"
        f"destinations:\n  - {{name: '{name}', provider: p, region: r, approved: true, model: m}}\n"
    )
    with pytest.raises(ConfigError, match="destination name"):
        load_policy(bad)


def test_policy_default_must_be_declared(tmp_path: Path) -> None:
    bad = tmp_path / "policy.yaml"
    bad.write_text(
        "default_destination: nope\n"
        "destinations:\n  - {name: x, provider: p, region: r, approved: true, model: m}\n"
    )
    with pytest.raises(ConfigError, match="default_destination"):
        load_policy(bad)


def _mutated_config(tmp_path: Path, mutate: Callable[[dict], object]) -> Path:
    data = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.__setitem__("input_max_chars", "lots"),
        lambda d: d["request_types"]["leave"].__setitem__("required", ["dates"]),
        lambda d: d["request_types"]["leave"].__setitem__("keywords", "leave"),
        lambda d: d["drafts"].pop("sign_off"),
        lambda d: d["drafts"].__setitem__("body_missing", "please send {stuff}"),
        lambda d: d["drafts"].__setitem__("body_complete", "Done: {items}"),
        lambda d: d.__setitem__("request_types", {}),
        lambda d: d["manipulation_patterns"].append("("),
    ],
    ids=[
        "cap-not-a-number",
        "required-is-a-list",
        "keywords-is-a-string",
        "draft-missing",
        "draft-unknown-field",
        "draft-field-from-other-call-site",
        "no-request-types",
        "bad-regex",
    ],
)
def test_malformed_config_fails_at_load_not_mid_request(
    tmp_path: Path, mutate: Callable[[dict], object]
) -> None:
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, mutate))


def test_yaml_syntax_error_is_a_config_error(tmp_path: Path) -> None:
    broken = tmp_path / "config.yaml"
    broken.write_text("request_types: [\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="config.yaml"):
        load_config(broken)


def test_no_cue_or_keyword_matches_a_placeholder_token() -> None:
    """Cues run on masked text, so none may fire on the placeholders themselves."""
    tokens = "[NAME_1] [EMAIL_1] [PHONE_1] [EID_MASKED]"
    for rt in load_config().request_types.values():
        for rx in rt.keywords + [rx for cues in rt.required.values() for rx in cues]:
            assert not rx.search(tokens), (rt.key, rx.pattern)
