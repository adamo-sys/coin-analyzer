"""Focused production-GUI wiring tests for advisory OCR review."""

from __future__ import annotations

import inspect
import queue
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from capture_import.desktop_import_pipeline_selection import ImportPipelineMode
from capture_import.desktop_ocr_review_handoff import DesktopOCRReviewHandoff
from capture_import.ui import CapturePackageImportDialog
from capture_import.workflow_ocr_stage import OCRMetadataExtractionStage
from capture_import.workflow_pipeline import ProcessingPipeline
from coin_collection_gui import CoinCollectionGUI
from tests.test_desktop_ocr_review_integration import (
    ArtifactSourceStage,
    DeterministicOCRProvider,
    _complete_candidate_review,
    _execute_opt_in_handoff,
)
from capture_import.desktop_ocr_conflict_review import OCRConflictReviewModel
from coin_collection import CoinCollection
from tests.test_workflow_image_integration import (
    _CoordinatorSpy,
    _ImmediateThread,
    _RecoverySpy,
    _WindowSpy,
)


class CoinCollectionGUIOCRIntegrationTests(unittest.TestCase):
    def gui(self) -> CoinCollectionGUI:
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = object()
        gui.app = SimpleNamespace(collection=object())
        gui.capture_import_ready = True
        gui.refresh_collection_list = Mock()
        return gui

    def test_visible_ocr_action_selects_explicit_ocr_mode(self) -> None:
        gui = self.gui()
        gui._open_capture_package_import = Mock()

        gui.import_capture_package_with_ocr()

        gui._open_capture_package_import.assert_called_once_with(
            import_mode=ImportPipelineMode.OCR_ENABLED,
        )

    def test_file_menu_exposes_ocr_assisted_action(self) -> None:
        menu_source = inspect.getsource(CoinCollectionGUI.create_menu_bar)

        self.assertIn("OCR-Assisted Capture Package...", menu_source)
        self.assertIn("self.import_capture_package_with_ocr", menu_source)
        self.assertIn("OCR-Assisted Coin Images...", menu_source)
        self.assertIn("self.import_coin_images_with_ocr", menu_source)

    def test_production_entry_passes_real_mode_and_handoff_callback(self) -> None:
        gui = self.gui()

        with (
            patch(
                "coin_collection_gui.filedialog.askopenfilename",
                return_value="coin.ca-package",
            ),
            patch("coin_collection_gui.CapturePackageImportDialog") as dialog,
        ):
            gui._open_capture_package_import(
                import_mode=ImportPipelineMode.OCR_ENABLED,
            )

        dialog.assert_called_once_with(
            gui.root,
            "coin.ca-package",
            gui.app.collection,
            on_success=gui.refresh_collection_list,
            import_mode=ImportPipelineMode.OCR_ENABLED,
            on_ocr_handoff=gui.open_ocr_review_handoff,
        )

    def test_cancelled_front_image_picker_has_no_effect(self) -> None:
        gui = self.gui()

        with (
            patch(
                "coin_collection_gui.filedialog.askopenfilename",
                return_value="",
            ) as picker,
            patch("coin_collection_gui.CapturePackageImportDialog") as dialog,
        ):
            gui.import_coin_images_with_ocr()

        picker.assert_called_once()
        dialog.assert_not_called()

    def test_cancelled_reverse_image_picker_has_no_effect(self) -> None:
        gui = self.gui()

        with (
            patch(
                "coin_collection_gui.filedialog.askopenfilename",
                side_effect=["front.jpg", ""],
            ) as picker,
            patch("coin_collection_gui.CapturePackageImportDialog") as dialog,
        ):
            gui.import_coin_images_with_ocr()

        self.assertEqual(picker.call_count, 2)
        dialog.assert_not_called()

    def test_real_image_adapter_launches_existing_ocr_dialog_seam(self) -> None:
        gui = self.gui()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front = root / "front.jpg"
            reverse = root / "reverse.png"
            from PIL import Image

            Image.new("RGB", (64, 64), "red").save(front, format="JPEG")
            Image.new("RGB", (64, 64), "blue").save(reverse, format="PNG")
            captured_path = None
            release = None

            with (
                patch(
                    "coin_collection_gui.filedialog.askopenfilename",
                    side_effect=[str(front), str(reverse)],
                ),
                patch("coin_collection_gui.CapturePackageImportDialog") as dialog,
            ):
                gui.import_coin_images_with_ocr()
                captured_path = Path(dialog.call_args.args[1])
                release = dialog.call_args.kwargs["on_source_released"]

            self.assertTrue(captured_path.exists())
            dialog.assert_called_once()
            self.assertEqual(
                dialog.call_args.kwargs["import_mode"],
                ImportPipelineMode.OCR_ENABLED,
            )
            self.assertEqual(
                dialog.call_args.kwargs["on_ocr_handoff"],
                gui.open_ocr_review_handoff,
            )
            release()
            self.assertFalse(captured_path.exists())

    def test_malformed_selected_image_reports_error_without_dialog(self) -> None:
        gui = self.gui()
        with tempfile.TemporaryDirectory() as temp:
            malformed = Path(temp) / "front.jpg"
            malformed.write_bytes(b"not-an-image")

            with (
                patch(
                    "coin_collection_gui.filedialog.askopenfilename",
                    side_effect=[str(malformed), str(malformed)],
                ),
                patch("coin_collection_gui.messagebox.showerror") as error,
                patch("coin_collection_gui.CapturePackageImportDialog") as dialog,
            ):
                gui.import_coin_images_with_ocr()

        dialog.assert_not_called()
        error.assert_called_once_with(
            "Coin Image OCR",
            "A selected file is not a valid JPG or PNG image.",
        )

    def test_adapter_source_release_callback_is_idempotent(self) -> None:
        dialog = CapturePackageImportDialog.__new__(CapturePackageImportDialog)
        released = Mock()
        dialog._source_released = False
        dialog._on_source_released = released

        dialog._release_source_once()
        dialog._release_source_once()

        released.assert_called_once_with()

    def test_real_sprint20_handoff_reaches_existing_candidate_review_seam(
        self,
    ) -> None:
        gui = self.gui()
        _provider, composition, _outcome, handoff = _execute_opt_in_handoff()
        parent = object()
        expected_dialog = object()

        with patch(
            "capture_import.desktop_ocr_candidate_review."
            "create_ocr_candidate_review_dialog",
            return_value=expected_dialog,
        ) as review_dialog:
            gui.open_ocr_review_handoff(parent, handoff)

        self.assertIsInstance(handoff, DesktopOCRReviewHandoff)
        self.assertIs(handoff.review_controller, composition.review_controller)
        self.assertIs(gui._ocr_review_handoff, handoff)
        self.assertIs(gui._ocr_review_dialog, expected_dialog)
        review_dialog.assert_called_once_with(
            parent=parent,
            report=handoff.report,
            review_controller=handoff.review_controller,
            reviewer_id="desktop-collector",
            on_close=gui._open_ocr_conflict_review,
        )

    def test_real_ocr_pipeline_stops_before_collection_prepare(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dialog = CapturePackageImportDialog.__new__(
                CapturePackageImportDialog
            )
            dialog._source_path = str(root / "source.ca-package")
            dialog._collection = SimpleNamespace(
                storage_path=str(root / "collection.json")
            )
            dialog._recovery = _RecoverySpy()
            coordinator = _CoordinatorSpy()
            dialog._coordinator = coordinator
            dialog._closed = False
            dialog._request_id = object()
            dialog._queue = queue.Queue()
            dialog._workspace = None
            dialog._import_mode = ImportPipelineMode.OCR_ENABLED
            dialog.window = _WindowSpy()
            provider = DeterministicOCRProvider()

            def runtime_factory(**_kwargs):
                return ProcessingPipeline(
                    (
                        ArtifactSourceStage(),
                        OCRMetadataExtractionStage(provider=provider),
                    )
                )

            dialog._ocr_runtime_factory = runtime_factory
            with (
                patch(
                    "capture_import.ui.WORKSPACE_ROOT",
                    str(root / "workspaces"),
                ),
                patch("capture_import.ui.threading.Thread", _ImmediateThread),
                patch(
                    "capture_import.workflow_ocr_stage._read_bounded_artifact",
                    return_value=b"in-memory-jpeg",
                ),
            ):
                dialog._start_prepare()

            request, kind, handoff = dialog._queue.get_nowait()
            self.assertIs(request, dialog._request_id)
            self.assertEqual(kind, "ocr_ready", repr(handoff))
            self.assertIsInstance(handoff, DesktopOCRReviewHandoff)
            self.assertIs(handoff, dialog._ocr_handoff)
            self.assertEqual(len(provider.calls), 2)
            self.assertEqual(coordinator.prepare_calls, [])
            self.assertIsNone(getattr(dialog, "_prepared", None))

    def test_operator_cancellation_causes_zero_collection_mutation(self) -> None:
        gui = self.gui()
        _provider, _composition, _outcome, handoff = _execute_opt_in_handoff()
        _candidate_model, review = _complete_candidate_review(handoff)
        conflict_model = OCRConflictReviewModel(
            report=handoff.report,
            review=review,
            review_controller=handoff.review_controller,
        )
        conflict_model.select_existing(value="1968")
        with tempfile.TemporaryDirectory() as temp:
            collection = CoinCollection(str(Path(temp) / "collection.json"))
            gui.app.collection = collection
            gui._ocr_review_handoff = handoff
            gui._ocr_review_parent = object()

            with patch(
                "coin_collection_gui.messagebox.askyesno",
                return_value=False,
            ) as confirm:
                gui._confirm_and_save_ocr_review(
                    review,
                    conflict_model.resolutions,
                )

        confirm.assert_called_once()
        self.assertEqual(collection.items, [])
        gui.refresh_collection_list.assert_not_called()

    def test_operator_confirmation_saves_and_reload_preserves_coin(self) -> None:
        gui = self.gui()
        _provider, _composition, _outcome, handoff = _execute_opt_in_handoff()
        _candidate_model, review = _complete_candidate_review(handoff)
        conflict_model = OCRConflictReviewModel(
            report=handoff.report,
            review=review,
            review_controller=handoff.review_controller,
        )
        conflict_model.select_existing(value="1968")
        with tempfile.TemporaryDirectory() as temp:
            storage = Path(temp) / "collection.json"
            collection = CoinCollection(str(storage))
            gui.app.collection = collection
            gui._ocr_review_handoff = handoff
            gui._ocr_review_parent = object()

            with (
                patch(
                    "coin_collection_gui.messagebox.askyesno",
                    return_value=True,
                ),
                patch("coin_collection_gui.messagebox.showinfo") as success,
            ):
                gui._confirm_and_save_ocr_review(
                    review,
                    conflict_model.resolutions,
                )
            reopened = CoinCollection(str(storage))

        self.assertEqual(len(reopened.items), 1)
        self.assertEqual(reopened.items[0].country, "Canada")
        self.assertEqual(reopened.items[0].denomination, "25 cents")
        self.assertEqual(reopened.items[0].year, "1968")
        gui.refresh_collection_list.assert_called_once_with()
        success.assert_called_once()

    def test_conflict_dialog_hands_completed_resolutions_to_save_seam(self) -> None:
        gui = self.gui()
        _provider, _composition, _outcome, handoff = _execute_opt_in_handoff()
        _candidate_model, review = _complete_candidate_review(handoff)
        gui._ocr_review_handoff = handoff
        gui._ocr_review_parent = object()
        gui._confirm_and_save_ocr_review = Mock()

        with patch(
            "capture_import.desktop_ocr_conflict_review."
            "create_ocr_conflict_review_dialog",
            return_value=object(),
        ) as dialog:
            gui._open_ocr_conflict_review(review.field_reviews)

        callback = dialog.call_args.kwargs["on_close"]
        resolutions = (object(),)
        callback(resolutions)
        gui._confirm_and_save_ocr_review.assert_called_once_with(
            gui._ocr_report_review,
            resolutions,
        )


if __name__ == "__main__":
    unittest.main()
