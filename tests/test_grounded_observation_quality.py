import pytest

from capture_import.grounded_observation_quality import (
    EvidenceQualityDecision,
    assess_coin_evidence,
    assess_observation_evidence,
)
from capture_import.grounded_visual_observation import GroundedVisualObservation


def _observation(role="obverse", **kwargs):
    return GroundedVisualObservation(role=role, **kwargs)


def test_empty_observation_escalates_fail_closed():
    result = assess_observation_evidence(_observation())

    assert result.decision is EvidenceQualityDecision.ESCALATE
    assert result.should_escalate
    assert result.score == 0
    assert "insufficient_independent_evidence" in result.reasons


def test_visible_date_is_strong_discriminator_without_model_confidence():
    result = assess_observation_evidence(
        _observation(visible_text=("1918",), date_like="1918")
    )

    assert result.decision is EvidenceQualityDecision.CONTINUE
    assert result.has_date_like
    assert result.useful_text_count == 1


def test_denomination_mark_is_strong_discriminator():
    result = assess_observation_evidence(
        _observation(denomination_mark="2 1/2")
    )

    assert result.decision is EvidenceQualityDecision.CONTINUE
    assert result.has_denomination_mark


def test_bare_number_is_not_treated_as_denomination_mark():
    result = assess_observation_evidence(
        _observation(denomination_mark="25")
    )

    assert result.decision is EvidenceQualityDecision.ESCALATE
    assert not result.has_denomination_mark


def test_three_independent_weak_signals_continue():
    result = assess_observation_evidence(
        _observation(
            visible_text=("BRITT",),
            script="Latin",
            motifs=("wreath",),
        )
    )

    assert result.decision is EvidenceQualityDecision.CONTINUE


def test_two_weak_signals_escalate():
    result = assess_observation_evidence(
        _observation(visible_text=("ONE",), script="Latin")
    )

    assert result.decision is EvidenceQualityDecision.ESCALATE


@pytest.mark.parametrize("date_like", ["19?8", "1955", "123456"])
def test_bounded_date_like_forms_are_accepted(date_like):
    result = assess_observation_evidence(_observation(date_like=date_like))
    assert result.has_date_like


@pytest.mark.parametrize("date_like", ["nineteen", "19-18", "12", "1234567"])
def test_unbounded_or_nonvisual_date_forms_do_not_route_as_date(date_like):
    result = assess_observation_evidence(_observation(date_like=date_like))
    assert not result.has_date_like


def test_two_sides_can_supply_complementary_evidence():
    obverse = _observation(
        "obverse",
        visible_text=("BRITT",),
        script="Latin",
    )
    reverse = _observation(
        "reverse",
        motifs=("wreath",),
    )

    result = assess_coin_evidence((obverse, reverse))

    assert result.decision is EvidenceQualityDecision.CONTINUE
    assert result.useful_text_count == 1
    assert result.motif_count == 1


def test_two_empty_sides_still_escalate():
    result = assess_coin_evidence(
        (_observation("obverse"), _observation("reverse"))
    )
    assert result.decision is EvidenceQualityDecision.ESCALATE


def test_duplicate_roles_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        assess_coin_evidence((_observation("obverse"), _observation("obverse")))


def test_more_than_two_sides_are_rejected():
    with pytest.raises(ValueError, match="at most two"):
        assess_coin_evidence(
            (
                _observation("obverse"),
                _observation("reverse"),
                _observation("obverse"),
            )
        )


def test_gate_contains_no_identity_acceptance_semantics():
    result = assess_observation_evidence(
        _observation(
            visible_text=("1918", "BRITT"),
            date_like="1918",
            script="Latin",
        )
    )
    assert result.decision is EvidenceQualityDecision.CONTINUE
    assert not hasattr(result, "accepted")
    assert not hasattr(result, "identity")
    assert not hasattr(result, "confidence")
    assert not hasattr(result, "country")
