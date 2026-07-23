"""Focused tests for Sprint 8 Unit 5: ObverseReversePairingStage.

All test images are synthetic OpenCV drawings so that metrics and scores
are deterministic and exactly assertable.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
from PIL import Image

import capture_import.workflow_obverse_reverse_pairing as pairing_module
from capture_import.workflow_execution import ImportWorkflow
from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
    StageArtifact,
    StageInput,
    StageResult,
)
from capture_import.workflow_obverse_reverse_pairing import (
    OBVERSE_REVERSE_PAIRING_STAGE_ID,
    PAIRING_THRESHOLD,
    ObverseReversePairingStage,
    _build_explanation,
    _color_histogram_similarity,
    _compute_image_metrics,
    _compute_pairing_score,
    _parse_artifact_key,
    _ratio_similarity,
    _require_contained,
)
from capture_import.workflow_pipeline import (
    ProcessingPipeline,
    StageContractError,
    StageExecutionError,
    WorkflowCancelledError,
)

# ---------------------------------------------------------------------------
# Synthetic-image helpers
# ---------------------------------------------------------------------------


def _save_test_jpeg(path: Path, image: np.ndarray, quality: int = 92) -> None:
    """Save an OpenCV BGR image as JPEG."""
    cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, quality])


def _make_uniform_image(
    *,
    width: int = 600,
    height: int = 600,
    color: tuple[int, int, int] = (128, 128, 128),
) -> np.ndarray:
    """Uniform-color image."""
    return np.full((height, width, 3), color, dtype=np.uint8)


def _make_gradient_image(
    *, width: int = 600, height: int = 600, direction: str = "horizontal"
) -> np.ndarray:
    """Smooth gradient image."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    if direction == "horizontal":
        for x in range(width):
            val = int(255 * x / width)
            img[:, x] = (val, val, val)
    else:
        for y in range(height):
            val = int(255 * y / height)
            img[y, :] = (val, val, val)
    return img


def _make_noisy_image(
    *, width: int = 600, height: int = 600, mean: int = 128, std: int = 30
) -> np.ndarray:
    """Noisy grey image with controlled mean and std."""
    noise = np.random.default_rng(42).normal(mean, std, (height, width))
    noise = np.clip(noise, 0, 255).astype(np.uint8)
    return np.stack([noise, noise, noise], axis=-1)


def _make_dark_image(*, width: int = 600, height: int = 600) -> np.ndarray:
    """Dark uniform image."""
    return np.full((height, width, 3), (40, 40, 40), dtype=np.uint8)


def _make_bright_image(*, width: int = 600, height: int = 600) -> np.ndarray:
    """Bright uniform image."""
    return np.full((height, width, 3), (220, 220, 220), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Stage-input builder
# ---------------------------------------------------------------------------


def _build_stage_input(
    *, workspace: Path, artifacts: dict[str, StageArtifact]
) -> StageInput:
    """Build a minimal StageInput for pairing tests."""
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


class ParseArtifactKeyTests(unittest.TestCase):
    def test_cropped_key(self) -> None:
        result = _parse_artifact_key("cropped-coin-1-front")
        self.assertEqual(result, ("cropped", "coin-1", "front"))

    def test_normalized_key(self) -> None:
        result = _parse_artifact_key("normalized-coin-1-reverse")
        self.assertEqual(result, ("normalized", "coin-1", "reverse"))

    def test_unknown_prefix(self) -> None:
        result = _parse_artifact_key("other-coin-1-front")
        self.assertIsNone(result)

    def test_no_hyphen_role(self) -> None:
        result = _parse_artifact_key("normalized-coin1")
        self.assertIsNone(result)


class RatioSimilarityTests(unittest.TestCase):
    def test_equal_values(self) -> None:
        self.assertAlmostEqual(_ratio_similarity(100.0, 100.0), 1.0, places=6)

    def test_different_values(self) -> None:
        self.assertAlmostEqual(_ratio_similarity(100.0, 200.0), 0.5, places=6)

    def test_zero_returns_zero(self) -> None:
        self.assertEqual(_ratio_similarity(0.0, 100.0), 0.0)
        self.assertEqual(_ratio_similarity(100.0, 0.0), 0.0)

    def test_negative_returns_zero(self) -> None:
        self.assertEqual(_ratio_similarity(-10.0, 100.0), 0.0)


class ComputeImageMetricsTests(unittest.TestCase):
    def test_uniform_image(self) -> None:
        img = _make_uniform_image(width=100, height=100, color=(128, 128, 128))
        mean, contrast, aspect, pixels = _compute_image_metrics(img)
        self.assertAlmostEqual(mean, 128.0, places=1)
        self.assertAlmostEqual(contrast, 0.0, places=1)
        self.assertEqual(aspect, 1.0)
        self.assertEqual(pixels, 10000)

    def test_gradient_image(self) -> None:
        img = _make_gradient_image(width=200, height=100)
        mean, contrast, aspect, pixels = _compute_image_metrics(img)
        self.assertGreater(contrast, 50.0)
        self.assertEqual(aspect, 2.0)
        self.assertEqual(pixels, 20000)


class ComputePairingScoreTests(unittest.TestCase):
    def test_identical_images_score_one(self) -> None:
        img = _make_uniform_image(width=600, height=600, color=(128, 128, 128))
        score, dim, aspect, bright, contrast, histogram = _compute_pairing_score(
            img, img
        )
        self.assertAlmostEqual(score, 1.0, places=3)
        self.assertAlmostEqual(dim, 1.0, places=3)
        self.assertAlmostEqual(aspect, 1.0, places=3)
        self.assertAlmostEqual(bright, 1.0, places=3)
        self.assertAlmostEqual(contrast, 1.0, places=3)
        self.assertAlmostEqual(histogram, 1.0, places=3)

    def test_different_sizes_lowers_dim_score(self) -> None:
        front = _make_uniform_image(width=600, height=600)
        reverse = _make_uniform_image(width=300, height=300)
        score, dim, aspect, bright, contrast, histogram = _compute_pairing_score(
            front, reverse
        )
        self.assertAlmostEqual(dim, 0.5, places=3)
        self.assertGreaterEqual(score, 0.0)
        self.assertLess(score, 1.0)

    def test_different_brightness_lowers_score(self) -> None:
        front = _make_dark_image()
        reverse = _make_bright_image()
        score, dim, aspect, bright, contrast, histogram = _compute_pairing_score(
            front, reverse
        )
        self.assertLess(bright, 0.5)
        self.assertLess(score, 1.0)

    def test_different_aspect_ratios_lowers_score(self) -> None:
        front = _make_uniform_image(width=600, height=600)
        reverse = _make_uniform_image(width=600, height=300)
        score, dim, aspect, bright, contrast, histogram = _compute_pairing_score(
            front, reverse
        )
        self.assertLess(aspect, 1.0)
        self.assertGreaterEqual(aspect, 0.4)

    def test_score_bounded(self) -> None:
        front = _make_uniform_image(width=100, height=100, color=(0, 0, 0))
        reverse = _make_uniform_image(
            width=1000, height=1000, color=(255, 255, 255)
        )
        score, *_ = _compute_pairing_score(front, reverse)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_disjoint_equal_luminance_colors_lower_histogram_score(self) -> None:
        front = _make_uniform_image(color=(255, 0, 0))
        reverse = _make_uniform_image(color=(0, 0, 97))
        front_gray = cv2.cvtColor(front, cv2.COLOR_BGR2GRAY)
        reverse_gray = cv2.cvtColor(reverse, cv2.COLOR_BGR2GRAY)
        self.assertEqual(int(front_gray[0, 0]), int(reverse_gray[0, 0]))
        score, _, _, brightness, _, histogram = _compute_pairing_score(
            front, reverse
        )
        self.assertEqual(brightness, 1.0)
        self.assertEqual(histogram, 0.0)
        self.assertLess(score, PAIRING_THRESHOLD)

    def test_similar_color_histograms_score_high(self) -> None:
        front = _make_uniform_image(color=(120, 130, 140))
        reverse = _make_uniform_image(color=(122, 132, 142))
        similarity = _color_histogram_similarity(front, reverse)
        self.assertGreaterEqual(similarity, 0.99)

    def test_histogram_similarity_is_deterministic_and_bounded(self) -> None:
        front = _make_noisy_image()
        reverse = _make_gradient_image()
        first = _color_histogram_similarity(front, reverse)
        second = _color_histogram_similarity(front, reverse)
        self.assertEqual(first, second)
        self.assertGreaterEqual(first, 0.0)
        self.assertLessEqual(first, 1.0)


class BuildExplanationTests(unittest.TestCase):
    def test_paired_explanation(self) -> None:
        text = _build_explanation(True, 0.9, 0.9, 0.9, 0.9, 0.9)
        self.assertIn("plausibly depict", text)
        self.assertIn("dimension=0.90", text)
        self.assertIn("color_histogram=0.90", text)

    def test_not_paired_explanation(self) -> None:
        text = _build_explanation(False, 0.3, 0.3, 0.3, 0.3, 0.3)
        self.assertIn("may not depict", text)


class RequireContainedTests(unittest.TestCase):
    def test_relative_path_passes(self) -> None:
        base = Path("/tmp/workspace")
        path = Path("cropped/coin-1/front.jpg")
        _require_contained(path, base, stage_id="test", label="output")

    def test_dotdot_raises(self) -> None:
        base = Path("/tmp/workspace")
        path = Path("../outside.jpg")
        with self.assertRaises(StageContractError) as ctx:
            _require_contained(path, base, stage_id="test", label="input")
        self.assertIn("parent traversal", str(ctx.exception))

    def test_absolute_raises(self) -> None:
        base = Path("/tmp/workspace")
        path = Path("C:/etc/passwd") if os.name == "nt" else Path("/etc/passwd")
        with self.assertRaises(StageContractError) as ctx:
            _require_contained(path, base, stage_id="test", label="input")
        self.assertIn("absolute", str(ctx.exception))


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

    def test_identical_front_reverse_pairs(self) -> None:
        """Two identical images should score 1.0 and pair."""
        img = _make_uniform_image(width=600, height=600, color=(128, 128, 128))
        for role in ("front", "reverse"):
            path = self.workspace / "normalized" / "coin-1" / f"{role}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            _save_test_jpeg(path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-1-reverse": StageArtifact(
                    relative_path="normalized/coin-1/reverse.jpg",
                    content_type="image/jpeg",
                ),
            },
        )
        stage = ObverseReversePairingStage()
        result = stage.execute(stage_input)

        self.assertEqual(result.artifacts, {})
        records = result.metadata["pairing_records"]
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["coin_id"], "coin-1")
        self.assertTrue(rec["paired"])
        self.assertAlmostEqual(rec["consistency_score"], 1.0, places=3)
        self.assertEqual(rec["front_width"], 600)
        self.assertEqual(rec["reverse_width"], 600)

    def test_mismatched_sizes_do_not_pair(self) -> None:
        """Very different sizes and brightness should produce a low score."""
        front = _make_uniform_image(width=600, height=600)
        reverse = _make_uniform_image(width=200, height=100, color=(255, 255, 255))
        for role, img in (("front", front), ("reverse", reverse)):
            path = self.workspace / "normalized" / "coin-1" / f"{role}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            _save_test_jpeg(path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-1-reverse": StageArtifact(
                    relative_path="normalized/coin-1/reverse.jpg",
                    content_type="image/jpeg",
                ),
            },
        )
        stage = ObverseReversePairingStage()
        result = stage.execute(stage_input)

        rec = result.metadata["pairing_records"][0]
        self.assertFalse(rec["paired"])
        self.assertLess(rec["consistency_score"], PAIRING_THRESHOLD)

    def test_multiple_coins(self) -> None:
        """Two coins, one pairs, one does not."""
        # Coin A: identical front/reverse -> pairs
        img_a = _make_uniform_image(width=600, height=600)
        for role in ("front", "reverse"):
            path = self.workspace / "normalized" / "coin-a" / f"{role}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            _save_test_jpeg(path, img_a)

        # Coin B: very different size and brightness -> does not pair
        front_b = _make_uniform_image(width=600, height=600)
        reverse_b = _make_uniform_image(width=200, height=100, color=(255, 255, 255))
        for role, img in (("front", front_b), ("reverse", reverse_b)):
            path = self.workspace / "normalized" / "coin-b" / f"{role}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            _save_test_jpeg(path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-a-front": StageArtifact(
                    relative_path="normalized/coin-a/front.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-a-reverse": StageArtifact(
                    relative_path="normalized/coin-a/reverse.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-b-front": StageArtifact(
                    relative_path="normalized/coin-b/front.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-b-reverse": StageArtifact(
                    relative_path="normalized/coin-b/reverse.jpg",
                    content_type="image/jpeg",
                ),
            },
        )
        stage = ObverseReversePairingStage()
        result = stage.execute(stage_input)

        self.assertEqual(result.metadata["total_coin_count"], 2)
        self.assertEqual(result.metadata["paired_coin_count"], 1)
        by_id = {r["coin_id"]: r for r in result.metadata["pairing_records"]}
        self.assertTrue(by_id["coin-a"]["paired"])
        self.assertFalse(by_id["coin-b"]["paired"])

    def test_prefers_cropped_over_normalized(self) -> None:
        """When both cropped and normalized exist, cropped is used."""
        img = _make_uniform_image(width=600, height=600)
        for role in ("front", "reverse"):
            # Write cropped version
            path = self.workspace / "cropped" / "coin-1" / f"{role}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            _save_test_jpeg(path, img)
            # Write normalized version (different size to detect which is used)
            norm_path = self.workspace / "normalized" / "coin-1" / f"{role}.jpg"
            norm_path.parent.mkdir(parents=True, exist_ok=True)
            _save_test_jpeg(
                norm_path, _make_uniform_image(width=300, height=300)
            )

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "cropped-coin-1-front": StageArtifact(
                    relative_path="cropped/coin-1/front.jpg",
                    content_type="image/jpeg",
                ),
                "cropped-coin-1-reverse": StageArtifact(
                    relative_path="cropped/coin-1/reverse.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-1-reverse": StageArtifact(
                    relative_path="normalized/coin-1/reverse.jpg",
                    content_type="image/jpeg",
                ),
            },
        )
        stage = ObverseReversePairingStage()
        result = stage.execute(stage_input)

        rec = result.metadata["pairing_records"][0]
        # Should use cropped (600x600), not normalized (300x300)
        self.assertEqual(rec["front_width"], 600)
        self.assertEqual(rec["reverse_width"], 600)

    def test_deterministic_ordering(self) -> None:
        """Records are ordered by coin_id."""
        for coin_id in ("coin-z", "coin-a"):
            img = _make_uniform_image(width=600, height=600)
            for role in ("front", "reverse"):
                path = self.workspace / "normalized" / coin_id / f"{role}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                _save_test_jpeg(path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                f"normalized-{coin_id}-{role}": StageArtifact(
                    relative_path=f"normalized/{coin_id}/{role}.jpg",
                    content_type="image/jpeg",
                )
                for coin_id in ("coin-z", "coin-a")
                for role in ("front", "reverse")
            },
        )
        stage = ObverseReversePairingStage()
        result = stage.execute(stage_input)

        coin_ids = [r["coin_id"] for r in result.metadata["pairing_records"]]
        self.assertEqual(coin_ids, ["coin-a", "coin-z"])

    def test_edge_ignored(self) -> None:
        """Edge images are ignored; only front and reverse matter."""
        img = _make_uniform_image(width=600, height=600)
        for role in ("front", "reverse"):
            path = self.workspace / "normalized" / "coin-1" / f"{role}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            _save_test_jpeg(path, img)
        # Add edge image
        edge_path = self.workspace / "normalized" / "coin-1" / "edge.jpg"
        edge_path.parent.mkdir(parents=True, exist_ok=True)
        _save_test_jpeg(edge_path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-1-reverse": StageArtifact(
                    relative_path="normalized/coin-1/reverse.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-1-edge": StageArtifact(
                    relative_path="normalized/coin-1/edge.jpg",
                    content_type="image/jpeg",
                ),
            },
        )
        stage = ObverseReversePairingStage()
        result = stage.execute(stage_input)

        self.assertEqual(result.metadata["total_coin_count"], 1)


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

    def test_no_eligible_artifacts_raises(self) -> None:
        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "other": StageArtifact(relative_path="x", content_type="text/plain")
            },
        )
        stage = ObverseReversePairingStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, OBVERSE_REVERSE_PAIRING_STAGE_ID)

    def test_missing_reverse_raises(self) -> None:
        img = _make_uniform_image(width=600, height=600)
        path = self.workspace / "normalized" / "coin-1" / "front.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        _save_test_jpeg(path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                )
            },
        )
        stage = ObverseReversePairingStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertIn("missing", str(ctx.exception).lower())

    def test_missing_front_raises(self) -> None:
        img = _make_uniform_image(width=600, height=600)
        path = self.workspace / "normalized" / "coin-1" / "reverse.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        _save_test_jpeg(path, img)

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-reverse": StageArtifact(
                    relative_path="normalized/coin-1/reverse.jpg",
                    content_type="image/jpeg",
                )
            },
        )
        stage = ObverseReversePairingStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertIn("missing", str(ctx.exception).lower())

    def test_missing_file_raises(self) -> None:
        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-1-reverse": StageArtifact(
                    relative_path="normalized/coin-1/reverse.jpg",
                    content_type="image/jpeg",
                ),
            },
        )
        stage = ObverseReversePairingStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, OBVERSE_REVERSE_PAIRING_STAGE_ID)

    def test_corrupt_image_raises(self) -> None:
        for role in ("front", "reverse"):
            bad = self.workspace / "normalized" / "coin-1" / f"{role}.jpg"
            bad.parent.mkdir(parents=True, exist_ok=True)
            bad.write_bytes(b"not an image")

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="normalized/coin-1/front.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-1-reverse": StageArtifact(
                    relative_path="normalized/coin-1/reverse.jpg",
                    content_type="image/jpeg",
                ),
            },
        )
        stage = ObverseReversePairingStage()
        with self.assertRaises(StageExecutionError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, OBVERSE_REVERSE_PAIRING_STAGE_ID)

    def test_path_escape_raises(self) -> None:
        outside = self.workspace.parent / "outside.jpg"
        outside.write_bytes(b"fake")

        stage_input = _build_stage_input(
            workspace=self.workspace,
            artifacts={
                "normalized-coin-1-front": StageArtifact(
                    relative_path="../outside.jpg",
                    content_type="image/jpeg",
                ),
                "normalized-coin-1-reverse": StageArtifact(
                    relative_path="normalized/coin-1/reverse.jpg",
                    content_type="image/jpeg",
                ),
            },
        )
        stage = ObverseReversePairingStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertIn("traversal", str(ctx.exception).lower())

    def _write_valid_pair(
        self,
        *,
        front_name: str = "front.jpg",
        reverse_name: str = "reverse.jpg",
    ) -> dict[str, StageArtifact]:
        image = _make_uniform_image(width=200, height=200)
        directory = self.workspace / "normalized" / "coin-1"
        directory.mkdir(parents=True, exist_ok=True)
        _save_test_jpeg(directory / front_name, image)
        _save_test_jpeg(directory / reverse_name, image)
        return {
            "normalized-coin-1-front": StageArtifact(
                relative_path=f"normalized/coin-1/{front_name}",
                content_type="image/jpeg",
            ),
            "normalized-coin-1-reverse": StageArtifact(
                relative_path=f"normalized/coin-1/{reverse_name}",
                content_type="image/jpeg",
            ),
        }

    def test_declared_mime_mismatch_raises_before_decode(self) -> None:
        artifacts = self._write_valid_pair()
        artifacts["normalized-coin-1-front"] = StageArtifact(
            relative_path="normalized/coin-1/front.jpg",
            content_type="image/png",
        )
        with (
            mock.patch.object(pairing_module.cv2, "imdecode") as decode,
            self.assertRaises(StageContractError),
        ):
            ObverseReversePairingStage().execute(
                _build_stage_input(workspace=self.workspace, artifacts=artifacts)
            )
        decode.assert_not_called()

    def test_extension_mismatch_raises_before_decode(self) -> None:
        artifacts = self._write_valid_pair()
        front_jpg = self.workspace / "normalized" / "coin-1" / "front.jpg"
        front_png = front_jpg.with_suffix(".png")
        front_jpg.replace(front_png)
        artifacts["normalized-coin-1-front"] = StageArtifact(
            relative_path="normalized/coin-1/front.png",
            content_type="image/jpeg",
        )
        with (
            mock.patch.object(pairing_module.cv2, "imdecode") as decode,
            self.assertRaises(StageContractError),
        ):
            ObverseReversePairingStage().execute(
                _build_stage_input(workspace=self.workspace, artifacts=artifacts)
            )
        decode.assert_not_called()

    def test_unsupported_decodable_format_raises_before_decode(self) -> None:
        artifacts = self._write_valid_pair()
        front_path = self.workspace / "normalized" / "coin-1" / "front.jpg"
        Image.new("RGB", (20, 20), "red").save(front_path, format="BMP")
        with (
            mock.patch.object(pairing_module.cv2, "imdecode") as decode,
            self.assertRaises(StageContractError),
        ):
            ObverseReversePairingStage().execute(
                _build_stage_input(workspace=self.workspace, artifacts=artifacts)
            )
        decode.assert_not_called()

    def test_file_size_limit_is_enforced_before_decode(self) -> None:
        artifacts = self._write_valid_pair()
        front_path = self.workspace / "normalized" / "coin-1" / "front.jpg"
        with (
            mock.patch.object(
                pairing_module, "MAX_IMAGE_SIZE", front_path.stat().st_size - 1
            ),
            mock.patch.object(pairing_module.cv2, "imdecode") as decode,
            self.assertRaises(StageContractError),
        ):
            ObverseReversePairingStage().execute(
                _build_stage_input(workspace=self.workspace, artifacts=artifacts)
            )
        decode.assert_not_called()

    def test_dimension_limit_is_enforced_before_decode(self) -> None:
        artifacts = self._write_valid_pair()
        with (
            mock.patch.object(pairing_module, "MAX_IMAGE_DIMENSION", 199),
            mock.patch.object(pairing_module.cv2, "imdecode") as decode,
            self.assertRaises(StageContractError),
        ):
            ObverseReversePairingStage().execute(
                _build_stage_input(workspace=self.workspace, artifacts=artifacts)
            )
        decode.assert_not_called()

    def test_pixel_limit_is_enforced_before_decode(self) -> None:
        artifacts = self._write_valid_pair()
        with (
            mock.patch.object(pairing_module, "MAX_IMAGE_PIXELS", 39_999),
            mock.patch.object(pairing_module.cv2, "imdecode") as decode,
            self.assertRaises(StageContractError),
        ):
            ObverseReversePairingStage().execute(
                _build_stage_input(workspace=self.workspace, artifacts=artifacts)
            )
        decode.assert_not_called()

    def test_exact_resource_boundaries_are_accepted(self) -> None:
        artifacts = self._write_valid_pair()
        front_path = self.workspace / "normalized" / "coin-1" / "front.jpg"
        with (
            mock.patch.object(
                pairing_module, "MAX_IMAGE_SIZE", front_path.stat().st_size
            ),
            mock.patch.object(pairing_module, "MAX_IMAGE_DIMENSION", 200),
            mock.patch.object(pairing_module, "MAX_IMAGE_PIXELS", 40_000),
        ):
            result = ObverseReversePairingStage().execute(
                _build_stage_input(workspace=self.workspace, artifacts=artifacts)
            )
        self.assertEqual(result.metadata["total_coin_count"], 1)

    def test_symlink_artifact_is_rejected(self) -> None:
        artifacts = self._write_valid_pair()
        front_path = self.workspace / "normalized" / "coin-1" / "front.jpg"
        outside = self.tmp / "outside.jpg"
        _save_test_jpeg(outside, _make_uniform_image(width=200, height=200))
        front_path.unlink()
        try:
            front_path.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        try:
            with self.assertRaises(StageContractError):
                ObverseReversePairingStage().execute(
                    _build_stage_input(workspace=self.workspace, artifacts=artifacts)
                )
        finally:
            front_path.unlink(missing_ok=True)

    @unittest.skipIf(os.name == "nt", "POSIX pathname replacement semantics")
    def test_replacement_after_verified_open_is_rejected(self) -> None:
        artifacts = self._write_valid_pair()
        original_open = pairing_module._open_artifact_readonly
        replacement = self.tmp / "replacement.jpg"
        _save_test_jpeg(replacement, _make_uniform_image(width=200, height=200))

        def replace_after_open(path: Path):
            handle = original_open(path)
            if path.name == "front.jpg":
                os.replace(replacement, path)
            return handle

        with (
            mock.patch.object(
                pairing_module,
                "_open_artifact_readonly",
                side_effect=replace_after_open,
            ),
            self.assertRaises(StageContractError),
        ):
            ObverseReversePairingStage().execute(
                _build_stage_input(workspace=self.workspace, artifacts=artifacts)
            )


class PipelineIntegrationTests(unittest.TestCase):
    def test_stage_conforms_to_protocol(self) -> None:
        stage = ObverseReversePairingStage()
        self.assertEqual(stage.stage_id, OBVERSE_REVERSE_PAIRING_STAGE_ID)
        self.assertTrue(callable(stage.execute))

    def test_stage_in_pipeline(self) -> None:
        from capture_import.workflow_crop_detection import CropDetectionStage
        from capture_import.workflow_image_normalization import (
            ImageNormalizationStage,
        )
        from capture_import.workflow_image_quality import ImageQualityScoringStage

        pipeline = ProcessingPipeline(
            stages=(
                ImageNormalizationStage(),
                ImageQualityScoringStage(),
                CropDetectionStage(),
                ObverseReversePairingStage(),
            )
        )
        self.assertIn(OBVERSE_REVERSE_PAIRING_STAGE_ID, pipeline.stage_ids)

    def test_repeated_execution_and_artifact_order_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            image = _make_noisy_image(width=200, height=200)
            for role in ("front", "reverse"):
                path = workspace / "normalized" / "coin-1" / f"{role}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                _save_test_jpeg(path, image)
            artifacts = {
                f"normalized-coin-1-{role}": StageArtifact(
                    relative_path=f"normalized/coin-1/{role}.jpg",
                    content_type="image/jpeg",
                )
                for role in ("front", "reverse")
            }
            stage = ObverseReversePairingStage()
            first = stage.execute(
                _build_stage_input(workspace=workspace, artifacts=artifacts)
            )
            second = stage.execute(
                _build_stage_input(
                    workspace=workspace,
                    artifacts=dict(reversed(tuple(artifacts.items()))),
                )
            )
            self.assertEqual(first.metadata, second.metadata)

    def test_cancellation_after_pairing_prevents_transaction_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            image = _make_uniform_image(width=200, height=200)
            for role in ("front", "reverse"):
                path = workspace / "normalized" / "coin-1" / f"{role}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                _save_test_jpeg(path, image)
            artifacts = {
                f"normalized-coin-1-{role}": StageArtifact(
                    relative_path=f"normalized/coin-1/{role}.jpg",
                    content_type="image/jpeg",
                )
                for role in ("front", "reverse")
            }

            class ArtifactFeeder:
                stage_id = "artifact-feeder"

                def execute(self, stage_input: StageInput) -> StageResult:
                    return StageResult(artifacts=artifacts, metadata={})

            checks = {"count": 0}
            transaction_calls: list[object] = []

            def is_cancelled() -> bool:
                checks["count"] += 1
                return checks["count"] >= 4

            workflow = ImportWorkflow(
                ProcessingPipeline(
                    stages=(ArtifactFeeder(), ObverseReversePairingStage())
                ),
                is_cancelled=is_cancelled,
            )
            request = _build_stage_input(
                workspace=workspace,
                artifacts={},
            ).request
            with self.assertRaises(WorkflowCancelledError):
                workflow.execute(
                    request,
                    workspace,
                    transaction=transaction_calls.append,
                )
            self.assertEqual(transaction_calls, [])


if __name__ == "__main__":
    unittest.main()
