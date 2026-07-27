"""Explicit headless persistence coordination for desktop OCR review.

This module is an opt-in command boundary.  It opens no dialogs, executes no
OCR, chooses no repository path, serializes no envelope, and performs no
automatic save.  Persistence before the first field review remains
unsupported by the current ``OCRReportReview`` aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass

from .workflow_ocr_models import OCRMetadataReport
from .workflow_ocr_review_controller import (
    OCRReviewControllerState,
    OCRReviewSessionController,
)
from .workflow_ocr_review_models import OCRReportReview
from .workflow_ocr_review_persistence_models import (
    OCRReviewSessionEnvelope,
    OCRReviewSessionLifecycle,
    OCRStoredConflictResolution,
)
from .workflow_ocr_review_persistence_service import (
    OCRReviewSessionPersistenceService,
)
from .workflow_ocr_review_service import OCRReviewMode
from .workflow_ocr_review_session import (
    OCRReviewSessionConflictResolutionRequest,
)


@dataclass(frozen=True, slots=True)
class DesktopOCRReviewResumeState:
    """Immutable desktop inputs reconstructed from one persisted session."""

    envelope: OCRReviewSessionEnvelope
    report: OCRMetadataReport
    report_review: OCRReportReview
    conflict_resolutions: tuple[
        OCRReviewSessionConflictResolutionRequest,
        ...,
    ]
    review_mode: OCRReviewMode
    controller_state: OCRReviewControllerState

    def __post_init__(self) -> None:
        if not isinstance(self.envelope, OCRReviewSessionEnvelope):
            raise TypeError(
                "envelope must be an OCRReviewSessionEnvelope."
            )
        if not isinstance(self.report, OCRMetadataReport):
            raise TypeError("report must be an OCRMetadataReport.")
        if not isinstance(self.report_review, OCRReportReview):
            raise TypeError(
                "report_review must be an OCRReportReview."
            )
        if not isinstance(self.conflict_resolutions, tuple):
            raise TypeError("conflict_resolutions must be a tuple.")
        if not isinstance(self.review_mode, OCRReviewMode):
            raise TypeError("review_mode must be an OCRReviewMode.")
        if not isinstance(
            self.controller_state,
            OCRReviewControllerState,
        ):
            raise TypeError(
                "controller_state must be an OCRReviewControllerState."
            )

        self.envelope.validate()
        self.report.validate()
        self.report_review.validate()
        for resolution in self.conflict_resolutions:
            if not isinstance(
                resolution,
                OCRReviewSessionConflictResolutionRequest,
            ):
                raise TypeError(
                    "conflict_resolutions must contain "
                    "OCRReviewSessionConflictResolutionRequest values."
                )
            resolution.validate()

        if (
            self.envelope.lifecycle_state
            is not OCRReviewSessionLifecycle.IN_PROGRESS
        ):
            raise ValueError(
                "Desktop resume state requires an IN_PROGRESS envelope."
            )
        if self.envelope.source_report != self.report:
            raise ValueError(
                "Resume report does not match the session envelope."
            )
        if (
            self.envelope.reviewer_id
            != self.report_review.reviewer_id
            or self.envelope.field_reviews
            != self.report_review.field_reviews
        ):
            raise ValueError(
                "Resume review does not match the session envelope."
            )
        if self.envelope.review_mode is not self.review_mode:
            raise ValueError(
                "Resume mode does not match the session envelope."
            )
        if (
            self.envelope.conflict_resolutions
            != _store_resolutions(self.conflict_resolutions)
        ):
            raise ValueError(
                "Resume conflict resolutions do not match the session "
                "envelope."
            )
        if (
            self.controller_state.session is None
            or self.controller_state.mode != self.review_mode.value
        ):
            raise ValueError(
                "Resume controller state does not represent the session."
            )


@dataclass(frozen=True, slots=True)
class DesktopOCRReviewPersistenceCoordinator:
    """Stateless explicit commands for persisted desktop OCR review."""

    persistence_service: OCRReviewSessionPersistenceService
    review_controller: OCRReviewSessionController

    def __post_init__(self) -> None:
        if not isinstance(
            self.persistence_service,
            OCRReviewSessionPersistenceService,
        ):
            raise TypeError(
                "persistence_service must be an "
                "OCRReviewSessionPersistenceService."
            )
        if not isinstance(
            self.review_controller,
            OCRReviewSessionController,
        ):
            raise TypeError(
                "review_controller must be an "
                "OCRReviewSessionController."
            )

    def create_session(
        self,
        *,
        session_id: str,
        source_fingerprint: str,
        report: OCRMetadataReport,
        report_review: OCRReportReview,
        review_mode: OCRReviewMode,
        conflict_resolutions: tuple[
            OCRReviewSessionConflictResolutionRequest,
            ...,
        ] = (),
    ) -> OCRReviewSessionEnvelope:
        """Create, but do not save, one in-progress desktop session."""

        stored = _store_resolutions(conflict_resolutions)
        return self.persistence_service.create_in_progress(
            session_id=session_id,
            source_fingerprint=source_fingerprint,
            source_report=report,
            report_review=report_review,
            review_mode=review_mode,
            conflict_resolutions=stored,
        )

    def save_session(
        self,
        envelope: OCRReviewSessionEnvelope,
    ) -> OCRReviewSessionEnvelope:
        """Perform one explicit save and return the unchanged envelope."""

        self.persistence_service.save(envelope)
        return envelope

    def load_for_resume(
        self,
        session_id: str,
        *,
        current_source_fingerprint: str,
    ) -> DesktopOCRReviewResumeState | None:
        """Load, reconstruct, and present one resumable immutable session."""

        reconstruction = self.persistence_service.load_for_resume(
            session_id,
            current_source_fingerprint=current_source_fingerprint,
        )
        if reconstruction is None:
            return None

        envelope = self.persistence_service.create_in_progress(
            session_id=session_id,
            source_fingerprint=current_source_fingerprint,
            source_report=reconstruction.source_report,
            report_review=reconstruction.review,
            review_mode=reconstruction.mode,
            conflict_resolutions=_store_resolutions(
                reconstruction.conflict_resolutions
            ),
        )
        controller_state = self.review_controller.present_session(
            report=reconstruction.source_report,
            review=reconstruction.review,
            resolutions=reconstruction.conflict_resolutions,
            mode=reconstruction.mode,
        )
        return DesktopOCRReviewResumeState(
            envelope=envelope,
            report=reconstruction.source_report,
            report_review=reconstruction.review,
            conflict_resolutions=reconstruction.conflict_resolutions,
            review_mode=reconstruction.mode,
            controller_state=controller_state,
        )

    def abandon_session(
        self,
        envelope: OCRReviewSessionEnvelope,
    ) -> OCRReviewSessionEnvelope:
        """Return a new abandoned envelope without saving or deleting."""

        return self.persistence_service.abandon(envelope)

    def complete_session(
        self,
        envelope: OCRReviewSessionEnvelope,
    ) -> OCRReviewSessionEnvelope:
        """Return a new completed envelope without saving it."""

        return self.persistence_service.complete(envelope)


def create_desktop_ocr_review_persistence_coordinator(
    *,
    persistence_service: OCRReviewSessionPersistenceService,
    review_controller: OCRReviewSessionController,
) -> DesktopOCRReviewPersistenceCoordinator:
    """Explicitly compose persistence commands without choosing storage."""

    return DesktopOCRReviewPersistenceCoordinator(
        persistence_service=persistence_service,
        review_controller=review_controller,
    )


def _store_resolutions(
    resolutions: tuple[
        OCRReviewSessionConflictResolutionRequest,
        ...,
    ],
) -> tuple[OCRStoredConflictResolution, ...]:
    if not isinstance(resolutions, tuple):
        raise TypeError("conflict_resolutions must be a tuple.")
    stored: list[OCRStoredConflictResolution] = []
    for resolution in resolutions:
        if not isinstance(
            resolution,
            OCRReviewSessionConflictResolutionRequest,
        ):
            raise TypeError(
                "conflict_resolutions must contain "
                "OCRReviewSessionConflictResolutionRequest values."
            )
        resolution.validate()
        stored_resolution = OCRStoredConflictResolution(
            source_coin_id=resolution.field.source_coin_id,
            field_name=resolution.field.field_name,
            decision=resolution.request.decision,
            value=resolution.request.value,
        )
        stored_resolution.validate()
        stored.append(stored_resolution)
    return tuple(
        sorted(stored, key=lambda item: item.identity)
    )
