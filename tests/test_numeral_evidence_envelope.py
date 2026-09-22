import pytest

from capture_import.grounded_visual_observation import GroundedVisualObservation
from capture_import.numeral_evidence_envelope import (
    build_numeral_evidence_envelope,
)


def _observation(role="obverse", **kwargs):
    return GroundedVisualObservation(role=role, **kwargs)


def test_date_and_denomination_compose_into_normalized_evidence():
    result = build_numeral_evidence_envelope(
        (
            _observation(
                visible_text=("CANADA", "25 CENTS", "1955"),
                date_like="1955",
                denomination_mark="25 CENTS",
            ),
        )
    )

    assert result.normalized.country is None
    assert result.normalized.year == "1955"
    assert result.normalized.denomination == "25 cents"
    assert result.normalized.visible_text == ("CANADA", "25 CENTS", "1955")
    assert result.normalized.source == "grounded_numeral_extraction"
    assert result.retrieval_ready
    assert not result.has_conflict


def test_date_only_is_retrieval_ready_without_inventing_denomination():
    result = build_numeral_evidence_envelope(
        (_observation(date_like="1918", visible_text=("1918",)),)
    )

    assert result.normalized.year == "1918"
    assert result.normalized.denomination is None
    assert result.retrieval_ready


def test_denomination_only_is_retrieval_ready_without_inventing_year():
    result = build_numeral_evidence_envelope(
        (_observation(denomination_mark="10 PISO", visible_text=("10 PISO",)),)
    )

    assert result.normalized.year is None
    assert result.normalized.denomination == "10 pesos"
    assert result.retrieval_ready


@pytest.mark.parametrize("mark", ["10 ÖRE", "5 öre", "10 ORE", "5 ore"])
def test_ore_marks_normalize_to_ascii_ore(mark):
    result = build_numeral_evidence_envelope(
        (_observation(denomination_mark=mark, visible_text=(mark,)),)
    )

    assert result.normalized.denomination == mark.split()[0] + " ore"


def test_visible_text_alone_can_be_retrieval_ready_but_not_identity_evidence():
    result = build_numeral_evidence_envelope(
        (_observation(visible_text=("LIBERTY",)),)
    )

    assert result.normalized.year is None
    assert result.normalized.denomination is None
    assert result.normalized.visible_text == ("LIBERTY",)
    assert result.retrieval_ready


def test_conflicting_dates_block_retrieval_ready():
    result = build_numeral_evidence_envelope(
        (
            _observation("obverse", date_like="1918", visible_text=("1918",)),
            _observation("reverse", date_like="1919", visible_text=("1919",)),
        )
    )

    assert result.date.conflict
    assert result.has_conflict
    assert not result.retrieval_ready
    assert result.normalized.year is None


def test_conflicting_denominations_block_retrieval_ready():
    result = build_numeral_evidence_envelope(
        (
            _observation("obverse", denomination_mark="5 CENTS", visible_text=("5 CENTS",)),
            _observation("reverse", denomination_mark="10 CENTS", visible_text=("10 CENTS",)),
        )
    )

    assert result.denomination.conflict
    assert result.has_conflict
    assert not result.retrieval_ready
    assert result.normalized.denomination is None


def test_uncertain_date_is_preserved_but_not_promoted_to_normalized_year():
    result = build_numeral_evidence_envelope(
        (_observation(date_like="19?8", visible_text=("19?8",)),)
    )

    assert result.date.candidates[0].value == "19?8"
    assert result.normalized.year is None
    assert not result.has_conflict


def test_duplicate_visible_text_across_sides_is_deduplicated_in_order():
    result = build_numeral_evidence_envelope(
        (
            _observation("obverse", visible_text=("CANADA", "1955")),
            _observation("reverse", visible_text=("CANADA", "25 CENTS")),
        )
    )

    assert result.normalized.visible_text == ("CANADA", "1955", "25 CENTS")


def test_empty_observation_is_not_retrieval_ready():
    result = build_numeral_evidence_envelope((_observation(),))

    assert not result.retrieval_ready
    assert not result.has_conflict
    assert result.normalized.year is None
    assert result.normalized.denomination is None


def test_envelope_has_no_identity_acceptance_or_confidence_fields():
    result = build_numeral_evidence_envelope(
        (_observation(date_like="1955", denomination_mark="25 CENTS", visible_text=("1955", "25 CENTS")),)
    )

    assert not hasattr(result, "identity")
    assert not hasattr(result, "accepted")
    assert not hasattr(result, "confidence")
    assert not hasattr(result, "candidate_id")
