"""Policy refuses what is not declared or not approved (T-7)."""

import pytest

from sitr.config import Destination, Policy
from sitr.policy import OFFLINE, describe, resolve, view
from sitr.refusal import Refusal

POLICY = Policy(
    destinations={
        "ok": Destination("ok", "Prov", "US", True, "m"),
        "blocked": Destination("blocked", "Prov", "EU", False, "m"),
    },
    default_destination="ok",
)


def test_approved_destination_resolves() -> None:
    assert resolve(POLICY, "ok").approved is True
    assert resolve(POLICY, None).name == "ok"


@pytest.mark.parametrize("name", ["blocked", "undeclared"])
def test_unapproved_or_undeclared_is_refused(name: str) -> None:
    with pytest.raises(Refusal) as e:
        resolve(POLICY, name)
    assert e.value.reason == "destination_not_approved"


def test_describe_is_audit_safe_for_any_name() -> None:
    assert describe(POLICY, "undeclared") == {
        "name": "undeclared",
        "provider": None,
        "region": None,
        "approved": False,
    }
    assert describe(POLICY, "blocked")["approved"] is False


def test_offline_destination_is_local_and_approved() -> None:
    assert view(OFFLINE) == {
        "name": "offline",
        "provider": "local",
        "region": "local",
        "approved": True,
    }
