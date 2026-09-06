"""Destination policy: configuration decides where masked text may go.

Undeclared or unapproved destinations are refused. Offline mode has an implicit local
destination that is always approved. A destination name is caller input: an undeclared
one is never echoed into a refusal detail or the audit record.
"""

from __future__ import annotations

from sitr.config import Destination, Policy
from sitr.refusal import Refusal

OFFLINE = Destination(
    name="offline", provider="local", region="local", approved=True, model="rule-based"
)
UNDECLARED = {"name": "undeclared", "provider": None, "region": None, "approved": False}


def resolve(policy: Policy, name: str | None) -> Destination:
    dest = policy.destinations.get(name or policy.default_destination)
    if dest is None:
        raise Refusal("destination_not_approved", "the destination is not declared in policy.yaml")
    if not dest.approved:
        raise Refusal(
            "destination_not_approved",
            f"destination '{dest.name}' ({dest.provider}, {dest.region}) is not approved",
        )
    return dest


def describe(policy: Policy, name: str | None) -> dict:
    """Audit-safe view of a destination; anything not in the policy is just 'undeclared'."""
    dest = policy.destinations.get(name or policy.default_destination)
    return view(dest) if dest else dict(UNDECLARED)


def view(dest: Destination) -> dict:
    return {
        "name": dest.name,
        "provider": dest.provider,
        "region": dest.region,
        "approved": dest.approved,
    }
