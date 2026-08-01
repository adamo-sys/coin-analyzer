"""Headless integration tests for the opt-in desktop OCR review handoff."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from capture_import.desktop_ocr_candidate_review import (
    OCRCandidatePreview,
    OCRCandidateReviewModel,
    create_ocr_candidate_review_dialog,
)
from capture_import.desktop_ocr_conflict_review import (
    OCRConflictReviewModel,
    create_ocr_conflict_review_dialog,
)
from capture_import.desktop_ocr_review_composition import (
    DesktopOCRReviewComposition,
    create_desktop_ocr_review_composition,
)
from capture_import.desktop_ocr_review_handoff import (
    DesktopOCRReviewHandoff,
    create_desktop_ocr_review_handoff,
)
from capture_import.workflow_execution import ImportWorkflow, PipelineOutcome
from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
    StageArtifact,
    StageResult,
)
from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRObservation,
)
from capture_import.workflow_ocr_stage import OCRMetadataExtractionStage
from capture_import.workflow_ocr_review_models import (
    OCRReportReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_presenter import OCRFinalFieldView
from capture_import.workflow_pipeline import ProcessingPipeline
from capture_import.workflow_stages import build_image_processing_pipeline


_DEFAULT_STAGE_IDS = (
    "package-validation",
    "manifest-preparation",
    "image-normalization",
    "image-quality-scoring",
    "crop-detection",
    "obverse-reverse-pairing",
    "image-duplicate-detection",
)


class DeterministicOCRProvider:
    """External OCR substitute returning real immutable Sprint 9 DTOs."""

    provider_id = "unit-1f-provider"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, bytes]] = []

    def analyze(
        self,
        *,
        source_coin_id: str,
        image_role: str,
        artifact_key: str,
        image_bytes: bytes,
    ) -> OCRMetadataReport:
        self.calls.append(
            (
                source_coin_id,
                image_role,
                artifact_key,
                image_bytes,
            )
        )
        values = {
            "front": (
                ("country", "CAN", 93.0, ("country legend",)),
                ("denomination", "25 cents", 88.0, ("value text",)),
                ("year", "1967", 97.5, ("four-digit year",)),
            ),
            "reverse": (
                ("country", "Canada", 90.0, ("reverse legend",)),
                ("denomination", "quarter", 72.0, ("ambiguous value",)),
                ("year", "1968", 84.5, ("date glyphs",)),
            ),
        }[image_role]
        candidates = tuple(
            OCRFieldCandidate(
                source_coin_id=source_coin_id,
                image_role=image_role,
                artifact_key=artifact_key,
                provider_id=self.provider_id,
                field_name=field_name,
                raw_text=value,
                normalized_value=value,
                confidence_score=confidence,
                evidence=evidence,
            )
            for field_name, value, confidence, evidence in values
        )
        report = OCRMetadataReport(
            provider_available=True,
            observations=(
                OCRObservation(
                    source_coin_id=source_coin_id,
                    image_role=image_role,
                    artifact_key=artifact_key,
                    provider_id=self.provider_id,
                    raw_text=f"{image_role} coin text",
                    confidence_score=89.0,
                ),
            ),
            candidates=candidates,
        )
        report.validate()
        return report


class ArtifactSourceStage:
    """In-memory artifact descriptors for the real composed OCR stage."""

    stage_id = "unit-1f-artifact-source"

    def execute(self, _stage_input) -> StageResult:
        return StageResult(
            artifacts={
                "cropped-coin-1-front": StageArtifact(
                    "virtual/front.jpg",
                    "image/jpeg",
                ),
                "cropped-coin-1-reverse": StageArtifact(
                    "virtual/reverse.jpg",
                    "image/jpeg",
                ),
            },
            metadata={},
        )


def _execute_opt_in_handoff(
    *,
    composition_factory=create_desktop_ocr_review_composition,
) -> tuple[
    DeterministicOCRProvider,
    DesktopOCRReviewComposition,
    PipelineOutcome,
    DesktopOCRReviewHandoff,
]:
    provider = DeterministicOCRProvider()

    def runtime_factory(**_kwargs) -> ProcessingPipeline:
        return ProcessingPipeline(
            (
                ArtifactSourceStage(),
                OCRMetadataExtractionStage(provider=provider),
            )
        )

    composition = composition_factory(
        raw_text_resolver=lambda *_args: "not used by fake runtime",
        runtime_factory=runtime_factory,
    )
    workflow = ImportWorkflow(composition.pipeline)
    fixture_root = Path.cwd() / "unit-1f"
    request = ImportRequest(
        source=fixture_root / "source.ca-package",
        collection_id="collection-not-used",
        configuration=ImportConfiguration(),
    )
    with patch(
        "capture_import.workflow_ocr_stage._read_bounded_artifact",
        return_value=b"in-memory-jpeg",
    ) as reader:
        outcome = workflow.execute(
            request,
            fixture_root / "workspace",
        )
    if reader.call_count != 2:
        raise AssertionError("Expected one injected read per image role.")

    handoff = create_desktop_ocr_review_handoff(
        composition=composition,
        outcome=outcome,
    )
    return provider, composition, outcome, handoff


def _complete_candidate_review(
    handoff: DesktopOCRReviewHandoff,
    *,
    preview_resolver=None,
) -> tuple[OCRCandidateReviewModel, OCRReportReview]:
    model = OCRCandidateReviewModel(
        report=handoff.report,
        review_controller=handoff.review_controller,
        reviewer_id="collector-1",
        preview_resolver=preview_resolver,
    )
    while True:
        candidate = model.current_candidate
        if candidate is None:
            break
        model.display
        identity = (candidate.field_name, candidate.image_role)
        if identity == ("country", "front"):
            model.correct(
                corrected_value="Canada",
                reason="Expanded country name.",
            )
        elif identity == ("denomination", "reverse"):
            model.reject(reason="Ambiguous denomination wording.")
        else:
            model.approve(reason="Accepted integration value.")
        if not model.next_candidate():
            break
    return model, OCRReportReview(
        reviewer_id="collector-1",
        field_reviews=model.reviews,
    )


class DesktopOCRReviewIntegrationTests(unittest.TestCase):
    def test_real_opt_in_composition_reaches_review_handoff(self) -> None:
        provider, composition, outcome, handoff = (
            _execute_opt_in_handoff()
        )

        self.assertIn(
            "ocr-metadata-extraction",
            composition.pipeline.stage_ids,
        )
        self.assertIsInstance(outcome, PipelineOutcome)
        self.assertIsInstance(handoff, DesktopOCRReviewHandoff)
        self.assertIs(
            handoff.review_controller,
            composition.review_controller,
        )
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(
            [(call[0], call[1], call[2]) for call in provider.calls],
            [
                ("coin-1", "front", "cropped-coin-1-front"),
                ("coin-1", "reverse", "cropped-coin-1-reverse"),
            ],
        )

    def test_workflow_reports_merge_into_one_real_immutable_report(
        self,
    ) -> None:
        _provider, _composition, _outcome, handoff = (
            _execute_opt_in_handoff()
        )

        self.assertIsInstance(handoff.report, OCRMetadataReport)
        self.assertEqual(len(handoff.report.observations), 2)
        self.assertEqual(len(handoff.report.candidates), 6)
        self.assertNotIn(
            "grade",
            {candidate.field_name for candidate in handoff.report.candidates},
        )
        year = next(
            candidate
            for candidate in handoff.report.candidates
            if (
                candidate.field_name == "year"
                and candidate.image_role == "front"
            )
        )
        self.assertEqual(year.source_coin_id, "coin-1")
        self.assertEqual(year.artifact_key, "cropped-coin-1-front")
        self.assertEqual(year.provider_id, "unit-1f-provider")
        self.assertEqual(year.confidence_score, 97.5)
        self.assertEqual(year.evidence, ("four-digit year",))

    def test_candidate_review_uses_real_controller_and_survives_navigation(
        self,
    ) -> None:
        _provider, _composition, _outcome, handoff = (
            _execute_opt_in_handoff()
        )
        model = OCRCandidateReviewModel(
            report=handoff.report,
            review_controller=handoff.review_controller,
            reviewer_id="collector-1",
        )

        first = model.correct(
            corrected_value="Canada",
            reason="Expanded country name.",
        )
        self.assertTrue(model.next_candidate())
        self.assertTrue(model.previous_candidate())

        self.assertEqual(model.current_review, first)
        self.assertEqual(
            model.current_candidate.human_review_state,
            OCRReviewDecision.CORRECT.value,
        )

    def test_complete_candidate_handoff_covers_all_human_decisions(
        self,
    ) -> None:
        _provider, _composition, _outcome, handoff = (
            _execute_opt_in_handoff()
        )

        model, review = _complete_candidate_review(handoff)

        self.assertEqual(model.candidate_count, 6)
        self.assertEqual(len(review.field_reviews), 6)
        decisions = {item.decision for item in review.field_reviews}
        self.assertIn(OCRReviewDecision.APPROVE, decisions)
        self.assertIn(OCRReviewDecision.CORRECT, decisions)
        self.assertIn(OCRReviewDecision.REJECT, decisions)

    def test_preview_resolver_receives_presented_candidates(self) -> None:
        _provider, _composition, _outcome, handoff = (
            _execute_opt_in_handoff()
        )
        seen = []

        def preview_resolver(candidate):
            seen.append(candidate)
            return OCRCandidatePreview(
                reference=candidate.artifact_key,
                unavailable_reason="Headless integration preview.",
            )

        model, _review = _complete_candidate_review(
            handoff,
            preview_resolver=preview_resolver,
        )

        self.assertEqual(len(seen), model.candidate_count)
        self.assertEqual(
            [item.artifact_key for item in seen],
            [
                item.artifact_key
                for item in handoff.review_controller.present_initial(
                    report=handoff.report
                ).candidates
            ],
        )

    def test_missing_preview_fails_safely_without_image_loading(self) -> None:
        _provider, _composition, _outcome, handoff = (
            _execute_opt_in_handoff()
        )
        model = OCRCandidateReviewModel(
            report=handoff.report,
            review_controller=handoff.review_controller,
            reviewer_id="collector-1",
            preview_resolver=lambda _candidate: None,
        )

        preview = model.display.preview

        self.assertIsNone(preview.image)
        self.assertEqual(
            preview.unavailable_reason,
            "Preview unavailable",
        )

    def test_reviewed_candidates_create_real_unresolved_conflict(self) -> None:
        _provider, _composition, _outcome, handoff = (
            _execute_opt_in_handoff()
        )
        _candidate_model, review = _complete_candidate_review(handoff)

        model = OCRConflictReviewModel(
            report=handoff.report,
            review=review,
            review_controller=handoff.review_controller,
        )
        display = model.display

        self.assertEqual(model.conflict_count, 1)
        self.assertEqual(display.conflict.field_name, "year")
        self.assertEqual(
            display.conflict.available_existing_values,
            ("1967", "1968"),
        )
        self.assertEqual(len(display.provenance), 2)
        self.assertEqual(
            [item.image_role for item in display.provenance],
            ["front", "reverse"],
        )
        self.assertEqual(display.unresolved_field_count, 1)
        unresolved = next(
            item
            for item in display.unresolved_fields
            if item.field_name == "year"
        )
        self.assertIsNone(unresolved.final_value)

    def test_select_existing_reaches_complete_final_projection(self) -> None:
        _provider, _composition, _outcome, handoff = (
            _execute_opt_in_handoff()
        )
        _candidate_model, review = _complete_candidate_review(handoff)
        model = OCRConflictReviewModel(
            report=handoff.report,
            review=review,
            review_controller=handoff.review_controller,
        )

        resolution = model.select_existing(value="1968")

        self.assertEqual(
            resolution.request.decision,
            OCRConflictResolutionDecision.SELECT_EXISTING_VALUE,
        )
        year = next(
            item
            for item in model.display.final_fields
            if item.field_name == "year"
        )
        self.assertEqual(year.final_value, "1968")
        self.assertTrue(model.display.is_complete)
        self.assertEqual(model.display.unresolved_field_count, 0)

    def test_corrected_value_reaches_projection_exactly_as_entered(
        self,
    ) -> None:
        _provider, _composition, _outcome, handoff = (
            _execute_opt_in_handoff()
        )
        _candidate_model, review = _complete_candidate_review(handoff)
        model = OCRConflictReviewModel(
            report=handoff.report,
            review=review,
            review_controller=handoff.review_controller,
        )

        model.enter_corrected(value=" 1969 ")

        year = next(
            item
            for item in model.display.final_fields
            if item.field_name == "year"
        )
        self.assertEqual(year.final_value, " 1969 ")

    def test_deferred_conflict_remains_unresolved_without_final_value(
        self,
    ) -> None:
        _provider, _composition, _outcome, handoff = (
            _execute_opt_in_handoff()
        )
        _candidate_model, review = _complete_candidate_review(handoff)
        model = OCRConflictReviewModel(
            report=handoff.report,
            review=review,
            review_controller=handoff.review_controller,
        )

        model.defer()

        self.assertFalse(model.display.is_complete)
        self.assertEqual(model.display.unresolved_field_count, 1)
        year = next(
            item
            for item in model.display.unresolved_fields
            if item.field_name == "year"
        )
        self.assertIsNone(year.final_value)

    def test_invalid_resolution_preserves_prior_controller_state(
        self,
    ) -> None:
        _provider, _composition, _outcome, handoff = (
            _execute_opt_in_handoff()
        )
        _candidate_model, review = _complete_candidate_review(handoff)
        model = OCRConflictReviewModel(
            report=handoff.report,
            review=review,
            review_controller=handoff.review_controller,
        )
        prior = model.select_existing(value="1967")

        with self.assertRaisesRegex(ValueError, "existing distinct value"):
            model.select_existing(value="not-available")

        self.assertIs(model.current_resolution, prior)
        self.assertEqual(
            model.display.conflict.selected_or_corrected_value,
            "1967",
        )

    def test_final_projection_does_not_create_collection_ready_object(
        self,
    ) -> None:
        _provider, _composition, _outcome, handoff = (
            _execute_opt_in_handoff()
        )
        _candidate_model, review = _complete_candidate_review(handoff)
        model = OCRConflictReviewModel(
            report=handoff.report,
            review=review,
            review_controller=handoff.review_controller,
        )
        model.select_existing(value="1967")

        self.assertTrue(
            all(
                isinstance(item, OCRFinalFieldView)
                for item in model.display.final_fields
            )
        )
        self.assertFalse(
            any(
                "collection" in type(item).__module__.lower()
                or "confirmed" in type(item).__module__.lower()
                for item in model.display.final_fields
            )
        )

    def test_handoff_rejects_inconsistent_workflow_metadata(self) -> None:
        _provider, composition, outcome, _handoff = (
            _execute_opt_in_handoff()
        )
        malformed = PipelineOutcome(
            artifacts=outcome.artifacts,
            metadata={
                **outcome.metadata,
                "ocr_processed_image_count": 3,
            },
        )

        with self.assertRaisesRegex(ValueError, "does not match"):
            create_desktop_ocr_review_handoff(
                composition=composition,
                outcome=malformed,
            )

    def test_handoff_accepts_composition_created_after_reload(self) -> None:
        handoff_module = importlib.import_module(
            "capture_import.desktop_ocr_review_handoff"
        )
        composition_module = importlib.import_module(
            "capture_import.desktop_ocr_review_composition"
        )
        original_composition_type = (
            composition_module.DesktopOCRReviewComposition
        )
        original_factory = (
            composition_module.create_desktop_ocr_review_composition
        )
        try:
            reloaded_module = importlib.reload(composition_module)
            reloaded_factory = (
                reloaded_module.create_desktop_ocr_review_composition
            )
            _provider, composition, outcome, handoff = (
                _execute_opt_in_handoff(
                    composition_factory=reloaded_factory
                )
            )
            self.assertIsInstance(
                handoff,
                handoff_module.DesktopOCRReviewHandoff,
            )
            self.assertIs(
                handoff.review_controller,
                composition.review_controller,
            )
            self.assertEqual(len(outcome.metadata["ocr_reports"]), 2)
        finally:
            composition_module.DesktopOCRReviewComposition = (
                original_composition_type
            )
            composition_module.create_desktop_ocr_review_composition = (
                original_factory
            )

    def test_missing_composition_attributes_are_rejected(self) -> None:
        composition = create_desktop_ocr_review_composition(
            provider=DeterministicOCRProvider()
        )
        outcome = PipelineOutcome(artifacts={}, metadata={})

        with self.assertRaisesRegex(TypeError, "public pipeline"):
            create_desktop_ocr_review_handoff(
                composition=SimpleNamespace(
                    review_controller=composition.review_controller
                ),
                outcome=outcome,
            )
        with self.assertRaisesRegex(
            TypeError,
            "public review_controller",
        ):
            create_desktop_ocr_review_handoff(
                composition=SimpleNamespace(
                    pipeline=composition.pipeline
                ),
                outcome=outcome,
            )
        with self.assertRaisesRegex(TypeError, "public pipeline"):
            create_desktop_ocr_review_handoff(
                composition=object(),
                outcome=outcome,
            )

    def test_invalid_composition_attribute_values_are_rejected(
        self,
    ) -> None:
        composition = create_desktop_ocr_review_composition(
            provider=DeterministicOCRProvider()
        )
        outcome = PipelineOutcome(artifacts={}, metadata={})

        with self.assertRaisesRegex(
            TypeError,
            "pipeline must be a ProcessingPipeline",
        ):
            create_desktop_ocr_review_handoff(
                composition=SimpleNamespace(
                    pipeline=object(),
                    review_controller=composition.review_controller,
                ),
                outcome=outcome,
            )
        with self.assertRaisesRegex(
            TypeError,
            "review_controller must be an OCRReviewSessionController",
        ):
            create_desktop_ocr_review_handoff(
                composition=SimpleNamespace(
                    pipeline=composition.pipeline,
                    review_controller=object(),
                ),
                outcome=outcome,
            )

    def test_dialog_factories_construct_real_models_from_handoff(
        self,
    ) -> None:
        _provider, _composition, _outcome, handoff = (
            _execute_opt_in_handoff()
        )
        with patch(
            "capture_import.desktop_ocr_candidate_review."
            "OCRCandidateReviewDialog",
            side_effect=lambda **kwargs: kwargs["model"],
        ):
            candidate_model = create_ocr_candidate_review_dialog(
                parent=object(),
                report=handoff.report,
                review_controller=handoff.review_controller,
                reviewer_id="collector-1",
            )
        _completed_model, review = _complete_candidate_review(handoff)
        with patch(
            "capture_import.desktop_ocr_conflict_review."
            "OCRConflictReviewDialog",
            side_effect=lambda **kwargs: kwargs["model"],
        ):
            conflict_model = create_ocr_conflict_review_dialog(
                parent=object(),
                report=handoff.report,
                review=review,
                review_controller=handoff.review_controller,
            )

        self.assertIsInstance(candidate_model, OCRCandidateReviewModel)
        self.assertIsInstance(conflict_model, OCRConflictReviewModel)
        self.assertEqual(conflict_model.conflict_count, 1)


class DesktopOCRReviewIntegrationArchitectureTests(unittest.TestCase):
    def test_default_desktop_path_remains_ocr_free_and_inert(self) -> None:
        with patch(
            "tkinter.Toplevel",
            side_effect=AssertionError("review dialog opened"),
        ):
            default_pipeline = build_image_processing_pipeline()
            desktop = importlib.import_module("capture_import.ui")

        self.assertEqual(default_pipeline.stage_ids, _DEFAULT_STAGE_IDS)
        desktop_source = inspect.getsource(desktop)
        self.assertNotIn("desktop_ocr_review_handoff", desktop_source)
        self.assertNotIn("desktop_ocr_candidate_review", desktop_source)
        self.assertNotIn("desktop_ocr_conflict_review", desktop_source)

    def test_unit_1c_remains_the_explicit_opt_in_boundary(self) -> None:
        composition_module = importlib.import_module(
            "capture_import.desktop_ocr_review_composition"
        )
        source = inspect.getsource(composition_module)

        self.assertNotIn("desktop_ocr_review_handoff", source)
        self.assertNotIn("desktop_ocr_candidate_review", source)
        self.assertNotIn("desktop_ocr_conflict_review", source)
        self.assertIn("create_desktop_ocr_review_composition", source)

    def test_handoff_has_no_forbidden_integration_imports_or_state(
        self,
    ) -> None:
        module = importlib.import_module(
            "capture_import.desktop_ocr_review_handoff"
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
                "collections.abc",
                "dataclasses",
                "typing",
                "capture_import.workflow_execution",
                "capture_import.workflow_ocr_models",
                "capture_import.workflow_ocr_review_controller",
                "capture_import.workflow_pipeline",
            },
        )
        self.assertNotIn("getenv", source)
        self.assertNotIn("environ", source)
        self.assertNotIn("global ", source)
        self.assertNotIn("grade", source.lower())

    def test_handoff_uses_existing_models_and_controller_only(self) -> None:
        source = inspect.getsource(
            importlib.import_module(
                "capture_import.desktop_ocr_review_handoff"
            )
        )

        self.assertIn("OCRMetadataReport", source)
        self.assertIn("OCRReviewSessionController", source)
        self.assertNotIn("OCRConflictResolutionDecision", source)
        self.assertNotIn("OCRFinalMetadataProjection", source)
        self.assertNotIn("OCRReviewDecision", source)


if __name__ == "__main__":
    unittest.main()
