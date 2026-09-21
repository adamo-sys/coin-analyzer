import pytest

from capture_import.grounded_observation_shadow_routing import (
    ShadowRoute,
    project_shadow_route,
)
from capture_import.grounded_visual_observation import (
    GroundedVisualObservation,
    GroundedVisualObservationReport,
)


def _report(role="obverse", *, input_tokens=100, output_tokens=20, **evidence):
    return GroundedVisualObservationReport(
        observation=GroundedVisualObservation(role=role, **evidence),
        provider_id="cheap-observer",
        model_id="cheap-vision-v1",
        response_id=f"resp-{role}",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def test_sparse_evidence_projects_premium_escalation():
    result = project_shadow_route((_report(),))

    assert result.route is ShadowRoute.PREMIUM
    assert result.would_escalate
    assert result.quality.decision.value == "ESCALATE"


def test_grounded_date_projects_standard_route():
    result = project_shadow_route(
        (_report(visible_text=("1918",), date_like="1918"),)
    )

    assert result.route is ShadowRoute.STANDARD
    assert not result.would_escalate


def test_two_sides_are_assessed_as_one_evidence_envelope():
    result = project_shadow_route(
        (
            _report("obverse", visible_text=("BRITT",), script="Latin"),
            _report("reverse", motifs=("wreath",)),
        )
    )

    assert result.route is ShadowRoute.STANDARD


def test_projection_preserves_provider_model_and_token_provenance():
    first = _report("obverse", input_tokens=100, output_tokens=20)
    second = GroundedVisualObservationReport(
        observation=GroundedVisualObservation(
            role="reverse", date_like="1955"
        ),
        provider_id="second-observer",
        model_id="vision-v2",
        response_id="resp-reverse",
        input_tokens=80,
        output_tokens=10,
    )

    result = project_shadow_route((first, second))

    assert result.source_provider_ids == ("cheap-observer", "second-observer")
    assert result.source_model_ids == ("cheap-vision-v1", "vision-v2")
    assert result.input_tokens == 180
    assert result.output_tokens == 30


def test_unknown_token_usage_stays_unknown_instead_of_becoming_zero():
    result = project_shadow_route(
        (_report(input_tokens=None, output_tokens=None),)
    )

    assert result.input_tokens is None
    assert result.output_tokens is None


def test_serialization_is_explicitly_shadow_only():
    result = project_shadow_route((_report(),))
    payload = result.to_dict()

    assert payload["mode"] == "shadow"
    assert payload["route"] == "PREMIUM"
    assert payload["would_escalate"] is True
    assert "selected_provider" not in payload
    assert "identity" not in payload
    assert "accepted" not in payload
    assert "confidence" not in payload


def test_projection_does_not_invoke_a_provider():
    report = _report(date_like="1918")
    result = project_shadow_route((report,))

    assert result.route is ShadowRoute.STANDARD
    # The projection accepts completed reports only; it has no provider/callable.
    assert not hasattr(result, "provider")
    assert not hasattr(result, "execute")


def test_duplicate_side_roles_fail_closed_via_quality_gate():
    with pytest.raises(ValueError, match="unique"):
        project_shadow_route((_report("obverse"), _report("obverse")))


def test_empty_and_more_than_two_reports_are_rejected():
    with pytest.raises(ValueError, match="at least one"):
        project_shadow_route(())
    with pytest.raises(ValueError, match="at most two"):
        project_shadow_route(
            (_report("obverse"), _report("reverse"), _report("obverse"))
        )
