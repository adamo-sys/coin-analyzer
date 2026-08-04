"""Immutable UI-facing presentation models for reviewed advisory OCR.

Candidate confidence, evidence, raw text, and machine review status are
available only when presenting an ``OCRMetadataReport``.  Sprint 10
consolidation, conflict-resolution, final-projection, and session DTOs do not
retain those values.

Sprint 10 conflict-resolution DTOs also do not contain a resolution rationale.
The presentation models therefore expose ``resolution_rationale`` as ``None``
instead of inventing one.  Human field-review reasons remain available in
candidate views and accepted-value provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRFieldIdentity,
    OCRMetadataReport,
)
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
)
from capture_import.workflow_ocr_review_session import OCRReviewSessionResult
from capture_import.workflow_ocr_review_service import (
    OCRReviewMode,
    OCRReviewReconciliationService,
)


def _display_label(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _candidate_identity(candidate: OCRFieldCandidate) -> OCRFieldIdentity:
    return candidate.identity_key


def _review_identity(review: OCRFieldReview) -> OCRFieldIdentity:
    return review.identity_key


@dataclass(frozen=True, slots=True)
class OCRProvenanceView:
    """Display-ready bounded provenance for one accepted OCR value."""

    image_role: str
    image_role_label: str
    artifact_key: str
    provider_id: str
    original_value: str
    accepted_value: str
    decision: str
    decision_label: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_role": self.image_role,
            "image_role_label": self.image_role_label,
            "artifact_key": self.artifact_key,
            "provider_id": self.provider_id,
            "original_value": self.original_value,
            "accepted_value": self.accepted_value,
            "decision": self.decision,
            "decision_label": self.decision_label,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class OCRReviewCandidateView:
    """Display-ready state for one advisory OCR field candidate."""

    source_coin_id: str
    field_name: str
    field_label: str
    original_value: str
    raw_text: str
    image_role: str
    image_role_label: str
    artifact_key: str
    provider_id: str
    confidence_score: float
    evidence: tuple[str, ...]
    machine_review_status: str
    machine_review_label: str
    human_review_state: str | None
    human_review_label: str
    human_reviewed_value: str | None
    human_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_coin_id": self.source_coin_id,
            "field_name": self.field_name,
            "field_label": self.field_label,
            "original_value": self.original_value,
            "raw_text": self.raw_text,
            "image_role": self.image_role,
            "image_role_label": self.image_role_label,
            "artifact_key": self.artifact_key,
            "provider_id": self.provider_id,
            "confidence_score": self.confidence_score,
            "evidence": list(self.evidence),
            "machine_review_status": self.machine_review_status,
            "machine_review_label": self.machine_review_label,
            "human_review_state": self.human_review_state,
            "human_review_label": self.human_review_label,
            "human_reviewed_value": self.human_reviewed_value,
            "human_reason": self.human_reason,
        }


@dataclass(frozen=True, slots=True)
class OCRConsolidatedFieldView:
    """Display-ready agreed or conflicting consolidation state."""

    source_coin_id: str
    field_name: str
    field_label: str
    status: str
    status_label: str
    consolidated_value: str | None
    distinct_values: tuple[str, ...]
    provenance_count: int
    provenance: tuple[OCRProvenanceView, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_coin_id": self.source_coin_id,
            "field_name": self.field_name,
            "field_label": self.field_label,
            "status": self.status,
            "status_label": self.status_label,
            "consolidated_value": self.consolidated_value,
            "distinct_values": list(self.distinct_values),
            "provenance_count": self.provenance_count,
            "provenance": [item.to_dict() for item in self.provenance],
        }


@dataclass(frozen=True, slots=True)
class OCRConflictResolutionView:
    """Display-ready state for one consolidated conflict."""

    source_coin_id: str
    field_name: str
    field_label: str
    available_existing_values: tuple[str, ...]
    resolution_decision: str | None
    resolution_decision_label: str
    selected_or_corrected_value: str | None
    is_deferred: bool
    is_unresolved: bool
    resolution_rationale: str | None
    provenance_count: int
    provenance: tuple[OCRProvenanceView, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_coin_id": self.source_coin_id,
            "field_name": self.field_name,
            "field_label": self.field_label,
            "available_existing_values": list(
                self.available_existing_values
            ),
            "resolution_decision": self.resolution_decision,
            "resolution_decision_label": self.resolution_decision_label,
            "selected_or_corrected_value": (
                self.selected_or_corrected_value
            ),
            "is_deferred": self.is_deferred,
            "is_unresolved": self.is_unresolved,
            "resolution_rationale": self.resolution_rationale,
            "provenance_count": self.provenance_count,
            "provenance": [item.to_dict() for item in self.provenance],
        }


@dataclass(frozen=True, slots=True)
class OCRFinalFieldView:
    """Display-ready final or unresolved reviewed field."""

    source_coin_id: str
    field_name: str
    field_label: str
    final_value: str | None
    is_resolved: bool
    source_status: str
    source_status_label: str
    resolution_decision: str | None
    resolution_decision_label: str
    resolution_rationale: str | None
    provenance_count: int
    provenance: tuple[OCRProvenanceView, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_coin_id": self.source_coin_id,
            "field_name": self.field_name,
            "field_label": self.field_label,
            "final_value": self.final_value,
            "is_resolved": self.is_resolved,
            "source_status": self.source_status,
            "source_status_label": self.source_status_label,
            "resolution_decision": self.resolution_decision,
            "resolution_decision_label": self.resolution_decision_label,
            "resolution_rationale": self.resolution_rationale,
            "provenance_count": self.provenance_count,
            "provenance": [item.to_dict() for item in self.provenance],
        }


@dataclass(frozen=True, slots=True)
class OCRReviewSessionView:
    """Bounded display projection of an existing review-session result."""

    consolidated_fields: tuple[OCRConsolidatedFieldView, ...]
    conflict_resolutions: tuple[OCRConflictResolutionView, ...]
    final_fields: tuple[OCRFinalFieldView, ...]
    unresolved_fields: tuple[OCRFinalFieldView, ...]
    is_complete: bool
    accepted_candidate_count: int
    rejected_candidate_count: int
    deferred_candidate_count: int
    missing_candidate_count: int
    agreed_field_count: int
    conflict_field_count: int
    conflict_resolution_count: int
    final_field_count: int
    unresolved_field_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "consolidated_fields": [
                item.to_dict() for item in self.consolidated_fields
            ],
            "conflict_resolutions": [
                item.to_dict() for item in self.conflict_resolutions
            ],
            "final_fields": [
                item.to_dict() for item in self.final_fields
            ],
            "unresolved_fields": [
                item.to_dict() for item in self.unresolved_fields
            ],
            "summary": {
                "is_complete": self.is_complete,
                "accepted_candidate_count": self.accepted_candidate_count,
                "rejected_candidate_count": self.rejected_candidate_count,
                "deferred_candidate_count": self.deferred_candidate_count,
                "missing_candidate_count": self.missing_candidate_count,
                "agreed_field_count": self.agreed_field_count,
                "conflict_field_count": self.conflict_field_count,
                "conflict_resolution_count": (
                    self.conflict_resolution_count
                ),
                "final_field_count": self.final_field_count,
                "unresolved_field_count": self.unresolved_field_count,
            },
        }


class OCRReviewPresenter:
    """Pure stateless presenter for the immutable Sprint 9-10 OCR DTOs."""

    def present_candidates(
        self,
        *,
        source_report: OCRMetadataReport,
        review: OCRReportReview | None = None,
    ) -> tuple[OCRReviewCandidateView, ...]:
        if not isinstance(source_report, OCRMetadataReport):
            raise TypeError("source_report must be an OCRMetadataReport.")
        if review is not None and not isinstance(review, OCRReportReview):
            raise TypeError("review must be an OCRReportReview or None.")

        source_report.validate()
        if review is not None:
            review.validate()
            OCRReviewReconciliationService().reconcile(
                source_report=source_report,
                review=review,
                mode=OCRReviewMode.PARTIAL,
            )

        review_by_identity = (
            {}
            if review is None
            else {
                _review_identity(item): item
                for item in review.field_reviews
            }
        )

        candidates = tuple(
            sorted(
                source_report.candidates,
                key=lambda item: (
                    item.source_coin_id,
                    item.field_name,
                    item.image_role,
                    item.provider_id,
                    item.artifact_key,
                    item.normalized_value,
                ),
            )
        )
        return tuple(
            self._present_candidate(
                candidate,
                review_by_identity.get(_candidate_identity(candidate)),
            )
            for candidate in candidates
        )

    def present_consolidation(
        self,
        *,
        consolidation: OCRMetadataConsolidation,
    ) -> tuple[OCRConsolidatedFieldView, ...]:
        if not isinstance(consolidation, OCRMetadataConsolidation):
            raise TypeError(
                "consolidation must be an OCRMetadataConsolidation."
            )
        consolidation.validate()
        return tuple(
            self._present_consolidated_field(field)
            for field in consolidation.fields
        )

    def present_conflicts(
        self,
        *,
        consolidation: OCRMetadataConsolidation,
        resolutions: tuple[OCRResolvedConsolidatedField, ...] = (),
    ) -> tuple[OCRConflictResolutionView, ...]:
        if not isinstance(consolidation, OCRMetadataConsolidation):
            raise TypeError(
                "consolidation must be an OCRMetadataConsolidation."
            )
        if not isinstance(resolutions, tuple):
            raise TypeError("resolutions must be a tuple.")

        consolidation.validate()
        OCRFinalMetadataProjectionService().project(
            consolidation=consolidation,
            conflict_resolutions=resolutions,
        )
        resolution_by_identity: dict[
            tuple[str, str],
            OCRResolvedConsolidatedField,
        ] = {}
        for resolution in resolutions:
            if not isinstance(resolution, OCRResolvedConsolidatedField):
                raise TypeError(
                    "resolutions must contain "
                    "OCRResolvedConsolidatedField values."
                )
            resolution.validate()
            identity = (
                resolution.source_field.source_coin_id,
                resolution.source_field.field_name,
            )
            resolution_by_identity[identity] = resolution

        views: list[OCRConflictResolutionView] = []
        for field in consolidation.fields:
            if field.status is not OCRConsolidationStatus.CONFLICT:
                continue
            identity = (field.source_coin_id, field.field_name)
            resolution = resolution_by_identity.pop(identity, None)
            views.append(self._present_conflict(field, resolution))

        return tuple(views)

    def present_final_projection(
        self,
        *,
        projection: OCRFinalMetadataProjection,
    ) -> tuple[
        tuple[OCRFinalFieldView, ...],
        tuple[OCRFinalFieldView, ...],
    ]:
        if not isinstance(projection, OCRFinalMetadataProjection):
            raise TypeError(
                "projection must be an OCRFinalMetadataProjection."
            )
        projection.validate()
        return (
            tuple(
                self._present_final_field(field)
                for field in projection.final_fields
            ),
            tuple(
                self._present_final_field(field)
                for field in projection.unresolved_fields
            ),
        )

    def present_session(
        self,
        *,
        result: OCRReviewSessionResult,
    ) -> OCRReviewSessionView:
        if not isinstance(result, OCRReviewSessionResult):
            raise TypeError("result must be an OCRReviewSessionResult.")
        result.validate()

        consolidated_fields = self.present_consolidation(
            consolidation=result.consolidation
        )
        conflict_resolutions = self.present_conflicts(
            consolidation=result.consolidation,
            resolutions=result.conflict_resolutions,
        )
        final_fields, unresolved_fields = self.present_final_projection(
            projection=result.final_projection
        )
        return OCRReviewSessionView(
            consolidated_fields=consolidated_fields,
            conflict_resolutions=conflict_resolutions,
            final_fields=final_fields,
            unresolved_fields=unresolved_fields,
            is_complete=result.is_complete,
            accepted_candidate_count=result.reconciliation.accepted_count,
            rejected_candidate_count=result.reconciliation.rejected_count,
            deferred_candidate_count=result.reconciliation.deferred_count,
            missing_candidate_count=result.reconciliation.missing_count,
            agreed_field_count=result.consolidation.agreed_count,
            conflict_field_count=result.consolidation.conflict_count,
            conflict_resolution_count=result.conflict_resolution_count,
            final_field_count=result.final_field_count,
            unresolved_field_count=result.unresolved_field_count,
        )

    @staticmethod
    def _present_candidate(
        candidate: OCRFieldCandidate,
        review: OCRFieldReview | None,
    ) -> OCRReviewCandidateView:
        human_state = None if review is None else review.decision.value
        return OCRReviewCandidateView(
            source_coin_id=candidate.source_coin_id,
            field_name=candidate.field_name,
            field_label=_display_label(candidate.field_name),
            original_value=candidate.normalized_value,
            raw_text=candidate.raw_text,
            image_role=candidate.image_role,
            image_role_label=_display_label(candidate.image_role),
            artifact_key=candidate.artifact_key,
            provider_id=candidate.provider_id,
            confidence_score=float(candidate.confidence_score),
            evidence=candidate.evidence,
            machine_review_status=candidate.review_status.value,
            machine_review_label=_display_label(
                candidate.review_status.value
            ),
            human_review_state=human_state,
            human_review_label=(
                "Not Reviewed"
                if human_state is None
                else _display_label(human_state)
            ),
            human_reviewed_value=(
                None if review is None else review.reviewed_value
            ),
            human_reason=None if review is None else review.reason,
        )

    @staticmethod
    def _present_provenance(
        provenance: tuple[OCRAcceptedProvenance, ...],
    ) -> tuple[OCRProvenanceView, ...]:
        ordered = sorted(
            provenance,
            key=lambda item: (
                item.image_role,
                item.provider_id,
                item.artifact_key,
                item.accepted_value,
                item.original_value,
                item.decision.value,
                item.reason,
            ),
        )
        return tuple(
            OCRProvenanceView(
                image_role=item.image_role,
                image_role_label=_display_label(item.image_role),
                artifact_key=item.artifact_key,
                provider_id=item.provider_id,
                original_value=item.original_value,
                accepted_value=item.accepted_value,
                decision=item.decision.value,
                decision_label=_display_label(item.decision.value),
                reason=item.reason,
            )
            for item in ordered
        )

    def _present_consolidated_field(
        self,
        field: OCRConsolidatedField,
    ) -> OCRConsolidatedFieldView:
        provenance = self._present_provenance(field.provenance)
        return OCRConsolidatedFieldView(
            source_coin_id=field.source_coin_id,
            field_name=field.field_name,
            field_label=_display_label(field.field_name),
            status=field.status.value,
            status_label=_display_label(field.status.value),
            consolidated_value=field.consolidated_value,
            distinct_values=field.distinct_values,
            provenance_count=len(provenance),
            provenance=provenance,
        )

    def _present_conflict(
        self,
        field: OCRConsolidatedField,
        resolution: OCRResolvedConsolidatedField | None,
    ) -> OCRConflictResolutionView:
        provenance = self._present_provenance(field.provenance)
        decision = None if resolution is None else resolution.decision.value
        is_deferred = (
            resolution is not None
            and resolution.decision is OCRConflictResolutionDecision.DEFER
        )
        return OCRConflictResolutionView(
            source_coin_id=field.source_coin_id,
            field_name=field.field_name,
            field_label=_display_label(field.field_name),
            available_existing_values=field.distinct_values,
            resolution_decision=decision,
            resolution_decision_label=(
                "Not Resolved"
                if decision is None
                else _display_label(decision)
            ),
            selected_or_corrected_value=(
                None if resolution is None else resolution.resolved_value
            ),
            is_deferred=is_deferred,
            is_unresolved=(
                resolution is None
                or resolution.resolved_value is None
            ),
            resolution_rationale=None,
            provenance_count=len(provenance),
            provenance=provenance,
        )

    def _present_final_field(
        self,
        field: OCRFinalProjectedField,
    ) -> OCRFinalFieldView:
        source = field.source_field
        resolution = field.conflict_resolution
        provenance = self._present_provenance(source.provenance)
        decision = None if resolution is None else resolution.decision.value
        return OCRFinalFieldView(
            source_coin_id=source.source_coin_id,
            field_name=source.field_name,
            field_label=_display_label(source.field_name),
            final_value=field.final_value,
            is_resolved=field.is_resolved,
            source_status=source.status.value,
            source_status_label=_display_label(source.status.value),
            resolution_decision=decision,
            resolution_decision_label=(
                ""
                if decision is None
                else _display_label(decision)
            ),
            resolution_rationale=None,
            provenance_count=len(provenance),
            provenance=provenance,
        )
