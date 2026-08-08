"""Integration tests for reviewed OCR output entering the collection."""

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from capture_import.desktop_ocr_candidate_review import OCRCandidateReviewModel
from capture_import.desktop_ocr_conflict_review import OCRConflictReviewModel
from capture_import.reviewed_coin_collection_entry import (
    IncompleteReviewedCoinError,
    ReviewedCoinDraft,
    ReviewedCoinIdentityCollisionError,
    ReviewedCoinPersistenceError,
    create_reviewed_coin_draft,
    persist_reviewed_coin,
)
from capture_import.workflow_ocr_review_models import OCRReportReview
from coin_collection import CoinCollection
from tests.test_desktop_ocr_review_integration import (
    _complete_candidate_review,
    _execute_opt_in_handoff,
)


def _complete_review_and_resolution():
    _provider, _composition, _outcome, handoff = _execute_opt_in_handoff()
    _candidate_model, review = _complete_candidate_review(handoff)
    conflicts = OCRConflictReviewModel(
        report=handoff.report,
        review=review,
        review_controller=handoff.review_controller,
    )
    conflicts.select_existing(value="1968")
    return handoff, review, conflicts.resolutions


class ReviewedCoinCollectionEntryTests(unittest.TestCase):
    def test_real_review_mapping_creates_minimal_canonical_draft(self) -> None:
        handoff, review, resolutions = _complete_review_and_resolution()

        draft = create_reviewed_coin_draft(
            source_report=handoff.report,
            report_review=review,
            conflict_resolutions=resolutions,
        )

        self.assertEqual(draft.source_coin_id, "coin-1")
        self.assertEqual(draft.country, "Canada")
        self.assertEqual(draft.denomination, "25 cents")
        self.assertEqual(draft.year, "1968")
        self.assertEqual(draft.unmapped_fields, ())

    def test_rejected_required_field_fails_before_collection_mutation(self) -> None:
        _provider, _composition, _outcome, handoff = _execute_opt_in_handoff()
        model = OCRCandidateReviewModel(
            report=handoff.report,
            review_controller=handoff.review_controller,
            reviewer_id="collector-1",
        )
        while model.current_candidate is not None:
            if model.current_candidate.field_name == "country":
                model.reject(reason="Country cannot be confirmed.")
            else:
                model.approve(reason="Accepted integration value.")
            if not model.next_candidate():
                break
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=model.reviews,
        )

        with self.assertRaises(IncompleteReviewedCoinError):
            create_reviewed_coin_draft(
                source_report=handoff.report,
                report_review=review,
            )

    def test_unresolved_conflict_fails_before_draft_creation(self) -> None:
        _provider, _composition, _outcome, handoff = _execute_opt_in_handoff()
        _candidate_model, review = _complete_candidate_review(handoff)

        with self.assertRaises(ValueError):
            create_reviewed_coin_draft(
                source_report=handoff.report,
                report_review=review,
            )

    def test_persist_uses_real_collection_and_survives_reload(self) -> None:
        handoff, review, resolutions = _complete_review_and_resolution()
        draft = create_reviewed_coin_draft(
            source_report=handoff.report,
            report_review=review,
            conflict_resolutions=resolutions,
        )
        with tempfile.TemporaryDirectory() as temp:
            storage = Path(temp) / "collection.json"
            collection = CoinCollection(str(storage))

            item = persist_reviewed_coin(
                collection=collection,
                draft=draft,
                item_id="reviewed-coin-1",
                date_added="2026-08-08T12:00:00",
            )
            reopened = CoinCollection(str(storage))
            persisted = reopened.get_item(item.id)

        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.country, "Canada")
        self.assertEqual(persisted.denomination, "25 cents")
        self.assertEqual(persisted.year, "1968")
        self.assertEqual(persisted.grade, "")
        self.assertEqual(persisted.image_path, "")
        self.assertFalse(persisted.auto_detected)

    def test_save_failure_rolls_back_collection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            collection = CoinCollection(str(Path(temp) / "collection.json"))
            draft = ReviewedCoinDraft("coin-1", "Canada", "1 dollar", "1968")
            with patch.object(
                collection,
                "save_collection",
                return_value=False,
            ):
                collection.last_save_error = "disk unavailable"
                with self.assertRaises(ReviewedCoinPersistenceError):
                    persist_reviewed_coin(
                        collection=collection,
                        draft=draft,
                        item_id="reviewed-coin-1",
                    )

        self.assertEqual(collection.items, [])

    def test_record_id_collision_causes_zero_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            collection = CoinCollection(str(Path(temp) / "collection.json"))
            draft = ReviewedCoinDraft("coin-1", "Canada", "1 dollar", "1968")
            persist_reviewed_coin(
                collection=collection,
                draft=draft,
                item_id="same-id",
            )
            before = list(collection.items)

            with self.assertRaises(ReviewedCoinIdentityCollisionError):
                persist_reviewed_coin(
                    collection=collection,
                    draft=draft,
                    item_id="same-id",
                )

        self.assertEqual(collection.items, before)


if __name__ == "__main__":
    unittest.main()
