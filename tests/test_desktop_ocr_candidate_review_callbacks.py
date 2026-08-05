"""Callback and review-state integration tests for desktop OCR candidate review."""

from __future__ import annotations

from types import SimpleNamespace
import unittest

from capture_import.desktop_ocr_candidate_review import (
    OCRCandidateReviewDialog,
    OCRCandidateReviewModel,
    _FOCUS_CORRECT,
    _FOCUS_CORRECTION,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRReviewStatus,
)
from capture_import.workflow_ocr_review_controller import (
    OCRReviewSessionController,
)
from capture_import.workflow_ocr_review_models import OCRReviewDecision


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

    def test_failed_decision_preserves_batch_progress(self) -> None:
        model = self.model(_candidate())
        model.reject(reason="Prior decision.")
        before = model._batch_progress()

        with self.assertRaises(ValueError):
            model.approve(reason="")

        self.assertEqual(model._batch_progress(), before)

    def test_decision_does_not_automatically_advance_batch_position(self) -> None:
        model = self.model(
            _candidate(),
            _candidate(field_name="country", value="Canada"),
        )

        model.approve(reason="Approved current candidate.")

        self.assertEqual(model.candidate_index, 0)
        self.assertEqual(model._batch_progress().overall_position, 1)

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
        focus_roles = []
        dialog._schedule_focus = focus_roles.append

        dialog._run_action(
            lambda: (_ for _ in ()).throw(
                ValueError("reviewed_value must not be empty.")
            ),
            success_focus_role=_FOCUS_CORRECT,
            failure_focus_role=_FOCUS_CORRECTION,
        )

        self.assertEqual(
            errors,
            ["reviewed_value must not be empty."],
        )
        self.assertEqual(renders, [])
        self.assertEqual(focus_roles, [_FOCUS_CORRECTION])
