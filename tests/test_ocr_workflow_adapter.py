"""Focused tests for Sprint 9 Unit 1B OCR workflow adapter."""

from __future__ import annotations

import json
import unittest

from capture_import.workflow_ocr_models import OCRReviewStatus
from ocr_experiment import OCRExperiment
from ocr_validation import OCRValidationEngine
from ocr_workflow_adapter import OCRWorkflowAdapter


def reports(raw_text: str):
    suggestion = OCRExperiment().run(
        image_path="front.jpg",
        raw_text=raw_text,
    )
    validation = OCRValidationEngine().validate(
        suggestion_report=suggestion
    )
    return suggestion, validation


class OCRWorkflowAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = OCRWorkflowAdapter()

    def test_clear_ocr_maps_to_review_only_candidates(self) -> None:
        suggestion, validation = reports(
            "Canada 1967 25 cents ICCS ABC123"
        )

        report = self.adapter.adapt(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            suggestion_report=suggestion,
            validation_report=validation,
        )

        report.validate()
        fields = {
            (candidate.field_name, candidate.normalized_value)
            for candidate in report.candidates
        }

        self.assertIn(("year", "1967"), fields)
        self.assertIn(("country", "Canada"), fields)
        self.assertTrue(
            any(
                field == "denomination" and "25" in value
                for field, value in fields
            )
        )
        self.assertIs(
            report.review_status,
            OCRReviewStatus.REVIEW_REQUIRED,
        )
        self.assertTrue(
            all(
                candidate.review_status
                is OCRReviewStatus.REVIEW_REQUIRED
                for candidate in report.candidates
            )
        )

    def test_observation_uses_artifact_identity_not_image_path(self) -> None:
        suggestion, validation = reports("Canada 1967 25 cents")

        report = self.adapter.adapt(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            suggestion_report=suggestion,
            validation_report=validation,
        )

        observation = report.observations[0]
        self.assertEqual(
            observation.artifact_key,
            "cropped-coin-1-front",
        )
        self.assertNotIn(
            suggestion.result.image_path,
            json.dumps(report.to_dict()),
        )

    def test_multiple_values_create_unresolved_conflict(self) -> None:
        suggestion, validation = reports(
            "Canada 1961 1967 25 cents"
        )

        report = self.adapter.adapt(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            suggestion_report=suggestion,
            validation_report=validation,
        )

        self.assertIs(report.review_status, OCRReviewStatus.CONFLICT)
        self.assertEqual(len(report.conflicts), 1)
        self.assertEqual(
            report.conflicts[0].candidate_values,
            ("1961", "1967"),
        )
        self.assertTrue(
            all(
                candidate.review_status is OCRReviewStatus.CONFLICT
                for candidate in report.candidates
                if candidate.field_name == "year"
            )
        )

    def test_output_is_deterministic_and_json_safe(self) -> None:
        suggestion, validation = reports(
            "Canada 1967 25 cents ICCS ABC123"
        )

        first = self.adapter.adapt(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            suggestion_report=suggestion,
            validation_report=validation,
        )
        second = self.adapter.adapt(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            suggestion_report=suggestion,
            validation_report=validation,
        )

        self.assertEqual(first, second)
        self.assertEqual(first.to_dict(), second.to_dict())
        json.dumps(first.to_dict(), allow_nan=False, sort_keys=True)

    def test_unavailable_provider_returns_nonfailing_report(self) -> None:
        report = self.adapter.unavailable()

        self.assertFalse(report.provider_available)
        self.assertEqual(report.observations, ())
        self.assertEqual(report.candidates, ())
        self.assertEqual(report.conflicts, ())
        self.assertIs(
            report.review_status,
            OCRReviewStatus.UNAVAILABLE,
        )

    def test_mismatched_validation_report_is_rejected(self) -> None:
        first, _ = reports("Canada 1967 25 cents")
        second, second_validation = reports("Canada 1968 10 cents")

        with self.assertRaises(ValueError):
            self.adapter.adapt(
                source_coin_id="coin-1",
                image_role="front",
                artifact_key="cropped-coin-1-front",
                suggestion_report=first,
                validation_report=second_validation,
            )


if __name__ == "__main__":
    unittest.main()