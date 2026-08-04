"""Immutable OCR metadata contracts for the deterministic import workflow.

These models describe advisory OCR observations and metadata candidates before
any UI review or durable collection mutation. They do not invoke an OCR engine,
read image files, persist results, or authorize collection changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, NamedTuple, Protocol, runtime_checkable
import math
import unicodedata

from .workflow_models import JsonValue


MAX_OCR_TEXT_CHARS = 4096
MAX_OCR_VALUE_CHARS = 512
MAX_OCR_REASON_CHARS = 1024
MAX_OCR_PROVIDER_ID_CHARS = 128
MAX_OCR_ARTIFACT_KEY_CHARS = 255
MAX_OCR_EVIDENCE_ITEMS = 8
MAX_OCR_CONFLICT_VALUES = 8
MAX_OCR_OBSERVATIONS = 300
MAX_OCR_CANDIDATES = 300
MAX_OCR_CONFLICTS = 100

ALLOWED_OCR_FIELDS = frozenset(
    {
        "year",
        "denomination",
        "country",
        "monarch",
        "mintmark",
        "series_type",
        "banknote_prefix",
        "certification_number",
        "silver_indicator",
        "variety_keyword",
    }
)

ALLOWED_IMAGE_ROLES = frozenset({"front", "reverse", "edge"})


class OCRReviewStatus(str, Enum):
    """Review state for advisory OCR metadata."""

    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CONFLICT = "CONFLICT"
    UNAVAILABLE = "UNAVAILABLE"


class OCRFieldIdentity(NamedTuple):
    """Canonical tuple-like identity for one OCR field candidate or decision.

    The tuple ordering is intentionally stable so existing dictionary and set
    lookups continue to work unchanged while callers can read named attributes.
    """

    source_coin_id: str
    image_role: str
    artifact_key: str
    provider_id: str
    field_name: str
    value: str


def _require_text(
    value: Any,
    name: str,
    *,
    maximum: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string.")
    if not allow_empty and not value:
        raise ValueError(f"{name} must not be empty.")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds its character limit.")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must already be NFC-normalized.")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{name} must not contain control characters.")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError(f"{name} must not contain surrogate code points.")
    return value


def _require_confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("confidence_score must be numeric.")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 100.0:
        raise ValueError("confidence_score must be finite and between 0 and 100.")
    return result


def _validate_field_name(value: Any) -> str:
    text = _require_text(value, "field_name", maximum=64)
    if text not in ALLOWED_OCR_FIELDS:
        raise ValueError("field_name is not supported.")
    return text


def _validate_role(value: Any) -> str:
    text = _require_text(value, "image_role", maximum=16)
    if text not in ALLOWED_IMAGE_ROLES:
        raise ValueError("image_role must be front, reverse, or edge.")
    return text


def _validate_string_tuple(
    value: Any,
    name: str,
    *,
    maximum_items: int,
    maximum_chars: int,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be an immutable tuple.")
    if len(value) > maximum_items:
        raise ValueError(f"{name} contains too many values.")

    validated = tuple(
        _require_text(item, name, maximum=maximum_chars)
        for item in value
    )
    if len(set(validated)) != len(validated):
        raise ValueError(f"{name} must not contain duplicate values.")
    if validated != tuple(sorted(validated)):
        raise ValueError(f"{name} must use deterministic sorted order.")
    return validated


@dataclass(frozen=True, slots=True)
class OCRObservation:
    """Raw advisory text observed from one processed image artifact."""

    source_coin_id: str
    image_role: str
    artifact_key: str
    provider_id: str
    raw_text: str
    confidence_score: float

    def validate(self) -> None:
        _require_text(
            self.source_coin_id,
            "source_coin_id",
            maximum=16_384,
        )
        _validate_role(self.image_role)
        _require_text(
            self.artifact_key,
            "artifact_key",
            maximum=MAX_OCR_ARTIFACT_KEY_CHARS,
        )
        if "/" in self.artifact_key or "\\" in self.artifact_key:
            raise ValueError("artifact_key must be an identifier, not a path.")
        _require_text(
            self.provider_id,
            "provider_id",
            maximum=MAX_OCR_PROVIDER_ID_CHARS,
        )
        _require_text(
            self.raw_text,
            "raw_text",
            maximum=MAX_OCR_TEXT_CHARS,
            allow_empty=True,
        )
        _require_confidence(self.confidence_score)

    def to_dict(self) -> dict[str, JsonValue]:
        self.validate()
        return {
            "source_coin_id": self.source_coin_id,
            "image_role": self.image_role,
            "artifact_key": self.artifact_key,
            "provider_id": self.provider_id,
            "raw_text": self.raw_text,
            "confidence_score": float(self.confidence_score),
        }


@dataclass(frozen=True, slots=True)
class OCRFieldCandidate:
    """One normalized, non-authoritative metadata suggestion."""

    source_coin_id: str
    image_role: str
    artifact_key: str
    provider_id: str
    field_name: str
    raw_text: str
    normalized_value: str
    confidence_score: float
    evidence: tuple[str, ...] = ()
    review_status: OCRReviewStatus = OCRReviewStatus.REVIEW_REQUIRED

    def validate(self) -> None:
        _require_text(
            self.source_coin_id,
            "source_coin_id",
            maximum=16_384,
        )
        _validate_role(self.image_role)
        _require_text(
            self.artifact_key,
            "artifact_key",
            maximum=MAX_OCR_ARTIFACT_KEY_CHARS,
        )
        if "/" in self.artifact_key or "\\" in self.artifact_key:
            raise ValueError("artifact_key must be an identifier, not a path.")
        _require_text(
            self.provider_id,
            "provider_id",
            maximum=MAX_OCR_PROVIDER_ID_CHARS,
        )
        _validate_field_name(self.field_name)
        _require_text(
            self.raw_text,
            "raw_text",
            maximum=MAX_OCR_TEXT_CHARS,
            allow_empty=True,
        )
        _require_text(
            self.normalized_value,
            "normalized_value",
            maximum=MAX_OCR_VALUE_CHARS,
        )
        _require_confidence(self.confidence_score)
        _validate_string_tuple(
            self.evidence,
            "evidence",
            maximum_items=MAX_OCR_EVIDENCE_ITEMS,
            maximum_chars=MAX_OCR_VALUE_CHARS,
        )
        if not isinstance(self.review_status, OCRReviewStatus):
            raise ValueError("review_status must be an OCRReviewStatus.")
        if self.review_status is OCRReviewStatus.UNAVAILABLE:
            raise ValueError("field candidates cannot have UNAVAILABLE status.")

    @property
    def identity_key(self) -> OCRFieldIdentity:
        return OCRFieldIdentity(
            source_coin_id=self.source_coin_id,
            image_role=self.image_role,
            artifact_key=self.artifact_key,
            provider_id=self.provider_id,
            field_name=self.field_name,
            value=self.normalized_value,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        self.validate()
        return {
            "source_coin_id": self.source_coin_id,
            "image_role": self.image_role,
            "artifact_key": self.artifact_key,
            "provider_id": self.provider_id,
            "field_name": self.field_name,
            "raw_text": self.raw_text,
            "normalized_value": self.normalized_value,
            "confidence_score": float(self.confidence_score),
            "evidence": list(self.evidence),
            "review_status": self.review_status.value,
        }


@dataclass(frozen=True, slots=True)
class OCRConflict:
    """Unresolved disagreement between OCR metadata candidates."""

    source_coin_id: str
    field_name: str
    candidate_values: tuple[str, ...]
    reason: str
    review_status: OCRReviewStatus = OCRReviewStatus.CONFLICT

    def validate(self) -> None:
        _require_text(
            self.source_coin_id,
            "source_coin_id",
            maximum=16_384,
        )
        _validate_field_name(self.field_name)
        values = _validate_string_tuple(
            self.candidate_values,
            "candidate_values",
            maximum_items=MAX_OCR_CONFLICT_VALUES,
            maximum_chars=MAX_OCR_VALUE_CHARS,
        )
        if len(values) < 2:
            raise ValueError("candidate_values must contain at least two values.")
        _require_text(
            self.reason,
            "reason",
            maximum=MAX_OCR_REASON_CHARS,
        )
        if self.review_status is not OCRReviewStatus.CONFLICT:
            raise ValueError("OCR conflicts must have CONFLICT review status.")

    def to_dict(self) -> dict[str, JsonValue]:
        self.validate()
        return {
            "source_coin_id": self.source_coin_id,
            "field_name": self.field_name,
            "candidate_values": list(self.candidate_values),
            "reason": self.reason,
            "review_status": self.review_status.value,
        }


@dataclass(frozen=True, slots=True)
class OCRMetadataReport:
    """Bounded advisory OCR output for one workflow execution."""

    provider_available: bool
    observations: tuple[OCRObservation, ...] = ()
    candidates: tuple[OCRFieldCandidate, ...] = ()
    conflicts: tuple[OCRConflict, ...] = ()
    review_status: OCRReviewStatus = OCRReviewStatus.REVIEW_REQUIRED

    def validate(self) -> None:
        if not isinstance(self.provider_available, bool):
            raise ValueError("provider_available must be a boolean.")
        if not isinstance(self.observations, tuple):
            raise ValueError("observations must be an immutable tuple.")
        if not isinstance(self.candidates, tuple):
            raise ValueError("candidates must be an immutable tuple.")
        if not isinstance(self.conflicts, tuple):
            raise ValueError("conflicts must be an immutable tuple.")

        if len(self.observations) > MAX_OCR_OBSERVATIONS:
            raise ValueError("too many OCR observations.")
        if len(self.candidates) > MAX_OCR_CANDIDATES:
            raise ValueError("too many OCR field candidates.")
        if len(self.conflicts) > MAX_OCR_CONFLICTS:
            raise ValueError("too many OCR conflicts.")

        for observation in self.observations:
            if not isinstance(observation, OCRObservation):
                raise ValueError("observations contain an unsupported value.")
            observation.validate()

        for candidate in self.candidates:
            if not isinstance(candidate, OCRFieldCandidate):
                raise ValueError("candidates contain an unsupported value.")
            candidate.validate()

        for conflict in self.conflicts:
            if not isinstance(conflict, OCRConflict):
                raise ValueError("conflicts contain an unsupported value.")
            conflict.validate()

        observation_order = tuple(
            sorted(
                self.observations,
                key=lambda item: (
                    item.source_coin_id,
                    item.image_role,
                    item.artifact_key,
                    item.provider_id,
                    item.raw_text,
                ),
            )
        )
        if self.observations != observation_order:
            raise ValueError("observations are not in deterministic order.")

        candidate_order = tuple(
            sorted(
                self.candidates,
                key=lambda item: (
                    item.source_coin_id,
                    item.field_name,
                    item.image_role,
                    item.normalized_value,
                    item.provider_id,
                    item.artifact_key,
                ),
            )
        )
        if self.candidates != candidate_order:
            raise ValueError("candidates are not in deterministic order.")

        conflict_order = tuple(
            sorted(
                self.conflicts,
                key=lambda item: (
                    item.source_coin_id,
                    item.field_name,
                    item.candidate_values,
                ),
            )
        )
        if self.conflicts != conflict_order:
            raise ValueError("conflicts are not in deterministic order.")

        if not self.provider_available:
            if self.observations or self.candidates or self.conflicts:
                raise ValueError(
                    "unavailable providers cannot produce OCR results."
                )
            if self.review_status is not OCRReviewStatus.UNAVAILABLE:
                raise ValueError(
                    "unavailable providers require UNAVAILABLE review status."
                )
        elif self.conflicts:
            if self.review_status is not OCRReviewStatus.CONFLICT:
                raise ValueError(
                    "reports with conflicts require CONFLICT review status."
                )
        elif self.review_status is not OCRReviewStatus.REVIEW_REQUIRED:
            raise ValueError(
                "available OCR reports require REVIEW_REQUIRED status."
            )

    def to_dict(self) -> dict[str, JsonValue]:
        self.validate()
        return {
            "provider_available": self.provider_available,
            "observation_count": len(self.observations),
            "candidate_count": len(self.candidates),
            "conflict_count": len(self.conflicts),
            "review_status": self.review_status.value,
            "manual_review_required": True,
            "observations": [
                observation.to_dict() for observation in self.observations
            ],
            "candidates": [
                candidate.to_dict() for candidate in self.candidates
            ],
            "conflicts": [
                conflict.to_dict() for conflict in self.conflicts
            ],
        }


@runtime_checkable
class OCRProvider(Protocol):
    """Adapter boundary for a future OCR engine implementation."""

    @property
    def provider_id(self) -> str:
        ...

    def observe(
        self,
        *,
        source_coin_id: str,
        image_role: str,
        artifact_key: str,
        image_bytes: bytes,
    ) -> OCRObservation:
        ...