"""Destination policy: configuration decides where masked text may go.

Undeclared or unapproved destinations are refused. Offline mode has an implicit local
destination that is always approved.
"""

from __future__ import annotations

from sitr.config import Destination, Policy
from sitr.refusal import Refusal

OFFLINE = Destination(
    name="offline", provider="local", region="local", approved=True, model="rule-based"
)


def resolve(policy: Policy, name: str | None) -> Destination:
    name = name or policy.default_destination
    dest = policy.destinations.get(name)
    if dest is None:
        raise Refusal(
            "destination_not_approved", f"destination '{name}' is not declared in policy.yaml"
        )
    if not dest.approved:
        raise Refusal(
            "destination_not_approved",
            f"destination '{name}' ({dest.provider}, {dest.region}) is not approved",
        )
    return dest


def describe(policy: Policy, name: str | None) -> dict:
    """Audit-safe view of a destination, including ones that are not declared."""
    name = name or policy.default_destination
    dest = policy.destinations.get(name)
    if dest is None:
        return {"name": name, "provider": None, "region": None, "approved": False}
    return view(dest)


def view(dest: Destination) -> dict:
    return {
        "name": dest.name,
        "provider": dest.provider,
        "region": dest.region,
        "approved": dest.approved,
    }
