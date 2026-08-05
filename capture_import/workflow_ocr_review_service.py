"""Pure reconciliation of human OCR reviews against OCR metadata reports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRFieldIdentity,
    OCRMetadataReport,
)
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)

CandidateKey = OCRFieldIdentity


class OCRReviewMode(str, Enum):
    """Completeness mode for OCR review reconciliation."""

    STRICT_COMPLETE = "STRICT_COMPLETE"
    PARTIAL = "PARTIAL"


class OCRReviewReconciliationError(ValueError):
    """Raised when an OCR review cannot be reconciled safely."""


@dataclass(frozen=True, slots=True)
class AcceptedOCRField:
    """One human-approved or human-corrected OCR metadata value."""

    source_coin_id: str
    image_role: str
    artifact_key: str
    provider_id: str
    field_name: str
    original_value: str
    accepted_value: str
    decision: OCRReviewDecision
    reason: str

    def validate(self) -> None:
        if self.decision not in {
            OCRReviewDecision.APPROVE,
            OCRReviewDecision.CORRECT,
        }:
            raise ValueError("AcceptedOCRField requires APPROVE or CORRECT.")
        if self.field_name == "grade":
            raise ValueError("OCR review must not accept grade fields.")
        if (
            self.decision is OCRReviewDecision.APPROVE
            and self.accepted_value != self.original_value
        ):
            raise ValueError(
                "APPROVE requires accepted_value to equal original_value."
            )
        if (
            self.decision is OCRReviewDecision.CORRECT
            and self.accepted_value == self.original_value
        ):
            raise ValueError(
                "CORRECT requires accepted_value to differ from original_value."
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "source_coin_id": self.source_coin_id,
            "image_role": self.image_role,
            "artifact_key": self.artifact_key,
            "provider_id": self.provider_id,
            "field_name": self.field_name,
            "original_value": self.original_value,
            "accepted_value": self.accepted_value,
            "decision": self.decision.value,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class OCRReviewReconciliation:
    """Immutable result of reconciling a review against OCR candidates."""

    reviewer_id: str
    mode: OCRReviewMode
    accepted_fields: tuple[AcceptedOCRField, ...]
    rejected_candidate_keys: tuple[CandidateKey, ...]
    deferred_candidate_keys: tuple[CandidateKey, ...]
    missing_candidate_keys: tuple[CandidateKey, ...]
    has_source_conflicts: bool

    @property
    def accepted_count(self) -> int:
        return len(self.accepted_fields)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected_candidate_keys)

    @property
    def deferred_count(self) -> int:
        return len(self.deferred_candidate_keys)

    @property
    def missing_count(self) -> int:
        return len(self.missing_candidate_keys)

    @property
    def is_complete(self) -> bool:
        return self.deferred_count == 0 and self.missing_count == 0

    @staticmethod
    def _key_to_dict(key: CandidateKey) -> dict[str, str]:
        return {
            "source_coin_id": key[0],
            "image_role": key[1],
            "artifact_key": key[2],
            "provider_id": key[3],
            "field_name": key[4],
            "original_value": key[5],
        }

    def validate(self) -> None:
        if not isinstance(self.mode, OCRReviewMode):
            raise TypeError("mode must be an OCRReviewMode.")
        if not isinstance(self.accepted_fields, tuple):
            raise TypeError("accepted_fields must be a tuple.")
        for field in self.accepted_fields:
            if not isinstance(field, AcceptedOCRField):
                raise TypeError(
                    "accepted_fields must contain AcceptedOCRField values."
                )
            field.validate()
        for name, keys in (
            ("rejected_candidate_keys", self.rejected_candidate_keys),
            ("deferred_candidate_keys", self.deferred_candidate_keys),
            ("missing_candidate_keys", self.missing_candidate_keys),
        ):
            if not isinstance(keys, tuple):
                raise TypeError(f"{name} must be a tuple.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "reviewer_id": self.reviewer_id,
            "mode": self.mode.value,
            "accepted_fields": [field.to_dict() for field in self.accepted_fields],
            "rejected_candidate_keys": [
                self._key_to_dict(key) for key in self.rejected_candidate_keys
            ],
            "deferred_candidate_keys": [
                self._key_to_dict(key) for key in self.deferred_candidate_keys
            ],
            "missing_candidate_keys": [
                self._key_to_dict(key) for key in self.missing_candidate_keys
            ],
            "has_source_conflicts": self.has_source_conflicts,
            "summary": {
                "accepted_count": self.accepted_count,
                "rejected_count": self.rejected_count,
                "deferred_count": self.deferred_count,
                "missing_count": self.missing_count,
                "is_complete": self.is_complete,
            },
        }


def _candidate_key(candidate: OCRFieldCandidate) -> CandidateKey:
    return candidate.identity_key


def _review_key(review: OCRFieldReview) -> CandidateKey:
    return review.identity_key


class OCRReviewReconciliationService:
    """Stateless human-review reconciliation service."""

    def reconcile(
        self,
        *,
        source_report: OCRMetadataReport,
        review: OCRReportReview,
        mode: OCRReviewMode,
    ) -> OCRReviewReconciliation:
        if not isinstance(source_report, OCRMetadataReport):
            raise TypeError("source_report must be an OCRMetadataReport.")
        if not isinstance(review, OCRReportReview):
            raise TypeError("review must be an OCRReportReview.")
        if not isinstance(mode, OCRReviewMode):
            raise TypeError("mode must be an OCRReviewMode.")

        source_report.validate()
        review.validate()

        source_by_key: dict[CandidateKey, OCRFieldCandidate] = {}
        for candidate in source_report.candidates:
            key = _candidate_key(candidate)
            if key in source_by_key:
                raise OCRReviewReconciliationError(
                    f"Duplicate source candidate identity: {key!r}."
                )
            source_by_key[key] = candidate

        review_by_key: dict[CandidateKey, OCRFieldReview] = {}
        for field_review in review.field_reviews:
            key = _review_key(field_review)
            if key in review_by_key:
                raise OCRReviewReconciliationError(
                    f"Duplicate review target: {key!r}."
                )
            if key not in source_by_key:
                raise OCRReviewReconciliationError(
                    f"Review target does not exist in source report: {key!r}."
                )
            review_by_key[key] = field_review

        accepted_fields: list[AcceptedOCRField] = []
        rejected_keys: list[CandidateKey] = []
        deferred_keys: list[CandidateKey] = []
        missing_keys: list[CandidateKey] = []

        for candidate in source_report.candidates:
            key = _candidate_key(candidate)
            field_review = review_by_key.get(key)
            if field_review is None:
                missing_keys.append(key)
                continue

            if field_review.decision is OCRReviewDecision.APPROVE:
                accepted_fields.append(
                    AcceptedOCRField(
                        source_coin_id=candidate.source_coin_id,
                        image_role=candidate.image_role,
                        artifact_key=candidate.artifact_key,
                        provider_id=candidate.provider_id,
                        field_name=candidate.field_name,
                        original_value=candidate.normalized_value,
                        accepted_value=candidate.normalized_value,
                        decision=field_review.decision,
                        reason=field_review.reason,
                    )
                )
            elif field_review.decision is OCRReviewDecision.CORRECT:
                if field_review.reviewed_value is None:
                    raise OCRReviewReconciliationError(
                        "CORRECT review is missing reviewed_value."
                    )
                accepted_fields.append(
                    AcceptedOCRField(
                        source_coin_id=candidate.source_coin_id,
                        image_role=candidate.image_role,
                        artifact_key=candidate.artifact_key,
                        provider_id=candidate.provider_id,
                        field_name=candidate.field_name,
                        original_value=candidate.normalized_value,
                        accepted_value=field_review.reviewed_value,
                        decision=field_review.decision,
                        reason=field_review.reason,
                    )
                )
            elif field_review.decision is OCRReviewDecision.REJECT:
                rejected_keys.append(key)
            elif field_review.decision is OCRReviewDecision.DEFER:
                deferred_keys.append(key)

        if mode is OCRReviewMode.STRICT_COMPLETE and (
            missing_keys or deferred_keys
        ):
            raise OCRReviewReconciliationError(
                "Strict OCR review requires every source candidate to have "
                "a non-deferred decision. "
                f"Missing: {len(missing_keys)}; deferred: {len(deferred_keys)}."
            )

        result = OCRReviewReconciliation(
            reviewer_id=review.reviewer_id,
            mode=mode,
            accepted_fields=tuple(accepted_fields),
            rejected_candidate_keys=tuple(rejected_keys),
            deferred_candidate_keys=tuple(deferred_keys),
            missing_candidate_keys=tuple(missing_keys),
            has_source_conflicts=bool(source_report.conflicts),
        )
        result.validate()
        return result
