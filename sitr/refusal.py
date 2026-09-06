"""The one way any stage hands a request to a person: raise Refusal with a reason from SPEC §4.

Detail strings are static text written here or in policy; they never carry message content.
"""

REASONS = frozenset(
    {
        "empty",
        "too_long",
        "non_english",
        "suspected_manipulation",
        "unrecognised_request",
        "destination_not_approved",
        "outgoing_recheck_failed",
        "model_unavailable",
        "model_output_invalid",
    }
)


class Refusal(Exception):
    def __init__(self, reason: str, detail: str) -> None:
        if reason not in REASONS:
            raise ValueError(f"unknown refusal reason: {reason}")
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
