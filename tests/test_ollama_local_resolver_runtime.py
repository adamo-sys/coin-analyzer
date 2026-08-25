"""Focused tests for the loopback-only Ollama resolver runtime."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch
import urllib.error

from capture_import.ollama_local_resolver_runtime import (
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_MODEL,
    OllamaLocalResolverRuntime,
    OllamaRuntimeError,
)


class _Response:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _resolver_request() -> str:
    return json.dumps(
        {
            "schema": "coin-analyzer-local-resolver-v1",
            "evidence": {
                "ocr_text": ["CANADA", "10 CENTS", "1937"],
                "candidate_countries": ["Canada"],
                "candidate_denominations": ["10 cents"],
                "candidate_years": ["1937", "1957"],
                "candidate_ids": [],
            },
            "response_contract": {
                "country": "string|null",
                "denomination": "string|null",
                "year": "string|null",
                "candidate_id": "string|null",
                "confidence": "number|null",
                "reason": "string",
                "abstain": "boolean",
            },
        }
    )


class OllamaLocalResolverRuntimeTests(unittest.TestCase):
    def test_defaults_target_local_qwen3_8b(self) -> None:
        runtime = OllamaLocalResolverRuntime()

        self.assertEqual(runtime.model, DEFAULT_OLLAMA_MODEL)
        self.assertEqual(runtime.model, "qwen3:8b")
        self.assertEqual(runtime.endpoint, DEFAULT_OLLAMA_ENDPOINT)
        self.assertEqual(runtime.endpoint, "http://127.0.0.1:11434/api/generate")

    def test_invoke_posts_bounded_request_and_returns_model_response(self) -> None:
        model_result = json.dumps(
            {
                "country": "Canada",
                "denomination": "10 cents",
                "year": "1937",
                "candidate_id": None,
                "confidence": None,
                "reason": "evidence agrees",
                "abstain": False,
            }
        )
        envelope = json.dumps({"response": model_result, "done": True})
        captured = {}

        def fake_urlopen(request, *, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _Response(envelope)

        runtime = OllamaLocalResolverRuntime(timeout_seconds=12.5)
        request_json = _resolver_request()
        with patch(
            "capture_import.ollama_local_resolver_runtime.urllib.request.urlopen",
            side_effect=fake_urlopen,
        ):
            result = runtime.invoke(request_json)

        self.assertEqual(result, model_result)
        self.assertEqual(captured["timeout"], 12.5)
        request = captured["request"]
        self.assertEqual(request.full_url, DEFAULT_OLLAMA_ENDPOINT)
        self.assertEqual(request.get_method(), "POST")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "qwen3:8b")
        self.assertEqual(payload["prompt"], request_json)
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["format"], "json")
        self.assertEqual(payload["options"], {"temperature": 0})
        self.assertIn("abstain=true", payload["system"])
        self.assertNotIn("expected", payload)
        self.assertNotIn("ground_truth", payload)

    def test_custom_local_model_is_supported(self) -> None:
        runtime = OllamaLocalResolverRuntime(model="qwen-coin:latest")
        envelope = json.dumps({"response": '{"ok":true}'})

        with patch(
            "capture_import.ollama_local_resolver_runtime.urllib.request.urlopen",
            return_value=_Response(envelope),
        ) as mocked:
            runtime.invoke(_resolver_request())

        payload = json.loads(mocked.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["model"], "qwen-coin:latest")

    def test_non_loopback_or_non_generate_endpoints_are_rejected(self) -> None:
        invalid = (
            "https://127.0.0.1:11434/api/generate",
            "http://192.168.1.50:11434/api/generate",
            "http://example.com:11434/api/generate",
            "http://127.0.0.1:11434/api/chat",
            "http://user:pass@127.0.0.1:11434/api/generate",
            "http://127.0.0.1:11434/api/generate?x=1",
        )
        for endpoint in invalid:
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ValueError):
                    OllamaLocalResolverRuntime(endpoint=endpoint)

    def test_localhost_and_ipv6_loopback_are_allowed(self) -> None:
        self.assertEqual(
            OllamaLocalResolverRuntime(
                endpoint="http://localhost:11434/api/generate"
            ).endpoint,
            "http://localhost:11434/api/generate",
        )
        self.assertEqual(
            OllamaLocalResolverRuntime(
                endpoint="http://[::1]:11434/api/generate"
            ).endpoint,
            "http://[::1]:11434/api/generate",
        )

    def test_invalid_configuration_fails_before_network_access(self) -> None:
        for model in ("", "   "):
            with self.subTest(model=model):
                with self.assertRaises(ValueError):
                    OllamaLocalResolverRuntime(model=model)
        for timeout in (0, -1, True, "60"):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    OllamaLocalResolverRuntime(timeout_seconds=timeout)  # type: ignore[arg-type]

    def test_invalid_resolver_request_fails_without_network_access(self) -> None:
        runtime = OllamaLocalResolverRuntime()
        with patch(
            "capture_import.ollama_local_resolver_runtime.urllib.request.urlopen"
        ) as mocked:
            with self.assertRaises(OllamaRuntimeError):
                runtime.invoke("not-json")
            with self.assertRaises(OllamaRuntimeError):
                runtime.invoke("[]")
        mocked.assert_not_called()

    def test_network_failure_is_reported_as_runtime_failure(self) -> None:
        runtime = OllamaLocalResolverRuntime()
        with patch(
            "capture_import.ollama_local_resolver_runtime.urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with self.assertRaises(OllamaRuntimeError) as raised:
                runtime.invoke(_resolver_request())

        self.assertIn("connection refused", str(raised.exception))

    def test_malformed_or_missing_ollama_response_fails_closed(self) -> None:
        invalid_bodies = (
            "not-json",
            "[]",
            "{}",
            json.dumps({"response": ""}),
            json.dumps({"response": {"country": "Canada"}}),
        )
        runtime = OllamaLocalResolverRuntime()
        for body in invalid_bodies:
            with self.subTest(body=body):
                with patch(
                    "capture_import.ollama_local_resolver_runtime.urllib.request.urlopen",
                    return_value=_Response(body),
                ):
                    with self.assertRaises(OllamaRuntimeError):
                        runtime.invoke(_resolver_request())


if __name__ == "__main__":
    unittest.main()
