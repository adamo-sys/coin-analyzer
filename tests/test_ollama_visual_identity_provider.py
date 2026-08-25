"""Focused tests for the benchmark-only local Ollama visual provider."""

from __future__ import annotations

import json
import unittest

from capture_import.ollama_visual_identity_provider import (
    OllamaVisualIdentityProvider,
)
from capture_import.visual_identity_provider import (
    VisualIdentityImage,
    VisualIdentityMalformedOutput,
    VisualIdentityRequest,
)


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _request() -> VisualIdentityRequest:
    return VisualIdentityRequest(
        scan_id="local-vl-test",
        images=(
            VisualIdentityImage("obverse", "image/jpeg", b"front"),
            VisualIdentityImage("reverse", "image/jpeg", b"reverse"),
        ),
    )


class OllamaVisualIdentityProviderTests(unittest.TestCase):
    def test_decodes_structured_candidate_and_usage(self) -> None:
        raw = {
            "outcome": "CANDIDATES",
            "candidates": [
                {
                    "rank": 1,
                    "country": "Canada",
                    "denomination": "25 cents",
                    "year": "1967",
                    "type_design": "Centennial quarter",
                    "confidence": 0.8,
                    "observed_text": ["CANADA", "1967"],
                    "evidence_observations": ["Caribou reverse and 1967 date"],
                    "supporting_image_roles": ["obverse", "reverse"],
                }
            ],
        }
        seen = {}

        def opener(request, timeout):
            seen["timeout"] = timeout
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return _Response({
                "message": {"content": json.dumps(raw)},
                "prompt_eval_count": 123,
                "eval_count": 45,
            })

        provider = OllamaVisualIdentityProvider(opener=opener, timeout_seconds=30)
        report = provider.identify(_request())

        self.assertEqual(report.provider_id, "ollama-local-visual")
        self.assertEqual(report.model_id, "qwen2.5vl:7b")
        self.assertEqual(report.input_tokens, 123)
        self.assertEqual(report.output_tokens, 45)
        self.assertEqual(report.candidates[0].as_prediction(), {
            "country": "Canada",
            "denomination": "25 cents",
            "year": "1967",
            "type_design": "Centennial quarter",
        })
        self.assertEqual(seen["timeout"], 30.0)
        self.assertEqual(len(seen["body"]["messages"][0]["images"]), 2)
        self.assertEqual(seen["body"]["options"]["temperature"], 0)

    def test_supports_clean_abstention(self) -> None:
        provider = OllamaVisualIdentityProvider(
            opener=lambda *_args, **_kwargs: _Response({
                "message": {"content": json.dumps({
                    "outcome": "ABSTAINED", "candidates": []
                })
            })
        )
        report = provider.identify(_request())
        self.assertEqual(report.outcome, "ABSTAINED")
        self.assertEqual(report.candidates, ())

    def test_rejects_year_not_transcribed_verbatim(self) -> None:
        raw = {
            "outcome": "CANDIDATES",
            "candidates": [
                {
                    "rank": 1,
                    "country": "Canada",
                    "denomination": "25 cents",
                    "year": "1967",
                    "type_design": None,
                    "confidence": 0.5,
                    "observed_text": ["CANADA"],
                    "evidence_observations": ["Canadian design"],
                    "supporting_image_roles": ["obverse"],
                }
            ],
        }
        provider = OllamaVisualIdentityProvider(
            opener=lambda *_args, **_kwargs: _Response({
                "message": {"content": json.dumps(raw)}
            })
        )
        with self.assertRaisesRegex(VisualIdentityMalformedOutput, "year"):
            provider.identify(_request())

    def test_rejects_outcome_candidate_mismatch(self) -> None:
        provider = OllamaVisualIdentityProvider(
            opener=lambda *_args, **_kwargs: _Response({
                "message": {"content": json.dumps({
                    "outcome": "CANDIDATES", "candidates": []
                })
            })
        )
        with self.assertRaisesRegex(VisualIdentityMalformedOutput, "disagree"):
            provider.identify(_request())


if __name__ == "__main__":
    unittest.main()
