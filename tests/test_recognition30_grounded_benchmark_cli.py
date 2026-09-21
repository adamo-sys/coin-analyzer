from pathlib import Path
from types import SimpleNamespace

from capture_import.evidence_candidate_resolver import CatalogueCandidate
from capture_import.grounded_visual_observation import (
    GroundedVisualObservation,
    GroundedVisualObservationReport,
)
from capture_import.in_memory_catalogue_retriever import InMemoryCatalogueRetriever
from capture_import.recognition30_grounded_benchmark_cli import (
    _media_type,
    _select_cases,
    run_case,
)
from capture_import.recognition_decision_gate import RecognitionDecision


class FixtureProvider:
    provider_id = "fixture-observation"
    model_id = "fixture-model"

    def observe(self, request):
        role = request.image.role
        observation = (
            GroundedVisualObservation(
                role=role,
                date_like="1955",
                visible_text=("ELIZABETH",),
            )
            if role == "obverse"
            else GroundedVisualObservation(
                role=role,
                denomination_mark="25 CENTS",
                visible_text=("CANADA",),
            )
        )
        return GroundedVisualObservationReport(
            observation=observation,
            provider_id=self.provider_id,
            model_id=self.model_id,
            response_id=f"response-{role}",
            input_tokens=10,
            output_tokens=5,
        )


def _image(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"fixture")
    return SimpleNamespace(path=path)


def test_run_case_executes_observe_pipeline_and_post_decision_truth_scoring(tmp_path):
    case = SimpleNamespace(
        case_id="CA-R30-017",
        obverse=_image(tmp_path, "obverse.png"),
        reverse=_image(tmp_path, "reverse.png"),
    )
    retriever = InMemoryCatalogueRetriever(
        (
            CatalogueCandidate(
                "CA-R30-017",
                "Canada",
                "25 cents",
                "1955",
                legends=("ELIZABETH II", "CANADA"),
            ),
        )
    )

    outcome, reports, pipeline = run_case(
        case,
        provider=FixtureProvider(),
        retriever=retriever,
        retrieval_limit=10,
    )

    assert outcome.decision is RecognitionDecision.IDENTIFY
    assert outcome.correct
    assert outcome.predicted_candidate_id == "CA-R30-017"
    assert tuple(report.observation.role for report in reports) == (
        "obverse",
        "reverse",
    )
    assert pipeline.decision.candidate_id == "CA-R30-017"


def test_run_case_wrong_candidate_is_measured_as_unsafe(tmp_path):
    case = SimpleNamespace(
        case_id="truth",
        obverse=_image(tmp_path, "obverse.jpg"),
        reverse=_image(tmp_path, "reverse.jpg"),
    )
    retriever = InMemoryCatalogueRetriever(
        (
            CatalogueCandidate(
                "wrong",
                "Canada",
                "25 cents",
                "1955",
                legends=("ELIZABETH II", "CANADA"),
            ),
        )
    )

    outcome, _, _ = run_case(
        case,
        provider=FixtureProvider(),
        retriever=retriever,
        retrieval_limit=10,
    )

    assert outcome.decision is RecognitionDecision.IDENTIFY
    assert not outcome.correct
    assert outcome.unsafe_wrong_identification


def test_media_type_is_explicit_and_bounded():
    assert _media_type(Path("coin.jpg")) == "image/jpeg"
    assert _media_type(Path("coin.JPEG")) == "image/jpeg"
    assert _media_type(Path("coin.png")) == "image/png"

    try:
        _media_type(Path("coin.webp"))
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_case_selection_preserves_requested_order_and_rejects_unknown():
    a = SimpleNamespace(case_id="a")
    b = SimpleNamespace(case_id="b")
    manifest = SimpleNamespace(cases=(a, b))

    assert _select_cases(manifest, ("b", "a")) == (b, a)

    try:
        _select_cases(manifest, ("missing",))
    except SystemExit as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("expected SystemExit")
