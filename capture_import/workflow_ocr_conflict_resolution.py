"""Explicit human resolution of one consolidated OCR conflict."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from capture_import.workflow_ocr_consolidation import (
    OCRConsolidatedField,
    OCRConsolidationStatus,
)


class OCRConflictResolutionDecision(str, Enum):
    """Allowed human decisions for an OCR consolidation conflict."""

    SELECT_EXISTING_VALUE = "SELECT_EXISTING_VALUE"
    ENTER_CORRECTED_VALUE = "ENTER_CORRECTED_VALUE"
    DEFER = "DEFER"


@dataclass(frozen=True, slots=True)
class OCRConflictResolutionRequest:
    """Immutable request to resolve or defer one OCR conflict."""

    decision: OCRConflictResolutionDecision
    value: str | None

    def validate(self) -> None:
        if not isinstance(self.decision, OCRConflictResolutionDecision):
            raise TypeError(
                "decision must be an OCRConflictResolutionDecision."
            )

        if self.decision is OCRConflictResolutionDecision.DEFER:
            if self.value is not None:
                raise ValueError("DEFER requires value to be None.")
            return

        if not isinstance(self.value, str):
            raise TypeError(
                f"{self.decision.value} requires value to be a string."
            )
        if not self.value.strip():
            raise ValueError(
                f"{self.decision.value} requires a non-empty value."
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "decision": self.decision.value,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class OCRResolvedConsolidatedField:
    """Immutable result preserving the original consolidated conflict."""

    source_field: OCRConsolidatedField
    decision: OCRConflictResolutionDecision
    resolved_value: str | None

    def validate(self) -> None:
        if not isinstance(self.source_field, OCRConsolidatedField):
            raise TypeError(
                "source_field must be an OCRConsolidatedField."
            )
        self.source_field.validate()

        if self.source_field.status is not OCRConsolidationStatus.CONFLICT:
            raise ValueError("Only CONFLICT fields may be resolved.")
        if self.source_field.field_name == "grade":
            raise ValueError("OCR conflict resolution must not include grade.")

        if not isinstance(self.decision, OCRConflictResolutionDecision):
            raise TypeError(
                "decision must be an OCRConflictResolutionDecision."
            )

        if (
            self.decision
            is OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
        ):
            if self.resolved_value not in self.source_field.distinct_values:
                raise ValueError(
                    "SELECT_EXISTING_VALUE requires one existing distinct "
                    "value."
                )
            return

        if (
            self.decision
            is OCRConflictResolutionDecision.ENTER_CORRECTED_VALUE
        ):
            if not isinstance(self.resolved_value, str):
                raise TypeError(
                    "ENTER_CORRECTED_VALUE requires resolved_value to be a "
                    "string."
                )
            if not self.resolved_value.strip():
                raise ValueError(
                    "ENTER_CORRECTED_VALUE requires a non-empty resolved "
                    "value."
                )
            if self.resolved_value in self.source_field.distinct_values:
                raise ValueError(
                    "ENTER_CORRECTED_VALUE must differ from all conflicting "
                    "values."
                )
            return

        if self.resolved_value is not None:
            raise ValueError("DEFER requires resolved_value to be None.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "source_field": self.source_field.to_dict(),
            "decision": self.decision.value,
            "resolved_value": self.resolved_value,
        }


class OCRConflictResolutionService:
    """Pure stateless service for one explicit human conflict decision."""

    def resolve(
        self,
        *,
        field: OCRConsolidatedField,
        request: OCRConflictResolutionRequest,
    ) -> OCRResolvedConsolidatedField:
        if not isinstance(field, OCRConsolidatedField):
            raise TypeError("field must be an OCRConsolidatedField.")
        if not isinstance(request, OCRConflictResolutionRequest):
            raise TypeError(
                "request must be an OCRConflictResolutionRequest."
            )

        field.validate()
        request.validate()

        if field.status is not OCRConsolidationStatus.CONFLICT:
            raise ValueError("Only CONFLICT fields may be resolved.")

        result = OCRResolvedConsolidatedField(
            source_field=field,
            decision=request.decision,
            resolved_value=request.value,
        )
        result.validate()
        return result
