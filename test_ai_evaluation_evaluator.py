import unittest

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationCase,
    EvaluationOutcomeClassification,
    ObservedEvaluationResult,
)
from ai_evaluation_evaluator import evaluate_observed_result


def _candidate_case() -> EvaluationCase:
    return EvaluationCase(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id="case:001",
        allowed_candidate_ids=("candidate:accepted",),
        evidence_refs=("ref:case",),
    )


class AIEvaluationEvaluatorTests(unittest.TestCase):
    def test_allowed_candidate_is_correct(self) -> None:
        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:001",
            candidate_id="candidate:accepted",
            evidence_refs=("ref:observed",),
        )

        outcome = evaluate_observed_result(_candidate_case(), observed)

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.CORRECT,
        )
        self.assertEqual(
            outcome.observed_candidate_id,
            "candidate:accepted",
        )
        self.assertEqual(outcome.evidence_refs, ("ref:observed",))
        self.assertEqual(outcome.reason_codes, ())

    def test_unlisted_candidate_is_incorrect(self) -> None:
        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:001",
            candidate_id="candidate:other",
        )

        outcome = evaluate_observed_result(_candidate_case(), observed)

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )
        self.assertEqual(
            outcome.observed_candidate_id,
            "candidate:other",
        )
        self.assertEqual(
            outcome.reason_codes,
            ("candidate_not_allowed",),
        )

    def test_explicit_abstention_remains_distinct(self) -> None:
        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:001",
            abstained=True,
            evidence_refs=("ref:abstention",),
        )

        outcome = evaluate_observed_result(_candidate_case(), observed)

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.ABSTAINED,
        )
        self.assertIsNone(outcome.observed_candidate_id)
        self.assertEqual(
            outcome.evidence_refs,
            ("ref:abstention",),
        )

    def test_required_abstention_is_still_explicit_abstention(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:abstain",
            require_abstention=True,
        )
        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:abstain",
            abstained=True,
        )

        outcome = evaluate_observed_result(case, observed)

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.ABSTAINED,
        )

    def test_candidate_on_required_abstention_case_is_incorrect(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:abstain",
            require_abstention=True,
        )
        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:abstain",
            candidate_id="candidate:guess",
        )

        outcome = evaluate_observed_result(case, observed)

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )
        self.assertEqual(
            outcome.reason_codes,
            ("candidate_not_allowed",),
        )

    def test_missing_result_is_invalid_or_missing(self) -> None:
        outcome = evaluate_observed_result(_candidate_case(), None)

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.INVALID_OR_MISSING,
        )
        self.assertEqual(
            outcome.reason_codes,
            ("missing_observed_result",),
        )
        self.assertIsNone(outcome.observed_candidate_id)

    def test_invalid_observed_result_is_classified_explicitly(self) -> None:
        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:001",
        )

        outcome = evaluate_observed_result(_candidate_case(), observed)

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.INVALID_OR_MISSING,
        )
        self.assertEqual(
            outcome.reason_codes,
            ("invalid_observed_result",),
        )

    def test_case_identity_mismatch_fails_closed(self) -> None:
        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:other",
            candidate_id="candidate:accepted",
        )

        with self.assertRaisesRegex(ValueError, "case_id"):
            evaluate_observed_result(_candidate_case(), observed)

    def test_invalid_authoritative_case_is_not_reinterpreted(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:invalid",
        )

        with self.assertRaises(ValueError):
            evaluate_observed_result(case, None)

    def test_evaluation_is_deterministic_and_non_mutating(self) -> None:
        case = _candidate_case()
        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:001",
            candidate_id="candidate:accepted",
            evidence_refs=("ref:observed",),
        )

        first = evaluate_observed_result(case, observed)
        second = evaluate_observed_result(case, observed)

        self.assertEqual(first, second)
        self.assertEqual(
            observed.evidence_refs,
            ("ref:observed",),
        )


if __name__ == "__main__":
    unittest.main()