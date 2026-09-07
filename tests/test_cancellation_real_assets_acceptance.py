"""Acceptance coverage for cancellation with real temporary capture assets."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image

import capture_import.reviewed_coin_collection_entry as reviewed_entry
from capture_import.desktop_ocr_conflict_review import OCRConflictReviewModel
from capture_import.image_store import ManagedCollectionImageStore
from capture_import.snapshot import CapturePackageSnapshotService
from capture_import.standalone_image_intake import create_temporary_capture_package
from coin_collection import CoinCollection
from coin_collection_gui import CoinCollectionGUI
from tests.test_desktop_ocr_review_integration import (
    _complete_candidate_review,
    _execute_opt_in_handoff,
)


class CancellationRealAssetsAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.storage = self.root / "collection.json"
        self.collection = CoinCollection(str(self.storage))
        self.front = self.root / "front.jpg"
        self.reverse = self.root / "reverse.png"
        Image.new("RGB", (64, 64), "red").save(self.front, format="JPEG")
        Image.new("RGB", (64, 64), "blue").save(self.reverse, format="PNG")

        self.gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        self.gui.root = object()
        self.gui.app = SimpleNamespace(collection=self.collection)
        self.gui.capture_import_ready = True
        self.gui.refresh_collection_list = Mock()

    def _review(self):
        _provider, _composition, _outcome, handoff = _execute_opt_in_handoff()
        _candidate_model, review = _complete_candidate_review(handoff)
        conflict_model = OCRConflictReviewModel(
            report=handoff.report,
            review=review,
            review_controller=handoff.review_controller,
        )
        conflict_model.select_existing(value="1968")
        return handoff, review, conflict_model

    def test_cancel_releases_real_temporary_assets_without_collection_mutation(self) -> None:
        handoff, review, conflict_model = self._review()
        source = create_temporary_capture_package(
            front_path=self.front,
            reverse_path=self.reverse,
        )
        source_path = source.path
        source_root = source_path.parent
        self.assertTrue(source_path.exists())

        self.gui._ocr_review_handoff = handoff
        self.gui._ocr_review_parent = object()
        self.gui._ocr_managed_photo_source = source

        with (
            patch("coin_collection_gui.messagebox.askyesno", return_value=False) as confirm,
            patch("coin_collection_gui.messagebox.showinfo") as success,
            patch("coin_collection_gui.messagebox.showerror") as error,
            patch("capture_import.reviewed_coin_collection_entry.persist_reviewed_coin") as persist,
        ):
            self.gui._confirm_and_save_ocr_review(
                review,
                conflict_model.resolutions,
            )

        confirm.assert_called_once()
        persist.assert_not_called()
        success.assert_not_called()
        error.assert_not_called()
        self.gui.refresh_collection_list.assert_not_called()
        self.assertEqual([], self.collection.items)
        self.assertFalse(self.storage.exists())
        self.assertFalse(source_path.exists())
        self.assertFalse(source_root.exists())
        self.assertEqual(self.front.read_bytes(), self.front.read_bytes())
        self.assertEqual(self.reverse.read_bytes(), self.reverse.read_bytes())

    def test_fresh_retry_after_cancel_can_save_real_temporary_assets(self) -> None:
        handoff, review, conflict_model = self._review()

        cancelled_source = create_temporary_capture_package(
            front_path=self.front,
            reverse_path=self.reverse,
        )
        self.gui._ocr_review_handoff = handoff
        self.gui._ocr_review_parent = object()
        self.gui._ocr_managed_photo_source = cancelled_source

        with patch("coin_collection_gui.messagebox.askyesno", return_value=False):
            self.gui._confirm_and_save_ocr_review(review, conflict_model.resolutions)

        self.assertEqual([], self.collection.items)
        self.assertFalse(cancelled_source.path.exists())

        retry_handoff, retry_review, retry_conflict_model = self._review()
        retry_source = create_temporary_capture_package(
            front_path=self.front,
            reverse_path=self.reverse,
        )
        retry_path = retry_source.path
        self.gui._ocr_review_handoff = retry_handoff
        self.gui._ocr_review_parent = object()
        self.gui._ocr_managed_photo_source = retry_source

        images = ManagedCollectionImageStore(
            self.root / "managed",
            collection_path_prefix="managed",
        )
        snapshots = CapturePackageSnapshotService(self.root / "snapshots")
        real_persist = reviewed_entry.persist_reviewed_coin

        def persist_in_fixture(**kwargs):
            return real_persist(
                **kwargs,
                managed_image_store=images,
                snapshot_service=snapshots,
                import_lock_path=self.root / "import.lock",
            )

        with (
            patch("coin_collection_gui.messagebox.askyesno", return_value=True),
            patch("coin_collection_gui.messagebox.showinfo") as success,
            patch("coin_collection_gui.messagebox.showerror") as error,
            patch(
                "capture_import.reviewed_coin_collection_entry.persist_reviewed_coin",
                side_effect=persist_in_fixture,
            ),
        ):
            self.gui._confirm_and_save_ocr_review(
                retry_review,
                retry_conflict_model.resolutions,
            )

        error.assert_not_called()
        success.assert_called_once()
        self.gui.refresh_collection_list.assert_called_once()
        self.assertFalse(retry_path.exists())
        reopened = CoinCollection(str(self.storage))
        self.assertEqual(1, len(reopened.items))
        self.assertEqual("Canada", reopened.items[0].country)
        self.assertEqual("25 cents", reopened.items[0].denomination)
        self.assertEqual("1968", reopened.items[0].year)
        self.assertEqual(2, len(reopened.items[0].photos))


if __name__ == "__main__":
    unittest.main()
