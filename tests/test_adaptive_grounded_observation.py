from capture_import.adaptive_grounded_observation import decide_secondary_observation
from capture_import.grounded_visual_observation import GroundedVisualObservation


def _observation(**kwargs):
    return GroundedVisualObservation(role="obverse", **kwargs)


def test_structured_primary_evidence_does_not_request_secondary():
    decision = decide_secondary_observation(
        _observation(visible_text=("1968", "2 FR"), date_like="1968")
    )
    assert decision.request_secondary is False
    assert decision.reason == "primary_structured_evidence_sufficient"
    assert decision.missing_evidence == ("denomination",)


def test_no_visible_text_requests_secondary_with_explicit_gaps():
    decision = decide_secondary_observation(_observation())
    assert decision.request_secondary is True
    assert decision.reason == "primary_no_visible_text"
    assert decision.missing_evidence == ("visible_text", "year", "denomination")


def test_literal_text_without_date_or_denomination_requests_secondary():
    decision = decide_secondary_observation(
        _observation(visible_text=("LIBERTAS",))
    )
    assert decision.request_secondary is True
    assert decision.reason == "primary_literal_text_only"
    assert decision.missing_evidence == ("year", "denomination")


def test_denomination_only_primary_records_missing_year_without_extra_view():
    decision = decide_secondary_observation(
        _observation(visible_text=("25 CENTS",), denomination_mark="25 CENTS")
    )
    assert decision.request_secondary is False
    assert decision.missing_evidence == ("year",)


def test_policy_is_candidate_and_truth_independent():
    decision = decide_secondary_observation(
        _observation(visible_text=("HELVETIA",))
    )
    assert decision.request_secondary is True
    assert not hasattr(decision, "candidate_id")
    assert not hasattr(decision, "correct")
