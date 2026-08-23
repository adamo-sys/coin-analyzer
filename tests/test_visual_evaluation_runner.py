from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from capture_import.visual_evaluation_harness import load_visual_manifest
from capture_import.visual_evaluation_runner import (
    render_visual_summary,
    retention_results,
    run_visual_benchmark,
)
from capture_import.visual_identity_provider import (
    VisualIdentityCandidate,
    VisualIdentityMalformedOutput,
    VisualIdentityReport,
)


class _Clock:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


class _Provider:
    provider_id = "fake-visual"
    model_id = "gpt-5.6-terra"
    configuration = {"fixed": True}

    def __init__(
        self,
        *,
        country: str = "United States of America",
        denomination: str = "Half Dollar",
        year: str = "1935",
        type_design: str = "Wrong commemorative",
        failure: Exception | None = None,
    ) -> None:
        self.failure = failure
        self.requests = []
        self.values = country, denomination, year, type_design

    def identify(self, request):
        self.requests.append(request)
        if self.failure:
            raise self.failure
        country, denomination, year, type_design = self.values
        candidate = VisualIdentityCandidate(
            rank=1,
            country=country,
            denomination=denomination,
            year=year,
            type_design=type_design,
            confidence=0.9,
            evidence_observations=("visible legends",),
            supporting_image_roles=("obverse", "reverse"),
            provider_id=self.provider_id,
            model_id=self.model_id,
        )
        return VisualIdentityReport(
            outcome="CANDIDATES",
            candidates=(candidate,),
            provider_id=self.provider_id,
            model_id=self.model_id,
            response_id="response-1",
            input_tokens=100,
            output_tokens=20,
            raw_structured_result={
                "outcome": "CANDIDATES",
                "candidates": [{"country": country, "denomination": denomination}],
            },
        )


class VisualEvaluationRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        full = load_visual_manifest(root / "benchmarks" / "v2" / "manifest.json")
        case = replace(
            full.cases[0],
            expected={
                "country": "United States",
                "denomination": "1/2 dollar",
                "year": "1935",
                "type_design": "Expected commemorative",
            },
        )
        cls.one_case_manifest = replace(full, version="test-prospective", cases=(case,))

    def test_runner_passes_only_two_role_tagged_images_to_provider(self) -> None:
        provider = _Provider()
        report = run_visual_benchmark(
            self.one_case_manifest,
            provider,
            clock=_Clock(1.0, 1.5),
            git_commit="abc123",
        )
        request = provider.requests[0]
        self.assertEqual(tuple(image.role for image in request.images), ("obverse", "reverse"))
        self.assertFalse(hasattr(request, "expected"))
        self.assertFalse(hasattr(request.images[0], "path"))
        self.assertEqual(report["git_commit"], "abc123")
        self.assertEqual(report["usage"]["input_tokens"], 100)

    def test_exact_scoring_remains_distinct_from_canonical_scoring(self) -> None:
        report = run_visual_benchmark(
            self.one_case_manifest,
            _Provider(),
            clock=_Clock(1.0, 1.2),
        )
        self.assertEqual(report["exact_metrics"]["country_accuracy"], 0.0)
        self.assertEqual(report["exact_metrics"]["denomination_accuracy"], 0.0)
        self.assertEqual(report["canonical_metrics"]["country_accuracy"], 1.0)
        self.assertEqual(report["canonical_metrics"]["denomination_accuracy"], 1.0)
        self.assertEqual(report["canonical_metrics"]["full_required_identity_accuracy"], 1.0)

    def test_runner_reports_selective_safety_without_treating_source_score_as_probability(self) -> None:
        report = run_visual_benchmark(
            self.one_case_manifest,
            _Provider(),
            clock=_Clock(1.0, 1.2),
        )

        row = report["cases"][0]
        self.assertNotIn("source_score", row["predictions"][0])
        self.assertEqual(row["ranked_candidates"][0]["source_score"], 0.9)
        self.assertEqual(
            row["ranked_candidates"][0]["source_score_semantics"],
            "uncalibrated_provider_source_score",
        )
        for metrics in (report["exact_metrics"], report["canonical_metrics"]):
            self.assertEqual(
                metrics["source_score_safety"]["semantics"],
                "uncalibrated_provider_source_score",
            )
            self.assertEqual(
                metrics["field_coverage"]["full_required_identity"], 1.0
            )
            self.assertEqual(
                metrics["source_score_safety"]["high_score_predictions"], 1
            )

        summary = render_visual_summary(report)
        self.assertIn("Exact high-source-score incomplete identities: 0", summary)
        self.assertIn("Exact high-source-score incorrect identities: 1", summary)
        self.assertIn("Exact high-source-score unsafe rate: 100.0%", summary)
        self.assertIn("Canonical high-source-score incomplete identities: 0", summary)
        self.assertIn("Canonical high-source-score incorrect identities: 0", summary)
        self.assertIn("Canonical high-source-score unsafe rate: 0.0%", summary)

    def test_raw_values_and_canonical_rule_provenance_are_preserved(self) -> None:
        report = run_visual_benchmark(
            self.one_case_manifest,
            _Provider(),
            clock=_Clock(1.0, 1.2),
        )
        row = report["cases"][0]
        canonical = row["canonicalized_predictions"][0]
        self.assertEqual(canonical["country"]["raw_value"], "United States of America")
        self.assertEqual(canonical["denomination"]["raw_value"], "Half Dollar")
        self.assertIn(
            "jurisdiction.official-long-name",
            canonical["country"]["normalization_rules"],
        )
        self.assertIn(
            "denomination.fraction-word.half",
            canonical["denomination"]["normalization_rules"],
        )
        self.assertEqual(
            row["raw_structured_provider_result"]["candidates"][0]["country"],
            "United States of America",
        )

    def test_historical_jurisdiction_is_not_repaired(self) -> None:
        report = run_visual_benchmark(
            self.one_case_manifest,
            _Provider(country="British India", denomination="1/2 dollar"),
            clock=_Clock(1.0, 1.2),
        )
        self.assertEqual(report["canonical_metrics"]["country_accuracy"], 0.0)
        country = report["cases"][0]["canonicalized_predictions"][0]["country"]
        self.assertEqual(country["status"], "UNMAPPED")
        self.assertIsNone(country["canonical_value"])

    def test_required_identity_match_reports_exact_type_design_label_difference(self) -> None:
        report = run_visual_benchmark(
            self.one_case_manifest,
            _Provider(),
            clock=_Clock(1.0, 1.2),
        )
        row = report["cases"][0]
        self.assertTrue(row["canonical_scores"]["full_required_identity"])
        self.assertEqual(row["type_design_label_result"], "LABEL_DIFFERS")
        self.assertTrue(
            row["required_identity_correct_but_type_design_label_differs"]
        )
        diagnostic = report["canonical_metrics"][
            "required_identity_correct_but_type_design_label_differs"
        ]
        self.assertEqual(diagnostic["count"], 1)

    def test_semantically_similar_type_text_still_counts_only_as_label_difference(self) -> None:
        manifest = replace(
            self.one_case_manifest,
            cases=(
                replace(
                    self.one_case_manifest.cases[0],
                    expected={
                        "country": "United States",
                        "denomination": "1/2 dollar",
                        "year": "1935",
                        "type_design": "Elizabeth II beaver",
                    },
                ),
            ),
        )
        report = run_visual_benchmark(
            manifest,
            _Provider(type_design="Elizabeth II Beaver reverse type"),
            clock=_Clock(1.0, 1.2),
        )
        row = report["cases"][0]
        self.assertEqual(row["type_design_label_result"], "LABEL_DIFFERS")
        self.assertNotIn("substantive", row["type_design_label_result"].casefold())

    def test_malformed_failure_preserves_raw_output_usage_and_cost(self) -> None:
        failure = VisualIdentityMalformedOutput("truncated")
        failure.raw_provider_output = '{"outcome":"CANDIDATES"'
        failure.response_id = "resp-malformed"
        failure.input_tokens = 1_000
        failure.output_tokens = 2_000
        report = run_visual_benchmark(
            self.one_case_manifest,
            _Provider(failure=failure),
            clock=_Clock(2.0, 2.25),
        )
        row = report["cases"][0]
        self.assertEqual(row["outcome"], "INFRASTRUCTURE_FAILURE")
        self.assertEqual(row["raw_structured_provider_result"], failure.raw_provider_output)
        self.assertEqual(row["input_tokens"], 1_000)
        self.assertEqual(row["output_tokens"], 2_000)
        self.assertAlmostEqual(row["estimated_cost_usd"], 0.026)

    def test_retention_thresholds_are_frozen_at_inclusive_boundaries(self) -> None:
        exact = {
            "infrastructure_failures": 0,
            "abstention_rate": 0.50,
            "latency": {"mean_seconds": 5.0},
        }
        canonical = {
            "country_accuracy": 0.75,
            "denomination_accuracy": 0.70,
            "full_required_identity_accuracy": 0.50,
        }
        self.assertTrue(all(retention_results(exact, canonical).values()))
        canonical["country_accuracy"] = 0.749
        self.assertFalse(retention_results(exact, canonical)["canonical_country_accuracy"])


if __name__ == "__main__":
    unittest.main()
