"""Tests for v2.6.1 OCR Validation Layer."""

import os
import tempfile
import unittest

from ocr_experiment import OCRExperiment, OCRResult, OCRSuggestionReport
from ocr_validation import (
    OCRTrustLevel,
    OCRValidationEngine,
    OCRValidationExplanation,
    OCRValidationReport,
    OCRValidationScore,
)


def make_report(raw_text):
    return OCRExperiment().run("front.jpg", raw_text=raw_text)


class TestOCRValidationLayer(unittest.TestCase):
    def setUp(self):
        self.engine = OCRValidationEngine()

    def test_high_trust_clear_ocr(self):
        report = make_report("Canada 1926 10 cents PCGS 1234567 AB1234567 clear label")

        validation = self.engine.validate(suggestion_report=report)

        self.assertEqual(validation.trust_level, OCRTrustLevel.HIGH)
        self.assertGreaterEqual(validation.validation_score.score, 80)
        self.assertIn("Single year candidate detected", validation.validation_score.strengths)
        self.assertTrue(any("Manual Review Required" in warning for warning in validation.warnings))

    def test_low_trust_missing_critical_fields(self):
        report = make_report("blurred")

        validation = self.engine.validate(suggestion_report=report)

        self.assertEqual(validation.trust_level, OCRTrustLevel.LOW)
        self.assertTrue(any("No year candidate" in finding.message for finding in validation.findings))
        self.assertTrue(any("No denomination candidate" in finding.message for finding in validation.findings))
        self.assertTrue(any("No recognized country" in finding.message for finding in validation.findings))

    def test_year_validation_conflict_and_ambiguity(self):
        report = make_report("Canada 1926 1928 10 cents")

        validation = self.engine.validate(suggestion_report=report)

        self.assertTrue(any("Conflicting year candidates" in finding.message for finding in validation.findings))
        self.assertTrue(any("Ambiguous Year" in warning for warning in validation.warnings))
        self.assertIn(validation.trust_level, {OCRTrustLevel.MEDIUM, OCRTrustLevel.LOW})

    def test_denominations_conflict(self):
        report = make_report("Canada 1926 5 cents 50 cents")

        validation = self.engine.validate(suggestion_report=report)

        self.assertTrue(any(finding.category == "Denomination" for finding in validation.findings))
        self.assertTrue(any("Ambiguous Denomination" in warning for warning in validation.warnings))

    def test_country_validation_incomplete_country(self):
        result = OCRResult("front.jpg", raw_text="CANAOA 1926 10 cents")
        suggestion_report = OCRSuggestionReport(
            result=result,
            possible_years=["1926"],
            possible_denominations=["10 cents"],
            possible_countries=[],
            confidence=OCRExperiment().calculate_confidence(
                result.raw_text,
                {
                    "possible_years": ["1926"],
                    "possible_denominations": ["10 cents"],
                    "possible_countries": [],
                    "possible_note_prefixes": [],
                    "possible_certification_numbers": [],
                },
            ),
        )

        validation = self.engine.validate(suggestion_report=suggestion_report)

        self.assertTrue(any("CANAOA" in finding.message for finding in validation.findings))
        self.assertTrue(any("Ambiguous Country" in warning for warning in validation.warnings))

    def test_certification_validation_flags_malformed_values(self):
        report = make_report("Canada 1926 10 cents PCGS ABCD")

        validation = self.engine.validate(suggestion_report=report)

        self.assertTrue(any(finding.category == "Certification" for finding in validation.findings))
        self.assertTrue(any("certification" in weakness.lower() for weakness in validation.validation_score.weaknesses))

    def test_warning_generation_low_confidence(self):
        validation = self.engine.validate(suggestion_report=make_report(""))

        self.assertIn("Low Confidence OCR", validation.warnings)
        self.assertIn("Manual Review Required", validation.warnings)
        self.assertTrue(validation.review_recommendations)

    def test_validation_score_and_explanation_generation(self):
        validation = self.engine.validate(suggestion_report=make_report("Canada 1926 10 cents"))

        self.assertIsInstance(validation.validation_score, OCRValidationScore)
        self.assertIsInstance(validation.explanation, OCRValidationExplanation)
        self.assertIn("TRUST", validation.explanation.format_text())
        self.assertGreaterEqual(validation.validation_score.score, 0)
        self.assertLessEqual(validation.validation_score.score, 100)

    def test_export_generation(self):
        validation = self.engine.validate(suggestion_report=make_report("Canada 1926 10 cents PCGS 1234567"))

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "ocr-validation.csv")
            md_path = os.path.join(temp_dir, "ocr-validation.md")

            self.assertTrue(validation.export_csv(csv_path))
            self.assertTrue(validation.export_markdown(md_path))
            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("trust_level", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("OCR Validation Report", handle.read())

    def test_to_dict_round_trip(self):
        validation = self.engine.validate(suggestion_report=make_report("Canada 1926 10 cents PCGS 1234567"))

        restored = OCRValidationReport.from_dict(validation.to_dict())

        self.assertEqual(restored.trust_level, validation.trust_level)
        self.assertEqual(restored.validation_score.score, validation.validation_score.score)
        self.assertTrue(restored.review_recommendations)

    def test_existing_ocr_behavior_preserved(self):
        report = make_report("Canada 1926 10 cents")
        before = report.to_dict()

        self.engine.validate(suggestion_report=report)

        self.assertEqual(report.to_dict(), before)


if __name__ == "__main__":
    unittest.main()
