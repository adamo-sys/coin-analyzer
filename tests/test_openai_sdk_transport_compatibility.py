"""Offline compatibility checks against the real optional OpenAI SDK transport.

The ordinary test suite does not install the optional SDK. These tests therefore
skip unless the dependency is present. CI's ``openai-dependency-smoke`` job pins
the declared minimum candidate and runs this module with an in-memory transport;
no provider, network, image file, API key, or private collection data is used.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import unittest

from grounded_collection_assistant import AssistantProviderError
from openai_collection_assistant import OpenAIResponsesAdapter
from capture_import.visual_identity_provider import (
    OPENAI_VISUAL_MAX_OUTPUT_TOKENS,
    OPENAI_VISUAL_MODEL_ID,
    OPENAI_VISUAL_REASONING_EFFORT,
    OpenAITerraVisualIdentityProvider,
    VisualIdentityImage,
    VisualIdentityRequest,
)


_OPTIONAL_SDK_AVAILABLE = (
    importlib.util.find_spec("openai") is not None
    and importlib.util.find_spec("httpx2") is not None
)


def _response_body(text: str, *, model: str = "test-model") -> dict[str, object]:
    return {
        "id": "resp_transport_test",
        "created_at": 0,
        "model": model,
        "object": "response",
        "parallel_tool_calls": True,
        "status": "completed",
        "tool_choice": "auto",
        "tools": [],
        "output": [
            {
                "type": "message",
                "id": "msg_transport_test",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                        "annotations": [],
                    }
                ],
            }
        ],
    }


def _visual_payload() -> dict[str, object]:
    return {
        "outcome": "CANDIDATES",
        "candidates": [
            {
                "rank": 1,
                "country": "Canada",
                "denomination": "5 cents",
                "year": "1964",
                "type_design": "Elizabeth II and beaver",
                "confidence": 0.8,
                "observed_text": ["CANADA", "5 CENTS", "1964"],
                "field_evidence": {
                    "country": ["CANADA is visible"],
                    "denomination": ["5 CENTS is visible"],
                    "year": ["1964 is visible"],
                    "type_design": ["Portrait and beaver are visible"],
                },
                "evidence_observations": ["CANADA and 5 CENTS are visible"],
                "supporting_image_roles": ["obverse", "reverse"],
            }
        ],
    }


def _visual_request() -> VisualIdentityRequest:
    return VisualIdentityRequest(
        scan_id="sdk-transport-compat",
        images=(
            VisualIdentityImage("obverse", "image/jpeg", b"obverse-bytes"),
            VisualIdentityImage("reverse", "image/png", b"reverse-bytes"),
        ),
    )


@unittest.skipUnless(_OPTIONAL_SDK_AVAILABLE, "optional OpenAI SDK is not installed")
class OpenAISDKTransportCompatibilityTests(unittest.TestCase):
    def _client(self, handler):
        import httpx2
        from openai import OpenAI

        return OpenAI(
            api_key="sk-offline-transport-test",
            max_retries=0,
            base_url="https://example.test/v1",
            http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        )

    def test_collection_assistant_round_trips_real_sdk_parse_request(self) -> None:
        import httpx2

        requests: list[dict[str, object]] = []

        def respond(request):
            self.assertEqual(request.url.path, "/v1/responses")
            body = json.loads(request.content.decode("utf-8"))
            requests.append(body)
            parsed = {
                "status": "execute",
                "tool_calls": [
                    {
                        "tool_name": "inventory_count",
                        "country": "Canada",
                    }
                ],
                "message": "",
            }
            return httpx2.Response(200, json=_response_body(json.dumps(parsed)))

        with self._client(respond) as client:
            adapter = OpenAIResponsesAdapter(model="test-model", client=client)
            result = adapter.plan(
                "Count Canadian coins",
                [{"name": "inventory_count"}],
            )

        self.assertEqual(result["status"], "execute")
        self.assertEqual(result["tool_calls"], [
            {"name": "inventory_count", "arguments": {"country": "Canada"}}
        ])
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request["model"], "test-model")
        self.assertFalse(request["store"])
        self.assertEqual([row["role"] for row in request["input"]], ["system", "user"])
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        user_payload = json.loads(request["input"][1]["content"])
        self.assertEqual(set(user_payload), {"question", "allowlisted_tools"})

    def test_collection_assistant_maps_real_sdk_transport_error(self) -> None:
        import httpx2

        def fail(_request):
            return httpx2.Response(
                500,
                json={
                    "error": {
                        "message": "synthetic transport failure",
                        "type": "server_error",
                        "param": None,
                        "code": None,
                    }
                },
            )

        with self._client(fail) as client:
            adapter = OpenAIResponsesAdapter(model="test-model", client=client)
            with self.assertRaises(AssistantProviderError) as raised:
                adapter.plan("Count Canadian coins", [{"name": "inventory_count"}])

        self.assertIn("OpenAI request failed (", str(raised.exception))
        self.assertNotIn("synthetic transport failure", str(raised.exception))

    def test_visual_provider_round_trips_real_sdk_create_request(self) -> None:
        import httpx2

        requests: list[dict[str, object]] = []

        def respond(request):
            self.assertEqual(request.url.path, "/v1/responses")
            body = json.loads(request.content.decode("utf-8"))
            requests.append(body)
            return httpx2.Response(
                200,
                json=_response_body(
                    json.dumps(_visual_payload()),
                    model=OPENAI_VISUAL_MODEL_ID,
                ),
            )

        with self._client(respond) as client:
            report = OpenAITerraVisualIdentityProvider(client=client).identify(
                _visual_request()
            )

        self.assertEqual(report.candidates[0].country, "Canada")
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request["model"], OPENAI_VISUAL_MODEL_ID)
        self.assertEqual(request["reasoning"], {"effort": OPENAI_VISUAL_REASONING_EFFORT})
        self.assertEqual(request["tools"], [])
        self.assertFalse(request["store"])
        self.assertEqual(request["max_output_tokens"], OPENAI_VISUAL_MAX_OUTPUT_TOKENS)
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        content = request["input"][0]["content"]
        self.assertEqual(content[1]["detail"], "original")
        self.assertEqual(content[2]["detail"], "original")
        self.assertEqual(
            base64.b64decode(content[1]["image_url"].split(",", 1)[1]),
            b"obverse-bytes",
        )
        self.assertEqual(
            base64.b64decode(content[2]["image_url"].split(",", 1)[1]),
            b"reverse-bytes",
        )

    def test_visual_provider_preserves_real_sdk_rate_limit_error(self) -> None:
        import httpx2
        from openai import RateLimitError

        def rate_limited(_request):
            return httpx2.Response(
                429,
                headers={"x-request-id": "req_transport_test"},
                json={
                    "error": {
                        "message": "synthetic rate limit",
                        "type": "rate_limit_error",
                        "param": None,
                        "code": "rate_limit_exceeded",
                    }
                },
            )

        with self._client(rate_limited) as client:
            provider = OpenAITerraVisualIdentityProvider(client=client)
            with self.assertRaises(RateLimitError):
                provider.identify(_visual_request())


if __name__ == "__main__":
    unittest.main()
