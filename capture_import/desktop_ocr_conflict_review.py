"""Explicit Tkinter UI for resolving reviewed OCR metadata conflicts.

This module is opt-in and is not imported by default desktop startup.  Its
headless model reconstructs display state from immutable inputs and submits
every changed resolution aggregate through the Sprint 11 review controller.
The Tkinter dialog only adapts widget input to those model operations.
"""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Callable

from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
    OCRConflictResolutionRequest,
)
from capture_import.workflow_ocr_consolidation import (
    OCRConsolidatedField,
    OCRConsolidationStatus,
)
from capture_import.workflow_ocr_models import OCRMetadataReport
from capture_import.workflow_ocr_review_controller import (
    OCRReviewControllerState,
    OCRReviewSessionController,
)
from capture_import.workflow_ocr_review_models import OCRReportReview
from capture_import.workflow_ocr_review_presenter import (
    OCRConflictResolutionView,
    OCRFinalFieldView,
    OCRProvenanceView,
    OCRReviewCandidateView,
)
from capture_import.workflow_ocr_review_service import OCRReviewMode
from capture_import.workflow_ocr_review_session import (
    OCRReviewSessionConflictResolutionRequest,
    OCRReviewSessionRequest,
    OCRReviewSessionService,
)


ConflictIdentity = tuple[str, str]
ResolutionCallback = Callable[
    [tuple[OCRReviewSessionConflictResolutionRequest, ...]],
    None,
]


def _conflict_identity(
    conflict: OCRConflictResolutionView,
) -> ConflictIdentity:
    return (conflict.source_coin_id, conflict.field_name)


@dataclass(frozen=True, slots=True)
class OCRConflictProvenanceDisplay:
    """One uncollapsed provenance record with optional source-candidate data."""

    conflicting_value: str
    provider_id: str
    image_role: str
    image_role_label: str
    artifact_key: str
    source_value: str
    decision_label: str
    reason: str
    confidence_label: str
    evidence: tuple[str, ...]

    @property
    def evidence_label(self) -> str:
        return "\n".join(self.evidence) if self.evidence else "Unavailable"


@dataclass(frozen=True, slots=True)
class OCRConflictReviewDisplay:
    """Immutable render state for the current conflict and final projection."""

    conflict: OCRConflictResolutionView | None
    conflict_index: int
    conflict_count: int
    position_label: str
    provenance: tuple[OCRConflictProvenanceDisplay, ...]
    final_fields: tuple[OCRFinalFieldView, ...]
    unresolved_fields: tuple[OCRFinalFieldView, ...]
    is_complete: bool
    unresolved_field_count: int

    @property
    def has_conflict(self) -> bool:
        return self.conflict is not None


class OCRConflictReviewModel:
    """Ephemeral navigation and conflict-resolution interaction model."""

    __slots__ = (
        "_report",
        "_review",
        "_controller",
        "_mode",
        "_state",
        "_index",
        "_targets_by_identity",
        "_resolutions_by_identity",
    )

    def __init__(
        self,
        *,
        report: OCRMetadataReport,
        review: OCRReportReview,
        review_controller: OCRReviewSessionController,
        resolutions: tuple[
            OCRReviewSessionConflictResolutionRequest,
            ...,
        ] = (),
        mode: OCRReviewMode = OCRReviewMode.PARTIAL,
        session_service: OCRReviewSessionService | None = None,
    ) -> None:
        if not isinstance(
            review_controller,
            OCRReviewSessionController,
        ):
            raise TypeError(
                "review_controller must be an "
                "OCRReviewSessionController."
            )
        if not isinstance(resolutions, tuple):
            raise TypeError("resolutions must be a tuple.")
        if not isinstance(mode, OCRReviewMode):
            raise TypeError("mode must be an OCRReviewMode.")
        if (
            session_service is not None
            and not isinstance(session_service, OCRReviewSessionService)
        ):
            raise TypeError(
                "session_service must be an OCRReviewSessionService or None."
            )

        target_service = (
            OCRReviewSessionService()
            if session_service is None
            else session_service
        )
        baseline = target_service.run(
            request=OCRReviewSessionRequest(
                source_report=report,
                review=review,
                mode=mode,
            )
        )
        targets = tuple(
            field
            for field in baseline.consolidation.fields
            if field.status is OCRConsolidationStatus.CONFLICT
        )
        targets_by_identity = {
            (field.source_coin_id, field.field_name): field
            for field in targets
        }

        state = review_controller.present_session(
            report=report,
            review=review,
            resolutions=resolutions,
            mode=mode,
        )
        self._validate_state_targets(state, targets_by_identity)

        resolutions_by_identity: dict[
            ConflictIdentity,
            OCRReviewSessionConflictResolutionRequest,
        ] = {}
        for resolution in resolutions:
            resolution.validate()
            if resolution.identity in resolutions_by_identity:
                raise ValueError("Duplicate conflict resolution identity.")
            resolutions_by_identity[resolution.identity] = resolution

        self._report = report
        self._review = review
        self._controller = review_controller
        self._mode = mode
        self._state = state
        self._index = 0
        self._targets_by_identity = targets_by_identity
        self._resolutions_by_identity = resolutions_by_identity

    @staticmethod
    def _validate_state_targets(
        state: OCRReviewControllerState,
        targets: dict[ConflictIdentity, OCRConsolidatedField],
    ) -> None:
        if state.session is None:
            raise ValueError(
                "Conflict review requires a presented review session."
            )
        view_identities = {
            _conflict_identity(conflict)
            for conflict in state.session.conflict_resolutions
        }
        if view_identities != set(targets):
            raise ValueError(
                "Presented conflicts do not match consolidated targets."
            )

    @property
    def conflict_count(self) -> int:
        session = self._state.session
        return 0 if session is None else len(session.conflict_resolutions)

    @property
    def conflict_index(self) -> int:
        return self._index if self.conflict_count else 0

    @property
    def current_conflict(self) -> OCRConflictResolutionView | None:
        session = self._state.session
        if session is None or not session.conflict_resolutions:
            return None
        return session.conflict_resolutions[self._index]

    @property
    def current_resolution(
        self,
    ) -> OCRReviewSessionConflictResolutionRequest | None:
        conflict = self.current_conflict
        if conflict is None:
            return None
        return self._resolutions_by_identity.get(
            _conflict_identity(conflict)
        )

    @property
    def resolutions(
        self,
    ) -> tuple[OCRReviewSessionConflictResolutionRequest, ...]:
        return tuple(
            self._resolutions_by_identity[key]
            for key in sorted(self._resolutions_by_identity)
        )

    @property
    def display(self) -> OCRConflictReviewDisplay:
        session = self._state.session
        if session is None:
            raise ValueError(
                "Conflict review requires a presented review session."
            )
        conflict = self.current_conflict
        if conflict is None:
            return OCRConflictReviewDisplay(
                conflict=None,
                conflict_index=0,
                conflict_count=0,
                position_label="No OCR conflicts",
                provenance=(),
                final_fields=session.final_fields,
                unresolved_fields=session.unresolved_fields,
                is_complete=session.is_complete,
                unresolved_field_count=session.unresolved_field_count,
            )
        return OCRConflictReviewDisplay(
            conflict=conflict,
            conflict_index=self._index,
            conflict_count=self.conflict_count,
            position_label=(
                f"Conflict {self._index + 1} of {self.conflict_count}"
            ),
            provenance=tuple(
                self._present_provenance(conflict, provenance)
                for provenance in conflict.provenance
            ),
            final_fields=session.final_fields,
            unresolved_fields=session.unresolved_fields,
            is_complete=session.is_complete,
            unresolved_field_count=session.unresolved_field_count,
        )

    def next_conflict(self) -> bool:
        if self._index + 1 >= self.conflict_count:
            return False
        self._index += 1
        return True

    def previous_conflict(self) -> bool:
        if self._index == 0:
            return False
        self._index -= 1
        return True

    def select_existing(
        self,
        *,
        value: str,
    ) -> OCRReviewSessionConflictResolutionRequest:
        return self._submit(
            OCRConflictResolutionRequest(
                decision=(
                    OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
                ),
                value=value,
            )
        )

    def enter_corrected(
        self,
        *,
        value: str,
    ) -> OCRReviewSessionConflictResolutionRequest:
        return self._submit(
            OCRConflictResolutionRequest(
                decision=(
                    OCRConflictResolutionDecision.ENTER_CORRECTED_VALUE
                ),
                value=value,
            )
        )

    def defer(self) -> OCRReviewSessionConflictResolutionRequest:
        return self._submit(
            OCRConflictResolutionRequest(
                decision=OCRConflictResolutionDecision.DEFER,
                value=None,
            )
        )

    def _submit(
        self,
        request: OCRConflictResolutionRequest,
    ) -> OCRReviewSessionConflictResolutionRequest:
        conflict = self.current_conflict
        if conflict is None:
            raise ValueError("There is no OCR conflict to resolve.")
        identity = _conflict_identity(conflict)
        target = self._targets_by_identity[identity]
        resolution = OCRReviewSessionConflictResolutionRequest(
            field=target,
            request=request,
        )
        resolution.validate()

        proposed = dict(self._resolutions_by_identity)
        proposed[identity] = resolution
        ordered = tuple(proposed[key] for key in sorted(proposed))
        state = self._controller.apply_conflict_resolutions(
            report=self._report,
            review=self._review,
            resolutions=ordered,
            mode=self._mode,
        )
        self._validate_state_targets(state, self._targets_by_identity)

        self._resolutions_by_identity = proposed
        self._state = state
        return resolution

    def _present_provenance(
        self,
        conflict: OCRConflictResolutionView,
        provenance: OCRProvenanceView,
    ) -> OCRConflictProvenanceDisplay:
        candidate = self._find_candidate(conflict, provenance)
        confidence_label = (
            "Unavailable"
            if (
                candidate is None
                or isinstance(candidate.confidence_score, bool)
                or not isinstance(
                    candidate.confidence_score,
                    (int, float),
                )
            )
            else f"{float(candidate.confidence_score):.2f}%"
        )
        return OCRConflictProvenanceDisplay(
            conflicting_value=provenance.accepted_value,
            provider_id=provenance.provider_id,
            image_role=provenance.image_role,
            image_role_label=provenance.image_role_label,
            artifact_key=provenance.artifact_key,
            source_value=provenance.original_value,
            decision_label=provenance.decision_label,
            reason=provenance.reason,
            confidence_label=confidence_label,
            evidence=() if candidate is None else candidate.evidence,
        )

    def _find_candidate(
        self,
        conflict: OCRConflictResolutionView,
        provenance: OCRProvenanceView,
    ) -> OCRReviewCandidateView | None:
        matches = tuple(
            candidate
            for candidate in self._state.candidates
            if (
                candidate.source_coin_id == conflict.source_coin_id
                and candidate.field_name == conflict.field_name
                and candidate.image_role == provenance.image_role
                and candidate.artifact_key == provenance.artifact_key
                and candidate.provider_id == provenance.provider_id
                and candidate.original_value == provenance.original_value
            )
        )
        return matches[0] if len(matches) == 1 else None


class OCRConflictReviewDialog:
    """Concrete Tkinter dialog backed entirely by the headless model."""

    def __init__(
        self,
        *,
        parent: tk.Misc,
        model: OCRConflictReviewModel,
        on_close: ResolutionCallback | None = None,
    ) -> None:
        if not isinstance(model, OCRConflictReviewModel):
            raise TypeError("model must be an OCRConflictReviewModel.")
        if on_close is not None and not callable(on_close):
            raise TypeError("on_close must be callable or None.")

        self._model = model
        self._on_close = on_close
        self.window = tk.Toplevel(parent)
        self.window.title("OCR Conflict Resolution")
        self.window.geometry("800x660")
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self._position_var = tk.StringVar()
        self._coin_var = tk.StringVar()
        self._field_var = tk.StringVar()
        self._values_var = tk.StringVar()
        self._resolution_var = tk.StringVar()
        self._projection_var = tk.StringVar()
        self._provenance_var = tk.StringVar()
        self._existing_value_var = tk.StringVar()
        self._correction_var = tk.StringVar()
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
            ("Conflicting values", self._values_var),
            ("Current resolution", self._resolution_var),
            ("Final projection", self._projection_var),
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
                wraplength=590,
            ).grid(row=row, column=1, sticky=tk.W, pady=2)

        provenance_frame = ttk.LabelFrame(
            content,
            text="Provenance by conflicting value",
            padding="8",
        )
        provenance_frame.grid(
            row=6,
            column=0,
            columnspan=2,
            sticky=(tk.W, tk.E),
            pady=(12, 8),
        )
        ttk.Label(
            provenance_frame,
            textvariable=self._provenance_var,
            wraplength=730,
            justify=tk.LEFT,
        ).pack(fill=tk.X)

        decision_frame = ttk.LabelFrame(
            content,
            text="Resolution",
            padding="8",
        )
        decision_frame.grid(
            row=7,
            column=0,
            columnspan=2,
            sticky=(tk.W, tk.E),
        )
        decision_frame.columnconfigure(1, weight=1)
        ttk.Label(decision_frame, text="Existing value:").grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        self._existing_values = ttk.Combobox(
            decision_frame,
            textvariable=self._existing_value_var,
            state="readonly",
        )
        self._existing_values.grid(
            row=0,
            column=1,
            sticky=(tk.W, tk.E),
            padx=(8, 0),
        )
        self._select_existing_button = ttk.Button(
            decision_frame,
            text="Select Existing",
            command=self._select_existing,
        )
        self._select_existing_button.grid(
            row=0,
            column=2,
            padx=(8, 0),
        )

        ttk.Label(decision_frame, text="Correction:").grid(
            row=1,
            column=0,
            sticky=tk.W,
            pady=(8, 0),
        )
        ttk.Entry(
            decision_frame,
            textvariable=self._correction_var,
        ).grid(
            row=1,
            column=1,
            sticky=(tk.W, tk.E),
            padx=(8, 0),
            pady=(8, 0),
        )
        self._correct_button = ttk.Button(
            decision_frame,
            text="Use Correction",
            command=self._enter_corrected,
        )
        self._correct_button.grid(
            row=1,
            column=2,
            padx=(8, 0),
            pady=(8, 0),
        )
        self._defer_button = ttk.Button(
            decision_frame,
            text="Defer",
            command=self._defer,
        )
        self._defer_button.grid(
            row=2,
            column=2,
            sticky=tk.E,
            pady=(8, 0),
        )
        self._action_buttons = (
            self._select_existing_button,
            self._correct_button,
            self._defer_button,
        )

        ttk.Label(
            content,
            textvariable=self._error_var,
            foreground="red",
            wraplength=730,
        ).grid(
            row=8,
            column=0,
            columnspan=2,
            sticky=tk.W,
            pady=(8, 0),
        )

        navigation = ttk.Frame(content)
        navigation.grid(
            row=9,
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
        conflict = display.conflict
        self._position_var.set(display.position_label)
        self._projection_var.set(
            f"{'Complete' if display.is_complete else 'Incomplete'}; "
            f"{display.unresolved_field_count} unresolved"
        )

        if conflict is None:
            self._coin_var.set("")
            self._field_var.set("")
            self._values_var.set("")
            self._resolution_var.set("No conflict")
            self._provenance_var.set("No provenance")
            self._existing_values.configure(values=(), state=tk.DISABLED)
            self._existing_value_var.set("")
            self._correction_var.set("")
            for button in self._action_buttons:
                button.config(state=tk.DISABLED)
        else:
            self._coin_var.set(conflict.source_coin_id)
            self._field_var.set(conflict.field_label)
            self._values_var.set(
                "\n".join(conflict.available_existing_values)
            )
            self._resolution_var.set(
                self._format_resolution(conflict)
            )
            self._provenance_var.set(
                self._format_provenance(display)
            )
            self._existing_values.configure(
                values=conflict.available_existing_values,
                state="readonly",
            )
            for button in self._action_buttons:
                button.config(state=tk.NORMAL)
            resolution = self._model.current_resolution
            decision = (
                None if resolution is None else resolution.request.decision
            )
            value = (
                None if resolution is None else resolution.request.value
            )
            self._existing_value_var.set(
                value
                if (
                    decision
                    is OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
                )
                else ""
            )
            self._correction_var.set(
                value
                if (
                    decision
                    is OCRConflictResolutionDecision.ENTER_CORRECTED_VALUE
                )
                else ""
            )

        self._previous_button.config(
            state=(
                tk.NORMAL
                if display.has_conflict and display.conflict_index > 0
                else tk.DISABLED
            )
        )
        self._next_button.config(
            state=(
                tk.NORMAL
                if (
                    display.has_conflict
                    and display.conflict_index + 1
                    < display.conflict_count
                )
                else tk.DISABLED
            )
        )

    @staticmethod
    def _format_resolution(
        conflict: OCRConflictResolutionView,
    ) -> str:
        if conflict.resolution_decision is None:
            return "Unresolved"
        if conflict.is_deferred:
            return conflict.resolution_decision_label
        return (
            f"{conflict.resolution_decision_label}: "
            f"{conflict.selected_or_corrected_value}"
        )

    @staticmethod
    def _format_provenance(
        display: OCRConflictReviewDisplay,
    ) -> str:
        if not display.provenance:
            return "No provenance available"
        lines: list[str] = []
        for value in display.conflict.available_existing_values:
            lines.append(f"Value: {value}")
            matching = tuple(
                item
                for item in display.provenance
                if item.conflicting_value == value
            )
            if not matching:
                lines.append("  Provenance unavailable")
                continue
            for item in matching:
                evidence = (
                    "; ".join(item.evidence)
                    if item.evidence
                    else "Unavailable"
                )
                lines.append(
                    "  "
                    f"{item.provider_id} | {item.image_role_label} | "
                    f"{item.artifact_key} | source {item.source_value} | "
                    f"confidence {item.confidence_label} | "
                    f"evidence {evidence}"
                )
        return "\n".join(lines)

    def _run_action(self, action: Callable[[], object]) -> None:
        try:
            action()
        except (TypeError, ValueError) as exc:
            self._error_var.set(str(exc))
            return
        self._error_var.set("")
        self._render()

    def _select_existing(self) -> None:
        self._run_action(
            lambda: self._model.select_existing(
                value=self._existing_value_var.get()
            )
        )

    def _enter_corrected(self) -> None:
        self._run_action(
            lambda: self._model.enter_corrected(
                value=self._correction_var.get()
            )
        )

    def _defer(self) -> None:
        self._run_action(self._model.defer)

    def _next(self) -> None:
        if self._model.next_conflict():
            self._error_var.set("")
            self._render()

    def _previous(self) -> None:
        if self._model.previous_conflict():
            self._error_var.set("")
            self._render()

    def close(self) -> None:
        if self._on_close is not None:
            self._on_close(self._model.resolutions)
        self.window.destroy()


def create_ocr_conflict_review_dialog(
    *,
    parent: tk.Misc,
    report: OCRMetadataReport,
    review: OCRReportReview,
    review_controller: OCRReviewSessionController,
    resolutions: tuple[
        OCRReviewSessionConflictResolutionRequest,
        ...,
    ] = (),
    mode: OCRReviewMode = OCRReviewMode.PARTIAL,
    session_service: OCRReviewSessionService | None = None,
    on_close: ResolutionCallback | None = None,
) -> OCRConflictReviewDialog:
    """Explicitly construct the ephemeral conflict-resolution UI."""

    model = OCRConflictReviewModel(
        report=report,
        review=review,
        review_controller=review_controller,
        resolutions=resolutions,
        mode=mode,
        session_service=session_service,
    )
    return OCRConflictReviewDialog(
        parent=parent,
        model=model,
        on_close=on_close,
    )
