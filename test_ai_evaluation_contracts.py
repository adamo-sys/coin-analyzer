import unittest

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationAggregate,
    EvaluationCase,
    EvaluationCaseOutcome,
    EvaluationOutcomeClassification,
    ObservedEvaluationResult,
    aggregate_evaluation_outcomes,
)


class AIEvaluationContractsTests(unittest.TestCase):
    def test_valid_case_preserves_authoritative_ids(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:001",
            allowed_candidate_ids=("candidate:1858-10c",),
            evidence_refs=("ref:ocr:001", "ref:reverse:001"),
        )

        case.validate()

        self.assertEqual(case.case_id, "case:001")
        self.assertEqual(
            case.allowed_candidate_ids,
            ("candidate:1858-10c",),
        )
        self.assertEqual(
            case.evidence_refs,
            ("ref:ocr:001", "ref:reverse:001"),
        )

    def test_valid_correct_outcome(self) -> None:
        outcome = EvaluationCaseOutcome(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:002",
            classification=EvaluationOutcomeClassification.CORRECT,
            observed_candidate_id="candidate:correct",
        )

        outcome.validate()

    def test_valid_incorrect_outcome(self) -> None:
        outcome = EvaluationCaseOutcome(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:003",
            classification=EvaluationOutcomeClassification.INCORRECT,
            observed_candidate_id="candidate:wrong",
            reason_codes=("candidate_mismatch",),
        )

        outcome.validate()

    def test_explicit_abstention_is_distinct(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:004",
            require_abstention=True,
        )
        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:004",
            abstained=True,
        )
        outcome = EvaluationCaseOutcome(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:004",
            classification=EvaluationOutcomeClassification.ABSTAINED,
        )

        case.validate()
        observed.validate()
        outcome.validate()

        self.assertIsNone(observed.candidate_id)
        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.ABSTAINED,
        )

    def test_invalid_or_missing_is_distinct_from_incorrect(self) -> None:
        outcome = EvaluationCaseOutcome(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:005",
            classification=(
                EvaluationOutcomeClassification.INVALID_OR_MISSING
            ),
            reason_codes=("missing_output",),
        )

        outcome.validate()

        self.assertNotEqual(
            outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )

    def test_non_abstention_case_requires_candidate_truth(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:006",
        )

        with self.assertRaises(ValueError):
            case.validate()

    def test_abstention_case_rejects_allowed_candidate(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:007",
            allowed_candidate_ids=("candidate:one",),
            require_abstention=True,
        )

        with self.assertRaises(ValueError):
            case.validate()

    def test_observed_result_rejects_missing_candidate(self) -> None:
        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:008",
        )

        with self.assertRaises(ValueError):
            observed.validate()

    def test_observed_result_rejects_candidate_and_abstention(self) -> None:
        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:009",
            candidate_id="candidate:one",
            abstained=True,
        )

        with self.assertRaises(ValueError):
            observed.validate()

    def test_invalid_or_missing_requires_reason_code(self) -> None:
        outcome = EvaluationCaseOutcome(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:010",
            classification=(
                EvaluationOutcomeClassification.INVALID_OR_MISSING
            ),
        )

        with self.assertRaises(ValueError):
            outcome.validate()

    def test_rejects_empty_case_identity(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="",
            allowed_candidate_ids=("candidate:one",),
        )

        with self.assertRaises(ValueError):
            case.validate()

    def test_rejects_duplicate_candidate_ids(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:011",
            allowed_candidate_ids=("candidate:a", "candidate:a"),
        )

        with self.assertRaises(ValueError):
            case.validate()

    def test_rejects_unsorted_evidence_refs(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:012",
            allowed_candidate_ids=("candidate:one",),
            evidence_refs=("ref:z", "ref:a"),
        )

        with self.assertRaises(ValueError):
            case.validate()

    def test_rejects_duplicate_evidence_refs(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:013",
            allowed_candidate_ids=("candidate:one",),
            evidence_refs=("ref:a", "ref:a"),
        )

        with self.assertRaises(ValueError):
            case.validate()

    def test_rejects_unsupported_schema(self) -> None:
        case = EvaluationCase(
            schema_version="999",
            case_id="case:014",
            allowed_candidate_ids=("candidate:one",),
        )

        with self.assertRaises(ValueError):
            case.validate()

    def test_aggregate_counts_are_deterministic(self) -> None:
        outcomes = (
            EvaluationCaseOutcome(
                schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
                case_id="case:a",
                classification=EvaluationOutcomeClassification.CORRECT,
                observed_candidate_id="candidate:a",
            ),
            EvaluationCaseOutcome(
                schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
                case_id="case:b",
                classification=EvaluationOutcomeClassification.INCORRECT,
                observed_candidate_id="candidate:x",
            ),
            EvaluationCaseOutcome(
                schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
                case_id="case:c",
                classification=EvaluationOutcomeClassification.ABSTAINED,
            ),
            EvaluationCaseOutcome(
                schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
                case_id="case:d",
                classification=(
                    EvaluationOutcomeClassification.INVALID_OR_MISSING
                ),
                reason_codes=("missing_output",),
            ),
        )

        aggregate = aggregate_evaluation_outcomes(outcomes)

        self.assertEqual(
            aggregate,
            EvaluationAggregate(
                total=4,
                correct=1,
                incorrect=1,
                abstained=1,
                invalid_or_missing=1,
            ),
        )

    def test_aggregate_rejects_duplicate_case_identity(self) -> None:
        outcomes = (
            EvaluationCaseOutcome(
                schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
                case_id="case:duplicate",
                classification=EvaluationOutcomeClassification.CORRECT,
                observed_candidate_id="candidate:a",
            ),
            EvaluationCaseOutcome(
                schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
                case_id="case:duplicate",
                classification=EvaluationOutcomeClassification.INCORRECT,
                observed_candidate_id="candidate:b",
            ),
        )

        with self.assertRaises(ValueError):
            aggregate_evaluation_outcomes(outcomes)

    def test_aggregate_requires_counts_to_sum_to_total(self) -> None:
        aggregate = EvaluationAggregate(
            total=4,
            correct=1,
            incorrect=1,
            abstained=1,
            invalid_or_missing=0,
        )

        with self.assertRaises(ValueError):
            aggregate.validate()


if __name__ == "__main__":
    unittest.main()
