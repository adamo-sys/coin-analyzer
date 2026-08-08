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
    _execute_opt_in_handoff,
)
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


if __name__ == "__main__":
    unittest.main()
