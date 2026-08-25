"""Focused tests for the standalone local LLM resolver benchmark runner."""

from __future__ import annotations

import json
import unittest

from capture_import.local_llm_resolver import LocalLLMResolver, ResolverEvidence
from capture_import.local_llm_resolver_benchmark import (
    ResolverBenchmarkCase,
    run_local_resolver_benchmark,
)


class _FakeRuntime:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []

    def invoke(self, request_json: str) -> str:
        self.calls.append(request_json)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response  # type: ignore[return-value]


def _response(
    *,
    country: str | None = "Canada",
    denomination: str | None = "10 cents",
    year: str | None = "1937",
    abstain: bool = False,
) -> str:
    return json.dumps(
        {
            "country": country,
            "denomination": denomination,
            "year": year,
            "candidate_id": None,
            "confidence": None,
            "reason": "fixture",
            "abstain": abstain,
        }
    )


def _case(case_id: str = "case-1", *, certain: bool = True) -> ResolverBenchmarkCase:
    return ResolverBenchmarkCase(
        case_id=case_id,
        evidence=ResolverEvidence(
            ocr_text=("CANADA", "10 CENTS", "1937"),
            candidate_countries=("Canada",),
            candidate_denominations=("10 cents",),
            candidate_years=("1937", "1957"),
        ),
        expected={"country": "Canada", "denomination": "10 cents", "year": "1937"},
        identity_certain=certain,
    )


class LocalLLMResolverBenchmarkTests(unittest.TestCase):
    def test_runner_records_result_latency_and_metrics(self) -> None:
        runtime = _FakeRuntime([_response()])
        resolver = LocalLLMResolver(runtime, enabled=True)
        ticks = iter((10.0, 10.25))

        report = run_local_resolver_benchmark([_case()], resolver=resolver, clock=lambda: next(ticks))

        self.assertEqual(report["schema"], "coin-analyzer-local-resolver-benchmark-v1")
        self.assertEqual(len(report["rows"]), 1)
        row = report["rows"][0]
        self.assertEqual(row["case_id"], "case-1")
        self.assertEqual(row["latency_seconds"], 0.25)
        self.assertIsNone(row["resolver_failure"])
        self.assertEqual(row["result"].year, "1937")
        self.assertEqual(report["metrics"]["full_identity_accuracy"], 1.0)
        self.assertEqual(report["metrics"]["false_positive_rate"], 0.0)

    def test_expected_identity_is_not_sent_to_runtime(self) -> None:
        runtime = _FakeRuntime([_response()])
        resolver = LocalLLMResolver(runtime, enabled=True)
        ticks = iter((0.0, 0.1))

        run_local_resolver_benchmark([_case()], resolver=resolver, clock=lambda: next(ticks))

        request = json.loads(runtime.calls[0])
        self.assertNotIn("expected", request)
        self.assertNotIn("ground_truth", request)
        self.assertEqual(request["evidence"]["candidate_years"], ["1937", "1957"])

    def test_runtime_failure_is_recorded_and_scored_unresolved(self) -> None:
        runtime = _FakeRuntime([TimeoutError("timed out")])
        resolver = LocalLLMResolver(runtime, enabled=True)
        ticks = iter((1.0, 1.75))

        report = run_local_resolver_benchmark([_case()], resolver=resolver, clock=lambda: next(ticks))

        row = report["rows"][0]
        self.assertIsNone(row["result"])
        self.assertEqual(row["resolver_failure"]["type"], "LocalResolverRuntimeError")
        self.assertEqual(row["latency_seconds"], 0.75)
        self.assertEqual(report["metrics"]["resolver_failures"], 1)
        self.assertEqual(report["metrics"]["unresolved_rate"], 1.0)

    def test_abstention_and_wrong_answer_remain_distinct(self) -> None:
        runtime = _FakeRuntime([
            _response(country=None, denomination=None, year=None, abstain=True),
            _response(year="1957"),
        ])
        resolver = LocalLLMResolver(runtime, enabled=True)
        ticks = iter((0.0, 0.1, 0.1, 0.3))

        report = run_local_resolver_benchmark(
            [_case("abstain"), _case("wrong")],
            resolver=resolver,
            clock=lambda: next(ticks),
        )

        self.assertEqual(report["metrics"]["unresolved_rate"], 0.5)
        self.assertEqual(report["metrics"]["false_positive_rate"], 1.0)
        self.assertEqual(report["metrics"]["full_identity_accuracy"], 0.0)
        self.assertAlmostEqual(report["metrics"]["latency"]["mean_seconds"], 0.15)

    def test_uncertain_reference_is_executed_but_not_exact_scored(self) -> None:
        runtime = _FakeRuntime([_response(year="1957")])
        resolver = LocalLLMResolver(runtime, enabled=True)
        ticks = iter((2.0, 2.2))

        report = run_local_resolver_benchmark(
            [_case(certain=False)], resolver=resolver, clock=lambda: next(ticks)
        )

        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(report["metrics"]["certain_scored_cases"], 0)
        self.assertIsNone(report["metrics"]["full_identity_accuracy"])
        self.assertIsNone(report["metrics"]["false_positive_rate"])


if __name__ == "__main__":
    unittest.main()
