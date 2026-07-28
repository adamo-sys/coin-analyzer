"""Durable, non-authorizing evidence of human collection-change decisions.

These immutable contracts record what one human decided about referenced
Sprint 14 proposals.  They do not determine policy compatibility, prove
complete approval coverage, establish current-state freshness, authorize
execution, persist records, or mutate collection state.
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
    CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
    CollectionChangeOperation,
    CollectionChangePlan,
    CollectionFieldChangeProposal,
    CollectionRecordReference,
)


CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION = "1"

_MAX_ID_CHARS = 16_384
_MAX_FIELD_NAME_CHARS = 128
_MAX_SESSION_ID_CHARS = 256
_MAX_FINGERPRINT_CHARS = 4_096
_MAX_VALUE_CHARS = 4_096
_MAX_RATIONALE_CHARS = 4_096
_MAX_DECISIONS = 300
_FIELD_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,127}")
_UTC_TIMESTAMP_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z"
)

_REFERENCE_FIELDS = frozenset(
    {
        "target_record",
        "target_field",
        "source_coin_id",
        "review_session_id",
        "source_fingerprint",
        "plan_schema_version",
        "proposal_schema_version",
        "operation",
        "current_value",
        "proposed_value",
        "source_field_name",
    }
)
_DECISION_FIELDS = frozenset(
    {
        "schema_version",
        "proposal_reference",
        "decision",
        "approver_id",
        "decided_at",
        "rationale",
    }
)
_PLAN_APPROVAL_FIELDS = frozenset(
    {
        "schema_version",
        "target_record",
        "source_coin_id",
        "review_session_id",
        "source_fingerprint",
        "plan_schema_version",
        "decisions",
    }
)


class CollectionChangeApprovalError(ValueError):
    """Collection-change approval evidence is structurally invalid."""


class UnsupportedCollectionChangeApprovalSchemaVersion(
    CollectionChangeApprovalError
):
    """The collection-change approval schema version is unsupported."""


class InvalidCollectionChangeApprovalContextError(
    CollectionChangeApprovalError
):
    """Approval evidence is internally inconsistent."""


class DuplicateCollectionChangeApprovalDecisionError(
    CollectionChangeApprovalError
):
    """An approval record contains more than one decision for a target."""

    def __init__(self, target_field: str) -> None:
        self.target_field = target_field
        super().__init__(
            f"Duplicate collection-change decision for target field "
            f"{target_field!r}."
        )


class MismatchedCollectionChangeApprovalLinkageError(
    CollectionChangeApprovalError
):
    """Approval evidence does not share one exact plan linkage."""


class InvalidCollectionChangeApprovalTimestampError(
    CollectionChangeApprovalError
):
    """A caller-supplied decision time is not normalized UTC RFC 3339."""


class CollectionChangeApprovalDecision(str, Enum):
    """Explicit human intent without policy or execution authority."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    DEFER = "DEFER"


@dataclass(frozen=True, slots=True)
class CollectionChangeProposalReference:
    """Durable linkage to one proposal within one immutable plan context."""

    target_record: CollectionRecordReference
    target_field: str
    source_coin_id: str
    review_session_id: str | None
    source_fingerprint: str | None
    plan_schema_version: str
    proposal_schema_version: str
    operation: CollectionChangeOperation
    current_value: str | None
    proposed_value: str | None
    source_field_name: str

    def validate(self) -> None:
        if not isinstance(self.target_record, CollectionRecordReference):
            raise TypeError(
                "target_record must be a CollectionRecordReference."
            )
        self.target_record.validate()
        _field(self.target_field, "target_field")
        _text(
            self.source_coin_id,
            "source_coin_id",
            maximum=_MAX_ID_CHARS,
        )
        _optional_text(
            self.review_session_id,
            "review_session_id",
            maximum=_MAX_SESSION_ID_CHARS,
        )
        _optional_text(
            self.source_fingerprint,
            "source_fingerprint",
            maximum=_MAX_FINGERPRINT_CHARS,
        )
        _plan_schema(self.plan_schema_version, "plan_schema_version")
        _plan_schema(
            self.proposal_schema_version,
            "proposal_schema_version",
        )
        if not isinstance(self.operation, CollectionChangeOperation):
            raise TypeError(
                "operation must be a CollectionChangeOperation."
            )
        _optional_value(self.current_value, "current_value")
        _optional_value(self.proposed_value, "proposed_value")
        _field(self.source_field_name, "source_field_name")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "target_record": self.target_record.to_dict(),
            "target_field": self.target_field,
            "source_coin_id": self.source_coin_id,
            "review_session_id": self.review_session_id,
            "source_fingerprint": self.source_fingerprint,
            "plan_schema_version": self.plan_schema_version,
            "proposal_schema_version": self.proposal_schema_version,
            "operation": self.operation.value,
            "current_value": self.current_value,
            "proposed_value": self.proposed_value,
            "source_field_name": self.source_field_name,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "CollectionChangeProposalReference":
        data = _object(value, "CollectionChangeProposalReference")
        _fields(
            data,
            _REFERENCE_FIELDS,
            "CollectionChangeProposalReference",
        )
        result = cls(
            target_record=CollectionRecordReference.from_dict(
                data["target_record"]
            ),
            target_field=_string(data["target_field"], "target_field"),
            source_coin_id=_string(
                data["source_coin_id"],
                "source_coin_id",
            ),
            review_session_id=_optional_string(
                data["review_session_id"],
                "review_session_id",
            ),
            source_fingerprint=_optional_string(
                data["source_fingerprint"],
                "source_fingerprint",
            ),
            plan_schema_version=_string(
                data["plan_schema_version"],
                "plan_schema_version",
            ),
            proposal_schema_version=_string(
                data["proposal_schema_version"],
                "proposal_schema_version",
            ),
            operation=_enum(
                CollectionChangeOperation,
                data["operation"],
                "operation",
            ),
            current_value=_optional_string(
                data["current_value"],
                "current_value",
            ),
            proposed_value=_optional_string(
                data["proposed_value"],
                "proposed_value",
            ),
            source_field_name=_string(
                data["source_field_name"],
                "source_field_name",
            ),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class CollectionChangeProposalApproval:
    """One attributable human decision with no policy-validity claim."""

    schema_version: str
    proposal_reference: CollectionChangeProposalReference
    decision: CollectionChangeApprovalDecision
    approver_id: str
    decided_at: str
    rationale: str | None = None

    def validate(self) -> None:
        _approval_schema(self.schema_version)
        if not isinstance(
            self.proposal_reference,
            CollectionChangeProposalReference,
        ):
            raise TypeError(
                "proposal_reference must be a "
                "CollectionChangeProposalReference."
            )
        self.proposal_reference.validate()
        if not isinstance(self.decision, CollectionChangeApprovalDecision):
            raise TypeError(
                "decision must be a CollectionChangeApprovalDecision."
            )
        _text(
            self.approver_id,
            "approver_id",
            maximum=_MAX_ID_CHARS,
        )
        _timestamp(self.decided_at)
        if self.rationale is not None:
            _text(
                self.rationale,
                "rationale",
                maximum=_MAX_RATIONALE_CHARS,
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "proposal_reference": self.proposal_reference.to_dict(),
            "decision": self.decision.value,
            "approver_id": self.approver_id,
            "decided_at": self.decided_at,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "CollectionChangeProposalApproval":
        data = _object(value, "CollectionChangeProposalApproval")
        _fields(
            data,
            _DECISION_FIELDS,
            "CollectionChangeProposalApproval",
        )
        schema_version = _string(
            data["schema_version"],
            "schema_version",
        )
        _approval_schema(schema_version)
        result = cls(
            schema_version=schema_version,
            proposal_reference=CollectionChangeProposalReference.from_dict(
                data["proposal_reference"]
            ),
            decision=_enum(
                CollectionChangeApprovalDecision,
                data["decision"],
                "decision",
            ),
            approver_id=_string(data["approver_id"], "approver_id"),
            decided_at=_string(data["decided_at"], "decided_at"),
            rationale=_optional_string(data["rationale"], "rationale"),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class CollectionChangePlanApproval:
    """A deterministic, possibly partial record from exactly one approver."""

    schema_version: str
    target_record: CollectionRecordReference
    source_coin_id: str
    review_session_id: str | None
    source_fingerprint: str | None
    plan_schema_version: str
    decisions: tuple[CollectionChangeProposalApproval, ...]

    def validate(self) -> None:
        _approval_schema(self.schema_version)
        if not isinstance(self.target_record, CollectionRecordReference):
            raise TypeError(
                "target_record must be a CollectionRecordReference."
            )
        self.target_record.validate()
        _text(
            self.source_coin_id,
            "source_coin_id",
            maximum=_MAX_ID_CHARS,
        )
        _optional_text(
            self.review_session_id,
            "review_session_id",
            maximum=_MAX_SESSION_ID_CHARS,
        )
        _optional_text(
            self.source_fingerprint,
            "source_fingerprint",
            maximum=_MAX_FINGERPRINT_CHARS,
        )
        _plan_schema(self.plan_schema_version, "plan_schema_version")
        if not isinstance(self.decisions, tuple):
            raise TypeError("decisions must be a tuple.")
        if not 1 <= len(self.decisions) <= _MAX_DECISIONS:
            raise ValueError(
                "decisions must contain between 1 and 300 decisions."
            )
        if any(
            not isinstance(item, CollectionChangeProposalApproval)
            for item in self.decisions
        ):
            raise TypeError(
                "decisions must contain "
                "CollectionChangeProposalApproval values."
            )
        for decision in self.decisions:
            decision.validate()
        expected_order = tuple(
            sorted(
                self.decisions,
                key=lambda item: item.proposal_reference.target_field,
            )
        )
        if self.decisions != expected_order:
            raise InvalidCollectionChangeApprovalContextError(
                "decisions must be in deterministic target-field order."
            )

        target_fields: set[str] = set()
        approver_id: str | None = None
        for decision in self.decisions:
            reference = decision.proposal_reference
            if reference.target_field in target_fields:
                raise DuplicateCollectionChangeApprovalDecisionError(
                    reference.target_field
                )
            target_fields.add(reference.target_field)
            if (
                reference.target_record != self.target_record
                or reference.source_coin_id != self.source_coin_id
                or reference.review_session_id != self.review_session_id
                or (
                    reference.source_fingerprint
                    != self.source_fingerprint
                )
                or reference.plan_schema_version != self.plan_schema_version
            ):
                raise MismatchedCollectionChangeApprovalLinkageError(
                    "Every decision must use the approval record's exact "
                    "plan linkage."
                )
            if approver_id is None:
                approver_id = decision.approver_id
            elif decision.approver_id != approver_id:
                raise MismatchedCollectionChangeApprovalLinkageError(
                    "Every decision in one approval record must use one "
                    "approver_id."
                )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "target_record": self.target_record.to_dict(),
            "source_coin_id": self.source_coin_id,
            "review_session_id": self.review_session_id,
            "source_fingerprint": self.source_fingerprint,
            "plan_schema_version": self.plan_schema_version,
            "decisions": [
                decision.to_dict() for decision in self.decisions
            ],
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "CollectionChangePlanApproval":
        data = _object(value, "CollectionChangePlanApproval")
        _fields(
            data,
            _PLAN_APPROVAL_FIELDS,
            "CollectionChangePlanApproval",
        )
        schema_version = _string(
            data["schema_version"],
            "schema_version",
        )
        _approval_schema(schema_version)
        serialized_decisions = data["decisions"]
        if not isinstance(serialized_decisions, list):
            raise TypeError("decisions must be a list.")
        result = cls(
            schema_version=schema_version,
            target_record=CollectionRecordReference.from_dict(
                data["target_record"]
            ),
            source_coin_id=_string(
                data["source_coin_id"],
                "source_coin_id",
            ),
            review_session_id=_optional_string(
                data["review_session_id"],
                "review_session_id",
            ),
            source_fingerprint=_optional_string(
                data["source_fingerprint"],
                "source_fingerprint",
            ),
            plan_schema_version=_string(
                data["plan_schema_version"],
                "plan_schema_version",
            ),
            decisions=tuple(
                CollectionChangeProposalApproval.from_dict(item)
                for item in serialized_decisions
            ),
        )
        result.validate()
        return result


def create_collection_change_proposal_reference(
    plan: CollectionChangePlan,
    proposal: CollectionFieldChangeProposal,
) -> CollectionChangeProposalReference:
    """Reference an exact plan member without choosing an approval decision."""

    if not isinstance(plan, CollectionChangePlan):
        raise TypeError("plan must be a CollectionChangePlan.")
    if not isinstance(proposal, CollectionFieldChangeProposal):
        raise TypeError(
            "proposal must be a CollectionFieldChangeProposal."
        )
    plan.validate()
    proposal.validate()
    if not any(item is proposal for item in plan.proposals):
        raise MismatchedCollectionChangeApprovalLinkageError(
            f"Proposal for target field {proposal.target_field!r} is not "
            "an exact member of the supplied plan."
        )
    result = CollectionChangeProposalReference(
        target_record=plan.target_record,
        target_field=proposal.target_field,
        source_coin_id=plan.source_coin_id,
        review_session_id=plan.review_session_id,
        source_fingerprint=plan.source_fingerprint,
        plan_schema_version=plan.schema_version,
        proposal_schema_version=proposal.schema_version,
        operation=proposal.operation,
        current_value=proposal.current_value,
        proposed_value=proposal.proposed_value,
        source_field_name=proposal.source_observation.field_name,
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


def _approval_schema(value: object) -> None:
    if not isinstance(value, str):
        raise TypeError("schema_version must be a string.")
    if value != CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION:
        raise UnsupportedCollectionChangeApprovalSchemaVersion(
            f"Unsupported collection-change approval schema version: "
            f"{value!r}."
        )


def _plan_schema(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if value != CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION:
        raise InvalidCollectionChangeApprovalContextError(
            f"{name} must reference the current collection change-plan "
            "schema version."
        )


def _text(value: object, name: str, *, maximum: int) -> str:
    text = _string(value, name)
    if not text.strip():
        raise ValueError(f"{name} must not be blank.")
    _safe_string(text, name, maximum=maximum)
    return text


def _optional_text(
    value: object,
    name: str,
    *,
    maximum: int,
) -> None:
    if value is None:
        return
    _text(value, name, maximum=maximum)


def _optional_value(value: object, name: str) -> None:
    if value is None:
        return
    text = _string(value, name)
    _safe_string(text, name, maximum=_MAX_VALUE_CHARS)


def _safe_string(value: str, name: str, *, maximum: int) -> None:
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds its character limit.")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must already be NFC-normalized.")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{name} must not contain control characters.")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError(f"{name} must not contain surrogate code points.")


def _field(value: object, name: str) -> str:
    field_name = _text(
        value,
        name,
        maximum=_MAX_FIELD_NAME_CHARS,
    )
    if _FIELD_PATTERN.fullmatch(field_name) is None:
        raise ValueError(
            f"{name} must be a lowercase field token."
        )
    return field_name


def _timestamp(value: object) -> None:
    if not isinstance(value, str):
        raise TypeError("decided_at must be a string.")
    if _UTC_TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise InvalidCollectionChangeApprovalTimestampError(
            "decided_at must be a normalized UTC RFC 3339 timestamp."
        )
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise InvalidCollectionChangeApprovalTimestampError(
            "decided_at must be a normalized UTC RFC 3339 timestamp."
        ) from error
