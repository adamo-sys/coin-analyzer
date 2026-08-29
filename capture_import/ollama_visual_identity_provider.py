"""Benchmark-only local Ollama visual identity provider.

This module is intentionally isolated from desktop composition, OCR, review,
and persistence. It implements the existing provider-neutral visual identity
contract for local experimentation against the frozen visual benchmark.
"""

from __future__ import annotations

import base64
import json
from typing import Mapping
from urllib import error as urlerror
from urllib import request as urlrequest

from .visual_identity_provider import (
    VisualIdentityCandidate,
    VisualIdentityContractError,
    VisualIdentityMalformedOutput,
    VisualIdentityReport,
    VisualIdentityRequest,
)

OLLAMA_VISUAL_PROVIDER_ID = "ollama-local-visual"
OLLAMA_VISUAL_DEFAULT_MODEL = "qwen2.5vl:7b"
OLLAMA_VISUAL_DEFAULT_URL = "http://127.0.0.1:11434/api/chat"

OLLAMA_VISUAL_PROMPT = (
    "Identify the single physical coin shown in the two attached images. "
    "The first image is the obverse and the second is the reverse. Use only "
    "visible evidence in the images plus general numismatic knowledge. Return "
    "strict JSON matching the supplied schema. Return up to three ranked "
    "candidates. Each identity field is independently nullable. Do not guess "
    "a field when evidence is weak. If no identity field is defensible, set "
    "outcome to ABSTAINED and candidates to an empty array. Transcribe short "
    "visible text separately. Any proposed year must appear verbatim in "
    "observed_text. confidence is an uncalibrated source ranking score only."
)

OLLAMA_VISUAL_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["outcome", "candidates"],
    "properties": {
        "outcome": {"type": "string", "enum": ["CANDIDATES", "ABSTAINED"]},
        "candidates": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "rank", "country", "denomination", "year", "type_design",
                    "confidence", "observed_text", "evidence_observations",
                    "supporting_image_roles"
                ],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1, "maximum": 3},
                    "country": {"type": ["string", "null"]},
                    "denomination": {"type": ["string", "null"]},
                    "year": {"type": ["string", "null"]},
                    "type_design": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "observed_text": {"type": "array", "maxItems": 6, "items": {"type": "string"}},
                    "evidence_observations": {"type": "array", "minItems": 1, "maxItems": 2, "items": {"type": "string"}},
                    "supporting_image_roles": {"type": "array", "minItems": 1, "maxItems": 2, "items": {"type": "string", "enum": ["obverse", "reverse"]}}
                }
            }
        }
    }
}


class OllamaVisualIdentityError(RuntimeError):
    """Local Ollama visual runtime failed."""


class OllamaVisualIdentityProvider:
    """Local qwen2.5-vl-compatible provider for headless benchmark use only."""

    provider_id = OLLAMA_VISUAL_PROVIDER_ID

    def __init__(
        self,
        *,
        model: str = OLLAMA_VISUAL_DEFAULT_MODEL,
        url: str = OLLAMA_VISUAL_DEFAULT_URL,
        timeout_seconds: float = 120.0,
        opener=urlrequest.urlopen,
    ) -> None:
        self.model_id = str(model).strip()
        self._url = str(url).strip()
        self._timeout_seconds = float(timeout_seconds)
        self._opener = opener
        if not self.model_id or not self._url or self._timeout_seconds <= 0:
            raise ValueError("model, url, and positive timeout are required.")

    @property
    def configuration(self) -> Mapping[str, object]:
        return {
            "provider": "Ollama local",
            "provider_id": self.provider_id,
            "model": self.model_id,
            "url": self._url,
            "timeout_seconds": self._timeout_seconds,
            "stream": False,
            "temperature": 0,
            "benchmark_only": True,
            "prompt": OLLAMA_VISUAL_PROMPT,
        }

    def identify(self, request: VisualIdentityRequest) -> VisualIdentityReport:
        if not isinstance(request, VisualIdentityRequest):
            raise VisualIdentityContractError("request must be VisualIdentityRequest.")
        payload = {
            "model": self.model_id,
            "stream": False,
            "format": OLLAMA_VISUAL_SCHEMA,
            "options": {"temperature": 0},
            "messages": [{
                "role": "user",
                "content": OLLAMA_VISUAL_PROMPT,
                "images": [base64.b64encode(image.data).decode("ascii") for image in request.images],
            }],
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = urlrequest.Request(
            self._url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener(http_request, timeout=self._timeout_seconds) as response:
                envelope = json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError, UnicodeError, json.JSONDecodeError, urlerror.URLError) as exc:
            raise OllamaVisualIdentityError(f"local Ollama visual request failed: {exc}") from exc
        return self._decode(envelope)

    def _decode(self, envelope: object) -> VisualIdentityReport:
        if not isinstance(envelope, Mapping):
            raise VisualIdentityMalformedOutput("Ollama response envelope must be an object.")
        message = envelope.get("message")
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
            raise VisualIdentityMalformedOutput("Ollama response is missing message.content.")
        try:
            raw = json.loads(message["content"])
        except json.JSONDecodeError as exc:
            error = VisualIdentityMalformedOutput("Ollama visual output is not JSON.")
            error.raw_provider_output = message.get("content")
            raise error from exc
        if not isinstance(raw, Mapping) or set(raw) != {"outcome", "candidates"}:
            raise VisualIdentityMalformedOutput("visual output has unexpected top-level fields.")
        outcome = raw.get("outcome")
        rows = raw.get("candidates")
        if outcome not in {"CANDIDATES", "ABSTAINED"} or not isinstance(rows, list):
            raise VisualIdentityMalformedOutput("visual outcome or candidates is invalid.")
        if len(rows) > 3 or ((outcome == "CANDIDATES") != bool(rows)):
            raise VisualIdentityMalformedOutput("visual outcome and candidates disagree.")

        candidates = tuple(self._candidate(row) for row in rows)
        if tuple(item.rank for item in candidates) != tuple(range(1, len(candidates) + 1)):
            raise VisualIdentityMalformedOutput("candidate ranks must be contiguous from one.")

        return VisualIdentityReport(
            outcome=str(outcome),
            candidates=candidates,
            provider_id=self.provider_id,
            model_id=self.model_id,
            response_id=None,
            input_tokens=_optional_int(envelope.get("prompt_eval_count")),
            output_tokens=_optional_int(envelope.get("eval_count")),
            raw_structured_result=dict(raw),
        )

    def _candidate(self, raw: object) -> VisualIdentityCandidate:
        required = {
            "rank", "country", "denomination", "year", "type_design",
            "confidence", "observed_text", "evidence_observations",
            "supporting_image_roles"
        }
        if not isinstance(raw, Mapping) or set(raw) != required:
            raise VisualIdentityMalformedOutput("candidate fields do not match the local visual contract.")
        rank = raw["rank"]
        score = raw["confidence"]
        if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= 3:
            raise VisualIdentityMalformedOutput("candidate rank is invalid.")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= float(score) <= 1:
            raise VisualIdentityMalformedOutput("candidate source score is invalid.")
        observed = _string_tuple(raw["observed_text"], max_items=6, max_chars=48)
        evidence = _string_tuple(raw["evidence_observations"], min_items=1, max_items=2, max_chars=72)
        roles = _string_tuple(raw["supporting_image_roles"], min_items=1, max_items=2, max_chars=7)
        if any(role not in {"obverse", "reverse"} for role in roles):
            raise VisualIdentityMalformedOutput("candidate image role is invalid.")
        country = _nullable_text(raw["country"], 48)
        denomination = _nullable_text(raw["denomination"], 40)
        year = _nullable_text(raw["year"], 16)
        type_design = _nullable_text(raw["type_design"], 80)
        if year is not None and year not in observed:
            raise VisualIdentityMalformedOutput("proposed year must appear verbatim in observed_text.")
        return VisualIdentityCandidate(
            rank=rank,
            country=country,
            denomination=denomination,
            year=year,
            type_design=type_design,
            confidence=float(score),
            evidence_observations=evidence,
            supporting_image_roles=roles,
            provider_id=self.provider_id,
            model_id=self.model_id,
            observed_text=observed,
            field_evidence=(),
        )


def _nullable_text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise VisualIdentityMalformedOutput("identity text field is invalid.")
    return value.strip()


def _string_tuple(
    value: object,
    *,
    min_items: int = 0,
    max_items: int,
    max_chars: int,
) -> tuple[str, ...]:
    if not isinstance(value, list) or not min_items <= len(value) <= max_items:
        raise VisualIdentityMalformedOutput("bounded string array is invalid.")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or len(item.strip()) > max_chars:
            raise VisualIdentityMalformedOutput("bounded string array item is invalid.")
        text = item.strip()
        if text in items:
            raise VisualIdentityMalformedOutput("bounded string array contains duplicates.")
        items.append(text)
    return tuple(items)


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value
