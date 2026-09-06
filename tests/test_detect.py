"""Detector coverage per category, overlap handling, and stated non-coverage."""

import pytest

from sitr.detect import EID, EMAIL, NAME, PHONE, detect


def found(text: str) -> list[tuple[str, str]]:
    return [(s.category, s.text) for s in detect(text)]


@pytest.mark.parametrize("eid", ["784-1990-1234567-1", "784199012345671", "784 1990 1234567 1"])
def test_emirates_id_formats(eid: str) -> None:
    assert (EID, eid) in found(f"My ID is {eid} thanks")


@pytest.mark.parametrize(
    "phone",
    [
        "050 123 4567",
        "0501234567",
        "+971 50 123 4567",
        "+971501234567",
        "00971 55 987 6543",
        "+971 (0)50 123 4567",
        "+971(0)501234567",
        "971 50 123 4567",
    ],
)
def test_uae_mobile_formats(phone: str) -> None:
    assert (PHONE, phone) in found(f"Call me on {phone} please")


def test_sentence_initial_noun_is_not_a_name() -> None:
    assert detect("Salary certificate please, addressed to my bank for a loan.") == []


def test_longest_span_wins_when_categories_overlap() -> None:
    """A phone number inside an email must not leave a half-masked address behind."""
    assert found("Write to john0501234567@example.com") == [(EMAIL, "john0501234567@example.com")]


def test_email() -> None:
    assert (EMAIL, "sarah.mitchell@example.com") in found("Email sarah.mitchell@example.com today")


def test_name() -> None:
    assert (NAME, "Sarah Mitchell") in found("Hello, my name is Sarah Mitchell and I work here.")


def test_plain_text_has_no_detections() -> None:
    assert detect("I would like to request annual leave from 3 to 14 March.") == []


def test_spans_are_ordered_and_non_overlapping() -> None:
    spans = detect(
        "Contact Sarah Mitchell on 050 123 4567 or sarah.mitchell@example.com, "
        "ID 784-1990-1234567-1."
    )
    assert [s.category for s in spans] == [NAME, PHONE, EMAIL, EID]
    assert all(a.end <= b.start for a, b in zip(spans, spans[1:], strict=False))


def test_landline_is_a_stated_gap() -> None:
    assert detect("Office line 04 123 4567") == []
