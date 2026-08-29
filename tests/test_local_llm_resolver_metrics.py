"""Focused tests for standalone local LLM resolver scoring."""

from __future__ import annotations

import unittest

from capture_import.local_llm_resolver import ResolverResult
from capture_import.local_llm_resolver_metrics import score_local_resolver_results


def _result(
    *,
    country: str | None = "Canada",
    denomination: str | None = "10 cents",
    year: str | None = "1937",
    abstain: bool = False,
) -> ResolverResult:
    return ResolverResult(
        country=country,
        denomination=denomination,
        year=year,
        candidate_id=None,
        confidence=None,
        reason="test fixture",
        abstain=abstain,
    )


def _row(
    result: ResolverResult | None,
    *,
    certain: bool = True,
    failure: object = None,
    latency: float | None = 1.0,
    expected: dict[str, str] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "expected": expected
        or {"country": "Canada", "denomination": "10 cents", "year": "1937"},
        "identity_certain": certain,
        "result": result,
        "resolver_failure": failure,
    }
    if latency is not None:
        row["latency_seconds"] = latency
    return row


class LocalLLMResolverMetricsTests(unittest.TestCase):
    def test_exact_accuracy_and_full_identity(self) -> None:
        metrics = score_local_resolver_results([_row(_result())])

        self.assertEqual(metrics["country_accuracy"], 1.0)
        self.assertEqual(metrics["denomination_accuracy"], 1.0)
        self.assertEqual(metrics["year_accuracy"], 1.0)
        self.assertEqual(metrics["full_identity_accuracy"], 1.0)
        self.assertEqual(metrics["false_positive_rate"], 0.0)

    def test_normalization_is_trimmed_case_insensitive_exact_matching(self) -> None:
        metrics = score_local_resolver_results(
            [_row(_result(country="  CANADA ", denomination="10   CENTS", year="1937"))]
        )

        self.assertEqual(metrics["full_identity_accuracy"], 1.0)

    def test_abstention_counts_unresolved_but_not_false_positive(self) -> None:
        metrics = score_local_resolver_results(
            [_row(_result(country=None, denomination=None, year=None, abstain=True))]
        )

        self.assertEqual(metrics["unresolved_rate"], 1.0)
        self.assertEqual(metrics["full_identity_accuracy"], 0.0)
        self.assertIsNone(metrics["false_positive_rate"])

    def test_incorrect_non_abstaining_result_is_false_positive(self) -> None:
        metrics = score_local_resolver_results([_row(_result(year="1957"))])

        self.assertEqual(metrics["country_accuracy"], 1.0)
        self.assertEqual(metrics["denomination_accuracy"], 1.0)
        self.assertEqual(metrics["year_accuracy"], 0.0)
        self.assertEqual(metrics["full_identity_accuracy"], 0.0)
        self.assertEqual(metrics["false_positive_rate"], 1.0)

    def test_uncertain_reference_is_excluded_from_accuracy_and_false_positive(self) -> None:
        metrics = score_local_resolver_results([_row(_result(year="1957"), certain=False)])

        self.assertEqual(metrics["certain_scored_cases"], 0)
        self.assertIsNone(metrics["country_accuracy"])
        self.assertIsNone(metrics["full_identity_accuracy"])
        self.assertIsNone(metrics["false_positive_rate"])

    def test_uncertain_case_metrics_reward_abstention_and_penalize_field_emission(self) -> None:
        metrics = score_local_resolver_results(
            [
                _row(
                    _result(country=None, denomination=None, year=None, abstain=True),
                    certain=False,
                ),
                _row(
                    _result(country="Canada", denomination=None, year=None, abstain=False),
                    certain=False,
                ),
            ]
        )

        self.assertEqual(metrics["uncertain_cases"], 2)
        self.assertEqual(metrics["uncertain_case_abstention_rate"], 0.5)
        self.assertEqual(metrics["uncertain_case_non_abstention_rate"], 0.5)
        self.assertAlmostEqual(metrics["unsupported_field_emission_rate"], 1 / 6)

    def test_runtime_failure_counts_failure_and_unresolved(self) -> None:
        metrics = score_local_resolver_results(
            [_row(None, failure={"type": "TimeoutError"}, latency=2.0)]
        )

        self.assertEqual(metrics["resolver_failures"], 1)
        self.assertEqual(metrics["unresolved_rate"], 1.0)
        self.assertEqual(metrics["full_identity_accuracy"], 0.0)

    def test_latency_reports_mean_median_and_nearest_rank_p95(self) -> None:
        rows = [
            _row(_result(), latency=0.1),
            _row(_result(), latency=0.2),
            _row(_result(), latency=0.3),
            _row(_result(), latency=0.4),
            _row(_result(), latency=1.0),
        ]

        latency = score_local_resolver_results(rows)["latency"]

        self.assertAlmostEqual(latency["mean_seconds"], 0.4)
        self.assertEqual(latency["median_seconds"], 0.3)
        self.assertEqual(latency["p95_seconds"], 1.0)

    def test_empty_input_has_no_fabricated_rates_or_latency(self) -> None:
        metrics = score_local_resolver_results([])

        self.assertEqual(metrics["total_cases"], 0)
        self.assertIsNone(metrics["country_accuracy"])
        self.assertIsNone(metrics["unresolved_rate"])
        self.assertIsNone(metrics["false_positive_rate"])
        self.assertIsNone(metrics["uncertain_case_abstention_rate"])
        self.assertIsNone(metrics["uncertain_case_non_abstention_rate"])
        self.assertIsNone(metrics["unsupported_field_emission_rate"])
        self.assertEqual(
            metrics["latency"],
            {"mean_seconds": None, "median_seconds": None, "p95_seconds": None},
        )


if __name__ == "__main__":
    unittest.main()
