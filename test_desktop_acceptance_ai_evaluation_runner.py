import unittest
from pathlib import Path

from ai_evaluation_contracts import (
    EvaluationAggregate,
    EvaluationOutcomeClassification,
)
from capture_import.desktop_acceptance_ai_evaluation_runner import (
    evaluate_desktop_acceptance_manifest_results,
)
from capture_import.desktop_acceptance_scoring import DesktopAcceptanceResult
from capture_import.desktop_acceptance_set import (
    DesktopAcceptanceCase,
    DesktopAcceptanceManifest,
)


def _manifest_case(
    case_id: str,
    expected_action: str,
) -> DesktopAcceptanceCase:
    return DesktopAcceptanceCase(
        case_id=case_id,
        specimen_id=f"specimen-{case_id[-3:]}",
        repeated_case_id=None,
        expected_action=expected_action,
        expected_identity={},
        reserved_attribution={},
        capture_conditions={},
        capture_difference_fields=None,
        capture_difference_rationale=None,
        cohorts=("synthetic",),
        stability=False,
        privacy_classification="synthetic",
        prior_benchmark_use={},
        ground_truth_review={},
        action_review={},
        images=(),
        notes="synthetic runner test",
    )


def _manifest() -> DesktopAcceptanceManifest:
    return DesktopAcceptanceManifest(
        root=Path("."),
        cases=(
            _manifest_case("case-001", "identify"),
            _manifest_case("case-002", "identify"),
            _manifest_case("case-003", "abstain"),
            _manifest_case("case-004", "identify"),
            _manifest_case("case-005", "identify"),
        ),
        canonicalization_policy={},
        freeze={},
        stability_relevant_cohorts=(),
    )


def _results() -> tuple[DesktopAcceptanceResult, ...]:
    return (
        DesktopAcceptanceResult(
            case_id="case-001",
            observed_action="identify",
            proposed_identity={"country": "Canada"},
        ),
        DesktopAcceptanceResult(
            case_id="case-002",
            observed_action="identify",
            proposed_identity={"country": "Canada"},
        ),
        DesktopAcceptanceResult(
            case_id="case-003",
            observed_action="abstain",
            proposed_identity=None,
        ),
        DesktopAcceptanceResult(
            case_id="case-004",
            observed_action="unavailable",
            proposed_identity=None,
        ),
        DesktopAcceptanceResult(
            case_id="case-005",
            observed_action="infrastructure_failure",
            proposed_identity=None,
        ),
    )


def _authoritative_ids() -> dict[str, str]:
    return {
        "case-001": "candidate:one",
        "case-002": "candidate:two",
        "case-004": "candidate:four",
        "case-005": "candidate:five",
    }


def _observed_ids() -> dict[str, str]:
    return {
        "case-001": "candidate:one",
        "case-002": "candidate:wrong",
    }


class DesktopAcceptanceAIEvaluationRunnerTests(unittest.TestCase):
    def test_runner_composes_manifest_and_results_end_to_end(self) -> None:
        report = evaluate_desktop_acceptance_manifest_results(
            _manifest(),
            _results(),
            authoritative_candidate_ids_by_case=_authoritative_ids(),
            observed_candidate_ids_by_case=_observed_ids(),
        )

        self.assertEqual(
            tuple(outcome.classification for outcome in report.outcomes),
            (
                EvaluationOutcomeClassification.CORRECT,
                EvaluationOutcomeClassification.INCORRECT,
                EvaluationOutcomeClassification.ABSTAINED,
                EvaluationOutcomeClassification.INVALID_OR_MISSING,
                EvaluationOutcomeClassification.INVALID_OR_MISSING,
            ),
        )

        self.assertEqual(
            report.aggregate,
            EvaluationAggregate(
                total=5,
                correct=1,
                incorrect=1,
                abstained=1,
                invalid_or_missing=2,
            ),
        )

    def test_expected_and_observed_candidate_ids_are_distinct(self) -> None:
        report = evaluate_desktop_acceptance_manifest_results(
            _manifest(),
            _results(),
            authoritative_candidate_ids_by_case=_authoritative_ids(),
            observed_candidate_ids_by_case={
                "case-001": "candidate:wrong",
                "case-002": "candidate:two",
            },
        )

        self.assertEqual(
            report.outcomes[0].classification,
            EvaluationOutcomeClassification.INCORRECT,
        )
        self.assertEqual(
            report.outcomes[1].classification,
            EvaluationOutcomeClassification.CORRECT,
        )

    def test_runner_does_not_reuse_authoritative_ids_as_observed_ids(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "missing"):
            evaluate_desktop_acceptance_manifest_results(
                _manifest(),
                _results(),
                authoritative_candidate_ids_by_case=_authoritative_ids(),
                observed_candidate_ids_by_case={},
            )

    def test_runner_preserves_provider_unavailable_reason(self) -> None:
        report = evaluate_desktop_acceptance_manifest_results(
            _manifest(),
            _results(),
            authoritative_candidate_ids_by_case=_authoritative_ids(),
            observed_candidate_ids_by_case=_observed_ids(),
        )

        self.assertEqual(
            report.outcomes[3].reason_codes,
            ("provider_unavailable",),
        )

    def test_runner_preserves_infrastructure_failure_reason(self) -> None:
        report = evaluate_desktop_acceptance_manifest_results(
            _manifest(),
            _results(),
            authoritative_candidate_ids_by_case=_authoritative_ids(),
            observed_candidate_ids_by_case=_observed_ids(),
        )

        self.assertEqual(
            report.outcomes[4].reason_codes,
            ("infrastructure_failure",),
        )

    def test_runner_preserves_evidence_refs(self) -> None:
        report = evaluate_desktop_acceptance_manifest_results(
            _manifest(),
            _results(),
            authoritative_candidate_ids_by_case=_authoritative_ids(),
            observed_candidate_ids_by_case=_observed_ids(),
            evidence_refs_by_case={
                "case-001": ("ref:one",),
                "case-004": ("ref:unavailable",),
            },
        )

        self.assertEqual(
            report.outcomes[0].evidence_refs,
            ("ref:one",),
        )
        self.assertEqual(
            report.outcomes[3].evidence_refs,
            ("ref:unavailable",),
        )

    def test_missing_authoritative_candidate_fails_closed(self) -> None:
        authoritative = _authoritative_ids()
        del authoritative["case-001"]

        with self.assertRaisesRegex(ValueError, "missing"):
            evaluate_desktop_acceptance_manifest_results(
                _manifest(),
                _results(),
                authoritative_candidate_ids_by_case=authoritative,
                observed_candidate_ids_by_case=_observed_ids(),
            )

    def test_extra_authoritative_candidate_fails_closed(self) -> None:
        authoritative = _authoritative_ids()
        authoritative["case-999"] = "candidate:extra"

        with self.assertRaisesRegex(ValueError, "extra"):
            evaluate_desktop_acceptance_manifest_results(
                _manifest(),
                _results(),
                authoritative_candidate_ids_by_case=authoritative,
                observed_candidate_ids_by_case=_observed_ids(),
            )

    def test_extra_observed_candidate_fails_closed(self) -> None:
        observed = _observed_ids()
        observed["case-003"] = "candidate:forbidden"

        with self.assertRaisesRegex(ValueError, "extra"):
            evaluate_desktop_acceptance_manifest_results(
                _manifest(),
                _results(),
                authoritative_candidate_ids_by_case=_authoritative_ids(),
                observed_candidate_ids_by_case=observed,
            )

    def test_result_case_mismatch_fails_closed(self) -> None:
        results = list(_results())
        results[4] = DesktopAcceptanceResult(
            case_id="case-999",
            observed_action="infrastructure_failure",
            proposed_identity=None,
        )

        with self.assertRaisesRegex(ValueError, "same ordered case IDs"):
            evaluate_desktop_acceptance_manifest_results(
                _manifest(),
                tuple(results),
                authoritative_candidate_ids_by_case=_authoritative_ids(),
                observed_candidate_ids_by_case=_observed_ids(),
            )

    def test_runner_is_deterministic(self) -> None:
        first = evaluate_desktop_acceptance_manifest_results(
            _manifest(),
            _results(),
            authoritative_candidate_ids_by_case=_authoritative_ids(),
            observed_candidate_ids_by_case=_observed_ids(),
        )
        second = evaluate_desktop_acceptance_manifest_results(
            _manifest(),
            _results(),
            authoritative_candidate_ids_by_case=_authoritative_ids(),
            observed_candidate_ids_by_case=_observed_ids(),
        )

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
