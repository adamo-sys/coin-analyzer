"""Focused tests for the local resolver batch benchmark CLI."""

from __future__ import annotations

import json
import unittest

from capture_import.local_llm_resolver_batch_cli import (
    DEFAULT_MODELS,
    run_model_benchmarks,
    synthetic_cases,
)


class _Runtime:
    def __init__(self, *, model: str, timeout_seconds: float) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds

    def invoke(self, request_json: str) -> str:
        request = json.loads(request_json)
        evidence = request["evidence"]
        ocr = " ".join(evidence["ocr_text"])

        if self.model == "qwen-coin:latest" and "25 C?NTS" in ocr:
            denomination = "10 cents"
        elif "5 CENTS" in ocr:
            denomination = "5 cents"
        elif "25 C?NTS" in ocr:
            denomination = "25 cents"
        elif "10 CENTS" in ocr or "10 C?NTS" in ocr:
            denomination = "10 cents"
        else:
            denomination = None

        if "1957" in ocr:
            year = "1957"
        elif "1937" in ocr:
            year = "1937"
        elif "1967" in ocr:
            year = "1967"
        elif "1965" in ocr:
            year = "1965"
        else:
            year = None

        abstain = denomination is None or year is None
        return json.dumps(
            {
                "country": "Canada" if "CANAD" in ocr else None,
                "denomination": denomination,
                "year": year,
                "candidate_id": None,
                "confidence": None,
                "reason": "deterministic fixture",
                "abstain": abstain,
            }
        )


class LocalLLMResolverBatchCLITests(unittest.TestCase):
    def test_default_models_are_the_two_local_comparison_targets(self) -> None:
        self.assertEqual(DEFAULT_MODELS, ("qwen3:8b", "qwen-coin:latest"))

    def test_synthetic_cases_cover_certain_and_uncertain_inputs(self) -> None:
        cases = synthetic_cases()
        ids = {case.case_id for case in cases}

        self.assertEqual(len(cases), 6)
        self.assertIn("obvious-1937-10c", ids)
        self.assertIn("noisy-1967-25c", ids)
        self.assertIn("ambiguous-year-unknown", ids)
        self.assertIn("insufficient-evidence", ids)
        self.assertEqual(sum(case.identity_certain for case in cases), 4)

    def test_model_comparison_is_json_serializable_and_separate_per_model(self) -> None:
        output = run_model_benchmarks(
            DEFAULT_MODELS,
            timeout_seconds=120.0,
            runtime_factory=_Runtime,
        )

        encoded = json.dumps(output)
        self.assertIn("coin-analyzer-local-resolver-model-comparison-v1", encoded)
        self.assertEqual(set(output["models"]), set(DEFAULT_MODELS))

        qwen = output["models"]["qwen3:8b"]
        coin = output["models"]["qwen-coin:latest"]
        self.assertEqual(qwen["metrics"]["certain_scored_cases"], 4)
        self.assertEqual(qwen["metrics"]["full_identity_accuracy"], 1.0)
        self.assertLess(coin["metrics"]["full_identity_accuracy"], 1.0)

    def test_serialized_rows_do_not_expose_resolver_dataclass_objects(self) -> None:
        output = run_model_benchmarks(
            ("qwen3:8b",),
            timeout_seconds=30.0,
            runtime_factory=_Runtime,
        )

        rows = output["models"]["qwen3:8b"]["rows"]
        self.assertIsInstance(rows[0]["result"], dict)
        self.assertIn("abstain", rows[0]["result"])
        self.assertIsNone(rows[0]["result"]["confidence"])


if __name__ == "__main__":
    unittest.main()
