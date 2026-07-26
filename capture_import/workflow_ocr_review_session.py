"""Pure orchestration of the reviewed OCR metadata workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionRequest,
    OCRConflictResolutionService,
    OCRResolvedConsolidatedField,
)
from capture_import.workflow_ocr_consolidation import (
    OCRConsolidatedField,
    OCRMetadataConsolidation,
    OCRMetadataConsolidationService,
)
from capture_import.workflow_ocr_final_projection import (
    OCRFinalMetadataProjection,
    OCRFinalMetadataProjectionService,
)
from capture_import.workflow_ocr_models import OCRMetadataReport
from capture_import.workflow_ocr_review_models import OCRReportReview
from capture_import.workflow_ocr_review_service import (
    OCRReviewMode,
    OCRReviewReconciliation,
    OCRReviewReconciliationService,
)


@dataclass(frozen=True, slots=True)
class OCRReviewSessionConflictResolutionRequest:
    """One explicit resolution request and its auditable conflict target."""

    field: OCRConsolidatedField
    request: OCRConflictResolutionRequest

    @property
    def identity(self) -> tuple[str, str]:
        return (self.field.source_coin_id, self.field.field_name)

    def validate(self) -> None:
        if not isinstance(self.field, OCRConsolidatedField):
            raise TypeError("field must be an OCRConsolidatedField.")
        if not isinstance(self.request, OCRConflictResolutionRequest):
            raise TypeError(
                "request must be an OCRConflictResolutionRequest."
            )

        self.field.validate()
        self.request.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "field": self.field.to_dict(),
            "request": self.request.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class OCRReviewSessionRequest:
    """Immutable inputs for one reviewed OCR workflow execution."""

    source_report: OCRMetadataReport
    review: OCRReportReview
    mode: OCRReviewMode
    conflict_resolution_requests: tuple[
        OCRReviewSessionConflictResolutionRequest,
        ...,
    ] = ()

    def validate(self) -> None:
        if not isinstance(self.source_report, OCRMetadataReport):
            raise TypeError(
                "source_report must be an OCRMetadataReport."
            )
        if not isinstance(self.review, OCRReportReview):
            raise TypeError("review must be an OCRReportReview.")
        if not isinstance(self.mode, OCRReviewMode):
            raise TypeError("mode must be an OCRReviewMode.")
        if not isinstance(self.conflict_resolution_requests, tuple):
            raise TypeError(
                "conflict_resolution_requests must be a tuple."
            )

        self.source_report.validate()
        self.review.validate()

        for resolution_request in self.conflict_resolution_requests:
            if not isinstance(
                resolution_request,
                OCRReviewSessionConflictResolutionRequest,
            ):
                raise TypeError(
                    "conflict_resolution_requests must contain "
                    "OCRReviewSessionConflictResolutionRequest values."
                )
            resolution_request.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "source_report": self.source_report.to_dict(),
            "review": self.review.to_dict(),
            "mode": self.mode.value,
            "conflict_resolution_requests": [
                resolution_request.to_dict()
                for resolution_request in self.conflict_resolution_requests
            ],
        }


@dataclass(frozen=True, slots=True)
class OCRReviewSessionResult:
    """Auditable immutable results from every reviewed OCR stage."""

    reconciliation: OCRReviewReconciliation
    consolidation: OCRMetadataConsolidation
    conflict_resolutions: tuple[OCRResolvedConsolidatedField, ...]
    final_projection: OCRFinalMetadataProjection

    @property
    def is_complete(self) -> bool:
        return (
            self.reconciliation.is_complete
            and self.final_projection.is_complete
        )

    @property
    def final_field_count(self) -> int:
        return self.final_projection.final_count

    @property
    def unresolved_field_count(self) -> int:
        return self.final_projection.unresolved_count

    @property
    def conflict_resolution_count(self) -> int:
        return len(self.conflict_resolutions)

    def validate(self) -> None:
        if not isinstance(self.reconciliation, OCRReviewReconciliation):
            raise TypeError(
                "reconciliation must be an OCRReviewReconciliation."
            )
        if not isinstance(self.consolidation, OCRMetadataConsolidation):
            raise TypeError(
                "consolidation must be an OCRMetadataConsolidation."
            )
        if not isinstance(self.conflict_resolutions, tuple):
            raise TypeError("conflict_resolutions must be a tuple.")
        if not isinstance(
            self.final_projection,
            OCRFinalMetadataProjection,
        ):
            raise TypeError(
                "final_projection must be an "
                "OCRFinalMetadataProjection."
            )

        self.reconciliation.validate()
        self.consolidation.validate()
        self.final_projection.validate()

        for resolution in self.conflict_resolutions:
            if not isinstance(resolution, OCRResolvedConsolidatedField):
                raise TypeError(
                    "conflict_resolutions must contain "
                    "OCRResolvedConsolidatedField values."
                )
            resolution.validate()

        expected_order = tuple(
            sorted(
                self.conflict_resolutions,
                key=lambda resolution: (
                    resolution.source_field.source_coin_id,
                    resolution.source_field.field_name,
                ),
            )
        )
        if self.conflict_resolutions != expected_order:
            raise ValueError(
                "conflict_resolutions are not in deterministic order."
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "reconciliation": self.reconciliation.to_dict(),
            "consolidation": self.consolidation.to_dict(),
            "conflict_resolutions": [
                resolution.to_dict()
                for resolution in self.conflict_resolutions
            ],
            "final_projection": self.final_projection.to_dict(),
            "summary": {
                "is_complete": self.is_complete,
                "final_field_count": self.final_field_count,
                "unresolved_field_count": self.unresolved_field_count,
                "conflict_resolution_count": (
                    self.conflict_resolution_count
                ),
            },
        }


class OCRReviewSessionService:
    """Stateless application service coordinating reviewed OCR stages."""

    def run(
        self,
        *,
        request: OCRReviewSessionRequest,
    ) -> OCRReviewSessionResult:
        if not isinstance(request, OCRReviewSessionRequest):
            raise TypeError(
                "request must be an OCRReviewSessionRequest."
            )
        request.validate()

        reconciliation = OCRReviewReconciliationService().reconcile(
            source_report=request.source_report,
            review=request.review,
            mode=request.mode,
        )
        consolidation = OCRMetadataConsolidationService().consolidate(
            reconciliation=reconciliation,
        )

        ordered_requests = tuple(
            sorted(
                request.conflict_resolution_requests,
                key=lambda resolution_request: (
                    resolution_request.field.source_coin_id,
                    resolution_request.field.field_name,
                ),
            )
        )
        resolution_service = OCRConflictResolutionService()
        conflict_resolutions = tuple(
            resolution_service.resolve(
                field=resolution_request.field,
                request=resolution_request.request,
            )
            for resolution_request in ordered_requests
        )

        final_projection = OCRFinalMetadataProjectionService().project(
            consolidation=consolidation,
            conflict_resolutions=conflict_resolutions,
        )

        result = OCRReviewSessionResult(
            reconciliation=reconciliation,
            consolidation=consolidation,
            conflict_resolutions=conflict_resolutions,
            final_projection=final_projection,
        )
        result.validate()
        return result
