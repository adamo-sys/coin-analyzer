"""Tests for immutable human OCR-review contracts."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError

from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)


def _review(
    *,
    decision: OCRReviewDecision = OCRReviewDecision.APPROVE,
    original_value: str = "1967",
    reviewed_value: str | None = "1967",
    field_name: str = "year",
    reason: str = "Confirmed visually.",
) -> OCRFieldReview:
    return OCRFieldReview(
        source_coin_id="coin-1",
        image_role="front",
        artifact_key="cropped-coin-1-front",
        provider_id="legacy-ocr",
        field_name=field_name,
        original_value=original_value,
        decision=decision,
        reviewed_value=reviewed_value,
        reason=reason,
    )


class OCRReviewDecisionTests(unittest.TestCase):
    def test_exact_decision_values(self) -> None:
        self.assertEqual(
            [decision.value for decision in OCRReviewDecision],
            ["APPROVE", "CORRECT", "REJECT", "DEFER"],
        )


class OCRFieldReviewTests(unittest.TestCase):
    def test_valid_approval(self) -> None:
        _review().validate()

    def test_approval_requires_matching_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "APPROVE"):
            _review(reviewed_value="1968").validate()

    def test_valid_correction(self) -> None:
        _review(
            decision=OCRReviewDecision.CORRECT,
            reviewed_value="1968",
        ).validate()

    def test_correction_requires_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "CORRECT"):
            _review(
                decision=OCRReviewDecision.CORRECT,
                reviewed_value=None,
            ).validate()

    def test_correction_must_change_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "different"):
            _review(
                decision=OCRReviewDecision.CORRECT,
                reviewed_value="1967",
            ).validate()

    def test_rejection_requires_no_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "REJECT"):
            _review(
                decision=OCRReviewDecision.REJECT,
                reviewed_value="1967",
            ).validate()

    def test_deferral_requires_no_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "DEFER"):
            _review(
                decision=OCRReviewDecision.DEFER,
                reviewed_value="1967",
            ).validate()

    def test_reason_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "reason"):
            _review(reason="").validate()

    def test_grade_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            _review(field_name="grade").validate()

    def test_unknown_field_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            _review(field_name="unknown").validate()

    def test_invalid_decision_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "decision"):
            OCRFieldReview(
                source_coin_id="coin-1",
                image_role="front",
                artifact_key="artifact-1",
                provider_id="legacy-ocr",
                field_name="year",
                original_value="1967",
                decision="APPROVE",  # type: ignore[arg-type]
                reviewed_value="1967",
                reason="Confirmed.",
            ).validate()

    def test_contract_is_frozen(self) -> None:
        review = _review()

        with self.assertRaises(FrozenInstanceError):
            review.reason = "Changed"  # type: ignore[misc]

    def test_serialization_is_json_safe_and_deterministic(self) -> None:
        review = _review(reason="Confirmed Montréal example.")

        first = review.to_dict()
        second = review.to_dict()

        self.assertEqual(first, second)
        self.assertEqual(
            json.loads(json.dumps(first, ensure_ascii=False)),
            first,
        )


class OCRReportReviewTests(unittest.TestCase):
    def test_valid_mixed_report_and_counts(self) -> None:
        approved = _review()

        corrected = OCRFieldReview(
            source_coin_id="coin-1",
            image_role="reverse",
            artifact_key="cropped-coin-1-reverse",
            provider_id="legacy-ocr",
            field_name="country",
            original_value="CAN",
            decision=OCRReviewDecision.CORRECT,
            reviewed_value="Canada",
            reason="Full country name is visible.",
        )

        rejected = OCRFieldReview(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            provider_id="legacy-ocr",
            field_name="mintmark",
            original_value="H",
            decision=OCRReviewDecision.REJECT,
            reviewed_value=None,
            reason="No mintmark is visible.",
        )

        report = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(approved, corrected, rejected),
        )

        report.validate()

        self.assertEqual(report.approved_count, 1)
        self.assertEqual(report.corrected_count, 1)
        self.assertEqual(report.rejected_count, 1)
        self.assertEqual(report.deferred_count, 0)
        self.assertTrue(report.is_complete)

    def test_deferred_review_makes_report_incomplete(self) -> None:
        report = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(
                _review(
                    decision=OCRReviewDecision.DEFER,
                    reviewed_value=None,
                ),
            ),
        )

        report.validate()

        self.assertTrue(report.has_deferred_reviews)
        self.assertFalse(report.is_complete)

    def test_rejection_is_a_completed_decision(self) -> None:
        report = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(
                _review(
                    decision=OCRReviewDecision.REJECT,
                    reviewed_value=None,
                ),
            ),
        )

        report.validate()

        self.assertTrue(report.is_complete)

    def test_empty_report_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            OCRReportReview(
                reviewer_id="collector-1",
                field_reviews=(),
            ).validate()

    def test_field_reviews_must_be_tuple(self) -> None:
        with self.assertRaisesRegex(TypeError, "tuple"):
            OCRReportReview(
                reviewer_id="collector-1",
                field_reviews=[_review()],  # type: ignore[arg-type]
            ).validate()

    def test_duplicate_review_target_is_rejected(self) -> None:
        review = _review()

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            OCRReportReview(
                reviewer_id="collector-1",
                field_reviews=(review, review),
            ).validate()

    def test_report_serialization_is_deterministic(self) -> None:
        report = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(_review(),),
        )

        first = report.to_dict()
        second = report.to_dict()

        self.assertEqual(first, second)
        self.assertEqual(first["summary"]["approved_count"], 1)
        self.assertTrue(first["summary"]["is_complete"])

    def test_report_is_frozen(self) -> None:
        report = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(_review(),),
        )

        with self.assertRaises(FrozenInstanceError):
            report.reviewer_id = "other"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()