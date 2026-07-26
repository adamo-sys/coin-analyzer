"""Tests for pure OCR human-review reconciliation."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError

from capture_import.workflow_ocr_models import OCRFieldCandidate, OCRMetadataReport
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_service import (
    AcceptedOCRField,
    OCRReviewMode,
    OCRReviewReconciliationError,
    OCRReviewReconciliationService,
)


def _candidate(
    *,
    source_coin_id: str = "coin-1",
    image_role: str = "front",
    artifact_key: str = "crop-front",
    provider_id: str = "legacy-ocr",
    field_name: str = "year",
    normalized_value: str = "1967",
) -> OCRFieldCandidate:
    return OCRFieldCandidate(
        source_coin_id=source_coin_id,
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id=provider_id,
        field_name=field_name,
        raw_text=normalized_value,
        normalized_value=normalized_value,
        confidence_score=0.90,
    )


def _review(
    candidate: OCRFieldCandidate,
    *,
    decision: OCRReviewDecision = OCRReviewDecision.APPROVE,
    reviewed_value: str | None = None,
    reason: str = "Confirmed visually.",
) -> OCRFieldReview:
    if decision is OCRReviewDecision.APPROVE and reviewed_value is None:
        reviewed_value = candidate.normalized_value

    return OCRFieldReview(
        source_coin_id=candidate.source_coin_id,
        image_role=candidate.image_role,
        artifact_key=candidate.artifact_key,
        provider_id=candidate.provider_id,
        field_name=candidate.field_name,
        original_value=candidate.normalized_value,
        decision=decision,
        reviewed_value=reviewed_value,
        reason=reason,
    )


def _report(*candidates: OCRFieldCandidate) -> OCRMetadataReport:
    ordered_candidates = tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.source_coin_id,
                item.field_name,
                item.image_role,
                item.normalized_value,
                item.provider_id,
                item.artifact_key,
            ),
        )
    )

    return OCRMetadataReport(
        provider_available=True,
        candidates=ordered_candidates,
    )


class OCRReviewReconciliationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = OCRReviewReconciliationService()

    def test_strict_approval_produces_accepted_field(self) -> None:
        candidate = _candidate()
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(_review(candidate),),
        )

        result = self.service.reconcile(
            source_report=_report(candidate),
            review=review,
            mode=OCRReviewMode.STRICT_COMPLETE,
        )

        self.assertTrue(result.is_complete)
        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.accepted_fields[0].accepted_value, "1967")

    def test_strict_correction_uses_reviewed_value(self) -> None:
        candidate = _candidate()
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(
                _review(
                    candidate,
                    decision=OCRReviewDecision.CORRECT,
                    reviewed_value="1968",
                ),
            ),
        )

        result = self.service.reconcile(
            source_report=_report(candidate),
            review=review,
            mode=OCRReviewMode.STRICT_COMPLETE,
        )

        self.assertEqual(result.accepted_fields[0].original_value, "1967")
        self.assertEqual(result.accepted_fields[0].accepted_value, "1968")

    def test_strict_rejection_counts_as_complete(self) -> None:
        candidate = _candidate()
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(
                _review(
                    candidate,
                    decision=OCRReviewDecision.REJECT,
                    reviewed_value=None,
                ),
            ),
        )

        result = self.service.reconcile(
            source_report=_report(candidate),
            review=review,
            mode=OCRReviewMode.STRICT_COMPLETE,
        )

        self.assertTrue(result.is_complete)
        self.assertEqual(result.rejected_count, 1)
        self.assertEqual(result.accepted_count, 0)

    def test_strict_missing_review_fails(self) -> None:
        first = _candidate()
        second = _candidate(
            image_role="reverse",
            artifact_key="crop-reverse",
            field_name="country",
            normalized_value="Canada",
        )
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(_review(first),),
        )

        with self.assertRaisesRegex(
            OCRReviewReconciliationError,
            "Missing: 1",
        ):
            self.service.reconcile(
                source_report=_report(first, second),
                review=review,
                mode=OCRReviewMode.STRICT_COMPLETE,
            )

    def test_strict_deferred_review_fails(self) -> None:
        candidate = _candidate()
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(
                _review(
                    candidate,
                    decision=OCRReviewDecision.DEFER,
                    reviewed_value=None,
                ),
            ),
        )

        with self.assertRaisesRegex(
            OCRReviewReconciliationError,
            "deferred: 1",
        ):
            self.service.reconcile(
                source_report=_report(candidate),
                review=review,
                mode=OCRReviewMode.STRICT_COMPLETE,
            )

    def test_partial_missing_review_is_recorded(self) -> None:
        first = _candidate()
        second = _candidate(
            image_role="reverse",
            artifact_key="crop-reverse",
            field_name="country",
            normalized_value="Canada",
        )
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(_review(first),),
        )

        result = self.service.reconcile(
            source_report=_report(first, second),
            review=review,
            mode=OCRReviewMode.PARTIAL,
        )

        self.assertFalse(result.is_complete)
        self.assertEqual(result.missing_count, 1)
        self.assertEqual(result.accepted_count, 1)

    def test_partial_deferred_review_is_recorded(self) -> None:
        candidate = _candidate()
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(
                _review(
                    candidate,
                    decision=OCRReviewDecision.DEFER,
                    reviewed_value=None,
                ),
            ),
        )

        result = self.service.reconcile(
            source_report=_report(candidate),
            review=review,
            mode=OCRReviewMode.PARTIAL,
        )

        self.assertFalse(result.is_complete)
        self.assertEqual(result.deferred_count, 1)

    def test_invented_review_target_fails(self) -> None:
        source_candidate = _candidate()
        invented = _candidate(source_coin_id="coin-2")
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(_review(invented),),
        )

        with self.assertRaisesRegex(
            OCRReviewReconciliationError,
            "does not exist",
        ):
            self.service.reconcile(
                source_report=_report(source_candidate),
                review=review,
                mode=OCRReviewMode.PARTIAL,
            )

    def test_wrong_original_value_fails_as_invented_target(self) -> None:
        candidate = _candidate()
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(
                OCRFieldReview(
                    source_coin_id=candidate.source_coin_id,
                    image_role=candidate.image_role,
                    artifact_key=candidate.artifact_key,
                    provider_id=candidate.provider_id,
                    field_name=candidate.field_name,
                    original_value="1968",
                    decision=OCRReviewDecision.APPROVE,
                    reviewed_value="1968",
                    reason="Confirmed.",
                ),
            ),
        )

        with self.assertRaisesRegex(
            OCRReviewReconciliationError,
            "does not exist",
        ):
            self.service.reconcile(
                source_report=_report(candidate),
                review=review,
                mode=OCRReviewMode.PARTIAL,
            )

    def test_duplicate_source_candidate_identity_fails(self) -> None:
        candidate = _candidate()
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(_review(candidate),),
        )

        with self.assertRaisesRegex(
            OCRReviewReconciliationError,
            "Duplicate source",
        ):
            self.service.reconcile(
                source_report=_report(candidate, candidate),
                review=review,
                mode=OCRReviewMode.PARTIAL,
            )

    def test_invalid_mode_type_fails(self) -> None:
        candidate = _candidate()
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(_review(candidate),),
        )

        with self.assertRaisesRegex(TypeError, "mode"):
            self.service.reconcile(
                source_report=_report(candidate),
                review=review,
                mode="PARTIAL",  # type: ignore[arg-type]
            )

    def test_source_order_is_preserved(self) -> None:
        year = _candidate()
        country = _candidate(
            image_role="reverse",
            artifact_key="crop-reverse",
            field_name="country",
            normalized_value="Canada",
        )
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(_review(country), _review(year)),
        )

        result = self.service.reconcile(
            source_report=_report(year, country),
            review=review,
            mode=OCRReviewMode.STRICT_COMPLETE,
        )

        self.assertEqual(
            [field.field_name for field in result.accepted_fields],
            ["country", "year"],
        )

    def test_same_field_from_multiple_images_remains_separate(self) -> None:
        front = _candidate()
        reverse = _candidate(
            image_role="reverse",
            artifact_key="crop-reverse",
        )
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(_review(front), _review(reverse)),
        )

        result = self.service.reconcile(
            source_report=_report(front, reverse),
            review=review,
            mode=OCRReviewMode.STRICT_COMPLETE,
        )

        self.assertEqual(result.accepted_count, 2)

    def test_result_serialization_is_json_safe(self) -> None:
        candidate = _candidate()
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(
                _review(candidate, reason="Confirmed MontrÃƒÂ©al example."),
            ),
        )

        result = self.service.reconcile(
            source_report=_report(candidate),
            review=review,
            mode=OCRReviewMode.STRICT_COMPLETE,
        )
        payload = result.to_dict()

        self.assertEqual(
            json.loads(json.dumps(payload, ensure_ascii=False)),
            payload,
        )

    def test_result_is_frozen(self) -> None:
        candidate = _candidate()
        review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(_review(candidate),),
        )
        result = self.service.reconcile(
            source_report=_report(candidate),
            review=review,
            mode=OCRReviewMode.STRICT_COMPLETE,
        )

        with self.assertRaises(FrozenInstanceError):
            result.reviewer_id = "other"  # type: ignore[misc]

    def test_accepted_field_rejects_non_accepting_decision(self) -> None:
        field = AcceptedOCRField(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="crop-front",
            provider_id="legacy-ocr",
            field_name="year",
            original_value="1967",
            accepted_value="1967",
            decision=OCRReviewDecision.REJECT,
            reason="Rejected.",
        )

        with self.assertRaisesRegex(ValueError, "APPROVE or CORRECT"):
            field.validate()


if __name__ == "__main__":
    unittest.main()
