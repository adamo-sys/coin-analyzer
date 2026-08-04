"""Shared test-only builders for OCR review model fixtures.

These helpers exist only to reduce repeated object construction in a few
OCR review test modules while preserving the same domain-level semantics.
"""

from __future__ import annotations

from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRReviewStatus,
)
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_persistence_models import (
    CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION,
    OCRReviewSessionEnvelope,
    OCRReviewSessionLifecycle,
    OCRStoredConflictResolution,
)
from capture_import.workflow_ocr_review_service import OCRReviewMode


def candidate(
    *,
    source_coin_id: str = "coin-1",
    image_role: str = "front",
    artifact_key: str = "cropped-coin-1-front",
    provider_id: str = "provider-1",
    field_name: str = "year",
    normalized_value: str = "1967",
    confidence_score: float = 90.0,
    raw_text: str | None = None,
    value: str | None = None,
    evidence: tuple[str, ...] | None = None,
) -> OCRFieldCandidate:
    effective_value = normalized_value if value is None else value
    return OCRFieldCandidate(
        source_coin_id=source_coin_id,
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id=provider_id,
        field_name=field_name,
        raw_text=raw_text if raw_text is not None else effective_value,
        normalized_value=effective_value,
        confidence_score=confidence_score,
        evidence=(
            evidence if evidence is not None else (f"{image_role} evidence",)
        ),
    )


def review(
    *,
    decision: OCRReviewDecision = OCRReviewDecision.APPROVE,
    original_value: str = "1967",
    reviewed_value: str | None = "1967",
    field_name: str = "year",
    reason: str = "Confirmed visually.",
    source_coin_id: str = "coin-1",
    image_role: str = "front",
    artifact_key: str = "cropped-coin-1-front",
    provider_id: str = "legacy-ocr",
) -> OCRFieldReview:
    return OCRFieldReview(
        source_coin_id=source_coin_id,
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id=provider_id,
        field_name=field_name,
        original_value=original_value,
        decision=decision,
        reviewed_value=reviewed_value,
        reason=reason,
    )


def report(
    *,
    reviewer_id: str = "collector-1",
    field_reviews: tuple[OCRFieldReview, ...] = (),
) -> OCRReportReview:
    return OCRReportReview(
        reviewer_id=reviewer_id,
        field_reviews=field_reviews,
    )


def field_review(
    candidate: OCRFieldCandidate,
    *,
    decision: OCRReviewDecision = OCRReviewDecision.APPROVE,
    reviewed_value: str | None = None,
    reason: str | None = None,
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
        reason=(
            f"Reviewed {candidate.artifact_key}."
            if reason is None
            else reason
        ),
    )


def report_payload(
    *,
    provider_available: bool = True,
    candidates: tuple[OCRFieldCandidate, ...] = (),
    review_status: OCRReviewStatus = OCRReviewStatus.REVIEW_REQUIRED,
) -> OCRMetadataReport:
    return OCRMetadataReport(
        provider_available=provider_available,
        candidates=tuple(
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
        ),
        review_status=review_status,
    )


def resolution(
    *,
    decision: OCRConflictResolutionDecision = (
        OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
    ),
    value: str | None = "1967",
    field_name: str = "year",
    source_coin_id: str = "coin-1",
) -> OCRStoredConflictResolution:
    return OCRStoredConflictResolution(
        source_coin_id=source_coin_id,
        field_name=field_name,
        decision=decision,
        value=value,
    )


def envelope(
    *,
    lifecycle: OCRReviewSessionLifecycle = (
        OCRReviewSessionLifecycle.IN_PROGRESS
    ),
    resolutions: tuple[OCRStoredConflictResolution, ...] = (),
    field_reviews: tuple[OCRFieldReview, ...] | None = None,
    report: OCRMetadataReport | None = None,
    session_id: str = "review-session-1",
    source_fingerprint: str = "a" * 64,
    reviewer_id: str = "collector-1",
    review_mode: OCRReviewMode = OCRReviewMode.PARTIAL,
) -> OCRReviewSessionEnvelope:
    front = candidate(
        value="1967",
        image_role="front",
        artifact_key="year-front",
    )
    reverse = candidate(
        value="1968",
        image_role="reverse",
        artifact_key="year-reverse",
    )
    default_report = report_payload(candidates=(front, reverse))
    default_reviews = (
        field_review(front),
        field_review(reverse),
    )
    return OCRReviewSessionEnvelope(
        schema_version=CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION,
        session_id=session_id,
        source_fingerprint=source_fingerprint,
        lifecycle_state=lifecycle,
        review_mode=review_mode,
        reviewer_id=reviewer_id,
        source_report=default_report if report is None else report,
        field_reviews=(
            default_reviews if field_reviews is None else field_reviews
        ),
        conflict_resolutions=resolutions,
    )
