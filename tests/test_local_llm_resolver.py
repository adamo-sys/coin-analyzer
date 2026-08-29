"""Focused tests for the isolated local LLM resolver experiment."""

from __future__ import annotations

import json
import unittest

from capture_import.local_llm_resolver import (
    LocalLLMResolver,
    LocalResolverDisabled,
    LocalResolverResponseError,
    LocalResolverRuntimeError,
    ResolverEvidence,
)


class _FakeRuntime:
    def __init__(self, response: object = None, *, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[str] = []

    def invoke(self, request_json: str) -> str:
        self.calls.append(request_json)
        if self.error is not None:
            raise self.error
        return self.response  # type: ignore[return-value]


def _response(**overrides: object) -> str:
    payload: dict[str, object] = {
        "country": "Canada",
        "denomination": "10 cents",
        "year": "1937",
        "candidate_id": "canada-1937-10c",
        "confidence": None,
        "reason": "bounded evidence agrees",
        "abstain": False,
    }
    payload.update(overrides)
    return json.dumps(payload)


class LocalLLMResolverTests(unittest.TestCase):
    def test_disabled_by_default_and_does_not_call_runtime(self) -> None:
        runtime = _FakeRuntime(_response())
        resolver = LocalLLMResolver(runtime)

        with self.assertRaises(LocalResolverDisabled):
            resolver.resolve(ResolverEvidence(ocr_text=("CANADA",)))

        self.assertEqual(runtime.calls, [])

    def test_enabled_resolver_sends_bounded_evidence_and_parses_success(self) -> None:
        runtime = _FakeRuntime(_response())
        resolver = LocalLLMResolver(runtime, enabled=True)
        evidence = ResolverEvidence(
            ocr_text=("CANADA", "10 CENTS"),
            candidate_countries=("Canada",),
            candidate_denominations=("10 cents",),
            candidate_years=("1937", "1957"),
            candidate_ids=("canada-1937-10c", "canada-1957-10c"),
        )

        result = resolver.resolve(evidence)

        self.assertEqual(result.country, "Canada")
        self.assertEqual(result.denomination, "10 cents")
        self.assertEqual(result.year, "1937")
        self.assertEqual(result.candidate_id, "canada-1937-10c")
        self.assertIsNone(result.confidence)
        self.assertFalse(result.abstain)
        self.assertEqual(len(runtime.calls), 1)
        request = json.loads(runtime.calls[0])
        self.assertEqual(request["schema"], "coin-analyzer-local-resolver-v1")
        self.assertEqual(request["evidence"], evidence.to_payload())
        self.assertNotIn("expected", request)
        self.assertNotIn("ground_truth", request)

    def test_abstention_is_a_valid_structured_result(self) -> None:
        runtime = _FakeRuntime(
            _response(
                country=None,
                denomination=None,
                year=None,
                candidate_id=None,
                reason="insufficient evidence",
                abstain=True,
            )
        )

        result = LocalLLMResolver(runtime, enabled=True).resolve(ResolverEvidence())

        self.assertTrue(result.abstain)
        self.assertIsNone(result.country)
        self.assertIsNone(result.denomination)
        self.assertIsNone(result.year)
        self.assertIsNone(result.candidate_id)

    def test_partial_identity_is_normalized_to_complete_abstention(self) -> None:
        runtime = _FakeRuntime(
            _response(
                country="Canada",
                denomination="10 cents",
                year=None,
                candidate_id="canada-unknown-10c",
                reason="year is ambiguous",
                abstain=False,
            )
        )

        result = LocalLLMResolver(runtime, enabled=True).resolve(ResolverEvidence())

        self.assertTrue(result.abstain)
        self.assertIsNone(result.country)
        self.assertIsNone(result.denomination)
        self.assertIsNone(result.year)
        self.assertIsNone(result.candidate_id)
        self.assertEqual(result.reason, "year is ambiguous")

    def test_model_declared_abstention_clears_identity_fields(self) -> None:
        runtime = _FakeRuntime(
            _response(
                country="Canada",
                denomination="10 cents",
                year="1937",
                candidate_id="canada-1937-10c",
                reason="model chose to abstain",
                abstain=True,
            )
        )

        result = LocalLLMResolver(runtime, enabled=True).resolve(ResolverEvidence())

        self.assertTrue(result.abstain)
        self.assertIsNone(result.country)
        self.assertIsNone(result.denomination)
        self.assertIsNone(result.year)
        self.assertIsNone(result.candidate_id)

    def test_malformed_json_fails_closed(self) -> None:
        runtime = _FakeRuntime("```json\n{}\n```")

        with self.assertRaises(LocalResolverResponseError):
            LocalLLMResolver(runtime, enabled=True).resolve(ResolverEvidence())

    def test_schema_violation_fails_closed(self) -> None:
        payload = json.loads(_response())
        payload["unexpected"] = "value"
        runtime = _FakeRuntime(json.dumps(payload))

        with self.assertRaises(LocalResolverResponseError):
            LocalLLMResolver(runtime, enabled=True).resolve(ResolverEvidence())

    def test_wrong_field_types_fail_closed(self) -> None:
        invalid_cases = (
            {"abstain": "false"},
            {"confidence": True},
            {"year": 1937},
            {"reason": ""},
        )
        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                runtime = _FakeRuntime(_response(**overrides))
                with self.assertRaises(LocalResolverResponseError):
                    LocalLLMResolver(runtime, enabled=True).resolve(ResolverEvidence())

    def test_runtime_failure_is_reported_without_guessing(self) -> None:
        runtime = _FakeRuntime(error=TimeoutError("local runtime timed out"))

        with self.assertRaises(LocalResolverRuntimeError) as raised:
            LocalLLMResolver(runtime, enabled=True).resolve(ResolverEvidence())

        self.assertIn("TimeoutError", str(raised.exception))
        self.assertEqual(len(runtime.calls), 1)


if __name__ == "__main__":
    unittest.main()
