from pathlib import Path
from types import SimpleNamespace

from capture_import.evidence_candidate_resolver import CatalogueCandidate
from capture_import.grounded_visual_observation import (
    GroundedVisualObservation,
    GroundedVisualObservationReport,
)
from capture_import.in_memory_catalogue_retriever import InMemoryCatalogueRetriever
from capture_import.recognition30_grounded_benchmark_cli import (
    _load_dataset,
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
    dataset = SimpleNamespace(cases=(a, b))

    assert _select_cases(dataset, ("b", "a")) == (b, a)

    try:
        _select_cases(dataset, ("missing",))
    except SystemExit as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("expected SystemExit")


def test_csv_dataset_loader_uses_pair_manifest_and_ground_truth(tmp_path):
    root = tmp_path / "recognition30_v1"
    images = root / "images"
    images.mkdir(parents=True)
    (images / "IMG_1.JPEG").write_bytes(b"one")
    (images / "IMG_2.JPEG").write_bytes(b"two")
    (root / "pair_manifest.csv").write_text(
        "case_id,image_1,image_2\nCA-R30-001,IMG_1.JPEG,IMG_2.JPEG\n",
        encoding="utf-8",
    )
    (root / "ground_truth.csv").write_text(
        "case_id,image_1,image_2,country,denomination,year,variety,notes,truth_status\n"
        "CA-R30-001,IMG_1.JPEG,IMG_2.JPEG,Netherlands,10 cents,1974,Juliana,,Standard\n",
        encoding="utf-8",
    )

    dataset = _load_dataset(root)

    assert dataset.version == "recognition30_v1"
    assert len(dataset.cases) == 1
    case = dataset.cases[0]
    assert case.case_id == "CA-R30-001"
    assert case.obverse.path == images / "IMG_1.JPEG"
    assert case.reverse.path == images / "IMG_2.JPEG"
    assert case.expected == {
        "country": "Netherlands",
        "denomination": "10 cents",
        "year": "1974",
        "type_design": "Juliana",
    }


def test_csv_dataset_loader_fails_closed_on_pair_truth_mismatch(tmp_path):
    root = tmp_path / "recognition30_v1"
    images = root / "images"
    images.mkdir(parents=True)
    (images / "IMG_1.JPEG").write_bytes(b"one")
    (images / "IMG_2.JPEG").write_bytes(b"two")
    (root / "pair_manifest.csv").write_text(
        "case_id,image_1,image_2\nCA-R30-001,IMG_1.JPEG,IMG_2.JPEG\n",
        encoding="utf-8",
    )
    (root / "ground_truth.csv").write_text(
        "case_id,image_1,image_2,country,denomination,year,variety,notes,truth_status\n"
        "CA-R30-001,WRONG.JPEG,IMG_2.JPEG,Netherlands,10 cents,1974,Juliana,,Standard\n",
        encoding="utf-8",
    )

    try:
        _load_dataset(root)
    except ValueError as exc:
        assert "mismatch" in str(exc)
    else:
        raise AssertionError("expected ValueError")
