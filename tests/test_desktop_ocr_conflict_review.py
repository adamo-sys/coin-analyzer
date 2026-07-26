"""Headless tests for the desktop OCR conflict-resolution UI slice."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import importlib
import inspect
import unittest

from capture_import.desktop_ocr_conflict_review import (
    OCRConflictProvenanceDisplay,
    OCRConflictReviewDialog,
    OCRConflictReviewDisplay,
    OCRConflictReviewModel,
    create_ocr_conflict_review_dialog,
)
from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRReviewStatus,
)
from capture_import.workflow_ocr_review_controller import (
    OCRReviewSessionController,
)
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_service import OCRReviewMode
from capture_import.workflow_ocr_review_session import (
    OCRReviewSessionConflictResolutionRequest,
    OCRReviewSessionService,
)
from capture_import.workflow_stages import build_image_processing_pipeline


def _candidate(
    *,
    source_coin_id: str = "coin-1",
    field_name: str = "year",
    value: str = "1967",
    image_role: str = "front",
    artifact_key: str = "crop-front",
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


def _review(
    *candidates: OCRFieldCandidate,
    decisions: dict[str, tuple[OCRReviewDecision, str | None]] | None = None,
) -> OCRReportReview:
    decisions = {} if decisions is None else decisions
    field_reviews = []
    for candidate in candidates:
        decision, reviewed_value = decisions.get(
            candidate.artifact_key,
            (OCRReviewDecision.APPROVE, candidate.normalized_value),
        )
        field_reviews.append(
            OCRFieldReview(
                source_coin_id=candidate.source_coin_id,
                image_role=candidate.image_role,
                artifact_key=candidate.artifact_key,
                provider_id=candidate.provider_id,
                field_name=candidate.field_name,
                original_value=candidate.normalized_value,
                decision=decision,
                reviewed_value=reviewed_value,
                reason=f"Reviewed {candidate.artifact_key}.",
            )
        )
    return OCRReportReview(
        reviewer_id="reviewer-1",
        field_reviews=tuple(field_reviews),
    )


def _conflict_pair(
    *,
    source_coin_id: str = "coin-1",
    field_name: str = "year",
    first_value: str = "1967",
    second_value: str = "1968",
) -> tuple[OCRFieldCandidate, OCRFieldCandidate]:
    return (
        _candidate(
            source_coin_id=source_coin_id,
            field_name=field_name,
            value=first_value,
            image_role="front",
            artifact_key=f"{field_name}-front",
            provider_id="provider-front",
            confidence_score=91.25,
            evidence=("front evidence",),
        ),
        _candidate(
            source_coin_id=source_coin_id,
            field_name=field_name,
            value=second_value,
            image_role="reverse",
            artifact_key=f"{field_name}-reverse",
            provider_id="provider-reverse",
            confidence_score=82.5,
            evidence=("reverse evidence",),
        ),
    )


class RecordingController(OCRReviewSessionController):
    def __init__(self) -> None:
        super().__init__()
        self.present_calls = 0
        self.resolution_calls: list[
            tuple[OCRReviewSessionConflictResolutionRequest, ...]
        ] = []

    def present_session(self, **kwargs):
        self.present_calls += 1
        return super().present_session(**kwargs)

    def apply_conflict_resolutions(
        self,
        *,
        report,
        review,
        resolutions,
        mode,
    ):
        self.resolution_calls.append(resolutions)
        return super().apply_conflict_resolutions(
            report=report,
            review=review,
            resolutions=resolutions,
            mode=mode,
        )


class RecordingSessionService(OCRReviewSessionService):
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, request):
        self.calls += 1
        return super().run(request=request)


class OCRConflictReviewModelTests(unittest.TestCase):
    def model(
        self,
        *candidates: OCRFieldCandidate,
        controller: OCRReviewSessionController | None = None,
        resolutions: tuple[
            OCRReviewSessionConflictResolutionRequest,
            ...,
        ] = (),
        session_service: OCRReviewSessionService | None = None,
    ) -> OCRConflictReviewModel:
        report = _report(*candidates)
        return OCRConflictReviewModel(
            report=report,
            review=_review(*candidates),
            review_controller=(
                OCRReviewSessionController()
                if controller is None
                else controller
            ),
            resolutions=resolutions,
            session_service=session_service,
        )

    def test_explicit_construction_uses_injected_controller_without_ocr(
        self,
    ) -> None:
        controller = RecordingController()

        model = self.model(*_conflict_pair(), controller=controller)

        self.assertIsInstance(model, OCRConflictReviewModel)
        self.assertEqual(controller.present_calls, 1)
        self.assertEqual(controller.resolution_calls, [])
        self.assertNotIn(
            "ocr-metadata-extraction",
            build_image_processing_pipeline().stage_ids,
        )

    def test_exact_targets_come_from_injected_sprint_10_service(self) -> None:
        service = RecordingSessionService()

        self.model(*_conflict_pair(), session_service=service)

        self.assertEqual(service.calls, 1)

    def test_constructor_rejects_non_controller(self) -> None:
        candidates = _conflict_pair()
        with self.assertRaisesRegex(TypeError, "review_controller"):
            OCRConflictReviewModel(
                report=_report(*candidates),
                review=_review(*candidates),
                review_controller=object(),  # type: ignore[arg-type]
            )

    def test_one_conflict_display_uses_unit_1a_view(self) -> None:
        display = self.model(*_conflict_pair()).display

        self.assertIsInstance(display, OCRConflictReviewDisplay)
        self.assertEqual(display.position_label, "Conflict 1 of 1")
        self.assertEqual(display.conflict.source_coin_id, "coin-1")
        self.assertEqual(display.conflict.field_label, "Year")
        self.assertEqual(
            display.conflict.available_existing_values,
            ("1967", "1968"),
        )
        self.assertTrue(display.conflict.is_unresolved)

    def test_multiple_conflicts_keep_unit_1a_deterministic_order(self) -> None:
        country = _conflict_pair(
            source_coin_id="coin-1",
            field_name="country",
            first_value="Canada",
            second_value="US",
        )
        year = _conflict_pair()
        later = _conflict_pair(source_coin_id="coin-2")
        model = self.model(*later, *year, *country)

        identities = []
        while True:
            conflict = model.current_conflict
            identities.append(
                (conflict.source_coin_id, conflict.field_name)
            )
            if not model.next_conflict():
                break

        self.assertEqual(
            identities,
            [
                ("coin-1", "country"),
                ("coin-1", "year"),
                ("coin-2", "year"),
            ],
        )

    def test_position_and_count_update_with_navigation(self) -> None:
        model = self.model(
            *_conflict_pair(field_name="country"),
            *_conflict_pair(),
        )

        self.assertEqual(model.display.position_label, "Conflict 1 of 2")
        model.next_conflict()
        self.assertEqual(model.display.position_label, "Conflict 2 of 2")

    def test_all_provenance_records_remain_visible(self) -> None:
        first, second = _conflict_pair()
        duplicate_value = _candidate(
            value=first.normalized_value,
            image_role="edge",
            artifact_key="year-edge",
            provider_id="provider-edge",
            confidence_score=77.0,
            evidence=("edge evidence",),
        )

        display = self.model(first, second, duplicate_value).display

        self.assertEqual(len(display.provenance), 3)
        self.assertEqual(
            [
                item.conflicting_value
                for item in display.provenance
            ].count("1967"),
            2,
        )

    def test_provenance_is_enriched_with_confidence_and_evidence(self) -> None:
        display = self.model(*_conflict_pair()).display
        front = next(
            item
            for item in display.provenance
            if item.provider_id == "provider-front"
        )

        self.assertIsInstance(front, OCRConflictProvenanceDisplay)
        self.assertEqual(front.image_role, "front")
        self.assertEqual(front.artifact_key, "year-front")
        self.assertEqual(front.source_value, "1967")
        self.assertEqual(front.confidence_label, "91.25%")
        self.assertEqual(front.evidence, ("front evidence",))

    def test_initial_projection_is_unresolved_and_incomplete(self) -> None:
        display = self.model(*_conflict_pair()).display

        self.assertFalse(display.is_complete)
        self.assertEqual(display.unresolved_field_count, 1)
        year = next(
            field
            for field in display.unresolved_fields
            if field.field_name == "year"
        )
        self.assertIsNone(year.final_value)
        self.assertFalse(year.is_resolved)

    def test_grade_never_appears(self) -> None:
        model = self.model(*_conflict_pair())
        self.assertNotIn(
            "grade",
            tuple(
                conflict.field_name
                for conflict in model._state.session.conflict_resolutions
            ),
        )

    def test_select_existing_submits_exact_sprint_10_decision(self) -> None:
        controller = RecordingController()
        model = self.model(*_conflict_pair(), controller=controller)

        resolution = model.select_existing(value="1968")

        self.assertEqual(
            resolution.request.decision,
            OCRConflictResolutionDecision.SELECT_EXISTING_VALUE,
        )
        self.assertEqual(resolution.request.value, "1968")
        self.assertEqual(controller.resolution_calls[-1], (resolution,))

    def test_invalid_existing_value_is_rejected_without_state_change(
        self,
    ) -> None:
        model = self.model(*_conflict_pair())
        prior = model.select_existing(value="1967")

        with self.assertRaisesRegex(ValueError, "existing distinct value"):
            model.select_existing(value="not-available")

        self.assertIs(model.current_resolution, prior)
        self.assertEqual(
            model.display.conflict.selected_or_corrected_value,
            "1967",
        )

    def test_blank_existing_selection_is_not_silently_defaulted(self) -> None:
        model = self.model(*_conflict_pair())

        with self.assertRaises(ValueError):
            model.select_existing(value="")

        self.assertEqual(model.resolutions, ())

    def test_corrected_value_is_preserved_exactly(self) -> None:
        model = self.model(*_conflict_pair())

        resolution = model.enter_corrected(value=" 1969 ")

        self.assertEqual(
            resolution.request.decision,
            OCRConflictResolutionDecision.ENTER_CORRECTED_VALUE,
        )
        self.assertEqual(resolution.request.value, " 1969 ")
        self.assertEqual(
            model.display.conflict.selected_or_corrected_value,
            " 1969 ",
        )

    def test_blank_correction_is_rejected_without_state_change(self) -> None:
        model = self.model(*_conflict_pair())
        prior = model.select_existing(value="1967")

        with self.assertRaisesRegex(ValueError, "non-empty"):
            model.enter_corrected(value="   ")

        self.assertIs(model.current_resolution, prior)

    def test_corrected_existing_value_is_rejected_by_domain_service(self) -> None:
        model = self.model(*_conflict_pair())

        with self.assertRaisesRegex(ValueError, "must differ"):
            model.enter_corrected(value="1967")

        self.assertEqual(model.resolutions, ())

    def test_defer_submits_no_value_and_keeps_projection_unresolved(
        self,
    ) -> None:
        model = self.model(*_conflict_pair())

        resolution = model.defer()

        self.assertEqual(
            resolution.request.decision,
            OCRConflictResolutionDecision.DEFER,
        )
        self.assertIsNone(resolution.request.value)
        self.assertTrue(model.display.conflict.is_deferred)
        self.assertEqual(model.display.unresolved_field_count, 1)
        year = next(
            field
            for field in model.display.unresolved_fields
            if field.field_name == "year"
        )
        self.assertIsNone(year.final_value)

    def test_select_existing_updates_final_projection_after_validation(
        self,
    ) -> None:
        model = self.model(*_conflict_pair())

        model.select_existing(value="1968")

        year = next(
            field
            for field in model.display.final_fields
            if field.field_name == "year"
        )
        self.assertEqual(year.final_value, "1968")
        self.assertTrue(model.display.is_complete)
        self.assertEqual(model.display.unresolved_field_count, 0)

    def test_correction_updates_final_projection(self) -> None:
        model = self.model(*_conflict_pair())

        model.enter_corrected(value="1969")

        year = next(
            field
            for field in model.display.final_fields
            if field.field_name == "year"
        )
        self.assertEqual(year.final_value, "1969")
        self.assertTrue(year.is_resolved)

    def test_resolution_survives_navigation_and_is_reflected_on_return(
        self,
    ) -> None:
        model = self.model(
            *_conflict_pair(
                field_name="country",
                first_value="Canada",
                second_value="US",
            ),
            *_conflict_pair(),
        )
        model.select_existing(value="Canada")

        model.next_conflict()
        model.previous_conflict()

        self.assertEqual(
            model.current_resolution.request.value,
            "Canada",
        )
        self.assertEqual(
            model.current_conflict.resolution_decision,
            "SELECT_EXISTING_VALUE",
        )
        self.assertEqual(
            model.current_conflict.selected_or_corrected_value,
            "Canada",
        )

    def test_changed_aggregate_contains_prior_resolutions(self) -> None:
        controller = RecordingController()
        model = self.model(
            *_conflict_pair(
                field_name="country",
                first_value="Canada",
                second_value="US",
            ),
            *_conflict_pair(),
            controller=controller,
        )
        model.select_existing(value="Canada")
        model.next_conflict()

        model.defer()

        self.assertEqual(len(controller.resolution_calls[-1]), 2)
        self.assertEqual(len(model.resolutions), 2)

    def test_navigation_bounds_are_enforced(self) -> None:
        model = self.model(*_conflict_pair())

        self.assertFalse(model.previous_conflict())
        self.assertFalse(model.next_conflict())
        self.assertEqual(model.conflict_index, 0)

    def test_empty_conflict_state_is_safe(self) -> None:
        candidate = _candidate()
        model = self.model(candidate)

        self.assertEqual(model.conflict_count, 0)
        self.assertIsNone(model.current_conflict)
        self.assertEqual(model.display.position_label, "No OCR conflicts")
        self.assertFalse(model.next_conflict())
        with self.assertRaisesRegex(ValueError, "no OCR conflict"):
            model.defer()

    def test_initial_resolution_is_reflected_when_revisiting(self) -> None:
        model = self.model(*_conflict_pair())
        resolution = model.select_existing(value="1967")

        restored = self.model(
            *_conflict_pair(),
            resolutions=(resolution,),
        )

        self.assertEqual(restored.current_resolution, resolution)
        self.assertEqual(
            restored.current_conflict.selected_or_corrected_value,
            "1967",
        )


class OCRConflictReviewContractTests(unittest.TestCase):
    def test_display_contracts_are_immutable(self) -> None:
        pair = _conflict_pair()
        display = OCRConflictReviewModel(
            report=_report(*pair),
            review=_review(*pair),
            review_controller=OCRReviewSessionController(),
        ).display

        with self.assertRaises(FrozenInstanceError):
            display.position_label = "changed"
        with self.assertRaises(FrozenInstanceError):
            display.provenance[0].provider_id = "changed"

    def test_dialog_and_factory_public_api_exist(self) -> None:
        self.assertTrue(inspect.isclass(OCRConflictReviewDialog))
        self.assertTrue(callable(create_ocr_conflict_review_dialog))
        signature = inspect.signature(create_ocr_conflict_review_dialog)
        self.assertIn("review_controller", signature.parameters)
        self.assertIn("on_close", signature.parameters)

    def test_module_has_no_persistence_collection_or_filesystem_imports(
        self,
    ) -> None:
        module = importlib.import_module(
            "capture_import.desktop_ocr_conflict_review"
        )
        tree = ast.parse(inspect.getsource(module))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")

        forbidden_fragments = (
            "persistence",
            "collection",
            "confirmed_observation",
            "pathlib",
            "os",
        )
        self.assertFalse(
            any(
                fragment in imported
                for imported in imports
                for fragment in forbidden_fragments
            )
        )

    def test_unit_1c_and_default_desktop_do_not_import_conflict_ui(
        self,
    ) -> None:
        for module_name in (
            "capture_import.desktop_ocr_review_composition",
            "main",
        ):
            module = importlib.import_module(module_name)
            self.assertNotIn(
                "desktop_ocr_conflict_review",
                inspect.getsource(module),
            )

    def test_only_existing_domain_decisions_are_exposed(self) -> None:
        source = inspect.getsource(OCRConflictReviewModel)
        self.assertIn("SELECT_EXISTING_VALUE", source)
        self.assertIn("ENTER_CORRECTED_VALUE", source)
        self.assertIn("DEFER", source)
        self.assertNotIn("grade", source.lower())

    def test_actions_use_unit_1b_controller(self) -> None:
        source = inspect.getsource(OCRConflictReviewModel._submit)
        self.assertIn("apply_conflict_resolutions", source)
        self.assertIn(
            "OCRReviewSessionConflictResolutionRequest",
            source,
        )

    def test_mode_defaults_to_partial_review(self) -> None:
        default = inspect.signature(
            OCRConflictReviewModel
        ).parameters["mode"].default
        self.assertIs(default, OCRReviewMode.PARTIAL)


if __name__ == "__main__":
    unittest.main()
