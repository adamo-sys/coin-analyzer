"""Focused tests for ordinary-image adaptation into the OCR pipeline."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from capture_import.desktop_ocr_review_handoff import (
    create_desktop_ocr_review_handoff,
)
from capture_import.desktop_ocr_review_composition import (
    DesktopOCRReviewComposition,
)
from capture_import.desktop_ocr_conflict_review import OCRConflictReviewModel
from capture_import.package import CapturePackageValidator
from capture_import.standalone_image_intake import (
    MalformedStandaloneImageError,
    MissingStandaloneImageError,
    PartialStandaloneImageSelectionError,
    UnreadableStandaloneImageError,
    UnsupportedStandaloneImageError,
    create_temporary_capture_package,
)
from capture_import.workflow_execution import ImportWorkflow
from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
)
from capture_import.workflow_ocr_composition import (
    build_ocr_image_processing_pipeline,
)
from capture_import.workflow_ocr_review_controller import (
    OCRReviewSessionController,
)
from coin_collection import CoinCollection
from coin_collection_gui import CoinCollectionGUI
from tests.test_desktop_ocr_review_integration import (
    DeterministicOCRProvider,
    _complete_candidate_review,
)


def _write_image(path: Path, image_format: str, color) -> None:
    Image.new("RGB", (96, 96), color).save(path, format=image_format)


class StandaloneImageIntakeTests(unittest.TestCase):
    def test_generated_package_passes_authoritative_package_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front = root / "front.jpeg"
            reverse = root / "reverse.png"
            _write_image(front, "JPEG", (120, 100, 80))
            _write_image(reverse, "PNG", (80, 100, 120))

            source = create_temporary_capture_package(
                front_path=front,
                reverse_path=reverse,
            )
            payload = source.path.read_bytes()
            from hashlib import sha256

            validated = CapturePackageValidator().validate_stream(
                BytesIO(payload),
                source.path.name,
                package_sha256=sha256(payload).hexdigest(),
                package_byte_length=len(payload),
            )

            self.assertEqual(len(validated.manifest.coins), 1)
            self.assertEqual(
                [item.role.value for item in validated.media],
                ["front", "reverse"],
            )
            source.release()

    def test_raw_images_reach_real_existing_ocr_composition_and_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front = root / "front.jpg"
            reverse = root / "reverse.png"
            _write_image(front, "JPEG", (150, 120, 80))
            _write_image(reverse, "PNG", (140, 110, 70))
            source = create_temporary_capture_package(
                front_path=front,
                reverse_path=reverse,
            )
            workspace = (root / "workspace").absolute()
            workspace.mkdir()
            provider = DeterministicOCRProvider()
            pipeline = build_ocr_image_processing_pipeline(provider=provider)
            outcome = ImportWorkflow(pipeline).execute(
                ImportRequest(
                    source=source.path.absolute(),
                    collection_id="not-persisted",
                    configuration=ImportConfiguration(),
                ),
                workspace,
            )
            handoff = create_desktop_ocr_review_handoff(
                composition=DesktopOCRReviewComposition(
                    pipeline=pipeline,
                    review_controller=OCRReviewSessionController(),
                ),
                outcome=outcome,
            )

            self.assertEqual(len(provider.calls), 2)
            self.assertEqual(
                [(call[0], call[1]) for call in provider.calls],
                [("coin-1", "front"), ("coin-1", "reverse")],
            )
            self.assertEqual(len(handoff.report.observations), 2)
            source.release()

    def test_release_removes_owned_temporary_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front = root / "front.jpg"
            reverse = root / "reverse.jpg"
            _write_image(front, "JPEG", "red")
            _write_image(reverse, "JPEG", "blue")
            source = create_temporary_capture_package(
                front_path=front,
                reverse_path=reverse,
            )
            package_path = source.path

            source.release()
            source.release()

            self.assertFalse(package_path.exists())

    def test_raw_images_continue_through_confirmation_save_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front = root / "front.jpg"
            reverse = root / "reverse.png"
            _write_image(front, "JPEG", (150, 120, 80))
            _write_image(reverse, "PNG", (140, 110, 70))
            source = create_temporary_capture_package(
                front_path=front,
                reverse_path=reverse,
            )
            workspace = (root / "workspace").absolute()
            workspace.mkdir()
            provider = DeterministicOCRProvider()
            pipeline = build_ocr_image_processing_pipeline(provider=provider)
            composition = DesktopOCRReviewComposition(
                pipeline=pipeline,
                review_controller=OCRReviewSessionController(),
            )
            outcome = ImportWorkflow(pipeline).execute(
                ImportRequest(
                    source=source.path.absolute(),
                    collection_id="not-persisted-by-package-import",
                    configuration=ImportConfiguration(),
                ),
                workspace,
            )
            handoff = create_desktop_ocr_review_handoff(
                composition=composition,
                outcome=outcome,
            )
            _candidate_model, review = _complete_candidate_review(handoff)
            conflicts = OCRConflictReviewModel(
                report=handoff.report,
                review=review,
                review_controller=handoff.review_controller,
            )
            conflicts.select_existing(value="1968")
            storage = root / "collection.json"
            collection = CoinCollection(str(storage))
            gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
            gui.app = SimpleNamespace(collection=collection)
            gui._ocr_review_handoff = handoff
            gui._ocr_review_parent = object()
            gui.refresh_collection_list = Mock()

            with (
                patch(
                    "coin_collection_gui.messagebox.askyesno",
                    return_value=True,
                ),
                patch("coin_collection_gui.messagebox.showinfo"),
            ):
                gui._confirm_and_save_ocr_review(
                    review,
                    conflicts.resolutions,
                )
            reopened = CoinCollection(str(storage))
            source.release()

        self.assertEqual(len(reopened.items), 1)
        self.assertEqual(reopened.items[0].country, "Canada")
        self.assertEqual(reopened.items[0].denomination, "25 cents")
        self.assertEqual(reopened.items[0].year, "1968")
        self.assertEqual(reopened.items[0].image_path, "")

    def test_partial_selection_is_rejected_before_file_access(self) -> None:
        with self.assertRaises(PartialStandaloneImageSelectionError):
            create_temporary_capture_package(
                front_path="",
                reverse_path="reverse.jpg",
            )

    def test_missing_image_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing.jpg"
            with self.assertRaises(MissingStandaloneImageError):
                create_temporary_capture_package(
                    front_path=missing,
                    reverse_path=missing,
                )

    def test_unsupported_extension_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            unsupported = Path(temp) / "coin.gif"
            unsupported.write_bytes(b"GIF89a")
            with self.assertRaises(UnsupportedStandaloneImageError):
                create_temporary_capture_package(
                    front_path=unsupported,
                    reverse_path=unsupported,
                )

    def test_malformed_image_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            malformed = Path(temp) / "coin.jpg"
            malformed.write_bytes(b"not-a-jpeg")
            with self.assertRaises(MalformedStandaloneImageError):
                create_temporary_capture_package(
                    front_path=malformed,
                    reverse_path=malformed,
                )

    def test_unreadable_image_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "coin.jpg"
            _write_image(image, "JPEG", "green")
            with (
                patch(
                    "capture_import.standalone_image_intake.os.open",
                    side_effect=PermissionError("denied"),
                ),
                self.assertRaises(UnreadableStandaloneImageError),
            ):
                create_temporary_capture_package(
                    front_path=image,
                    reverse_path=image,
                )


if __name__ == "__main__":
    unittest.main()
