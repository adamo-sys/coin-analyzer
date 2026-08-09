from __future__ import annotations

import base64
import json
from pathlib import Path
import unittest

from inference_telemetry import InferenceTelemetryRecord
from capture_import.visual_identity_provider import (
    OPENAI_VISUAL_EVIDENCE_MAX_CHARS,
    OPENAI_VISUAL_IMAGE_DETAIL,
    OPENAI_VISUAL_MAX_CANDIDATES,
    OPENAI_VISUAL_MAX_EVIDENCE_OBSERVATIONS,
    OPENAI_VISUAL_MAX_OUTPUT_TOKENS,
    OPENAI_VISUAL_MODEL_ID,
    OPENAI_VISUAL_PROMPT,
    OPENAI_VISUAL_REASONING_EFFORT,
    PREVIOUS_OPENAI_VISUAL_MAX_OUTPUT_TOKENS,
    OpenAITerraVisualIdentityProvider,
    VisualIdentityImage,
    VisualIdentityMalformedOutput,
    VisualIdentityRequest,
)


class _Sink:
    def __init__(self) -> None:
        self.records: list[InferenceTelemetryRecord] = []

    def write(self, record: InferenceTelemetryRecord) -> None:
        self.records.append(record)


class _Usage:
    input_tokens = 1_000
    output_tokens = 100


class _Response:
    def __init__(self, payload: object) -> None:
        self.id = "resp-test"
        self.output_text = payload if isinstance(payload, str) else json.dumps(payload)
        self.usage = _Usage()


class _Responses:
    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class _Client:
    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.responses = _Responses(response, error)


def _payload(*, ranks=(1,), evidence: str = "CANADA and 5 CENTS are visible") -> dict[str, object]:
    return {
        "outcome": "CANDIDATES" if ranks else "ABSTAINED",
        "candidates": [
            {
                "rank": rank,
                "country": "Canada",
                "denomination": "5 cents",
                "year": "1964",
                "type_design": "Elizabeth II and beaver",
                "confidence": 0.8,
                "evidence_observations": [evidence],
                "supporting_image_roles": ["obverse", "reverse"],
            }
            for rank in ranks
        ],
    }


def _request() -> VisualIdentityRequest:
    return VisualIdentityRequest(
        scan_id="visual-v2-prospective-neutral-case",
        images=(
            VisualIdentityImage("obverse", "image/jpeg", b"obverse-bytes"),
            VisualIdentityImage("reverse", "image/png", b"reverse-bytes"),
        ),
    )


class VisualIdentityProviderTests(unittest.TestCase):
    def test_fixed_request_supplies_both_images_without_paths_or_ground_truth(self) -> None:
        client = _Client(_Response(_payload()))
        provider = OpenAITerraVisualIdentityProvider(client=client)

        report = provider.identify(_request())

        self.assertEqual(report.candidates[0].country, "Canada")
        call = client.responses.calls[0]
        self.assertEqual(call["model"], "gpt-5.6-terra")
        self.assertEqual(call["reasoning"], {"effort": "low"})
        self.assertEqual(call["tools"], [])
        self.assertFalse(call["store"])
        self.assertEqual(call["max_output_tokens"], OPENAI_VISUAL_MAX_OUTPUT_TOKENS)
        self.assertTrue(call["text"]["format"]["strict"])
        content = call["input"][0]["content"]
        self.assertEqual(content[0], {"type": "input_text", "text": OPENAI_VISUAL_PROMPT})
        self.assertEqual([item["detail"] for item in content[1:]], ["original", "original"])
        self.assertEqual(
            base64.b64decode(content[1]["image_url"].split(",", 1)[1]),
            b"obverse-bytes",
        )
        serialized = json.dumps(call)
        for forbidden in ("neutral-case", "expected", "case_id", "Numista"):
            self.assertNotIn(forbidden, serialized)

    def test_configuration_is_fixed_and_records_changed_token_limit(self) -> None:
        configuration = OpenAITerraVisualIdentityProvider(
            client=_Client(_Response(_payload()))
        ).configuration
        self.assertEqual(configuration["model"], OPENAI_VISUAL_MODEL_ID)
        self.assertEqual(configuration["reasoning_effort"], OPENAI_VISUAL_REASONING_EFFORT)
        self.assertEqual(configuration["image_detail"], OPENAI_VISUAL_IMAGE_DETAIL)
        self.assertEqual(configuration["max_candidates"], OPENAI_VISUAL_MAX_CANDIDATES)
        self.assertEqual(configuration["max_output_tokens"], 2000)
        self.assertEqual(configuration["previous_max_output_tokens"], 1200)
        self.assertEqual(PREVIOUS_OPENAI_VISUAL_MAX_OUTPUT_TOKENS, 1200)

    def test_schema_has_hard_evidence_and_free_text_bounds(self) -> None:
        schema = OpenAITerraVisualIdentityProvider(
            client=_Client(_Response(_payload()))
        ).configuration["structured_output_schema"]
        candidates = schema["properties"]["candidates"]
        properties = candidates["items"]["properties"]
        self.assertEqual(candidates["maxItems"], 3)
        self.assertEqual(
            properties["evidence_observations"]["maxItems"],
            OPENAI_VISUAL_MAX_EVIDENCE_OBSERVATIONS,
        )
        self.assertEqual(
            properties["evidence_observations"]["items"]["maxLength"],
            OPENAI_VISUAL_EVIDENCE_MAX_CHARS,
        )
        for field in ("country", "denomination", "year", "type_design"):
            self.assertIn("maxLength", properties[field])

    def test_local_validation_rejects_overlong_evidence(self) -> None:
        with self.assertRaises(VisualIdentityMalformedOutput):
            OpenAITerraVisualIdentityProvider(
                client=_Client(
                    _Response(_payload(evidence="x" * (OPENAI_VISUAL_EVIDENCE_MAX_CHARS + 1)))
                )
            ).identify(_request())

    def test_candidate_order_is_deterministic_by_explicit_rank(self) -> None:
        report = OpenAITerraVisualIdentityProvider(
            client=_Client(_Response(_payload(ranks=(2, 1))))
        ).identify(_request())
        self.assertEqual([candidate.rank for candidate in report.candidates], [1, 2])

    def test_noncontiguous_or_duplicate_ranks_are_malformed(self) -> None:
        for ranks in ((2,), (1, 1)):
            with self.subTest(ranks=ranks), self.assertRaises(VisualIdentityMalformedOutput):
                OpenAITerraVisualIdentityProvider(
                    client=_Client(_Response(_payload(ranks=ranks)))
                ).identify(_request())

    def test_truncated_output_is_infrastructure_failure_with_usage(self) -> None:
        sink = _Sink()
        provider = OpenAITerraVisualIdentityProvider(
            client=_Client(_Response('{"outcome":"CANDIDATES"')),
            telemetry_sink=sink,
        )
        with self.assertRaises(VisualIdentityMalformedOutput) as raised:
            provider.identify(_request())
        self.assertEqual(raised.exception.input_tokens, 1_000)
        self.assertEqual(raised.exception.output_tokens, 100)
        self.assertFalse(sink.records[0].success)
        self.assertEqual(sink.records[0].input_tokens, 1_000)
        self.assertAlmostEqual(sink.records[0].estimated_cost_usd, 0.0032)

    def test_provider_exception_identity_is_preserved(self) -> None:
        failure = RuntimeError("remote provider unavailable")
        sink = _Sink()
        provider = OpenAITerraVisualIdentityProvider(
            client=_Client(error=failure), telemetry_sink=sink
        )
        with self.assertRaises(RuntimeError) as raised:
            provider.identify(_request())
        self.assertIs(raised.exception, failure)
        self.assertFalse(sink.records[0].success)

    def test_success_telemetry_attributes_stage_usage_and_cost(self) -> None:
        sink = _Sink()
        OpenAITerraVisualIdentityProvider(
            client=_Client(_Response(_payload())), telemetry_sink=sink
        ).identify(_request())
        record = sink.records[0]
        self.assertEqual(record.stage, "visual-identity")
        self.assertEqual(record.provider, "OpenAI")
        self.assertEqual(record.model, "gpt-5.6-terra")
        self.assertEqual(record.input_tokens, 1_000)
        self.assertEqual(record.output_tokens, 100)
        self.assertAlmostEqual(record.estimated_cost_usd, 0.0032)

    def test_visual_integration_does_not_modify_ocr_or_persistence_boundaries(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for relative in (
            "coin_collection.py",
            "capture_import/desktop_import_pipeline_selection.py",
            "capture_import/workflow_ocr_composition.py",
            "capture_import/desktop_ocr_review_composition.py",
            "capture_import/desktop_ocr_review_handoff.py",
            "capture_import/workflow_ocr_review_session.py",
            "capture_import/workflow_ocr_review_controller.py",
            "capture_import/reviewed_coin_collection_entry.py",
            "capture_import/workflow_ocr_review_persistence_service.py",
        ):
            source = (root / relative).read_text(encoding="utf-8")
            for forbidden in (
                "visual_identity_provider",
                "visual_evaluation_runner",
                "evidence_fusion",
                "fusion_evaluation_runner",
                "OpenAITerraVisualIdentityProvider",
                "fuse_identity_evidence",
            ):
                self.assertNotIn(forbidden, source, relative)

        gui_source = (root / "coin_collection_gui.py").read_text(encoding="utf-8")
        self.assertIn("import_coin_images_with_visual_ai", gui_source)
        self.assertNotIn("evidence_fusion", gui_source)
        self.assertNotIn("fuse_identity_evidence", gui_source)


if __name__ == "__main__":
    unittest.main()
