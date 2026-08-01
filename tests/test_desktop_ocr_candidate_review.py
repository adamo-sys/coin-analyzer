"""Headless tests for the first desktop OCR candidate-review UI slice."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import importlib
import inspect
import json
import unittest
from unittest.mock import patch

from capture_import.desktop_ocr_candidate_review import (
    AdjustedPreviewRenderer,
    CropAdjustedPreviewRenderer,
    NormalizedCrop,
    OCRCandidatePreview,
    OCRCandidateReviewDialog,
    OCRCandidateReviewDisplay,
    OCRCandidateReviewModel,
    _CONTRAST_MAXIMUM,
    _CONTRAST_MINIMUM,
    _CROP_MINIMUM_SIZE,
    _CROP_STEP,
    _ImageReviewAdjustmentStore,
    _ZOOM_MAXIMUM,
    _ZOOM_MINIMUM,
    _preview_column_count,
    create_ocr_candidate_review_dialog,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRReviewStatus,
)
from capture_import.workflow_ocr_review_controller import (
    OCRReviewControllerState,
    OCRReviewSessionController,
)
from capture_import.workflow_ocr_review_models import OCRReviewDecision
from capture_import.workflow_ocr_review_presenter import OCRReviewPresenter
from capture_import.workflow_stages import build_image_processing_pipeline


def _candidate(
    *,
    source_coin_id: str = "coin-1",
    field_name: str = "year",
    value: str = "1967",
    image_role: str = "front",
    artifact_key: str = "crop-1",
    provider_id: str = "provider-1",
    confidence_score: float = 94.5,
    evidence: tuple[str, ...] = (),
) -> OCRFieldCandidate:
    return OCRFieldCandidate(
        source_coin_id=source_coin_id,
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id=provider_id,
        field_name=field_name,
        raw_text=f"raw {value}",
        normalized_value=value,
        confidence_score=confidence_score,
        evidence=evidence,
    )


def _report(*candidates: OCRFieldCandidate) -> OCRMetadataReport:
    return OCRMetadataReport(
        provider_available=True,
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
        review_status=OCRReviewStatus.REVIEW_REQUIRED,
    )


class RecordingController(OCRReviewSessionController):
    def __init__(self) -> None:
        super().__init__()
        self.initial_calls = 0
        self.review_calls = 0

    def present_initial(self, *, report):
        self.initial_calls += 1
        return super().present_initial(report=report)

    def apply_field_reviews(self, *, report, review, mode):
        self.review_calls += 1
        return super().apply_field_reviews(
            report=report,
            review=review,
            mode=mode,
        )


class MissingConfidenceController(OCRReviewSessionController):
    def present_initial(self, *, report):
        state = super().present_initial(report=report)
        candidate = replace(
            state.candidates[0],
            confidence_score=None,  # type: ignore[arg-type]
        )
        return OCRReviewControllerState(
            candidates=(candidate,),
            mode=None,
            session=None,
        )


class OCRCandidateReviewModelTests(unittest.TestCase):
    def model(
        self,
        *candidates: OCRFieldCandidate,
        controller: OCRReviewSessionController | None = None,
        preview_resolver=None,
    ) -> OCRCandidateReviewModel:
        return OCRCandidateReviewModel(
            report=_report(*candidates),
            review_controller=(
                OCRReviewSessionController()
                if controller is None
                else controller
            ),
            reviewer_id="reviewer-1",
            preview_resolver=preview_resolver,
        )

    def test_component_is_constructed_explicitly_without_ocr_execution(
        self,
    ) -> None:
        controller = RecordingController()

        model = self.model(_candidate(), controller=controller)

        self.assertIsInstance(model, OCRCandidateReviewModel)
        self.assertEqual(controller.initial_calls, 1)
        self.assertEqual(controller.review_calls, 0)
        self.assertNotIn(
            "ocr-metadata-extraction",
            build_image_processing_pipeline().stage_ids,
        )

    def test_one_candidate_display_uses_unit_1a_state(self) -> None:
        display = self.model(_candidate()).display

        self.assertIsInstance(display, OCRCandidateReviewDisplay)
        self.assertEqual(display.position_label, "Candidate 1 of 1")
        self.assertEqual(display.candidate.source_coin_id, "coin-1")
        self.assertEqual(display.candidate.field_label, "Year")
        self.assertEqual(display.candidate.original_value, "1967")
        self.assertEqual(display.candidate.image_role, "front")
        self.assertEqual(display.candidate.artifact_key, "crop-1")
        self.assertEqual(display.candidate.provider_id, "provider-1")

    def test_multiple_candidates_use_deterministic_order(self) -> None:
        model = self.model(
            _candidate(source_coin_id="coin-2"),
            _candidate(source_coin_id="coin-1"),
            _candidate(
                source_coin_id="coin-1",
                field_name="country",
                value="Canada",
                image_role="reverse",
                artifact_key="country",
            ),
        )

        identities = []
        while True:
            candidate = model.current_candidate
            identities.append(
                (candidate.source_coin_id, candidate.field_name)
            )
            if not model.next_candidate():
                break

        self.assertEqual(
            identities,
            [
                ("coin-1", "country"),
                ("coin-1", "year"),
                ("coin-2", "year"),
            ],
        )

    def test_position_and_count_update_during_navigation(self) -> None:
        model = self.model(
            _candidate(field_name="country", value="Canada"),
            _candidate(),
        )

        self.assertEqual(model.display.position_label, "Candidate 1 of 2")
        model.next_candidate()
        self.assertEqual(model.display.position_label, "Candidate 2 of 2")

    def test_confidence_evidence_and_provenance_are_visible(self) -> None:
        display = self.model(
            _candidate(
                confidence_score=87.25,
                evidence=("date glyphs", "reverse legend"),
            )
        ).display

        self.assertEqual(display.confidence_label, "87.25%")
        self.assertEqual(
            display.evidence_label,
            "date glyphs\nreverse legend",
        )
        self.assertEqual(display.candidate.provider_id, "provider-1")
        self.assertEqual(display.candidate.image_role, "front")
        self.assertEqual(display.candidate.artifact_key, "crop-1")

    def test_missing_confidence_and_evidence_are_safe(self) -> None:
        display = self.model(
            _candidate(),
            controller=MissingConfidenceController(),
        ).display

        self.assertEqual(display.confidence_label, "Unavailable")
        self.assertEqual(display.evidence_label, "No evidence")

    def test_available_preview_reference_and_image_are_preserved(self) -> None:
        image = object()
        seen = []

        def resolve(candidate):
            seen.append(candidate)
            return OCRCandidatePreview(
                reference="snapshot:crop-1",
                image=image,
            )

        display = self.model(
            _candidate(),
            preview_resolver=resolve,
        ).display

        self.assertEqual(len(seen), 1)
        self.assertEqual(display.preview.reference, "snapshot:crop-1")
        self.assertIs(display.preview.image, image)

    def test_unavailable_preview_uses_artifact_reference(self) -> None:
        display = self.model(_candidate()).display

        self.assertEqual(display.preview.reference, "crop-1")
        self.assertEqual(
            display.preview.unavailable_reason,
            "Preview unavailable",
        )

    def test_preview_resolver_failure_is_displayed_safely(self) -> None:
        def fail(_candidate):
            raise RuntimeError("image lease closed")

        display = self.model(
            _candidate(),
            preview_resolver=fail,
        ).display

        self.assertEqual(display.preview.reference, "crop-1")
        self.assertEqual(
            display.preview.unavailable_reason,
            "Preview unavailable: image lease closed",
        )

    def test_two_sided_review_resolves_obverse_and_reverse_together(
        self,
    ) -> None:
        images = {"front": object(), "reverse": object()}

        def resolve(candidate):
            return OCRCandidatePreview(
                reference=candidate.artifact_key,
                image=images[candidate.image_role],
            )

        model = self.model(
            _candidate(image_role="front", artifact_key="obverse-crop"),
            _candidate(
                field_name="country",
                value="Canada",
                image_role="reverse",
                artifact_key="reverse-crop",
            ),
            preview_resolver=resolve,
        )

        sides = model._side_previews(model.display)

        self.assertEqual(
            tuple(side.role for side in sides),
            ("front", "reverse"),
        )
        self.assertEqual(
            tuple(side.label for side in sides),
            ("Obverse image", "Reverse image"),
        )
        self.assertIs(sides[0].preview.image, images["front"])
        self.assertIs(sides[1].preview.image, images["reverse"])

    def test_one_sided_review_has_clear_obverse_state(self) -> None:
        model = self.model(_candidate(image_role="front"))

        sides = model._side_previews(model.display)

        self.assertEqual(len(sides), 1)
        self.assertEqual(sides[0].label, "Obverse image")
        self.assertEqual(
            sides[0].alt_text,
            "Obverse image for coin coin-1",
        )
        self.assertEqual(
            sides[0].preview.unavailable_reason,
            "Preview unavailable",
        )

    def test_empty_review_has_no_side_previews(self) -> None:
        model = self.model()

        self.assertEqual(model._side_previews(model.display), ())

    def test_side_previews_are_scoped_to_current_coin(self) -> None:
        model = self.model(
            _candidate(source_coin_id="coin-1", image_role="front"),
            _candidate(
                source_coin_id="coin-2",
                field_name="country",
                value="Canada",
                image_role="reverse",
            ),
        )

        sides = model._side_previews(model.display)

        self.assertEqual(tuple(side.role for side in sides), ("front",))

    def test_preview_layout_stacks_at_narrow_widths(self) -> None:
        self.assertEqual(_preview_column_count(619), 1)
        self.assertEqual(_preview_column_count(620), 2)

    def test_side_preview_accessibility_metadata_is_meaningful(self) -> None:
        model = self.model(
            _candidate(image_role="reverse", artifact_key="reverse-crop")
        )

        side = model._side_previews(model.display)[0]

        self.assertEqual(side.label, "Reverse image")
        self.assertEqual(
            side.alt_text,
            "Reverse image for coin coin-1",
        )

    def test_existing_current_preview_contract_is_preserved(self) -> None:
        image = object()
        model = self.model(
            _candidate(),
            preview_resolver=lambda _candidate: OCRCandidatePreview(
                reference="existing-reference",
                image=image,
            ),
        )

        display = model.display

        self.assertEqual(display.preview.reference, "existing-reference")
        self.assertIs(display.preview.image, image)

    def test_adjusted_preview_renderer_contract_is_optional(self) -> None:
        image = object()

        legacy = OCRCandidatePreview(reference="legacy", image=image)
        renderer: AdjustedPreviewRenderer = lambda _zoom, _contrast: object()
        adjustable = OCRCandidatePreview(
            reference="adjustable",
            image=image,
            adjusted_image_renderer=renderer,
        )

        self.assertIsNone(legacy.adjusted_image_renderer)
        self.assertIs(adjustable.adjusted_image_renderer, renderer)
        with self.assertRaisesRegex(TypeError, "must be callable"):
            OCRCandidatePreview(
                reference="invalid",
                adjusted_image_renderer=object(),  # type: ignore[arg-type]
            )

    def test_crop_renderer_contract_is_optional_and_precisely_typed(self) -> None:
        renderer: CropAdjustedPreviewRenderer = (
            lambda _zoom, _contrast, _crop: object()
        )
        preview = OCRCandidatePreview(
            reference="crop-capable",
            image=object(),
            crop_adjusted_image_renderer=renderer,
        )

        self.assertIs(preview.crop_adjusted_image_renderer, renderer)
        self.assertIsNone(
            OCRCandidatePreview(reference="legacy").crop_adjusted_image_renderer
        )
        self.assertEqual(
            CropAdjustedPreviewRenderer,
            __import__("typing").Callable[[float, float, NormalizedCrop], object],
        )
        with self.assertRaisesRegex(TypeError, "must be callable"):
            OCRCandidatePreview(
                reference="invalid",
                crop_adjusted_image_renderer=object(),  # type: ignore[arg-type]
            )

    def test_normalized_crop_defaults_are_full_image_and_immutable(self) -> None:
        crop = NormalizedCrop()

        self.assertEqual(
            (crop.left, crop.top, crop.right, crop.bottom),
            (0.0, 0.0, 1.0, 1.0),
        )
        self.assertEqual(
            crop.label,
            "Crop left 0.00, top 0.00, right 1.00, bottom 1.00",
        )
        with self.assertRaises(FrozenInstanceError):
            crop.left = 0.1  # type: ignore[misc]
        with self.assertRaises(AttributeError):
            crop.extra = True  # type: ignore[attr-defined]

    def test_normalized_crop_accepts_valid_edges_and_minimum_dimensions(self) -> None:
        crop = NormalizedCrop(0.15, 0.25, 0.80, 0.45)

        self.assertEqual(crop, NormalizedCrop(0.15, 0.25, 0.80, 0.45))
        self.assertEqual(crop.bottom - crop.top, _CROP_MINIMUM_SIZE)

    def test_normalized_crop_rejects_invalid_types_and_nonfinite_values(self) -> None:
        for invalid in (0, True, "0", None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(TypeError):
                    NormalizedCrop(left=invalid)  # type: ignore[arg-type]
        for invalid in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "finite"):
                    NormalizedCrop(left=invalid)

    def test_normalized_crop_rejects_bounds_empty_inversion_and_small_regions(
        self,
    ) -> None:
        invalid_crops = (
            (-0.01, 0.0, 1.0, 1.0),
            (0.0, 0.0, 1.01, 1.0),
            (0.5, 0.0, 0.5, 1.0),
            (0.7, 0.0, 0.5, 1.0),
            (0.0, 0.5, 1.0, 0.5),
            (0.0, 0.7, 1.0, 0.5),
            (0.0, 0.0, 0.19, 1.0),
            (0.0, 0.0, 1.0, 0.19),
        )
        for values in invalid_crops:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    NormalizedCrop(*values)

    def test_crop_composes_with_zoom_and_contrast_and_forwards_exact_values(
        self,
    ) -> None:
        calls = []
        preview = OCRCandidatePreview(
            reference="front",
            image=object(),
            crop_adjusted_image_renderer=lambda zoom, contrast, crop: (
                calls.append((zoom, contrast, crop)) or object()
            ),
        )
        store = _ImageReviewAdjustmentStore()
        identity = ("coin-1", "front", "front")

        store.change_zoom(identity, preview, 1)
        store.change_contrast(identity, preview, 1)
        store.change_crop(identity, preview, "left", 1)

        expected_crop = NormalizedCrop(0.05, 0.0, 1.0, 1.0)
        self.assertEqual(calls[-1], (1.25, 1.1, expected_crop))
        self.assertEqual(store.adjustment(identity).crop, expected_crop)

    def test_crop_renderer_supersedes_old_renderer_for_composed_adjustments(
        self,
    ) -> None:
        old_calls = []
        crop_calls = []
        preview = OCRCandidatePreview(
            reference="front",
            image=object(),
            adjusted_image_renderer=lambda zoom, contrast: (
                old_calls.append((zoom, contrast)) or object()
            ),
            crop_adjusted_image_renderer=lambda zoom, contrast, crop: (
                crop_calls.append((zoom, contrast, crop)) or object()
            ),
        )
        store = _ImageReviewAdjustmentStore()

        store.change_zoom(("coin-1", "front", "front"), preview, 1)

        self.assertEqual(old_calls, [])
        self.assertEqual(crop_calls, [(1.25, 1.0, NormalizedCrop())])

    def test_crop_edges_are_bounded_and_enforce_minimum_dimensions(self) -> None:
        preview = OCRCandidatePreview(
            reference="front",
            image=object(),
            crop_adjusted_image_renderer=lambda _zoom, _contrast, _crop: object(),
        )
        store = _ImageReviewAdjustmentStore()
        identity = ("coin-1", "front", "front")

        store.change_crop(identity, preview, "left", 100)
        self.assertEqual(store.adjustment(identity).crop.left, 0.8)
        store.change_crop(identity, preview, "right", -100)
        self.assertEqual(store.adjustment(identity).crop.right, 1.0)
        store.change_crop(identity, preview, "left", -100)
        store.change_crop(identity, preview, "top", 100)
        self.assertEqual(store.adjustment(identity).crop.top, 0.8)
        store.change_crop(identity, preview, "bottom", -100)
        self.assertEqual(store.adjustment(identity).crop.bottom, 1.0)
        with self.assertRaisesRegex(ValueError, "crop edge"):
            store.change_crop(identity, preview, "center", 1)
        with self.assertRaisesRegex(TypeError, "steps"):
            store.change_crop(identity, preview, "left", True)  # type: ignore[arg-type]

    def test_each_crop_edge_moves_by_the_documented_step(self) -> None:
        preview = OCRCandidatePreview(
            reference="front",
            image=object(),
            crop_adjusted_image_renderer=(
                lambda _zoom, _contrast, _crop: object()
            ),
        )
        cases = (
            ("left", 1, "left", 0.05),
            ("top", 1, "top", 0.05),
            ("right", -1, "right", 0.95),
            ("bottom", -1, "bottom", 0.95),
        )

        for edge, steps, attribute, expected in cases:
            with self.subTest(edge=edge):
                store = _ImageReviewAdjustmentStore()
                identity = ("coin-1", "front", edge)
                store.change_crop(identity, preview, edge, steps)
                self.assertEqual(
                    getattr(store.adjustment(identity).crop, attribute),
                    expected,
                )

    def test_crop_state_is_independent_by_side_and_reference(self) -> None:
        preview = OCRCandidatePreview(
            reference="shared",
            image=object(),
            crop_adjusted_image_renderer=lambda _zoom, _contrast, _crop: object(),
        )
        store = _ImageReviewAdjustmentStore()
        front = ("coin-1", "front", "front-a")
        reverse = ("coin-1", "reverse", "reverse-a")
        next_front = ("coin-1", "front", "front-b")

        store.change_crop(front, preview, "left", 1)
        store.change_crop(reverse, preview, "right", -1)

        self.assertEqual(store.adjustment(front).crop.left, _CROP_STEP)
        self.assertEqual(store.adjustment(reverse).crop.right, 1.0 - _CROP_STEP)
        self.assertEqual(store.adjustment(next_front).crop, NormalizedCrop())

    def test_reset_restores_full_crop_and_exact_original_without_callback(self) -> None:
        original = object()
        calls = []
        preview = OCRCandidatePreview(
            reference="front",
            image=original,
            crop_adjusted_image_renderer=lambda zoom, contrast, crop: (
                calls.append((zoom, contrast, crop)) or object()
            ),
        )
        store = _ImageReviewAdjustmentStore()
        identity = ("coin-1", "front", "front")
        store.change_crop(identity, preview, "left", 1)

        self.assertIs(store.reset(identity, preview), original)
        self.assertEqual(len(calls), 1)
        self.assertEqual(store.adjustment(identity).crop, NormalizedCrop())
        self.assertEqual(store.adjustment(identity).zoom, 1.0)
        self.assertEqual(store.adjustment(identity).contrast, 1.0)

    def test_crop_render_failure_rolls_back_state_and_display_image(self) -> None:
        valid = object()
        calls = 0

        def render(_zoom, _contrast, _crop):
            nonlocal calls
            calls += 1
            if calls == 1:
                return valid
            raise RuntimeError("pixel detail must not leak")

        preview = OCRCandidatePreview(
            reference="front",
            image=object(),
            crop_adjusted_image_renderer=render,
        )
        store = _ImageReviewAdjustmentStore()
        identity = ("coin-1", "front", "front")
        store.change_crop(identity, preview, "left", 1)

        with self.assertRaisesRegex(ValueError, "could not be rendered") as ctx:
            store.change_crop(identity, preview, "top", 1)

        self.assertNotIn("pixel", str(ctx.exception))
        self.assertEqual(
            store.adjustment(identity).crop,
            NormalizedCrop(0.05, 0.0, 1.0, 1.0),
        )
        self.assertIs(store.displayed_image(identity, preview), valid)

    def test_legacy_and_zoom_only_previews_disable_crop_without_breaking_adjustments(
        self,
    ) -> None:
        store = _ImageReviewAdjustmentStore()
        legacy = OCRCandidatePreview(reference="legacy", image=object())
        zoom_only = OCRCandidatePreview(
            reference="zoom-only",
            image=object(),
            adjusted_image_renderer=lambda _zoom, _contrast: object(),
        )

        self.assertFalse(store.is_crop_adjustable(legacy))
        self.assertFalse(store.is_crop_adjustable(zoom_only))
        self.assertTrue(store.is_adjustable(zoom_only))
        store.change_zoom(("coin-1", "front", "zoom-only"), zoom_only, 1)
        with self.assertRaisesRegex(ValueError, "Crop adjustments"):
            store.change_crop(
                ("coin-1", "front", "zoom-only"),
                zoom_only,
                "left",
                1,
            )

    def test_crop_only_renderer_supports_zoom_contrast_and_retains_rendered_image(
        self,
    ) -> None:
        rendered = object()
        preview = OCRCandidatePreview(
            reference="crop-only",
            image=object(),
            crop_adjusted_image_renderer=lambda _zoom, _contrast, _crop: rendered,
        )
        store = _ImageReviewAdjustmentStore()
        identity = ("coin-1", "front", "crop-only")

        self.assertTrue(store.is_adjustable(preview))
        self.assertTrue(store.is_crop_adjustable(preview))
        self.assertIs(store.change_contrast(identity, preview, 1), rendered)
        self.assertIs(store.displayed_image(identity, preview), rendered)

    def test_adjustment_defaults_and_callback_argument_forwarding(self) -> None:
        calls = []
        rendered = object()
        preview = OCRCandidatePreview(
            reference="front",
            image=object(),
            adjusted_image_renderer=lambda zoom, contrast: (
                calls.append((zoom, contrast)) or rendered
            ),
        )
        store = _ImageReviewAdjustmentStore()
        identity = ("coin-1", "front", "front")

        self.assertEqual(store.adjustment(identity).zoom, 1.0)
        self.assertEqual(store.adjustment(identity).contrast, 1.0)
        self.assertIs(store.change_zoom(identity, preview, 1), rendered)
        self.assertEqual(calls, [(1.25, 1.0)])

    def test_zoom_steps_and_boundaries_are_enforced(self) -> None:
        calls = []
        preview = OCRCandidatePreview(
            reference="front",
            image=object(),
            adjusted_image_renderer=lambda zoom, contrast: (
                calls.append((zoom, contrast)) or object()
            ),
        )
        store = _ImageReviewAdjustmentStore()
        identity = ("coin-1", "front", "front")

        store.change_zoom(identity, preview, 100)
        self.assertEqual(store.adjustment(identity).zoom, _ZOOM_MAXIMUM)
        store.change_zoom(identity, preview, 1)
        self.assertEqual(calls[-1], (_ZOOM_MAXIMUM, 1.0))
        store.change_zoom(identity, preview, -100)
        self.assertEqual(store.adjustment(identity).zoom, _ZOOM_MINIMUM)
        with self.assertRaisesRegex(TypeError, "steps"):
            store.change_zoom(identity, preview, True)  # type: ignore[arg-type]

    def test_contrast_steps_and_boundaries_are_enforced(self) -> None:
        calls = []
        preview = OCRCandidatePreview(
            reference="front",
            image=object(),
            adjusted_image_renderer=lambda zoom, contrast: (
                calls.append((zoom, contrast)) or object()
            ),
        )
        store = _ImageReviewAdjustmentStore()
        identity = ("coin-1", "front", "front")

        store.change_contrast(identity, preview, 1)
        self.assertEqual(calls[-1], (1.0, 1.1))
        store.change_contrast(identity, preview, 100)
        self.assertEqual(
            store.adjustment(identity).contrast,
            _CONTRAST_MAXIMUM,
        )
        store.change_contrast(identity, preview, -100)
        self.assertEqual(
            store.adjustment(identity).contrast,
            _CONTRAST_MINIMUM,
        )

    def test_reset_restores_original_without_callback(self) -> None:
        original = object()
        calls = []
        preview = OCRCandidatePreview(
            reference="front",
            image=original,
            adjusted_image_renderer=lambda zoom, contrast: (
                calls.append((zoom, contrast)) or object()
            ),
        )
        store = _ImageReviewAdjustmentStore()
        identity = ("coin-1", "front", "front")
        store.change_zoom(identity, preview, 1)

        reset_image = store.reset(identity, preview)

        self.assertIs(reset_image, original)
        self.assertEqual(calls, [(1.25, 1.0)])
        self.assertEqual(store.adjustment(identity).zoom, 1.0)
        self.assertEqual(store.adjustment(identity).contrast, 1.0)

    def test_adjustment_state_is_independent_by_side_and_reference(self) -> None:
        preview = OCRCandidatePreview(
            reference="shared",
            image=object(),
            adjusted_image_renderer=lambda _zoom, _contrast: object(),
        )
        store = _ImageReviewAdjustmentStore()
        front = ("coin-1", "front", "front-a")
        reverse = ("coin-1", "reverse", "reverse-a")
        next_front = ("coin-1", "front", "front-b")

        store.change_zoom(front, preview, 1)
        store.change_contrast(reverse, preview, 1)

        self.assertEqual(store.adjustment(front).zoom, 1.25)
        self.assertEqual(store.adjustment(front).contrast, 1.0)
        self.assertEqual(store.adjustment(reverse).zoom, 1.0)
        self.assertEqual(store.adjustment(reverse).contrast, 1.1)
        self.assertEqual(store.adjustment(next_front).zoom, 1.0)

    def test_legacy_and_missing_previews_are_not_adjustable(self) -> None:
        store = _ImageReviewAdjustmentStore()
        legacy = OCRCandidatePreview(reference="legacy", image=object())
        missing = OCRCandidatePreview(
            reference="missing",
            adjusted_image_renderer=lambda _zoom, _contrast: object(),
        )

        self.assertFalse(store.is_adjustable(legacy))
        self.assertFalse(store.is_adjustable(missing))
        with self.assertRaisesRegex(ValueError, "unavailable"):
            store.change_zoom(("coin-1", "front", "legacy"), legacy, 1)

    def test_render_failure_preserves_prior_valid_state_and_image(self) -> None:
        original = object()
        valid = object()
        calls = 0

        def render(_zoom, _contrast):
            nonlocal calls
            calls += 1
            if calls == 1:
                return valid
            raise RuntimeError("decoder detail must not leak")

        preview = OCRCandidatePreview(
            reference="front",
            image=original,
            adjusted_image_renderer=render,
        )
        store = _ImageReviewAdjustmentStore()
        identity = ("coin-1", "front", "front")
        store.change_zoom(identity, preview, 1)

        with self.assertRaisesRegex(ValueError, "could not be rendered") as ctx:
            store.change_contrast(identity, preview, 1)

        self.assertNotIn("decoder", str(ctx.exception))
        self.assertEqual(store.adjustment(identity).zoom, 1.25)
        self.assertEqual(store.adjustment(identity).contrast, 1.0)
        self.assertIs(store.displayed_image(identity, preview), valid)

    def test_rendered_image_is_retained_until_reset(self) -> None:
        rendered = object()
        preview = OCRCandidatePreview(
            reference="front",
            image=object(),
            adjusted_image_renderer=lambda _zoom, _contrast: rendered,
        )
        store = _ImageReviewAdjustmentStore()
        identity = ("coin-1", "front", "front")

        store.change_zoom(identity, preview, 1)

        self.assertIs(store.displayed_image(identity, preview), rendered)
        self.assertIs(store.reset(identity, preview), preview.image)
        self.assertIs(store.displayed_image(identity, preview), preview.image)

    def test_none_render_result_preserves_default_state(self) -> None:
        original = object()
        preview = OCRCandidatePreview(
            reference="front",
            image=original,
            adjusted_image_renderer=lambda _zoom, _contrast: None,
        )
        store = _ImageReviewAdjustmentStore()
        identity = ("coin-1", "front", "front")

        with self.assertRaisesRegex(ValueError, "could not be rendered"):
            store.change_zoom(identity, preview, 1)

        self.assertEqual(store.adjustment(identity).zoom, 1.0)
        self.assertIs(store.displayed_image(identity, preview), original)

    def test_visual_adjustment_does_not_mutate_report_or_evidence(self) -> None:
        candidate = _candidate(evidence=("date glyphs",))
        report = _report(candidate)
        before = report.to_dict()
        preview = OCRCandidatePreview(
            reference="front",
            image=object(),
            crop_adjusted_image_renderer=(
                lambda _zoom, _contrast, _crop: object()
            ),
        )
        store = _ImageReviewAdjustmentStore()

        store.change_crop(
            ("coin-1", "front", "front"),
            preview,
            "left",
            1,
        )

        self.assertEqual(report.to_dict(), before)

    def test_approve_creates_existing_review_decision(self) -> None:
        controller = RecordingController()
        model = self.model(_candidate(), controller=controller)

        review = model.approve(reason="Confirmed visually.")

        self.assertIs(review.decision, OCRReviewDecision.APPROVE)
        self.assertEqual(review.reviewed_value, "1967")
        self.assertEqual(controller.review_calls, 1)
        self.assertEqual(
            model.current_candidate.human_review_state,
            "APPROVE",
        )

    def test_correct_preserves_explicit_value_without_normalization(
        self,
    ) -> None:
        model = self.model(_candidate())

        review = model.correct(
            corrected_value=" 1968 ",
            reason="Spacing retained intentionally.",
        )

        self.assertIs(review.decision, OCRReviewDecision.CORRECT)
        self.assertEqual(review.reviewed_value, " 1968 ")
        self.assertEqual(
            model.current_candidate.human_reviewed_value,
            " 1968 ",
        )

    def test_blank_correction_is_rejected_without_mutation(self) -> None:
        model = self.model(_candidate())
        approved = model.approve(reason="Initial decision.")
        before = model.reviews

        with self.assertRaisesRegex(ValueError, "must not be empty"):
            model.correct(
                corrected_value="",
                reason="Invalid correction.",
            )

        self.assertEqual(model.reviews, before)
        self.assertIs(model.current_review, approved)

    def test_reject_creates_existing_review_decision(self) -> None:
        model = self.model(_candidate())

        review = model.reject(reason="Not supported by image.")

        self.assertIs(review.decision, OCRReviewDecision.REJECT)
        self.assertIsNone(review.reviewed_value)
        self.assertEqual(
            model.current_candidate.human_review_state,
            "REJECT",
        )

    def test_defer_creates_existing_review_decision(self) -> None:
        model = self.model(_candidate())

        review = model.defer(reason="Needs another image.")

        self.assertIs(review.decision, OCRReviewDecision.DEFER)
        self.assertIsNone(review.reviewed_value)
        self.assertEqual(
            model.current_candidate.human_review_state,
            "DEFER",
        )

    def test_existing_decision_is_reflected_when_revisiting(self) -> None:
        first = _candidate(field_name="country", value="Canada")
        second = _candidate()
        model = self.model(first, second)

        model.approve(reason="Country confirmed.")
        model.next_candidate()
        model.previous_candidate()

        self.assertIsNotNone(model.current_review)
        self.assertIs(
            model.current_review.decision,
            OCRReviewDecision.APPROVE,
        )
        self.assertEqual(
            model.current_candidate.human_review_state,
            "APPROVE",
        )

    def test_invalid_reason_does_not_replace_prior_decision(self) -> None:
        model = self.model(_candidate())
        prior = model.reject(reason="Unreadable.")

        with self.assertRaisesRegex(ValueError, "reason"):
            model.approve(reason="")

        self.assertIs(model.current_review, prior)
        self.assertIs(
            model.current_review.decision,
            OCRReviewDecision.REJECT,
        )

    def test_next_and_previous_are_bounded(self) -> None:
        model = self.model(_candidate(), _candidate(source_coin_id="coin-2"))

        self.assertFalse(model.previous_candidate())
        self.assertTrue(model.next_candidate())
        self.assertFalse(model.next_candidate())
        self.assertTrue(model.previous_candidate())
        self.assertFalse(model.previous_candidate())

    def test_decisions_survive_navigation(self) -> None:
        model = self.model(
            _candidate(field_name="country", value="Canada"),
            _candidate(),
        )

        country = model.approve(reason="Country confirmed.")
        model.next_candidate()
        year = model.defer(reason="Year unclear.")
        model.previous_candidate()

        self.assertEqual(model.current_review, country)
        self.assertEqual(set(model.reviews), {country, year})

    def test_empty_report_is_safe(self) -> None:
        model = self.model()

        self.assertFalse(model.display.has_candidate)
        self.assertEqual(model.display.position_label, "No OCR candidates")
        self.assertFalse(model.next_candidate())
        self.assertFalse(model.previous_candidate())
        with self.assertRaisesRegex(ValueError, "no OCR candidate"):
            model.approve(reason="Impossible.")

    def test_input_report_is_not_mutated(self) -> None:
        report = _report(_candidate())
        before = report.to_dict()
        model = OCRCandidateReviewModel(
            report=report,
            review_controller=OCRReviewSessionController(),
            reviewer_id="reviewer-1",
        )

        model.approve(reason="Confirmed.")

        self.assertEqual(report.to_dict(), before)

    def test_grade_never_appears(self) -> None:
        model = self.model(_candidate())

        self.assertNotIn("grade", json.dumps(model.display.candidate.to_dict()))
        with self.assertRaisesRegex(ValueError, "field_name"):
            self.model(_candidate(field_name="grade", value="MS-63"))

    def test_preview_and_display_models_are_immutable(self) -> None:
        preview = OCRCandidatePreview(reference="crop-1")
        display = self.model(_candidate()).display

        with self.assertRaises(FrozenInstanceError):
            preview.reference = "other"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            display.candidate_count = 2  # type: ignore[misc]

    def test_explicit_dialog_factory_wires_model_headlessly(self) -> None:
        sentinel = object()
        captured = {}

        def construct(**kwargs):
            captured.update(kwargs)
            return sentinel

        with patch(
            "capture_import.desktop_ocr_candidate_review."
            "OCRCandidateReviewDialog",
            side_effect=construct,
        ):
            result = create_ocr_candidate_review_dialog(
                parent=object(),  # type: ignore[arg-type]
                report=_report(_candidate()),
                review_controller=OCRReviewSessionController(),
                reviewer_id="reviewer-1",
            )

        self.assertIs(result, sentinel)
        self.assertIsInstance(
            captured["model"],
            OCRCandidateReviewModel,
        )

    def test_dialog_surfaces_validation_error_without_rerender(self) -> None:
        dialog = OCRCandidateReviewDialog.__new__(
            OCRCandidateReviewDialog
        )
        errors = []
        renders = []

        class ErrorVar:
            def set(self, value):
                errors.append(value)

        dialog._error_var = ErrorVar()
        dialog._render = lambda: renders.append(True)

        dialog._run_action(
            lambda: (_ for _ in ()).throw(
                ValueError("reviewed_value must not be empty.")
            )
        )

        self.assertEqual(
            errors,
            ["reviewed_value must not be empty."],
        )
        self.assertEqual(renders, [])

    def test_architecture_and_opt_in_boundaries(self) -> None:
        module = importlib.import_module(
            "capture_import.desktop_ocr_candidate_review"
        )
        source = inspect.getsource(module)
        tree = ast.parse(source)
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
        }

        self.assertEqual(
            imported_modules,
            {
                "__future__",
                "dataclasses",
                "tkinter",
                "typing",
                "capture_import.workflow_ocr_models",
                "capture_import.workflow_ocr_review_controller",
                "capture_import.workflow_ocr_review_models",
                "capture_import.workflow_ocr_review_presenter",
                "capture_import.workflow_ocr_review_service",
            },
        )
        prohibited = (
            "pathlib",
            "persistence",
            "collection",
            "confirmed_observation",
            "legacy_ocr",
            "workflow_ocr_runtime",
        )
        self.assertFalse(
            any(
                fragment in imported
                for imported in imported_modules
                for fragment in prohibited
            )
        )
        prohibited_calls = {"open", "getenv", "putenv", "register"}
        self.assertFalse(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in prohibited_calls
                for node in ast.walk(tree)
            )
        )

        default_source = inspect.getsource(
            importlib.import_module("capture_import.ui")
        )
        composition_source = inspect.getsource(
            importlib.import_module(
                "capture_import.desktop_ocr_review_composition"
            )
        )
        self.assertNotIn(
            "desktop_ocr_candidate_review",
            default_source,
        )
        self.assertNotIn(
            "desktop_ocr_candidate_review",
            composition_source,
        )
        self.assertIn('"<Configure>"', source)
        self.assertIn("takefocus=True", source)
        for accessible_name in (
            "Zoom out",
            "Zoom in",
            "Contrast down",
            "Contrast up",
            "Reset view",
            "Crop visible area",
            "Left outward",
            "Left inward",
            "Top outward",
            "Top inward",
            "Right inward",
            "Right outward",
            "Bottom inward",
            "Bottom outward",
        ):
            self.assertIn(accessible_name, source)
        self.assertIn("state=control_state", source)
        self.assertIn("state=crop_state", source)
        self.assertIn("row=index // 3", source)
        self.assertIn("row=index // 2", source)


if __name__ == "__main__":
    unittest.main()
