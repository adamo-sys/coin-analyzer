from types import SimpleNamespace

import pytest

from capture_import.grounded_visual_observation import (
    GroundedVisualObservation,
    GroundedVisualObservationContractError,
    GroundedVisualObservationReport,
)
from capture_import.multiview_grounded_observation import (
    GroundedObservationViewReport,
    union_grounded_observation_views,
    view_provenance,
)


def _view(view, role="obverse", **kwargs):
    observation = GroundedVisualObservation(role=role, **kwargs)
    return GroundedObservationViewReport(
        view=view,
        report=GroundedVisualObservationReport(
            observation=observation,
            provider_id="fixture",
            model_id="fixture",
            response_id=f"response-{view}",
            input_tokens=10,
            output_tokens=2,
        ),
    )


def test_union_preserves_literal_text_from_both_views_with_stable_order():
    result = union_grounded_observation_views(
        (
            _view("full_face", visible_text=("1968", "HELVETIA")),
            _view("rim", visible_text=("HELVETIA", "5 FR")),
        )
    )

    assert result.visible_text == ("1968", "HELVETIA", "5 FR")


def test_union_keeps_agreeing_specialized_readings():
    result = union_grounded_observation_views(
        (
            _view("full_face", date_like="1968", denomination_mark="5 FR"),
            _view("rim", date_like="1968", denomination_mark="5 fr"),
        )
    )

    assert result.date_like == "1968"
    assert result.denomination_mark == "5 FR"


def test_union_discards_conflicting_specialized_readings():
    result = union_grounded_observation_views(
        (
            _view("full_face", visible_text=("1968",), date_like="1968"),
            _view("rim", visible_text=("1983",), date_like="1983"),
        )
    )

    assert result.visible_text == ("1968", "1983")
    assert result.date_like is None


def test_union_rejects_cross_side_views():
    with pytest.raises(GroundedVisualObservationContractError):
        union_grounded_observation_views(
            (_view("full_face", "obverse"), _view("rim", "reverse"))
        )


def test_provenance_retains_view_and_provider_metadata():
    rows = view_provenance(
        (_view("rim", visible_text=("HELVETIA",), date_like="1968"),)
    )

    assert rows == (
        {
            "view": "rim",
            "role": "obverse",
            "visible_text": ["HELVETIA"],
            "date_like": "1968",
            "denomination_mark": None,
            "response_id": "response-rim",
            "input_tokens": 10,
            "output_tokens": 2,
        },
    )
