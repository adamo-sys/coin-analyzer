"""Shared test-only builders for OCR review model fixtures.

These helpers exist only to reduce repeated object construction in a few
OCR review test modules while preserving the same domain-level semantics.
"""

from __future__ import annotations

from capture_import.workflow_ocr_models import OCRFieldCandidate
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)


def candidate(
    *,
    source_coin_id: str = "coin-1",
    image_role: str = "front",
    artifact_key: str = "cropped-coin-1-front",
    provider_id: str = "legacy-ocr",
    field_name: str = "year",
    normalized_value: str = "1967",
    confidence_score: float = 0.90,
    raw_text: str | None = None,
) -> OCRFieldCandidate:
    return OCRFieldCandidate(
        source_coin_id=source_coin_id,
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id=provider_id,
        field_name=field_name,
        raw_text=raw_text if raw_text is not None else normalized_value,
        normalized_value=normalized_value,
        confidence_score=confidence_score,
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
