"""OpenAI implementation of the grounded visual observation contract."""

from __future__ import annotations

import base64
import json
from typing import Mapping

from .grounded_visual_observation import (
    GroundedVisualObservation,
    GroundedVisualObservationContractError,
    GroundedVisualObservationProvider,
    GroundedVisualObservationReport,
    GroundedVisualObservationRequest,
)


OPENAI_GROUNDED_OBSERVATION_PROVIDER_ID = "openai-responses-grounded-observation"
OPENAI_GROUNDED_OBSERVATION_MODEL_ID = "gpt-5.6-terra"
OPENAI_GROUNDED_OBSERVATION_REASONING_EFFORT = "low"
OPENAI_GROUNDED_OBSERVATION_IMAGE_DETAIL = "original"
OPENAI_GROUNDED_OBSERVATION_MAX_OUTPUT_TOKENS = 800

OPENAI_GROUNDED_OBSERVATION_PROMPT = (
    "Observe only visually defensible evidence in this single coin-side image. "
    "Do not identify the coin. Do not guess or infer country, jurisdiction, "
    "denomination, year, ruler, coin type, catalogue entry, mint, or authority. "
    "Treat this as literal transcription, not numismatic interpretation. "
    "Inspect the full coin face, including the rim legend and small text near "
    "the portrait or central motif, before returning the observation. "
    "For visible_text, transcribe each distinct readable inscription as a "
    "separate item, preserving the characters and word order actually visible. "
    "Include literal alphabetic legends as well as numeric inscriptions. "
    "Do not translate, normalize, reconstruct, silently correct, or complete "
    "unclear legends. If only part of an inscription is readable, return only "
    "the readable fragment; do not fill the missing characters from context. "
    "date_like is a second copy of a clearly visible date-like numeral already "
    "supported by the pixels; it is not permission to infer a year. "
    "denomination_mark is a second copy of a clearly visible numeric/unit "
    "expression already supported by the pixels; preserve a visible unit or "
    "currency mark with the numeral when readable. Do not turn a bare numeral "
    "into a denomination by guessing its unit. "
    "Describe a portrait only when visibly defensible and describe appearance, "
    "not identity. Motifs must be visible objects or design elements. "
    "Missing evidence is preferred to guessed evidence. Return only the "
    "requested structured observation."
)

OPENAI_GROUNDED_OBSERVATION_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "visible_text",
        "script",
        "portrait",
        "motifs",
        "construction",
        "shape",
        "date_like",
        "denomination_mark",
    ],
    "properties": {
        "visible_text": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "minLength": 1, "maxLength": 64},
        },
        "script": {"type": ["string", "null"], "maxLength": 64},
        "portrait": {"type": ["string", "null"], "maxLength": 96},
        "motifs": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "minLength": 1, "maxLength": 64},
        },
        "construction": {"type": ["string", "null"], "maxLength": 64},
        "shape": {"type": ["string", "null"], "maxLength": 64},
        "date_like": {"type": ["string", "null"], "maxLength": 32},
        "denomination_mark": {"type": ["string", "null"], "maxLength": 32},
    },
}


class GroundedVisualObservationMalformedOutput(
    GroundedVisualObservationContractError
):
    """Provider output cannot become a grounded observation."""


class OpenAIGroundedVisualObservationProvider(GroundedVisualObservationProvider):
    """One-side observation provider with no identity semantics."""

    provider_id = OPENAI_GROUNDED_OBSERVATION_PROVIDER_ID
    model_id = OPENAI_GROUNDED_OBSERVATION_MODEL_ID

    def __init__(self, *, client: object | None = None) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI()
        self._client = client

    @property
    def configuration(self) -> Mapping[str, object]:
        return {
            "api": "Responses API",
            "provider": "OpenAI",
            "provider_id": self.provider_id,
            "model": self.model_id,
            "reasoning_effort": OPENAI_GROUNDED_OBSERVATION_REASONING_EFFORT,
            "image_detail": OPENAI_GROUNDED_OBSERVATION_IMAGE_DETAIL,
            "max_output_tokens": OPENAI_GROUNDED_OBSERVATION_MAX_OUTPUT_TOKENS,
            "tools": [],
            "store": False,
            "prompt": OPENAI_GROUNDED_OBSERVATION_PROMPT,
            "structured_output_schema": OPENAI_GROUNDED_OBSERVATION_SCHEMA,
        }

    def observe(
        self, request: GroundedVisualObservationRequest
    ) -> GroundedVisualObservationReport:
        if not isinstance(request, GroundedVisualObservationRequest):
            raise GroundedVisualObservationContractError(
                "request must be GroundedVisualObservationRequest."
            )
        encoded = base64.b64encode(request.image.data).decode("ascii")
        response = self._client.responses.create(
            model=self.model_id,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": OPENAI_GROUNDED_OBSERVATION_PROMPT,
                        },
                        {
                            "type": "input_image",
                            "detail": OPENAI_GROUNDED_OBSERVATION_IMAGE_DETAIL,
                            "image_url": (
                                f"data:{request.image.media_type};base64,{encoded}"
                            ),
                        },
                    ],
                }
            ],
            reasoning={"effort": OPENAI_GROUNDED_OBSERVATION_REASONING_EFFORT},
            text={
                "format": {
                    "type": "json_schema",
                    "name": "grounded_visual_observation",
                    "strict": True,
                    "schema": OPENAI_GROUNDED_OBSERVATION_SCHEMA,
                },
                "verbosity": "low",
            },
            tools=[],
            max_output_tokens=OPENAI_GROUNDED_OBSERVATION_MAX_OUTPUT_TOKENS,
            store=False,
        )
        raw_text = getattr(response, "output_text", None)
        try:
            raw = json.loads(raw_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise GroundedVisualObservationMalformedOutput(
                "provider response is not valid structured JSON."
            ) from exc

        observation = _validated_observation(raw, role=request.image.role)
        usage = getattr(response, "usage", None)
        response_id = getattr(response, "id", None)
        return GroundedVisualObservationReport(
            observation=observation,
            provider_id=self.provider_id,
            model_id=self.model_id,
            response_id=response_id if isinstance(response_id, str) and response_id else None,
            input_tokens=_token_count(getattr(usage, "input_tokens", None)),
            output_tokens=_token_count(getattr(usage, "output_tokens", None)),
        )


def _validated_observation(
    raw: object, *, role: str
) -> GroundedVisualObservation:
    expected = set(OPENAI_GROUNDED_OBSERVATION_SCHEMA["required"])
    if not isinstance(raw, Mapping) or set(raw) != expected:
        raise GroundedVisualObservationMalformedOutput(
            "structured observation fields do not match the contract."
        )
    visible_text = _string_list(raw["visible_text"], "visible_text")
    motifs = _string_list(raw["motifs"], "motifs")
    return GroundedVisualObservation(
        role=role,
        visible_text=visible_text,
        script=_optional_text(raw["script"], "script"),
        portrait=_optional_text(raw["portrait"], "portrait"),
        motifs=motifs,
        construction=_optional_text(raw["construction"], "construction"),
        shape=_optional_text(raw["shape"], "shape"),
        date_like=_optional_text(raw["date_like"], "date_like"),
        denomination_mark=_optional_text(
            raw["denomination_mark"], "denomination_mark"
        ),
    )


def _string_list(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 8:
        raise GroundedVisualObservationMalformedOutput(
            f"{name} must be an array with at most eight strings."
        )
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise GroundedVisualObservationMalformedOutput(
                f"{name} entries must be non-empty strings."
            )
        text = item.strip()
        if text in result:
            raise GroundedVisualObservationMalformedOutput(
                f"{name} entries must not contain duplicates."
            )
        result.append(text)
    return tuple(result)


def _optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise GroundedVisualObservationMalformedOutput(
            f"{name} must be a non-empty string or null."
        )
    return value.strip()


def _token_count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value
