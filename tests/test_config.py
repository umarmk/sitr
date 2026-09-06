"""The shipped policy.yaml and config.yaml load and describe the closed set of request types."""

from sitr.config import load_config, load_policy


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
