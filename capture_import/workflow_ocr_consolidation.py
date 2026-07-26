"""Deterministic consolidation of accepted OCR metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from capture_import.workflow_ocr_review_models import OCRReviewDecision
from capture_import.workflow_ocr_review_service import (
    AcceptedOCRField,
    OCRReviewReconciliation,
)


class OCRConsolidationStatus(str, Enum):
    """Field-level consolidation outcome."""

    AGREED = "AGREED"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class OCRAcceptedProvenance:
    """Provenance retained for one accepted OCR field value."""

    image_role: str
    artifact_key: str
    provider_id: str
    original_value: str
    accepted_value: str
    decision: OCRReviewDecision
    reason: str

    def validate(self) -> None:
        if not isinstance(self.decision, OCRReviewDecision):
            raise TypeError("decision must be an OCRReviewDecision.")

        if self.decision not in {
            OCRReviewDecision.APPROVE,
            OCRReviewDecision.CORRECT,
        }:
            raise ValueError(
                "OCRAcceptedProvenance requires APPROVE or CORRECT."
            )

        for name, value in (
            ("image_role", self.image_role),
            ("artifact_key", self.artifact_key),
            ("provider_id", self.provider_id),
            ("original_value", self.original_value),
            ("accepted_value", self.accepted_value),
            ("reason", self.reason),
        ):
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string.")
            if not value.strip():
                raise ValueError(f"{name} must not be empty.")

        if (
            self.decision is OCRReviewDecision.APPROVE
            and self.accepted_value != self.original_value
        ):
            raise ValueError(
                "APPROVE provenance requires accepted_value to equal "
                "original_value."
            )

        if (
            self.decision is OCRReviewDecision.CORRECT
            and self.accepted_value == self.original_value
        ):
            raise ValueError(
                "CORRECT provenance requires accepted_value to differ from "
                "original_value."
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "image_role": self.image_role,
            "artifact_key": self.artifact_key,
            "provider_id": self.provider_id,
            "original_value": self.original_value,
            "accepted_value": self.accepted_value,
            "decision": self.decision.value,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class OCRConsolidatedField:
    """Deterministic field-level consolidation result."""

    source_coin_id: str
    field_name: str
    status: OCRConsolidationStatus
    consolidated_value: str | None
    distinct_values: tuple[str, ...]
    provenance: tuple[OCRAcceptedProvenance, ...]

    def validate(self) -> None:
        if not isinstance(self.status, OCRConsolidationStatus):
            raise TypeError("status must be an OCRConsolidationStatus.")

        if not isinstance(self.source_coin_id, str):
            raise TypeError("source_coin_id must be a string.")
        if not self.source_coin_id.strip():
            raise ValueError("source_coin_id must not be empty.")

        if not isinstance(self.field_name, str):
            raise TypeError("field_name must be a string.")
        if not self.field_name.strip():
            raise ValueError("field_name must not be empty.")
        if self.field_name == "grade":
            raise ValueError("OCR consolidation must not include grade.")

        if not isinstance(self.distinct_values, tuple):
            raise TypeError("distinct_values must be a tuple.")
        if not self.distinct_values:
            raise ValueError("distinct_values must not be empty.")
        if self.distinct_values != tuple(sorted(set(self.distinct_values))):
            raise ValueError(
                "distinct_values must be unique and deterministically sorted."
            )

        if not isinstance(self.provenance, tuple):
            raise TypeError("provenance must be a tuple.")
        if not self.provenance:
            raise ValueError("provenance must not be empty.")

        provenance_values: set[str] = set()
        for item in self.provenance:
            if not isinstance(item, OCRAcceptedProvenance):
                raise TypeError(
                    "provenance must contain OCRAcceptedProvenance values."
                )
            item.validate()
            provenance_values.add(item.accepted_value)

        if provenance_values != set(self.distinct_values):
            raise ValueError(
                "distinct_values must exactly match provenance values."
            )

        if self.status is OCRConsolidationStatus.AGREED:
            if len(self.distinct_values) != 1:
                raise ValueError(
                    "AGREED requires exactly one distinct value."
                )
            if self.consolidated_value != self.distinct_values[0]:
                raise ValueError(
                    "AGREED requires consolidated_value to equal the "
                    "single distinct value."
                )

        elif self.status is OCRConsolidationStatus.CONFLICT:
            if len(self.distinct_values) < 2:
                raise ValueError(
                    "CONFLICT requires at least two distinct values."
                )
            if self.consolidated_value is not None:
                raise ValueError(
                    "CONFLICT requires consolidated_value to be None."
                )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "source_coin_id": self.source_coin_id,
            "field_name": self.field_name,
            "status": self.status.value,
            "consolidated_value": self.consolidated_value,
            "distinct_values": list(self.distinct_values),
            "provenance": [item.to_dict() for item in self.provenance],
        }


@dataclass(frozen=True, slots=True)
class OCRMetadataConsolidation:
    """Immutable aggregate of consolidated OCR fields."""

    fields: tuple[OCRConsolidatedField, ...]

    def validate(self) -> None:
        if not isinstance(self.fields, tuple):
            raise TypeError("fields must be a tuple.")

        expected_order = tuple(
            sorted(
                self.fields,
                key=lambda item: (
                    item.source_coin_id,
                    item.field_name,
                ),
            )
        )
        if self.fields != expected_order:
            raise ValueError("fields are not in deterministic order.")

        identities: set[tuple[str, str]] = set()
        for field in self.fields:
            if not isinstance(field, OCRConsolidatedField):
                raise TypeError(
                    "fields must contain OCRConsolidatedField values."
                )
            field.validate()
            identity = (field.source_coin_id, field.field_name)
            if identity in identities:
                raise ValueError("Duplicate consolidated field identity.")
            identities.add(identity)

    @property
    def agreed_count(self) -> int:
        return sum(
            field.status is OCRConsolidationStatus.AGREED
            for field in self.fields
        )

    @property
    def conflict_count(self) -> int:
        return sum(
            field.status is OCRConsolidationStatus.CONFLICT
            for field in self.fields
        )

    @property
    def has_conflicts(self) -> bool:
        return self.conflict_count > 0

    @property
    def is_resolved(self) -> bool:
        return not self.has_conflicts

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "fields": [field.to_dict() for field in self.fields],
            "summary": {
                "agreed_count": self.agreed_count,
                "conflict_count": self.conflict_count,
                "has_conflicts": self.has_conflicts,
                "is_resolved": self.is_resolved,
            },
        }


def _to_provenance(field: AcceptedOCRField) -> OCRAcceptedProvenance:
    return OCRAcceptedProvenance(
        image_role=field.image_role,
        artifact_key=field.artifact_key,
        provider_id=field.provider_id,
        original_value=field.original_value,
        accepted_value=field.accepted_value,
        decision=field.decision,
        reason=field.reason,
    )


class OCRMetadataConsolidationService:
    """Stateless accepted-OCR consolidation service."""

    def consolidate(
        self,
        *,
        reconciliation: OCRReviewReconciliation,
    ) -> OCRMetadataConsolidation:
        if not isinstance(reconciliation, OCRReviewReconciliation):
            raise TypeError(
                "reconciliation must be an OCRReviewReconciliation."
            )

        reconciliation.validate()

        grouped: dict[tuple[str, str], list[AcceptedOCRField]] = {}
        for field in reconciliation.accepted_fields:
            key = (field.source_coin_id, field.field_name)
            grouped.setdefault(key, []).append(field)

        consolidated_fields: list[OCRConsolidatedField] = []

        for (source_coin_id, field_name), accepted_fields in sorted(
            grouped.items(),
            key=lambda item: item[0],
        ):
            provenance = tuple(
                sorted(
                    (_to_provenance(field) for field in accepted_fields),
                    key=lambda item: (
                        item.accepted_value,
                        item.image_role,
                        item.provider_id,
                        item.artifact_key,
                        item.original_value,
                        item.decision.value,
                        item.reason,
                    ),
                )
            )

            distinct_values = tuple(
                sorted({item.accepted_value for item in provenance})
            )

            if len(distinct_values) == 1:
                status = OCRConsolidationStatus.AGREED
                consolidated_value: str | None = distinct_values[0]
            else:
                status = OCRConsolidationStatus.CONFLICT
                consolidated_value = None

            consolidated_field = OCRConsolidatedField(
                source_coin_id=source_coin_id,
                field_name=field_name,
                status=status,
                consolidated_value=consolidated_value,
                distinct_values=distinct_values,
                provenance=provenance,
            )
            consolidated_field.validate()
            consolidated_fields.append(consolidated_field)

        result = OCRMetadataConsolidation(
            fields=tuple(consolidated_fields),
        )
        result.validate()
        return result
