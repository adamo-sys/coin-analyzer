from types import SimpleNamespace

from capture_import.adaptive_grounded_observation import decide_secondary_observation
from capture_import.grounded_visual_observation import GroundedVisualObservation
from capture_import.recognition30_grounded_benchmark_cli import (\n    _adaptive_routing_provenance,\n    build_parser,\n)


def test_adaptive_views_flag_is_opt_in():
    parser = build_parser()
    assert parser.parse_args(["dataset"]).adaptive_views is False
    assert parser.parse_args(["dataset", "--adaptive-views"]).adaptive_views is True


def test_secondary_routing_is_based_only_on_primary_evidence():
    strong = GroundedVisualObservation(
        role="obverse",
        visible_text=("1968", "2 FR"),
        date_like="1968",
        denomination_mark="2 FR",
    )
    weak = GroundedVisualObservation(
        role="obverse",
        visible_text=("LIBERTAS",),
    )

    assert decide_secondary_observation(strong).request_secondary is False
    assert decide_secondary_observation(weak).request_secondary is True


def test_secondary_decision_exposes_reason_and_missing_evidence():
    weak = GroundedVisualObservation(role="reverse", visible_text=("LIBERTAS",))

    decision = decide_secondary_observation(weak)

    assert decision.request_secondary is True
    assert decision.reason == "primary_literal_text_only"
    assert decision.missing_evidence == ("year", "denomination")


def test_routing_provenance_is_reconstructed_from_primary_view_only():
    provenance = (
        {
            "view": "full_face",
            "role": "obverse",
            "visible_text": ("LIBERTAS",),
            "date_like": None,
            "denomination_mark": None,
        },
        {
            "view": "rim",
            "role": "obverse",
            "visible_text": ("1918",),
            "date_like": "1918",
            "denomination_mark": None,
        },
        {
            "view": "full_face",
            "role": "reverse",
            "visible_text": ("1968", "2 FR"),
            "date_like": "1968",
            "denomination_mark": "2 FR",
        },
    )

    rows = _adaptive_routing_provenance(provenance)

    assert len(rows) == 2
    assert rows[0]["requested"] is True
    assert rows[0]["reason"] == "primary_literal_text_only"
    assert rows[0]["missing_evidence"] == ["year", "denomination"]
    assert rows[1]["requested"] is False
    assert rows[1]["reason"] == "primary_structured_evidence_sufficient"
