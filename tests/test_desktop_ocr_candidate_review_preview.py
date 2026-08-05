"""Preview, crop, and image-adjustment tests for desktop OCR candidate review."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from capture_import.desktop_ocr_candidate_review import (
    AdjustedPreviewRenderer,
    CropAdjustedPreviewRenderer,
    NormalizedCrop,
    OCRCandidatePreview,
    OCRCandidateReviewModel,
    _CONTRAST_MAXIMUM,
    _CONTRAST_MINIMUM,
    _CROP_MINIMUM_SIZE,
    _CROP_STEP,
    _ImageReviewAdjustmentStore,
    _ZOOM_MAXIMUM,
    _ZOOM_MINIMUM,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRReviewStatus,
)
from capture_import.workflow_ocr_review_controller import (
    OCRReviewSessionController,
)


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
        # Frozen, slotted dataclasses raise either exception across supported
        # Python runtimes; the invariant is that no new attribute is created.
        with self.assertRaises((AttributeError, TypeError)):
            crop.extra = True  # type: ignore[attr-defined]
        self.assertFalse(hasattr(crop, "extra"))

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
