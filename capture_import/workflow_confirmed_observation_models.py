"""Immutable, collection-independent human-confirmed metadata contracts.

These contracts form a trust boundary for future mapping.  They preserve exact
submitted and optional canonical values plus bounded provenance, but they do not
map OCR projections, normalize values, persist observations, inspect collection
records, plan changes, or authorize mutation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import math
import unicodedata
from typing import Any


CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION = "1"

_MAX_ID_CHARS = 16_384
_MAX_FIELD_NAME_CHARS = 128
_MAX_VALUE_CHARS = 4_096
_MAX_REVIEWER_ID_CHARS = 256
_MAX_PROVIDER_ID_CHARS = 256
_MAX_IMAGE_ROLE_CHARS = 64
_MAX_ARTIFACT_KEY_CHARS = 1_024
_MAX_EVIDENCE_ITEM_CHARS = 4_096
_MAX_EVIDENCE_ITEMS = 32
_MAX_RATIONALE_CHARS = 4_096
_MAX_OBSERVATIONS = 300
_MAX_PROVENANCE_ITEMS = 64
_MAX_SESSION_ID_CHARS = 256
_MAX_SOURCE_FINGERPRINT_CHARS = 4_096

_PROVENANCE_FIELDS = frozenset(
    {
        "provider_id",
        "image_role",
        "artifact_key",
        "source_value",
        "confidence_score",
        "evidence",
    }
)
_OBSERVATION_FIELDS = frozenset(
    {
        "schema_version",
        "source_coin_id",
        "field_name",
        "submitted_value",
        "canonical_value",
        "reviewer_id",
        "provenance",
        "source_type",
        "rationale",
    }
)
_SET_FIELDS = frozenset(
    {
        "schema_version",
        "source_coin_id",
        "reviewer_id",
        "observations",
        "review_session_id",
        "source_fingerprint",
    }
)
_UNCONFIRMED_VALUE_MARKERS = frozenset(
    {
        "defer",
        "deferred",
        "missing",
        "reject",
        "rejected",
        "unresolved",
    }
)


class UnsupportedConfirmedObservationSchemaVersion(ValueError):
    """The confirmed-observation schema version is not supported."""


class ConfirmedObservationSource(str, Enum):
    """Explicit origin of one human-confirmed field."""

    OCR_REVIEW = "OCR_REVIEW"
    MANUAL_ENTRY = "MANUAL_ENTRY"


@dataclass(frozen=True, slots=True)
class ConfirmedObservationProvenance:
    """Bounded immutable lineage for one submitted field value."""

    provider_id: str
    image_role: str
    artifact_key: str
    source_value: str
    confidence_score: float | None = None
    evidence: tuple[str, ...] = ()

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (
            self.provider_id,
            self.image_role,
            self.artifact_key,
            self.source_value,
        )

    def validate(self) -> None:
        _text(
            self.provider_id,
            "provider_id",
            maximum=_MAX_PROVIDER_ID_CHARS,
        )
        _text(
            self.image_role,
            "image_role",
            maximum=_MAX_IMAGE_ROLE_CHARS,
        )
        _text(
            self.artifact_key,
            "artifact_key",
            maximum=_MAX_ARTIFACT_KEY_CHARS,
        )
        _text(
            self.source_value,
            "source_value",
            maximum=_MAX_VALUE_CHARS,
        )
        _confidence(self.confidence_score)
        if not isinstance(self.evidence, tuple):
            raise TypeError("evidence must be a tuple.")
        if len(self.evidence) > _MAX_EVIDENCE_ITEMS:
            raise ValueError("evidence contains too many items.")
        for index, item in enumerate(self.evidence):
            _text(
                item,
                f"evidence[{index}]",
                maximum=_MAX_EVIDENCE_ITEM_CHARS,
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "provider_id": self.provider_id,
            "image_role": self.image_role,
            "artifact_key": self.artifact_key,
            "source_value": self.source_value,
            "confidence_score": (
                None
                if self.confidence_score is None
                else float(self.confidence_score)
            ),
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "ConfirmedObservationProvenance":
        data = _object(value, "ConfirmedObservationProvenance")
        _fields(
            data,
            _PROVENANCE_FIELDS,
            "ConfirmedObservationProvenance",
        )
        evidence = _list(data["evidence"], "evidence")
        result = cls(
            provider_id=_string_value(data["provider_id"], "provider_id"),
            image_role=_string_value(data["image_role"], "image_role"),
            artifact_key=_string_value(
                data["artifact_key"],
                "artifact_key",
            ),
            source_value=_string_value(
                data["source_value"],
                "source_value",
            ),
            confidence_score=_optional_number(
                data["confidence_score"],
                "confidence_score",
            ),
            evidence=tuple(
                _string_value(item, f"evidence[{index}]")
                for index, item in enumerate(evidence)
            ),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class ConfirmedFieldObservation:
    """One scalar metadata field explicitly confirmed by a human."""

    schema_version: str
    source_coin_id: str
    field_name: str
    submitted_value: str
    canonical_value: str | None
    reviewer_id: str
    provenance: tuple[ConfirmedObservationProvenance, ...]
    source_type: ConfirmedObservationSource
    rationale: str | None = None

    @property
    def identity(self) -> tuple[str, str]:
        return (self.source_coin_id, self.field_name)

    def validate(self) -> None:
        _schema(self.schema_version)
        _text(
            self.source_coin_id,
            "source_coin_id",
            maximum=_MAX_ID_CHARS,
        )
        field_name = _text(
            self.field_name,
            "field_name",
            maximum=_MAX_FIELD_NAME_CHARS,
        )
        if field_name.strip().casefold() == "grade":
            raise ValueError("Confirmed observations must not include grade.")
        submitted = _text(
            self.submitted_value,
            "submitted_value",
            maximum=_MAX_VALUE_CHARS,
        )
        _confirmed_value(submitted, "submitted_value")
        if self.canonical_value is not None:
            canonical = _text(
                self.canonical_value,
                "canonical_value",
                maximum=_MAX_VALUE_CHARS,
            )
            _confirmed_value(canonical, "canonical_value")
        _text(
            self.reviewer_id,
            "reviewer_id",
            maximum=_MAX_REVIEWER_ID_CHARS,
        )
        if not isinstance(self.source_type, ConfirmedObservationSource):
            raise TypeError(
                "source_type must be a ConfirmedObservationSource."
            )
        if self.rationale is not None:
            _text(
                self.rationale,
                "rationale",
                maximum=_MAX_RATIONALE_CHARS,
            )
        if not isinstance(self.provenance, tuple):
            raise TypeError("provenance must be a tuple.")
        if len(self.provenance) > _MAX_PROVENANCE_ITEMS:
            raise ValueError("provenance contains too many items.")
        if (
            self.source_type is ConfirmedObservationSource.OCR_REVIEW
            and not self.provenance
        ):
            raise ValueError(
                "OCR_REVIEW confirmed observations require provenance."
            )
        if any(
            not isinstance(item, ConfirmedObservationProvenance)
            for item in self.provenance
        ):
            raise TypeError(
                "provenance must contain "
                "ConfirmedObservationProvenance values."
            )
        expected_order = tuple(
            sorted(self.provenance, key=lambda item: item.identity)
        )
        if self.provenance != expected_order:
            raise ValueError(
                "provenance must be in deterministic identity order."
            )
        identities: set[tuple[str, str, str, str]] = set()
        for item in self.provenance:
            item.validate()
            if item.identity in identities:
                raise ValueError("Duplicate confirmed provenance identity.")
            identities.add(item.identity)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "source_coin_id": self.source_coin_id,
            "field_name": self.field_name,
            "submitted_value": self.submitted_value,
            "canonical_value": self.canonical_value,
            "reviewer_id": self.reviewer_id,
            "provenance": [item.to_dict() for item in self.provenance],
            "source_type": self.source_type.value,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "ConfirmedFieldObservation":
        data = _object(value, "ConfirmedFieldObservation")
        _fields(data, _OBSERVATION_FIELDS, "ConfirmedFieldObservation")
        schema_version = _string_value(
            data["schema_version"],
            "schema_version",
        )
        _schema(schema_version)
        provenance = _list(data["provenance"], "provenance")
        result = cls(
            schema_version=schema_version,
            source_coin_id=_string_value(
                data["source_coin_id"],
                "source_coin_id",
            ),
            field_name=_string_value(data["field_name"], "field_name"),
            submitted_value=_string_value(
                data["submitted_value"],
                "submitted_value",
            ),
            canonical_value=_optional_string_value(
                data["canonical_value"],
                "canonical_value",
            ),
            reviewer_id=_string_value(
                data["reviewer_id"],
                "reviewer_id",
            ),
            provenance=tuple(
                ConfirmedObservationProvenance.from_dict(item)
                for item in provenance
            ),
            source_type=_enum(
                ConfirmedObservationSource,
                data["source_type"],
                "source_type",
            ),
            rationale=_optional_string_value(
                data["rationale"],
                "rationale",
            ),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class ConfirmedObservationSet:
    """All scalar fields confirmed by one reviewer for one source coin."""

    schema_version: str
    source_coin_id: str
    reviewer_id: str
    observations: tuple[ConfirmedFieldObservation, ...]
    review_session_id: str | None = None
    source_fingerprint: str | None = None

    def validate(self) -> None:
        _schema(self.schema_version)
        source_coin_id = _text(
            self.source_coin_id,
            "source_coin_id",
            maximum=_MAX_ID_CHARS,
        )
        reviewer_id = _text(
            self.reviewer_id,
            "reviewer_id",
            maximum=_MAX_REVIEWER_ID_CHARS,
        )
        if self.review_session_id is not None:
            _text(
                self.review_session_id,
                "review_session_id",
                maximum=_MAX_SESSION_ID_CHARS,
            )
        if self.source_fingerprint is not None:
            _text(
                self.source_fingerprint,
                "source_fingerprint",
                maximum=_MAX_SOURCE_FINGERPRINT_CHARS,
            )
        if not isinstance(self.observations, tuple):
            raise TypeError("observations must be a tuple.")
        if not self.observations:
            raise ValueError(
                "observations must contain at least one confirmed field."
            )
        if len(self.observations) > _MAX_OBSERVATIONS:
            raise ValueError("observations contains too many fields.")
        if any(
            not isinstance(item, ConfirmedFieldObservation)
            for item in self.observations
        ):
            raise TypeError(
                "observations must contain "
                "ConfirmedFieldObservation values."
            )
        expected_order = tuple(
            sorted(self.observations, key=lambda item: item.field_name)
        )
        if self.observations != expected_order:
            raise ValueError(
                "observations must be in deterministic field-name order."
            )
        field_names: set[str] = set()
        for observation in self.observations:
            observation.validate()
            if observation.source_coin_id != source_coin_id:
                raise ValueError(
                    "All confirmed observations must use the aggregate "
                    "source_coin_id."
                )
            if observation.reviewer_id != reviewer_id:
                raise ValueError(
                    "All confirmed observations must use the aggregate "
                    "reviewer_id."
                )
            if observation.field_name in field_names:
                raise ValueError("Duplicate confirmed field name.")
            field_names.add(observation.field_name)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "source_coin_id": self.source_coin_id,
            "reviewer_id": self.reviewer_id,
            "observations": [
                observation.to_dict()
                for observation in self.observations
            ],
            "review_session_id": self.review_session_id,
            "source_fingerprint": self.source_fingerprint,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "ConfirmedObservationSet":
        data = _object(value, "ConfirmedObservationSet")
        _fields(data, _SET_FIELDS, "ConfirmedObservationSet")
        schema_version = _string_value(
            data["schema_version"],
            "schema_version",
        )
        _schema(schema_version)
        observations = _list(data["observations"], "observations")
        result = cls(
            schema_version=schema_version,
            source_coin_id=_string_value(
                data["source_coin_id"],
                "source_coin_id",
            ),
            reviewer_id=_string_value(
                data["reviewer_id"],
                "reviewer_id",
            ),
            observations=tuple(
                ConfirmedFieldObservation.from_dict(item)
                for item in observations
            ),
            review_session_id=_optional_string_value(
                data["review_session_id"],
                "review_session_id",
            ),
            source_fingerprint=_optional_string_value(
                data["source_fingerprint"],
                "source_fingerprint",
            ),
        )
        result.validate()
        return result


def _object(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object.")
    return value


def _fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    name: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing fields: {missing!r}")
        if unknown:
            details.append(f"unknown fields: {unknown!r}")
        raise ValueError(f"{name} has " + "; ".join(details) + ".")


def _string_value(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    return value


def _optional_string_value(
    value: object,
    name: str,
) -> str | None:
    if value is None:
        return None
    return _string_value(value, name)


def _list(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list.")
    return value


def _optional_number(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric or None.")
    return float(value)


def _enum(
    enum_type: type[Enum],
    value: object,
    name: str,
) -> Any:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    try:
        return enum_type(value)
    except ValueError as error:
        raise ValueError(f"{name} is unsupported.") from error


def _schema(value: object) -> None:
    if not isinstance(value, str):
        raise TypeError("schema_version must be a string.")
    if value != CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION:
        raise UnsupportedConfirmedObservationSchemaVersion(
            f"Unsupported confirmed-observation schema version: {value!r}."
        )


def _text(value: object, name: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value.strip():
        raise ValueError(f"{name} must not be blank.")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds its character limit.")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must already be NFC-normalized.")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{name} must not contain control characters.")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError(f"{name} must not contain surrogate code points.")
    return value


def _confirmed_value(value: str, name: str) -> None:
    if value.strip().casefold() in _UNCONFIRMED_VALUE_MARKERS:
        raise ValueError(
            f"{name} must not contain an unresolved or deferred marker."
        )


def _confidence(value: object) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("confidence_score must be numeric or None.")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 100.0:
        raise ValueError(
            "confidence_score must be finite and between 0 and 100."
        )
