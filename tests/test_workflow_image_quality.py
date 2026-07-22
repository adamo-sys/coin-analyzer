"""Focused tests for Sprint 8 Unit 3: ImageQualityScoringStage."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from capture_import.workflow_image_normalization import ImageNormalizationStage
from capture_import.workflow_image_quality import (
    IMAGE_QUALITY_SCORING_STAGE_ID,
    ImageQualityScoringStage,
    QualityConfidence,
    ReadinessDecision,
    _parse_normalized_key,
    _score_and_decide,
)
from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
    StageArtifact,
    StageInput,
)
from capture_import.workflow_pipeline import (
    ProcessingPipeline,
    StageContractError,
    StageExecutionError,
)
from capture_import.workflow_stages import (
    PREPARED_MANIFEST_ARTIFACT,
    PREPARED_MANIFEST_NAME,
)


def _make_test_image_cv2(
    *,
    width: int = 640,
    height: int = 480,
    color: tuple[int, int, int] = (128, 64, 32),
) -> np.ndarray:
    """Generate a test image as an OpenCV BGR array."""
    bgr = (color[2], color[1], color[0])
    image = np.full((height, width, 3), bgr, dtype=np.uint8)
    return image


def _save_test_jpeg(path: Path, image: np.ndarray, quality: int = 92) -> None:
    """Save an OpenCV BGR image as JPEG."""
    cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, quality])


def _make_blurred_image(*, width: int = 640, height: int = 480) -> np.ndarray:
    """Generate a heavily blurred image (low sharpness)."""
    image = _make_test_image_cv2(width=width, height=height)
    return cv2.GaussianBlur(image, (51, 51), 10)


def _make_low_contrast_image(*, width: int = 640, height: int = 480) -> np.ndarray:
    """Generate a low-contrast image (narrow intensity range)."""
    gray = np.full((height, width), 128, dtype=np.uint8)
    noise = np.random.RandomState(42).randint(0, 5, (height, width), dtype=np.uint8)
    gray = cv2.add(gray, noise)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _make_underexposed_image(*, width: int = 640, height: int = 480) -> np.ndarray:
    """Generate a dark (underexposed) image."""
    gray = np.full((height, width), 30, dtype=np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _make_overexposed_image(*, width: int = 640, height: int = 480) -> np.ndarray:
    """Generate a bright (overexposed) image."""
    gray = np.full((height, width), 240, dtype=np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _make_blown_highlight_image(*, width: int = 640, height: int = 480) -> np.ndarray:
    """Generate an image with many blown highlights."""
    gray = np.full((height, width), 252, dtype=np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _make_high_quality_image(*, width: int = 1200, height: int = 900) -> np.ndarray:
    """Generate a high-quality image (sharp, good contrast, proper exposure)."""
    x = np.linspace(0, 255, width, dtype=np.uint8)
    y = np.linspace(0, 255, height, dtype=np.uint8)
    X, Y = np.meshgrid(x, y)
    pattern = ((X + Y) // 2).astype(np.uint8)
    return cv2.cvtColor(pattern, cv2.COLOR_GRAY2BGR)


def _make_tiny_image(*, width: int = 200, height: int = 150) -> np.ndarray:
    """Generate an extremely small image."""
    return _make_test_image_cv2(width=width, height=height)


def _build_manifest(
    *,
    coin_id: str = "coin-1",
    photos: dict[str, str] | None = None,
) -> dict:
    """Build a minimal manifest payload for testing."""
    if photos is None:
        photos = {"front": "images/coin-1-front.jpg"}
    return {
        "schema": "coin-analyzer.capture-package",
        "package_version": "1.0",
        "created_by": "Test",
        "created_with": "0.1.0",
        "exported_at": "2026-07-21T12:00:00Z",
        "session": {
            "id": "session-1",
            "name": "Test Session",
            "description": "",
            "session_date": None,
            "created_at": "2026-07-21T12:00:00Z",
            "updated_at": "2026-07-21T12:00:00Z",
        },
        "coins": [
            {
                "id": coin_id,
                "position": 0,
                "country": "Canada",
                "denomination": "1 Dollar",
                "year": "1967",
                "mint": "",
                "purchase_price": "0.00",
                "purchase_currency": "CAD",
                "seller": "",
                "purchase_date": None,
                "notes": "",
                "quantity": 1,
                "composition": "silver",
                "is_bullion": False,
                "asw_troy_ounces": None,
                "photos": {
                    role: {
                        "path": path,
                        "original_name": Path(path).name,
                        "mime_type": "image/jpeg",
                        "byte_length": 1024,
                        "width": 640,
                        "height": 480,
                        "captured_at": "2026-07-21T12:00:00Z",
                    }
                    for role, path in photos.items()
                },
                "created_at": "2026-07-21T12:00:00Z",
                "updated_at": "2026-07-21T12:00:00Z",
            }
        ],
    }


def _build_package_zip(
    *,
    path: Path,
    manifest: dict,
    images: dict[str, bytes],
) -> None:
    """Build a capture-package zip at ``path`` with manifest and images."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "capture_package.json",
            json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        )
        for image_path, image_bytes in images.items():
            zf.writestr(image_path, image_bytes)


def _run_normalization(
    *,
    source: Path,
    workspace: Path,
    manifest: dict,
    images: dict[str, bytes],
) -> StageInput:
    """Run normalization stage and return the stage input with artifacts."""
    _build_package_zip(path=source, manifest=manifest, images=images)
    manifest_path = workspace / PREPARED_MANIFEST_NAME
    manifest_path.write_bytes(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
    )
    artifacts = {
        PREPARED_MANIFEST_ARTIFACT: StageArtifact(
            relative_path=PREPARED_MANIFEST_NAME,
            content_type="application/json",
        )
    }
    stage_input = StageInput(
        request=ImportRequest(
            source=source,
            collection_id="collection-1",
            configuration=ImportConfiguration(),
        ),
        workspace=workspace,
        artifacts=artifacts,
    )
    normalizer = ImageNormalizationStage()
    result = normalizer.execute(stage_input)

    return StageInput(
        request=stage_input.request,
        workspace=workspace,
        artifacts=dict(result.artifacts),
    )


class ParseNormalizedKeyTests(unittest.TestCase):
    def test_valid_key(self) -> None:
        self.assertEqual(
            _parse_normalized_key("normalized-coin-1-front"), ("coin-1", "front")
        )
        self.assertEqual(
            _parse_normalized_key("normalized-coin-1-reverse"), ("coin-1", "reverse")
        )
        self.assertEqual(_parse_normalized_key("normalized-a-b-edge"), ("a-b", "edge"))

    def test_non_normalized_key(self) -> None:
        self.assertIsNone(_parse_normalized_key("prepared-manifest"))
        self.assertIsNone(_parse_normalized_key("other"))

    def test_malformed_key(self) -> None:
        self.assertIsNone(_parse_normalized_key("normalized"))
        self.assertIsNone(_parse_normalized_key("normalized-"))


class ScoreAndDecideTests(unittest.TestCase):
    def test_perfect_quality(self) -> None:
        metrics = {
            "resolution": 1200,
            "sharpness": 500,
            "contrast": 80,
            "brightness": 128,
            "blown_highlight_ratio": 0.0,
        }
        score, decision, confidence = _score_and_decide(metrics)
        self.assertEqual(score, 100)
        self.assertEqual(decision, ReadinessDecision.READY)
        self.assertEqual(confidence, QualityConfidence.HIGH)

    def test_tiny_resolution(self) -> None:
        metrics = {
            "resolution": 200,
            "sharpness": 500,
            "contrast": 80,
            "brightness": 128,
            "blown_highlight_ratio": 0.0,
        }
        score, decision, confidence = _score_and_decide(metrics)
        self.assertEqual(score, 65)
        self.assertEqual(decision, ReadinessDecision.MAYBE)
        self.assertEqual(confidence, QualityConfidence.MEDIUM)

    def test_limited_resolution(self) -> None:
        metrics = {
            "resolution": 500,
            "sharpness": 500,
            "contrast": 80,
            "brightness": 128,
            "blown_highlight_ratio": 0.0,
        }
        score, decision, confidence = _score_and_decide(metrics)
        self.assertEqual(score, 85)
        self.assertEqual(decision, ReadinessDecision.READY)
        self.assertEqual(confidence, QualityConfidence.MEDIUM)

    def test_very_low_sharpness(self) -> None:
        metrics = {
            "resolution": 1200,
            "sharpness": 10,
            "contrast": 80,
            "brightness": 128,
            "blown_highlight_ratio": 0.0,
        }
        score, decision, confidence = _score_and_decide(metrics)
        self.assertEqual(score, 70)
        self.assertEqual(decision, ReadinessDecision.MAYBE)
        self.assertEqual(confidence, QualityConfidence.MEDIUM)

    def test_moderate_blur(self) -> None:
        metrics = {
            "resolution": 1200,
            "sharpness": 50,
            "contrast": 80,
            "brightness": 128,
            "blown_highlight_ratio": 0.0,
        }
        score, decision, confidence = _score_and_decide(metrics)
        self.assertEqual(score, 85)
        self.assertEqual(decision, ReadinessDecision.READY)
        self.assertEqual(confidence, QualityConfidence.MEDIUM)

    def test_low_contrast(self) -> None:
        metrics = {
            "resolution": 1200,
            "sharpness": 500,
            "contrast": 10,
            "brightness": 128,
            "blown_highlight_ratio": 0.0,
        }
        score, decision, confidence = _score_and_decide(metrics)
        self.assertEqual(score, 85)
        self.assertEqual(decision, ReadinessDecision.READY)
        self.assertEqual(confidence, QualityConfidence.MEDIUM)

    def test_underexposed(self) -> None:
        metrics = {
            "resolution": 1200,
            "sharpness": 500,
            "contrast": 80,
            "brightness": 30,
            "blown_highlight_ratio": 0.0,
        }
        score, decision, confidence = _score_and_decide(metrics)
        self.assertEqual(score, 80)
        self.assertEqual(decision, ReadinessDecision.READY)
        self.assertEqual(confidence, QualityConfidence.MEDIUM)

    def test_overexposed(self) -> None:
        metrics = {
            "resolution": 1200,
            "sharpness": 500,
            "contrast": 80,
            "brightness": 240,
            "blown_highlight_ratio": 0.0,
        }
        score, decision, confidence = _score_and_decide(metrics)
        self.assertEqual(score, 80)
        self.assertEqual(decision, ReadinessDecision.READY)
        self.assertEqual(confidence, QualityConfidence.MEDIUM)

    def test_blown_highlights(self) -> None:
        metrics = {
            "resolution": 1200,
            "sharpness": 500,
            "contrast": 80,
            "brightness": 128,
            "blown_highlight_ratio": 0.5,
        }
        score, decision, confidence = _score_and_decide(metrics)
        self.assertEqual(score, 85)
        self.assertEqual(decision, ReadinessDecision.READY)
        self.assertEqual(confidence, QualityConfidence.MEDIUM)

    def test_not_ready_threshold(self) -> None:
        # Multiple issues push score below 50.
        metrics = {
            "resolution": 200,
            "sharpness": 10,
            "contrast": 10,
            "brightness": 30,
            "blown_highlight_ratio": 0.5,
        }
        score, decision, confidence = _score_and_decide(metrics)
        self.assertLess(score, 50)
        self.assertEqual(decision, ReadinessDecision.NOT_READY)
        self.assertEqual(confidence, QualityConfidence.LOW)

    def test_medium_confidence_one_issue(self) -> None:
        metrics = {
            "resolution": 500,
            "sharpness": 500,
            "contrast": 80,
            "brightness": 128,
            "blown_highlight_ratio": 0.0,
        }
        score, decision, confidence = _score_and_decide(metrics)
        self.assertEqual(score, 85)
        self.assertEqual(decision, ReadinessDecision.READY)
        self.assertEqual(confidence, QualityConfidence.MEDIUM)

    def test_low_confidence_three_plus_issues(self) -> None:
        metrics = {
            "resolution": 200,
            "sharpness": 10,
            "contrast": 10,
            "brightness": 30,
            "blown_highlight_ratio": 0.5,
        }
        score, decision, confidence = _score_and_decide(metrics)
        self.assertLess(score, 50)
        self.assertEqual(decision, ReadinessDecision.NOT_READY)
        self.assertEqual(confidence, QualityConfidence.LOW)

    def test_score_clamping(self) -> None:
        metrics = {
            "resolution": 100,
            "sharpness": 0,
            "contrast": 0,
            "brightness": 0,
            "blown_highlight_ratio": 1.0,
        }
        score, decision, _ = _score_and_decide(metrics)
        self.assertEqual(score, 0)
        self.assertEqual(decision, ReadinessDecision.NOT_READY)


class ValidQualityScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.source = self.tmp / "test.ca-package"
        self.workspace = self.tmp / "workspace"
        self.workspace.mkdir()

    def tearDown(self) -> None:
        for root, dirs, files in os.walk(self.tmp, topdown=False):
            for name in files:
                os.chmod(Path(root) / name, 0o666)
                (Path(root) / name).unlink()
            for name in dirs:
                os.chmod(Path(root) / name, 0o777)
                (Path(root) / name).rmdir()
        self.tmp.rmdir()

    def test_single_front_image(self) -> None:
        image = _make_high_quality_image()
        buf = BytesIO()
        pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        pil_img.save(buf, format="JPEG", quality=92)
        manifest = _build_manifest(
            coin_id="coin-1", photos={"front": "images/front.jpg"}
        )
        stage_input = _run_normalization(
            source=self.source,
            workspace=self.workspace,
            manifest=manifest,
            images={"images/front.jpg": buf.getvalue()},
        )
        stage = ImageQualityScoringStage()
        result = stage.execute(stage_input)

        self.assertEqual(result.metadata.get("quality_scored_image_count"), 1)
        records = result.metadata.get("quality_records", [])
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["coin_id"], "coin-1")
        self.assertEqual(record["role"], "front")
        self.assertGreaterEqual(record["readiness_score"], 80)
        self.assertEqual(record["decision"], ReadinessDecision.READY.value)

    def test_multiple_roles(self) -> None:
        front = _make_high_quality_image()
        reverse = _make_high_quality_image()
        buf_front = BytesIO()
        buf_reverse = BytesIO()
        Image.fromarray(cv2.cvtColor(front, cv2.COLOR_BGR2RGB)).save(
            buf_front, format="JPEG", quality=92
        )
        Image.fromarray(cv2.cvtColor(reverse, cv2.COLOR_BGR2RGB)).save(
            buf_reverse, format="JPEG", quality=92
        )

        manifest = _build_manifest(
            coin_id="coin-1",
            photos={"front": "images/front.jpg", "reverse": "images/reverse.jpg"},
        )
        stage_input = _run_normalization(
            source=self.source,
            workspace=self.workspace,
            manifest=manifest,
            images={
                "images/front.jpg": buf_front.getvalue(),
                "images/reverse.jpg": buf_reverse.getvalue(),
            },
        )
        stage = ImageQualityScoringStage()
        result = stage.execute(stage_input)

        self.assertEqual(result.metadata.get("quality_scored_image_count"), 2)
        records = result.metadata.get("quality_records", [])
        roles = {r["role"] for r in records}
        self.assertEqual(roles, {"front", "reverse"})

    def test_multiple_coins(self) -> None:
        coin1 = _make_high_quality_image()
        coin2 = _make_high_quality_image()
        buf1 = BytesIO()
        buf2 = BytesIO()
        Image.fromarray(cv2.cvtColor(coin1, cv2.COLOR_BGR2RGB)).save(
            buf1, format="JPEG", quality=92
        )
        Image.fromarray(cv2.cvtColor(coin2, cv2.COLOR_BGR2RGB)).save(
            buf2, format="JPEG", quality=92
        )

        manifest = _build_manifest(coin_id="coin-a", photos={"front": "images/a.jpg"})
        manifest["coins"].append(
            {
                "id": "coin-b",
                "position": 1,
                "country": "Canada",
                "denomination": "25 Cents",
                "year": "1992",
                "mint": "",
                "purchase_price": "0.00",
                "purchase_currency": "CAD",
                "seller": "",
                "purchase_date": None,
                "notes": "",
                "quantity": 1,
                "composition": "nickel",
                "is_bullion": False,
                "asw_troy_ounces": None,
                "photos": {
                    "front": {
                        "path": "images/b.jpg",
                        "original_name": "b.jpg",
                        "mime_type": "image/jpeg",
                        "byte_length": 1024,
                        "width": 640,
                        "height": 480,
                        "captured_at": "2026-07-21T12:00:00Z",
                    }
                },
                "created_at": "2026-07-21T12:00:00Z",
                "updated_at": "2026-07-21T12:00:00Z",
            }
        )
        stage_input = _run_normalization(
            source=self.source,
            workspace=self.workspace,
            manifest=manifest,
            images={
                "images/a.jpg": buf1.getvalue(),
                "images/b.jpg": buf2.getvalue(),
            },
        )
        stage = ImageQualityScoringStage()
        result = stage.execute(stage_input)

        self.assertEqual(result.metadata.get("quality_scored_image_count"), 2)
        records = result.metadata.get("quality_records", [])
        coin_ids = {r["coin_id"] for r in records}
        self.assertEqual(coin_ids, {"coin-a", "coin-b"})

    def test_blurred_image_scores_lower(self) -> None:
        sharp = _make_high_quality_image()
        blurred = _make_blurred_image(width=1200, height=900)
        buf_sharp = BytesIO()
        buf_blur = BytesIO()
        Image.fromarray(cv2.cvtColor(sharp, cv2.COLOR_BGR2RGB)).save(
            buf_sharp, format="JPEG", quality=92
        )
        Image.fromarray(cv2.cvtColor(blurred, cv2.COLOR_BGR2RGB)).save(
            buf_blur, format="JPEG", quality=92
        )

        manifest = _build_manifest(
            coin_id="coin-1",
            photos={"sharp": "images/sharp.jpg", "blurred": "images/blurred.jpg"},
        )
        stage_input = _run_normalization(
            source=self.source,
            workspace=self.workspace,
            manifest=manifest,
            images={
                "images/sharp.jpg": buf_sharp.getvalue(),
                "images/blurred.jpg": buf_blur.getvalue(),
            },
        )
        stage = ImageQualityScoringStage()
        result = stage.execute(stage_input)

        records = {r["role"]: r for r in result.metadata["quality_records"]}
        self.assertGreater(
            records["sharp"]["sharpness"], records["blurred"]["sharpness"]
        )
        self.assertGreater(
            records["sharp"]["readiness_score"], records["blurred"]["readiness_score"]
        )

    def test_low_contrast_image(self) -> None:
        image = _make_low_contrast_image(width=1200, height=900)
        buf = BytesIO()
        Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).save(
            buf, format="JPEG", quality=92
        )

        manifest = _build_manifest(
            coin_id="coin-1", photos={"front": "images/front.jpg"}
        )
        stage_input = _run_normalization(
            source=self.source,
            workspace=self.workspace,
            manifest=manifest,
            images={"images/front.jpg": buf.getvalue()},
        )
        stage = ImageQualityScoringStage()
        result = stage.execute(stage_input)

        record = result.metadata["quality_records"][0]
        self.assertLess(record["contrast"], 20)
        self.assertLess(record["readiness_score"], 100)
        self.assertEqual(record["confidence"], QualityConfidence.MEDIUM.value)

    def test_underexposed_image(self) -> None:
        image = _make_underexposed_image(width=1200, height=900)
        buf = BytesIO()
        Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).save(
            buf, format="JPEG", quality=92
        )

        manifest = _build_manifest(
            coin_id="coin-1", photos={"front": "images/front.jpg"}
        )
        stage_input = _run_normalization(
            source=self.source,
            workspace=self.workspace,
            manifest=manifest,
            images={"images/front.jpg": buf.getvalue()},
        )
        stage = ImageQualityScoringStage()
        result = stage.execute(stage_input)

        record = result.metadata["quality_records"][0]
        self.assertLess(record["brightness"], 45)
        self.assertLess(record["readiness_score"], 100)

    def test_overexposed_image(self) -> None:
        image = _make_overexposed_image(width=1200, height=900)
        buf = BytesIO()
        Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).save(
            buf, format="JPEG", quality=92
        )

        manifest = _build_manifest(
            coin_id="coin-1", photos={"front": "images/front.jpg"}
        )
        stage_input = _run_normalization(
            source=self.source,
            workspace=self.workspace,
            manifest=manifest,
            images={"images/front.jpg": buf.getvalue()},
        )
        stage = ImageQualityScoringStage()
        result = stage.execute(stage_input)

        record = result.metadata["quality_records"][0]
        self.assertGreater(record["brightness"], 215)
        self.assertLess(record["readiness_score"], 100)

    def test_blown_highlight_image(self) -> None:
        image = _make_blown_highlight_image(width=1200, height=900)
        buf = BytesIO()
        Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).save(
            buf, format="JPEG", quality=92
        )

        manifest = _build_manifest(
            coin_id="coin-1", photos={"front": "images/front.jpg"}
        )
        stage_input = _run_normalization(
            source=self.source,
            workspace=self.workspace,
            manifest=manifest,
            images={"images/front.jpg": buf.getvalue()},
        )
        stage = ImageQualityScoringStage()
        result = stage.execute(stage_input)

        record = result.metadata["quality_records"][0]
        self.assertGreater(record["blown_highlight_ratio"], 0.12)
        self.assertLess(record["readiness_score"], 100)

    def test_tiny_image_low_resolution(self) -> None:
        image = _make_tiny_image(width=200, height=150)
        buf = BytesIO()
        Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).save(
            buf, format="JPEG", quality=92
        )

        manifest = _build_manifest(
            coin_id="coin-1", photos={"front": "images/front.jpg"}
        )
        stage_input = _run_normalization(
            source=self.source,
            workspace=self.workspace,
            manifest=manifest,
            images={"images/front.jpg": buf.getvalue()},
        )
        stage = ImageQualityScoringStage()
        result = stage.execute(stage_input)

        record = result.metadata["quality_records"][0]
        self.assertLess(record["resolution"], 300)
        self.assertLess(record["readiness_score"], 70)
        self.assertEqual(record["decision"], ReadinessDecision.NOT_READY.value)

    def test_deterministic_repeated_scoring(self) -> None:
        image = _make_high_quality_image()
        buf = BytesIO()
        Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).save(
            buf, format="JPEG", quality=92
        )

        manifest = _build_manifest(
            coin_id="coin-1", photos={"front": "images/front.jpg"}
        )
        stage_input = _run_normalization(
            source=self.source,
            workspace=self.workspace,
            manifest=manifest,
            images={"images/front.jpg": buf.getvalue()},
        )
        stage = ImageQualityScoringStage()
        result1 = stage.execute(stage_input)
        result2 = stage.execute(stage_input)

        self.assertEqual(
            result1.metadata["quality_records"],
            result2.metadata["quality_records"],
        )


class FailureModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.workspace = self.tmp / "workspace"
        self.workspace.mkdir()

    def tearDown(self) -> None:
        for root, dirs, files in os.walk(self.tmp, topdown=False):
            for name in files:
                os.chmod(Path(root) / name, 0o666)
                (Path(root) / name).unlink()
            for name in dirs:
                os.chmod(Path(root) / name, 0o777)
                (Path(root) / name).rmdir()
        self.tmp.rmdir()

    def test_no_normalized_artifacts_raises_contract_error(self) -> None:
        stage_input = StageInput(
            request=ImportRequest(
                source=self.workspace / "dummy",
                collection_id="collection-1",
                configuration=ImportConfiguration(),
            ),
            workspace=self.workspace,
            artifacts={
                "prepared-manifest": StageArtifact(
                    relative_path="x", content_type="application/json"
                )
            },
        )
        stage = ImageQualityScoringStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, IMAGE_QUALITY_SCORING_STAGE_ID)
        self.assertIn("normalized", str(ctx.exception).lower())

    def test_missing_normalized_file_raises_contract_error(self) -> None:
        artifacts = {
            "normalized-coin-1-front": StageArtifact(
                relative_path="normalized/coin-1/front.jpg",
                content_type="image/jpeg",
            )
        }
        stage_input = StageInput(
            request=ImportRequest(
                source=self.workspace / "dummy",
                collection_id="collection-1",
                configuration=ImportConfiguration(),
            ),
            workspace=self.workspace,
            artifacts=artifacts,
        )
        stage = ImageQualityScoringStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, IMAGE_QUALITY_SCORING_STAGE_ID)

    def test_corrupt_image_raises_execution_error(self) -> None:
        bad_path = self.workspace / "normalized" / "coin-1" / "front.jpg"
        bad_path.parent.mkdir(parents=True, exist_ok=True)
        bad_path.write_bytes(b"not an image")

        artifacts = {
            "normalized-coin-1-front": StageArtifact(
                relative_path="normalized/coin-1/front.jpg",
                content_type="image/jpeg",
            )
        }
        stage_input = StageInput(
            request=ImportRequest(
                source=self.workspace / "dummy",
                collection_id="collection-1",
                configuration=ImportConfiguration(),
            ),
            workspace=self.workspace,
            artifacts=artifacts,
        )
        stage = ImageQualityScoringStage()
        with self.assertRaises(StageExecutionError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, IMAGE_QUALITY_SCORING_STAGE_ID)


class PipelineIntegrationTests(unittest.TestCase):
    def test_stage_conforms_to_protocol(self) -> None:
        stage = ImageQualityScoringStage()
        self.assertEqual(stage.stage_id, IMAGE_QUALITY_SCORING_STAGE_ID)
        self.assertTrue(callable(stage.execute))

    def test_stage_in_pipeline(self) -> None:
        from capture_import.workflow_image_normalization import ImageNormalizationStage

        pipeline = ProcessingPipeline(
            stages=(ImageNormalizationStage(), ImageQualityScoringStage())
        )
        self.assertIn(IMAGE_QUALITY_SCORING_STAGE_ID, pipeline.stage_ids)


if __name__ == "__main__":
    unittest.main()
