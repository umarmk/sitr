"""Placeholders are reversible for names, emails and phones; Emirates IDs are not (T-5, T-6)."""

from sitr.detect import detect
from sitr.mask import EID_PLACEHOLDER, Masker, restore

TEXT = "Hi, I am Sarah Mitchell, 050 123 4567, sarah.mitchell@example.com. Ask for Sarah Mitchell."


def test_round_trip_is_lossless() -> None:
    masker = Masker()
    masked = masker.apply(TEXT, detect(TEXT))
    assert "Sarah Mitchell" not in masked and "050 123 4567" not in masked
    assert restore(masked, masker.mapping) == (TEXT, [])


def test_same_value_gets_same_placeholder() -> None:
    masker = Masker()
    masked = masker.apply(TEXT, detect(TEXT))
    assert masked.count("[NAME_1]") == 2 and "[NAME_2]" not in masked


def test_eid_is_masked_irreversibly() -> None:
    text = "ID 784-1990-1234567-1 and again 784-1990-1234567-1"
    masker = Masker()
    masked = masker.apply(text, detect(text))
    assert masked == f"ID {EID_PLACEHOLDER} and again {EID_PLACEHOLDER}"
    assert masker.mapping == {} and masker.counts["EID"] == 2
    assert restore(masked, masker.mapping)[0] == masked


def test_unknown_placeholder_stays_literal_and_is_reported() -> None:
    restored, unknown = restore("Dear [NAME_1], cc [EMAIL_9]", {"[NAME_1]": "Sarah Mitchell"})
    assert restored == "Dear Sarah Mitchell, cc [EMAIL_9]"
    assert unknown == ["[EMAIL_9]"]


def test_case_distinct_values_stay_distinct() -> None:
    text = "Write to Alice@Example.com or alice@example.com"
    masker = Masker()
    masked = masker.apply(text, detect(text))
    assert "[EMAIL_1]" in masked and "[EMAIL_2]" in masked
    assert restore(masked, masker.mapping) == (text, [])
