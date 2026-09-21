from pathlib import Path
from types import SimpleNamespace

from capture_import.evidence_candidate_resolver import CatalogueCandidate
from capture_import.grounded_visual_observation import (
    GroundedVisualObservation,
    GroundedVisualObservationReport,
)
from capture_import.in_memory_catalogue_retriever import InMemoryCatalogueRetriever
from capture_import.recognition30_grounded_benchmark_cli import (
    build_parser,
    _load_dataset,
    _localized_image_bytes,
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
    import cv2
    import numpy as np

    path = tmp_path / name
    image = np.zeros((500, 500, 3), dtype=np.uint8)
    cv2.circle(image, (250, 250), 180, (255, 255, 255), 8)
    assert cv2.imwrite(str(path), image)
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

    outcome, reports, pipeline, localizations = run_case(
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
    assert len(localizations) == 2
    assert all("localized" in row for row in localizations)


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

    outcome, _, _, _ = run_case(
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


def test_localized_image_bytes_falls_back_when_no_circle(tmp_path):
    import cv2
    import numpy as np

    path = tmp_path / "blank.png"
    assert cv2.imwrite(str(path), np.zeros((200, 200, 3), dtype=np.uint8))

    data, media_type, metadata = _localized_image_bytes(path)

    assert data == path.read_bytes()
    assert media_type == "image/png"
    assert metadata == {"localized": False}


def test_localized_image_bytes_emits_bounded_jpeg_crop(tmp_path, monkeypatch):
    import cv2
    import numpy as np
    from capture_import.phone_photo_coin_localization import CoinCircleLocalization

    path = tmp_path / "coin.png"
    assert cv2.imwrite(str(path), np.zeros((100, 120, 3), dtype=np.uint8))
    localization = CoinCircleLocalization(
        center_x=60, center_y=50, radius=30, score=1.0, radius_ratio=0.3,
        center_distance=0.0, outside_ratio=0.0, crop_x=20, crop_y=10,
        crop_width=80, crop_height=80, source_width=120, source_height=100,
    )
    monkeypatch.setattr(
        "capture_import.recognition30_grounded_benchmark_cli.localize_coin_circle",
        lambda image: localization,
    )

    data, media_type, metadata = _localized_image_bytes(path)

    decoded = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[:2] == (80, 80)
    assert media_type == "image/jpeg"
    assert metadata["localized"] is True
    assert metadata["crop_width"] == 80
    assert metadata["crop_height"] == 80


def test_verification_diagnostics_are_available_from_run_case(tmp_path):
    case = SimpleNamespace(
        case_id="CA-R30-017",
        obverse=_image(tmp_path, "diag-obverse.png"),
        reverse=_image(tmp_path, "diag-reverse.png"),
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

    _, _, pipeline, _ = run_case(
        case,
        provider=FixtureProvider(),
        retriever=retriever,
        retrieval_limit=10,
    )

    row = pipeline.verification.rows[0]
    assert row.candidate.candidate_id == "CA-R30-017"
    assert row.matched_fields == ("year", "denomination", "visible_text")
    assert row.conflicting_fields == ()
    assert row.supporting_roles == ("obverse", "reverse")
    assert row.supporting_text == ("ELIZABETH", "CANADA")
    assert row.verified


def test_diagnostics_flag_is_opt_in():
    parser = build_parser()

    default_args = parser.parse_args(["dataset"])
    diagnostic_args = parser.parse_args(["dataset", "--diagnostics"])

    assert default_args.diagnostics is False
    assert diagnostic_args.diagnostics is True
