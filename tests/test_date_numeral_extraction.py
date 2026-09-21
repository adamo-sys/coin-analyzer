import pytest

from capture_import.date_numeral_extraction import extract_date_numerals
from capture_import.grounded_visual_observation import GroundedVisualObservation


def _observation(role="obverse", **kwargs):
    return GroundedVisualObservation(role=role, **kwargs)


def test_exact_date_like_resolves_literal_value():
    result = extract_date_numerals((_observation(date_like="1918", visible_text=("1918",)),))

    assert result.resolved_value == "1918"
    assert not result.conflict
    assert not result.unresolved
    assert result.candidates[0].source_field == "date_like"
    assert result.candidates[0].role == "obverse"


def test_visible_text_can_supply_date_without_date_like_field():
    result = extract_date_numerals(
        (_observation(visible_text=("IN TWO", "1918", "BRITT")),)
    )

    assert result.resolved_value == "1918"
    assert result.candidates[0].source_field == "visible_text"


def test_uncertain_digit_is_preserved_but_never_repaired_or_resolved():
    result = extract_date_numerals((_observation(date_like="19?8", visible_text=("19?8",)),))

    assert result.resolved_value is None
    assert result.unresolved
    assert result.candidates[0].value == "19?8"
    assert result.candidates[0].uncertain


def test_two_matching_sides_resolve_same_literal_value():
    result = extract_date_numerals(
        (
            _observation("obverse", visible_text=("1955",)),
            _observation("reverse", date_like="1955", visible_text=("1955",)),
        )
    )

    assert result.resolved_value == "1955"
    assert not result.conflict
    assert len(result.candidates) == 2


def test_incompatible_exact_dates_are_conflict_and_unresolved():
    result = extract_date_numerals(
        (
            _observation("obverse", date_like="1918"),
            _observation("reverse", visible_text=("1919",)),
        )
    )

    assert result.resolved_value is None
    assert result.conflict
    assert result.unresolved


def test_uncertain_token_does_not_override_exact_token():
    result = extract_date_numerals(
        (
            _observation("obverse", date_like="1918"),
            _observation("reverse", date_like="19?8", visible_text=("19?8",)),
        )
    )

    assert result.resolved_value == "1918"
    assert not result.conflict


@pytest.mark.parametrize(
    "text",
    ["18", "1968A", "A1968", "12345", "nineteen sixty eight"],
)
def test_nonliteral_four_digit_tokens_are_not_dates(text):
    result = extract_date_numerals((_observation(visible_text=(text,)),))

    assert result.candidates == ()
    assert result.resolved_value is None
    assert result.unresolved


def test_date_embedded_in_punctuation_is_extracted_without_normalization():
    result = extract_date_numerals(
        (_observation(visible_text=("· 1968 ·",)),)
    )

    assert result.resolved_value == "1968"


def test_duplicate_same_source_token_is_deduplicated():
    result = extract_date_numerals(
        (_observation(visible_text=("1918", "1918")),)
    )

    assert len(result.candidates) == 1


def test_date_like_and_visible_text_keep_distinct_provenance():
    result = extract_date_numerals(
        (_observation(date_like="1918", visible_text=("1918",)),)
    )

    assert len(result.candidates) == 2
    assert {item.source_field for item in result.candidates} == {
        "date_like",
        "visible_text",
    }


def test_empty_evidence_abstains():
    result = extract_date_numerals((_observation(),))

    assert result.candidates == ()
    assert result.resolved_value is None
    assert not result.conflict
    assert result.unresolved


def test_duplicate_roles_and_too_many_sides_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        extract_date_numerals((_observation(), _observation()))
    with pytest.raises(ValueError, match="at most two"):
        extract_date_numerals(
            (
                _observation("obverse"),
                _observation("reverse"),
                _observation("obverse"),
            )
        )


def test_extractor_has_no_identity_or_calendar_inference_fields():
    result = extract_date_numerals((_observation(date_like="1918", visible_text=("1918",)),))

    assert not hasattr(result, "country")
    assert not hasattr(result, "identity")
    assert not hasattr(result, "confidence")
    assert not hasattr(result, "ruler")


def test_uncorroborated_date_like_is_not_promoted():
    result = extract_date_numerals(
        (_observation(date_like="1983", visible_text=("1968",)),)
    )

    assert result.resolved_value == "1968"
    assert all(item.value != "1983" for item in result.candidates)
    assert not result.conflict


def test_date_like_requires_same_side_transcription():
    result = extract_date_numerals(
        (
            _observation("obverse", date_like="1968"),
            _observation("reverse", visible_text=("1968",)),
        )
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].role == "reverse"
    assert result.candidates[0].source_field == "visible_text"
