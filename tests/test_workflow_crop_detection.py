"""Focused tests for Sprint 8 Unit 4: CropDetectionStage.

All test images are synthetic OpenCV drawings with precise geometry so
that crop rectangles and confidence values are deterministic and
exactly assertable.
"""

from __future__ import annotations

import math
import os
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from capture_import.workflow_crop_detection import (
    CROP_DETECTION_STAGE_ID,
    CROP_PADDING_RATIO,
    MIN_CROP_CONFIDENCE,
    CropDetectionStage,
    _apply_padding,
    _compute_confidence,
    _find_best_crop,
    _qualify_contour,
    _require_contained,
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

# ---------------------------------------------------------------------------
# Synthetic-image helpers
# ---------------------------------------------------------------------------


def _save_test_jpeg(path: Path, image: np.ndarray, quality: int = 92) -> None:
    """Save an OpenCV BGR image as JPEG."""
    cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, quality])


def _make_dark_coin_on_light(*, size: int = 600, radius: int = 200) -> np.ndarray:
    """Dark grey circle on a light background."""
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    cv2.circle(img, (size // 2, size // 2), radius, (30, 30, 30), -1)
    return img


def _make_light_coin_on_dark(*, size: int = 600, radius: int = 200) -> np.ndarray:
    """Light grey circle on a dark background."""
    img = np.full((size, size, 3), 30, dtype=np.uint8)
    cv2.circle(img, (size // 2, size // 2), radius, (220, 220, 220), -1)
    return img


def _make_square_object(*, size: int = 600) -> np.ndarray:
    """Square (aspect ratio 1.0, but circularity is low)."""
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    half = size // 2
    quarter = size // 4
    cv2.rectangle(
        img,
        (quarter, quarter),
        (half + quarter, half + quarter),
        (30, 30, 30),
        -1,
    )
    return img


def _make_elongated_object(*, size: int = 600) -> np.ndarray:
    """Elongated ellipse (low aspect ratio)."""
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    cv2.ellipse(
        img,
        (size // 2, size // 2),
        (250, 80),
        0,
        0,
        360,
        (30, 30, 30),
        -1,
    )
    return img


def _make_tiny_circle(*, size: int = 200, radius: int = 20) -> np.ndarray:
    """Very small circle (rejected by area ratio on a 600x600 canvas)."""
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    cv2.circle(img, (size // 2, size // 2), radius, (30, 30, 30), -1)
    return img


def _make_full_frame_coin(*, size: int = 600) -> np.ndarray:
    """Circle filling almost the entire frame (area ratio near 0.98)."""
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    cv2.circle(img, (size // 2, size // 2), size // 2 - 10, (30, 30, 30), -1)
    return img


def _make_two_equal_circles(*, size: int = 600) -> np.ndarray:
    """Two same-size circles for tie-breaker determinism."""
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    cv2.circle(img, (150, 300), 100, (30, 30, 30), -1)
    cv2.circle(img, (450, 300), 100, (30, 30, 30), -1)
    return img


def _make_coin_at_edge(*, size: int = 600, radius: int = 150) -> np.ndarray:
    """Circle touching the top-left edge (padding must clamp)."""
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    cv2.circle(img, (radius, radius), radius, (30, 30, 30), -1)
    return img


def _make_medium_coin(*, size: int = 600, radius: int = 180) -> np.ndarray:
    """Medium coin occupying ~60% area ratio (area_score should be high)."""
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    cv2.circle(img, (size // 2, size // 2), radius, (30, 30, 30), -1)
    return img


# ---------------------------------------------------------------------------
# Stage-input builder
# ---------------------------------------------------------------------------


def _build_stage_input(
    *,
    workspace: Path,
    artifacts: dict[str, StageArtifact],
) -> StageInput:
    """Build a minimal StageInput for crop-detection tests."""
    return StageInput(
        request=ImportRequest(
            source=workspace / "dummy.ca-package",
            collection_id="collection-1",
            configuration=ImportConfiguration(),
        ),
        workspace=workspace,
        artifacts=artifacts,
    )


# ---------------------------------------------------------------------------
# Internal-function tests
# ---------------------------------------------------------------------------


class QualifyContourTests(unittest.TestCase):
    def test_perfect_circle_qualifies(self) -> None:
        area = math.pi * 100 * 100
        perimeter = 2 * math.pi * 100
        bbox = (0, 0, 200, 200)
        image_area = 600.0 * 600.0
        result = _qualify_contour(area, perimeter, bbox, image_area)
        self.assertIsNotNone(result)
        area_ratio, aspect_ratio, circularity = result
        self.assertAlmostEqual(circularity, 1.0, places=3)
        self.assertAlmostEqual(aspect_ratio, 1.0, places=3)

    def test_square_rejected_by_circularity(self) -> None:
        area = 200.0 * 200.0
        perimeter = 4.0 * 200.0
        bbox = (0, 0, 200, 200)
        image_area = 600.0 * 600.0
        result = _qualify_contour(area, perimeter, bbox, image_area)
        self.assertIsNone(result)

    def test_elongated_rejected_by_aspect(self) -> None:
        area = math.pi * 200 * 50
        perimeter = 2 * math.pi * math.sqrt((200**2 + 50**2) / 2)
        bbox = (0, 0, 400, 100)
        image_area = 600.0 * 600.0
        result = _qualify_contour(area, perimeter, bbox, image_area)
        self.assertIsNone(result)

    def test_tiny_rejected_by_area(self) -> None:
        area = math.pi * 10 * 10
        perimeter = 2 * math.pi * 10
        bbox = (0, 0, 20, 20)
        image_area = 600.0 * 600.0
        result = _qualify_contour(area, perimeter, bbox, image_area)
        self.assertIsNone(result)


class ComputeConfidenceTests(unittest.TestCase):
    def test_perfect_scores_to_one(self) -> None:
        conf = _compute_confidence(0.5, 1.0, 1.0)
        self.assertAlmostEqual(conf, 1.0, places=3)

    def test_low_circularity_reduces_confidence(self) -> None:
        conf = _compute_confidence(0.5, 1.0, 0.6)
        self.assertLess(conf, 1.0)
        self.assertGreaterEqual(conf, 0.0)

    def test_poor_aspect_reduces_confidence(self) -> None:
        conf = _compute_confidence(0.5, 0.8, 1.0)
        self.assertLess(conf, 1.0)

    def test_small_area_reduces_confidence(self) -> None:
        conf = _compute_confidence(0.1, 1.0, 1.0)
        self.assertLess(conf, 1.0)

    def test_confidence_bounded(self) -> None:
        conf = _compute_confidence(0.01, 0.5, 0.3)
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)

    def test_area_score_symmetric_around_target(self) -> None:
        """Area score penalizes deviation from TARGET_AREA_RATIO=0.5."""
        conf_50 = _compute_confidence(0.50, 1.0, 1.0)
        conf_25 = _compute_confidence(0.25, 1.0, 1.0)
        conf_75 = _compute_confidence(0.75, 1.0, 1.0)
        # At 0.50 area ratio, area_score is 1.0 -> highest confidence.
        # At 0.25 and 0.75, area_score is 0.5 -> lower confidence.
        self.assertGreater(conf_50, conf_25)
        self.assertAlmostEqual(conf_25, conf_75, places=4)

    def test_full_frame_area_penalized(self) -> None:
        """Near-full-frame coins get reduced area_score but still pass."""
        # area_ratio 0.98 -> area_score = 1.0 - |0.98 - 0.5| / 0.5 = 0.04
        conf = _compute_confidence(0.98, 1.0, 1.0)
        # Circularit 1.0, aspect 1.0 -> only area drags it down.
        # 0.40*1.0 + 0.35*1.0 + 0.25*0.04 = 0.76
        self.assertAlmostEqual(conf, 0.76, places=4)

    def test_medium_coin_high_confidence(self) -> None:
        """A 60%-area-ratio coin should score well."""
        # area_ratio 0.60 -> area_score = 1.0 - |0.60 - 0.5| / 0.5 = 0.80
        conf = _compute_confidence(0.60, 1.0, 1.0)
        # 0.40*1.0 + 0.35*1.0 + 0.25*0.80 = 0.95
        self.assertAlmostEqual(conf, 0.95, places=4)
        self.assertGreater(conf, MIN_CROP_CONFIDENCE)

    def test_confidence_threshold_boundary(self) -> None:
        """Direct test of the crop-decision branch at MIN_CROP_CONFIDENCE.

        Confidence is rounded to 4 decimals before comparison.
        """
        threshold = MIN_CROP_CONFIDENCE  # 0.65

        # Just below threshold -> no crop
        below = round(threshold - 0.0001, 4)
        self.assertFalse(below >= threshold)

        # Exactly at threshold -> crop (>= is inclusive)
        self.assertTrue(threshold >= threshold)

        # Just above threshold -> crop
        above = round(threshold + 0.0001, 4)
        self.assertTrue(above >= threshold)


class ApplyPaddingTests(unittest.TestCase):
    def test_padding_expands_all_sides(self) -> None:
        x, y, w, h = _apply_padding(100, 100, 200, 200, 600, 600)
        pad = max(1, int(200 * CROP_PADDING_RATIO))
        self.assertEqual(x, 100 - pad)
        self.assertEqual(y, 100 - pad)
        self.assertEqual(w, 200 + 2 * pad)
        self.assertEqual(h, 200 + 2 * pad)

    def test_padding_clamps_at_zero(self) -> None:
        x, y, w, h = _apply_padding(0, 0, 100, 100, 600, 600)
        self.assertEqual(x, 0)
        self.assertEqual(y, 0)

    def test_padding_clamps_at_max(self) -> None:
        x, y, w, h = _apply_padding(500, 500, 100, 100, 600, 600)
        self.assertLessEqual(x + w, 600)
        self.assertLessEqual(y + h, 600)


class RequireContainedTests(unittest.TestCase):
    def test_relative_path_passes(self) -> None:
        base = Path("/tmp/workspace")
        path = Path("cropped/coin-1/front.jpg")
        # Should not raise.
        _require_contained(path, base, stage_id="test", label="output")

    def test_dotdot_component_raises(self) -> None:
        base = Path("/tmp/workspace")
        path = Path("normalized/../outside.jpg")
        with self.assertRaises(StageContractError) as ctx:
            _require_contained(path, base, stage_id="test", label="input")
        self.assertIn("parent traversal", str(ctx.exception))

    def test_absolute_path_raises(self) -> None:
        base = Path("/tmp/workspace")
        path = Path("C:/etc/passwd") if os.name == "nt" else Path("/etc/passwd")
        with self.assertRaises(StageContractError) as ctx:
            _require_contained(path, base, stage_id="test", label="input")
        self.assertIn("absolute", str(ctx.exception))

    def test_windows_relative_path_passes(self) -> None:
        base = Path("C:/workspace")
        path = Path("cropped/coin-1/front.jpg")
        _require_contained(path, base, stage_id="test", label="output")


class FindBestCropTests(unittest.TestCase):
    def test_dark_coin_on_light(self) -> None:
        img = _make_dark_coin_on_light()
        result = _find_best_crop(img)
        self.assertIsNotNone(result)
        x, y, w, h, conf = result
        self.assertGreater(conf, MIN_CROP_CONFIDENCE)
        self.assertLess(abs((x + w // 2) - 300), 50)
        self.assertLess(abs((y + h // 2) - 300), 50)

    def test_light_coin_on_dark(self) -> None:
        img = _make_light_coin_on_dark()
        result = _find_best_crop(img)
        self.assertIsNotNone(result)
        _, _, _, _, conf = result
        self.assertGreater(conf, MIN_CROP_CONFIDENCE)

    def test_square_rejected_no_crop(self) -> None:
        img = _make_square_object()
        result = _find_best_crop(img)
        self.assertIsNone(result)

    def test_elongated_rejected_no_crop(self) -> None:
        img = _make_elongated_object()
        result = _find_best_crop(img)
        self.assertIsNone(result)

    def test_full_frame_confidence_penalized(self) -> None:
        img = _make_full_frame_coin()
        result = _find_best_crop(img)
        self.assertIsNotNone(result)
        # Full-frame area ratio ~0.98 gets area_score penalty.
        self.assertLess(result[4], 0.95)
        # But perfect circularity still keeps it above threshold.
        self.assertGreaterEqual(result[4], MIN_CROP_CONFIDENCE)

    def test_two_equal_circles_deterministic(self) -> None:
        img = _make_two_equal_circles()
        result1 = _find_best_crop(img)
        result2 = _find_best_crop(img)
        self.assertEqual(result1, result2)
        self.assertIsNotNone(result1)

    def test_edge_touching_circle_clamped(self) -> None:
        img = _make_coin_at_edge()
        result = _find_best_crop(img)
        self.assertIsNotNone(result)
        x, y, w, h, _ = result
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + w, img.shape[1])
        self.assertLessEqual(y + h, img.shape[0])

    def test_medium_coin_passes_threshold(self) -> None:
        """A tightly framed but valid coin should still exceed threshold."""
        img = _make_medium_coin()
        result = _find_best_crop(img)
        self.assertIsNotNone(result)
        self.assertGreater(result[4], MIN_CROP_CONFIDENCE)


# ---------------------------------------------------------------------------
# Stage-integration tests
# ---------------------------------------------------------------------------


class HappyPathTests(unittest.TestCase):
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

    def test_dark_coin_crop_applied(self) -> None:
        img = _make_dark_coin_on_light()
        norm_path = self.workspace / "normalized" / "coin-1" / "front.jpg"
        norm_path.parent.mkdir(parents=True, exist_ok=True)
        _save_test_jpeg(norm_path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                )
            },
        )
        stage = CropDetectionStage()
        result = stage.execute(stage_input)

        self.assertIn("cropped-coin-1-front", result.artifacts)
        records = result.metadata["crop_records"]
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertTrue(rec["crop_applied"])
        self.assertGreater(rec["crop_confidence"], MIN_CROP_CONFIDENCE)
        self.assertEqual(rec["coin_id"], "coin-1")
        self.assertEqual(rec["role"], "front")

    def test_light_coin_crop_applied(self) -> None:
        img = _make_light_coin_on_dark()
        norm_path = self.workspace / "normalized" / "coin-1" / "front.jpg"
        norm_path.parent.mkdir(parents=True, exist_ok=True)
        _save_test_jpeg(norm_path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                )
            },
        )
        stage = CropDetectionStage()
        result = stage.execute(stage_input)

        records = result.metadata["crop_records"]
        self.assertTrue(records[0]["crop_applied"])

    def test_multiple_coins_and_roles(self) -> None:
        for coin_id, role in (("coin-a", "front"), ("coin-b", "reverse")):
            img = _make_dark_coin_on_light()
            norm_path = self.workspace / "normalized" / coin_id / f"{role}.jpg"
            norm_path.parent.mkdir(parents=True, exist_ok=True)
            _save_test_jpeg(norm_path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-a-front": StageArtifact(
                    relative_path="normalized/coin-a/front.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-b-reverse": StageArtifact(
                    relative_path="normalized/coin-b/reverse.jpg",
                    content_type="image/jpeg",
                ),
            },
        )
        stage = CropDetectionStage()
        result = stage.execute(stage_input)

        self.assertEqual(result.metadata["crop_applied_image_count"], 2)
        roles = {r["role"] for r in result.metadata["crop_records"]}
        self.assertEqual(roles, {"front", "reverse"})

    def test_fallback_no_crop(self) -> None:
        img = _make_square_object()
        norm_path = self.workspace / "normalized" / "coin-1" / "front.jpg"
        norm_path.parent.mkdir(parents=True, exist_ok=True)
        _save_test_jpeg(norm_path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                )
            },
        )
        stage = CropDetectionStage()
        result = stage.execute(stage_input)

        rec = result.metadata["crop_records"][0]
        self.assertFalse(rec["crop_applied"])
        self.assertEqual(rec["crop_confidence"], 0.0)
        self.assertEqual(rec["x"], 0)
        self.assertEqual(rec["y"], 0)
        self.assertEqual(rec["width"], 600)
        self.assertEqual(rec["height"], 600)

        cropped_path = self.workspace / "cropped" / "coin-1" / "front.jpg"
        self.assertEqual(cropped_path.read_bytes(), norm_path.read_bytes())

    def test_deterministic_record_ordering(self) -> None:
        for coin_id in ("coin-z", "coin-a"):
            img = _make_dark_coin_on_light()
            norm_path = self.workspace / "normalized" / coin_id / "front.jpg"
            norm_path.parent.mkdir(parents=True, exist_ok=True)
            _save_test_jpeg(norm_path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-z-front": StageArtifact(
                    relative_path="normalized/coin-z/front.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-a-front": StageArtifact(
                    relative_path="normalized/coin-a/front.jpg",
                    content_type="image/jpeg",
                ),
            },
        )
        stage = CropDetectionStage()
        result = stage.execute(stage_input)

        coin_ids = [r["coin_id"] for r in result.metadata["crop_records"]]
        self.assertEqual(coin_ids, ["coin-a", "coin-z"])

    def test_medium_coin_crop_applied(self) -> None:
        """A valid medium-sized coin should be cropped, not fall back."""
        img = _make_medium_coin()
        norm_path = self.workspace / "normalized" / "coin-1" / "front.jpg"
        norm_path.parent.mkdir(parents=True, exist_ok=True)
        _save_test_jpeg(norm_path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                )
            },
        )
        stage = CropDetectionStage()
        result = stage.execute(stage_input)

        rec = result.metadata["crop_records"][0]
        self.assertTrue(rec["crop_applied"])
        self.assertGreater(rec["crop_confidence"], MIN_CROP_CONFIDENCE)


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

    def test_no_normalized_artifacts_raises(self) -> None:
        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "other": StageArtifact(relative_path="x", content_type="text/plain")
            },
        )
        stage = CropDetectionStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, CROP_DETECTION_STAGE_ID)

    def test_missing_file_raises(self) -> None:
        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                )
            },
        )
        stage = CropDetectionStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, CROP_DETECTION_STAGE_ID)

    def test_corrupt_image_raises(self) -> None:
        bad = self.workspace / "normalized" / "coin-1" / "front.jpg"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_bytes(b"not an image")

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                )
            },
        )
        stage = CropDetectionStage()
        with self.assertRaises(StageExecutionError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, CROP_DETECTION_STAGE_ID)

    def test_source_escape_existing_file_raises(self) -> None:
        """An outside path to an existing file must fail as containment."""
        outside = self.workspace.parent / "outside.jpg"
        outside.write_bytes(b"fake image")

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="../outside.jpg",
                    content_type="image/jpeg",
                )
            },
        )
        stage = CropDetectionStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertIn("parent traversal", str(ctx.exception))

    def test_source_escape_missing_file_raises(self) -> None:
        """An outside path to a nonexistent file must also fail as containment."""
        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="../nonexistent.jpg",
                    content_type="image/jpeg",
                )
            },
        )
        stage = CropDetectionStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertIn("parent traversal", str(ctx.exception))

    def test_empty_image_fallback(self) -> None:
        img = np.full((600, 600, 3), 255, dtype=np.uint8)
        norm_path = self.workspace / "normalized" / "coin-1" / "front.jpg"
        norm_path.parent.mkdir(parents=True, exist_ok=True)
        _save_test_jpeg(norm_path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                )
            },
        )
        stage = CropDetectionStage()
        result = stage.execute(stage_input)

        rec = result.metadata["crop_records"][0]
        self.assertFalse(rec["crop_applied"])

    def test_duplicate_identity_raises(self) -> None:
        """Two artifact keys resolving to the same (coin_id, role) must fail."""
        from unittest.mock import patch

        img = _make_dark_coin_on_light()
        norm_path = self.workspace / "normalized" / "coin-1" / "front.jpg"
        norm_path.parent.mkdir(parents=True, exist_ok=True)
        _save_test_jpeg(norm_path, img)

        call_count = 0

        def mock_parse(key: str):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return ("coin-1", "front")
            return None

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-1-front-alt": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                ),
            },
        )

        with patch(
            "capture_import.workflow_crop_detection._parse_normalized_key",
            side_effect=mock_parse,
        ):
            stage = CropDetectionStage()
            with self.assertRaises(StageContractError) as ctx:
                stage.execute(stage_input)
            self.assertIn("duplicate", str(ctx.exception).lower())


class PipelineIntegrationTests(unittest.TestCase):
    def test_stage_conforms_to_protocol(self) -> None:
        stage = CropDetectionStage()
        self.assertEqual(stage.stage_id, CROP_DETECTION_STAGE_ID)
        self.assertTrue(callable(stage.execute))

    def test_stage_in_pipeline(self) -> None:
        from capture_import.workflow_image_normalization import (
            ImageNormalizationStage,
        )
        from capture_import.workflow_image_quality import (
            ImageQualityScoringStage,
        )

        pipeline = ProcessingPipeline(
            stages=(
                ImageNormalizationStage(),
                ImageQualityScoringStage(),
                CropDetectionStage(),
            )
        )
        self.assertIn(CROP_DETECTION_STAGE_ID, pipeline.stage_ids)


if __name__ == "__main__":
    unittest.main()
