"""Final collection-independent projection of reviewed OCR metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
    OCRResolvedConsolidatedField,
)
from capture_import.workflow_ocr_consolidation import (
    OCRConsolidatedField,
    OCRConsolidationStatus,
    OCRMetadataConsolidation,
)


def _identity(field: OCRConsolidatedField) -> tuple[str, str]:
    return (field.source_coin_id, field.field_name)


@dataclass(frozen=True, slots=True)
class OCRFinalProjectedField:
    """One final or unresolved field with its full review lineage."""

    source_field: OCRConsolidatedField
    final_value: str | None
    conflict_resolution: OCRResolvedConsolidatedField | None

    def validate(self) -> None:
        if not isinstance(self.source_field, OCRConsolidatedField):
            raise TypeError(
                "source_field must be an OCRConsolidatedField."
            )
        self.source_field.validate()

        if self.source_field.field_name == "grade":
            raise ValueError("Final OCR projection must not include grade.")

        if self.source_field.status is OCRConsolidationStatus.AGREED:
            if self.conflict_resolution is not None:
                raise ValueError(
                    "AGREED fields must not have a conflict resolution."
                )
            if self.final_value != self.source_field.consolidated_value:
                raise ValueError(
                    "AGREED final_value must equal consolidated_value."
                )
            return

        if self.conflict_resolution is None:
            if self.final_value is not None:
                raise ValueError(
                    "An unresolved conflict must not emit a final value."
                )
            return

        if not isinstance(
            self.conflict_resolution,
            OCRResolvedConsolidatedField,
        ):
            raise TypeError(
                "conflict_resolution must be an "
                "OCRResolvedConsolidatedField or None."
            )
        self.conflict_resolution.validate()

        if self.conflict_resolution.source_field != self.source_field:
            raise ValueError(
                "Conflict resolution source values and provenance must "
                "match source_field."
            )

        if (
            self.conflict_resolution.decision
            is OCRConflictResolutionDecision.DEFER
        ):
            if self.final_value is not None:
                raise ValueError("DEFER must not emit a final value.")
            return

        if self.final_value != self.conflict_resolution.resolved_value:
            raise ValueError(
                "Resolved conflict final_value must equal resolved_value."
            )

    @property
    def identity(self) -> tuple[str, str]:
        return _identity(self.source_field)

    @property
    def is_resolved(self) -> bool:
        return self.final_value is not None

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "source_field": self.source_field.to_dict(),
            "final_value": self.final_value,
            "conflict_resolution": (
                None
                if self.conflict_resolution is None
                else self.conflict_resolution.to_dict()
            ),
        }


@dataclass(frozen=True, slots=True)
class OCRFinalMetadataProjection:
    """Immutable final and unresolved reviewed OCR metadata."""

    final_fields: tuple[OCRFinalProjectedField, ...]
    unresolved_fields: tuple[OCRFinalProjectedField, ...]

    @property
    def final_count(self) -> int:
        return len(self.final_fields)

    @property
    def unresolved_count(self) -> int:
        return len(self.unresolved_fields)

    @property
    def is_complete(self) -> bool:
        return self.unresolved_count == 0

    def validate(self) -> None:
        for name, fields in (
            ("final_fields", self.final_fields),
            ("unresolved_fields", self.unresolved_fields),
        ):
            if not isinstance(fields, tuple):
                raise TypeError(f"{name} must be a tuple.")
            if any(
                not isinstance(field, OCRFinalProjectedField)
                for field in fields
            ):
                raise TypeError(
                    f"{name} must contain OCRFinalProjectedField values."
                )

            expected_order = tuple(
                sorted(fields, key=lambda field: field.identity)
            )
            if fields != expected_order:
                raise ValueError(
                    f"{name} are not in deterministic order."
                )

        identities: set[tuple[str, str]] = set()

        for field in self.final_fields:
            field.validate()
            if not field.is_resolved:
                raise ValueError(
                    "final_fields must emit final values."
                )
            if field.identity in identities:
                raise ValueError("Duplicate projected field identity.")
            identities.add(field.identity)

        for field in self.unresolved_fields:
            field.validate()
            if field.is_resolved:
                raise ValueError(
                    "unresolved_fields must not emit final values."
                )
            if field.identity in identities:
                raise ValueError("Duplicate projected field identity.")
            identities.add(field.identity)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "final_fields": [
                field.to_dict() for field in self.final_fields
            ],
            "unresolved_fields": [
                field.to_dict() for field in self.unresolved_fields
            ],
            "summary": {
                "final_count": self.final_count,
                "unresolved_count": self.unresolved_count,
                "is_complete": self.is_complete,
            },
        }


class OCRFinalMetadataProjectionService:
    """Pure stateless service for final reviewed OCR projection."""

    def project(
        self,
        *,
        consolidation: OCRMetadataConsolidation,
        conflict_resolutions: tuple[OCRResolvedConsolidatedField, ...],
    ) -> OCRFinalMetadataProjection:
        if not isinstance(consolidation, OCRMetadataConsolidation):
            raise TypeError(
                "consolidation must be an OCRMetadataConsolidation."
            )
        if not isinstance(conflict_resolutions, tuple):
            raise TypeError("conflict_resolutions must be a tuple.")

        consolidation.validate()
        source_by_identity = {
            _identity(field): field for field in consolidation.fields
        }

        resolution_by_identity: dict[
            tuple[str, str],
            OCRResolvedConsolidatedField,
        ] = {}

        for resolution in conflict_resolutions:
            if not isinstance(resolution, OCRResolvedConsolidatedField):
                raise TypeError(
                    "conflict_resolutions must contain "
                    "OCRResolvedConsolidatedField values."
                )
            if not isinstance(
                resolution.source_field,
                OCRConsolidatedField,
            ):
                raise TypeError(
                    "resolution source_field must be an "
                    "OCRConsolidatedField."
                )

            identity = _identity(resolution.source_field)
            if identity in resolution_by_identity:
                raise ValueError("Duplicate conflict resolution identity.")

            source_field = source_by_identity.get(identity)
            if source_field is None:
                raise ValueError("Invented conflict resolution target.")
            if source_field.status is not OCRConsolidationStatus.CONFLICT:
                raise ValueError(
                    "Conflict resolution targets a non-conflict field."
                )

            resolution.validate()
            if resolution.source_field != source_field:
                raise ValueError(
                    "Conflict resolution original distinct values and "
                    "provenance do not match consolidation."
                )

            resolution_by_identity[identity] = resolution

        final_fields: list[OCRFinalProjectedField] = []
        unresolved_fields: list[OCRFinalProjectedField] = []

        for source_field in consolidation.fields:
            resolution = resolution_by_identity.get(
                _identity(source_field)
            )

            if source_field.status is OCRConsolidationStatus.AGREED:
                projected = OCRFinalProjectedField(
                    source_field=source_field,
                    final_value=source_field.consolidated_value,
                    conflict_resolution=None,
                )
            elif (
                resolution is None
                or resolution.decision
                is OCRConflictResolutionDecision.DEFER
            ):
                projected = OCRFinalProjectedField(
                    source_field=source_field,
                    final_value=None,
                    conflict_resolution=resolution,
                )
            else:
                projected = OCRFinalProjectedField(
                    source_field=source_field,
                    final_value=resolution.resolved_value,
                    conflict_resolution=resolution,
                )

            projected.validate()
            if projected.is_resolved:
                final_fields.append(projected)
            else:
                unresolved_fields.append(projected)

        result = OCRFinalMetadataProjection(
            final_fields=tuple(final_fields),
            unresolved_fields=tuple(unresolved_fields),
        )
        result.validate()
        return result
