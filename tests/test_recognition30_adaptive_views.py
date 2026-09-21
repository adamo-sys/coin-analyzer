from types import SimpleNamespace

from capture_import.adaptive_grounded_observation import decide_secondary_observation
from capture_import.grounded_visual_observation import GroundedVisualObservation
from capture_import.recognition30_grounded_benchmark_cli import build_parser


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
