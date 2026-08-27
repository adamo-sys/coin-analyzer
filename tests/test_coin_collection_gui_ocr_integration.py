"""Focused production-GUI wiring tests for advisory OCR review."""

from __future__ import annotations

import inspect
import queue
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

import capture_import.reviewed_coin_collection_entry as reviewed_entry
from capture_import.desktop_import_pipeline_selection import ImportPipelineMode
from capture_import.desktop_ocr_review_handoff import DesktopOCRReviewHandoff
from capture_import.image_store import ManagedCollectionImageStore
from capture_import.snapshot import CapturePackageSnapshotService
from capture_import.standalone_image_intake import (
    create_temporary_capture_package,
)
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

    def test_file_menu_exposes_primary_image_import_action(self) -> None:
        menu_source = inspect.getsource(CoinCollectionGUI.create_menu_bar)

        self.assertIn("OCR-Assisted Capture Package...", menu_source)
        self.assertIn("self.import_capture_package_with_ocr", menu_source)
        self.assertIn('label="Import Coin Images..."', menu_source)
        self.assertIn("self.import_coin_images_with_ocr", menu_source)

    def test_default_capture_package_action_remains_non_ocr(self) -> None:
        gui = self.gui()
        gui._open_capture_package_import = Mock()

        gui.import_capture_package()

        gui._open_capture_package_import.assert_called_once_with(
            import_mode=ImportPipelineMode.DEFAULT,
        )

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
                release = dialog.call_args.kwargs["on_close"]

            self.assertTrue(captured_path.exists())
            dialog.assert_called_once()
            self.assertEqual(
                dialog.call_args.kwargs["import_mode"],
                ImportPipelineMode.OCR_ENABLED,
            )
            callback = dialog.call_args.kwargs["on_ocr_handoff"]
            gui.open_ocr_review_handoff = Mock()
            parent = object()
            handoff = object()
            callback(parent, handoff)
            gui.open_ocr_review_handoff.assert_called_once()
            forwarded = gui.open_ocr_review_handoff.call_args
            self.assertEqual(forwarded.args, (parent, handoff))
            self.assertEqual(
                forwarded.kwargs["managed_photo_source"].path,
                captured_path,
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

    def test_dialog_close_callback_is_idempotent(self) -> None:
        dialog = CapturePackageImportDialog.__new__(CapturePackageImportDialog)
        closed = Mock()
        dialog._close_notified = False
        dialog._on_close = closed

        dialog._notify_close_once()
        dialog._notify_close_once()

        closed.assert_called_once_with()

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
            source = SimpleNamespace(path=Path(temp) / "source.ca-package")
            source.release = Mock()
            gui._ocr_managed_photo_source = source

            with (
                patch(
                    "coin_collection_gui.messagebox.askyesno",
                    return_value=False,
                ) as confirm,
                patch(
                    "capture_import.reviewed_coin_collection_entry."
                    "persist_reviewed_coin"
                ) as persist,
            ):
                gui._confirm_and_save_ocr_review(
                    review,
                    conflict_model.resolutions,
                )

        confirm.assert_called_once()
        persist.assert_not_called()
        source.release.assert_called_once_with()
        self.assertEqual(collection.items, [])
        gui.refresh_collection_list.assert_not_called()

    def test_unresolved_review_releases_source_without_managed_write(self) -> None:
        gui = self.gui()
        _provider, _composition, _outcome, handoff = _execute_opt_in_handoff()
        _candidate_model, review = _complete_candidate_review(handoff)
        gui._ocr_review_handoff = handoff
        gui._ocr_review_parent = object()
        source = SimpleNamespace(path=Path("source.ca-package"))
        source.release = Mock()
        gui._ocr_managed_photo_source = source

        with (
            patch("coin_collection_gui.messagebox.showwarning") as warning,
            patch(
                "capture_import.reviewed_coin_collection_entry."
                "persist_reviewed_coin"
            ) as persist,
        ):
            gui._confirm_and_save_ocr_review(review, ())

        warning.assert_called_once()
        persist.assert_not_called()
        source.release.assert_called_once_with()

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

    def test_fixture_backed_corrected_save_reopens_with_valid_managed_photos(
        self,
    ) -> None:
        gui = self.gui()
        _provider, _composition, _outcome, handoff = _execute_opt_in_handoff()
        _candidate_model, review = _complete_candidate_review(handoff)
        conflict_model = OCRConflictReviewModel(
            report=handoff.report,
            review=review,
            review_controller=handoff.review_controller,
        )
        conflict_model.enter_corrected(value="1969")
        raw_years = {
            candidate.normalized_value
            for candidate in handoff.report.candidates
            if candidate.field_name == "year"
        }

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front = root / "fixture-front.jpg"
            reverse = root / "fixture-reverse.png"
            Image.new("RGB", (64, 64), "red").save(front, format="JPEG")
            Image.new("RGB", (64, 64), "blue").save(reverse, format="PNG")
            source = create_temporary_capture_package(
                front_path=front,
                reverse_path=reverse,
            )
            source_path = source.path
            storage = root / "collection.json"
            collection = CoinCollection(str(storage))
            images = ManagedCollectionImageStore(
                root / "managed",
                collection_path_prefix="managed",
            )
            snapshots = CapturePackageSnapshotService(root / "snapshots")
            gui.app.collection = collection
            gui._ocr_review_handoff = handoff
            gui._ocr_review_parent = object()
            gui._ocr_managed_photo_source = source
            real_persist = reviewed_entry.persist_reviewed_coin

            def persist_in_fixture(**kwargs):
                return real_persist(
                    **kwargs,
                    managed_image_store=images,
                    snapshot_service=snapshots,
                    import_lock_path=root / "import.lock",
                )

            with (
                patch(
                    "coin_collection_gui.messagebox.askyesno",
                    return_value=True,
                ) as confirm,
                patch("coin_collection_gui.messagebox.showinfo") as success,
                patch(
                    "capture_import.reviewed_coin_collection_entry."
                    "persist_reviewed_coin",
                    side_effect=persist_in_fixture,
                ),
            ):
                gui._confirm_and_save_ocr_review(
                    review,
                    conflict_model.resolutions,
                )

            reopened = CoinCollection(str(storage))
            self.assertEqual(len(reopened.items), 1)
            persisted = reopened.items[0]
            managed_paths = [
                images.root.joinpath(*Path(photo.path).parts[1:])
                for photo in persisted.photos
            ]

            self.assertEqual(persisted.country, "Canada")
            self.assertEqual(persisted.denomination, "25 cents")
            self.assertEqual(persisted.year, "1969")
            self.assertNotIn(persisted.year, raw_years)
            self.assertEqual(
                [photo.role.value for photo in persisted.photos],
                ["FRONT", "BACK"],
            )
            self.assertEqual(persisted.image_path, persisted.photos[0].path)
            self.assertTrue(all(path.is_file() for path in managed_paths))
            self.assertFalse(source_path.exists())
            confirmation_message = confirm.call_args.args[1]
            self.assertIn("Country: Canada", confirmation_message)
            self.assertIn("Denomination: 25 cents", confirmation_message)
            self.assertIn("Year: 1969", confirmation_message)
            gui.refresh_collection_list.assert_called_once_with()
            success.assert_called_once()

    def test_recovery_required_save_failure_is_distinct_and_non_mutating(
        self,
    ) -> None:
        recovery_error_type = getattr(
            reviewed_entry,
            "ReviewedCoinRecoveryRequiredError",
            None,
        )
        self.assertIsNotNone(
            recovery_error_type,
            "The reviewed-save boundary needs a typed recovery state.",
        )
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
            source = SimpleNamespace(path=Path(temp) / "source.ca-package")
            source.release = Mock()
            gui._ocr_managed_photo_source = source

            with (
                patch(
                    "coin_collection_gui.messagebox.askyesno",
                    return_value=True,
                ),
                patch("coin_collection_gui.messagebox.showerror") as error,
                patch(
                    "capture_import.reviewed_coin_collection_entry."
                    "persist_reviewed_coin",
                    side_effect=recovery_error_type(),
                ),
            ):
                gui._confirm_and_save_ocr_review(
                    review,
                    conflict_model.resolutions,
                )

        error.assert_called_once_with(
            "Reviewed Coin Recovery Required",
            "The reviewed coin save did not reach a proven clean state. "
            "Recovery or operator attention is required.",
            parent=gui._ocr_review_parent,
        )
        source.release.assert_called_once_with()
        self.assertEqual(collection.items, [])
        gui.refresh_collection_list.assert_not_called()

    def test_real_managed_photo_cleanup_failure_emits_recovery_state(
        self,
    ) -> None:
        private_detail = r"C:\private-collection\managed\coin-photo.jpg"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front = root / "fixture-front.jpg"
            reverse = root / "fixture-reverse.png"
            Image.new("RGB", (64, 64), "red").save(front, format="JPEG")
            Image.new("RGB", (64, 64), "blue").save(reverse, format="PNG")
            source = create_temporary_capture_package(
                front_path=front,
                reverse_path=reverse,
            )
            collection = CoinCollection(str(root / "collection.json"))
            images = ManagedCollectionImageStore(root / "managed")

            with (
                patch.object(collection, "add_item", return_value=False),
                patch.object(
                    images,
                    "cleanup",
                    side_effect=OSError(private_detail),
                ) as cleanup,
                self.assertRaises(
                    reviewed_entry.ReviewedCoinRecoveryRequiredError
                ) as raised,
            ):
                reviewed_entry.persist_reviewed_coin(
                    collection=collection,
                    draft=reviewed_entry.ReviewedCoinDraft(
                        "coin-1",
                        "Canada",
                        "25 cents",
                        "1969",
                    ),
                    source_package_path=source.path,
                    managed_image_store=images,
                    snapshot_service=CapturePackageSnapshotService(
                        root / "snapshots"
                    ),
                    import_lock_path=root / "import.lock",
                )

            remaining_managed_files = [
                path for path in images.root.rglob("*") if path.is_file()
            ]
            source.release()

        cleanup.assert_called_once()
        self.assertEqual(
            str(raised.exception),
            reviewed_entry.ReviewedCoinRecoveryRequiredError.safe_message,
        )
        self.assertNotIn(private_detail, str(raised.exception))
        self.assertIsInstance(raised.exception.__cause__, OSError)
        self.assertEqual(collection.items, [])
        self.assertTrue(remaining_managed_files)

    def test_clean_save_failure_redacts_private_exception_detail(self) -> None:
        gui = self.gui()
        _provider, _composition, _outcome, handoff = _execute_opt_in_handoff()
        _candidate_model, review = _complete_candidate_review(handoff)
        conflict_model = OCRConflictReviewModel(
            report=handoff.report,
            review=review,
            review_controller=handoff.review_controller,
        )
        conflict_model.select_existing(value="1968")
        private_detail = r"C:\private-collection\collection.json"
        with tempfile.TemporaryDirectory() as temp:
            collection = CoinCollection(str(Path(temp) / "collection.json"))
            gui.app.collection = collection
            gui._ocr_review_handoff = handoff
            gui._ocr_review_parent = object()
            source = SimpleNamespace(path=Path(temp) / "source.ca-package")
            source.release = Mock()
            gui._ocr_managed_photo_source = source

            with (
                patch(
                    "coin_collection_gui.messagebox.askyesno",
                    return_value=True,
                ),
                patch("coin_collection_gui.messagebox.showerror") as error,
                patch(
                    "capture_import.reviewed_coin_collection_entry."
                    "persist_reviewed_coin",
                    side_effect=reviewed_entry.ReviewedCoinPersistenceError(
                        private_detail
                    ),
                ),
            ):
                gui._confirm_and_save_ocr_review(
                    review,
                    conflict_model.resolutions,
                )

        error.assert_called_once_with(
            "Collection Save Failed",
            "The reviewed coin could not be saved. "
            "No collection changes were confirmed.",
            parent=gui._ocr_review_parent,
        )
        self.assertNotIn(private_detail, error.call_args.args[1])
        source.release.assert_called_once_with()
        self.assertEqual(collection.items, [])
        gui.refresh_collection_list.assert_not_called()

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
