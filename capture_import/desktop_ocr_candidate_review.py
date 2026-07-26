"""Explicit Tkinter candidate-review UI for advisory OCR metadata.

This module is not imported by default desktop startup or composition.  It
contains one concrete dialog and a headless interaction model so review
decisions and navigation can be tested without a display server.

Image loading is deliberately outside this module.  An optional preview
resolver may supply an already-created Tk-compatible image object or an
unavailable result for the current Unit 1A candidate view.
"""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Callable

from capture_import.workflow_ocr_models import OCRMetadataReport
from capture_import.workflow_ocr_review_controller import (
    OCRReviewControllerState,
    OCRReviewSessionController,
)
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_presenter import (
    OCRReviewCandidateView,
)
from capture_import.workflow_ocr_review_service import OCRReviewMode


CandidateIdentity = tuple[str, str, str, str, str, str]
PreviewResolver = Callable[
    [OCRReviewCandidateView],
    "OCRCandidatePreview | None",
]
ReviewCallback = Callable[[tuple[OCRFieldReview, ...]], None]


def _candidate_identity(
    candidate: OCRReviewCandidateView,
) -> CandidateIdentity:
    return (
        candidate.source_coin_id,
        candidate.field_name,
        candidate.image_role,
        candidate.provider_id,
        candidate.artifact_key,
        candidate.original_value,
    )


@dataclass(frozen=True, slots=True)
class OCRCandidatePreview:
    """Injected preview result without filesystem or image-loading behavior."""

    reference: str
    image: object | None = None
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reference, str):
            raise TypeError("reference must be a string.")
        if not self.reference.strip():
            raise ValueError("reference must not be empty.")
        if (
            self.unavailable_reason is not None
            and not isinstance(self.unavailable_reason, str)
        ):
            raise TypeError(
                "unavailable_reason must be a string or None."
            )


@dataclass(frozen=True, slots=True)
class OCRCandidateReviewDisplay:
    """Immutable headless render state for the current candidate."""

    candidate: OCRReviewCandidateView | None
    candidate_index: int
    candidate_count: int
    position_label: str
    confidence_label: str
    evidence_label: str
    preview: OCRCandidatePreview | None

    @property
    def has_candidate(self) -> bool:
        return self.candidate is not None


class OCRCandidateReviewModel:
    """Ephemeral candidate navigation and decision adapter."""

    __slots__ = (
        "_report",
        "_controller",
        "_reviewer_id",
        "_preview_resolver",
        "_state",
        "_index",
        "_reviews_by_identity",
    )

    def __init__(
        self,
        *,
        report: OCRMetadataReport,
        review_controller: OCRReviewSessionController,
        reviewer_id: str,
        preview_resolver: PreviewResolver | None = None,
    ) -> None:
        if not isinstance(
            review_controller,
            OCRReviewSessionController,
        ):
            raise TypeError(
                "review_controller must be an "
                "OCRReviewSessionController."
            )
        if not isinstance(reviewer_id, str):
            raise TypeError("reviewer_id must be a string.")
        if preview_resolver is not None and not callable(preview_resolver):
            raise TypeError("preview_resolver must be callable or None.")

        state = review_controller.present_initial(report=report)
        self._report = report
        self._controller = review_controller
        self._reviewer_id = reviewer_id
        self._preview_resolver = preview_resolver
        self._state = state
        self._index = 0
        self._reviews_by_identity: dict[
            CandidateIdentity,
            OCRFieldReview,
        ] = {}

    @property
    def candidate_count(self) -> int:
        return len(self._state.candidates)

    @property
    def candidate_index(self) -> int:
        return self._index if self.candidate_count else 0

    @property
    def current_candidate(self) -> OCRReviewCandidateView | None:
        if not self._state.candidates:
            return None
        return self._state.candidates[self._index]

    @property
    def current_review(self) -> OCRFieldReview | None:
        candidate = self.current_candidate
        if candidate is None:
            return None
        return self._reviews_by_identity.get(
            _candidate_identity(candidate)
        )

    @property
    def reviews(self) -> tuple[OCRFieldReview, ...]:
        return tuple(
            self._reviews_by_identity[key]
            for key in sorted(self._reviews_by_identity)
        )

    @property
    def display(self) -> OCRCandidateReviewDisplay:
        candidate = self.current_candidate
        if candidate is None:
            return OCRCandidateReviewDisplay(
                candidate=None,
                candidate_index=0,
                candidate_count=0,
                position_label="No OCR candidates",
                confidence_label="Unavailable",
                evidence_label="No evidence",
                preview=None,
            )

        confidence = candidate.confidence_score
        confidence_label = (
            f"{float(confidence):.2f}%"
            if (
                not isinstance(confidence, bool)
                and isinstance(confidence, (int, float))
            )
            else "Unavailable"
        )
        return OCRCandidateReviewDisplay(
            candidate=candidate,
            candidate_index=self._index,
            candidate_count=self.candidate_count,
            position_label=(
                f"Candidate {self._index + 1} of {self.candidate_count}"
            ),
            confidence_label=confidence_label,
            evidence_label=(
                "\n".join(candidate.evidence)
                if candidate.evidence
                else "No evidence"
            ),
            preview=self._resolve_preview(candidate),
        )

    def next_candidate(self) -> bool:
        if self._index + 1 >= self.candidate_count:
            return False
        self._index += 1
        return True

    def previous_candidate(self) -> bool:
        if self._index == 0:
            return False
        self._index -= 1
        return True

    def approve(self, *, reason: str) -> OCRFieldReview:
        candidate = self._require_candidate()
        return self._submit(
            candidate=candidate,
            decision=OCRReviewDecision.APPROVE,
            reviewed_value=candidate.original_value,
            reason=reason,
        )

    def correct(
        self,
        *,
        corrected_value: str,
        reason: str,
    ) -> OCRFieldReview:
        return self._submit(
            candidate=self._require_candidate(),
            decision=OCRReviewDecision.CORRECT,
            reviewed_value=corrected_value,
            reason=reason,
        )

    def reject(self, *, reason: str) -> OCRFieldReview:
        return self._submit(
            candidate=self._require_candidate(),
            decision=OCRReviewDecision.REJECT,
            reviewed_value=None,
            reason=reason,
        )

    def defer(self, *, reason: str) -> OCRFieldReview:
        return self._submit(
            candidate=self._require_candidate(),
            decision=OCRReviewDecision.DEFER,
            reviewed_value=None,
            reason=reason,
        )

    def _require_candidate(self) -> OCRReviewCandidateView:
        candidate = self.current_candidate
        if candidate is None:
            raise ValueError("There is no OCR candidate to review.")
        return candidate

    def _submit(
        self,
        *,
        candidate: OCRReviewCandidateView,
        decision: OCRReviewDecision,
        reviewed_value: str | None,
        reason: str,
    ) -> OCRFieldReview:
        review = OCRFieldReview(
            source_coin_id=candidate.source_coin_id,
            image_role=candidate.image_role,
            artifact_key=candidate.artifact_key,
            provider_id=candidate.provider_id,
            field_name=candidate.field_name,
            original_value=candidate.original_value,
            decision=decision,
            reviewed_value=reviewed_value,
            reason=reason,
        )
        review.validate()

        proposed = dict(self._reviews_by_identity)
        proposed[_candidate_identity(candidate)] = review
        ordered_reviews = tuple(
            proposed[key] for key in sorted(proposed)
        )
        report_review = OCRReportReview(
            reviewer_id=self._reviewer_id,
            field_reviews=ordered_reviews,
        )

        state = self._controller.apply_field_reviews(
            report=self._report,
            review=report_review,
            mode=OCRReviewMode.PARTIAL,
        )

        self._reviews_by_identity = proposed
        self._state = state
        return review

    def _resolve_preview(
        self,
        candidate: OCRReviewCandidateView,
    ) -> OCRCandidatePreview:
        reference = candidate.artifact_key
        if self._preview_resolver is None:
            return OCRCandidatePreview(
                reference=reference,
                unavailable_reason="Preview unavailable",
            )
        try:
            preview = self._preview_resolver(candidate)
        except Exception as exc:
            return OCRCandidatePreview(
                reference=reference,
                unavailable_reason=f"Preview unavailable: {exc}",
            )
        if preview is None:
            return OCRCandidatePreview(
                reference=reference,
                unavailable_reason="Preview unavailable",
            )
        if not isinstance(preview, OCRCandidatePreview):
            raise TypeError(
                "preview_resolver must return OCRCandidatePreview or None."
            )
        return preview


class OCRCandidateReviewDialog:
    """Concrete Tkinter dialog backed entirely by the headless model."""

    def __init__(
        self,
        *,
        parent: tk.Misc,
        model: OCRCandidateReviewModel,
        on_close: ReviewCallback | None = None,
    ) -> None:
        if not isinstance(model, OCRCandidateReviewModel):
            raise TypeError("model must be an OCRCandidateReviewModel.")
        if on_close is not None and not callable(on_close):
            raise TypeError("on_close must be callable or None.")

        self._model = model
        self._on_close = on_close
        self._preview_image: object | None = None

        self.window = tk.Toplevel(parent)
        self.window.title("OCR Candidate Review")
        self.window.geometry("760x620")
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self._position_var = tk.StringVar()
        self._coin_var = tk.StringVar()
        self._field_var = tk.StringVar()
        self._value_var = tk.StringVar()
        self._role_var = tk.StringVar()
        self._artifact_var = tk.StringVar()
        self._provider_var = tk.StringVar()
        self._confidence_var = tk.StringVar()
        self._evidence_var = tk.StringVar()
        self._human_state_var = tk.StringVar()
        self._preview_reference_var = tk.StringVar()
        self._correction_var = tk.StringVar()
        self._reason_var = tk.StringVar()
        self._error_var = tk.StringVar()

        self._build_widgets()
        self._render()

    def _build_widgets(self) -> None:
        content = ttk.Frame(self.window, padding="12")
        content.pack(fill=tk.BOTH, expand=True)
        content.columnconfigure(1, weight=1)

        ttk.Label(
            content,
            textvariable=self._position_var,
            font=("TkDefaultFont", 11, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        rows = (
            ("Source coin", self._coin_var),
            ("Field", self._field_var),
            ("OCR value", self._value_var),
            ("Image role", self._role_var),
            ("Artifact", self._artifact_var),
            ("Provider", self._provider_var),
            ("Confidence", self._confidence_var),
            ("Evidence", self._evidence_var),
            ("Human review", self._human_state_var),
        )
        for row, (label, variable) in enumerate(rows, start=1):
            ttk.Label(content, text=f"{label}:").grid(
                row=row,
                column=0,
                sticky=tk.NW,
                padx=(0, 10),
                pady=2,
            )
            ttk.Label(
                content,
                textvariable=variable,
                wraplength=540,
            ).grid(row=row, column=1, sticky=tk.W, pady=2)

        preview_frame = ttk.LabelFrame(
            content,
            text="Source preview",
            padding="8",
        )
        preview_frame.grid(
            row=10,
            column=0,
            columnspan=2,
            sticky=(tk.W, tk.E),
            pady=(12, 8),
        )
        self._preview_label = ttk.Label(
            preview_frame,
            text="Preview unavailable",
            anchor=tk.CENTER,
        )
        self._preview_label.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            preview_frame,
            textvariable=self._preview_reference_var,
            wraplength=680,
        ).pack(fill=tk.X, pady=(6, 0))

        decision_frame = ttk.LabelFrame(
            content,
            text="Human decision",
            padding="8",
        )
        decision_frame.grid(
            row=11,
            column=0,
            columnspan=2,
            sticky=(tk.W, tk.E),
            pady=(8, 0),
        )
        decision_frame.columnconfigure(1, weight=1)
        ttk.Label(decision_frame, text="Correction:").grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        ttk.Entry(
            decision_frame,
            textvariable=self._correction_var,
        ).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 0))
        ttk.Label(decision_frame, text="Reason:").grid(
            row=1,
            column=0,
            sticky=tk.W,
            pady=(6, 0),
        )
        ttk.Entry(
            decision_frame,
            textvariable=self._reason_var,
        ).grid(
            row=1,
            column=1,
            sticky=(tk.W, tk.E),
            padx=(8, 0),
            pady=(6, 0),
        )

        action_frame = ttk.Frame(decision_frame)
        action_frame.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky=tk.W,
            pady=(10, 0),
        )
        self._action_buttons = (
            ttk.Button(
                action_frame,
                text="Approve",
                command=self._approve,
            ),
            ttk.Button(
                action_frame,
                text="Correct",
                command=self._correct,
            ),
            ttk.Button(
                action_frame,
                text="Reject",
                command=self._reject,
            ),
            ttk.Button(
                action_frame,
                text="Defer",
                command=self._defer,
            ),
        )
        for column, button in enumerate(self._action_buttons):
            button.grid(row=0, column=column, padx=(0, 6))

        ttk.Label(
            content,
            textvariable=self._error_var,
            foreground="red",
            wraplength=680,
        ).grid(
            row=12,
            column=0,
            columnspan=2,
            sticky=tk.W,
            pady=(8, 0),
        )

        navigation = ttk.Frame(content)
        navigation.grid(
            row=13,
            column=0,
            columnspan=2,
            sticky=(tk.W, tk.E),
            pady=(14, 0),
        )
        self._previous_button = ttk.Button(
            navigation,
            text="Previous",
            command=self._previous,
        )
        self._previous_button.pack(side=tk.LEFT)
        self._next_button = ttk.Button(
            navigation,
            text="Next",
            command=self._next,
        )
        self._next_button.pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(
            navigation,
            text="Close",
            command=self.close,
        ).pack(side=tk.RIGHT)

    def _render(self) -> None:
        display = self._model.display
        candidate = display.candidate
        self._position_var.set(display.position_label)

        if candidate is None:
            for variable in (
                self._coin_var,
                self._field_var,
                self._value_var,
                self._role_var,
                self._artifact_var,
                self._provider_var,
                self._human_state_var,
            ):
                variable.set("")
            self._confidence_var.set(display.confidence_label)
            self._evidence_var.set(display.evidence_label)
            self._preview_reference_var.set("")
            self._preview_image = None
            self._preview_label.config(
                image="",
                text="No OCR candidates",
            )
            for button in self._action_buttons:
                button.config(state=tk.DISABLED)
        else:
            self._coin_var.set(candidate.source_coin_id)
            self._field_var.set(candidate.field_label)
            self._value_var.set(candidate.original_value)
            self._role_var.set(candidate.image_role_label)
            self._artifact_var.set(candidate.artifact_key)
            self._provider_var.set(candidate.provider_id)
            self._confidence_var.set(display.confidence_label)
            self._evidence_var.set(display.evidence_label)
            self._human_state_var.set(candidate.human_review_label)
            for button in self._action_buttons:
                button.config(state=tk.NORMAL)
            self._render_preview(display.preview)

        review = self._model.current_review
        self._correction_var.set(
            ""
            if review is None or review.reviewed_value is None
            else review.reviewed_value
        )
        self._reason_var.set("" if review is None else review.reason)
        self._previous_button.config(
            state=(
                tk.NORMAL
                if display.has_candidate and display.candidate_index > 0
                else tk.DISABLED
            )
        )
        self._next_button.config(
            state=(
                tk.NORMAL
                if (
                    display.has_candidate
                    and display.candidate_index + 1
                    < display.candidate_count
                )
                else tk.DISABLED
            )
        )

    def _render_preview(
        self,
        preview: OCRCandidatePreview | None,
    ) -> None:
        if preview is None:
            self._preview_image = None
            self._preview_reference_var.set("")
            self._preview_label.config(
                image="",
                text="Preview unavailable",
            )
            return

        self._preview_reference_var.set(
            f"Reference: {preview.reference}"
        )
        if preview.image is not None:
            self._preview_image = preview.image
            self._preview_label.config(image=preview.image, text="")
        else:
            self._preview_image = None
            self._preview_label.config(
                image="",
                text=(
                    preview.unavailable_reason
                    or "Preview unavailable"
                ),
            )

    def _run_action(self, action: Callable[[], object]) -> None:
        try:
            action()
        except (TypeError, ValueError) as exc:
            self._error_var.set(str(exc))
            return
        self._error_var.set("")
        self._render()

    def _approve(self) -> None:
        self._run_action(
            lambda: self._model.approve(reason=self._reason_var.get())
        )

    def _correct(self) -> None:
        self._run_action(
            lambda: self._model.correct(
                corrected_value=self._correction_var.get(),
                reason=self._reason_var.get(),
            )
        )

    def _reject(self) -> None:
        self._run_action(
            lambda: self._model.reject(reason=self._reason_var.get())
        )

    def _defer(self) -> None:
        self._run_action(
            lambda: self._model.defer(reason=self._reason_var.get())
        )

    def _next(self) -> None:
        if self._model.next_candidate():
            self._error_var.set("")
            self._render()

    def _previous(self) -> None:
        if self._model.previous_candidate():
            self._error_var.set("")
            self._render()

    def close(self) -> None:
        if self._on_close is not None:
            self._on_close(self._model.reviews)
        self.window.destroy()


def create_ocr_candidate_review_dialog(
    *,
    parent: tk.Misc,
    report: OCRMetadataReport,
    review_controller: OCRReviewSessionController,
    reviewer_id: str,
    preview_resolver: PreviewResolver | None = None,
    on_close: ReviewCallback | None = None,
) -> OCRCandidateReviewDialog:
    """Explicitly construct the ephemeral candidate-review UI."""

    model = OCRCandidateReviewModel(
        report=report,
        review_controller=review_controller,
        reviewer_id=reviewer_id,
        preview_resolver=preview_resolver,
    )
    return OCRCandidateReviewDialog(
        parent=parent,
        model=model,
        on_close=on_close,
    )
