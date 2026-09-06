import unittest

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationAggregate,
    EvaluationCase,
    EvaluationCaseOutcome,
    EvaluationOutcomeClassification,
)
from capture_import.desktop_acceptance_ai_evaluation_batch import (
    DesktopAcceptanceAIEvaluationBatchReport,
    evaluate_desktop_acceptance_batch,
)
from capture_import.desktop_acceptance_scoring import DesktopAcceptanceResult


def _candidate_case(case_id: str) -> EvaluationCase:
    return EvaluationCase(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id=case_id,
        allowed_candidate_ids=("candidate:accepted",),
    )


def _cases() -> tuple[EvaluationCase, ...]:
    return (
        _candidate_case("case:abstain"),
        _candidate_case("case:identify"),
        _candidate_case("case:infra"),
        _candidate_case("case:unavailable"),
    )


def _results() -> tuple[DesktopAcceptanceResult, ...]:
    return (
        DesktopAcceptanceResult(
            case_id="case:abstain",
            observed_action="abstain",
            proposed_identity=None,
        ),
        DesktopAcceptanceResult(
            case_id="case:identify",
            observed_action="identify",
            proposed_identity={"country": "Canada"},
        ),
        DesktopAcceptanceResult(
            case_id="case:infra",
            observed_action="infrastructure_failure",
            proposed_identity=None,
        ),
        DesktopAcceptanceResult(
            case_id="case:unavailable",
            observed_action="unavailable",
            proposed_identity=None,
        ),
    )


class DesktopAcceptanceAIEvaluationBatchTests(unittest.TestCase):
    def test_batch_evaluates_and_aggregates_exact_frozen_set(self) -> None:
        report = evaluate_desktop_acceptance_batch(
            _cases(),
            _results(),
            candidate_ids_by_case={
                "case:identify": "candidate:accepted",
            },
        )

        self.assertEqual(
            tuple(outcome.case_id for outcome in report.outcomes),
            (
                "case:abstain",
                "case:identify",
                "case:infra",
                "case:unavailable",
            ),
        )
        self.assertEqual(
            tuple(
                outcome.classification
                for outcome in report.outcomes
            ),
            (
                EvaluationOutcomeClassification.ABSTAINED,
                EvaluationOutcomeClassification.CORRECT,
                EvaluationOutcomeClassification.INVALID_OR_MISSING,
                EvaluationOutcomeClassification.INVALID_OR_MISSING,
            ),
        )
        self.assertEqual(
            report.aggregate,
            EvaluationAggregate(
                total=4,
                correct=1,
                incorrect=0,
                abstained=1,
                invalid_or_missing=2,
            ),
        )

    def test_batch_preserves_specialized_missing_reasons(self) -> None:
        report = evaluate_desktop_acceptance_batch(
            _cases(),
            _results(),
            candidate_ids_by_case={
                "case:identify": "candidate:accepted",
            },
        )

        by_id = {
            outcome.case_id: outcome
            for outcome in report.outcomes
        }

        self.assertEqual(
            by_id["case:infra"].reason_codes,
            ("infrastructure_failure",),
        )
        self.assertEqual(
            by_id["case:unavailable"].reason_codes,
            ("provider_unavailable",),
        )

    def test_batch_preserves_explicit_evidence_refs(self) -> None:
        report = evaluate_desktop_acceptance_batch(
            _cases(),
            _results(),
            candidate_ids_by_case={
                "case:identify": "candidate:accepted",
            },
            evidence_refs_by_case={
                "case:identify": ("ref:identify",),
                "case:infra": ("ref:infra",),
            },
        )

        by_id = {
            outcome.case_id: outcome
            for outcome in report.outcomes
        }

        self.assertEqual(
            by_id["case:identify"].evidence_refs,
            ("ref:identify",),
        )
        self.assertEqual(
            by_id["case:infra"].evidence_refs,
            ("ref:infra",),
        )

    def test_missing_candidate_mapping_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing"):
            evaluate_desktop_acceptance_batch(
                _cases(),
                _results(),
                candidate_ids_by_case={},
            )

    def test_extra_candidate_mapping_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "extra"):
            evaluate_desktop_acceptance_batch(
                _cases(),
                _results(),
                candidate_ids_by_case={
                    "case:identify": "candidate:accepted",
                    "case:infra": "candidate:forbidden",
                },
            )

    def test_unknown_evidence_case_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown"):
            evaluate_desktop_acceptance_batch(
                _cases(),
                _results(),
                candidate_ids_by_case={
                    "case:identify": "candidate:accepted",
                },
                evidence_refs_by_case={
                    "case:unknown": ("ref:unknown",),
                },
            )

    def test_missing_result_case_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "same ordered case IDs"):
            evaluate_desktop_acceptance_batch(
                _cases(),
                _results()[:-1],
                candidate_ids_by_case={
                    "case:identify": "candidate:accepted",
                },
            )

    def test_unsorted_cases_fail_closed(self) -> None:
        cases = _cases()

        with self.assertRaisesRegex(ValueError, "case IDs must be sorted"):
            evaluate_desktop_acceptance_batch(
                (cases[1], cases[0], cases[2], cases[3]),
                _results(),
                candidate_ids_by_case={
                    "case:identify": "candidate:accepted",
                },
            )

    def test_unsorted_results_fail_closed(self) -> None:
        results = _results()

        with self.assertRaisesRegex(
            ValueError,
            "result IDs must be sorted",
        ):
            evaluate_desktop_acceptance_batch(
                _cases(),
                (results[1], results[0], results[2], results[3]),
                candidate_ids_by_case={
                    "case:identify": "candidate:accepted",
                },
            )

    def test_invalid_authoritative_case_fails_closed(self) -> None:
        invalid = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:abstain",
        )
        cases = (
            invalid,
            _candidate_case("case:identify"),
            _candidate_case("case:infra"),
            _candidate_case("case:unavailable"),
        )

        with self.assertRaises(ValueError):
            evaluate_desktop_acceptance_batch(
                cases,
                _results(),
                candidate_ids_by_case={
                    "case:identify": "candidate:accepted",
                },
            )

    def test_batch_is_deterministic(self) -> None:
        kwargs = {
            "candidate_ids_by_case": {
                "case:identify": "candidate:accepted",
            }
        }

        first = evaluate_desktop_acceptance_batch(
            _cases(),
            _results(),
            **kwargs,
        )
        second = evaluate_desktop_acceptance_batch(
            _cases(),
            _results(),
            **kwargs,
        )

        self.assertEqual(first, second)

    def test_report_rejects_mismatched_aggregate(self) -> None:
        outcome = EvaluationCaseOutcome(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:001",
            classification=EvaluationOutcomeClassification.ABSTAINED,
        )
        report = DesktopAcceptanceAIEvaluationBatchReport(
            outcomes=(outcome,),
            aggregate=EvaluationAggregate(
                total=1,
                correct=1,
                incorrect=0,
                abstained=0,
                invalid_or_missing=0,
            ),
        )

        with self.assertRaisesRegex(ValueError, "aggregate"):
            report.validate()


if __name__ == "__main__":
    unittest.main()
