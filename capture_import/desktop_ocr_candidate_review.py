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
import math
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
AdjustedPreviewRenderer = Callable[[float, float], object]
ReviewCallback = Callable[[tuple[OCRFieldReview, ...]], None]
_PreviewIdentity = tuple[str, str, str]

_REVIEW_IMAGE_ROLES = ("front", "reverse")
_REVIEW_IMAGE_LABELS = {
    "front": "Obverse image",
    "reverse": "Reverse image",
}
_NARROW_PREVIEW_WIDTH = 620
_ZOOM_MINIMUM = 0.5
_ZOOM_DEFAULT = 1.0
_ZOOM_MAXIMUM = 3.0
_ZOOM_STEP = 0.25
_CONTRAST_MINIMUM = 0.5
_CONTRAST_DEFAULT = 1.0
_CONTRAST_MAXIMUM = 2.0
_CONTRAST_STEP = 0.1
_CROP_MINIMUM_SIZE = 0.20
_CROP_STEP = 0.05
_SELECTED_PREVIEW_STYLE = "SelectedCandidate.TLabelframe"
_RELATED_PREVIEW_STYLE = "RelatedCandidate.TLabelframe"


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


def _review_identity(review: OCRFieldReview) -> CandidateIdentity:
    return (
        review.source_coin_id,
        review.field_name,
        review.image_role,
        review.provider_id,
        review.artifact_key,
        review.original_value,
    )


@dataclass(frozen=True, slots=True)
class NormalizedCrop:
    """Immutable normalized rectangle retained for visual image review."""

    left: float = 0.0
    top: float = 0.0
    right: float = 1.0
    bottom: float = 1.0

    def __post_init__(self) -> None:
        coordinates = (self.left, self.top, self.right, self.bottom)
        if any(type(value) is not float for value in coordinates):
            raise TypeError("crop coordinates must be floats.")
        if any(not math.isfinite(value) for value in coordinates):
            raise ValueError("crop coordinates must be finite.")
        if any(value < 0.0 or value > 1.0 for value in coordinates):
            raise ValueError("crop coordinates must be between 0.0 and 1.0.")
        if self.left >= self.right or self.top >= self.bottom:
            raise ValueError("crop edges must define a non-empty rectangle.")
        if (
            self.right - self.left + 1e-9 < _CROP_MINIMUM_SIZE
            or self.bottom - self.top + 1e-9 < _CROP_MINIMUM_SIZE
        ):
            raise ValueError(
                "crop width and height must each be at least 0.20."
            )

    @property
    def label(self) -> str:
        return (
            f"Crop left {self.left:.2f}, top {self.top:.2f}, "
            f"right {self.right:.2f}, bottom {self.bottom:.2f}"
        )


CropAdjustedPreviewRenderer = Callable[[float, float, NormalizedCrop], object]
_FULL_IMAGE_CROP = NormalizedCrop()


@dataclass(frozen=True, slots=True)
class OCRCandidatePreview:
    """Injected preview result without filesystem or image-loading behavior."""

    reference: str
    image: object | None = None
    unavailable_reason: str | None = None
    adjusted_image_renderer: AdjustedPreviewRenderer | None = None
    crop_adjusted_image_renderer: CropAdjustedPreviewRenderer | None = None

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
        if (
            self.adjusted_image_renderer is not None
            and not callable(self.adjusted_image_renderer)
        ):
            raise TypeError(
                "adjusted_image_renderer must be callable or None."
            )
        if (
            self.crop_adjusted_image_renderer is not None
            and not callable(self.crop_adjusted_image_renderer)
        ):
            raise TypeError(
                "crop_adjusted_image_renderer must be callable or None."
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


@dataclass(frozen=True, slots=True)
class _OCRReviewSidePreview:
    """Private render state for one side of the current coin."""

    role: str
    label: str
    alt_text: str
    identity: _PreviewIdentity
    preview: OCRCandidatePreview
    is_selected: bool

    @property
    def selection_label(self) -> str:
        return (
            "Selected candidate reference"
            if self.is_selected
            else "Related image evidence (not selected)"
        )

    @property
    def panel_title(self) -> str:
        state = "Selected" if self.is_selected else "Related evidence"
        return f"{self.label} - {state}"


@dataclass(frozen=True, slots=True)
class _ImageReviewAdjustment:
    zoom: float = _ZOOM_DEFAULT
    contrast: float = _CONTRAST_DEFAULT
    crop: NormalizedCrop = _FULL_IMAGE_CROP

    @property
    def label(self) -> str:
        return f"Zoom {self.zoom:.2f}×; contrast {self.contrast:.2f}×"


class _ImageReviewAdjustmentStore:
    """Dialog-local adjustment values and rendered-image references."""

    __slots__ = ("_adjustments", "_rendered_images")

    def __init__(self) -> None:
        self._adjustments: dict[_PreviewIdentity, _ImageReviewAdjustment] = {}
        self._rendered_images: dict[_PreviewIdentity, object] = {}

    def adjustment(
        self,
        identity: _PreviewIdentity,
    ) -> _ImageReviewAdjustment:
        return self._adjustments.get(identity, _ImageReviewAdjustment())

    def displayed_image(
        self,
        identity: _PreviewIdentity,
        preview: OCRCandidatePreview,
    ) -> object | None:
        return self._rendered_images.get(identity, preview.image)

    @staticmethod
    def is_adjustable(preview: OCRCandidatePreview) -> bool:
        return (
            preview.image is not None
            and (
                preview.adjusted_image_renderer is not None
                or preview.crop_adjusted_image_renderer is not None
            )
        )

    @staticmethod
    def is_crop_adjustable(preview: OCRCandidatePreview) -> bool:
        return (
            preview.image is not None
            and preview.crop_adjusted_image_renderer is not None
        )

    def change_zoom(
        self,
        identity: _PreviewIdentity,
        preview: OCRCandidatePreview,
        steps: int,
    ) -> object:
        current = self.adjustment(identity)
        proposed = _ImageReviewAdjustment(
            zoom=_bounded_value(
                current.zoom + _require_steps(steps) * _ZOOM_STEP,
                _ZOOM_MINIMUM,
                _ZOOM_MAXIMUM,
            ),
            contrast=current.contrast,
            crop=current.crop,
        )
        return self._render(identity, preview, current, proposed)

    def change_contrast(
        self,
        identity: _PreviewIdentity,
        preview: OCRCandidatePreview,
        steps: int,
    ) -> object:
        current = self.adjustment(identity)
        proposed = _ImageReviewAdjustment(
            zoom=current.zoom,
            contrast=_bounded_value(
                current.contrast + _require_steps(steps) * _CONTRAST_STEP,
                _CONTRAST_MINIMUM,
                _CONTRAST_MAXIMUM,
            ),
            crop=current.crop,
        )
        return self._render(identity, preview, current, proposed)

    def change_crop(
        self,
        identity: _PreviewIdentity,
        preview: OCRCandidatePreview,
        edge: str,
        steps: int,
    ) -> object:
        if edge not in {"left", "top", "right", "bottom"}:
            raise ValueError("crop edge must be left, top, right, or bottom.")
        if not self.is_crop_adjustable(preview):
            raise ValueError(
                "Crop adjustments are unavailable for this preview."
            )
        current = self.adjustment(identity)
        crop = current.crop
        delta = _require_steps(steps) * _CROP_STEP
        values = {
            "left": crop.left,
            "top": crop.top,
            "right": crop.right,
            "bottom": crop.bottom,
        }
        limits = {
            "left": (0.0, crop.right - _CROP_MINIMUM_SIZE),
            "top": (0.0, crop.bottom - _CROP_MINIMUM_SIZE),
            "right": (crop.left + _CROP_MINIMUM_SIZE, 1.0),
            "bottom": (crop.top + _CROP_MINIMUM_SIZE, 1.0),
        }
        minimum, maximum = limits[edge]
        values[edge] = _bounded_value(values[edge] + delta, minimum, maximum)
        proposed = _ImageReviewAdjustment(
            zoom=current.zoom,
            contrast=current.contrast,
            crop=NormalizedCrop(**values),
        )
        return self._render(identity, preview, current, proposed)

    def reset(
        self,
        identity: _PreviewIdentity,
        preview: OCRCandidatePreview,
    ) -> object | None:
        self._adjustments.pop(identity, None)
        self._rendered_images.pop(identity, None)
        return preview.image

    def _render(
        self,
        identity: _PreviewIdentity,
        preview: OCRCandidatePreview,
        current: _ImageReviewAdjustment,
        proposed: _ImageReviewAdjustment,
    ) -> object:
        renderer = preview.adjusted_image_renderer
        crop_renderer = preview.crop_adjusted_image_renderer
        if (
            preview.image is None
            or (renderer is None and crop_renderer is None)
        ):
            raise ValueError(
                "Image adjustments are unavailable for this preview."
            )
        if proposed == current:
            displayed = self.displayed_image(identity, preview)
            if displayed is None:
                raise ValueError(
                    "Image adjustments are unavailable for this preview."
                )
            return displayed
        try:
            if crop_renderer is not None:
                rendered = crop_renderer(
                    proposed.zoom,
                    proposed.contrast,
                    proposed.crop,
                )
            else:
                if renderer is None:
                    raise ValueError(
                        "Image adjustments are unavailable for this preview."
                    )
                rendered = renderer(proposed.zoom, proposed.contrast)
        except Exception:
            raise ValueError("Image adjustment could not be rendered.") from None
        if rendered is None:
            raise ValueError("Image adjustment could not be rendered.")
        self._adjustments[identity] = proposed
        self._rendered_images[identity] = rendered
        return rendered


@dataclass(frozen=True, slots=True)
class _OCRReviewSideWidgets:
    side: _OCRReviewSidePreview
    image_label: ttk.Label
    adjustment_var: tk.StringVar
    crop_var: tk.StringVar


def _require_steps(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("adjustment steps must be an integer.")
    return value


def _bounded_value(value: float, minimum: float, maximum: float) -> float:
    return round(min(maximum, max(minimum, value)), 2)


def _preview_column_count(width: int) -> int:
    """Return the responsive preview column count for a dialog width."""

    return 1 if width < _NARROW_PREVIEW_WIDTH else 2


class OCRCandidateReviewModel:
    """Ephemeral candidate navigation and decision adapter."""

    __slots__ = (
        "_report",
        "_controller",
        "_reviewer_id",
        "_mode",
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
        reviews: tuple[OCRFieldReview, ...] = (),
        mode: OCRReviewMode = OCRReviewMode.PARTIAL,
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
        if not isinstance(reviews, tuple):
            raise TypeError("reviews must be a tuple.")
        if not isinstance(mode, OCRReviewMode):
            raise TypeError("mode must be an OCRReviewMode.")
        if preview_resolver is not None and not callable(preview_resolver):
            raise TypeError("preview_resolver must be callable or None.")

        state = review_controller.present_initial(report=report)
        reviews_by_identity: dict[
            CandidateIdentity,
            OCRFieldReview,
        ] = {}
        if reviews:
            report_review = OCRReportReview(
                reviewer_id=reviewer_id,
                field_reviews=reviews,
            )
            report_review.validate()
            candidate_identities = {
                _candidate_identity(candidate)
                for candidate in state.candidates
            }
            for review in reviews:
                identity = _review_identity(review)
                if identity not in candidate_identities:
                    raise ValueError(
                        "Persisted review does not target a presented "
                        "OCR candidate."
                    )
                reviews_by_identity[identity] = review
            ordered_reviews = tuple(
                reviews_by_identity[key]
                for key in sorted(reviews_by_identity)
            )
            state = review_controller.apply_field_reviews(
                report=report,
                review=OCRReportReview(
                    reviewer_id=reviewer_id,
                    field_reviews=ordered_reviews,
                ),
                mode=mode,
            )

        self._report = report
        self._controller = review_controller
        self._reviewer_id = reviewer_id
        self._mode = mode
        self._preview_resolver = preview_resolver
        self._state = state
        self._index = 0
        self._reviews_by_identity = reviews_by_identity

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
            mode=self._mode,
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

    def _side_previews(
        self,
        display: OCRCandidateReviewDisplay,
    ) -> tuple[_OCRReviewSidePreview, ...]:
        """Resolve available obverse/reverse evidence without changing APIs."""

        current = display.candidate
        if current is None:
            return ()

        candidates_by_role: dict[str, OCRReviewCandidateView] = {}
        for candidate in self._state.candidates:
            if candidate.source_coin_id != current.source_coin_id:
                continue
            if candidate.image_role not in _REVIEW_IMAGE_ROLES:
                continue
            candidates_by_role.setdefault(candidate.image_role, candidate)
        if current.image_role in _REVIEW_IMAGE_ROLES:
            candidates_by_role[current.image_role] = current

        sides = []
        current_identity = _candidate_identity(current)
        for role in _REVIEW_IMAGE_ROLES:
            candidate = candidates_by_role.get(role)
            if candidate is None:
                continue
            preview = (
                display.preview
                if candidate is current and display.preview is not None
                else self._resolve_preview(candidate)
            )
            label = _REVIEW_IMAGE_LABELS[role]
            is_selected = _candidate_identity(candidate) == current_identity
            selection_description = (
                "selected candidate reference"
                if is_selected
                else "related image evidence"
            )
            sides.append(
                _OCRReviewSidePreview(
                    role=role,
                    label=label,
                    alt_text=(
                        f"{label} for coin {candidate.source_coin_id}; "
                        f"{selection_description}"
                    ),
                    identity=(
                        candidate.source_coin_id,
                        role,
                        preview.reference,
                    ),
                    preview=preview,
                    is_selected=is_selected,
                )
            )

        if sides:
            return tuple(sides)

        preview = display.preview
        if preview is None:
            return ()
        return (
            _OCRReviewSidePreview(
                role=current.image_role,
                label="Source image",
                alt_text=(
                    f"Source image for coin {current.source_coin_id}; "
                    "selected candidate reference"
                ),
                identity=(
                    current.source_coin_id,
                    current.image_role,
                    preview.reference,
                ),
                preview=preview,
                is_selected=True,
            ),
        )


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
        self._adjustments = _ImageReviewAdjustmentStore()
        self._preview_images: dict[
            _PreviewIdentity,
            tuple[object, ...],
        ] = {}
        self._preview_panels: tuple[ttk.LabelFrame, ...] = ()
        self._preview_widgets: dict[
            _PreviewIdentity,
            _OCRReviewSideWidgets,
        ] = {}

        self.window = tk.Toplevel(parent)
        self.window.title("OCR Candidate Review")
        self.window.geometry("760x620")
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self._configure_candidate_highlight_styles()

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
        self._correction_var = tk.StringVar()
        self._reason_var = tk.StringVar()
        self._error_var = tk.StringVar()

        self._build_widgets()
        self._render()

    def _configure_candidate_highlight_styles(self) -> None:
        style = ttk.Style(self.window)
        style.configure(
            _SELECTED_PREVIEW_STYLE,
            borderwidth=3,
            relief=tk.SOLID,
        )
        style.configure(
            f"{_SELECTED_PREVIEW_STYLE}.Label",
            font=("TkDefaultFont", 10, "bold"),
        )
        style.configure(
            _RELATED_PREVIEW_STYLE,
            borderwidth=1,
            relief=tk.GROOVE,
        )

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

        self._preview_frame = ttk.LabelFrame(
            content,
            text="Coin image review",
            padding="8",
        )
        self._preview_frame.grid(
            row=10,
            column=0,
            columnspan=2,
            sticky=(tk.W, tk.E, tk.N, tk.S),
            pady=(12, 8),
        )
        self._preview_grid = ttk.Frame(self._preview_frame)
        self._preview_grid.pack(fill=tk.BOTH, expand=True)
        self._preview_frame.bind(
            "<Configure>",
            lambda event: self._layout_preview_panels(event.width),
        )

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
            self._render_side_previews(())
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
            self._render_side_previews(self._model._side_previews(display))

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

    def _render_side_previews(
        self,
        sides: tuple[_OCRReviewSidePreview, ...],
    ) -> None:
        for child in self._preview_grid.winfo_children():
            child.destroy()

        if not sides:
            ttk.Label(
                self._preview_grid,
                text="No obverse or reverse images are available for review.",
                anchor=tk.CENTER,
                takefocus=True,
            ).grid(row=0, column=0, sticky="nsew", padx=4, pady=8)
            self._preview_images = {}
            self._preview_panels = ()
            self._preview_widgets = {}
            return

        panels = []
        images: dict[_PreviewIdentity, tuple[object, ...]] = {}
        widgets: dict[_PreviewIdentity, _OCRReviewSideWidgets] = {}
        for side in sides:
            panel = ttk.LabelFrame(
                self._preview_grid,
                text=side.panel_title,
                padding="6",
                style=(
                    _SELECTED_PREVIEW_STYLE
                    if side.is_selected
                    else _RELATED_PREVIEW_STYLE
                ),
            )
            ttk.Label(
                panel,
                text=side.selection_label,
                font=(
                    ("TkDefaultFont", 10, "bold")
                    if side.is_selected
                    else "TkDefaultFont"
                ),
                takefocus=True,
            ).pack(fill=tk.X, pady=(0, 6))
            preview = side.preview
            displayed_image = self._adjustments.displayed_image(
                side.identity,
                preview,
            )
            if displayed_image is None:
                image_label = ttk.Label(
                    panel,
                    text=(
                        preview.unavailable_reason
                        or f"{side.label} unavailable"
                    ),
                    anchor=tk.CENTER,
                    takefocus=True,
                )
            else:
                image_label = ttk.Label(
                    panel,
                    image=displayed_image,
                    text=side.alt_text,
                    compound=tk.BOTTOM,
                    anchor=tk.CENTER,
                    takefocus=True,
                )
                retained = [displayed_image]
                if preview.image is not displayed_image:
                    retained.append(preview.image)
                images[side.identity] = tuple(retained)
            image_label.pack(fill=tk.BOTH, expand=True)
            ttk.Label(
                panel,
                text=f"Reference: {preview.reference}",
                wraplength=320,
            ).pack(fill=tk.X, pady=(6, 0))
            adjustment = self._adjustments.adjustment(side.identity)
            adjustment_var = tk.StringVar(value=adjustment.label)
            ttk.Label(
                panel,
                textvariable=adjustment_var,
                takefocus=True,
            ).pack(fill=tk.X, pady=(6, 0))
            crop_var = tk.StringVar(value=adjustment.crop.label)
            ttk.Label(
                panel,
                textvariable=crop_var,
                takefocus=True,
            ).pack(fill=tk.X, pady=(2, 0))
            controls = ttk.Frame(panel)
            controls.pack(fill=tk.X, pady=(4, 0))
            control_state = (
                tk.NORMAL
                if self._adjustments.is_adjustable(preview)
                else tk.DISABLED
            )
            control_specs = (
                (
                    "Zoom out",
                    lambda identity=side.identity: self._change_zoom(
                        identity,
                        -1,
                    ),
                ),
                (
                    "Zoom in",
                    lambda identity=side.identity: self._change_zoom(
                        identity,
                        1,
                    ),
                ),
                (
                    "Contrast down",
                    lambda identity=side.identity: self._change_contrast(
                        identity,
                        -1,
                    ),
                ),
                (
                    "Contrast up",
                    lambda identity=side.identity: self._change_contrast(
                        identity,
                        1,
                    ),
                ),
                (
                    "Reset view",
                    lambda identity=side.identity: self._reset_adjustment(
                        identity
                    ),
                ),
            )
            for index, (text, command) in enumerate(control_specs):
                ttk.Button(
                    controls,
                    text=text,
                    command=command,
                    state=control_state,
                    takefocus=True,
                ).grid(
                    row=index // 3,
                    column=index % 3,
                    padx=(0, 4),
                    pady=(0, 4),
                    sticky=tk.W,
                )
            crop_controls = ttk.LabelFrame(
                panel,
                text="Crop visible area",
                padding="4",
            )
            crop_controls.pack(fill=tk.X, pady=(2, 0))
            crop_state = (
                tk.NORMAL
                if self._adjustments.is_crop_adjustable(preview)
                else tk.DISABLED
            )
            crop_specs = (
                ("Left outward", "left", -1),
                ("Left inward", "left", 1),
                ("Top outward", "top", -1),
                ("Top inward", "top", 1),
                ("Right inward", "right", -1),
                ("Right outward", "right", 1),
                ("Bottom inward", "bottom", -1),
                ("Bottom outward", "bottom", 1),
            )
            for index, (text, edge, steps) in enumerate(crop_specs):
                ttk.Button(
                    crop_controls,
                    text=text,
                    command=(
                        lambda identity=side.identity, edge=edge, steps=steps:
                        self._change_crop(identity, edge, steps)
                    ),
                    state=crop_state,
                    takefocus=True,
                ).grid(
                    row=index // 2,
                    column=index % 2,
                    padx=(0, 4),
                    pady=(0, 4),
                    sticky=tk.W,
                )
            widgets[side.identity] = _OCRReviewSideWidgets(
                side=side,
                image_label=image_label,
                adjustment_var=adjustment_var,
                crop_var=crop_var,
            )
            panels.append(panel)

        self._preview_images = images
        self._preview_panels = tuple(panels)
        self._preview_widgets = widgets
        self._layout_preview_panels(self._preview_frame.winfo_width())

    def _change_zoom(self, identity: _PreviewIdentity, steps: int) -> None:
        self._change_adjustment(identity, "zoom", steps)

    def _change_contrast(
        self,
        identity: _PreviewIdentity,
        steps: int,
    ) -> None:
        self._change_adjustment(identity, "contrast", steps)

    def _change_crop(
        self,
        identity: _PreviewIdentity,
        edge: str,
        steps: int,
    ) -> None:
        widgets = self._preview_widgets[identity]
        try:
            image = self._adjustments.change_crop(
                identity,
                widgets.side.preview,
                edge,
                steps,
            )
        except (TypeError, ValueError) as exc:
            self._error_var.set(str(exc))
            return
        self._error_var.set("")
        self._display_adjusted_image(identity, widgets, image)

    def _change_adjustment(
        self,
        identity: _PreviewIdentity,
        adjustment_name: str,
        steps: int,
    ) -> None:
        widgets = self._preview_widgets[identity]
        try:
            if adjustment_name == "zoom":
                image = self._adjustments.change_zoom(
                    identity,
                    widgets.side.preview,
                    steps,
                )
            else:
                image = self._adjustments.change_contrast(
                    identity,
                    widgets.side.preview,
                    steps,
                )
        except (TypeError, ValueError) as exc:
            self._error_var.set(str(exc))
            return
        self._error_var.set("")
        self._display_adjusted_image(identity, widgets, image)

    def _display_adjusted_image(
        self,
        identity: _PreviewIdentity,
        widgets: _OCRReviewSideWidgets,
        image: object,
    ) -> None:
        widgets.image_label.config(image=image)
        original = widgets.side.preview.image
        retained = [image]
        if original is not None and original is not image:
            retained.append(original)
        self._preview_images[identity] = tuple(retained)
        widgets.adjustment_var.set(
            self._adjustments.adjustment(identity).label
        )
        widgets.crop_var.set(
            self._adjustments.adjustment(identity).crop.label
        )

    def _reset_adjustment(self, identity: _PreviewIdentity) -> None:
        widgets = self._preview_widgets[identity]
        image = self._adjustments.reset(identity, widgets.side.preview)
        if image is None:
            self._error_var.set(
                "Image adjustments are unavailable for this preview."
            )
            return
        self._error_var.set("")
        widgets.image_label.config(image=image)
        self._preview_images[identity] = (image,)
        widgets.adjustment_var.set(
            self._adjustments.adjustment(identity).label
        )
        widgets.crop_var.set(
            self._adjustments.adjustment(identity).crop.label
        )

    def _layout_preview_panels(self, width: int) -> None:
        columns = _preview_column_count(width)
        self._preview_grid.columnconfigure(0, weight=1)
        self._preview_grid.columnconfigure(
            1,
            weight=1 if columns == 2 else 0,
        )
        for index, panel in enumerate(self._preview_panels):
            panel.grid_forget()
            panel.grid(
                row=index // columns,
                column=index % columns,
                sticky="nsew",
                padx=4,
                pady=4,
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
    reviews: tuple[OCRFieldReview, ...] = (),
    mode: OCRReviewMode = OCRReviewMode.PARTIAL,
    preview_resolver: PreviewResolver | None = None,
    on_close: ReviewCallback | None = None,
) -> OCRCandidateReviewDialog:
    """Explicitly construct the ephemeral candidate-review UI."""

    model = OCRCandidateReviewModel(
        report=report,
        review_controller=review_controller,
        reviewer_id=reviewer_id,
        reviews=reviews,
        mode=mode,
        preview_resolver=preview_resolver,
    )
    return OCRCandidateReviewDialog(
        parent=parent,
        model=model,
        on_close=on_close,
    )
