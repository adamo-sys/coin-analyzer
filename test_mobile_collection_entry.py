import csv
import os
import tempfile
import unittest

from coin_collection import CoinItem
from legacy_portfolio_importer import LegacyWantListIntent
from mobile_collection_entry import (
    APPROVE,
    REJECT,
    REVIEW,
    CollectionEntryCandidate,
    CollectionEntryReport,
    MobileCollectionEntryEngine,
    WORKFLOW_COIN_SHOW,
)
from ocr_assisted_identification import OCRIdentificationCandidate, IdentificationEvidence, OCRIdentificationEngine
from watchlist_engine import Watchlist, WatchlistItem, WatchPriority, WATCH_TYPE_SERIES


class TestMobileCollectionEntry(unittest.TestCase):
    def make_ocr_candidate(self):
        return OCRIdentificationCandidate(
            source_photo_id="photo-1",
            country="Canada",
            year="1945",
            denomination="5 cents",
            monarch="George VI",
            series_type="Nickel",
            confidence_level="HIGH",
            confidence_score=86,
            evidence=IdentificationEvidence(
                ocr_text_used="Canada 1945 5 cents George VI",
                validation_score=82,
                trust_level="HIGH",
                supporting_keywords=["Canada", "1945", "5 cents"],
            ),
        )

    def make_item(self, item_id="1", country="Canada", denomination="5 cents", year="1945", grade="VF-20"):
        return CoinItem(item_id, "", country, denomination, year, grade, "", "2026-06-22")

    def test_candidate_creation_from_ocr_candidate_tracks_fields_and_confidence(self):
        candidate = MobileCollectionEntryEngine().from_ocr_candidate(self.make_ocr_candidate(), acquisition_source=WORKFLOW_COIN_SHOW)

        self.assertEqual(candidate.country, "Canada")
        self.assertEqual(candidate.year, "1945")
        self.assertEqual(candidate.denomination, "5 cents")
        self.assertEqual(candidate.monarch, "George VI")
        self.assertEqual(candidate.acquisition_source, WORKFLOW_COIN_SHOW)
        self.assertGreater(candidate.field_confidence["country"], 0)
        self.assertEqual(candidate.review_status, "PENDING_REVIEW")
        self.assertIn("Manual review required", "; ".join(candidate.warnings))

    def test_ocr_integration_identifies_and_prepares_report(self):
        report = MobileCollectionEntryEngine().identify_and_prepare(raw_text="Canada 1945 5 cents George VI", acquisition_source=WORKFLOW_COIN_SHOW)

        self.assertIsInstance(report, CollectionEntryReport)
        self.assertEqual(report.candidate_count, 1)
        self.assertIn("Canada", report.candidates[0].title)
        self.assertEqual(report.review_count, 1)

    def test_collection_context_flags_duplicate_or_already_owned(self):
        engine = MobileCollectionEntryEngine(collection_items=[self.make_item(grade="VF-20")])

        candidate = engine.from_ocr_candidate(self.make_ocr_candidate())

        self.assertIn(candidate.collection_status, {"already owned", "duplicate", "review required"})
        self.assertIn("Manual review", "; ".join(candidate.warnings))

    def test_collection_context_flags_possible_upgrade(self):
        engine = MobileCollectionEntryEngine(collection_items=[self.make_item(grade="G-4")])
        candidate = CollectionEntryCandidate(candidate_id="entry-upgrade", country="Canada", year="1945", denomination="5 cents", grade_estimate="EF-40")

        engine._apply_collection_context(candidate)

        self.assertEqual(candidate.collection_status, "possible upgrade")

    def test_want_list_and_watchlist_contexts_are_reviewed(self):
        intent = LegacyWantListIntent(
            sheet_name="WANT_LIST", row_number=2, legacy_id="w1", target_coin="Newfoundland 50 cents 1904",
            priority="High", target_grade="VF-20", budget=125.0, why_wanted="Explicit target", status="Active", priority_score=75,
        )
        watchlist = Watchlist("Field", [WatchlistItem("Newfoundland", WATCH_TYPE_SERIES, "Newfoundland", WatchPriority.CRITICAL)])
        engine = MobileCollectionEntryEngine(want_list_intents=[intent], watchlists=[watchlist])
        ocr_candidate = OCRIdentificationEngine().identify(raw_text="Newfoundland 1904 50 cents").candidates[0]

        candidate = engine.from_ocr_candidate(ocr_candidate)

        self.assertIn(candidate.collection_status, {"want-list match", "watchlist match", "collection gap"})
        self.assertTrue(candidate.collection_context)

    def test_portfolio_impact_preview_is_preview_only(self):
        candidate = MobileCollectionEntryEngine(collection_items=[self.make_item()]).from_ocr_candidate(self.make_ocr_candidate())

        preview = "; ".join(candidate.portfolio_impact_preview)

        self.assertIn("Preview only", preview)
        self.assertIn("Collection value impact", preview)

    def test_review_workflow_prepares_approved_record_without_mutation(self):
        engine = MobileCollectionEntryEngine()
        candidate = engine.from_ocr_candidate(self.make_ocr_candidate())

        approved = engine.review_candidate(candidate, APPROVE, "Looks correct")
        rejected = engine.review_candidate(candidate, REJECT, "Bad OCR")
        review = engine.review_candidate(candidate, REVIEW, "Needs grade")

        self.assertEqual(approved.decision, APPROVE)
        self.assertEqual(approved.approved_entry_record["mutation_allowed"], "NO")
        self.assertEqual(rejected.decision, REJECT)
        self.assertEqual(review.decision, REVIEW)

    def test_report_exports_markdown_and_csv(self):
        engine = MobileCollectionEntryEngine()
        candidate = engine.from_ocr_candidate(self.make_ocr_candidate())
        review = engine.review_candidate(candidate, REVIEW)
        report = engine.report([candidate], [review])

        with tempfile.TemporaryDirectory() as temp_dir:
            md_path = os.path.join(temp_dir, "entry.md")
            csv_path = os.path.join(temp_dir, "entry.csv")
            self.assertTrue(report.export_markdown(md_path))
            self.assertTrue(report.export_csv(csv_path))
            with open(md_path, encoding="utf-8") as handle:
                self.assertIn("Mobile Collection Entry Report", handle.read())
            with open(csv_path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["row_type"], "candidate")
            self.assertEqual(rows[1]["row_type"], "review")


if __name__ == "__main__":
    unittest.main()
