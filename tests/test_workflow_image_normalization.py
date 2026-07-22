"""Focused tests for Sprint 8 Unit 2: ImageNormalizationStage."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import warnings
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image
from PIL.ExifTags import Base

from capture_import.limits import MAX_IMAGE_DIMENSION
from capture_import.workflow_image_normalization import (
    IMAGE_NORMALIZATION_STAGE_ID,
    ImageNormalizationStage,
    _role_filename,
)
from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
    StageArtifact,
    StageInput,
    StageResult,
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


def _make_test_image(
    *,
    mode: str = "RGB",
    width: int = 640,
    height: int = 480,
    color: tuple[int, int, int] = (128, 64, 32),
    format: str = "JPEG",
    exif: bytes | None = None,
) -> bytes:
    """Generate a small in-memory test image."""
    buf = BytesIO()
    image = Image.new(mode, (width, height), color)
    save_kwargs: dict = {}
    if format == "JPEG":
        save_kwargs["quality"] = 85
    if exif is not None:
        save_kwargs["exif"] = exif
    image.save(buf, format=format, **save_kwargs)
    return buf.getvalue()


def _make_test_png(*, width: int = 640, height: int = 480) -> bytes:
    """Generate a small in-memory PNG test image."""
    return _make_test_image(
        mode="RGBA",
        width=width,
        height=height,
        color=(128, 64, 32, 255),
        format="PNG",
    )


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
                        "mime_type": (
                            "image/jpeg" if path.endswith(".jpg") else "image/png"
                        ),
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


def _make_stage_input(
    *,
    source: Path,
    workspace: Path,
    manifest: dict | None = None,
) -> StageInput:
    """Construct a StageInput with a prepared manifest in the workspace."""
    if manifest is not None:
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
    else:
        artifacts = {}

    return StageInput(
        request=ImportRequest(
            source=source,
            collection_id="collection-1",
            configuration=ImportConfiguration(),
        ),
        workspace=workspace,
        artifacts=artifacts,
    )


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


class RoleFilenameTests(unittest.TestCase):
    def test_known_roles(self) -> None:
        self.assertEqual(_role_filename("front"), "front")
        self.assertEqual(_role_filename("reverse"), "reverse")
        self.assertEqual(_role_filename("edge"), "edge")

    def test_unknown_role_fallback(self) -> None:
        self.assertEqual(_role_filename("oblique"), "oblique")


class ValidNormalizationTests(unittest.TestCase):
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

    def test_single_jpeg_normalized(self) -> None:
        image_bytes = _make_test_image(width=640, height=480, color=(200, 100, 50))
        manifest = _build_manifest(
            coin_id="coin-1", photos={"front": "images/coin-1-front.jpg"}
        )
        _build_package_zip(
            path=self.source,
            manifest=manifest,
            images={"images/coin-1-front.jpg": image_bytes},
        )
        stage_input = _make_stage_input(
            source=self.source,
            workspace=self.workspace,
            manifest=manifest,
        )
        stage = ImageNormalizationStage()
        result = stage.execute(stage_input)

        self.assertIsInstance(result, StageResult)
        self.assertIn("normalized-coin-1-front", result.artifacts)
        artifact = result.artifacts["normalized-coin-1-front"]
        self.assertEqual(artifact.relative_path, "normalized/coin-1/front.jpg")
        self.assertEqual(artifact.content_type, "image/jpeg")

        # Verify the file exists and is a valid JPEG.
        output_path = self.workspace / artifact.relative_path
        self.assertTrue(output_path.exists())
        with Image.open(output_path) as img:
            self.assertEqual(img.format, "JPEG")
            self.assertEqual(img.mode, "RGB")

        # Verify metadata.
        self.assertEqual(result.metadata.get("normalized_image_count"), 1)
        dims = result.metadata.get("normalized_dimensions", {})
        self.assertIn("coin-1/front", dims)
        self.assertIn("width", dims["coin-1/front"])
        self.assertIn("height", dims["coin-1/front"])

    def test_png_converted_to_jpeg(self) -> None:
        png_bytes = _make_test_png(width=400, height=300)
        manifest = _build_manifest(
            coin_id="coin-1", photos={"front": "images/coin-1-front.png"}
        )
        # Patch mime_type in manifest for PNG.
        manifest["coins"][0]["photos"]["front"]["mime_type"] = "image/png"
        _build_package_zip(
            path=self.source,
            manifest=manifest,
            images={"images/coin-1-front.png": png_bytes},
        )
        stage_input = _make_stage_input(
            source=self.source, workspace=self.workspace, manifest=manifest
        )
        stage = ImageNormalizationStage()
        result = stage.execute(stage_input)

        artifact = result.artifacts["normalized-coin-1-front"]
        output_path = self.workspace / artifact.relative_path
        with Image.open(output_path) as img:
            self.assertEqual(img.format, "JPEG")
            self.assertEqual(img.mode, "RGB")

    def test_multiple_roles_per_coin(self) -> None:
        front = _make_test_image(width=300, height=200, color=(255, 0, 0))
        reverse = _make_test_image(width=300, height=200, color=(0, 255, 0))
        manifest = _build_manifest(
            coin_id="coin-1",
            photos={
                "front": "images/front.jpg",
                "reverse": "images/reverse.jpg",
            },
        )
        _build_package_zip(
            path=self.source,
            manifest=manifest,
            images={
                "images/front.jpg": front,
                "images/reverse.jpg": reverse,
            },
        )
        stage_input = _make_stage_input(
            source=self.source, workspace=self.workspace, manifest=manifest
        )
        stage = ImageNormalizationStage()
        result = stage.execute(stage_input)

        self.assertEqual(result.metadata.get("normalized_image_count"), 2)
        self.assertIn("normalized-coin-1-front", result.artifacts)
        self.assertIn("normalized-coin-1-reverse", result.artifacts)

    def test_multiple_coins(self) -> None:
        manifest = _build_manifest(coin_id="coin-1", photos={"front": "images/a.jpg"})
        # Add a second coin.
        manifest["coins"].append(
            {
                "id": "coin-2",
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
        _build_package_zip(
            path=self.source,
            manifest=manifest,
            images={
                "images/a.jpg": _make_test_image(color=(255, 0, 0)),
                "images/b.jpg": _make_test_image(color=(0, 0, 255)),
            },
        )
        stage_input = _make_stage_input(
            source=self.source, workspace=self.workspace, manifest=manifest
        )
        stage = ImageNormalizationStage()
        result = stage.execute(stage_input)

        self.assertEqual(result.metadata.get("normalized_image_count"), 2)
        self.assertIn("normalized-coin-1-front", result.artifacts)
        self.assertIn("normalized-coin-2-front", result.artifacts)

    def test_exif_is_stripped(self) -> None:
        # Create an image with EXIF data.
        buf = BytesIO()
        image = Image.new("RGB", (100, 100), (128, 128, 128))
        exif = Image.Exif()
        exif[Base.ImageDescription] = "Test Coin"
        image.save(buf, format="JPEG", quality=85, exif=exif.tobytes())
        image_bytes = buf.getvalue()

        manifest = _build_manifest(
            coin_id="coin-1", photos={"front": "images/front.jpg"}
        )
        _build_package_zip(
            path=self.source,
            manifest=manifest,
            images={"images/front.jpg": image_bytes},
        )
        stage_input = _make_stage_input(
            source=self.source, workspace=self.workspace, manifest=manifest
        )
        stage = ImageNormalizationStage()
        result = stage.execute(stage_input)

        artifact = result.artifacts["normalized-coin-1-front"]
        output_path = self.workspace / artifact.relative_path
        with Image.open(output_path) as img:
            # EXIF should be stripped (None or empty).
            exif_data = img.info.get("exif")
            self.assertTrue(
                exif_data is None or len(exif_data) == 0,
                f"EXIF data present: {exif_data!r}",
            )

    def test_dimension_capping(self) -> None:
        # Create an oversized image.
        oversize = MAX_IMAGE_DIMENSION + 500
        image_bytes = _make_test_image(width=oversize, height=oversize)
        manifest = _build_manifest(coin_id="coin-1", photos={"front": "images/big.jpg"})
        _build_package_zip(
            path=self.source,
            manifest=manifest,
            images={"images/big.jpg": image_bytes},
        )
        stage_input = _make_stage_input(
            source=self.source, workspace=self.workspace, manifest=manifest
        )
        stage = ImageNormalizationStage(max_dimension=MAX_IMAGE_DIMENSION)
        result = stage.execute(stage_input)

        dims = result.metadata["normalized_dimensions"]["coin-1/front"]
        max_dim = max(dims["width"], dims["height"])
        self.assertLessEqual(max_dim, MAX_IMAGE_DIMENSION)

    def test_oversized_image_no_decompression_warning(self) -> None:
        """DecompressionBombWarning must be suppressed during normalization.

        The stage intentionally resizes oversized images, so Pillow's
        warning about decompression bombs is expected noise.  The
        DecompressionBombError (hard limit) is still fatal and caught
        separately.
        """
        oversize = MAX_IMAGE_DIMENSION + 500
        image_bytes = _make_test_image(width=oversize, height=oversize)
        manifest = _build_manifest(coin_id="coin-1", photos={"front": "images/big.jpg"})
        _build_package_zip(
            path=self.source,
            manifest=manifest,
            images={"images/big.jpg": image_bytes},
        )
        stage_input = _make_stage_input(
            source=self.source, workspace=self.workspace, manifest=manifest
        )
        stage = ImageNormalizationStage()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = stage.execute(stage_input)
            # No DecompressionBombWarning should have been emitted.
            bomb_warnings = [
                warning
                for warning in w
                if issubclass(warning.category, Image.DecompressionBombWarning)
            ]
            self.assertEqual(
                len(bomb_warnings),
                0,
                f"Unexpected DecompressionBombWarning: {bomb_warnings}",
            )
        self.assertEqual(result.metadata.get("normalized_image_count"), 1)


class FailureModeTests(unittest.TestCase):
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

    def test_missing_manifest_artifact_raises_contract_error(self) -> None:
        stage_input = _make_stage_input(
            source=self.source, workspace=self.workspace, manifest=None
        )
        stage = ImageNormalizationStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, IMAGE_NORMALIZATION_STAGE_ID)
        self.assertIn("prepared-manifest", str(ctx.exception))

    def test_missing_image_in_archive_raises_execution_error(self) -> None:
        manifest = _build_manifest(
            coin_id="coin-1", photos={"front": "images/missing.jpg"}
        )
        _build_package_zip(
            path=self.source,
            manifest=manifest,
            images={},  # No images included.
        )
        stage_input = _make_stage_input(
            source=self.source, workspace=self.workspace, manifest=manifest
        )
        stage = ImageNormalizationStage()
        with self.assertRaises(StageExecutionError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, IMAGE_NORMALIZATION_STAGE_ID)
        self.assertIn("missing", str(ctx.exception).lower())

    def test_corrupt_image_raises_execution_error(self) -> None:
        manifest = _build_manifest(coin_id="coin-1", photos={"front": "images/bad.jpg"})
        _build_package_zip(
            path=self.source,
            manifest=manifest,
            images={"images/bad.jpg": b"not an image"},
        )
        stage_input = _make_stage_input(
            source=self.source, workspace=self.workspace, manifest=manifest
        )
        stage = ImageNormalizationStage()
        with self.assertRaises(StageExecutionError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, IMAGE_NORMALIZATION_STAGE_ID)

    def test_invalid_manifest_json_raises_contract_error(self) -> None:
        manifest_path = self.workspace / PREPARED_MANIFEST_NAME
        manifest_path.write_bytes(b"not json")
        artifacts = {
            PREPARED_MANIFEST_ARTIFACT: StageArtifact(
                relative_path=PREPARED_MANIFEST_NAME,
                content_type="application/json",
            )
        }
        stage_input = StageInput(
            request=ImportRequest(
                source=self.source,
                collection_id="collection-1",
                configuration=ImportConfiguration(),
            ),
            workspace=self.workspace,
            artifacts=artifacts,
        )
        stage = ImageNormalizationStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, IMAGE_NORMALIZATION_STAGE_ID)

    def test_coin_id_with_parent_traversal_raises_contract_error(self) -> None:
        manifest = _build_manifest(coin_id="..", photos={"front": "images/front.jpg"})
        _build_package_zip(
            path=self.source,
            manifest=manifest,
            images={"images/front.jpg": _make_test_image()},
        )
        stage_input = _make_stage_input(
            source=self.source, workspace=self.workspace, manifest=manifest
        )
        stage = ImageNormalizationStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, IMAGE_NORMALIZATION_STAGE_ID)
        self.assertIn("unsafe", str(ctx.exception).lower())

    def test_coin_id_with_path_separator_raises_contract_error(self) -> None:
        manifest = _build_manifest(coin_id="a/b", photos={"front": "images/front.jpg"})
        _build_package_zip(
            path=self.source,
            manifest=manifest,
            images={"images/front.jpg": _make_test_image()},
        )
        stage_input = _make_stage_input(
            source=self.source, workspace=self.workspace, manifest=manifest
        )
        stage = ImageNormalizationStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, IMAGE_NORMALIZATION_STAGE_ID)

    def test_coin_id_empty_raises_contract_error(self) -> None:
        manifest = _build_manifest(coin_id="", photos={"front": "images/front.jpg"})
        # Empty coin_id fails the 'not coin_id' check before _validate_coin_id.
        # This test confirms the early validation path.
        _build_package_zip(
            path=self.source,
            manifest=manifest,
            images={"images/front.jpg": _make_test_image()},
        )
        stage_input = _make_stage_input(
            source=self.source, workspace=self.workspace, manifest=manifest
        )
        stage = ImageNormalizationStage()
        with self.assertRaises(StageContractError) as ctx:
            stage.execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, IMAGE_NORMALIZATION_STAGE_ID)


class PipelineIntegrationTests(unittest.TestCase):
    def test_stage_conforms_to_protocol(self) -> None:
        stage = ImageNormalizationStage()
        self.assertEqual(stage.stage_id, IMAGE_NORMALIZATION_STAGE_ID)
        self.assertTrue(callable(stage.execute))

    def test_stage_in_pipeline(self) -> None:

        pipeline = ProcessingPipeline(stages=(ImageNormalizationStage(),))
        self.assertEqual(pipeline.stage_ids, (IMAGE_NORMALIZATION_STAGE_ID,))


if __name__ == "__main__":
    unittest.main()
