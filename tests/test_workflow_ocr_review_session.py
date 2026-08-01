"""Tests for pure reviewed OCR session orchestration."""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import unittest
from dataclasses import FrozenInstanceError, replace

from tests.frozen_dataclass_compat import (
    assert_frozen_slotted_assignment_rejected,
)

from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
    OCRConflictResolutionRequest,
)
from capture_import.workflow_ocr_consolidation import (
    OCRConsolidatedField,
    OCRMetadataConsolidationService,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
)
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_service import (
    OCRReviewMode,
    OCRReviewReconciliationError,
    OCRReviewReconciliationService,
)
from capture_import.workflow_ocr_review_session import (
    OCRReviewSessionConflictResolutionRequest,
    OCRReviewSessionRequest,
    OCRReviewSessionResult,
    OCRReviewSessionService,
)


def _candidate(
    *,
    source_coin_id: str = "coin-1",
    image_role: str = "front",
    artifact_key: str = "crop-front",
    provider_id: str = "legacy-ocr",
    field_name: str = "year",
    value: str = "1967",
) -> OCRFieldCandidate:
    return OCRFieldCandidate(
        source_coin_id=source_coin_id,
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id=provider_id,
        field_name=field_name,
        raw_text=value,
        normalized_value=value,
        confidence_score=0.90,
    )


def _report(*candidates: OCRFieldCandidate) -> OCRMetadataReport:
    return OCRMetadataReport(
        provider_available=True,
        candidates=tuple(
            sorted(
                candidates,
                key=lambda candidate: (
                    candidate.source_coin_id,
                    candidate.field_name,
                    candidate.image_role,
                    candidate.normalized_value,
                    candidate.provider_id,
                    candidate.artifact_key,
                ),
            )
        ),
    )


def _field_review(
    candidate: OCRFieldCandidate,
    *,
    decision: OCRReviewDecision = OCRReviewDecision.APPROVE,
    reviewed_value: str | None = None,
    reason: str = "Reviewed by collector.",
) -> OCRFieldReview:
    if decision is OCRReviewDecision.APPROVE and reviewed_value is None:
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
        reason=reason,
    )


def _review(*field_reviews: OCRFieldReview) -> OCRReportReview:
    return OCRReportReview(
        reviewer_id="collector-1",
        field_reviews=tuple(field_reviews),
    )


def _request(
    *,
    report: OCRMetadataReport,
    review: OCRReportReview,
    mode: OCRReviewMode = OCRReviewMode.STRICT_COMPLETE,
    resolutions: tuple[
        OCRReviewSessionConflictResolutionRequest,
        ...,
    ] = (),
) -> OCRReviewSessionRequest:
    return OCRReviewSessionRequest(
        source_report=report,
        review=review,
        mode=mode,
        conflict_resolution_requests=resolutions,
    )


def _consolidated_field(
    *,
    report: OCRMetadataReport,
    review: OCRReportReview,
) -> OCRConsolidatedField:
    reconciliation = OCRReviewReconciliationService().reconcile(
        source_report=report,
        review=review,
        mode=OCRReviewMode.STRICT_COMPLETE,
    )
    consolidation = OCRMetadataConsolidationService().consolidate(
        reconciliation=reconciliation,
    )
    return consolidation.fields[0]


def _targeted_resolution(
    field: OCRConsolidatedField,
    *,
    decision: OCRConflictResolutionDecision = (
        OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
    ),
    value: str | None = "1967",
) -> OCRReviewSessionConflictResolutionRequest:
    return OCRReviewSessionConflictResolutionRequest(
        field=field,
        request=OCRConflictResolutionRequest(
            decision=decision,
            value=value,
        ),
    )


def _conflict_inputs() -> tuple[
    OCRMetadataReport,
    OCRReportReview,
    OCRConsolidatedField,
]:
    front = _candidate()
    reverse = _candidate(
        image_role="reverse",
        artifact_key="crop-reverse",
        value="1968",
    )
    report = _report(front, reverse)
    review = _review(_field_review(front), _field_review(reverse))
    return report, review, _consolidated_field(report=report, review=review)


class OCRReviewSessionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = OCRReviewSessionService()

    def test_strict_approved_field(self) -> None:
        candidate = _candidate()
        result = self.service.run(
            request=_request(
                report=_report(candidate),
                review=_review(_field_review(candidate)),
            )
        )

        self.assertTrue(result.is_complete)
        self.assertEqual(result.reconciliation.accepted_count, 1)
        self.assertEqual(result.final_field_count, 1)
        self.assertEqual(
            result.final_projection.final_fields[0].final_value,
            "1967",
        )

    def test_strict_corrected_field_preserves_reason(self) -> None:
        candidate = _candidate()
        result = self.service.run(
            request=_request(
                report=_report(candidate),
                review=_review(
                    _field_review(
                        candidate,
                        decision=OCRReviewDecision.CORRECT,
                        reviewed_value="1969",
                        reason="Corrected final digit after review.",
                    )
                ),
            )
        )

        provenance = result.consolidation.fields[0].provenance[0]
        self.assertEqual(provenance.accepted_value, "1969")
        self.assertEqual(
            provenance.reason,
            "Corrected final digit after review.",
        )

    def test_strict_rejected_candidate_has_no_final_field(self) -> None:
        candidate = _candidate()
        result = self.service.run(
            request=_request(
                report=_report(candidate),
                review=_review(
                    _field_review(
                        candidate,
                        decision=OCRReviewDecision.REJECT,
                    )
                ),
            )
        )

        self.assertTrue(result.is_complete)
        self.assertEqual(result.reconciliation.rejected_count, 1)
        self.assertEqual(result.final_field_count, 0)

    def test_strict_agreed_multi_source_value(self) -> None:
        front = _candidate()
        reverse = _candidate(
            image_role="reverse",
            artifact_key="crop-reverse",
        )
        result = self.service.run(
            request=_request(
                report=_report(front, reverse),
                review=_review(
                    _field_review(front),
                    _field_review(reverse),
                ),
            )
        )

        self.assertEqual(result.consolidation.agreed_count, 1)
        self.assertEqual(
            len(result.consolidation.fields[0].provenance),
            2,
        )
        self.assertEqual(result.final_field_count, 1)

    def test_conflict_selects_existing_value(self) -> None:
        report, review, conflict = _conflict_inputs()
        result = self.service.run(
            request=_request(
                report=report,
                review=review,
                resolutions=(
                    _targeted_resolution(conflict, value="1968"),
                ),
            )
        )

        self.assertTrue(result.is_complete)
        self.assertEqual(result.conflict_resolution_count, 1)
        self.assertEqual(
            result.final_projection.final_fields[0].final_value,
            "1968",
        )

    def test_conflict_enters_corrected_value(self) -> None:
        report, review, conflict = _conflict_inputs()
        result = self.service.run(
            request=_request(
                report=report,
                review=review,
                resolutions=(
                    _targeted_resolution(
                        conflict,
                        decision=(
                            OCRConflictResolutionDecision
                            .ENTER_CORRECTED_VALUE
                        ),
                        value="1969",
                    ),
                ),
            )
        )

        self.assertEqual(
            result.final_projection.final_fields[0].final_value,
            "1969",
        )

    def test_partial_missing_review_is_incomplete(self) -> None:
        reviewed = _candidate()
        missing = _candidate(
            field_name="country",
            value="Canada",
            image_role="reverse",
            artifact_key="crop-reverse",
        )
        result = self.service.run(
            request=_request(
                report=_report(reviewed, missing),
                review=_review(_field_review(reviewed)),
                mode=OCRReviewMode.PARTIAL,
            )
        )

        self.assertFalse(result.is_complete)
        self.assertEqual(result.reconciliation.missing_count, 1)
        self.assertEqual(result.final_field_count, 1)

    def test_partial_deferred_review_is_incomplete(self) -> None:
        candidate = _candidate()
        result = self.service.run(
            request=_request(
                report=_report(candidate),
                review=_review(
                    _field_review(
                        candidate,
                        decision=OCRReviewDecision.DEFER,
                    )
                ),
                mode=OCRReviewMode.PARTIAL,
            )
        )

        self.assertFalse(result.is_complete)
        self.assertEqual(result.reconciliation.deferred_count, 1)
        self.assertEqual(result.final_field_count, 0)

    def test_strict_missing_or_deferred_review_fails(self) -> None:
        reviewed = _candidate()
        missing = _candidate(
            field_name="country",
            value="Canada",
            image_role="reverse",
            artifact_key="crop-reverse",
        )

        with self.assertRaises(OCRReviewReconciliationError):
            self.service.run(
                request=_request(
                    report=_report(reviewed, missing),
                    review=_review(_field_review(reviewed)),
                )
            )

        with self.assertRaises(OCRReviewReconciliationError):
            self.service.run(
                request=_request(
                    report=_report(reviewed),
                    review=_review(
                        _field_review(
                            reviewed,
                            decision=OCRReviewDecision.DEFER,
                        )
                    ),
                )
            )

    def test_unresolved_conflict_without_resolution(self) -> None:
        report, review, _ = _conflict_inputs()
        result = self.service.run(
            request=_request(report=report, review=review)
        )

        self.assertFalse(result.is_complete)
        self.assertEqual(result.unresolved_field_count, 1)
        self.assertEqual(result.conflict_resolution_count, 0)

    def test_deferred_conflict_resolution_remains_unresolved(self) -> None:
        report, review, conflict = _conflict_inputs()
        result = self.service.run(
            request=_request(
                report=report,
                review=review,
                resolutions=(
                    _targeted_resolution(
                        conflict,
                        decision=OCRConflictResolutionDecision.DEFER,
                        value=None,
                    ),
                ),
            )
        )

        self.assertFalse(result.is_complete)
        self.assertEqual(result.unresolved_field_count, 1)
        self.assertEqual(result.conflict_resolution_count, 1)

    def test_invented_conflict_resolution_is_rejected(self) -> None:
        report, review, conflict = _conflict_inputs()
        invented = replace(conflict, source_coin_id="coin-invented")

        with self.assertRaisesRegex(ValueError, "Invented"):
            self.service.run(
                request=_request(
                    report=report,
                    review=review,
                    resolutions=(_targeted_resolution(invented),),
                )
            )

    def test_duplicate_conflict_resolution_is_rejected(self) -> None:
        report, review, conflict = _conflict_inputs()
        resolution = _targeted_resolution(conflict)

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.service.run(
                request=_request(
                    report=report,
                    review=review,
                    resolutions=(resolution, resolution),
                )
            )

    def test_mismatched_conflict_resolution_is_rejected(self) -> None:
        report, review, conflict = _conflict_inputs()
        mismatched = replace(
            conflict,
            provenance=(
                replace(
                    conflict.provenance[0],
                    reason="Mismatched review rationale.",
                ),
                conflict.provenance[1],
            ),
        )

        with self.assertRaisesRegex(ValueError, "do not match"):
            self.service.run(
                request=_request(
                    report=report,
                    review=review,
                    resolutions=(_targeted_resolution(mismatched),),
                )
            )

    def test_non_conflict_resolution_is_rejected(self) -> None:
        candidate = _candidate()
        report = _report(candidate)
        review = _review(_field_review(candidate))
        agreed = _consolidated_field(report=report, review=review)

        with self.assertRaisesRegex(ValueError, "CONFLICT"):
            self.service.run(
                request=_request(
                    report=report,
                    review=review,
                    resolutions=(_targeted_resolution(agreed),),
                )
            )

    def test_deterministic_order_across_coins_and_fields(self) -> None:
        coin_2_year = _candidate(source_coin_id="coin-2")
        coin_1_year = _candidate(source_coin_id="coin-1")
        coin_1_country = _candidate(
            source_coin_id="coin-1",
            image_role="reverse",
            artifact_key="crop-country",
            field_name="country",
            value="Canada",
        )
        report = _report(coin_2_year, coin_1_year, coin_1_country)
        review = _review(
            _field_review(coin_2_year),
            _field_review(coin_1_year),
            _field_review(coin_1_country),
        )

        result = self.service.run(
            request=_request(report=report, review=review)
        )

        self.assertEqual(
            [
                field.identity
                for field in result.final_projection.final_fields
            ],
            [
                ("coin-1", "country"),
                ("coin-1", "year"),
                ("coin-2", "year"),
            ],
        )

    def test_deterministic_json_safe_serialization(self) -> None:
        report, review, conflict = _conflict_inputs()
        request = _request(
            report=report,
            review=review,
            resolutions=(_targeted_resolution(conflict),),
        )

        first = self.service.run(request=request).to_dict()
        second = self.service.run(request=request).to_dict()

        self.assertEqual(first, second)
        self.assertEqual(json.loads(json.dumps(first)), first)
        self.assertNotIn("timestamp", first)

    def test_request_and_result_are_immutable_and_slotted(self) -> None:
        candidate = _candidate()
        request = _request(
            report=_report(candidate),
            review=_review(_field_review(candidate)),
        )
        result = self.service.run(request=request)

        with self.assertRaises(FrozenInstanceError):
            request.mode = OCRReviewMode.PARTIAL  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.consolidation = object()  # type: ignore[misc]
        with assert_frozen_slotted_assignment_rejected(self, request):
            request.extra = "no"  # type: ignore[attr-defined]

    def test_inputs_are_not_mutated(self) -> None:
        report, review, conflict = _conflict_inputs()
        request = _request(
            report=report,
            review=review,
            resolutions=(_targeted_resolution(conflict),),
        )
        before = request.to_dict()

        self.service.run(request=request)

        self.assertEqual(request.to_dict(), before)

    def test_invalid_input_and_result_types_are_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "request"):
            self.service.run(request=object())  # type: ignore[arg-type]

        candidate = _candidate()
        request = OCRReviewSessionRequest(
            source_report=_report(candidate),
            review=_review(_field_review(candidate)),
            mode="STRICT_COMPLETE",  # type: ignore[arg-type]
        )
        with self.assertRaisesRegex(TypeError, "mode"):
            request.validate()

        valid_result = self.service.run(
            request=_request(
                report=_report(candidate),
                review=_review(_field_review(candidate)),
            )
        )
        invalid_result = OCRReviewSessionResult(
            reconciliation=object(),  # type: ignore[arg-type]
            consolidation=valid_result.consolidation,
            conflict_resolutions=(),
            final_projection=valid_result.final_projection,
        )
        with self.assertRaisesRegex(TypeError, "reconciliation"):
            invalid_result.validate()

    def test_grade_remains_impossible(self) -> None:
        grade = _candidate(field_name="grade", value="MS-63")

        with self.assertRaisesRegex(ValueError, "field_name"):
            self.service.run(
                request=_request(
                    report=_report(grade),
                    review=_review(_field_review(grade)),
                )
            )

    def test_import_boundary(self) -> None:
        module = importlib.import_module(
            "capture_import.workflow_ocr_review_session"
        )
        tree = ast.parse(inspect.getsource(module))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
        }
        allowed_modules = {
            "__future__",
            "dataclasses",
            "typing",
            "capture_import.workflow_ocr_conflict_resolution",
            "capture_import.workflow_ocr_consolidation",
            "capture_import.workflow_ocr_final_projection",
            "capture_import.workflow_ocr_models",
            "capture_import.workflow_ocr_review_models",
            "capture_import.workflow_ocr_review_service",
        }

        self.assertEqual(imported_modules, allowed_modules)


if __name__ == "__main__":
    unittest.main()
