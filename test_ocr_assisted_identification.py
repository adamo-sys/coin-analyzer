import os
import tempfile
import unittest

from coin_collection import CoinItem
from legacy_portfolio_importer import LegacyWantListIntent
from ocr_assisted_identification import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    OCRIdentificationEngine,
    OCRIdentificationReport,
    REVIEW_REQUIRED,
)
from ocr_validation import OCRValidationEngine
from photo_capture_workflow import ROLE_COIN_FRONT, PhotoCaptureWorkflow
from watchlist_engine import WATCH_TYPE_KEYWORD, WatchPriority, Watchlist, WatchlistItem


class TestOCRAssistedIdentification(unittest.TestCase):
    def test_ocr_candidate_generation_extracts_core_fields(self):
        report = OCRIdentificationEngine().identify(
            raw_text="Canada 1945 5 cents George VI silver ICCS MS12345 Near 6"
        )
        candidate = report.candidates[0]

        self.assertEqual(candidate.year, "1945")
        self.assertEqual(candidate.country, "Canada")
        self.assertEqual(candidate.denomination, "5 cents")
        self.assertEqual(candidate.monarch, "George VI")
        self.assertEqual(candidate.certification_number, "MS12345")
        self.assertIn("Near 6", candidate.possible_variety_keywords)
        self.assertEqual(candidate.review_status, REVIEW_REQUIRED)

    def test_confidence_scoring_uses_validation_and_evidence(self):
        high = OCRIdentificationEngine().identify(
            raw_text="Canada 1945 5 cents George VI silver ICCS MS12345 Near 6"
        ).candidates[0]
        low = OCRIdentificationEngine().identify(raw_text="blur").candidates[0]

        self.assertIn(high.confidence_level, {CONFIDENCE_HIGH, CONFIDENCE_MEDIUM})
        self.assertGreater(high.confidence_score, low.confidence_score)
        self.assertEqual(low.confidence_level, CONFIDENCE_LOW)

    def test_evidence_reports_supporting_conflicts_and_missing_fields(self):
        candidate = OCRIdentificationEngine().identify(
            raw_text="Canada 1945 1946 5 cents 50 cents George VI"
        ).candidates[0]

        self.assertTrue(candidate.evidence.supporting_keywords)
        self.assertTrue(candidate.evidence.conflicts_detected)
        self.assertEqual(candidate.evidence.missing_evidence, [])

    def test_ocr_validation_report_integration(self):
        validation = OCRValidationEngine().validate_captured_photo(
            type("Photo", (), {"file_path": "front.jpg"})(),
            raw_text="Newfoundland 1904 50 cents Edward VII"
        )

        report = OCRIdentificationEngine().identify_from_validation_report(validation, source_photo_id="photo-1")

        self.assertEqual(report.candidates[0].source_photo_id, "photo-1")
        self.assertEqual(report.candidates[0].country, "Newfoundland")
        self.assertIn("50 cents", report.candidates[0].denomination)

    def test_photo_capture_integration(self):
        workflow = PhotoCaptureWorkflow()
        session = workflow.start_session(subject="Field coin")
        photo = session.add_photo("front.jpg", ROLE_COIN_FRONT)

        report = OCRIdentificationEngine().identify_from_captured_photo(
            photo,
            raw_text="Newfoundland 1904 50 cents Edward VII"
        )

        self.assertEqual(report.candidates[0].source_photo_id, photo.photo_id)
        self.assertIn(ROLE_COIN_FRONT, report.candidates[0].evidence.supporting_keywords)

    def test_session_pipeline_generates_candidates_for_photos(self):
        workflow = PhotoCaptureWorkflow()
        session = workflow.capture_coin_pair("Canada 1911 10 cents", "front.jpg", "back.jpg")
        raw_text = {
            session.photos[0].photo_id: "Canada 1911 10 cents George V",
            session.photos[1].photo_id: "Canada 1911 10 cents reverse",
        }

        report = OCRIdentificationEngine().identify_from_session(session, raw_text)

        self.assertEqual(report.candidate_count, 2)
        self.assertTrue(all(candidate.review_status == REVIEW_REQUIRED for candidate in report.candidates))

    def test_collection_context_marks_existing_and_gap_candidates(self):
        items = [
            CoinItem("1", "", "Canada", "5 cents", "1945", "VF-20", "", "2026-06-22"),
            CoinItem("2", "", "Canada", "10 cents", "1910", "F-12", "", "2026-06-22"),
        ]
        engine = OCRIdentificationEngine(collection_items=items)

        owned = engine.identify(raw_text="Canada 1945 5 cents George VI").candidates[0]
        gap = engine.identify(raw_text="Canada 1911 10 cents George V").candidates[0]

        self.assertIn(owned.collection_status, {"already owned", "needs review"})
        self.assertIn(gap.collection_status, {"collection gap", "needs review"})

    def test_want_list_and_watchlist_context(self):
        intent = LegacyWantListIntent(
            sheet_name="WANT_LIST",
            row_number=2,
            legacy_id="w1",
            target_coin="Newfoundland 1904 50 cents",
            priority="High",
            target_grade="VF-20",
            budget=125,
            why_wanted="Explicit target",
            status="Active",
            priority_score=75,
        )
        watchlist = Watchlist("OCR watches", [
            WatchlistItem("Newfoundland", WATCH_TYPE_KEYWORD, "Newfoundland", WatchPriority.HIGH)
        ])

        candidate = OCRIdentificationEngine(
            want_list_intents=[intent],
            watchlists=[watchlist],
        ).identify(raw_text="Newfoundland 1904 50 cents Edward VII").candidates[0]

        self.assertIn(candidate.collection_status, {"want-list match", "watchlist match", "collection gap"})
        self.assertTrue(candidate.watchlist_matches)

    def test_export_generation(self):
        report = OCRIdentificationEngine().identify(raw_text="Canada 1945 5 cents George VI")

        self.assertIsInstance(report, OCRIdentificationReport)
        self.assertIn("OCR-Assisted Identification Report", report.format_markdown())

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "ocr_identification.csv")
            md_path = os.path.join(temp_dir, "ocr_identification.md")
            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, encoding="utf-8") as handle:
                self.assertIn("confidence_level", handle.readline())
            with open(md_path, encoding="utf-8") as handle:
                self.assertIn("Manual review required", handle.read())


if __name__ == "__main__":
    unittest.main()
