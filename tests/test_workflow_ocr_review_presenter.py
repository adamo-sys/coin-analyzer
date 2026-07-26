"""Focused tests for immutable desktop OCR review presentation models."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import importlib
import inspect
import json
import unittest

from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
    OCRConflictResolutionRequest,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRReviewStatus,
)
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_presenter import (
    OCRReviewPresenter,
)
from capture_import.workflow_ocr_review_service import OCRReviewMode
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


def _session(
    report: OCRMetadataReport,
    review: OCRReportReview,
    *,
    conflict_decision: OCRConflictResolutionDecision | None = None,
    conflict_value: str | None = None,
):
    provisional = OCRReviewSessionService().run(
        request=OCRReviewSessionRequest(
            source_report=report,
            review=review,
            mode=OCRReviewMode.PARTIAL,
        )
    )
    requests = ()
    if conflict_decision is not None:
        requests = (
            OCRReviewSessionConflictResolutionRequest(
                field=provisional.consolidation.fields[0],
                request=OCRConflictResolutionRequest(
                    decision=conflict_decision,
                    value=conflict_value,
                ),
            ),
        )
    return OCRReviewSessionService().run(
        request=OCRReviewSessionRequest(
            source_report=report,
            review=review,
            mode=OCRReviewMode.PARTIAL,
            conflict_resolution_requests=requests,
        )
    )


class OCRReviewPresenterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.presenter = OCRReviewPresenter()

    def test_single_candidate_presentation(self) -> None:
        candidate = _candidate()

        view = self.presenter.present_candidates(
            source_report=_report(candidate)
        )[0]

        self.assertEqual(view.source_coin_id, "coin-1")
        self.assertEqual(view.field_name, "year")
        self.assertEqual(view.field_label, "Year")
        self.assertEqual(view.original_value, "1967")
        self.assertEqual(view.human_review_state, None)
        self.assertEqual(view.human_review_label, "Not Reviewed")

    def test_candidate_preserves_evidence_and_confidence(self) -> None:
        candidate = _candidate(
            confidence_score=87.25,
            evidence=("date", "legend"),
        )

        view = self.presenter.present_candidates(
            source_report=_report(candidate)
        )[0]

        self.assertEqual(view.confidence_score, 87.25)
        self.assertEqual(view.evidence, ("date", "legend"))
        self.assertEqual(view.raw_text, "raw 1967")
        self.assertEqual(view.machine_review_status, "REVIEW_REQUIRED")

    def test_candidate_with_human_approve_decision(self) -> None:
        candidate = _candidate()
        view = self.presenter.present_candidates(
            source_report=_report(candidate),
            review=_review(_field_review(candidate)),
        )[0]

        self.assertEqual(view.human_review_state, "APPROVE")
        self.assertEqual(view.human_reviewed_value, "1967")
        self.assertEqual(view.human_reason, "APPROVE reason")

    def test_candidate_with_human_correction(self) -> None:
        candidate = _candidate()
        view = self.presenter.present_candidates(
            source_report=_report(candidate),
            review=_review(
                _field_review(
                    candidate,
                    decision=OCRReviewDecision.CORRECT,
                    reviewed_value="1968",
                )
            ),
        )[0]

        self.assertEqual(view.human_review_state, "CORRECT")
        self.assertEqual(view.human_reviewed_value, "1968")

    def test_candidate_rejected(self) -> None:
        candidate = _candidate()
        view = self.presenter.present_candidates(
            source_report=_report(candidate),
            review=_review(
                _field_review(
                    candidate,
                    decision=OCRReviewDecision.REJECT,
                )
            ),
        )[0]

        self.assertEqual(view.human_review_state, "REJECT")
        self.assertIsNone(view.human_reviewed_value)

    def test_candidate_deferred(self) -> None:
        candidate = _candidate()
        view = self.presenter.present_candidates(
            source_report=_report(candidate),
            review=_review(
                _field_review(
                    candidate,
                    decision=OCRReviewDecision.DEFER,
                )
            ),
        )[0]

        self.assertEqual(view.human_review_state, "DEFER")
        self.assertIsNone(view.human_reviewed_value)

    def test_agreed_consolidated_field(self) -> None:
        candidate = _candidate()
        result = _session(
            _report(candidate),
            _review(_field_review(candidate)),
        )

        view = self.presenter.present_consolidation(
            consolidation=result.consolidation
        )[0]

        self.assertEqual(view.status, "AGREED")
        self.assertEqual(view.consolidated_value, "1967")
        self.assertEqual(view.distinct_values, ("1967",))

    def test_conflicting_consolidated_field(self) -> None:
        first = _candidate(value="1967", artifact_key="crop-1")
        second = _candidate(
            value="1968",
            image_role="reverse",
            artifact_key="crop-2",
        )
        result = _session(
            _report(first, second),
            _review(_field_review(first), _field_review(second)),
        )

        view = self.presenter.present_consolidation(
            consolidation=result.consolidation
        )[0]

        self.assertEqual(view.status, "CONFLICT")
        self.assertIsNone(view.consolidated_value)
        self.assertEqual(view.distinct_values, ("1967", "1968"))

    def test_multiple_provenance_records_are_preserved(self) -> None:
        first = _candidate(artifact_key="crop-1")
        second = _candidate(
            image_role="reverse",
            artifact_key="crop-2",
        )
        result = _session(
            _report(first, second),
            _review(_field_review(first), _field_review(second)),
        )

        view = self.presenter.present_consolidation(
            consolidation=result.consolidation
        )[0]

        self.assertEqual(view.provenance_count, 2)
        self.assertEqual(
            [item.artifact_key for item in view.provenance],
            ["crop-1", "crop-2"],
        )

    def test_resolved_conflict_selecting_existing_value(self) -> None:
        result = self._conflict_session(
            OCRConflictResolutionDecision.SELECT_EXISTING_VALUE,
            "1967",
        )

        view = self.presenter.present_conflicts(
            consolidation=result.consolidation,
            resolutions=result.conflict_resolutions,
        )[0]

        self.assertEqual(
            view.resolution_decision,
            "SELECT_EXISTING_VALUE",
        )
        self.assertEqual(view.selected_or_corrected_value, "1967")
        self.assertFalse(view.is_unresolved)

    def test_resolved_conflict_entering_corrected_value(self) -> None:
        result = self._conflict_session(
            OCRConflictResolutionDecision.ENTER_CORRECTED_VALUE,
            "1969",
        )

        view = self.presenter.present_conflicts(
            consolidation=result.consolidation,
            resolutions=result.conflict_resolutions,
        )[0]

        self.assertEqual(
            view.resolution_decision,
            "ENTER_CORRECTED_VALUE",
        )
        self.assertEqual(view.selected_or_corrected_value, "1969")
        self.assertIsNone(view.resolution_rationale)

    def test_deferred_conflict(self) -> None:
        result = self._conflict_session(
            OCRConflictResolutionDecision.DEFER,
            None,
        )

        view = self.presenter.present_conflicts(
            consolidation=result.consolidation,
            resolutions=result.conflict_resolutions,
        )[0]

        self.assertTrue(view.is_deferred)
        self.assertTrue(view.is_unresolved)
        self.assertIsNone(view.selected_or_corrected_value)

    def test_final_complete_projection(self) -> None:
        candidate = _candidate()
        result = _session(
            _report(candidate),
            _review(_field_review(candidate)),
        )

        view = self.presenter.present_session(result=result)

        self.assertTrue(view.is_complete)
        self.assertEqual(view.final_field_count, 1)
        self.assertEqual(view.unresolved_field_count, 0)
        self.assertEqual(view.final_fields[0].final_value, "1967")

    def test_final_incomplete_projection(self) -> None:
        result = self._conflict_session(None, None)

        view = self.presenter.present_session(result=result)

        self.assertFalse(view.is_complete)
        self.assertEqual(view.final_field_count, 0)
        self.assertEqual(view.unresolved_field_count, 1)

    def test_unresolved_field_emits_no_final_value(self) -> None:
        result = self._conflict_session(None, None)

        final_fields, unresolved = (
            self.presenter.present_final_projection(
                projection=result.final_projection
            )
        )

        self.assertEqual(final_fields, ())
        self.assertEqual(len(unresolved), 1)
        self.assertIsNone(unresolved[0].final_value)
        self.assertFalse(unresolved[0].is_resolved)

    def test_deterministic_ordering_across_coins_and_fields(self) -> None:
        candidates = (
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
        views = self.presenter.present_candidates(
            source_report=_report(*candidates)
        )

        self.assertEqual(
            [(item.source_coin_id, item.field_name) for item in views],
            [
                ("coin-1", "country"),
                ("coin-1", "year"),
                ("coin-2", "year"),
            ],
        )

    def test_deterministic_json_serialization(self) -> None:
        result = self._conflict_session(
            OCRConflictResolutionDecision.SELECT_EXISTING_VALUE,
            "1967",
        )

        first = self.presenter.present_session(result=result).to_dict()
        second = self.presenter.present_session(result=result).to_dict()

        self.assertEqual(first, second)
        self.assertEqual(json.loads(json.dumps(first)), first)
        self.assertNotIn("timestamp", json.dumps(first))

    def test_view_models_are_immutable_and_slotted(self) -> None:
        view = self.presenter.present_candidates(
            source_report=_report(_candidate())
        )[0]

        with self.assertRaises(FrozenInstanceError):
            view.field_name = "country"  # type: ignore[misc]
        with self.assertRaises(AttributeError):
            view.extra = "no"  # type: ignore[attr-defined]

    def test_inputs_remain_unchanged(self) -> None:
        candidate = _candidate()
        report = _report(candidate)
        review = _review(_field_review(candidate))
        before_report = report.to_dict()
        before_review = review.to_dict()

        self.presenter.present_candidates(
            source_report=report,
            review=review,
        )

        self.assertEqual(report.to_dict(), before_report)
        self.assertEqual(review.to_dict(), before_review)

    def test_invalid_source_types_are_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "source_report"):
            self.presenter.present_candidates(  # type: ignore[arg-type]
                source_report=object()
            )
        with self.assertRaisesRegex(TypeError, "consolidation"):
            self.presenter.present_consolidation(  # type: ignore[arg-type]
                consolidation=object()
            )
        with self.assertRaisesRegex(TypeError, "projection"):
            self.presenter.present_final_projection(  # type: ignore[arg-type]
                projection=object()
            )
        with self.assertRaisesRegex(TypeError, "result"):
            self.presenter.present_session(result=object())  # type: ignore[arg-type]

    def test_grade_remains_excluded(self) -> None:
        candidate = _candidate(field_name="grade", value="MS-63")

        with self.assertRaisesRegex(ValueError, "field_name"):
            self.presenter.present_candidates(
                source_report=_report(candidate)
            )
        self.assertNotIn(
            "grade",
            json.dumps(
                self.presenter.present_candidates(
                    source_report=_report(_candidate())
                )[0].to_dict()
            ),
        )

    def test_import_boundary(self) -> None:
        module = importlib.import_module(
            "capture_import.workflow_ocr_review_presenter"
        )
        tree = ast.parse(inspect.getsource(module))
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
                "capture_import.workflow_ocr_conflict_resolution",
                "capture_import.workflow_ocr_consolidation",
                "capture_import.workflow_ocr_final_projection",
                "capture_import.workflow_ocr_models",
                "capture_import.workflow_ocr_review_models",
                "capture_import.workflow_ocr_review_session",
                "capture_import.workflow_ocr_review_service",
            },
        )

    @staticmethod
    def _conflict_session(
        decision: OCRConflictResolutionDecision | None,
        value: str | None,
    ):
        first = _candidate(value="1967", artifact_key="crop-1")
        second = _candidate(
            value="1968",
            image_role="reverse",
            artifact_key="crop-2",
        )
        return _session(
            _report(first, second),
            _review(_field_review(first), _field_review(second)),
            conflict_decision=decision,
            conflict_value=value,
        )


if __name__ == "__main__":
    unittest.main()
