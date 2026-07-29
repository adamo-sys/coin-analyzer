"""Pure compatibility diagnostics for plans and observed collection state.

This module compares one durable collection change plan with one durable,
caller-supplied freshness-evidence envelope.  A matched result means only that
the supplied field state exactly agrees with the plan's retained current
values.  It does not establish recency, protect against later concurrent
changes, inspect approval, authorize execution, persist results, or mutate a
collection.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from collection_management.workflow_collection_change_plan_models import (
    CollectionChangePlan,
    CollectionFieldChangeProposal,
)
from collection_management.workflow_collection_freshness_evidence_models import (
    CollectionFreshnessFieldAvailability,
    CollectionFreshnessFieldEvidence,
    CollectionRecordFreshnessEvidence,
)


class CollectionFreshnessCompatibilityError(ValueError):
    """Freshness evidence cannot be compared safely with the plan."""


class InvalidCollectionFreshnessCompatibilityContextError(
    CollectionFreshnessCompatibilityError
):
    """The plan, evidence, finding, or result is internally inconsistent."""


class MismatchedCollectionFreshnessRecordError(
    CollectionFreshnessCompatibilityError
):
    """The evidence belongs to a different collection record."""


class UnmatchedCollectionFreshnessEvidenceFieldError(
    CollectionFreshnessCompatibilityError
):
    """Supplied evidence describes a field absent from the plan."""

    def __init__(self, target_field: str) -> None:
        self.target_field = target_field
        super().__init__(
            "Collection freshness evidence field does not match the plan: "
            f"{target_field!r}."
        )


class NonMatchingCollectionFreshnessEvidenceError(
    CollectionFreshnessCompatibilityError
):
    """Strict validation found non-matching or incomplete evidence."""

    def __init__(
        self,
        *,
        mismatched_fields: tuple[str, ...],
        unavailable_fields: tuple[str, ...],
        missing_fields: tuple[str, ...],
    ) -> None:
        self.mismatched_fields = mismatched_fields
        self.unavailable_fields = unavailable_fields
        self.missing_fields = missing_fields
        super().__init__(
            "Collection freshness evidence did not match every plan field; "
            f"mismatched={mismatched_fields!r}, "
            f"unavailable={unavailable_fields!r}, "
            f"missing={missing_fields!r}."
        )


class CollectionFreshnessCompatibilityStatus(str, Enum):
    """Exact supplied-state relationship without execution authority."""

    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"
    UNAVAILABLE = "UNAVAILABLE"
    MISSING = "MISSING"


class CollectionFreshnessCompatibilityReason(str, Enum):
    """Bounded reason for one proposal-level freshness finding."""

    EXPECTED_PRESENT_VALUE_MATCHED = "EXPECTED_PRESENT_VALUE_MATCHED"
    EXPECTED_ABSENT_STATE_MATCHED = "EXPECTED_ABSENT_STATE_MATCHED"
    EXPECTED_PRESENT_VALUE_DIFFERED = (
        "EXPECTED_PRESENT_VALUE_DIFFERED"
    )
    EXPECTED_PRESENT_BUT_OBSERVED_ABSENT = (
        "EXPECTED_PRESENT_BUT_OBSERVED_ABSENT"
    )
    EXPECTED_ABSENT_BUT_OBSERVED_PRESENT = (
        "EXPECTED_ABSENT_BUT_OBSERVED_PRESENT"
    )
    EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"


_Compatibility = tuple[
    CollectionFreshnessCompatibilityStatus,
    CollectionFreshnessCompatibilityReason,
]
_COMPARISON_MATRIX: MappingProxyType[
    tuple[
        bool,
        CollectionFreshnessFieldAvailability | None,
        bool | None,
    ],
    _Compatibility,
] = MappingProxyType(
    {
        (
            True,
            CollectionFreshnessFieldAvailability.PRESENT,
            True,
        ): (
            CollectionFreshnessCompatibilityStatus.MATCHED,
            CollectionFreshnessCompatibilityReason.EXPECTED_PRESENT_VALUE_MATCHED,
        ),
        (
            True,
            CollectionFreshnessFieldAvailability.PRESENT,
            False,
        ): (
            CollectionFreshnessCompatibilityStatus.MISMATCHED,
            CollectionFreshnessCompatibilityReason.EXPECTED_PRESENT_VALUE_DIFFERED,
        ),
        (
            True,
            CollectionFreshnessFieldAvailability.ABSENT,
            None,
        ): (
            CollectionFreshnessCompatibilityStatus.MISMATCHED,
            CollectionFreshnessCompatibilityReason.EXPECTED_PRESENT_BUT_OBSERVED_ABSENT,
        ),
        (
            True,
            CollectionFreshnessFieldAvailability.UNAVAILABLE,
            None,
        ): (
            CollectionFreshnessCompatibilityStatus.UNAVAILABLE,
            CollectionFreshnessCompatibilityReason.EVIDENCE_UNAVAILABLE,
        ),
        (True, None, None): (
            CollectionFreshnessCompatibilityStatus.MISSING,
            CollectionFreshnessCompatibilityReason.EVIDENCE_MISSING,
        ),
        (
            False,
            CollectionFreshnessFieldAvailability.ABSENT,
            None,
        ): (
            CollectionFreshnessCompatibilityStatus.MATCHED,
            CollectionFreshnessCompatibilityReason.EXPECTED_ABSENT_STATE_MATCHED,
        ),
        (
            False,
            CollectionFreshnessFieldAvailability.PRESENT,
            None,
        ): (
            CollectionFreshnessCompatibilityStatus.MISMATCHED,
            CollectionFreshnessCompatibilityReason.EXPECTED_ABSENT_BUT_OBSERVED_PRESENT,
        ),
        (
            False,
            CollectionFreshnessFieldAvailability.UNAVAILABLE,
            None,
        ): (
            CollectionFreshnessCompatibilityStatus.UNAVAILABLE,
            CollectionFreshnessCompatibilityReason.EVIDENCE_UNAVAILABLE,
        ),
        (False, None, None): (
            CollectionFreshnessCompatibilityStatus.MISSING,
            CollectionFreshnessCompatibilityReason.EVIDENCE_MISSING,
        ),
    }
)


@dataclass(frozen=True, slots=True)
class CollectionFreshnessCompatibilityFinding:
    """One exact plan proposal and its optional observed field evidence."""

    proposal: CollectionFieldChangeProposal
    evidence: CollectionFreshnessFieldEvidence | None
    status: CollectionFreshnessCompatibilityStatus
    reason: CollectionFreshnessCompatibilityReason

    def validate(self) -> None:
        if not isinstance(self.proposal, CollectionFieldChangeProposal):
            raise InvalidCollectionFreshnessCompatibilityContextError(
                "proposal must be a CollectionFieldChangeProposal."
            )
        try:
            self.proposal.validate()
        except (TypeError, ValueError) as error:
            raise InvalidCollectionFreshnessCompatibilityContextError(
                str(error)
            ) from error
        if (
            self.evidence is not None
            and not isinstance(
                self.evidence,
                CollectionFreshnessFieldEvidence,
            )
        ):
            raise InvalidCollectionFreshnessCompatibilityContextError(
                "evidence must be CollectionFreshnessFieldEvidence or None."
            )
        if self.evidence is not None:
            try:
                self.evidence.validate()
            except (TypeError, ValueError) as error:
                raise InvalidCollectionFreshnessCompatibilityContextError(
                    str(error)
                ) from error
            if self.evidence.target_field != self.proposal.target_field:
                raise InvalidCollectionFreshnessCompatibilityContextError(
                    "Finding evidence must match proposal target_field."
                )
        if not isinstance(
            self.status,
            CollectionFreshnessCompatibilityStatus,
        ):
            raise InvalidCollectionFreshnessCompatibilityContextError(
                "status must be a CollectionFreshnessCompatibilityStatus."
            )
        if not isinstance(
            self.reason,
            CollectionFreshnessCompatibilityReason,
        ):
            raise InvalidCollectionFreshnessCompatibilityContextError(
                "reason must be a CollectionFreshnessCompatibilityReason."
            )
        expected = _classify(self.proposal, self.evidence)
        if (self.status, self.reason) != expected:
            raise InvalidCollectionFreshnessCompatibilityContextError(
                "Finding status and reason do not match expected and "
                "observed state."
            )


@dataclass(frozen=True, slots=True)
class CollectionChangePlanFreshnessCompatibility:
    """Complete transient diagnostics for one plan and evidence envelope."""

    plan: CollectionChangePlan
    evidence: CollectionRecordFreshnessEvidence
    findings: tuple[CollectionFreshnessCompatibilityFinding, ...]
    all_fields_matched: bool
    contains_mismatched_items: bool
    contains_unavailable_items: bool
    contains_missing_items: bool

    def validate(self) -> None:
        _validate_inputs(self.plan, self.evidence)
        _validate_record_binding(self.plan, self.evidence)
        if not isinstance(self.findings, tuple):
            raise InvalidCollectionFreshnessCompatibilityContextError(
                "findings must be a tuple."
            )
        if len(self.findings) != len(self.plan.proposals):
            raise InvalidCollectionFreshnessCompatibilityContextError(
                "Findings must cover every plan proposal exactly once."
            )
        if any(
            not isinstance(
                item,
                CollectionFreshnessCompatibilityFinding,
            )
            for item in self.findings
        ):
            raise InvalidCollectionFreshnessCompatibilityContextError(
                "findings must contain "
                "CollectionFreshnessCompatibilityFinding values."
            )

        evidence_by_field = _evidence_lookup(self.evidence)
        plan_fields = frozenset(
            proposal.target_field for proposal in self.plan.proposals
        )
        _reject_extra_evidence(evidence_by_field, plan_fields)
        for finding, proposal in zip(
            self.findings,
            self.plan.proposals,
        ):
            finding.validate()
            if finding.proposal is not proposal:
                raise InvalidCollectionFreshnessCompatibilityContextError(
                    "Finding must retain the exact plan proposal."
                )
            expected_evidence = evidence_by_field.get(
                proposal.target_field
            )
            if finding.evidence is not expected_evidence:
                raise InvalidCollectionFreshnessCompatibilityContextError(
                    "Finding must retain the exact matching evidence field."
                )

        expected = _summaries(self.findings)
        actual = (
            self.all_fields_matched,
            self.contains_mismatched_items,
            self.contains_unavailable_items,
            self.contains_missing_items,
        )
        if any(not isinstance(value, bool) for value in actual):
            raise InvalidCollectionFreshnessCompatibilityContextError(
                "Freshness compatibility summaries must be booleans."
            )
        if actual != expected:
            raise InvalidCollectionFreshnessCompatibilityContextError(
                "Freshness compatibility summaries are inconsistent with "
                "findings."
            )


class CollectionFreshnessCompatibilityValidator:
    """Stateless exact comparator with no recency or authority behavior."""

    __slots__ = ()

    def validate(
        self,
        plan: CollectionChangePlan,
        evidence: CollectionRecordFreshnessEvidence,
    ) -> CollectionChangePlanFreshnessCompatibility:
        _validate_inputs(plan, evidence)
        _validate_record_binding(plan, evidence)

        evidence_by_field = _evidence_lookup(evidence)
        plan_fields = frozenset(
            proposal.target_field for proposal in plan.proposals
        )
        _reject_extra_evidence(evidence_by_field, plan_fields)

        findings: list[CollectionFreshnessCompatibilityFinding] = []
        for proposal in plan.proposals:
            field_evidence = evidence_by_field.get(proposal.target_field)
            status, reason = _classify(proposal, field_evidence)
            finding = CollectionFreshnessCompatibilityFinding(
                proposal=proposal,
                evidence=field_evidence,
                status=status,
                reason=reason,
            )
            finding.validate()
            findings.append(finding)

        finding_tuple = tuple(findings)
        summaries = _summaries(finding_tuple)
        result = CollectionChangePlanFreshnessCompatibility(
            plan=plan,
            evidence=evidence,
            findings=finding_tuple,
            all_fields_matched=summaries[0],
            contains_mismatched_items=summaries[1],
            contains_unavailable_items=summaries[2],
            contains_missing_items=summaries[3],
        )
        result.validate()
        return result


def validate_collection_freshness_compatibility(
    plan: CollectionChangePlan,
    evidence: CollectionRecordFreshnessEvidence,
) -> CollectionChangePlanFreshnessCompatibility:
    """Compare supplied state with plan expectations without authorization."""

    return CollectionFreshnessCompatibilityValidator().validate(
        plan,
        evidence,
    )


def require_matching_collection_freshness_evidence(
    plan: CollectionChangePlan,
    evidence: CollectionRecordFreshnessEvidence,
) -> CollectionChangePlanFreshnessCompatibility:
    """Require exact supplied-state matches without asserting recency.

    A successful result remains independent from approval, concurrency,
    repository state after observation, execution, and mutation eligibility.
    """

    result = validate_collection_freshness_compatibility(plan, evidence)
    if not result.all_fields_matched:
        raise NonMatchingCollectionFreshnessEvidenceError(
            mismatched_fields=tuple(
                item.proposal.target_field
                for item in result.findings
                if (
                    item.status
                    is CollectionFreshnessCompatibilityStatus.MISMATCHED
                )
            ),
            unavailable_fields=tuple(
                item.proposal.target_field
                for item in result.findings
                if (
                    item.status
                    is CollectionFreshnessCompatibilityStatus.UNAVAILABLE
                )
            ),
            missing_fields=tuple(
                item.proposal.target_field
                for item in result.findings
                if (
                    item.status
                    is CollectionFreshnessCompatibilityStatus.MISSING
                )
            ),
        )
    return result


def _validate_inputs(
    plan: object,
    evidence: object,
) -> None:
    if not isinstance(plan, CollectionChangePlan):
        raise InvalidCollectionFreshnessCompatibilityContextError(
            "plan must be a CollectionChangePlan."
        )
    if not isinstance(evidence, CollectionRecordFreshnessEvidence):
        raise InvalidCollectionFreshnessCompatibilityContextError(
            "evidence must be a CollectionRecordFreshnessEvidence."
        )
    try:
        plan.validate()
        evidence.validate()
    except CollectionFreshnessCompatibilityError:
        raise
    except (TypeError, ValueError) as error:
        raise InvalidCollectionFreshnessCompatibilityContextError(
            str(error)
        ) from error


def _validate_record_binding(
    plan: CollectionChangePlan,
    evidence: CollectionRecordFreshnessEvidence,
) -> None:
    if plan.target_record != evidence.target_record:
        raise MismatchedCollectionFreshnessRecordError(
            "Freshness evidence target record does not match the plan."
        )


def _evidence_lookup(
    evidence: CollectionRecordFreshnessEvidence,
) -> dict[str, CollectionFreshnessFieldEvidence]:
    result: dict[str, CollectionFreshnessFieldEvidence] = {}
    for field in evidence.fields:
        if field.target_field in result:
            raise InvalidCollectionFreshnessCompatibilityContextError(
                "Freshness evidence contains duplicate target fields."
            )
        result[field.target_field] = field
    return result


def _reject_extra_evidence(
    evidence_by_field: dict[str, CollectionFreshnessFieldEvidence],
    plan_fields: frozenset[str],
) -> None:
    for target_field in evidence_by_field:
        if target_field not in plan_fields:
            raise UnmatchedCollectionFreshnessEvidenceFieldError(
                target_field
            )


def _classify(
    proposal: CollectionFieldChangeProposal,
    evidence: CollectionFreshnessFieldEvidence | None,
) -> _Compatibility:
    expected_present = proposal.current_value is not None
    availability = None if evidence is None else evidence.availability
    values_equal: bool | None = None
    if (
        expected_present
        and availability is CollectionFreshnessFieldAvailability.PRESENT
    ):
        values_equal = evidence.value == proposal.current_value
    result = _COMPARISON_MATRIX.get(
        (expected_present, availability, values_equal)
    )
    if result is None:
        raise InvalidCollectionFreshnessCompatibilityContextError(
            "Expected and observed state have no explicit compatibility "
            "rule."
        )
    return result


def _summaries(
    findings: tuple[CollectionFreshnessCompatibilityFinding, ...],
) -> tuple[bool, bool, bool, bool]:
    statuses = tuple(item.status for item in findings)
    return (
        all(
            status is CollectionFreshnessCompatibilityStatus.MATCHED
            for status in statuses
        ),
        CollectionFreshnessCompatibilityStatus.MISMATCHED in statuses,
        CollectionFreshnessCompatibilityStatus.UNAVAILABLE in statuses,
        CollectionFreshnessCompatibilityStatus.MISSING in statuses,
    )
