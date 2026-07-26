"""Tests for accepted OCR metadata consolidation."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError

from capture_import.workflow_ocr_consolidation import (
    OCRAcceptedProvenance,
    OCRConsolidatedField,
    OCRConsolidationStatus,
    OCRMetadataConsolidationService,
)
from capture_import.workflow_ocr_review_models import OCRReviewDecision
from capture_import.workflow_ocr_review_service import (
    AcceptedOCRField,
    OCRReviewMode,
    OCRReviewReconciliation,
)


def _accepted(
    *,
    source_coin_id: str = "coin-1",
    image_role: str = "front",
    artifact_key: str = "crop-front",
    provider_id: str = "legacy-ocr",
    field_name: str = "year",
    original_value: str = "1967",
    accepted_value: str = "1967",
    decision: OCRReviewDecision = OCRReviewDecision.APPROVE,
    reason: str = "Confirmed visually.",
) -> AcceptedOCRField:
    return AcceptedOCRField(
        source_coin_id=source_coin_id,
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id=provider_id,
        field_name=field_name,
        original_value=original_value,
        accepted_value=accepted_value,
        decision=decision,
        reason=reason,
    )


def _reconciliation(
    *fields: AcceptedOCRField,
) -> OCRReviewReconciliation:
    ordered_fields = tuple(
        sorted(
            fields,
            key=lambda item: (
                item.source_coin_id,
                item.field_name,
                item.image_role,
                item.accepted_value,
                item.provider_id,
                item.artifact_key,
            ),
        )
    )

    return OCRReviewReconciliation(
        reviewer_id="collector-1",
        mode=OCRReviewMode.STRICT_COMPLETE,
        accepted_fields=ordered_fields,
        rejected_candidate_keys=(),
        deferred_candidate_keys=(),
        missing_candidate_keys=(),
        has_source_conflicts=False,
    )


class OCRMetadataConsolidationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = OCRMetadataConsolidationService()

    def test_single_value_is_agreed(self) -> None:
        result = self.service.consolidate(
            reconciliation=_reconciliation(_accepted()),
        )

        self.assertEqual(len(result.fields), 1)
        field = result.fields[0]
        self.assertEqual(field.status, OCRConsolidationStatus.AGREED)
        self.assertEqual(field.consolidated_value, "1967")
        self.assertEqual(field.distinct_values, ("1967",))

    def test_multiple_identical_values_are_agreed(self) -> None:
        front = _accepted()
        reverse = _accepted(
            image_role="reverse",
            artifact_key="crop-reverse",
        )

        result = self.service.consolidate(
            reconciliation=_reconciliation(front, reverse),
        )

        field = result.fields[0]
        self.assertEqual(field.status, OCRConsolidationStatus.AGREED)
        self.assertEqual(field.consolidated_value, "1967")
        self.assertEqual(len(field.provenance), 2)

    def test_distinct_values_produce_conflict(self) -> None:
        first = _accepted()
        second = _accepted(
            image_role="reverse",
            artifact_key="crop-reverse",
            original_value="1968",
            accepted_value="1968",
        )

        result = self.service.consolidate(
            reconciliation=_reconciliation(first, second),
        )

        field = result.fields[0]
        self.assertEqual(field.status, OCRConsolidationStatus.CONFLICT)
        self.assertIsNone(field.consolidated_value)
        self.assertEqual(field.distinct_values, ("1967", "1968"))

    def test_three_distinct_values_remain_preserved(self) -> None:
        result = self.service.consolidate(
            reconciliation=_reconciliation(
                _accepted(),
                _accepted(
                    image_role="reverse",
                    artifact_key="crop-reverse",
                    original_value="1968",
                    accepted_value="1968",
                ),
                _accepted(
                    image_role="label",
                    artifact_key="crop-label",
                    original_value="1969",
                    accepted_value="1969",
                ),
            ),
        )

        self.assertEqual(
            result.fields[0].distinct_values,
            ("1967", "1968", "1969"),
        )

    def test_different_fields_remain_separate(self) -> None:
        year = _accepted()
        country = _accepted(
            field_name="country",
            original_value="Canada",
            accepted_value="Canada",
        )

        result = self.service.consolidate(
            reconciliation=_reconciliation(year, country),
        )

        self.assertEqual(
            [field.field_name for field in result.fields],
            ["country", "year"],
        )

    def test_different_coins_remain_separate(self) -> None:
        first = _accepted(source_coin_id="coin-1")
        second = _accepted(source_coin_id="coin-2")

        result = self.service.consolidate(
            reconciliation=_reconciliation(first, second),
        )

        self.assertEqual(
            [field.source_coin_id for field in result.fields],
            ["coin-1", "coin-2"],
        )

    def test_corrected_and_approved_provenance_are_preserved(self) -> None:
        approved = _accepted()
        corrected = _accepted(
            image_role="reverse",
            artifact_key="crop-reverse",
            original_value="196Z",
            accepted_value="1967",
            decision=OCRReviewDecision.CORRECT,
            reason="Final character corrected to 7.",
        )

        result = self.service.consolidate(
            reconciliation=_reconciliation(approved, corrected),
        )

        decisions = {
            item.decision
            for item in result.fields[0].provenance
        }

        self.assertEqual(
            decisions,
            {
                OCRReviewDecision.APPROVE,
                OCRReviewDecision.CORRECT,
            },
        )

    def test_provenance_order_is_deterministic(self) -> None:
        reverse = _accepted(
            image_role="reverse",
            artifact_key="crop-reverse",
        )
        front = _accepted()

        result = self.service.consolidate(
            reconciliation=_reconciliation(reverse, front),
        )

        self.assertEqual(
            [item.image_role for item in result.fields[0].provenance],
            ["front", "reverse"],
        )

    def test_serialization_is_json_safe_and_deterministic(self) -> None:
        result = self.service.consolidate(
            reconciliation=_reconciliation(
                _accepted(reason="Confirmed Montréal example."),
            ),
        )

        first = result.to_dict()
        second = result.to_dict()

        self.assertEqual(first, second)
        self.assertEqual(
            json.loads(json.dumps(first, ensure_ascii=False)),
            first,
        )

    def test_empty_reconciliation_produces_resolved_empty_result(self) -> None:
        result = self.service.consolidate(
            reconciliation=_reconciliation(),
        )

        self.assertEqual(result.fields, ())
        self.assertTrue(result.is_resolved)
        self.assertFalse(result.has_conflicts)

    def test_non_reconciliation_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "reconciliation"):
            self.service.consolidate(
                reconciliation=object(),  # type: ignore[arg-type]
            )

    def test_grade_field_is_rejected(self) -> None:
        field = OCRConsolidatedField(
            source_coin_id="coin-1",
            field_name="grade",
            status=OCRConsolidationStatus.AGREED,
            consolidated_value="MS-63",
            distinct_values=("MS-63",),
            provenance=(
                OCRAcceptedProvenance(
                    image_role="front",
                    artifact_key="crop-front",
                    provider_id="legacy-ocr",
                    original_value="MS-63",
                    accepted_value="MS-63",
                    decision=OCRReviewDecision.APPROVE,
                    reason="Visible on holder.",
                ),
            ),
        )

        with self.assertRaisesRegex(ValueError, "grade"):
            field.validate()

    def test_agreed_state_requires_one_distinct_value(self) -> None:
        field = OCRConsolidatedField(
            source_coin_id="coin-1",
            field_name="year",
            status=OCRConsolidationStatus.AGREED,
            consolidated_value="1967",
            distinct_values=("1967", "1968"),
            provenance=(
                OCRAcceptedProvenance(
                    image_role="front",
                    artifact_key="crop-front",
                    provider_id="legacy-ocr",
                    original_value="1967",
                    accepted_value="1967",
                    decision=OCRReviewDecision.APPROVE,
                    reason="Confirmed.",
                ),
                OCRAcceptedProvenance(
                    image_role="reverse",
                    artifact_key="crop-reverse",
                    provider_id="legacy-ocr",
                    original_value="1968",
                    accepted_value="1968",
                    decision=OCRReviewDecision.APPROVE,
                    reason="Confirmed.",
                ),
            ),
        )

        with self.assertRaisesRegex(ValueError, "exactly one"):
            field.validate()

    def test_conflict_state_requires_no_consolidated_value(self) -> None:
        field = OCRConsolidatedField(
            source_coin_id="coin-1",
            field_name="year",
            status=OCRConsolidationStatus.CONFLICT,
            consolidated_value="1967",
            distinct_values=("1967", "1968"),
            provenance=(
                OCRAcceptedProvenance(
                    image_role="front",
                    artifact_key="crop-front",
                    provider_id="legacy-ocr",
                    original_value="1967",
                    accepted_value="1967",
                    decision=OCRReviewDecision.APPROVE,
                    reason="Confirmed.",
                ),
                OCRAcceptedProvenance(
                    image_role="reverse",
                    artifact_key="crop-reverse",
                    provider_id="legacy-ocr",
                    original_value="1968",
                    accepted_value="1968",
                    decision=OCRReviewDecision.APPROVE,
                    reason="Confirmed.",
                ),
            ),
        )

        with self.assertRaisesRegex(ValueError, "None"):
            field.validate()

    def test_result_is_frozen(self) -> None:
        result = self.service.consolidate(
            reconciliation=_reconciliation(_accepted()),
        )

        with self.assertRaises(FrozenInstanceError):
            result.fields = ()  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
