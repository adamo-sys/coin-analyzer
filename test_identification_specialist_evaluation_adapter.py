import unittest

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationCase,
    EvaluationOutcomeClassification,
)
from ai_evaluation_evaluator import evaluate_observed_result
from identification_specialist import (
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
    run_identification_specialist,
)
from identification_specialist_evaluation_adapter import (
    adapt_identification_specialist_result,
)


def _evaluation_case() -> EvaluationCase:
    return EvaluationCase(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id="case:specialist:001",
        allowed_candidate_ids=("candidate:correct",),
        evidence_refs=("ref:001",),
    )


def _request(
    *,
    eligible: tuple[str, ...],
    evidence: tuple[str, ...] = ("ref:001",),
) -> IdentificationSpecialistRequest:
    return IdentificationSpecialistRequest(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id="case:specialist:001",
        candidate_ids=(
            "candidate:correct",
            "candidate:wrong",
        ),
        eligible_candidate_ids=eligible,
        evidence_refs=evidence,
    )


class IdentificationSpecialistEvaluationAdapterTests(unittest.TestCase):
    def test_correct_specialist_selection_evaluates_correct(self) -> None:
        result = run_identification_specialist(
            _request(eligible=("candidate:correct",))
        )

        observed = adapt_identification_specialist_result(result)
        outcome = evaluate_observed_result(
            _evaluation_case(),
            observed,
        )

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.CORRECT,
        )

    def test_wrong_specialist_selection_evaluates_incorrect(self) -> None:
        result = run_identification_specialist(
            _request(eligible=("candidate:wrong",))
        )

        observed = adapt_identification_specialist_result(result)
        outcome = evaluate_observed_result(
            _evaluation_case(),
            observed,
        )

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )
        self.assertEqual(
            outcome.reason_codes,
            ("candidate_not_allowed",),
        )

    def test_multiple_candidates_evaluate_as_explicit_abstention(self) -> None:
        result = run_identification_specialist(
            _request(
                eligible=(
                    "candidate:correct",
                    "candidate:wrong",
                )
            )
        )

        observed = adapt_identification_specialist_result(result)
        outcome = evaluate_observed_result(
            _evaluation_case(),
            observed,
        )

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.ABSTAINED,
        )

    def test_zero_candidates_evaluate_as_explicit_abstention(self) -> None:
        result = run_identification_specialist(
            _request(eligible=())
        )

        observed = adapt_identification_specialist_result(result)
        outcome = evaluate_observed_result(
            _evaluation_case(),
            observed,
        )

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.ABSTAINED,
        )

    def test_missing_result_remains_invalid_or_missing(self) -> None:
        outcome = evaluate_observed_result(
            _evaluation_case(),
            None,
        )

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.INVALID_OR_MISSING,
        )
        self.assertEqual(
            outcome.reason_codes,
            ("missing_observed_result",),
        )

    def test_authoritative_and_observed_ids_remain_separate(self) -> None:
        result = run_identification_specialist(
            _request(eligible=("candidate:wrong",))
        )

        observed = adapt_identification_specialist_result(result)

        self.assertEqual(
            _evaluation_case().allowed_candidate_ids,
            ("candidate:correct",),
        )
        self.assertEqual(
            observed.candidate_id,
            "candidate:wrong",
        )

        outcome = evaluate_observed_result(
            _evaluation_case(),
            observed,
        )

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )

    def test_adapter_preserves_case_identity(self) -> None:
        result = run_identification_specialist(
            _request(eligible=("candidate:correct",))
        )

        observed = adapt_identification_specialist_result(result)

        self.assertEqual(
            observed.case_id,
            "case:specialist:001",
        )

    def test_adapter_preserves_evidence_refs_exactly(self) -> None:
        evidence = (
            "ref:001",
            "ref:002",
        )

        result = run_identification_specialist(
            _request(
                eligible=("candidate:correct",),
                evidence=evidence,
            )
        )

        observed = adapt_identification_specialist_result(result)

        self.assertEqual(observed.evidence_refs, evidence)

    def test_abstention_evidence_refs_are_preserved(self) -> None:
        evidence = (
            "ref:001",
            "ref:002",
        )

        result = run_identification_specialist(
            _request(
                eligible=(),
                evidence=evidence,
            )
        )

        observed = adapt_identification_specialist_result(result)

        self.assertTrue(observed.abstained)
        self.assertEqual(observed.evidence_refs, evidence)

    def test_adapter_rejects_invalid_specialist_result(self) -> None:
        invalid = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:specialist:001",
            candidate_id="candidate:correct",
            abstained=True,
        )

        with self.assertRaises(ValueError):
            adapt_identification_specialist_result(invalid)

    def test_adapter_rejects_wrong_type(self) -> None:
        with self.assertRaises(TypeError):
            adapt_identification_specialist_result(
                object()  # type: ignore[arg-type]
            )

    def test_integration_is_deterministic(self) -> None:
        request = _request(
            eligible=("candidate:correct",)
        )

        first_result = run_identification_specialist(request)
        second_result = run_identification_specialist(request)

        first_observed = adapt_identification_specialist_result(
            first_result
        )
        second_observed = adapt_identification_specialist_result(
            second_result
        )

        first_outcome = evaluate_observed_result(
            _evaluation_case(),
            first_observed,
        )
        second_outcome = evaluate_observed_result(
            _evaluation_case(),
            second_observed,
        )

        self.assertEqual(first_result, second_result)
        self.assertEqual(first_observed, second_observed)
        self.assertEqual(first_outcome, second_outcome)


if __name__ == "__main__":
    unittest.main()
