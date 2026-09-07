import unittest
from dataclasses import replace

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationCase,
    EvaluationOutcomeClassification,
)
from identification_specialist import (
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
    run_identification_specialist,
)
from identification_verification_evaluation_report import (
    IdentificationVerificationEvaluationReport,
    compare_identification_verification_and_evaluation,
)


CASE_ID = "case:specialist:001"


def _request(
    *,
    candidates: tuple[str, ...] = (
        "candidate:alpha",
        "candidate:beta",
    ),
    eligible: tuple[str, ...] = ("candidate:alpha",),
    evidence: tuple[str, ...] = (
        "ref:001",
        "ref:002",
    ),
) -> IdentificationSpecialistRequest:
    return IdentificationSpecialistRequest(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id=CASE_ID,
        candidate_ids=candidates,
        eligible_candidate_ids=eligible,
        evidence_refs=evidence,
    )


def _evaluation_case(
    *,
    allowed: tuple[str, ...] = ("candidate:alpha",),
    require_abstention: bool = False,
    evidence: tuple[str, ...] = (
        "ref:001",
        "ref:002",
    ),
    case_id: str = CASE_ID,
) -> EvaluationCase:
    return EvaluationCase(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id=case_id,
        allowed_candidate_ids=allowed,
        require_abstention=require_abstention,
        evidence_refs=evidence,
    )


class IdentificationVerificationEvaluationReportTests(unittest.TestCase):
    def test_policy_valid_and_evaluation_correct(self) -> None:
        request = _request(
            eligible=("candidate:alpha",)
        )
        result = run_identification_specialist(request)

        report = compare_identification_verification_and_evaluation(
            request,
            result,
            _evaluation_case(
                allowed=("candidate:alpha",)
            ),
        )

        self.assertTrue(report.verification.accepted)
        self.assertEqual(
            report.evaluation_outcome.classification,
            EvaluationOutcomeClassification.CORRECT,
        )

    def test_policy_valid_can_be_evaluation_incorrect(self) -> None:
        request = _request(
            eligible=("candidate:alpha",)
        )
        result = run_identification_specialist(request)

        report = compare_identification_verification_and_evaluation(
            request,
            result,
            _evaluation_case(
                allowed=("candidate:beta",)
            ),
        )

        self.assertTrue(report.verification.accepted)
        self.assertEqual(
            report.evaluation_outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )
        self.assertEqual(
            report.specialist_result.candidate_id,
            "candidate:alpha",
        )

    def test_verifier_rejection_can_be_evaluation_correct(self) -> None:
        request = _request(
            eligible=("candidate:alpha",)
        )

        # Structurally valid and caller-authorized, but violates the
        # deterministic specialist policy because beta is not the sole
        # eligible candidate.
        tampered = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=CASE_ID,
            candidate_id="candidate:beta",
            abstained=False,
            evidence_refs=request.evidence_refs,
        )

        report = compare_identification_verification_and_evaluation(
            request,
            tampered,
            _evaluation_case(
                allowed=("candidate:beta",)
            ),
        )

        self.assertFalse(report.verification.accepted)
        self.assertEqual(
            report.verification.reason_codes,
            ("candidate_does_not_match_sole_eligible",),
        )
        self.assertEqual(
            report.evaluation_outcome.classification,
            EvaluationOutcomeClassification.CORRECT,
        )

    def test_verifier_rejection_can_be_evaluation_incorrect(self) -> None:
        request = _request(
            eligible=("candidate:alpha",)
        )

        tampered = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=CASE_ID,
            candidate_id="candidate:beta",
            abstained=False,
            evidence_refs=request.evidence_refs,
        )

        report = compare_identification_verification_and_evaluation(
            request,
            tampered,
            _evaluation_case(
                allowed=("candidate:alpha",)
            ),
        )

        self.assertFalse(report.verification.accepted)
        self.assertEqual(
            report.evaluation_outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )

    def test_valid_required_abstention_remains_explicit(self) -> None:
        request = _request(
            eligible=()
        )
        result = run_identification_specialist(request)

        report = compare_identification_verification_and_evaluation(
            request,
            result,
            _evaluation_case(
                allowed=(),
                require_abstention=True,
            ),
        )

        self.assertTrue(report.verification.accepted)
        self.assertTrue(report.specialist_result.abstained)
        self.assertEqual(
            report.evaluation_outcome.classification,
            EvaluationOutcomeClassification.ABSTAINED,
        )

    def test_policy_valid_abstention_can_differ_from_evaluation_expectation(
        self,
    ) -> None:
        request = _request(
            eligible=()
        )
        result = run_identification_specialist(request)

        report = compare_identification_verification_and_evaluation(
            request,
            result,
            _evaluation_case(
                allowed=("candidate:alpha",),
                require_abstention=False,
            ),
        )

        self.assertTrue(report.verification.accepted)
        self.assertEqual(
            report.evaluation_outcome.classification,
            EvaluationOutcomeClassification.ABSTAINED,
        )

    def test_specialist_result_is_preserved_exactly(self) -> None:
        request = _request()
        result = run_identification_specialist(request)

        report = compare_identification_verification_and_evaluation(
            request,
            result,
            _evaluation_case(),
        )

        self.assertIs(report.specialist_result, result)
        self.assertEqual(report.specialist_result, result)

    def test_evidence_refs_are_preserved_exactly(self) -> None:
        evidence = (
            "ref:ocr:001",
            "ref:photo:002",
        )

        request = _request(evidence=evidence)
        result = run_identification_specialist(request)

        report = compare_identification_verification_and_evaluation(
            request,
            result,
            _evaluation_case(evidence=evidence),
        )

        self.assertEqual(
            report.specialist_result.evidence_refs,
            evidence,
        )

    def test_authoritative_and_observed_candidate_ids_remain_separate(
        self,
    ) -> None:
        request = _request(
            eligible=("candidate:alpha",)
        )
        result = run_identification_specialist(request)

        evaluation_case = _evaluation_case(
            allowed=("candidate:beta",)
        )

        report = compare_identification_verification_and_evaluation(
            request,
            result,
            evaluation_case,
        )

        self.assertEqual(
            result.candidate_id,
            "candidate:alpha",
        )
        self.assertEqual(
            evaluation_case.allowed_candidate_ids,
            ("candidate:beta",),
        )
        self.assertEqual(
            report.evaluation_outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )

    def test_request_evaluation_case_id_mismatch_fails_closed(self) -> None:
        request = _request()
        result = run_identification_specialist(request)

        with self.assertRaisesRegex(
            ValueError,
            "evaluation_case case_id must match request",
        ):
            compare_identification_verification_and_evaluation(
                request,
                result,
                _evaluation_case(
                    case_id="case:specialist:999",
                ),
            )

    def test_result_evaluation_case_id_mismatch_fails_closed(self) -> None:
        request = _request()
        result = run_identification_specialist(request)
        tampered = replace(
            result,
            case_id="case:specialist:999",
        )

        with self.assertRaisesRegex(
            ValueError,
            "evaluation_case case_id must match result",
        ):
            compare_identification_verification_and_evaluation(
                request,
                tampered,
                _evaluation_case(),
            )

    def test_wrong_request_type_fails_closed(self) -> None:
        request = _request()
        result = run_identification_specialist(request)

        with self.assertRaises(TypeError):
            compare_identification_verification_and_evaluation(
                object(),  # type: ignore[arg-type]
                result,
                _evaluation_case(),
            )

    def test_wrong_result_type_fails_closed(self) -> None:
        request = _request()

        with self.assertRaises(TypeError):
            compare_identification_verification_and_evaluation(
                request,
                object(),  # type: ignore[arg-type]
                _evaluation_case(),
            )

    def test_wrong_evaluation_case_type_fails_closed(self) -> None:
        request = _request()
        result = run_identification_specialist(request)

        with self.assertRaises(TypeError):
            compare_identification_verification_and_evaluation(
                request,
                result,
                object(),  # type: ignore[arg-type]
            )

    def test_malformed_request_fails_closed(self) -> None:
        request = _request(
            candidates=(
                "candidate:beta",
                "candidate:alpha",
            ),
            eligible=("candidate:alpha",),
        )

        result = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=CASE_ID,
            candidate_id="candidate:alpha",
            abstained=False,
            evidence_refs=(
                "ref:001",
                "ref:002",
            ),
        )

        with self.assertRaises(ValueError):
            compare_identification_verification_and_evaluation(
                request,
                result,
                _evaluation_case(),
            )

    def test_malformed_result_fails_closed(self) -> None:
        request = _request()

        invalid = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=CASE_ID,
            candidate_id="candidate:alpha",
            abstained=True,
            evidence_refs=request.evidence_refs,
        )

        with self.assertRaises(ValueError):
            compare_identification_verification_and_evaluation(
                request,
                invalid,
                _evaluation_case(),
            )

    def test_inputs_are_not_mutated(self) -> None:
        request = _request()
        result = run_identification_specialist(request)
        evaluation_case = _evaluation_case()

        request_before = request
        result_before = result
        evaluation_case_before = evaluation_case

        compare_identification_verification_and_evaluation(
            request,
            result,
            evaluation_case,
        )

        self.assertEqual(request, request_before)
        self.assertEqual(result, result_before)
        self.assertEqual(evaluation_case, evaluation_case_before)

    def test_comparison_is_deterministic(self) -> None:
        request = _request()
        result = run_identification_specialist(request)
        evaluation_case = _evaluation_case()

        first = compare_identification_verification_and_evaluation(
            request,
            result,
            evaluation_case,
        )
        second = compare_identification_verification_and_evaluation(
            request,
            result,
            evaluation_case,
        )

        self.assertEqual(first, second)

    def test_report_validation_rejects_wrong_specialist_type(self) -> None:
        request = _request()
        result = run_identification_specialist(request)

        valid = compare_identification_verification_and_evaluation(
            request,
            result,
            _evaluation_case(),
        )

        invalid = IdentificationVerificationEvaluationReport(
            specialist_result=object(),  # type: ignore[arg-type]
            verification=valid.verification,
            evaluation_outcome=valid.evaluation_outcome,
        )

        with self.assertRaises(TypeError):
            invalid.validate()

    def test_report_validation_rejects_wrong_verification_type(self) -> None:
        request = _request()
        result = run_identification_specialist(request)

        valid = compare_identification_verification_and_evaluation(
            request,
            result,
            _evaluation_case(),
        )

        invalid = IdentificationVerificationEvaluationReport(
            specialist_result=result,
            verification=object(),  # type: ignore[arg-type]
            evaluation_outcome=valid.evaluation_outcome,
        )

        with self.assertRaises(TypeError):
            invalid.validate()

    def test_report_validation_rejects_wrong_outcome_type(self) -> None:
        request = _request()
        result = run_identification_specialist(request)

        valid = compare_identification_verification_and_evaluation(
            request,
            result,
            _evaluation_case(),
        )

        invalid = IdentificationVerificationEvaluationReport(
            specialist_result=result,
            verification=valid.verification,
            evaluation_outcome=object(),  # type: ignore[arg-type]
        )

        with self.assertRaises(TypeError):
            invalid.validate()


if __name__ == "__main__":
    unittest.main()
