"""Explicit desktop controls for persisted OCR review sessions.

The headless model in this module owns only ephemeral control state.  Every
write and lifecycle transition delegates to the injected Sprint 12 Unit 1D
coordinator.  The thin Tkinter surface is opt-in and performs no repository
selection, serialization, source hashing, OCR execution, or automatic saving.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from .desktop_ocr_review_persistence import (
    DesktopOCRReviewPersistenceCoordinator,
    DesktopOCRReviewResumeState,
)
from .workflow_ocr_models import OCRMetadataReport
from .workflow_ocr_review_local_repository import (
    OCRReviewSessionCorruptError,
    OCRReviewSessionRepositoryError,
    OCRReviewSessionWriteError,
)
from .workflow_ocr_review_models import OCRReportReview
from .workflow_ocr_review_persistence_models import (
    OCRReviewSessionEnvelope,
    OCRReviewSessionLifecycle,
    UnsupportedOCRReviewSessionSchemaVersion,
)
from .workflow_ocr_review_persistence_service import (
    OCRReviewSessionNotResumableError,
    OCRReviewSessionStaleSourceError,
)
from .workflow_ocr_review_service import OCRReviewMode
from .workflow_ocr_review_session import (
    OCRReviewSessionConflictResolutionRequest,
)


ResumeApplication = Callable[[DesktopOCRReviewResumeState], None]
Confirmation = Callable[[], bool]

_COORDINATOR_METHODS = (
    "create_session",
    "save_session",
    "load_for_resume",
    "abandon_session",
    "complete_session",
)


class DesktopOCRReviewPersistenceOperation(str, Enum):
    """User-triggered persistence commands."""

    SAVE = "SAVE"
    RESUME = "RESUME"
    ABANDON_AND_SAVE = "ABANDON_AND_SAVE"
    COMPLETE_AND_SAVE = "COMPLETE_AND_SAVE"


class DesktopOCRReviewPersistenceOutcome(str, Enum):
    """Bounded outcome state for one persistence command."""

    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class DesktopOCRReviewPersistenceErrorCategory(str, Enum):
    """Stable user-facing categories without exposing storage internals."""

    NOT_FOUND = "NOT_FOUND"
    STALE_SOURCE = "STALE_SOURCE"
    NOT_RESUMABLE = "NOT_RESUMABLE"
    CORRUPT_DATA = "CORRUPT_DATA"
    UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"
    WRITE_FAILURE = "WRITE_FAILURE"
    REPOSITORY_ACCESS = "REPOSITORY_ACCESS"
    DOMAIN_VALIDATION = "DOMAIN_VALIDATION"
    INVALID_CALLER_INPUT = "INVALID_CALLER_INPUT"


@dataclass(frozen=True, slots=True)
class DesktopOCRReviewSessionDraft:
    """Immutable reviewed state sufficient to create one persisted envelope."""

    session_id: str
    source_fingerprint: str
    report: OCRMetadataReport
    report_review: OCRReportReview
    review_mode: OCRReviewMode
    conflict_resolutions: tuple[
        OCRReviewSessionConflictResolutionRequest,
        ...,
    ] = ()

    def validate(self) -> None:
        if not isinstance(self.session_id, str):
            raise TypeError("session_id must be a string.")
        if not isinstance(self.source_fingerprint, str):
            raise TypeError("source_fingerprint must be a string.")
        if not isinstance(self.report, OCRMetadataReport):
            raise TypeError("report must be an OCRMetadataReport.")
        if not isinstance(self.report_review, OCRReportReview):
            raise TypeError("report_review must be an OCRReportReview.")
        if not isinstance(self.review_mode, OCRReviewMode):
            raise TypeError("review_mode must be an OCRReviewMode.")
        if not isinstance(self.conflict_resolutions, tuple):
            raise TypeError("conflict_resolutions must be a tuple.")
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


@dataclass(frozen=True, slots=True)
class DesktopOCRReviewPersistenceCommandResult:
    """Immutable status and payload for one explicit control command."""

    operation: DesktopOCRReviewPersistenceOperation
    outcome: DesktopOCRReviewPersistenceOutcome
    message: str
    error_category: (
        DesktopOCRReviewPersistenceErrorCategory | None
    ) = None
    envelope: OCRReviewSessionEnvelope | None = None
    resume_state: DesktopOCRReviewResumeState | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.operation,
            DesktopOCRReviewPersistenceOperation,
        ):
            raise TypeError(
                "operation must be a "
                "DesktopOCRReviewPersistenceOperation."
            )
        if not isinstance(
            self.outcome,
            DesktopOCRReviewPersistenceOutcome,
        ):
            raise TypeError(
                "outcome must be a DesktopOCRReviewPersistenceOutcome."
            )
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must be a nonblank string.")
        if (
            self.error_category is not None
            and not isinstance(
                self.error_category,
                DesktopOCRReviewPersistenceErrorCategory,
            )
        ):
            raise TypeError(
                "error_category must be a "
                "DesktopOCRReviewPersistenceErrorCategory or None."
            )
        if (
            self.envelope is not None
            and not isinstance(self.envelope, OCRReviewSessionEnvelope)
        ):
            raise TypeError(
                "envelope must be an OCRReviewSessionEnvelope or None."
            )
        if (
            self.resume_state is not None
            and not isinstance(
                self.resume_state,
                DesktopOCRReviewResumeState,
            )
        ):
            raise TypeError(
                "resume_state must be a "
                "DesktopOCRReviewResumeState or None."
            )
        if self.outcome is DesktopOCRReviewPersistenceOutcome.SUCCESS:
            if self.error_category is not None:
                raise ValueError(
                    "Successful command results cannot have an error category."
                )
            if (
                self.operation
                is DesktopOCRReviewPersistenceOperation.RESUME
            ):
                if self.resume_state is None or self.envelope is not None:
                    raise ValueError(
                        "Successful resume requires only resume_state."
                    )
            elif self.envelope is None or self.resume_state is not None:
                raise ValueError(
                    "Successful non-resume commands require only envelope."
                )
        elif self.envelope is not None or self.resume_state is not None:
            raise ValueError(
                "Unsuccessful command results cannot contain state payloads."
            )


@dataclass(frozen=True, slots=True)
class DesktopOCRReviewPersistenceControlsDisplay:
    """Immutable render state for the opt-in persistence controls."""

    has_envelope: bool
    current_session_id: str | None
    lifecycle: OCRReviewSessionLifecycle | None
    save_available: bool
    resume_available: bool
    abandon_available: bool
    complete_available: bool
    last_result: DesktopOCRReviewPersistenceCommandResult | None


class DesktopOCRReviewPersistenceControlsModel:
    """Headless commands with explicit ephemeral current-session state."""

    __slots__ = (
        "_coordinator",
        "_apply_resume",
        "_confirm_abandon",
        "_confirm_complete",
        "_current_state",
        "_last_result",
    )

    def __init__(
        self,
        *,
        coordinator: DesktopOCRReviewPersistenceCoordinator,
        apply_resume: ResumeApplication,
        confirm_abandon: Confirmation,
        confirm_complete: Confirmation,
        current_state: (
            DesktopOCRReviewSessionDraft
            | OCRReviewSessionEnvelope
            | None
        ) = None,
    ) -> None:
        _validate_coordinator(coordinator)
        for callback, name in (
            (apply_resume, "apply_resume"),
            (confirm_abandon, "confirm_abandon"),
            (confirm_complete, "confirm_complete"),
        ):
            if not callable(callback):
                raise TypeError(f"{name} must be callable.")
        self._coordinator = coordinator
        self._apply_resume = apply_resume
        self._confirm_abandon = confirm_abandon
        self._confirm_complete = confirm_complete
        self._current_state = None
        self._last_result = None
        if current_state is not None:
            self.set_current_state(current_state)

    @property
    def current_state(
        self,
    ) -> DesktopOCRReviewSessionDraft | OCRReviewSessionEnvelope | None:
        return self._current_state

    @property
    def current_envelope(self) -> OCRReviewSessionEnvelope | None:
        return (
            self._current_state
            if isinstance(self._current_state, OCRReviewSessionEnvelope)
            else None
        )

    @property
    def last_result(
        self,
    ) -> DesktopOCRReviewPersistenceCommandResult | None:
        return self._last_result

    @property
    def display(self) -> DesktopOCRReviewPersistenceControlsDisplay:
        state = self._current_state
        envelope = self.current_envelope
        in_progress = (
            envelope is not None
            and envelope.lifecycle_state
            is OCRReviewSessionLifecycle.IN_PROGRESS
        )
        return DesktopOCRReviewPersistenceControlsDisplay(
            has_envelope=envelope is not None,
            current_session_id=(
                None if state is None else state.session_id
            ),
            lifecycle=(
                None if envelope is None else envelope.lifecycle_state
            ),
            save_available=(
                isinstance(state, DesktopOCRReviewSessionDraft)
                or in_progress
            ),
            resume_available=True,
            abandon_available=in_progress,
            complete_available=in_progress,
            last_result=self._last_result,
        )

    def set_current_state(
        self,
        state: DesktopOCRReviewSessionDraft | OCRReviewSessionEnvelope,
    ) -> None:
        """Supply a new immutable review snapshot through a public seam."""

        _validate_current_state(state)
        self._current_state = state
        self._last_result = None

    def save(self) -> DesktopOCRReviewPersistenceCommandResult:
        """Create if needed and perform exactly one explicit save."""

        operation = DesktopOCRReviewPersistenceOperation.SAVE
        state = self._current_state
        if not self.display.save_available or state is None:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
                "No saveable in-progress OCR review state is available.",
            )
        try:
            if isinstance(state, DesktopOCRReviewSessionDraft):
                envelope = self._coordinator.create_session(
                    session_id=state.session_id,
                    source_fingerprint=state.source_fingerprint,
                    report=state.report,
                    report_review=state.report_review,
                    review_mode=state.review_mode,
                    conflict_resolutions=state.conflict_resolutions,
                )
            else:
                envelope = state
            saved = self._coordinator.save_session(envelope)
            _require_envelope(saved)
        except OCRReviewSessionWriteError:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.WRITE_FAILURE,
                "The OCR review session could not be saved.",
            )
        except OCRReviewSessionRepositoryError:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.REPOSITORY_ACCESS,
                "The OCR review-session repository could not be accessed.",
            )
        except (TypeError, ValueError) as error:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
                str(error),
            )
        self._current_state = saved
        return self._success(
            operation,
            "OCR review session saved.",
            envelope=saved,
        )

    def resume(
        self,
        session_id: str,
        *,
        current_source_fingerprint: str,
    ) -> DesktopOCRReviewPersistenceCommandResult:
        """Load and apply one session, changing current state only on success."""

        operation = DesktopOCRReviewPersistenceOperation.RESUME
        previous = self._current_state
        try:
            resumed = self._coordinator.load_for_resume(
                session_id,
                current_source_fingerprint=current_source_fingerprint,
            )
        except OCRReviewSessionStaleSourceError:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.STALE_SOURCE,
                "The saved OCR review session belongs to a different source.",
            )
        except OCRReviewSessionNotResumableError:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.NOT_RESUMABLE,
                "The saved OCR review session is terminal and cannot resume.",
            )
        except UnsupportedOCRReviewSessionSchemaVersion:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.UNSUPPORTED_SCHEMA,
                "The saved OCR review session uses an unsupported schema.",
            )
        except OCRReviewSessionCorruptError:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.CORRUPT_DATA,
                "The saved OCR review session is corrupt.",
            )
        except OCRReviewSessionRepositoryError:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.REPOSITORY_ACCESS,
                "The OCR review-session repository could not be accessed.",
            )
        except (TypeError, ValueError) as error:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
                str(error),
            )
        if resumed is None:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.NOT_FOUND,
                "No saved OCR review session was found.",
                outcome=DesktopOCRReviewPersistenceOutcome.NOT_FOUND,
            )
        if not isinstance(resumed, DesktopOCRReviewResumeState):
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
                "The persistence coordinator returned invalid resume state.",
            )
        try:
            self._apply_resume(resumed)
        except (TypeError, ValueError) as error:
            self._current_state = previous
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
                str(error),
            )
        self._current_state = resumed.envelope
        return self._success(
            operation,
            "OCR review session resumed.",
            resume_state=resumed,
        )

    def abandon_and_save(
        self,
    ) -> DesktopOCRReviewPersistenceCommandResult:
        """Confirm, abandon, and explicitly save exactly once."""

        return self._transition_and_save(
            operation=(
                DesktopOCRReviewPersistenceOperation.ABANDON_AND_SAVE
            ),
            confirmation=self._confirm_abandon,
            transition=self._coordinator.abandon_session,
            success_message="OCR review session abandoned and saved.",
        )

    def complete_and_save(
        self,
    ) -> DesktopOCRReviewPersistenceCommandResult:
        """Confirm, validate completion, and explicitly save exactly once."""

        return self._transition_and_save(
            operation=(
                DesktopOCRReviewPersistenceOperation.COMPLETE_AND_SAVE
            ),
            confirmation=self._confirm_complete,
            transition=self._coordinator.complete_session,
            success_message="OCR review session completed and saved.",
        )

    def _transition_and_save(
        self,
        *,
        operation: DesktopOCRReviewPersistenceOperation,
        confirmation: Confirmation,
        transition: Callable[
            [OCRReviewSessionEnvelope],
            OCRReviewSessionEnvelope,
        ],
        success_message: str,
    ) -> DesktopOCRReviewPersistenceCommandResult:
        original = self.current_envelope
        if (
            original is None
            or original.lifecycle_state
            is not OCRReviewSessionLifecycle.IN_PROGRESS
        ):
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
                "An in-progress persisted OCR review session is required.",
            )
        try:
            confirmed = confirmation()
        except (TypeError, ValueError) as error:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
                str(error),
            )
        if not isinstance(confirmed, bool):
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
                "Confirmation callback must return a boolean.",
            )
        if not confirmed:
            return self._failure(
                operation,
                None,
                "OCR review session transition cancelled.",
                outcome=DesktopOCRReviewPersistenceOutcome.CANCELLED,
            )
        try:
            transitioned = transition(original)
            _require_envelope(transitioned)
            saved = self._coordinator.save_session(transitioned)
            _require_envelope(saved)
        except OCRReviewSessionWriteError:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.WRITE_FAILURE,
                "The transitioned OCR review session could not be saved.",
            )
        except OCRReviewSessionRepositoryError:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.REPOSITORY_ACCESS,
                "The OCR review-session repository could not be accessed.",
            )
        except TypeError as error:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
                str(error),
            )
        except ValueError as error:
            return self._failure(
                operation,
                DesktopOCRReviewPersistenceErrorCategory.DOMAIN_VALIDATION,
                str(error),
            )
        self._current_state = saved
        return self._success(
            operation,
            success_message,
            envelope=saved,
        )

    def _success(
        self,
        operation: DesktopOCRReviewPersistenceOperation,
        message: str,
        *,
        envelope: OCRReviewSessionEnvelope | None = None,
        resume_state: DesktopOCRReviewResumeState | None = None,
    ) -> DesktopOCRReviewPersistenceCommandResult:
        result = DesktopOCRReviewPersistenceCommandResult(
            operation=operation,
            outcome=DesktopOCRReviewPersistenceOutcome.SUCCESS,
            message=message,
            envelope=envelope,
            resume_state=resume_state,
        )
        self._last_result = result
        return result

    def _failure(
        self,
        operation: DesktopOCRReviewPersistenceOperation,
        category: DesktopOCRReviewPersistenceErrorCategory | None,
        message: str,
        *,
        outcome: DesktopOCRReviewPersistenceOutcome = (
            DesktopOCRReviewPersistenceOutcome.FAILED
        ),
    ) -> DesktopOCRReviewPersistenceCommandResult:
        result = DesktopOCRReviewPersistenceCommandResult(
            operation=operation,
            outcome=outcome,
            message=message,
            error_category=category,
        )
        self._last_result = result
        return result


class DesktopOCRReviewPersistenceControls(ttk.Frame):
    """Thin opt-in Tk controls backed by the headless command model."""

    def __init__(
        self,
        *,
        parent: tk.Misc,
        model: DesktopOCRReviewPersistenceControlsModel,
    ) -> None:
        if not isinstance(
            model,
            DesktopOCRReviewPersistenceControlsModel,
        ):
            raise TypeError(
                "model must be a "
                "DesktopOCRReviewPersistenceControlsModel."
            )
        super().__init__(parent, padding="8")
        self._model = model
        self._resume_session_id = tk.StringVar()
        self._source_fingerprint = tk.StringVar()
        self._current_var = tk.StringVar()
        self._lifecycle_var = tk.StringVar()
        self._status_var = tk.StringVar()
        self._build_widgets()
        self._render()

    def _build_widgets(self) -> None:
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text="Current session:").grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        ttk.Label(self, textvariable=self._current_var).grid(
            row=0,
            column=1,
            sticky=tk.W,
        )
        ttk.Label(self, text="Lifecycle:").grid(
            row=1,
            column=0,
            sticky=tk.W,
        )
        ttk.Label(self, textvariable=self._lifecycle_var).grid(
            row=1,
            column=1,
            sticky=tk.W,
        )
        ttk.Label(self, text="Resume session ID:").grid(
            row=2,
            column=0,
            sticky=tk.W,
            pady=(8, 0),
        )
        ttk.Entry(
            self,
            textvariable=self._resume_session_id,
        ).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(8, 0))
        ttk.Label(self, text="Current source fingerprint:").grid(
            row=3,
            column=0,
            sticky=tk.W,
        )
        ttk.Entry(
            self,
            textvariable=self._source_fingerprint,
        ).grid(row=3, column=1, sticky=(tk.W, tk.E))
        actions = ttk.Frame(self)
        actions.grid(
            row=4,
            column=0,
            columnspan=2,
            sticky=tk.W,
            pady=(10, 0),
        )
        self._save_button = ttk.Button(
            actions,
            text="Save",
            command=self._save,
        )
        self._resume_button = ttk.Button(
            actions,
            text="Resume",
            command=self._resume,
        )
        self._abandon_button = ttk.Button(
            actions,
            text="Abandon and Save",
            command=self._abandon,
        )
        self._complete_button = ttk.Button(
            actions,
            text="Complete and Save",
            command=self._complete,
        )
        for button in (
            self._save_button,
            self._resume_button,
            self._abandon_button,
            self._complete_button,
        ):
            button.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(
            self,
            textvariable=self._status_var,
            wraplength=680,
        ).grid(
            row=5,
            column=0,
            columnspan=2,
            sticky=tk.W,
            pady=(8, 0),
        )

    def _save(self) -> None:
        self._model.save()
        self._render()

    def _resume(self) -> None:
        self._model.resume(
            self._resume_session_id.get(),
            current_source_fingerprint=self._source_fingerprint.get(),
        )
        self._render()

    def _abandon(self) -> None:
        self._model.abandon_and_save()
        self._render()

    def _complete(self) -> None:
        self._model.complete_and_save()
        self._render()

    def _render(self) -> None:
        display = self._model.display
        self._current_var.set(display.current_session_id or "None")
        self._lifecycle_var.set(
            "Not persisted"
            if display.lifecycle is None
            else display.lifecycle.value
        )
        self._status_var.set(
            ""
            if display.last_result is None
            else display.last_result.message
        )
        for button, available in (
            (self._save_button, display.save_available),
            (self._resume_button, display.resume_available),
            (self._abandon_button, display.abandon_available),
            (self._complete_button, display.complete_available),
        ):
            button.configure(
                state=tk.NORMAL if available else tk.DISABLED
            )


def create_desktop_ocr_review_persistence_controls(
    *,
    parent: tk.Misc,
    coordinator: DesktopOCRReviewPersistenceCoordinator,
    apply_resume: ResumeApplication,
    current_state: (
        DesktopOCRReviewSessionDraft
        | OCRReviewSessionEnvelope
        | None
    ) = None,
    confirm_abandon: Confirmation | None = None,
    confirm_complete: Confirmation | None = None,
) -> DesktopOCRReviewPersistenceControls:
    """Explicitly construct persistence controls without choosing storage."""

    abandon_confirmation = (
        (
            lambda: messagebox.askyesno(
                "Abandon OCR Review",
                "Abandon this OCR review session and save its terminal state?",
                parent=parent,
            )
        )
        if confirm_abandon is None
        else confirm_abandon
    )
    complete_confirmation = (
        (
            lambda: messagebox.askyesno(
                "Complete OCR Review",
                "Complete this OCR review session and save its terminal state?",
                parent=parent,
            )
        )
        if confirm_complete is None
        else confirm_complete
    )
    model = DesktopOCRReviewPersistenceControlsModel(
        coordinator=coordinator,
        apply_resume=apply_resume,
        confirm_abandon=abandon_confirmation,
        confirm_complete=complete_confirmation,
        current_state=current_state,
    )
    return DesktopOCRReviewPersistenceControls(
        parent=parent,
        model=model,
    )


def _validate_coordinator(coordinator: object) -> None:
    missing = tuple(
        name
        for name in _COORDINATOR_METHODS
        if not callable(getattr(coordinator, name, None))
    )
    if missing:
        raise TypeError(
            "coordinator must expose the Unit 1D persistence commands: "
            + ", ".join(_COORDINATOR_METHODS)
            + "."
        )


def _validate_current_state(
    state: DesktopOCRReviewSessionDraft | OCRReviewSessionEnvelope,
) -> None:
    if isinstance(state, DesktopOCRReviewSessionDraft):
        state.validate()
        return
    if isinstance(state, OCRReviewSessionEnvelope):
        state.validate()
        return
    raise TypeError(
        "current_state must be a DesktopOCRReviewSessionDraft or "
        "OCRReviewSessionEnvelope."
    )


def _require_envelope(value: object) -> None:
    if not isinstance(value, OCRReviewSessionEnvelope):
        raise TypeError(
            "The persistence coordinator must return an "
            "OCRReviewSessionEnvelope."
        )
    value.validate()
