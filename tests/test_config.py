"""The shipped policy.yaml and config.yaml load, and malformed policy is rejected loudly."""

from pathlib import Path

import pytest

from sitr.config import ConfigError, load_config, load_policy


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


def test_policy_default_must_be_declared(tmp_path: Path) -> None:
    bad = tmp_path / "policy.yaml"
    bad.write_text(
        "default_destination: nope\n"
        "destinations:\n  - {name: x, provider: p, region: r, approved: true, model: m}\n"
    )
    with pytest.raises(ConfigError, match="default_destination"):
        load_policy(bad)


def test_no_cue_or_keyword_matches_a_placeholder_token() -> None:
    """Cues run on masked text, so none may fire on the placeholders themselves."""
    tokens = "[NAME_1] [EMAIL_1] [PHONE_1] [EID_MASKED]"
    for rt in load_config().request_types.values():
        for rx in rt.keywords + [rx for cues in rt.required.values() for rx in cues]:
            assert not rx.search(tokens), (rt.key, rx.pattern)
