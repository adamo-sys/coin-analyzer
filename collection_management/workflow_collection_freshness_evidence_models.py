"""Durable caller-supplied observations of collection-record field state.

These immutable contracts record what one caller observed for one identified
collection record and when that observation occurred.  They do not read a
repository, compare evidence with a plan, decide freshness, authorize
execution, persist evidence, or mutate collection state.

The active collection repository exposes no authoritative record revision or
optimistic-concurrency token.  This schema therefore records exact field state
without inventing a revision value.  A future validator must determine which
fields a plan requires and whether supplied evidence remains sufficient.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Any
import unicodedata

from collection_management.workflow_collection_change_plan_models import (
    CollectionRecordReference,
)


CURRENT_COLLECTION_FRESHNESS_EVIDENCE_SCHEMA_VERSION = "1"

_MAX_FIELD_NAME_CHARS = 128
_MAX_FIELDS = 300
_MAX_VALUE_CHARS = 4_096
_FIELD_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,127}")
_UTC_TIMESTAMP_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z"
)
_FIELD_EVIDENCE_FIELDS = frozenset(
    {
        "target_field",
        "availability",
        "value",
    }
)
_RECORD_EVIDENCE_FIELDS = frozenset(
    {
        "schema_version",
        "target_record",
        "fields",
        "observed_at",
    }
)


class CollectionFreshnessEvidenceError(ValueError):
    """Collection freshness evidence is structurally invalid."""


class UnsupportedCollectionFreshnessEvidenceSchemaVersion(
    CollectionFreshnessEvidenceError
):
    """The collection freshness-evidence schema version is unsupported."""


class InvalidCollectionFreshnessEvidenceContextError(
    CollectionFreshnessEvidenceError
):
    """Collection freshness evidence is internally inconsistent."""


class DuplicateCollectionFreshnessEvidenceFieldError(
    CollectionFreshnessEvidenceError
):
    """A record evidence envelope repeats one target field."""

    def __init__(self, target_field: str) -> None:
        self.target_field = target_field
        super().__init__(
            "Duplicate collection freshness-evidence target field: "
            f"{target_field!r}."
        )


class InvalidCollectionFreshnessEvidenceTimestampError(
    CollectionFreshnessEvidenceError
):
    """A caller-supplied observation time is not strict UTC RFC 3339."""


class CollectionFreshnessFieldAvailability(str, Enum):
    """Caller-observed availability without a freshness verdict."""

    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class CollectionFreshnessFieldEvidence:
    """Exact caller-supplied state for one collection target field."""

    target_field: str
    availability: CollectionFreshnessFieldAvailability
    value: str | None

    def validate(self) -> None:
        _target_field(self.target_field)
        if not isinstance(
            self.availability,
            CollectionFreshnessFieldAvailability,
        ):
            raise TypeError(
                "availability must be a "
                "CollectionFreshnessFieldAvailability."
            )
        if (
            self.availability
            is CollectionFreshnessFieldAvailability.PRESENT
        ):
            if not isinstance(self.value, str):
                raise InvalidCollectionFreshnessEvidenceContextError(
                    "PRESENT field evidence requires a string value."
                )
            _safe_string(
                self.value,
                "value",
                maximum=_MAX_VALUE_CHARS,
            )
        elif self.value is not None:
            raise InvalidCollectionFreshnessEvidenceContextError(
                "ABSENT and UNAVAILABLE field evidence must use None."
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "target_field": self.target_field,
            "availability": self.availability.value,
            "value": self.value,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "CollectionFreshnessFieldEvidence":
        data = _object(value, "CollectionFreshnessFieldEvidence")
        _fields(
            data,
            _FIELD_EVIDENCE_FIELDS,
            "CollectionFreshnessFieldEvidence",
        )
        result = cls(
            target_field=_string(
                data["target_field"],
                "target_field",
            ),
            availability=_availability(data["availability"]),
            value=_optional_string(data["value"], "value"),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class CollectionRecordFreshnessEvidence:
    """Versioned observations for one record at one caller-supplied time."""

    schema_version: str
    target_record: CollectionRecordReference
    fields: tuple[CollectionFreshnessFieldEvidence, ...]
    observed_at: str

    def validate(self) -> None:
        _schema(self.schema_version)
        if not isinstance(self.target_record, CollectionRecordReference):
            raise TypeError(
                "target_record must be a CollectionRecordReference."
            )
        self.target_record.validate()
        _timestamp(self.observed_at)
        if not isinstance(self.fields, tuple):
            raise TypeError("fields must be a tuple.")
        if not 1 <= len(self.fields) <= _MAX_FIELDS:
            raise InvalidCollectionFreshnessEvidenceContextError(
                "fields must contain between 1 and 300 field observations."
            )
        if any(
            not isinstance(item, CollectionFreshnessFieldEvidence)
            for item in self.fields
        ):
            raise TypeError(
                "fields must contain "
                "CollectionFreshnessFieldEvidence values."
            )

        targets: set[str] = set()
        for field in self.fields:
            field.validate()
            if field.target_field in targets:
                raise DuplicateCollectionFreshnessEvidenceFieldError(
                    field.target_field
                )
            targets.add(field.target_field)

        expected_order = tuple(
            sorted(
                self.fields,
                key=lambda field: field.target_field,
            )
        )
        if self.fields != expected_order:
            raise InvalidCollectionFreshnessEvidenceContextError(
                "fields must be in deterministic target-field order."
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "target_record": self.target_record.to_dict(),
            "fields": [field.to_dict() for field in self.fields],
            "observed_at": self.observed_at,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "CollectionRecordFreshnessEvidence":
        data = _object(value, "CollectionRecordFreshnessEvidence")
        _fields(
            data,
            _RECORD_EVIDENCE_FIELDS,
            "CollectionRecordFreshnessEvidence",
        )
        schema_version = _string(
            data["schema_version"],
            "schema_version",
        )
        _schema(schema_version)
        target_record = CollectionRecordReference.from_dict(
            data["target_record"]
        )
        observed_at = _string(data["observed_at"], "observed_at")
        _timestamp(observed_at)
        serialized_fields = data["fields"]
        if not isinstance(serialized_fields, list):
            raise TypeError("fields must be a list.")
        result = cls(
            schema_version=schema_version,
            target_record=target_record,
            fields=tuple(
                CollectionFreshnessFieldEvidence.from_dict(item)
                for item in serialized_fields
            ),
            observed_at=observed_at,
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
        raise InvalidCollectionFreshnessEvidenceContextError(
            f"{name} has " + "; ".join(details) + "."
        )


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    return value


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _string(value, name)


def _schema(value: object) -> None:
    if not isinstance(value, str):
        raise TypeError("schema_version must be a string.")
    if value != CURRENT_COLLECTION_FRESHNESS_EVIDENCE_SCHEMA_VERSION:
        raise UnsupportedCollectionFreshnessEvidenceSchemaVersion(
            "Unsupported collection freshness-evidence schema version: "
            f"{value!r}."
        )


def _availability(value: object) -> CollectionFreshnessFieldAvailability:
    if not isinstance(value, str):
        raise TypeError("availability must be a string.")
    try:
        return CollectionFreshnessFieldAvailability(value)
    except ValueError as error:
        raise InvalidCollectionFreshnessEvidenceContextError(
            f"Unsupported collection freshness field availability: "
            f"{value!r}."
        ) from error


def _target_field(value: object) -> str:
    target_field = _string(value, "target_field")
    _safe_string(
        target_field,
        "target_field",
        maximum=_MAX_FIELD_NAME_CHARS,
    )
    if _FIELD_PATTERN.fullmatch(target_field) is None:
        raise InvalidCollectionFreshnessEvidenceContextError(
            "target_field must be a lowercase field token."
        )
    return target_field


def _timestamp(value: object) -> None:
    if not isinstance(value, str):
        raise TypeError("observed_at must be a string.")
    if _UTC_TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise InvalidCollectionFreshnessEvidenceTimestampError(
            "observed_at must be a normalized UTC RFC 3339 timestamp."
        )
    if (
        int(value[11:13]) > 23
        or int(value[14:16]) > 59
        or int(value[17:19]) > 59
    ):
        raise InvalidCollectionFreshnessEvidenceTimestampError(
            "observed_at must be a normalized UTC RFC 3339 timestamp."
        )
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise InvalidCollectionFreshnessEvidenceTimestampError(
            "observed_at must be a normalized UTC RFC 3339 timestamp."
        ) from error


def _safe_string(value: str, name: str, *, maximum: int) -> None:
    if len(value) > maximum:
        raise InvalidCollectionFreshnessEvidenceContextError(
            f"{name} exceeds its character limit."
        )
    if unicodedata.normalize("NFC", value) != value:
        raise InvalidCollectionFreshnessEvidenceContextError(
            f"{name} must already be NFC-normalized."
        )
    if any(
        unicodedata.category(character) == "Cc"
        for character in value
    ):
        raise InvalidCollectionFreshnessEvidenceContextError(
            f"{name} must not contain control characters."
        )
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise InvalidCollectionFreshnessEvidenceContextError(
            f"{name} must not contain surrogate code points."
        )
