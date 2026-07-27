"""Immutable proposals for future collection change planning.

These contracts describe possible field changes against one caller-identified
collection record.  They do not locate records, compare values, choose policy,
approve proposals, persist plans, or mutate collection state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import re
import unicodedata
from typing import Any

from capture_import.workflow_confirmed_observation_models import (
    ConfirmedFieldObservation,
)


CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION = "1"

_MAX_ID_CHARS = 16_384
_MAX_FIELD_NAME_CHARS = 128
_MAX_VALUE_CHARS = 4_096
_MAX_RATIONALE_CHARS = 4_096
_MAX_SESSION_ID_CHARS = 256
_MAX_SOURCE_FINGERPRINT_CHARS = 4_096
_MAX_PROPOSALS = 300
_TARGET_FIELD_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,127}")

_RECORD_REFERENCE_FIELDS = frozenset({"record_id"})
_PROPOSAL_FIELDS = frozenset(
    {
        "schema_version",
        "target_record",
        "target_field",
        "current_value",
        "proposed_value",
        "operation",
        "approval_requirement",
        "source_observation",
        "reason_code",
        "rationale",
    }
)
_PLAN_FIELDS = frozenset(
    {
        "schema_version",
        "target_record",
        "source_coin_id",
        "review_session_id",
        "source_fingerprint",
        "proposals",
    }
)


class UnsupportedCollectionChangePlanSchemaVersion(ValueError):
    """The collection change-plan schema version is unsupported."""


class CollectionChangeOperation(str, Enum):
    """Structural operation described by a proposal, never a command."""

    ADD = "ADD"
    UPDATE = "UPDATE"
    CLEAR = "CLEAR"
    NO_CHANGE = "NO_CHANGE"
    CONFLICT = "CONFLICT"


class CollectionChangeApprovalRequirement(str, Enum):
    """Whether a future approval boundary must review the proposal."""

    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED = "REQUIRED"


class CollectionChangeReasonCode(str, Enum):
    """Bounded reason corresponding to one structural operation."""

    NEW_VALUE = "NEW_VALUE"
    DIFFERENT_VALUE = "DIFFERENT_VALUE"
    EXPLICIT_CLEAR = "EXPLICIT_CLEAR"
    EQUIVALENT_VALUE = "EQUIVALENT_VALUE"
    EXISTING_VALUE_CONFLICT = "EXISTING_VALUE_CONFLICT"


_EXPECTED_APPROVAL = {
    CollectionChangeOperation.ADD: (
        CollectionChangeApprovalRequirement.REQUIRED
    ),
    CollectionChangeOperation.UPDATE: (
        CollectionChangeApprovalRequirement.REQUIRED
    ),
    CollectionChangeOperation.CLEAR: (
        CollectionChangeApprovalRequirement.REQUIRED
    ),
    CollectionChangeOperation.NO_CHANGE: (
        CollectionChangeApprovalRequirement.NOT_REQUIRED
    ),
    CollectionChangeOperation.CONFLICT: (
        CollectionChangeApprovalRequirement.REQUIRED
    ),
}
_EXPECTED_REASON = {
    CollectionChangeOperation.ADD: CollectionChangeReasonCode.NEW_VALUE,
    CollectionChangeOperation.UPDATE: (
        CollectionChangeReasonCode.DIFFERENT_VALUE
    ),
    CollectionChangeOperation.CLEAR: (
        CollectionChangeReasonCode.EXPLICIT_CLEAR
    ),
    CollectionChangeOperation.NO_CHANGE: (
        CollectionChangeReasonCode.EQUIVALENT_VALUE
    ),
    CollectionChangeOperation.CONFLICT: (
        CollectionChangeReasonCode.EXISTING_VALUE_CONFLICT
    ),
}


@dataclass(frozen=True, slots=True)
class CollectionRecordReference:
    """Caller-supplied identity of one target collection record."""

    record_id: str

    def validate(self) -> None:
        _text(self.record_id, "record_id", maximum=_MAX_ID_CHARS)

    def to_dict(self) -> dict[str, str]:
        self.validate()
        return {"record_id": self.record_id}

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "CollectionRecordReference":
        data = _object(value, "CollectionRecordReference")
        _fields(data, _RECORD_REFERENCE_FIELDS, "CollectionRecordReference")
        result = cls(record_id=_string(data["record_id"], "record_id"))
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class CollectionFieldChangeProposal:
    """One immutable, traceable field proposal with no approval state."""

    schema_version: str
    target_record: CollectionRecordReference
    target_field: str
    current_value: str | None
    proposed_value: str | None
    operation: CollectionChangeOperation
    approval_requirement: CollectionChangeApprovalRequirement
    source_observation: ConfirmedFieldObservation
    reason_code: CollectionChangeReasonCode
    rationale: str | None = None

    @property
    def source_value(self) -> str:
        """Return the explicit Sprint 13 value this proposal must preserve."""

        if self.source_observation.canonical_value is not None:
            return self.source_observation.canonical_value
        return self.source_observation.submitted_value

    def validate(self) -> None:
        _schema(self.schema_version)
        if not isinstance(self.target_record, CollectionRecordReference):
            raise TypeError(
                "target_record must be a CollectionRecordReference."
            )
        self.target_record.validate()
        _target_field(self.target_field)
        _optional_value(self.current_value, "current_value")
        _optional_value(self.proposed_value, "proposed_value")
        if not isinstance(self.operation, CollectionChangeOperation):
            raise TypeError(
                "operation must be a CollectionChangeOperation."
            )
        if not isinstance(
            self.approval_requirement,
            CollectionChangeApprovalRequirement,
        ):
            raise TypeError(
                "approval_requirement must be a "
                "CollectionChangeApprovalRequirement."
            )
        if not isinstance(self.reason_code, CollectionChangeReasonCode):
            raise TypeError(
                "reason_code must be a CollectionChangeReasonCode."
            )
        if not isinstance(
            self.source_observation,
            ConfirmedFieldObservation,
        ):
            raise TypeError(
                "source_observation must be a ConfirmedFieldObservation."
            )
        self.source_observation.validate()
        if self.rationale is not None:
            _text(
                self.rationale,
                "rationale",
                maximum=_MAX_RATIONALE_CHARS,
            )

        expected_approval = _EXPECTED_APPROVAL[self.operation]
        if self.approval_requirement is not expected_approval:
            raise ValueError(
                f"{self.operation.value} requires approval_requirement "
                f"{expected_approval.value}."
            )
        expected_reason = _EXPECTED_REASON[self.operation]
        if self.reason_code is not expected_reason:
            raise ValueError(
                f"{self.operation.value} requires reason_code "
                f"{expected_reason.value}."
            )

        self._validate_operation_values()
        if (
            self.proposed_value is not None
            and self.proposed_value != self.source_value
        ):
            raise ValueError(
                "proposed_value must exactly match the source observation's "
                "canonical value when present, otherwise its submitted value."
            )

    def _validate_operation_values(self) -> None:
        current = self.current_value
        proposed = self.proposed_value
        if self.operation is CollectionChangeOperation.ADD:
            if current is not None or proposed is None:
                raise ValueError(
                    "ADD requires absent current_value and present "
                    "proposed_value."
                )
        elif self.operation is CollectionChangeOperation.UPDATE:
            if (
                current is None
                or proposed is None
                or current == proposed
            ):
                raise ValueError(
                    "UPDATE requires present, exactly different current and "
                    "proposed values."
                )
        elif self.operation is CollectionChangeOperation.CLEAR:
            if current is None or proposed is not None:
                raise ValueError(
                    "CLEAR requires present current_value and absent "
                    "proposed_value."
                )
        elif self.operation is CollectionChangeOperation.NO_CHANGE:
            if (
                current is None
                or proposed is None
                or current != proposed
            ):
                raise ValueError(
                    "NO_CHANGE requires present, exactly equal current and "
                    "proposed values."
                )
        elif self.operation is CollectionChangeOperation.CONFLICT:
            if (
                current is None
                or proposed is None
                or current == proposed
            ):
                raise ValueError(
                    "CONFLICT requires present, exactly different current "
                    "and proposed values."
                )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "target_record": self.target_record.to_dict(),
            "target_field": self.target_field,
            "current_value": self.current_value,
            "proposed_value": self.proposed_value,
            "operation": self.operation.value,
            "approval_requirement": self.approval_requirement.value,
            "source_observation": self.source_observation.to_dict(),
            "reason_code": self.reason_code.value,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "CollectionFieldChangeProposal":
        data = _object(value, "CollectionFieldChangeProposal")
        _fields(data, _PROPOSAL_FIELDS, "CollectionFieldChangeProposal")
        schema_version = _string(
            data["schema_version"],
            "schema_version",
        )
        _schema(schema_version)
        result = cls(
            schema_version=schema_version,
            target_record=CollectionRecordReference.from_dict(
                data["target_record"]
            ),
            target_field=_string(data["target_field"], "target_field"),
            current_value=_optional_string(
                data["current_value"],
                "current_value",
            ),
            proposed_value=_optional_string(
                data["proposed_value"],
                "proposed_value",
            ),
            operation=_enum(
                CollectionChangeOperation,
                data["operation"],
                "operation",
            ),
            approval_requirement=_enum(
                CollectionChangeApprovalRequirement,
                data["approval_requirement"],
                "approval_requirement",
            ),
            source_observation=ConfirmedFieldObservation.from_dict(
                data["source_observation"]
            ),
            reason_code=_enum(
                CollectionChangeReasonCode,
                data["reason_code"],
                "reason_code",
            ),
            rationale=_optional_string(data["rationale"], "rationale"),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class CollectionChangePlan:
    """A deterministic proposal aggregate for exactly one target record."""

    schema_version: str
    target_record: CollectionRecordReference
    source_coin_id: str
    proposals: tuple[CollectionFieldChangeProposal, ...]
    review_session_id: str | None = None
    source_fingerprint: str | None = None

    def validate(self) -> None:
        _schema(self.schema_version)
        if not isinstance(self.target_record, CollectionRecordReference):
            raise TypeError(
                "target_record must be a CollectionRecordReference."
            )
        self.target_record.validate()
        source_coin_id = _text(
            self.source_coin_id,
            "source_coin_id",
            maximum=_MAX_ID_CHARS,
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
        if not isinstance(self.proposals, tuple):
            raise TypeError("proposals must be a tuple.")
        if not 1 <= len(self.proposals) <= _MAX_PROPOSALS:
            raise ValueError(
                "proposals must contain between 1 and 300 field proposals."
            )
        if any(
            not isinstance(item, CollectionFieldChangeProposal)
            for item in self.proposals
        ):
            raise TypeError(
                "proposals must contain CollectionFieldChangeProposal "
                "values."
            )
        expected_order = tuple(
            sorted(self.proposals, key=lambda item: item.target_field)
        )
        if self.proposals != expected_order:
            raise ValueError(
                "proposals must be in deterministic target-field order."
            )

        target_fields: set[str] = set()
        source_fields: set[str] = set()
        reviewer_id: str | None = None
        for proposal in self.proposals:
            proposal.validate()
            if proposal.target_record != self.target_record:
                raise ValueError(
                    "All proposals must use the plan target_record."
                )
            observation = proposal.source_observation
            if observation.source_coin_id != source_coin_id:
                raise ValueError(
                    "All proposal observations must use the plan "
                    "source_coin_id."
                )
            if reviewer_id is None:
                reviewer_id = observation.reviewer_id
            elif observation.reviewer_id != reviewer_id:
                raise ValueError(
                    "All proposal observations must use one reviewer_id."
                )
            if proposal.target_field in target_fields:
                raise ValueError("Duplicate proposal target_field.")
            target_fields.add(proposal.target_field)
            if observation.field_name in source_fields:
                raise ValueError("Duplicate source observation field_name.")
            source_fields.add(observation.field_name)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "target_record": self.target_record.to_dict(),
            "source_coin_id": self.source_coin_id,
            "review_session_id": self.review_session_id,
            "source_fingerprint": self.source_fingerprint,
            "proposals": [
                proposal.to_dict() for proposal in self.proposals
            ],
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "CollectionChangePlan":
        data = _object(value, "CollectionChangePlan")
        _fields(data, _PLAN_FIELDS, "CollectionChangePlan")
        schema_version = _string(
            data["schema_version"],
            "schema_version",
        )
        _schema(schema_version)
        proposals = data["proposals"]
        if not isinstance(proposals, list):
            raise TypeError("proposals must be a list.")
        result = cls(
            schema_version=schema_version,
            target_record=CollectionRecordReference.from_dict(
                data["target_record"]
            ),
            source_coin_id=_string(
                data["source_coin_id"],
                "source_coin_id",
            ),
            proposals=tuple(
                CollectionFieldChangeProposal.from_dict(item)
                for item in proposals
            ),
            review_session_id=_optional_string(
                data["review_session_id"],
                "review_session_id",
            ),
            source_fingerprint=_optional_string(
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
    if value != CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION:
        raise UnsupportedCollectionChangePlanSchemaVersion(
            f"Unsupported collection change-plan schema version: {value!r}."
        )


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


def _text(value: object, name: str, *, maximum: int) -> str:
    text = _string(value, name)
    if not text.strip():
        raise ValueError(f"{name} must not be blank.")
    _safe_string(text, name, maximum=maximum)
    return text


def _optional_value(value: object, name: str) -> str | None:
    if value is None:
        return None
    text = _string(value, name)
    _safe_string(text, name, maximum=_MAX_VALUE_CHARS)
    return text


def _safe_string(value: str, name: str, *, maximum: int) -> None:
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds its character limit.")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must already be NFC-normalized.")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{name} must not contain control characters.")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError(f"{name} must not contain surrogate code points.")


def _target_field(value: object) -> str:
    field_name = _text(
        value,
        "target_field",
        maximum=_MAX_FIELD_NAME_CHARS,
    )
    if _TARGET_FIELD_PATTERN.fullmatch(field_name) is None:
        raise ValueError(
            "target_field must be a lowercase collection field token."
        )
    if field_name == "grade":
        raise ValueError("Collection change plans must not target grade.")
    return field_name
