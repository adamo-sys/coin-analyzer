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


def test_no_visible_text_requests_secondary():
    decision = decide_secondary_observation(_observation())
    assert decision.request_secondary is True
    assert decision.reason == "primary_no_visible_text"


def test_literal_text_without_date_or_denomination_requests_secondary():
    decision = decide_secondary_observation(
        _observation(visible_text=("LIBERTAS",))
    )
    assert decision.request_secondary is True
    assert decision.reason == "primary_literal_text_only"


def test_policy_is_candidate_and_truth_independent():
    decision = decide_secondary_observation(
        _observation(visible_text=("HELVETIA",))
    )
    assert decision.request_secondary is True
    assert not hasattr(decision, "candidate_id")
    assert not hasattr(decision, "correct")
