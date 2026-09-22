import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from capture_import.evidence_candidate_resolver import CatalogueCandidate
from capture_import.grounded_visual_observation import (
    GroundedVisualObservation,
    GroundedVisualObservationContractError,
    GroundedVisualObservationReport,
)
from capture_import.openai_grounded_visual_observation_provider import (
    GroundedVisualObservationProviderTimeout,
)
from capture_import.in_memory_catalogue_retriever import InMemoryCatalogueRetriever
from capture_import.recognition30_grounded_benchmark_cli import (
    RECOGNITION30_DATASET_FINGERPRINT_SCHEME,
    RECOGNITION30_V1_DATASET_FINGERPRINT,
    build_parser,
    _dataset_fingerprint,
    _executable_dataset_identity,
    _load_dataset,
    _localized_image_bytes,
    _media_type,
    _select_cases,
    _recognition_semantics,
    _validate_execution_options,
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


def _fingerprint_fixture(root, *, image_order=("IMG_B.JPEG", "IMG_A.JPEG")):
    images = root / "images"
    images.mkdir(parents=True)
    for name in image_order:
        (images / name).write_bytes(name.encode("ascii"))
    (root / "pair_manifest.csv").write_bytes(
        b'"case_id","image_1","image_2"\r\n'
        b'"CA-R30-001","IMG_A.JPEG","IMG_B.JPEG"\r\n'
    )
    (root / "ground_truth.csv").write_bytes(
        b"case_id,image_1,image_2,country,denomination,year,variety,notes,truth_status\n"
        b"CA-R30-001,IMG_A.JPEG,IMG_B.JPEG,Example,1 unit,2000,,,Standard\n"
    )
    return root


def test_dataset_fingerprint_is_deterministic_and_sorted_by_basename(tmp_path):
    first = _fingerprint_fixture(tmp_path / "first")
    second = _fingerprint_fixture(
        tmp_path / "second", image_order=("IMG_A.JPEG", "IMG_B.JPEG")
    )

    assert _dataset_fingerprint(first) == _dataset_fingerprint(first)
    assert _dataset_fingerprint(first) == _dataset_fingerprint(second)


def test_dataset_fingerprint_changes_when_an_included_file_changes(tmp_path):
    root = _fingerprint_fixture(tmp_path / "dataset")
    baseline = _dataset_fingerprint(root)

    (root / "images" / "IMG_A.JPEG").write_bytes(b"changed-image")

    assert _dataset_fingerprint(root) != baseline


def test_dataset_fingerprint_excludes_timestamp_metadata(tmp_path):
    root = _fingerprint_fixture(tmp_path / "dataset")
    baseline = _dataset_fingerprint(root)

    os.utime(root / "ground_truth.csv", (1_000_000_000, 1_000_000_000))

    assert _dataset_fingerprint(root) == baseline


def test_recognition30_v1_executable_identity_rejects_legacy_fingerprint():
    with pytest.raises(ValueError, match="does not match"):
        _executable_dataset_identity(
            "recognition30_v1",
            "4f6988ed84fd5c4db1e06452e942bcfb75b0f495f74c5d54ad37e44c17b534de",
        )

    assert _executable_dataset_identity(
        "recognition30_v1", RECOGNITION30_V1_DATASET_FINGERPRINT
    ) == {
        "scheme": RECOGNITION30_DATASET_FINGERPRINT_SCHEME,
        "fingerprint": RECOGNITION30_V1_DATASET_FINGERPRINT,
    }


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

    outcome, reports, pipeline, localizations, failures, provenance = run_case(
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
    assert failures == ()


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

    outcome, _, _, _, failures, provenance = run_case(
        case,
        provider=FixtureProvider(),
        retriever=retriever,
        retrieval_limit=10,
    )

    assert outcome.decision is RecognitionDecision.IDENTIFY
    assert not outcome.correct
    assert outcome.unsafe_wrong_identification
    assert failures == ()


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

    _, _, pipeline, _, failures, provenance = run_case(
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
    assert failures == ()


def test_diagnostics_flag_is_opt_in():
    parser = build_parser()

    default_args = parser.parse_args(["dataset"])
    diagnostic_args = parser.parse_args(["dataset", "--diagnostics"])

    assert default_args.diagnostics is False
    assert diagnostic_args.diagnostics is True


def test_cli_provider_timeout_default_and_override_are_explicit():
    parser = build_parser()

    assert parser.parse_args(["dataset"]).provider_timeout_seconds == 120.0
    assert (
        parser.parse_args(["dataset", "--provider-timeout-seconds", "7.5"])
        .provider_timeout_seconds
        == 7.5
    )


@pytest.mark.parametrize("value", ("0", "-1"))
def test_cli_rejects_non_positive_provider_timeout_before_execution(value):
    args = build_parser().parse_args(
        ["dataset", "--provider-timeout-seconds", value]
    )

    with pytest.raises(SystemExit, match="positive"):
        _validate_execution_options(args)


def test_timeout_is_execution_metadata_not_recognition_semantics():
    parser = build_parser()
    short = parser.parse_args(["dataset", "--provider-timeout-seconds", "1"])
    default = parser.parse_args(["dataset"])

    assert _recognition_semantics(short) == _recognition_semantics(default)


def test_cli_declares_oracle_candidate_scope():
    parser = build_parser()

    assert "oracle candidate availability" in parser.description
    assert "not production retrieval" in parser.description


def test_evidence_report_flag_is_optional():
    parser = build_parser()

    default_args = parser.parse_args(["dataset"])
    report_args = parser.parse_args(
        ["dataset", "--evidence-report", "evidence.json"]
    )

    assert default_args.evidence_report is None
    assert report_args.evidence_report == Path("evidence.json")


class FailingReverseProvider(FixtureProvider):
    def observe(self, request):
        if request.image.role == "reverse":
            raise GroundedVisualObservationContractError(
                "provider response is not valid structured JSON."
            )
        return super().observe(request)


def test_run_case_provider_failure_abstains_and_preserves_successful_side(tmp_path):
    case = SimpleNamespace(
        case_id="CA-R30-017",
        obverse=_image(tmp_path, "failure-obverse.png"),
        reverse=_image(tmp_path, "failure-reverse.png"),
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

    outcome, reports, pipeline, localizations, failures, provenance = run_case(
        case,
        provider=FailingReverseProvider(),
        retriever=retriever,
        retrieval_limit=10,
    )

    assert outcome.decision is RecognitionDecision.ABSTAIN
    assert outcome.reason == "provider_observation_failure"
    assert not outcome.unsafe_wrong_identification
    assert pipeline is None
    assert tuple(report.observation.role for report in reports) == ("obverse",)
    assert len(localizations) == 2
    assert failures == (
        {
            "role": "reverse",
            "view": "full_face",
                "error_type": "GroundedVisualObservationContractError",
                "message": "provider response is not valid structured JSON.",
                "failure_kind": "provider_contract",
            },
    )


def test_provider_failure_does_not_retry_failed_side(tmp_path):
    calls = []

    class CountingFailureProvider(FixtureProvider):
        def observe(self, request):
            calls.append(request.image.role)
            if request.image.role == "obverse":
                raise GroundedVisualObservationContractError("malformed")
            return super().observe(request)

    case = SimpleNamespace(
        case_id="CA-R30-017",
        obverse=_image(tmp_path, "no-retry-obverse.png"),
        reverse=_image(tmp_path, "no-retry-reverse.png"),
    )
    retriever = InMemoryCatalogueRetriever(
        (
            CatalogueCandidate(
                "CA-R30-017", "Canada", "25 cents", "1955"
            ),
        )
    )

    outcome, reports, pipeline, _, failures, provenance = run_case(
        case,
        provider=CountingFailureProvider(),
        retriever=retriever,
        retrieval_limit=10,
    )

    assert calls == ["obverse", "reverse", "reverse"]
    assert outcome.decision is RecognitionDecision.ABSTAIN
    assert pipeline is None
    assert tuple(report.observation.role for report in reports) == ("reverse",)
    assert len(failures) == 1


def test_timeout_is_structured_pipeline_failure_and_next_side_runs(tmp_path):
    calls = []

    class TimeoutThenSuccessProvider(FixtureProvider):
        def observe(self, request):
            calls.append(request.image.role)
            if request.image.role == "obverse":
                raise GroundedVisualObservationProviderTimeout(120.0)
            return super().observe(request)

    case = SimpleNamespace(
        case_id="CA-R30-017",
        obverse=_image(tmp_path, "timeout-obverse.png"),
        reverse=_image(tmp_path, "timeout-reverse.png"),
    )
    retriever = InMemoryCatalogueRetriever(
        (CatalogueCandidate("CA-R30-017", "Canada", "25 cents", "1955"),)
    )

    outcome, _, pipeline, _, failures, _ = run_case(
        case,
        provider=TimeoutThenSuccessProvider(),
        retriever=retriever,
        retrieval_limit=10,
    )

    assert calls == ["obverse", "reverse", "reverse"]
    assert outcome.decision is RecognitionDecision.ABSTAIN
    assert outcome.reason == "provider_observation_failure"
    assert pipeline is None
    assert failures[0]["failure_kind"] == "provider_timeout"
    assert failures[0]["diagnostics"]["timeout_seconds"] == 120.0


def test_diagnostics_guard_allows_provider_failure_without_pipeline():
    parser = build_parser()
    args = parser.parse_args(["dataset", "--diagnostics"])

    pipeline = None
    provider_failures = (
        {
            "role": "obverse",
            "error_type": "GroundedVisualObservationMalformedOutput",
            "message": "provider response is not valid structured JSON.",
        },
    )

    assert args.diagnostics
    assert provider_failures
    assert pipeline is None


def test_multiview_execution_is_bounded_to_two_calls_per_localized_side(tmp_path):
    calls = []

    class CountingProvider(FixtureProvider):
        def observe(self, request):
            calls.append(request.image.role)
            return super().observe(request)

    case = SimpleNamespace(
        case_id="CA-R30-017",
        obverse=_image(tmp_path, "multi-obverse.png"),
        reverse=_image(tmp_path, "multi-reverse.png"),
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

    outcome, reports, pipeline, _, failures, provenance = run_case(
        case,
        provider=CountingProvider(),
        retriever=retriever,
        retrieval_limit=10,
    )

    assert calls == ["obverse", "obverse", "reverse", "reverse"]
    assert len(reports) == 2
    assert len(provenance) == 4
    assert failures == ()
    assert outcome.decision is RecognitionDecision.IDENTIFY
    assert pipeline is not None
