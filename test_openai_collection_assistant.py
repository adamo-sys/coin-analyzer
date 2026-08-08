"""Optional OpenAI adapter contract and cloud-payload tests with no network."""

import json
import os
import unittest
from unittest.mock import patch

from inference_telemetry import telemetry_scan

from openai_collection_assistant import (
    OPENAI_API_KEY_ENV,
    OPENAI_MODEL_ENV,
    OpenAIProviderConfigurationError,
    OpenAIResponsesAdapter,
)


class Parsed:
    def __init__(self, value):
        self.value = value

    def model_dump(self):
        return self.value


class Response:
    def __init__(self, value, usage=None):
        self.output_parsed = Parsed(value)
        self.usage = usage


class FakeResponses:
    def __init__(self, values):
        self.values = list(values)
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return Response(self.values.pop(0))


class FakeClient:
    def __init__(self, values):
        self.responses = FakeResponses(values)


class OpenAIAdapterTests(unittest.TestCase):
    def test_environment_configuration_is_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(OpenAIProviderConfigurationError):
                OpenAIResponsesAdapter.from_environment()
            configured, message = OpenAIResponsesAdapter.configuration_status()
        self.assertFalse(configured)
        self.assertIn(OPENAI_API_KEY_ENV, message)

    def test_planning_payload_contains_question_and_tool_schemas_only(self):
        client = FakeClient([{
            "status": "execute",
            "tool_calls": [{
                "tool_name": "inventory_count",
                "country": "Canada",
                "issuer": None,
                "denomination": None,
                "year": None,
                "acquisition_source": None,
                "acquisition_year": None,
                "limit": None,
            }],
            "message": "",
        }])
        adapter = OpenAIResponsesAdapter(model="test-model", client=client)
        with patch("openai_collection_assistant._structured_models", return_value=(object, object)):
            result = adapter.plan("Count Canadian coins", [{"name": "inventory_count"}])
        self.assertEqual("inventory_count", result["tool_calls"][0]["name"])
        call = client.responses.calls[0]
        self.assertFalse(call["store"])
        self.assertEqual("test-model", call["model"])
        user_payload = json.loads(call["input"][1]["content"])
        self.assertEqual({"question", "allowlisted_tools"}, set(user_payload))
        self.assertNotIn("collection", user_payload)

    def test_explanation_payload_is_bounded_evidence_and_marks_strings_untrusted(self):
        client = FakeClient([{
            "answer": "Grounded.",
            "evidence_ids": ["inventory_count:1"],
            "limitations": [],
        }])
        adapter = OpenAIResponsesAdapter(model="test-model", client=client)
        evidence = [{
            "tool": "inventory_count",
            "summary": "Matched 1.",
            "data": {"record_count": 1},
            "evidence": [{"evidence_id": "inventory_count:1"}],
            "limitations": [],
            "truncated": False,
        }]
        with patch("openai_collection_assistant._structured_models", return_value=(object, object)):
            result = adapter.explain("Count records", evidence)
        self.assertEqual("Grounded.", result["answer"])
        call = client.responses.calls[0]
        self.assertFalse(call["store"])
        self.assertIn("untrusted data", call["input"][0]["content"])
        payload = json.loads(call["input"][1]["content"])
        self.assertEqual({"question", "bounded_tool_evidence"}, set(payload))

    def test_adapter_import_does_not_require_openai_sdk(self):
        adapter = OpenAIResponsesAdapter(model="test-model", client=FakeClient([]))
        self.assertEqual("OpenAI", adapter.provider_name)
        self.assertEqual("test-model", adapter.model_name)

    def test_adapter_records_supplied_usage_and_model_attribution(self):
        class Usage:
            input_tokens = 12
            output_tokens = 3

        class Responses(FakeResponses):
            def parse(self, **kwargs):
                self.calls.append(kwargs)
                return Response(self.values.pop(0), usage=Usage())

        class Client:
            responses = Responses([{
                "status": "clarification",
                "tool_calls": [],
                "message": "Clarify.",
            }])

        class Sink:
            def __init__(self):
                self.records = []

            def write(self, record):
                self.records.append(record)

        sink = Sink()
        adapter = OpenAIResponsesAdapter(
            model="test-model",
            client=Client(),
            telemetry_sink=sink,
        )
        with (
            patch(
                "openai_collection_assistant._structured_models",
                return_value=(object, object),
            ),
            telemetry_scan("assistant-request-1"),
        ):
            adapter.plan("Question", [])

        self.assertEqual(len(sink.records), 1)
        record = sink.records[0]
        self.assertEqual(record.scan_id, "assistant-request-1")
        self.assertEqual(record.stage, "ask-my-collection-plan")
        self.assertEqual(record.provider, "OpenAI")
        self.assertEqual(record.model, "test-model")
        self.assertEqual(record.input_tokens, 12)
        self.assertEqual(record.output_tokens, 3)
        self.assertIsNone(record.estimated_cost_usd)


if __name__ == "__main__":
    unittest.main()
