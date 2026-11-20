"""Synthetic EXIF pixel-orientation regressions; no private photographs."""

from __future__ import annotations

import struct
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from capture_import.workflow_crop_detection import CropDetectionStage
from capture_import.workflow_image_normalization import ImageNormalizationStage
from capture_import.workflow_models import StageInput
from capture_import.workflow_obverse_reverse_pairing import ObverseReversePairingStage
from capture_import.workflow_pipeline import StageExecutionError
from tests.test_workflow_image_normalization import (
    _build_manifest,
    _build_package_zip,
    _make_stage_input,
)

# Hand-derived label grids for the EXIF display transformations. Each cell is
# a large solid block, so JPEG error is measured away from block boundaries.
_RAW_GRID = ("ABC", "DEF")
_ORIENTED_GRIDS = {
    1: ("ABC", "DEF"),
    2: ("CBA", "FED"),
    3: ("FED", "CBA"),
    4: ("DEF", "ABC"),
    5: ("AD", "BE", "CF"),
    6: ("DA", "EB", "FC"),
    7: ("FC", "EB", "DA"),
    8: ("CF", "BE", "AD"),
}
_COLORS = {
    "A": (220, 30, 30),
    "B": (30, 200, 30),
    "C": (30, 30, 220),
    "D": (220, 200, 30),
    "E": (200, 30, 200),
    "F": (30, 200, 200),
}
_CELL = 32


def _pattern_payload(orientation=None, *, format="PNG", raw_exif=None):
    image = Image.new("RGB", (96, 64))
    draw = ImageDraw.Draw(image)
    for y, row in enumerate(_RAW_GRID):
        for x, label in enumerate(row):
            draw.rectangle(
                (x * _CELL, y * _CELL, (x + 1) * _CELL - 1, (y + 1) * _CELL - 1),
                fill=_COLORS[label],
            )
    exif = Image.Exif()
    exif[270] = "Synthetic private metadata must be stripped"
    if orientation is not None:
        exif[274] = orientation
    buffer = BytesIO()
    image.save(buffer, format=format, exif=raw_exif or exif.tobytes())
    return buffer.getvalue()


class ExifOrientationTests(unittest.TestCase):
    def assert_grid(self, payload, grid, *, cell=_CELL):
        with Image.open(BytesIO(payload)) as output:
            self.assertEqual(output.format, "JPEG")
            self.assertEqual(output.mode, "RGB")
            self.assertEqual(output.size, (len(grid[0]) * cell, len(grid) * cell))
            self.assertFalse(output.getexif())
            self.assertNotIn("exif", output.info)
            self.assertFalse(output.info.get("progressive", False))
            for y, row in enumerate(grid):
                for x, label in enumerate(row):
                    # Multiple off-centre samples detect misplaced/mirrored cells.
                    for dx, dy in ((8, 8), (20, 12), (12, 24)):
                        point = (
                            x * cell + dx * cell // _CELL,
                            y * cell + dy * cell // _CELL,
                        )
                        actual = output.getpixel(point)
                        self.assertLessEqual(
                            max(abs(a - b) for a, b in zip(actual, _COLORS[label])),
                            12,
                            (point, label, actual),
                        )

    def test_all_eight_orientations_place_pixels_and_strip_exif(self):
        stage = ImageNormalizationStage()
        for format in ("JPEG", "PNG"):
            for orientation, grid in _ORIENTED_GRIDS.items():
                with self.subTest(format=format, orientation=orientation):
                    source = _pattern_payload(orientation, format=format)
                    output, width, height = stage._normalize_image(source)
                    self.assertEqual(
                        (width, height), (len(grid[0]) * _CELL, len(grid) * _CELL)
                    )
                    self.assert_grid(output, grid)
                    self.assertEqual(stage._normalize_image(source)[0], output)

    def test_missing_and_identity_orientation_do_not_change_pixels(self):
        stage = ImageNormalizationStage()
        missing = stage._normalize_image(_pattern_payload())[0]
        identity = stage._normalize_image(_pattern_payload(1))[0]
        self.assertEqual(missing, identity)
        self.assert_grid(missing, _RAW_GRID)
        # Also exercise a source with no EXIF block at all.
        with Image.open(BytesIO(_pattern_payload())) as image:
            buffer = BytesIO()
            image.save(buffer, format="PNG")
        self.assertEqual(stage._normalize_image(buffer.getvalue())[0], missing)

    def test_unsupported_orientation_leaves_pixels_unchanged(self):
        for orientation in (0, 9, 65535):
            with self.subTest(orientation=orientation):
                output = ImageNormalizationStage()._normalize_image(
                    _pattern_payload(orientation)
                )[0]
                self.assert_grid(output, _RAW_GRID)

    def test_wrong_type_orientation_is_not_interpreted_as_valid(self):
        # A syntactically valid TIFF IFD with ASCII rather than SHORT orientation.
        raw_exif = (
            b"Exif\x00\x00II"
            + struct.pack("<HIH", 42, 8, 1)
            + struct.pack("<HHI4sI", 274, 2, 2, b"6\x00\x00\x00", 0)
        )
        output = ImageNormalizationStage()._normalize_image(
            _pattern_payload(raw_exif=raw_exif)
        )[0]
        self.assert_grid(output, _RAW_GRID)

    def test_malformed_exif_fails_with_stage_execution_error(self):
        for raw_exif in (b"Exif\x00\x00invalid TIFF header", b"Exif\x00\x00II*\x00"):
            with self.subTest(raw_exif=raw_exif):
                payload = _pattern_payload(raw_exif=raw_exif)
                with self.assertRaises(StageExecutionError) as caught:
                    ImageNormalizationStage()._normalize_image(payload)
                self.assertEqual(caught.exception.stage_id, "image-normalization")

    def test_rotation_precedes_dimension_cap(self):
        output, width, height = ImageNormalizationStage(
            max_dimension=48
        )._normalize_image(_pattern_payload(6))
        self.assertEqual((width, height), (32, 48))
        self.assert_grid(output, _ORIENTED_GRIDS[6], cell=16)

    def test_reprocessing_normalized_output_does_not_rotate_again(self):
        stage = ImageNormalizationStage()
        for orientation, grid in _ORIENTED_GRIDS.items():
            with self.subTest(orientation=orientation):
                first = stage._normalize_image(_pattern_payload(orientation))[0]
                second = stage._normalize_image(first)[0]
                self.assert_grid(second, grid)
                self.assertEqual(stage._normalize_image(first)[0], second)

    def test_archive_immutable_and_corrected_artifacts_reach_crop_and_pairing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "synthetic.ca-package"
            workspace = root / "workspace"
            workspace.mkdir()
            manifest = _build_manifest(
                photos={
                    "front": "images/front.png",
                    "reverse": "images/reverse.png",
                }
            )
            front = _pattern_payload(6)
            reverse = _pattern_payload(5)
            _build_package_zip(
                path=source,
                manifest=manifest,
                images={
                    "images/front.png": front,
                    "images/reverse.png": reverse,
                },
            )
            original_archive = source.read_bytes()
            stage_input = _make_stage_input(
                source=source,
                workspace=workspace,
                manifest=manifest,
            )
            normalized = ImageNormalizationStage().execute(stage_input)
            self.assertEqual(
                normalized.metadata["normalized_dimensions"],
                {
                    "coin-1/front": {"width": 64, "height": 96},
                    "coin-1/reverse": {"width": 64, "height": 96},
                },
            )
            for role, orientation in (("front", 6), ("reverse", 5)):
                artifact = normalized.artifacts[f"normalized-coin-1-{role}"]
                self.assertEqual(artifact.content_type, "image/jpeg")
                self.assertEqual(
                    artifact.relative_path, f"normalized/coin-1/{role}.jpg"
                )
                self.assert_grid(
                    (workspace / artifact.relative_path).read_bytes(),
                    _ORIENTED_GRIDS[orientation],
                )
            downstream = StageInput(
                request=stage_input.request,
                workspace=workspace,
                artifacts=normalized.artifacts,
            )
            cropped = CropDetectionStage().execute(downstream)
            for record in cropped.metadata["crop_records"]:
                self.assertEqual(
                    (record["source_width"], record["source_height"]), (64, 96)
                )
                self.assertFalse(record["crop_applied"])
                role = record["role"]
                self.assertEqual(
                    (
                        workspace
                        / cropped.artifacts[f"cropped-coin-1-{role}"].relative_path
                    ).read_bytes(),
                    (
                        workspace
                        / normalized.artifacts[
                            f"normalized-coin-1-{role}"
                        ].relative_path
                    ).read_bytes(),
                )
            pairing_stage = ObverseReversePairingStage()
            normalized_pairing = pairing_stage.execute(downstream)
            cropped_pairing = pairing_stage.execute(
                StageInput(
                    request=stage_input.request,
                    workspace=workspace,
                    artifacts={**normalized.artifacts, **cropped.artifacts},
                )
            )
            self.assertEqual(cropped_pairing.metadata, normalized_pairing.metadata)
            record = cropped_pairing.metadata["pairing_records"][0]
            self.assertEqual(
                (
                    record["front_width"],
                    record["front_height"],
                    record["reverse_width"],
                    record["reverse_height"],
                ),
                (64, 96, 64, 96),
            )
            self.assertEqual(source.read_bytes(), original_archive)
            with zipfile.ZipFile(source) as archive:
                self.assertEqual(archive.read("images/front.png"), front)
                self.assertEqual(archive.read("images/reverse.png"), reverse)


if __name__ == "__main__":
    unittest.main()
