"""Tests for v2.6 advisory OCR Experiments."""

import os
import tempfile
import unittest

from coin_collection import CoinItem
from mobile_companion import MobileCandidateEntry
from ocr_experiment import OCRConfidence, OCRExperiment, OCRResult, OCRSuggestionReport
from persistence_manager import AppState, PersistenceManager
from photo_assisted_entry import PhotoCandidate
from photo_vault import PhotoRecord


SAMPLE_TEXT = "Canada 1926 10 cents PCGS 1234567 prefix AB1234567"


def make_item(item_id, country, denomination, year, grade):
    return CoinItem(
        id=item_id,
        image_path="",
        country=country,
        denomination=denomination,
        year=year,
        grade=grade,
        notes="",
        date_added="2026-06-19",
    )


class TestOCRExperiment(unittest.TestCase):
    def test_ocr_result_creation(self):
        result = OCRResult("front.jpg", raw_text="Newfoundland 1904 50 cents")

        self.assertEqual(result.image_path, "front.jpg")
        self.assertIn("1904", result.raw_text)
        self.assertTrue(result.created_at)

    def test_suggestion_extraction_from_raw_text(self):
        report = OCRExperiment().run("front.jpg", raw_text=SAMPLE_TEXT)

        self.assertIsInstance(report, OCRSuggestionReport)
        self.assertIn("1926", report.possible_years)
        self.assertTrue(any("10" in value for value in report.possible_denominations))
        self.assertIn("Canada", report.possible_countries)
        self.assertIn("AB1234567", report.possible_note_prefixes)
        self.assertIn("1234567", report.possible_certification_numbers)
        self.assertTrue(report.manual_review_required)

    def test_confidence_calculation_high_medium_low(self):
        experiment = OCRExperiment()
        high = experiment.run("front.jpg", raw_text="Canada 1926 10 cents PCGS 1234567 AB1234567 clear label").confidence
        medium = experiment.run("front.jpg", raw_text="Canada 1926").confidence
        low = experiment.run("front.jpg", raw_text="").confidence

        self.assertIsInstance(high, OCRConfidence)
        self.assertEqual(high.level, "High")
        self.assertIn(medium.level, {"Medium", "Low"})
        self.assertEqual(low.level, "Low")

    def test_missing_image_is_graceful_and_review_only(self):
        report = OCRExperiment().run("missing-photo.jpg")

        self.assertEqual(report.confidence.level, "Low")
        self.assertTrue(report.manual_review_required)
        self.assertTrue(any("Image file not found" in warning for warning in report.warnings))
        self.assertTrue(any("No OCR text available" in warning for warning in report.warnings))

    def test_export_generation(self):
        report = OCRExperiment().run("front.jpg", raw_text=SAMPLE_TEXT)

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "ocr.csv")
            md_path = os.path.join(temp_dir, "ocr.md")

            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("manual_review_required", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("OCR Suggestion Report", handle.read())

    def test_persistence_round_trip_for_ocr_reports(self):
        report = OCRExperiment().run("front.jpg", raw_text=SAMPLE_TEXT)

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PersistenceManager(state_dir=os.path.join(temp_dir, "state"))
            saved = manager.save_state(AppState(
                ocr_results=[report.result],
                ocr_reports=[report],
            ))
            loaded = manager.load_state()

            self.assertTrue(saved.success)
            self.assertEqual(len(loaded.state.ocr_results), 1)
            self.assertEqual(len(loaded.state.ocr_reports), 1)
            self.assertIn("1926", loaded.state.ocr_reports[0].possible_years)
            self.assertTrue(loaded.state.ocr_reports[0].manual_review_required)

    def test_photo_candidate_integration(self):
        candidate = PhotoCandidate(
            title="Newfoundland 50 cents 1904",
            front_photo="front.jpg",
            reverse_photo="reverse.jpg",
        )

        report = OCRExperiment().from_photo_candidate(candidate, raw_text="Newfoundland 1904 50 cents ICCS XSZ431")

        self.assertEqual(report.result.image_path, "front.jpg")
        self.assertIn("Newfoundland", report.possible_countries)
        self.assertIn("1904", report.possible_years)
        self.assertIn("XSZ431", report.possible_certification_numbers)

    def test_photo_record_integration(self):
        record = PhotoRecord(
            file_path="coin_photos/references/wide-9.jpg",
            photo_type="Reference Photo",
            notes="Wide 9 reference",
        )

        report = OCRExperiment().from_photo_record(record, raw_text="Wide 9 1859 Canada")

        self.assertEqual(report.result.image_path, record.file_path)
        self.assertIn("1859", report.possible_years)
        self.assertIn("Canada", report.possible_countries)

    def test_mobile_candidate_integration(self):
        entry = MobileCandidateEntry(
            item_title="Canada 1937 25 cents",
            asking_price=18,
            photo_reference_id="mobile-photo.jpg",
        )

        report = OCRExperiment().from_mobile_candidate(entry, raw_text="Canada 1937 quarter")

        self.assertEqual(report.result.image_path, "mobile-photo.jpg")
        self.assertIn("1937", report.possible_years)
        self.assertTrue(report.manual_review_required)

    def test_no_collection_mutation(self):
        items = [
            make_item("1", "Canada", "10 cents", "1926", "F-12"),
            make_item("2", "Newfoundland", "50 cents", "1904", "VG-8"),
        ]
        before = [item.to_dict() for item in items]

        OCRExperiment().run("front.jpg", raw_text=SAMPLE_TEXT)

        self.assertEqual([item.to_dict() for item in items], before)

    def test_to_dict_round_trip(self):
        report = OCRExperiment().run("front.jpg", raw_text=SAMPLE_TEXT)
        restored = OCRSuggestionReport.from_dict(report.to_dict())

        self.assertEqual(restored.result.image_path, report.result.image_path)
        self.assertEqual(restored.confidence.level, report.confidence.level)
        self.assertEqual(restored.possible_years, report.possible_years)
        self.assertTrue(restored.manual_review_required)


if __name__ == "__main__":
    unittest.main()
