"""Isolated, opt-in local LLM resolver contract for benchmark/test use only."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol


_RESPONSE_KEYS = {
    "country",
    "denomination",
    "year",
    "candidate_id",
    "confidence",
    "reason",
    "abstain",
}


class LocalResolverError(RuntimeError):
    """Base failure for the standalone local resolver experiment."""


class LocalResolverDisabled(LocalResolverError):
    """Raised when the experiment is invoked without its explicit feature flag."""


class LocalResolverRuntimeError(LocalResolverError):
    """Raised when the injected local runtime cannot produce a response."""


class LocalResolverResponseError(LocalResolverError):
    """Raised when a local runtime response violates the strict JSON contract."""


@dataclass(frozen=True, slots=True)
class ResolverEvidence:
    """Bounded, provenance-safe evidence already produced by recognition code."""

    ocr_text: tuple[str, ...] = ()
    candidate_countries: tuple[str, ...] = ()
    candidate_denominations: tuple[str, ...] = ()
    candidate_years: tuple[str, ...] = ()
    candidate_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, list[str]]:
        return {
            "ocr_text": list(self.ocr_text),
            "candidate_countries": list(self.candidate_countries),
            "candidate_denominations": list(self.candidate_denominations),
            "candidate_years": list(self.candidate_years),
            "candidate_ids": list(self.candidate_ids),
        }


@dataclass(frozen=True, slots=True)
class ResolverResult:
    country: str | None
    denomination: str | None
    year: str | None
    candidate_id: str | None
    confidence: float | None
    reason: str
    abstain: bool


class LocalResolverRuntime(Protocol):
    """Injectable local-only runtime boundary used by the experiment."""

    def invoke(self, request_json: str) -> str:
        """Return the model's raw JSON response."""


class LocalLLMResolver:
    """Feature-gated adapter that validates a local runtime's strict JSON output."""

    def __init__(self, runtime: LocalResolverRuntime, *, enabled: bool = False) -> None:
        self._runtime = runtime
        self._enabled = enabled

    def resolve(self, evidence: ResolverEvidence) -> ResolverResult:
        if not self._enabled:
            raise LocalResolverDisabled("local LLM resolver experiment is disabled")

        request_json = json.dumps(
            {
                "schema": "coin-analyzer-local-resolver-v1",
                "evidence": evidence.to_payload(),
                "response_contract": {
                    "country": "string|null",
                    "denomination": "string|null",
                    "year": "string|null",
                    "candidate_id": "string|null",
                    "confidence": "number|null",
                    "reason": "string",
                    "abstain": "boolean",
                },
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        try:
            raw = self._runtime.invoke(request_json)
        except Exception as exc:
            raise LocalResolverRuntimeError(
                f"local resolver runtime failed: {type(exc).__name__}: {exc}"
            ) from exc

        return _parse_response(raw)


def _optional_text(payload: dict[str, object], field: str) -> str | None:
    value = payload[field]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise LocalResolverResponseError(f"{field} must be a non-empty string or null")
    return value.strip()


def _parse_response(raw: object) -> ResolverResult:
    if not isinstance(raw, str):
        raise LocalResolverResponseError("runtime response must be a JSON string")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LocalResolverResponseError("runtime response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise LocalResolverResponseError("runtime response must be a JSON object")
    if set(payload) != _RESPONSE_KEYS:
        missing = sorted(_RESPONSE_KEYS.difference(payload))
        extra = sorted(set(payload).difference(_RESPONSE_KEYS))
        raise LocalResolverResponseError(
            f"runtime response schema mismatch; missing={missing}, extra={extra}"
        )

    confidence_raw = payload["confidence"]
    if confidence_raw is None:
        confidence = None
    elif isinstance(confidence_raw, bool) or not isinstance(confidence_raw, (int, float)):
        raise LocalResolverResponseError("confidence must be numeric or null")
    else:
        confidence = float(confidence_raw)

    reason_raw = payload["reason"]
    if not isinstance(reason_raw, str) or not reason_raw.strip():
        raise LocalResolverResponseError("reason must be a non-empty string")
    abstain_raw = payload["abstain"]
    if not isinstance(abstain_raw, bool):
        raise LocalResolverResponseError("abstain must be boolean")

    return ResolverResult(
        country=_optional_text(payload, "country"),
        denomination=_optional_text(payload, "denomination"),
        year=_optional_text(payload, "year"),
        candidate_id=_optional_text(payload, "candidate_id"),
        confidence=confidence,
        reason=reason_raw.strip(),
        abstain=abstain_raw,
    )
