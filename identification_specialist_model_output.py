"""Strict synthetic model-output boundary; no real provider payload is defined.

Candidate IDs alone are not sufficient input for real identification. Actual
image/evidence content and real transports require separate authorization.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from typing import NoReturn

from identification_specialist import (
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
)
from identification_specialist_execution import IdentificationSpecialistExecutor


IDENTIFICATION_MODEL_SCHEMA_VERSION = "1"
MAX_MODEL_RESPONSE_CHARS = 262_144
_RESPONSE_FIELDS = frozenset({"schema_version", "candidate_id", "abstained"})


@dataclass(frozen=True, slots=True)
class IdentificationModelRequest:
    """Adapter-created synthetic projection, not a real-provider payload."""

    schema_version: str
    candidate_ids: tuple[str, ...]


IdentificationModelTransport = Callable[[IdentificationModelRequest], str]


def _validate_request(request: IdentificationSpecialistRequest) -> None:
    if not isinstance(request, IdentificationSpecialistRequest):
        raise TypeError("request must be an IdentificationSpecialistRequest.")
    request.validate()


def _object_without_duplicates(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Model response contains duplicate JSON keys.")
        value[key] = item
    return value


def _reject_constant(value: str) -> NoReturn:
    raise ValueError("Model response contains a non-JSON numeric constant.")


def parse_identification_model_output(
    request: IdentificationSpecialistRequest,
    raw_response: str,
) -> IdentificationSpecialistResult:
    """Decode one strict observed decision without repair or policy inference."""

    _validate_request(request)
    if not isinstance(raw_response, str):
        raise TypeError("raw_response must be JSON text.")
    if len(raw_response) > MAX_MODEL_RESPONSE_CHARS:
        raise ValueError("Model response exceeds its character limit.")
    try:
        raw_response.encode("utf-8", errors="strict")
        payload = json.loads(
            raw_response,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("Model response must be valid bounded JSON.") from error
    if not isinstance(payload, dict):
        raise ValueError("Model response must be a JSON object.")
    if payload.keys() != _RESPONSE_FIELDS:
        raise ValueError("Model response fields must match the schema exactly.")

    version = payload["schema_version"]
    if not isinstance(version, str):
        raise TypeError("schema_version must be a string.")
    if version != IDENTIFICATION_MODEL_SCHEMA_VERSION:
        raise ValueError("Unsupported model response schema_version.")
    candidate_id = payload["candidate_id"]
    abstained = payload["abstained"]
    if candidate_id is not None and not isinstance(candidate_id, str):
        raise TypeError("candidate_id must be a string or null.")
    if not isinstance(abstained, bool):
        raise TypeError("abstained must be a boolean.")
    if candidate_id is not None:
        try:
            candidate_id.encode("utf-8", errors="strict")
        except UnicodeError as error:
            raise ValueError("candidate_id must contain valid Unicode.") from error

    result = IdentificationSpecialistResult(
        schema_version=request.schema_version,
        case_id=request.case_id,
        candidate_id=candidate_id,
        abstained=abstained,
        evidence_refs=request.evidence_refs,
    )
    result.validate()
    if candidate_id is not None and candidate_id not in request.candidate_ids:
        raise ValueError("candidate_id is not authorized by the request.")
    return result


def create_model_identification_executor(
    executor_id: str,
    transport: IdentificationModelTransport,
) -> IdentificationSpecialistExecutor:
    """Bind a trusted injected transport to the unchanged execution seam.

    Only a synthetic projection is sent. No EvaluationCase, evidence, case ID,
    eligibility, prompts, or actual content is exposed by this adapter.
    """

    if not callable(transport):
        raise TypeError("transport must be callable.")

    def execute(
        request: IdentificationSpecialistRequest,
    ) -> IdentificationSpecialistResult:
        _validate_request(request)
        model_request = IdentificationModelRequest(
            schema_version=IDENTIFICATION_MODEL_SCHEMA_VERSION,
            candidate_ids=request.candidate_ids,
        )
        raw_response = transport(model_request)
        return parse_identification_model_output(request, raw_response)

    executor = IdentificationSpecialistExecutor(executor_id, execute)
    executor.validate()
    return executor
