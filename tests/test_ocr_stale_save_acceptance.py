"""Offline acceptance journeys for reviewed OCR persistence under stale storage."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from capture_import.desktop_ocr_conflict_review import OCRConflictReviewModel
from capture_import.reviewed_coin_collection_entry import (
    ReviewedCoinPersistenceError,
    create_reviewed_coin_draft,
    persist_reviewed_coin,
)
from coin_collection import CoinCollection, CoinItem
from coin_collection_gui import CoinCollectionGUI
from tests.test_desktop_ocr_review_integration import (
    _complete_candidate_review,
    _execute_opt_in_handoff,
)


class OCRStaleSaveAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.storage = self.root / "collection.json"
        self.collection = CoinCollection(str(self.storage))
        self.assertTrue(
            self.collection.add_item(
                CoinItem(
                    id="seed",
                    image_path="",
                    country="Canada",
                    denomination="25 cents",
                    year="1967",
                    grade="",
                    notes="original",
                    date_added="2026-01-01",
                )
            )
        )
        _provider, _composition, _outcome, self.handoff = _execute_opt_in_handoff()
        _candidate_model, self.review = _complete_candidate_review(self.handoff)
        conflict_model = OCRConflictReviewModel(
            report=self.handoff.report,
            review=self.review,
            review_controller=self.handoff.review_controller,
        )
        conflict_model.select_existing(value="1968")
        self.resolutions = conflict_model.resolutions
        self.draft = create_reviewed_coin_draft(
            source_report=self.handoff.report,
            report_review=self.review,
            conflict_resolutions=self.resolutions,
        )

    def _external_change(self) -> bytes:
        other = CoinCollection(str(self.storage))
        self.assertTrue(other.update_item("seed", {"notes": "other window saved"}))
        return self.storage.read_bytes()

    def test_stale_reviewed_ocr_save_preserves_newer_storage_and_rolls_back_memory(self) -> None:
        original_ids = [item.id for item in self.collection.items]
        newer_bytes = self._external_change()

        with self.assertRaises(ReviewedCoinPersistenceError) as caught:
            persist_reviewed_coin(
                collection=self.collection,
                draft=self.draft,
                item_id="12345678-1234-4234-8234-123456789abc",
                date_added="2026-01-01",
            )

        message = str(caught.exception)
        self.assertIn("not saved", message)
        self.assertIn("changed outside this window", message)
        self.assertIn("Reload", message)
        self.assertEqual(self.storage.read_bytes(), newer_bytes)
        self.assertEqual([item.id for item in self.collection.items], original_ids)
        self.assertIsNone(
            self.collection.get_item("12345678-1234-4234-8234-123456789abc")
        )

    def test_explicit_reload_allows_reviewed_ocr_retry_without_losing_competing_change(self) -> None:
        self._external_change()
        target_id = "12345678-1234-4234-8234-123456789abc"

        with self.assertRaises(ReviewedCoinPersistenceError):
            persist_reviewed_coin(
                collection=self.collection,
                draft=self.draft,
                item_id=target_id,
                date_added="2026-01-01",
            )

        self.collection.load_collection()
        saved = persist_reviewed_coin(
            collection=self.collection,
            draft=self.draft,
            item_id=target_id,
            date_added="2026-01-01",
        )
        reopened = CoinCollection(str(self.storage))

        self.assertEqual(saved.id, target_id)
        self.assertEqual(reopened.get_item("seed").notes, "other window saved")
        persisted = reopened.get_item(target_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(
            (persisted.country, persisted.denomination, persisted.year),
            (self.draft.country, self.draft.denomination, self.draft.year),
        )

    def test_gui_reports_stale_ocr_save_as_failure_and_does_not_refresh(self) -> None:
        self._external_change()
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = object()
        gui.app = SimpleNamespace(collection=self.collection)
        gui.refresh_collection_list = Mock()
        gui._ocr_review_handoff = self.handoff
        gui._ocr_review_parent = object()
        gui._ocr_managed_photo_source = None

        with (
            patch("coin_collection_gui.messagebox.askyesno", return_value=True),
            patch("coin_collection_gui.messagebox.showerror") as error,
            patch("coin_collection_gui.messagebox.showinfo") as info,
        ):
            gui._confirm_and_save_ocr_review(self.review, self.resolutions)

        info.assert_not_called()
        gui.refresh_collection_list.assert_not_called()
        error.assert_called_once()
        title, message = error.call_args.args[:2]
        self.assertIn("Save", title)
        self.assertIn("not saved", message)
        self.assertIn("changed outside this window", message)
        self.assertIn("Reload", message)


if __name__ == "__main__":
    unittest.main()
