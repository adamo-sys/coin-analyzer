"""Tests for final reviewed OCR metadata projection."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError, replace

from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
    OCRResolvedConsolidatedField,
)
from capture_import.workflow_ocr_consolidation import (
    OCRAcceptedProvenance,
    OCRConsolidatedField,
    OCRConsolidationStatus,
    OCRMetadataConsolidation,
)
from capture_import.workflow_ocr_final_projection import (
    OCRFinalMetadataProjection,
    OCRFinalMetadataProjectionService,
    OCRFinalProjectedField,
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
        reason="Accepted during human OCR review.",
    )


def _agreed(
    *,
    source_coin_id: str = "coin-1",
    field_name: str = "country",
    value: str = "Canada",
) -> OCRConsolidatedField:
    return OCRConsolidatedField(
        source_coin_id=source_coin_id,
        field_name=field_name,
        status=OCRConsolidationStatus.AGREED,
        consolidated_value=value,
        distinct_values=(value,),
        provenance=(_provenance(value, image_role="front"),),
    )


def _conflict(
    *,
    source_coin_id: str = "coin-1",
    field_name: str = "year",
    values: tuple[str, str] = ("1967", "1968"),
) -> OCRConsolidatedField:
    return OCRConsolidatedField(
        source_coin_id=source_coin_id,
        field_name=field_name,
        status=OCRConsolidationStatus.CONFLICT,
        consolidated_value=None,
        distinct_values=values,
        provenance=(
            _provenance(values[0], image_role="front"),
            _provenance(values[1], image_role="reverse"),
        ),
    )


def _resolution(
    field: OCRConsolidatedField,
    *,
    decision: OCRConflictResolutionDecision = (
        OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
    ),
    value: str | None = "1967",
) -> OCRResolvedConsolidatedField:
    return OCRResolvedConsolidatedField(
        source_field=field,
        decision=decision,
        resolved_value=value,
    )


def _consolidation(
    *fields: OCRConsolidatedField,
) -> OCRMetadataConsolidation:
    return OCRMetadataConsolidation(
        fields=tuple(
            sorted(
                fields,
                key=lambda field: (
                    field.source_coin_id,
                    field.field_name,
                ),
            )
        )
    )


class OCRFinalMetadataProjectionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = OCRFinalMetadataProjectionService()

    def test_agreed_field_passes_through_unchanged(self) -> None:
        agreed = _agreed()

        result = self.service.project(
            consolidation=_consolidation(agreed),
            conflict_resolutions=(),
        )

        self.assertEqual(result.final_count, 1)
        self.assertEqual(result.unresolved_count, 0)
        self.assertTrue(result.is_complete)
        self.assertIs(result.final_fields[0].source_field, agreed)
        self.assertEqual(result.final_fields[0].final_value, "Canada")
        self.assertIsNone(result.final_fields[0].conflict_resolution)

    def test_resolved_conflict_produces_one_final_value(self) -> None:
        conflict = _conflict()
        resolution = _resolution(conflict, value="1968")

        result = self.service.project(
            consolidation=_consolidation(conflict),
            conflict_resolutions=(resolution,),
        )

        projected = result.final_fields[0]
        self.assertEqual(projected.final_value, "1968")
        self.assertIs(projected.conflict_resolution, resolution)
        self.assertEqual(projected.source_field.provenance, conflict.provenance)

    def test_corrected_conflict_preserves_resolution_rationale(self) -> None:
        conflict = _conflict()
        resolution = _resolution(
            conflict,
            decision=(
                OCRConflictResolutionDecision.ENTER_CORRECTED_VALUE
            ),
            value="1969",
        )

        result = self.service.project(
            consolidation=_consolidation(conflict),
            conflict_resolutions=(resolution,),
        )

        projected = result.final_fields[0]
        self.assertIs(projected.conflict_resolution, resolution)
        self.assertEqual(
            projected.conflict_resolution.decision,
            OCRConflictResolutionDecision.ENTER_CORRECTED_VALUE,
        )
        self.assertEqual(projected.final_value, "1969")

    def test_deferred_conflict_has_no_final_value(self) -> None:
        conflict = _conflict()
        deferred = _resolution(
            conflict,
            decision=OCRConflictResolutionDecision.DEFER,
            value=None,
        )

        result = self.service.project(
            consolidation=_consolidation(conflict),
            conflict_resolutions=(deferred,),
        )

        self.assertFalse(result.is_complete)
        self.assertEqual(result.final_count, 0)
        self.assertEqual(result.unresolved_count, 1)
        self.assertIsNone(result.unresolved_fields[0].final_value)
        self.assertIs(
            result.unresolved_fields[0].conflict_resolution,
            deferred,
        )

    def test_conflict_without_resolution_remains_unresolved(self) -> None:
        conflict = _conflict()

        result = self.service.project(
            consolidation=_consolidation(conflict),
            conflict_resolutions=(),
        )

        projected = result.unresolved_fields[0]
        self.assertIs(projected.source_field, conflict)
        self.assertIsNone(projected.final_value)
        self.assertIsNone(projected.conflict_resolution)

    def test_fields_are_deterministically_ordered(self) -> None:
        conflict_b = _conflict(
            source_coin_id="coin-2",
            field_name="year",
        )
        conflict_a = _conflict(
            source_coin_id="coin-1",
            field_name="year",
        )
        agreed = _agreed(
            source_coin_id="coin-1",
            field_name="country",
        )

        result = self.service.project(
            consolidation=_consolidation(
                conflict_b,
                conflict_a,
                agreed,
            ),
            conflict_resolutions=(
                _resolution(conflict_b),
                _resolution(conflict_a),
            ),
        )

        self.assertEqual(
            [field.identity for field in result.final_fields],
            [
                ("coin-1", "country"),
                ("coin-1", "year"),
                ("coin-2", "year"),
            ],
        )

    def test_duplicate_resolution_identities_are_rejected(self) -> None:
        conflict = _conflict()
        resolution = _resolution(conflict)

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.service.project(
                consolidation=_consolidation(conflict),
                conflict_resolutions=(resolution, resolution),
            )

    def test_invented_conflict_resolution_is_rejected(self) -> None:
        source = _conflict()
        invented = _conflict(source_coin_id="coin-invented")

        with self.assertRaisesRegex(ValueError, "Invented"):
            self.service.project(
                consolidation=_consolidation(source),
                conflict_resolutions=(_resolution(invented),),
            )

    def test_resolution_targeting_agreed_field_is_rejected(self) -> None:
        agreed = _agreed()
        invalid_resolution = OCRResolvedConsolidatedField(
            source_field=agreed,
            decision=(
                OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
            ),
            resolved_value="Canada",
        )

        with self.assertRaisesRegex(ValueError, "non-conflict"):
            self.service.project(
                consolidation=_consolidation(agreed),
                conflict_resolutions=(invalid_resolution,),
            )

    def test_mismatched_distinct_values_are_rejected(self) -> None:
        source = _conflict()
        mismatched = _conflict(values=("1967", "1969"))

        with self.assertRaisesRegex(ValueError, "do not match"):
            self.service.project(
                consolidation=_consolidation(source),
                conflict_resolutions=(_resolution(mismatched),),
            )

    def test_mismatched_provenance_is_rejected(self) -> None:
        source = _conflict()
        changed_provenance = replace(
            source,
            provenance=(
                replace(
                    source.provenance[0],
                    reason="Different human review rationale.",
                ),
                source.provenance[1],
            ),
        )

        with self.assertRaisesRegex(ValueError, "do not match"):
            self.service.project(
                consolidation=_consolidation(source),
                conflict_resolutions=(_resolution(changed_provenance),),
            )

    def test_projection_contract_rejects_duplicate_identities(self) -> None:
        agreed = _agreed()
        projected = OCRFinalProjectedField(
            source_field=agreed,
            final_value="Canada",
            conflict_resolution=None,
        )
        result = OCRFinalMetadataProjection(
            final_fields=(projected, projected),
            unresolved_fields=(),
        )

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            result.validate()

    def test_grade_is_prohibited(self) -> None:
        grade = _agreed(field_name="grade", value="MS-63")

        with self.assertRaisesRegex(ValueError, "grade"):
            self.service.project(
                consolidation=_consolidation(grade),
                conflict_resolutions=(),
            )

    def test_contracts_are_frozen_and_slotted(self) -> None:
        result = self.service.project(
            consolidation=_consolidation(_agreed()),
            conflict_resolutions=(),
        )
        projected = result.final_fields[0]

        with self.assertRaises(FrozenInstanceError):
            projected.final_value = "Other"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.final_fields = ()  # type: ignore[misc]
        with self.assertRaises(AttributeError):
            projected.extra = "no"  # type: ignore[attr-defined]

    def test_serialization_is_json_safe_and_deterministic(self) -> None:
        agreed = _agreed()
        conflict = _conflict()
        resolution = _resolution(conflict, value="1968")
        result = self.service.project(
            consolidation=_consolidation(agreed, conflict),
            conflict_resolutions=(resolution,),
        )

        first = result.to_dict()
        second = result.to_dict()

        self.assertEqual(first, second)
        self.assertEqual(json.loads(json.dumps(first)), first)
        self.assertNotIn("timestamp", first)
        self.assertEqual(first["summary"]["final_count"], 2)
        self.assertEqual(
            first["final_fields"][1]["source_field"]["provenance"],
            [item.to_dict() for item in conflict.provenance],
        )
        self.assertEqual(
            first["final_fields"][1]["conflict_resolution"]["decision"],
            "SELECT_EXISTING_VALUE",
        )

    def test_invalid_inputs_are_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "consolidation"):
            self.service.project(
                consolidation=object(),  # type: ignore[arg-type]
                conflict_resolutions=(),
            )
        with self.assertRaisesRegex(TypeError, "tuple"):
            self.service.project(
                consolidation=_consolidation(),
                conflict_resolutions=[],  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
