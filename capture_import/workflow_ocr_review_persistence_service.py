"""Application coordination for persisted OCR review sessions.

The service builds and transforms immutable Unit 1A envelopes, delegates
storage to an injected repository, and delegates review truth to Sprint 10.
It performs no automatic persistence, source hashing, filesystem inspection,
desktop integration, migration, or collection work.

The current ``OCRReportReview`` aggregate requires at least one field review,
so persistence before the first review remains unsupported.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .workflow_ocr_models import OCRMetadataReport
from .workflow_ocr_review_models import OCRReportReview
from .workflow_ocr_review_persistence_models import (
    CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION,
    OCRReviewSessionEnvelope,
    OCRReviewSessionLifecycle,
    OCRReviewSessionReconstruction,
    OCRReviewSessionRepository,
    OCRStoredConflictResolution,
)
from .workflow_ocr_review_service import OCRReviewMode
from .workflow_ocr_review_session import OCRReviewSessionService


_SOURCE_FINGERPRINT_CHARS = 64


class OCRReviewSessionPersistenceServiceError(Exception):
    """Base error for persistence-service coordination policy."""


class OCRReviewSessionStaleSourceError(
    OCRReviewSessionPersistenceServiceError
):
    """The current source fingerprint differs from the persisted source."""


class OCRReviewSessionNotResumableError(
    OCRReviewSessionPersistenceServiceError
):
    """The persisted lifecycle is terminal and cannot be resumed."""


@dataclass(frozen=True, slots=True, init=False)
class OCRReviewSessionPersistenceService:
    """Stateless coordinator above review-session contracts and storage."""

    _repository: OCRReviewSessionRepository
    _session_service: OCRReviewSessionService

    def __init__(
        self,
        repository: OCRReviewSessionRepository,
        session_service: OCRReviewSessionService | None = None,
    ) -> None:
        if not isinstance(repository, OCRReviewSessionRepository):
            raise TypeError(
                "repository must implement OCRReviewSessionRepository."
            )
        if (
            session_service is not None
            and not isinstance(session_service, OCRReviewSessionService)
        ):
            raise TypeError(
                "session_service must be an OCRReviewSessionService or None."
            )
        object.__setattr__(self, "_repository", repository)
        object.__setattr__(
            self,
            "_session_service",
            (
                OCRReviewSessionService()
                if session_service is None
                else session_service
            ),
        )

    def create_in_progress(
        self,
        *,
        session_id: str,
        source_fingerprint: str,
        source_report: OCRMetadataReport,
        report_review: OCRReportReview,
        review_mode: OCRReviewMode,
        conflict_resolutions: tuple[
            OCRStoredConflictResolution,
            ...,
        ] = (),
    ) -> OCRReviewSessionEnvelope:
        """Build, but do not save, one validated in-progress envelope."""

        if not isinstance(report_review, OCRReportReview):
            raise TypeError("report_review must be an OCRReportReview.")
        report_review.validate()
        envelope = OCRReviewSessionEnvelope(
            schema_version=(
                CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION
            ),
            session_id=session_id,
            source_fingerprint=source_fingerprint,
            lifecycle_state=OCRReviewSessionLifecycle.IN_PROGRESS,
            review_mode=review_mode,
            reviewer_id=report_review.reviewer_id,
            source_report=source_report,
            field_reviews=report_review.field_reviews,
            conflict_resolutions=conflict_resolutions,
        )
        envelope.validate()
        return envelope

    def save(self, envelope: OCRReviewSessionEnvelope) -> None:
        """Validate lifecycle truth, then delegate one explicit save."""

        self._require_envelope(envelope)
        envelope.validate_lifecycle(
            session_service=self._session_service
        )
        self._repository.save(envelope)

    def load(
        self,
        session_id: str,
    ) -> OCRReviewSessionEnvelope | None:
        """Load without reconstruction, migration, or source comparison."""

        return self._repository.get(session_id)

    def load_for_resume(
        self,
        session_id: str,
        *,
        current_source_fingerprint: str,
    ) -> OCRReviewSessionReconstruction | None:
        """Load and reconstruct one fresh, nonterminal review session."""

        current = _validate_source_fingerprint(
            current_source_fingerprint
        )
        envelope = self._repository.get(session_id)
        if envelope is None:
            return None
        self._require_envelope(envelope)
        if (
            envelope.lifecycle_state
            is not OCRReviewSessionLifecycle.IN_PROGRESS
        ):
            raise OCRReviewSessionNotResumableError(
                f"{envelope.lifecycle_state.value} OCR review sessions "
                "are not resumable."
            )
        if envelope.source_fingerprint != current:
            raise OCRReviewSessionStaleSourceError(
                "The persisted OCR review session source is stale."
            )
        return envelope.reconstruct(
            session_service=self._session_service
        )

    def complete(
        self,
        envelope: OCRReviewSessionEnvelope,
    ) -> OCRReviewSessionEnvelope:
        """Return a new completed envelope after delegated domain validation."""

        self._require_in_progress(envelope, operation="complete")
        completed = replace(
            envelope,
            lifecycle_state=OCRReviewSessionLifecycle.COMPLETED,
        )
        completed.validate_lifecycle(
            session_service=self._session_service
        )
        return completed

    def abandon(
        self,
        envelope: OCRReviewSessionEnvelope,
    ) -> OCRReviewSessionEnvelope:
        """Return a new abandoned audit envelope without deleting or saving."""

        self._require_in_progress(envelope, operation="abandon")
        abandoned = replace(
            envelope,
            lifecycle_state=OCRReviewSessionLifecycle.ABANDONED,
        )
        abandoned.validate()
        return abandoned

    @staticmethod
    def _require_envelope(
        envelope: OCRReviewSessionEnvelope,
    ) -> None:
        if not isinstance(envelope, OCRReviewSessionEnvelope):
            raise TypeError(
                "envelope must be an OCRReviewSessionEnvelope."
            )
        envelope.validate()

    @classmethod
    def _require_in_progress(
        cls,
        envelope: OCRReviewSessionEnvelope,
        *,
        operation: str,
    ) -> None:
        cls._require_envelope(envelope)
        if (
            envelope.lifecycle_state
            is not OCRReviewSessionLifecycle.IN_PROGRESS
        ):
            raise ValueError(
                f"Only IN_PROGRESS OCR review sessions may {operation}."
            )


def _validate_source_fingerprint(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "current_source_fingerprint must be a string."
        )
    if (
        len(value) != _SOURCE_FINGERPRINT_CHARS
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise ValueError(
            "current_source_fingerprint must be a 64-character lowercase "
            "hexadecimal value."
        )
    return value
