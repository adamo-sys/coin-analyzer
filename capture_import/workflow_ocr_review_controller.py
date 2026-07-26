"""Pure application controller for immutable OCR review sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from capture_import.workflow_ocr_models import OCRMetadataReport
from capture_import.workflow_ocr_review_models import OCRReportReview
from capture_import.workflow_ocr_review_presenter import (
    OCRReviewCandidateView,
    OCRReviewPresenter,
    OCRReviewSessionView,
)
from capture_import.workflow_ocr_review_service import OCRReviewMode
from capture_import.workflow_ocr_review_session import (
    OCRReviewSessionConflictResolutionRequest,
    OCRReviewSessionRequest,
    OCRReviewSessionService,
)


@dataclass(frozen=True, slots=True)
class OCRReviewControllerState:
    """Display-ready state reconstructed from immutable review inputs."""

    candidates: tuple[OCRReviewCandidateView, ...]
    mode: str | None
    session: OCRReviewSessionView | None

    @property
    def is_initial(self) -> bool:
        return self.session is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [
                candidate.to_dict() for candidate in self.candidates
            ],
            "mode": self.mode,
            "session": (
                None if self.session is None else self.session.to_dict()
            ),
            "is_initial": self.is_initial,
        }


class OCRReviewSessionController:
    """Stateless coordinator for Sprint 10 services and Unit 1A views."""

    __slots__ = ("_session_service", "_presenter")

    def __init__(
        self,
        *,
        session_service: OCRReviewSessionService | None = None,
        presenter: OCRReviewPresenter | None = None,
    ) -> None:
        if (
            session_service is not None
            and not isinstance(session_service, OCRReviewSessionService)
        ):
            raise TypeError(
                "session_service must be an OCRReviewSessionService or None."
            )
        if (
            presenter is not None
            and not isinstance(presenter, OCRReviewPresenter)
        ):
            raise TypeError(
                "presenter must be an OCRReviewPresenter or None."
            )
        self._session_service = (
            OCRReviewSessionService()
            if session_service is None
            else session_service
        )
        self._presenter = (
            OCRReviewPresenter() if presenter is None else presenter
        )

    def present_initial(
        self,
        *,
        report: OCRMetadataReport,
    ) -> OCRReviewControllerState:
        """Present advisory candidates before any human field review."""

        candidates = self._presenter.present_candidates(
            source_report=report
        )
        return OCRReviewControllerState(
            candidates=candidates,
            mode=None,
            session=None,
        )

    def apply_field_reviews(
        self,
        *,
        report: OCRMetadataReport,
        review: OCRReportReview,
        mode: OCRReviewMode,
    ) -> OCRReviewControllerState:
        """Apply a complete immutable review aggregate."""

        return self.present_session(
            report=report,
            review=review,
            mode=mode,
        )

    def apply_conflict_resolutions(
        self,
        *,
        report: OCRMetadataReport,
        review: OCRReportReview,
        resolutions: tuple[
            OCRReviewSessionConflictResolutionRequest,
            ...,
        ],
        mode: OCRReviewMode,
    ) -> OCRReviewControllerState:
        """Apply explicit targeted conflict-resolution requests."""

        return self.present_session(
            report=report,
            review=review,
            resolutions=resolutions,
            mode=mode,
        )

    def present_session(
        self,
        *,
        report: OCRMetadataReport,
        review: OCRReportReview | None = None,
        resolutions: tuple[
            OCRReviewSessionConflictResolutionRequest,
            ...,
        ] = (),
        mode: OCRReviewMode = OCRReviewMode.PARTIAL,
    ) -> OCRReviewControllerState:
        """Reconstruct one deterministic session state from immutable inputs."""

        if not isinstance(mode, OCRReviewMode):
            raise TypeError("mode must be an OCRReviewMode.")
        if not isinstance(resolutions, tuple):
            raise TypeError("resolutions must be a tuple.")

        if review is None:
            if resolutions:
                raise ValueError(
                    "Conflict resolutions require an OCRReportReview."
                )
            return self.present_initial(report=report)

        if not isinstance(review, OCRReportReview):
            raise TypeError("review must be an OCRReportReview or None.")

        result = self._session_service.run(
            request=OCRReviewSessionRequest(
                source_report=report,
                review=review,
                mode=mode,
                conflict_resolution_requests=resolutions,
            )
        )
        candidates = self._presenter.present_candidates(
            source_report=report,
            review=review,
        )
        session = self._presenter.present_session(result=result)
        return OCRReviewControllerState(
            candidates=candidates,
            mode=mode.value,
            session=session,
        )
