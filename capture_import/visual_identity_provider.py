"""Headless provider-neutral visual identity contract and fixed Terra experiment."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import math
import re
from typing import Mapping, Protocol, runtime_checkable

from inference_telemetry import TelemetrySink, instrument_inference


OPENAI_VISUAL_PROVIDER_ID = "openai-responses-visual"
OPENAI_VISUAL_MODEL_ID = "gpt-5.6-terra"
OPENAI_VISUAL_REASONING_EFFORT = "low"
OPENAI_VISUAL_IMAGE_DETAIL = "original"
OPENAI_VISUAL_MAX_OUTPUT_TOKENS = 2000
PREVIOUS_OPENAI_VISUAL_MAX_OUTPUT_TOKENS = 1200
OPENAI_VISUAL_MAX_CANDIDATES = 3
OPENAI_VISUAL_MAX_EVIDENCE_OBSERVATIONS = 2
OPENAI_VISUAL_MAX_OBSERVED_TEXT = 6
OPENAI_VISUAL_MAX_FIELD_EVIDENCE = 2
OPENAI_VISUAL_COUNTRY_MAX_CHARS = 48
OPENAI_VISUAL_DENOMINATION_MAX_CHARS = 40
OPENAI_VISUAL_YEAR_MAX_CHARS = 16
OPENAI_VISUAL_TYPE_DESIGN_MAX_CHARS = 80
OPENAI_VISUAL_EVIDENCE_MAX_CHARS = 72
OPENAI_VISUAL_OBSERVED_TEXT_MAX_CHARS = 48
VISUAL_IDENTITY_SCAN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

OPENAI_VISUAL_PROMPT = (
    "Identify the single physical coin shown in these two photographs. The "
    "first image is the obverse and the second image is the reverse. Using "
    "only visible evidence in the images and your general knowledge, return "
    "up to three ranked composite identity candidates. Do not use external "
    "tools or sources. Transcribe short visible text separately from inferred "
    "identity. Every identity field is independently nullable; preserve useful "
    "partial findings instead of guessing. Abstain only when no identity field "
    "can be proposed. Every proposed field needs field-specific visible "
    "evidence; leave field evidence empty for fields you do not propose. A "
    "proposed year must also occur verbatim in observed_text. "
    "The 0-to-1 confidence value is an uncalibrated provider source score, not "
    "a probability. Give brief bounded evidence based on visible legends, "
    "numerals, motifs, or designs. State which image roles support each candidate."
)

OPENAI_VISUAL_OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["outcome", "candidates"],
    "properties": {
        "outcome": {"type": "string", "enum": ["CANDIDATES", "ABSTAINED"]},
        "candidates": {
            "type": "array",
            "maxItems": OPENAI_VISUAL_MAX_CANDIDATES,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "rank",
                    "country",
                    "denomination",
                    "year",
                    "type_design",
                    "confidence",
                    "observed_text",
                    "field_evidence",
                    "evidence_observations",
                    "supporting_image_roles",
                ],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1, "maximum": 3},
                    "country": {
                        "type": ["string", "null"],
                        "maxLength": OPENAI_VISUAL_COUNTRY_MAX_CHARS,
                    },
                    "denomination": {
                        "type": ["string", "null"],
                        "maxLength": OPENAI_VISUAL_DENOMINATION_MAX_CHARS,
                    },
                    "year": {
                        "type": ["string", "null"],
                        "maxLength": OPENAI_VISUAL_YEAR_MAX_CHARS,
                    },
                    "type_design": {
                        "type": ["string", "null"],
                        "maxLength": OPENAI_VISUAL_TYPE_DESIGN_MAX_CHARS,
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "observed_text": {
                        "type": "array",
                        "maxItems": OPENAI_VISUAL_MAX_OBSERVED_TEXT,
                        "items": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": OPENAI_VISUAL_OBSERVED_TEXT_MAX_CHARS,
                        },
                    },
                    "field_evidence": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["country", "denomination", "year", "type_design"],
                        "properties": {
                            field: {
                                "type": "array",
                                "maxItems": OPENAI_VISUAL_MAX_FIELD_EVIDENCE,
                                "items": {
                                    "type": "string",
                                    "minLength": 1,
                                    "maxLength": OPENAI_VISUAL_EVIDENCE_MAX_CHARS,
                                },
                            }
                            for field in ("country", "denomination", "year", "type_design")
                        },
                    },
                    "evidence_observations": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": OPENAI_VISUAL_MAX_EVIDENCE_OBSERVATIONS,
                        "items": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": OPENAI_VISUAL_EVIDENCE_MAX_CHARS,
                        },
                    },
                    "supporting_image_roles": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 2,
                        "items": {
                            "type": "string",
                            "enum": ["obverse", "reverse"],
                        },
                    },
                },
            },
        },
    },
}


class VisualIdentityContractError(ValueError):
    """A visual request or structured result violates the experiment contract."""


class VisualIdentityMalformedOutput(VisualIdentityContractError):
    """The provider returned output that cannot become a valid report."""

    raw_provider_output: object = None
    response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class VisualIdentityImage:
    role: str
    media_type: str
    data: bytes

    def __post_init__(self) -> None:
        if self.role not in {"obverse", "reverse"}:
            raise VisualIdentityContractError("image role must be obverse or reverse.")
        if self.media_type not in {"image/jpeg", "image/png"}:
            raise VisualIdentityContractError("image media type must be JPEG or PNG.")
        if not isinstance(self.data, bytes) or not self.data:
            raise VisualIdentityContractError("image data must be non-empty bytes.")


@dataclass(frozen=True, slots=True)
class VisualIdentityRequest:
    scan_id: str
    images: tuple[VisualIdentityImage, VisualIdentityImage]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.scan_id, str)
            or VISUAL_IDENTITY_SCAN_ID_PATTERN.fullmatch(self.scan_id) is None
        ):
            raise VisualIdentityContractError(
                "scan_id must contain only letters, numbers, underscores, or "
                "hyphens and be at most 64 characters."
            )
        if tuple(image.role for image in self.images) != ("obverse", "reverse"):
            raise VisualIdentityContractError(
                "images must contain exactly obverse then reverse."
            )


@dataclass(frozen=True, slots=True)
class VisualIdentityCandidate:
    rank: int
    country: str | None
    denomination: str | None
    year: str | None
    type_design: str | None
    confidence: float
    evidence_observations: tuple[str, ...]
    supporting_image_roles: tuple[str, ...]
    provider_id: str
    model_id: str
    observed_text: tuple[str, ...] = ()
    field_evidence: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @property
    def source_score(self) -> float:
        """Return the provider's uncalibrated source score."""

        return self.confidence

    def evidence_for(self, field: str) -> tuple[str, ...]:
        return dict(self.field_evidence).get(field, ())

    def as_prediction(self) -> dict[str, str]:
        prediction: dict[str, str] = {}
        if self.country is not None:
            prediction["country"] = self.country
        if self.denomination is not None:
            prediction["denomination"] = self.denomination
        if self.year is not None:
            prediction["year"] = self.year
        if self.type_design is not None:
            prediction["type_design"] = self.type_design
        return prediction


@dataclass(frozen=True, slots=True)
class VisualIdentityReport:
    outcome: str
    candidates: tuple[VisualIdentityCandidate, ...]
    provider_id: str
    model_id: str
    response_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    raw_structured_result: Mapping[str, object]
    # Evaluation-only retained candidates may include candidates hidden by a
    # public abstention. Production providers leave this empty and preserve
    # their existing public outcome.
    diagnostic_candidates: tuple[VisualIdentityCandidate, ...] = ()


@runtime_checkable
class VisualIdentityProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def model_id(self) -> str: ...

    def identify(self, request: VisualIdentityRequest) -> VisualIdentityReport: ...


class OpenAITerraVisualIdentityProvider:
    """One immutable GPT-5.6 Terra Responses API experiment configuration."""

    provider_id = OPENAI_VISUAL_PROVIDER_ID
    model_id = OPENAI_VISUAL_MODEL_ID

    def __init__(
        self,
        *,
        client: object | None = None,
        telemetry_sink: TelemetrySink | None = None,
    ) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI()
        self._client = client
        self._telemetry_sink = telemetry_sink

    @property
    def configuration(self) -> Mapping[str, object]:
        return {
            "api": "Responses API",
            "provider": "OpenAI",
            "provider_id": self.provider_id,
            "model": self.model_id,
            "reasoning_effort": OPENAI_VISUAL_REASONING_EFFORT,
            "image_detail": OPENAI_VISUAL_IMAGE_DETAIL,
            "max_output_tokens": OPENAI_VISUAL_MAX_OUTPUT_TOKENS,
            "previous_max_output_tokens": PREVIOUS_OPENAI_VISUAL_MAX_OUTPUT_TOKENS,
            "max_candidates": OPENAI_VISUAL_MAX_CANDIDATES,
            "max_evidence_observations": OPENAI_VISUAL_MAX_EVIDENCE_OBSERVATIONS,
            "max_observed_text": OPENAI_VISUAL_MAX_OBSERVED_TEXT,
            "max_field_evidence": OPENAI_VISUAL_MAX_FIELD_EVIDENCE,
            "evidence_observation_max_chars": OPENAI_VISUAL_EVIDENCE_MAX_CHARS,
            "country_max_chars": OPENAI_VISUAL_COUNTRY_MAX_CHARS,
            "denomination_max_chars": OPENAI_VISUAL_DENOMINATION_MAX_CHARS,
            "year_max_chars": OPENAI_VISUAL_YEAR_MAX_CHARS,
            "type_design_max_chars": OPENAI_VISUAL_TYPE_DESIGN_MAX_CHARS,
            "tools": [],
            "store": False,
            "prompt": OPENAI_VISUAL_PROMPT,
            "structured_output_schema": OPENAI_VISUAL_OUTPUT_SCHEMA,
        }

    def identify(self, request: VisualIdentityRequest) -> VisualIdentityReport:
        if not isinstance(request, VisualIdentityRequest):
            raise VisualIdentityContractError("request must be VisualIdentityRequest.")
        return instrument_inference(
            lambda: self._identify(request),
            scan_id=request.scan_id,
            stage="visual-identity",
            provider="OpenAI",
            model=self.model_id,
            sink=self._telemetry_sink,
            usage_resolver=lambda report: (report.input_tokens, report.output_tokens),
            error_usage_resolver=lambda error: (
                getattr(error, "input_tokens", None),
                getattr(error, "output_tokens", None),
            ),
        )

    def _identify(self, request: VisualIdentityRequest) -> VisualIdentityReport:
        content: list[dict[str, object]] = [
            {"type": "input_text", "text": OPENAI_VISUAL_PROMPT}
        ]
        for image in request.images:
            encoded = base64.b64encode(image.data).decode("ascii")
            content.append(
                {
                    "type": "input_image",
                    "detail": OPENAI_VISUAL_IMAGE_DETAIL,
                    "image_url": f"data:{image.media_type};base64,{encoded}",
                }
            )
        response = self._client.responses.create(
            model=self.model_id,
            input=[{"role": "user", "content": content}],
            reasoning={"effort": OPENAI_VISUAL_REASONING_EFFORT},
            text={
                "format": {
                    "type": "json_schema",
                    "name": "visual_identity_report",
                    "strict": True,
                    "schema": OPENAI_VISUAL_OUTPUT_SCHEMA,
                },
                "verbosity": "low",
            },
            tools=[],
            max_output_tokens=OPENAI_VISUAL_MAX_OUTPUT_TOKENS,
            store=False,
        )
        output_text = getattr(response, "output_text", None)
        try:
            raw = json.loads(output_text)
        except (AttributeError, TypeError, json.JSONDecodeError) as error:
            malformed = VisualIdentityMalformedOutput(
                "provider response is not schema-valid JSON output."
            )
            _attach_response_context(malformed, output_text, response)
            raise malformed from error
        try:
            return _validated_report(raw, response)
        except VisualIdentityMalformedOutput as error:
            _attach_response_context(error, raw, response)
            raise


def _validated_report(raw: object, response: object) -> VisualIdentityReport:
    if not isinstance(raw, Mapping) or set(raw) != {"outcome", "candidates"}:
        raise VisualIdentityMalformedOutput("structured result has unexpected fields.")
    outcome = raw.get("outcome")
    rows = raw.get("candidates")
    if outcome not in {"CANDIDATES", "ABSTAINED"} or not isinstance(rows, list):
        raise VisualIdentityMalformedOutput("structured outcome or candidates is invalid.")
    if len(rows) > OPENAI_VISUAL_MAX_CANDIDATES:
        raise VisualIdentityMalformedOutput("too many visual candidates.")
    if (outcome == "CANDIDATES") != bool(rows):
        raise VisualIdentityMalformedOutput("outcome and candidates disagree.")
    candidates = tuple(
        sorted((_validated_candidate(row) for row in rows), key=lambda item: item.rank)
    )
    if tuple(item.rank for item in candidates) != tuple(range(1, len(candidates) + 1)):
        raise VisualIdentityMalformedOutput(
            "candidate ranks must be unique and contiguous."
        )
    usage = getattr(response, "usage", None)
    input_tokens = _token_count(getattr(usage, "input_tokens", None))
    output_tokens = _token_count(getattr(usage, "output_tokens", None))
    response_id = getattr(response, "id", None)
    return VisualIdentityReport(
        outcome=str(outcome),
        candidates=candidates,
        provider_id=OPENAI_VISUAL_PROVIDER_ID,
        model_id=OPENAI_VISUAL_MODEL_ID,
        response_id=response_id if isinstance(response_id, str) else None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        raw_structured_result=dict(raw),
    )


def _validated_candidate(raw: object) -> VisualIdentityCandidate:
    required = {
        "rank",
        "country",
        "denomination",
        "year",
        "type_design",
        "confidence",
        "observed_text",
        "field_evidence",
        "evidence_observations",
        "supporting_image_roles",
    }
    if not isinstance(raw, Mapping) or set(raw) != required:
        raise VisualIdentityMalformedOutput("candidate fields do not match the contract.")
    rank = raw["rank"]
    confidence = raw["confidence"]
    if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= 3:
        raise VisualIdentityMalformedOutput("candidate rank is invalid.")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        raise VisualIdentityMalformedOutput("candidate confidence is invalid.")
    observations = _bounded_string_list(
        raw["evidence_observations"],
        "evidence observations",
        maximum_items=OPENAI_VISUAL_MAX_EVIDENCE_OBSERVATIONS,
        maximum_chars=OPENAI_VISUAL_EVIDENCE_MAX_CHARS,
    )
    observed_text = _bounded_optional_string_list(
        raw["observed_text"],
        "observed text",
        maximum_items=OPENAI_VISUAL_MAX_OBSERVED_TEXT,
        maximum_chars=OPENAI_VISUAL_OBSERVED_TEXT_MAX_CHARS,
    )
    raw_field_evidence = raw["field_evidence"]
    fields = ("country", "denomination", "year", "type_design")
    if (
        not isinstance(raw_field_evidence, Mapping)
        or set(raw_field_evidence) != set(fields)
    ):
        raise VisualIdentityMalformedOutput("candidate field evidence is invalid.")
    field_evidence = tuple(
        (
            field,
            _bounded_optional_string_list(
                raw_field_evidence[field],
                f"{field} evidence",
                maximum_items=OPENAI_VISUAL_MAX_FIELD_EVIDENCE,
                maximum_chars=OPENAI_VISUAL_EVIDENCE_MAX_CHARS,
            ),
        )
        for field in fields
    )
    roles = raw["supporting_image_roles"]
    if (
        not isinstance(roles, list)
        or not 1 <= len(roles) <= 2
        or len(set(roles)) != len(roles)
        or any(role not in {"obverse", "reverse"} for role in roles)
    ):
        raise VisualIdentityMalformedOutput("supporting image roles are invalid.")
    country = _optional_bounded_text(
        raw["country"], "country", OPENAI_VISUAL_COUNTRY_MAX_CHARS
    )
    denomination = _optional_bounded_text(
        raw["denomination"],
        "denomination",
        OPENAI_VISUAL_DENOMINATION_MAX_CHARS,
    )
    year = _optional_bounded_text(
        raw["year"], "year", OPENAI_VISUAL_YEAR_MAX_CHARS
    )
    type_design = _optional_bounded_text(
        raw["type_design"], "type_design", OPENAI_VISUAL_TYPE_DESIGN_MAX_CHARS
    )
    values = dict(zip(fields, (country, denomination, year, type_design)))
    evidence_by_field = dict(field_evidence)
    if not any(values.values()):
        raise VisualIdentityMalformedOutput("candidate must propose at least one field.")
    if any(
        value is not None and not evidence_by_field[field]
        for field, value in values.items()
    ):
        raise VisualIdentityMalformedOutput("every proposed field requires field evidence.")
    if any(value is None and evidence_by_field[field] for field, value in values.items()):
        raise VisualIdentityMalformedOutput(
            "field evidence cannot support a field that was not proposed."
        )
    if year is not None and year not in observed_text:
        raise VisualIdentityMalformedOutput(
            "a proposed year must occur verbatim in observed text."
        )
    return VisualIdentityCandidate(
        rank=rank,
        country=country,
        denomination=denomination,
        year=year,
        type_design=type_design,
        confidence=float(confidence),
        evidence_observations=observations,
        supporting_image_roles=tuple(roles),
        provider_id=OPENAI_VISUAL_PROVIDER_ID,
        model_id=OPENAI_VISUAL_MODEL_ID,
        observed_text=observed_text,
        field_evidence=field_evidence,
    )


def _bounded_text(value: object, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise VisualIdentityMalformedOutput(f"candidate {name} is invalid.")
    return value.strip()


def _optional_bounded_text(value: object, name: str, limit: int) -> str | None:
    if value is None:
        return None
    return _bounded_text(value, name, limit)


def _bounded_string_list(
    value: object,
    name: str,
    *,
    maximum_items: int,
    maximum_chars: int,
) -> tuple[str, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= maximum_items:
        raise VisualIdentityMalformedOutput(f"candidate {name} are invalid.")
    result = tuple(_bounded_text(item, name, maximum_chars) for item in value)
    if len(set(result)) != len(result):
        raise VisualIdentityMalformedOutput(f"candidate {name} contain duplicates.")
    return result


def _bounded_optional_string_list(
    value: object,
    name: str,
    *,
    maximum_items: int,
    maximum_chars: int,
) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum_items:
        raise VisualIdentityMalformedOutput(f"candidate {name} are invalid.")
    result = tuple(_bounded_text(item, name, maximum_chars) for item in value)
    if len(set(result)) != len(result):
        raise VisualIdentityMalformedOutput(f"candidate {name} contain duplicates.")
    return result


def _token_count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _attach_response_context(
    error: VisualIdentityMalformedOutput,
    raw: object,
    response: object,
) -> None:
    usage = getattr(response, "usage", None)
    error.raw_provider_output = raw
    response_id = getattr(response, "id", None)
    error.response_id = response_id if isinstance(response_id, str) else None
    error.input_tokens = _token_count(getattr(usage, "input_tokens", None))
    error.output_tokens = _token_count(getattr(usage, "output_tokens", None))
