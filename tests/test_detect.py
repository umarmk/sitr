"""Detector coverage per category, overlap handling, and deliberate non-matches."""

import pytest

from sitr.detect import EID, EMAIL, NAME, PHONE, detect


def found(text: str) -> list[tuple[str, str]]:
    return [(s.category, s.text) for s in detect(text)]


def arabic_indic(s: str) -> str:
    return "".join(chr(0x0660 + int(c)) if c.isdigit() else c for c in s)


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


def test_possessive_is_not_part_of_the_name() -> None:
    assert found("Laura Chen's ID is ready and Yousef Ibrahim's is not") == [
        (NAME, "Laura Chen"),
        (NAME, "Yousef Ibrahim"),
    ]


def test_eid_glued_to_a_name_stays_its_own_span() -> None:
    """spaCy merges the two; the EID must never end up inside a reversible NAME placeholder."""
    assert found("Leave for Mohammed bin Rashid 784199012345671 please") == [
        (NAME, "Mohammed bin Rashid"),
        (EID, "784199012345671"),
    ]


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


@pytest.mark.parametrize(
    "phone", ["04 123 4567", "+971 2 444 5555", "06 555 1212", "+971 4 3456789", "02-666-7788"]
)
def test_uae_landline_formats(phone: str) -> None:
    assert (PHONE, phone) in found(f"Office line {phone} please")


@pytest.mark.parametrize(
    "phone", ["+44 20 7946 0958", "+1 212 555 0199", "+91 98765 43210", "0091 98765 43210"]
)
def test_international_formats(phone: str) -> None:
    assert (PHONE, phone) in found(f"Abroad, call {phone} instead")


def test_arabic_indic_digits_are_read_and_the_original_text_is_kept() -> None:
    eid, phone = arabic_indic("784-1990-1234567-1"), arabic_indic("050 123 4567")
    assert found(f"ID {eid}, mobile {phone}") == [(EID, eid), (PHONE, phone)]


@pytest.mark.parametrize(
    "text",
    [
        "Ticket INC0012345 is still open",
        "Meeting room 04-12 is booked from 09:30 until 11:00",
        "PO number 7841990123 was raised",
        "Invoice 2026-0912 for AED 15,000",
    ],
)
def test_reference_numbers_dates_and_times_are_not_phones(text: str) -> None:
    assert detect(text) == []
