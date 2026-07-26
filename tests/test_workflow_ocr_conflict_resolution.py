"""Tests for explicit human resolution of OCR consolidation conflicts."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError

from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
    OCRConflictResolutionRequest,
    OCRConflictResolutionService,
    OCRResolvedConsolidatedField,
)
from capture_import.workflow_ocr_consolidation import (
    OCRAcceptedProvenance,
    OCRConsolidatedField,
    OCRConsolidationStatus,
)
from capture_import.workflow_ocr_review_models import OCRReviewDecision


def _provenance(
    value: str,
    *,
    image_role: str,
) -> OCRAcceptedProvenance:
    return OCRAcceptedProvenance(
        image_role=image_role,
        artifact_key=f"crop-{image_role}",
        provider_id="legacy-ocr",
        original_value=value,
        accepted_value=value,
        decision=OCRReviewDecision.APPROVE,
        reason="Confirmed during OCR review.",
    )


def _field(
    *,
    field_name: str = "year",
    status: OCRConsolidationStatus = OCRConsolidationStatus.CONFLICT,
) -> OCRConsolidatedField:
    if status is OCRConsolidationStatus.AGREED:
        return OCRConsolidatedField(
            source_coin_id="coin-1",
            field_name=field_name,
            status=status,
            consolidated_value="1967",
            distinct_values=("1967",),
            provenance=(_provenance("1967", image_role="front"),),
        )

    return OCRConsolidatedField(
        source_coin_id="coin-1",
        field_name=field_name,
        status=status,
        consolidated_value=None,
        distinct_values=("1967", "1968"),
        provenance=(
            _provenance("1967", image_role="front"),
            _provenance("1968", image_role="reverse"),
        ),
    )


class OCRConflictResolutionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = OCRConflictResolutionService()

    def test_select_existing_value_preserves_source_conflict(self) -> None:
        field = _field()

        result = self.service.resolve(
            field=field,
            request=OCRConflictResolutionRequest(
                decision=(
                    OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
                ),
                value="1968",
            ),
        )

        self.assertEqual(result.resolved_value, "1968")
        self.assertIs(result.source_field, field)
        self.assertEqual(
            result.source_field.distinct_values,
            ("1967", "1968"),
        )
        self.assertEqual(result.source_field.provenance, field.provenance)

    def test_select_existing_value_rejects_unknown_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "existing distinct"):
            self.service.resolve(
                field=_field(),
                request=OCRConflictResolutionRequest(
                    decision=(
                        OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
                    ),
                    value="1969",
                ),
            )

    def test_corrected_value_must_be_new_and_non_empty(self) -> None:
        for value, message in (
            ("", "non-empty"),
            ("   ", "non-empty"),
            ("1967", "differ"),
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, message):
                    self.service.resolve(
                        field=_field(),
                        request=OCRConflictResolutionRequest(
                            decision=(
                                OCRConflictResolutionDecision
                                .ENTER_CORRECTED_VALUE
                            ),
                            value=value,
                        ),
                    )

    def test_corrected_value_is_emitted_without_changing_source_values(self) -> None:
        field = _field()

        result = self.service.resolve(
            field=field,
            request=OCRConflictResolutionRequest(
                decision=(
                    OCRConflictResolutionDecision.ENTER_CORRECTED_VALUE
                ),
                value="1969",
            ),
        )

        self.assertEqual(result.resolved_value, "1969")
        self.assertEqual(field.distinct_values, ("1967", "1968"))
        self.assertEqual(
            {item.accepted_value for item in field.provenance},
            {"1967", "1968"},
        )

    def test_defer_emits_no_resolved_value(self) -> None:
        result = self.service.resolve(
            field=_field(),
            request=OCRConflictResolutionRequest(
                decision=OCRConflictResolutionDecision.DEFER,
                value=None,
            ),
        )

        self.assertIsNone(result.resolved_value)

    def test_defer_rejects_a_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "None"):
            self.service.resolve(
                field=_field(),
                request=OCRConflictResolutionRequest(
                    decision=OCRConflictResolutionDecision.DEFER,
                    value="1967",
                ),
            )

    def test_agreed_field_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "CONFLICT"):
            self.service.resolve(
                field=_field(status=OCRConsolidationStatus.AGREED),
                request=OCRConflictResolutionRequest(
                    decision=(
                        OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
                    ),
                    value="1967",
                ),
            )

    def test_grade_is_never_allowed(self) -> None:
        with self.assertRaisesRegex(ValueError, "grade"):
            self.service.resolve(
                field=_field(field_name="grade"),
                request=OCRConflictResolutionRequest(
                    decision=OCRConflictResolutionDecision.DEFER,
                    value=None,
                ),
            )

    def test_contracts_are_frozen(self) -> None:
        request = OCRConflictResolutionRequest(
            decision=OCRConflictResolutionDecision.DEFER,
            value=None,
        )
        result = self.service.resolve(field=_field(), request=request)

        with self.assertRaises(FrozenInstanceError):
            request.value = "1967"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.resolved_value = "1967"  # type: ignore[misc]

    def test_serialization_is_json_safe_and_preserves_provenance(self) -> None:
        result = self.service.resolve(
            field=_field(),
            request=OCRConflictResolutionRequest(
                decision=(
                    OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
                ),
                value="1967",
            ),
        )

        serialized = result.to_dict()

        self.assertEqual(
            json.loads(json.dumps(serialized, ensure_ascii=False)),
            serialized,
        )
        self.assertEqual(
            serialized["source_field"]["distinct_values"],
            ["1967", "1968"],
        )
        self.assertEqual(
            len(serialized["source_field"]["provenance"]),
            2,
        )
        self.assertNotIn("timestamp", serialized)

    def test_result_contract_enforces_decision_invariants(self) -> None:
        result = OCRResolvedConsolidatedField(
            source_field=_field(),
            decision=OCRConflictResolutionDecision.DEFER,
            resolved_value="1967",
        )

        with self.assertRaisesRegex(ValueError, "None"):
            result.validate()

    def test_invalid_contract_types_are_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "field"):
            self.service.resolve(
                field=object(),  # type: ignore[arg-type]
                request=OCRConflictResolutionRequest(
                    decision=OCRConflictResolutionDecision.DEFER,
                    value=None,
                ),
            )

        with self.assertRaisesRegex(TypeError, "request"):
            self.service.resolve(
                field=_field(),
                request=object(),  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
