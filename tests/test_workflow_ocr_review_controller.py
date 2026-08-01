"""Focused tests for the pure OCR review-session controller."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import importlib
import inspect
import json
import unittest

from tests.frozen_dataclass_compat import (
    assert_frozen_slotted_assignment_rejected,
)

from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
    OCRConflictResolutionRequest,
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
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_presenter import OCRReviewPresenter
from capture_import.workflow_ocr_review_service import (
    OCRReviewMode,
    OCRReviewReconciliationError,
)
from capture_import.workflow_ocr_review_session import (
    OCRReviewSessionConflictResolutionRequest,
    OCRReviewSessionRequest,
    OCRReviewSessionService,
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


def _field_review(
    candidate: OCRFieldCandidate,
    *,
    decision: OCRReviewDecision = OCRReviewDecision.APPROVE,
    reviewed_value: str | None = None,
) -> OCRFieldReview:
    if decision is OCRReviewDecision.APPROVE:
        reviewed_value = candidate.normalized_value
    return OCRFieldReview(
        source_coin_id=candidate.source_coin_id,
        image_role=candidate.image_role,
        artifact_key=candidate.artifact_key,
        provider_id=candidate.provider_id,
        field_name=candidate.field_name,
        original_value=candidate.normalized_value,
        decision=decision,
        reviewed_value=reviewed_value,
        reason=f"{decision.value} reason",
    )


def _review(*field_reviews: OCRFieldReview) -> OCRReportReview:
    return OCRReportReview(
        reviewer_id="reviewer-1",
        field_reviews=field_reviews,
    )


def _conflict_inputs() -> tuple[
    OCRMetadataReport,
    OCRReportReview,
]:
    first = _candidate(value="1967", artifact_key="crop-1")
    second = _candidate(
        value="1968",
        image_role="reverse",
        artifact_key="crop-2",
    )
    return (
        _report(first, second),
        _review(_field_review(first), _field_review(second)),
    )


def _resolution(
    report: OCRMetadataReport,
    review: OCRReportReview,
    *,
    decision: OCRConflictResolutionDecision,
    value: str | None,
) -> OCRReviewSessionConflictResolutionRequest:
    provisional = OCRReviewSessionService().run(
        request=OCRReviewSessionRequest(
            source_report=report,
            review=review,
            mode=OCRReviewMode.PARTIAL,
        )
    )
    return OCRReviewSessionConflictResolutionRequest(
        field=provisional.consolidation.fields[0],
        request=OCRConflictResolutionRequest(
            decision=decision,
            value=value,
        ),
    )


class RecordingSessionService(OCRReviewSessionService):
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, request: OCRReviewSessionRequest):
        self.calls += 1
        return super().run(request=request)


class RecordingPresenter(OCRReviewPresenter):
    def __init__(self) -> None:
        self.candidate_calls = 0
        self.session_calls = 0

    def present_candidates(self, **kwargs):
        self.candidate_calls += 1
        return super().present_candidates(**kwargs)

    def present_session(self, **kwargs):
        self.session_calls += 1
        return super().present_session(**kwargs)


class OCRReviewSessionControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = OCRReviewSessionController()

    def test_initial_empty_report(self) -> None:
        state = self.controller.present_initial(report=_report())

        self.assertTrue(state.is_initial)
        self.assertEqual(state.candidates, ())
        self.assertIsNone(state.mode)
        self.assertIsNone(state.session)

    def test_initial_one_candidate(self) -> None:
        state = self.controller.present_initial(
            report=_report(_candidate())
        )

        self.assertEqual(len(state.candidates), 1)
        self.assertEqual(state.candidates[0].original_value, "1967")
        self.assertIsNone(state.candidates[0].human_review_state)

    def test_initial_multiple_coins_and_fields_are_ordered(self) -> None:
        state = self.controller.present_initial(
            report=_report(
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
        )

        self.assertEqual(
            [
                (item.source_coin_id, item.field_name)
                for item in state.candidates
            ],
            [
                ("coin-1", "country"),
                ("coin-1", "year"),
                ("coin-2", "year"),
            ],
        )

    def test_initial_preserves_confidence_and_evidence(self) -> None:
        state = self.controller.present_initial(
            report=_report(
                _candidate(
                    confidence_score=87.25,
                    evidence=("date", "legend"),
                )
            )
        )

        self.assertEqual(state.candidates[0].confidence_score, 87.25)
        self.assertEqual(state.candidates[0].evidence, ("date", "legend"))

    def test_apply_approve_review(self) -> None:
        candidate = _candidate()
        state = self.controller.apply_field_reviews(
            report=_report(candidate),
            review=_review(_field_review(candidate)),
            mode=OCRReviewMode.STRICT_COMPLETE,
        )

        self.assertEqual(
            state.candidates[0].human_review_state,
            "APPROVE",
        )
        self.assertEqual(state.session.final_fields[0].final_value, "1967")

    def test_apply_correction_review(self) -> None:
        candidate = _candidate()
        state = self.controller.apply_field_reviews(
            report=_report(candidate),
            review=_review(
                _field_review(
                    candidate,
                    decision=OCRReviewDecision.CORRECT,
                    reviewed_value="1968",
                )
            ),
            mode=OCRReviewMode.STRICT_COMPLETE,
        )

        self.assertEqual(
            state.candidates[0].human_reviewed_value,
            "1968",
        )
        self.assertEqual(state.session.final_fields[0].final_value, "1968")

    def test_apply_reject_review(self) -> None:
        candidate = _candidate()
        state = self.controller.apply_field_reviews(
            report=_report(candidate),
            review=_review(
                _field_review(
                    candidate,
                    decision=OCRReviewDecision.REJECT,
                )
            ),
            mode=OCRReviewMode.STRICT_COMPLETE,
        )

        self.assertEqual(state.candidates[0].human_review_state, "REJECT")
        self.assertEqual(state.session.rejected_candidate_count, 1)
        self.assertEqual(state.session.final_field_count, 0)

    def test_apply_defer_review_in_partial_mode(self) -> None:
        candidate = _candidate()
        state = self.controller.apply_field_reviews(
            report=_report(candidate),
            review=_review(
                _field_review(
                    candidate,
                    decision=OCRReviewDecision.DEFER,
                )
            ),
            mode=OCRReviewMode.PARTIAL,
        )

        self.assertEqual(state.candidates[0].human_review_state, "DEFER")
        self.assertEqual(state.session.deferred_candidate_count, 1)
        self.assertFalse(state.session.is_complete)

    def test_mixed_field_reviews(self) -> None:
        approved = _candidate(field_name="year")
        rejected = _candidate(
            field_name="country",
            value="Canada",
            image_role="reverse",
            artifact_key="country",
        )
        state = self.controller.apply_field_reviews(
            report=_report(approved, rejected),
            review=_review(
                _field_review(approved),
                _field_review(
                    rejected,
                    decision=OCRReviewDecision.REJECT,
                ),
            ),
            mode=OCRReviewMode.STRICT_COMPLETE,
        )

        self.assertEqual(state.session.accepted_candidate_count, 1)
        self.assertEqual(state.session.rejected_candidate_count, 1)
        self.assertEqual(state.session.final_field_count, 1)

    def test_strict_mode_rejects_deferred_review(self) -> None:
        candidate = _candidate()

        with self.assertRaisesRegex(
            OCRReviewReconciliationError,
            "Strict OCR review",
        ):
            self.controller.apply_field_reviews(
                report=_report(candidate),
                review=_review(
                    _field_review(
                        candidate,
                        decision=OCRReviewDecision.DEFER,
                    )
                ),
                mode=OCRReviewMode.STRICT_COMPLETE,
            )

    def test_partial_mode_preserves_missing_review(self) -> None:
        reviewed = _candidate(field_name="year")
        missing = _candidate(
            field_name="country",
            value="Canada",
            image_role="reverse",
            artifact_key="country",
        )
        state = self.controller.apply_field_reviews(
            report=_report(reviewed, missing),
            review=_review(_field_review(reviewed)),
            mode=OCRReviewMode.PARTIAL,
        )

        self.assertEqual(state.session.missing_candidate_count, 1)
        self.assertFalse(state.session.is_complete)

    def test_invalid_review_target_is_rejected(self) -> None:
        candidate = _candidate()
        other = replace(candidate, artifact_key="invented")

        with self.assertRaisesRegex(
            OCRReviewReconciliationError,
            "does not exist",
        ):
            self.controller.apply_field_reviews(
                report=_report(candidate),
                review=_review(_field_review(other)),
                mode=OCRReviewMode.PARTIAL,
            )

    def test_duplicate_review_is_rejected_by_domain(self) -> None:
        candidate = _candidate()
        duplicate = _field_review(candidate)

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.controller.apply_field_reviews(
                report=_report(candidate),
                review=_review(duplicate, duplicate),
                mode=OCRReviewMode.PARTIAL,
            )

    def test_inputs_are_not_mutated(self) -> None:
        report, review = _conflict_inputs()
        resolution = _resolution(
            report,
            review,
            decision=(
                OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
            ),
            value="1967",
        )
        before_report = report.to_dict()
        before_review = review.to_dict()
        before_resolutions = tuple(
            item.to_dict() for item in (resolution,)
        )

        self.controller.apply_conflict_resolutions(
            report=report,
            review=review,
            resolutions=(resolution,),
            mode=OCRReviewMode.PARTIAL,
        )

        self.assertEqual(report.to_dict(), before_report)
        self.assertEqual(review.to_dict(), before_review)
        self.assertEqual(
            tuple(item.to_dict() for item in (resolution,)),
            before_resolutions,
        )

    def test_agreed_consolidated_field(self) -> None:
        candidate = _candidate()
        state = self.controller.apply_field_reviews(
            report=_report(candidate),
            review=_review(_field_review(candidate)),
            mode=OCRReviewMode.STRICT_COMPLETE,
        )

        field = state.session.consolidated_fields[0]
        self.assertEqual(field.status, "AGREED")
        self.assertEqual(field.consolidated_value, "1967")

    def test_conflicting_field_is_unresolved(self) -> None:
        report, review = _conflict_inputs()
        state = self.controller.apply_field_reviews(
            report=report,
            review=review,
            mode=OCRReviewMode.PARTIAL,
        )

        self.assertEqual(
            state.session.consolidated_fields[0].status,
            "CONFLICT",
        )
        self.assertTrue(
            state.session.conflict_resolutions[0].is_unresolved
        )

    def test_multiple_provenance_records_are_preserved(self) -> None:
        report, review = _conflict_inputs()
        state = self.controller.apply_field_reviews(
            report=report,
            review=review,
            mode=OCRReviewMode.PARTIAL,
        )

        field = state.session.consolidated_fields[0]
        self.assertEqual(field.provenance_count, 2)
        self.assertEqual(len(field.provenance), 2)

    def test_select_existing_conflict_value(self) -> None:
        report, review = _conflict_inputs()
        resolution = _resolution(
            report,
            review,
            decision=(
                OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
            ),
            value="1967",
        )
        state = self.controller.apply_conflict_resolutions(
            report=report,
            review=review,
            resolutions=(resolution,),
            mode=OCRReviewMode.PARTIAL,
        )

        conflict = state.session.conflict_resolutions[0]
        self.assertEqual(conflict.selected_or_corrected_value, "1967")
        self.assertFalse(conflict.is_unresolved)

    def test_enter_corrected_conflict_value(self) -> None:
        report, review = _conflict_inputs()
        resolution = _resolution(
            report,
            review,
            decision=(
                OCRConflictResolutionDecision.ENTER_CORRECTED_VALUE
            ),
            value="1969",
        )
        state = self.controller.apply_conflict_resolutions(
            report=report,
            review=review,
            resolutions=(resolution,),
            mode=OCRReviewMode.PARTIAL,
        )

        self.assertEqual(
            state.session.final_fields[0].final_value,
            "1969",
        )
        self.assertIsNone(
            state.session.final_fields[0].resolution_rationale
        )

    def test_defer_conflict(self) -> None:
        report, review = _conflict_inputs()
        resolution = _resolution(
            report,
            review,
            decision=OCRConflictResolutionDecision.DEFER,
            value=None,
        )
        state = self.controller.apply_conflict_resolutions(
            report=report,
            review=review,
            resolutions=(resolution,),
            mode=OCRReviewMode.PARTIAL,
        )

        conflict = state.session.conflict_resolutions[0]
        self.assertTrue(conflict.is_deferred)
        self.assertTrue(conflict.is_unresolved)

    def test_invalid_resolution_is_rejected_by_domain(self) -> None:
        report, review = _conflict_inputs()
        resolution = _resolution(
            report,
            review,
            decision=(
                OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
            ),
            value="1967",
        )
        invented_field = replace(
            resolution.field,
            source_coin_id="invented",
        )

        with self.assertRaisesRegex(ValueError, "Invented"):
            self.controller.apply_conflict_resolutions(
                report=report,
                review=review,
                resolutions=(
                    replace(resolution, field=invented_field),
                ),
                mode=OCRReviewMode.PARTIAL,
            )

    def test_complete_session_and_counts_match_domain_output(self) -> None:
        candidate = _candidate()
        report = _report(candidate)
        review = _review(_field_review(candidate))
        state = self.controller.present_session(
            report=report,
            review=review,
            mode=OCRReviewMode.STRICT_COMPLETE,
        )
        domain = OCRReviewSessionService().run(
            request=OCRReviewSessionRequest(
                source_report=report,
                review=review,
                mode=OCRReviewMode.STRICT_COMPLETE,
            )
        )

        self.assertTrue(state.session.is_complete)
        self.assertEqual(
            state.session.final_field_count,
            domain.final_field_count,
        )
        self.assertEqual(
            state.session.unresolved_field_count,
            domain.unresolved_field_count,
        )

    def test_incomplete_session_emits_no_unresolved_value(self) -> None:
        report, review = _conflict_inputs()
        state = self.controller.present_session(
            report=report,
            review=review,
        )

        self.assertFalse(state.session.is_complete)
        self.assertEqual(state.session.unresolved_field_count, 1)
        self.assertIsNone(
            state.session.unresolved_fields[0].final_value
        )

    def test_equivalent_inputs_serialize_identically(self) -> None:
        report, review = _conflict_inputs()

        first = self.controller.present_session(
            report=report,
            review=review,
        ).to_dict()
        second = self.controller.present_session(
            report=report,
            review=review,
        ).to_dict()

        self.assertEqual(first, second)
        self.assertEqual(json.loads(json.dumps(first)), first)
        self.assertNotIn("timestamp", json.dumps(first))

    def test_controller_state_is_immutable_and_slotted(self) -> None:
        state = self.controller.present_initial(
            report=_report(_candidate())
        )

        self.assertIsInstance(state, OCRReviewControllerState)
        with self.assertRaises(FrozenInstanceError):
            state.mode = "PARTIAL"  # type: ignore[misc]
        with assert_frozen_slotted_assignment_rejected(self, state):
            state.extra = "no"  # type: ignore[attr-defined]

    def test_invalid_source_types_are_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "source_report"):
            self.controller.present_initial(  # type: ignore[arg-type]
                report=object()
            )
        with self.assertRaisesRegex(TypeError, "review"):
            self.controller.present_session(  # type: ignore[arg-type]
                report=_report(_candidate()),
                review=object(),
            )
        with self.assertRaisesRegex(TypeError, "mode"):
            self.controller.present_session(  # type: ignore[arg-type]
                report=_report(_candidate()),
                mode="PARTIAL",
            )
        with self.assertRaisesRegex(TypeError, "resolutions"):
            self.controller.present_session(  # type: ignore[arg-type]
                report=_report(_candidate()),
                resolutions=[],
            )

    def test_grade_is_absent(self) -> None:
        state = self.controller.present_initial(
            report=_report(_candidate())
        )

        self.assertNotIn("grade", json.dumps(state.to_dict()))
        with self.assertRaisesRegex(ValueError, "field_name"):
            self.controller.present_initial(
                report=_report(
                    _candidate(field_name="grade", value="MS-63")
                )
            )

    def test_injected_session_service_and_presenter_are_used(self) -> None:
        service = RecordingSessionService()
        presenter = RecordingPresenter()
        controller = OCRReviewSessionController(
            session_service=service,
            presenter=presenter,
        )
        candidate = _candidate()

        controller.apply_field_reviews(
            report=_report(candidate),
            review=_review(_field_review(candidate)),
            mode=OCRReviewMode.STRICT_COMPLETE,
        )

        self.assertEqual(service.calls, 1)
        self.assertEqual(presenter.candidate_calls, 1)
        self.assertEqual(presenter.session_calls, 1)

    def test_architecture_import_boundary(self) -> None:
        module = importlib.import_module(
            "capture_import.workflow_ocr_review_controller"
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
                "typing",
                "capture_import.workflow_ocr_models",
                "capture_import.workflow_ocr_review_models",
                "capture_import.workflow_ocr_review_presenter",
                "capture_import.workflow_ocr_review_service",
                "capture_import.workflow_ocr_review_session",
            },
        )
        prohibited = (
            "tkinter",
            "PyQt",
            "filesystem",
            "pathlib",
            "os.",
            "environ",
            "persistence",
            "collection",
            "confirmed_observation",
            "legacy_ocr",
        )
        self.assertFalse(any(token in source for token in prohibited))


if __name__ == "__main__":
    unittest.main()
