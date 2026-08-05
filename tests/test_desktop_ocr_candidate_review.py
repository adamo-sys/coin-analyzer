"""Headless tests for the first desktop OCR candidate-review UI slice."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import importlib
import inspect
import json
from types import SimpleNamespace
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
    _FOCUS_APPROVE,
    _FOCUS_CLOSE,
    _FOCUS_CORRECT,
    _FOCUS_CORRECTION,
    _FOCUS_DEFER,
    _FOCUS_REASON,
    _FOCUS_REJECT,
    _ImageReviewAdjustmentStore,
    _SHORTCUT_BINDINGS,
    _SHORTCUT_HELP_TEXT,
    _ZOOM_MAXIMUM,
    _ZOOM_MINIMUM,
    _adjustment_capability_label,
    _initial_focus_role,
    _preview_column_count,
    _preview_wrap_width,
    _responsive_wrap_width,
    _scroll_fraction_for_visibility,
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
        selected = tuple(side for side in sides if side.is_selected)
        self.assertEqual(len(selected), 1)
        self.assertEqual(
            selected[0].preview.reference,
            model.current_candidate.artifact_key,
        )
        related = tuple(side for side in sides if not side.is_selected)
        self.assertEqual(len(related), 1)
        self.assertEqual(
            related[0].selection_label,
            "Related image evidence (not selected)",
        )
        self.assertIn("related image evidence", related[0].alt_text)

    def test_initial_candidate_reference_is_explicitly_selected(self) -> None:
        model = self.model(
            _candidate(image_role="front", artifact_key="front-reference")
        )

        side = model._side_previews(model.display)[0]

        self.assertTrue(side.is_selected)
        self.assertEqual(side.selection_label, "Selected candidate reference")
        self.assertEqual(side.panel_title, "Obverse image - Selected")
        self.assertIn("selected candidate reference", side.alt_text)

    def test_highlighting_does_not_mutate_report_ranking_or_evidence(self) -> None:
        candidates = (
            _candidate(
                field_name="country",
                value="Canada",
                evidence=("country glyphs",),
            ),
            _candidate(evidence=("date glyphs",)),
        )
        report = _report(*candidates)
        before = report.to_dict()
        model = OCRCandidateReviewModel(
            report=report,
            review_controller=OCRReviewSessionController(),
            reviewer_id="reviewer-1",
        )

        model._side_previews(model.display)
        model.next_candidate()
        model._side_previews(model.display)

        self.assertEqual(report.to_dict(), before)

    def test_one_sided_review_has_clear_obverse_state(self) -> None:
        model = self.model(_candidate(image_role="front"))

        sides = model._side_previews(model.display)

        self.assertEqual(len(sides), 1)
        self.assertEqual(sides[0].label, "Obverse image")
        self.assertEqual(
            sides[0].alt_text,
            "Obverse image for coin coin-1; selected candidate reference",
        )
        self.assertTrue(sides[0].is_selected)
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
            "Reverse image for coin coin-1; selected candidate reference",
        )
        self.assertEqual(side.selection_label, "Selected candidate reference")

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

    def test_next_and_previous_are_bounded(self) -> None:
        model = self.model(_candidate(), _candidate(source_coin_id="coin-2"))

        self.assertFalse(model.previous_candidate())
        self.assertTrue(model.next_candidate())
        self.assertFalse(model.next_candidate())
        self.assertTrue(model.previous_candidate())
        self.assertFalse(model.previous_candidate())

    def test_batch_progress_counts_deterministic_full_report_queue(self) -> None:
        model = self.model(
            _candidate(source_coin_id="coin-2"),
            _candidate(source_coin_id="coin-1"),
            _candidate(
                source_coin_id="coin-1",
                field_name="country",
                value="Canada",
                artifact_key="country",
            ),
        )

        progress = model._batch_progress()

        self.assertEqual((progress.total, progress.reviewed, progress.remaining), (3, 0, 3))
        self.assertEqual(progress.current_coin_id, "coin-1")
        self.assertEqual(
            (progress.overall_position, progress.coin_position, progress.coin_total),
            (1, 1, 2),
        )

    def test_batch_progress_counts_each_review_decision(self) -> None:
        model = self.model(
            _candidate(field_name="country", value="Canada", artifact_key="country"),
            _candidate(field_name="denomination", value="1 cent", artifact_key="denomination"),
            _candidate(field_name="mintmark", value="P", artifact_key="mintmark"),
            _candidate(),
        )

        model.approve(reason="Approved.")
        model.next_candidate()
        model.correct(corrected_value="One cent", reason="Corrected.")
        model.next_candidate()
        model.reject(reason="Rejected.")
        model.next_candidate()
        model.defer(reason="Deferred.")
        progress = model._batch_progress()

        self.assertEqual((progress.reviewed, progress.remaining), (4, 0))
        self.assertEqual(
            (progress.approved, progress.corrected, progress.rejected, progress.deferred),
            (1, 1, 1, 1),
        )
        self.assertTrue(progress.queue_reviewed)
        self.assertFalse(progress.domain_complete)

    def test_replacing_decision_updates_category_not_reviewed_count(self) -> None:
        model = self.model(_candidate())
        model.approve(reason="Initially approved.")
        before = model._batch_progress()

        model.reject(reason="Reconsidered.")
        after = model._batch_progress()

        self.assertEqual((before.reviewed, after.reviewed), (1, 1))
        self.assertEqual((before.approved, before.rejected), (1, 0))
        self.assertEqual((after.approved, after.rejected), (0, 1))

    def test_equal_approvals_are_agreed_without_conflict(self) -> None:
        model = self.model(
            _candidate(artifact_key="front-year"),
            _candidate(image_role="reverse", artifact_key="reverse-year"),
        )

        model.approve(reason="Front agrees.")
        model.next_candidate()
        model.approve(reason="Reverse agrees.")
        progress = model._batch_progress()

        self.assertEqual(progress.unresolved_conflicts, 0)
        self.assertTrue(progress.queue_reviewed)
        self.assertTrue(progress.domain_complete)

    def test_different_approvals_expose_unresolved_conflict(self) -> None:
        model = self.model(
            _candidate(artifact_key="front-year"),
            _candidate(
                image_role="reverse",
                artifact_key="reverse-year",
                value="1968",
            ),
        )

        model.approve(reason="Front reading.")
        model.next_candidate()
        model.approve(reason="Reverse reading.")
        progress = model._batch_progress()

        self.assertEqual(progress.unresolved_conflicts, 1)
        self.assertTrue(progress.queue_reviewed)
        self.assertFalse(progress.domain_complete)
        self.assertIn("unresolved conflicts", progress.state_label)

    def test_coin_progress_changes_at_existing_queue_boundary(self) -> None:
        model = self.model(
            _candidate(source_coin_id="coin-1", field_name="country", value="Canada"),
            _candidate(source_coin_id="coin-1"),
            _candidate(source_coin_id="coin-2"),
        )
        model.next_candidate()
        model.next_candidate()

        progress = model._batch_progress()

        self.assertEqual(progress.current_coin_id, "coin-2")
        self.assertEqual(
            (progress.overall_position, progress.coin_position, progress.coin_total),
            (3, 1, 1),
        )

    def test_empty_batch_progress_is_explicit_and_safe(self) -> None:
        progress = self.model()._batch_progress()

        self.assertEqual((progress.total, progress.reviewed, progress.remaining), (0, 0, 0))
        self.assertIsNone(progress.current_coin_id)
        self.assertIsNone(progress.overall_position)
        self.assertFalse(progress.queue_reviewed)
        self.assertFalse(progress.domain_complete)
        self.assertEqual(progress.position_label, "No current candidate or coin.")
        self.assertIn("Batch queue is empty", progress.state_label)

    def test_fully_reviewed_rejected_queue_is_domain_complete(self) -> None:
        model = self.model(_candidate(), _candidate(field_name="country", value="Canada"))
        model.reject(reason="Rejected year.")
        model.next_candidate()
        model.reject(reason="Rejected country.")

        progress = model._batch_progress()

        self.assertTrue(progress.queue_reviewed)
        self.assertTrue(progress.domain_complete)
        self.assertEqual(progress.remaining, 0)
        self.assertEqual(progress.state_label, "Queue reviewed. Domain session complete.")

    def test_fully_reviewed_deferred_queue_is_not_domain_complete(self) -> None:
        model = self.model(_candidate())
        model.defer(reason="Needs more evidence.")

        progress = model._batch_progress()

        self.assertTrue(progress.queue_reviewed)
        self.assertFalse(progress.domain_complete)
        self.assertEqual(progress.deferred, 1)

    def test_partial_queue_wording_distinguishes_domain_completion(self) -> None:
        model = self.model(_candidate(), _candidate(field_name="country", value="Canada"))
        model.approve(reason="Year confirmed.")

        progress = model._batch_progress()

        self.assertFalse(progress.queue_reviewed)
        self.assertFalse(progress.domain_complete)
        self.assertIn("not fully reviewed", progress.state_label)
        self.assertIn("Domain session is not complete", progress.state_label)

    def test_batch_summary_is_readable_non_color_text(self) -> None:
        progress = self.model(_candidate())._batch_progress()

        for text in (
            "1 total",
            "0 reviewed",
            "1 remaining",
            "0 approved",
            "0 corrected",
            "0 rejected",
            "0 deferred",
            "0 unresolved conflicts",
        ):
            self.assertIn(text, progress.counts_label)
        self.assertIn("coin coin-1", progress.position_label)

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

    def test_adjustment_capability_text_is_explicit(self) -> None:
        legacy = OCRCandidatePreview(reference="legacy", image=object())
        zoom_only = OCRCandidatePreview(
            reference="zoom-only",
            image=object(),
            adjusted_image_renderer=lambda _zoom, _contrast: object(),
        )
        crop = OCRCandidatePreview(
            reference="crop",
            image=object(),
            crop_adjusted_image_renderer=(
                lambda _zoom, _contrast, _crop: object()
            ),
        )
        missing = OCRCandidatePreview(reference="missing")

        self.assertIn("legacy or unsupported", _adjustment_capability_label(legacy))
        self.assertIn("crop adjustment is unavailable", _adjustment_capability_label(zoom_only))
        self.assertIn("crop adjustments are available", _adjustment_capability_label(crop))
        self.assertIn("no preview image", _adjustment_capability_label(missing))

    def test_responsive_wrap_widths_are_bounded_and_deterministic(self) -> None:
        self.assertEqual(
            _responsive_wrap_width(760, inset=40, maximum=680),
            680,
        )
        self.assertEqual(
            _responsive_wrap_width(200, inset=80, maximum=680),
            160,
        )
        self.assertEqual(_preview_wrap_width(619), 320)
        self.assertEqual(_preview_wrap_width(620), 262)
        for invalid in (-1, True, 1.5):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    _responsive_wrap_width(  # type: ignore[arg-type]
                        invalid,
                        inset=40,
                        maximum=680,
                    )

    def test_scroll_fraction_exposes_above_and_below_focus(self) -> None:
        self.assertEqual(
            _scroll_fraction_for_visibility(
                focus_top=50,
                focus_bottom=70,
                viewport_top=100,
                viewport_height=200,
                content_height=1000,
            ),
            0.05,
        )
        self.assertEqual(
            _scroll_fraction_for_visibility(
                focus_top=350,
                focus_bottom=400,
                viewport_top=100,
                viewport_height=200,
                content_height=1000,
            ),
            0.2,
        )
        self.assertIsNone(
            _scroll_fraction_for_visibility(
                focus_top=150,
                focus_bottom=200,
                viewport_top=100,
                viewport_height=200,
                content_height=1000,
            )
        )

    def test_focus_visibility_scrolls_only_content_descendants(self) -> None:
        class Widget:
            def __init__(self, master=None, top=0, height=20, requested=1000):
                self.master = master
                self.top = top
                self.height = height
                self.requested = requested

            def winfo_rooty(self):
                return self.top

            def winfo_height(self):
                return self.height

            def winfo_reqheight(self):
                return self.requested

        class Canvas:
            def __init__(self):
                self.moves = []

            def canvasy(self, _value):
                return 100

            def winfo_height(self):
                return 200

            def yview_moveto(self, fraction):
                self.moves.append(fraction)

        dialog = OCRCandidateReviewDialog.__new__(OCRCandidateReviewDialog)
        dialog._content = Widget(top=0)
        dialog._scroll_canvas = Canvas()
        descendant = Widget(master=dialog._content, top=350, height=50)

        dialog._ensure_focused_widget_visible(
            SimpleNamespace(widget=descendant)
        )
        dialog._ensure_focused_widget_visible(
            SimpleNamespace(widget=Widget(top=500))
        )

        self.assertEqual(dialog._scroll_canvas.moves, [0.2])

    def test_accessibility_widget_contract_is_dialog_local_and_passive(
        self,
    ) -> None:
        build_source = inspect.getsource(OCRCandidateReviewDialog._build_widgets)
        render_source = inspect.getsource(OCRCandidateReviewDialog._render)
        preview_source = inspect.getsource(
            OCRCandidateReviewDialog._render_side_previews
        )
        full_source = inspect.getsource(OCRCandidateReviewDialog)

        self.assertIn("tk.Canvas", build_source)
        self.assertIn("ttk.Scrollbar", build_source)
        self.assertIn("takefocus=True", build_source)
        self.assertGreaterEqual(full_source.count("takefocus=False"), 8)
        self.assertIn(
            "self._correction_entry.config(state=tk.DISABLED, takefocus=False)",
            render_source,
        )
        self.assertIn(
            "self._reason_entry.config(state=tk.DISABLED, takefocus=False)",
            render_source,
        )
        self.assertIn("takefocus=(control_state == tk.NORMAL)", preview_source)
        self.assertIn("takefocus=(crop_state == tk.NORMAL)", preview_source)
        self.assertIn(
            '"Reset crop, zoom, and contrast"',
            preview_source,
        )
        self.assertNotIn("bind_all", full_source)
        self.assertNotIn("focus_force", full_source)

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
            "Selected candidate reference",
            "Related image evidence (not selected)",
            "Zoom out",
            "Zoom in",
            "Contrast down",
            "Contrast up",
            "Reset crop, zoom, and contrast",
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
        self.assertIn('"SelectedCandidate.TLabelframe"', source)
        self.assertIn('"RelatedCandidate.TLabelframe"', source)
        self.assertIn("borderwidth=3", source)
        self.assertIn('font=("TkDefaultFont", 10, "bold")', source)


if __name__ == "__main__":
    unittest.main()
