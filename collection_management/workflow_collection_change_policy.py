"""Conservative, non-authorizing assessment of collection change plans.

Assessment classifies immutable Unit 1A proposals as safe no-ops,
approval-required changes, or blocked conflicts.  It never grants approval,
authorizes execution, persists decisions, rereads collection state, or mutates
the source plan.

CLEAR is structurally representable by Unit 1A but is not currently emitted by
Unit 1D.  Valid future CLEAR plans are handled defensively and remain blocked
until an explicit destructive-clear policy and user-confirmation boundary
exist; assessment never authorizes a destructive action.

CONFLICT is likewise structurally representable by Unit 1A.  Unit 1D does not
infer it from ordinary value differences; valid conflict proposals remain
blocked pending later conflict-resolution work, with no automatic overwrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from collection_management.workflow_collection_change_plan_models import (
    CollectionChangeOperation,
    CollectionChangePlan,
    CollectionFieldChangeProposal,
)


class CollectionChangePolicyStatus(str, Enum):
    """Bounded evidence classification with no approval state."""

    SAFE_NO_OP = "SAFE_NO_OP"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    BLOCKED_CONFLICT = "BLOCKED_CONFLICT"


class CollectionChangePolicyError(ValueError):
    """A collection change plan cannot be assessed under current policy."""


class UnsupportedCollectionChangePolicyOperationError(
    CollectionChangePolicyError
):
    """The proposal operation has no explicit policy classification."""

    def __init__(self, operation: object, target_field: str) -> None:
        self.operation = operation
        self.target_field = target_field
        rendered = (
            operation.value
            if isinstance(operation, CollectionChangeOperation)
            else repr(operation)
        )
        super().__init__(
            f"Unsupported collection change operation {rendered} for "
            f"target field {target_field!r}."
        )


class InvalidCollectionChangePolicyContextError(
    CollectionChangePolicyError
):
    """Assessment evidence is inconsistent with its source plan."""


class BlockedCollectionChangePlanError(CollectionChangePolicyError):
    """Strict assessment found fields requiring conflict resolution."""

    def __init__(
        self,
        *,
        record_id: str,
        target_fields: tuple[str, ...],
    ) -> None:
        self.record_id = record_id
        self.target_fields = target_fields
        super().__init__(
            f"Collection change plan for record {record_id!r} is blocked "
            f"on target fields {target_fields!r}."
        )


_OPERATION_POLICY: MappingProxyType[
    CollectionChangeOperation,
    CollectionChangePolicyStatus,
] = MappingProxyType(
    {
        CollectionChangeOperation.ADD: (
            CollectionChangePolicyStatus.REQUIRES_APPROVAL
        ),
        CollectionChangeOperation.UPDATE: (
            CollectionChangePolicyStatus.REQUIRES_APPROVAL
        ),
        CollectionChangeOperation.CLEAR: (
            CollectionChangePolicyStatus.BLOCKED_CONFLICT
        ),
        CollectionChangeOperation.NO_CHANGE: (
            CollectionChangePolicyStatus.SAFE_NO_OP
        ),
        CollectionChangeOperation.CONFLICT: (
            CollectionChangePolicyStatus.BLOCKED_CONFLICT
        ),
    }
)


@dataclass(frozen=True, slots=True)
class CollectionChangePolicyAssessment:
    """One proposal and its bounded, non-authorizing policy status."""

    proposal: CollectionFieldChangeProposal
    status: CollectionChangePolicyStatus

    def validate(self) -> None:
        if not isinstance(self.proposal, CollectionFieldChangeProposal):
            raise TypeError(
                "proposal must be a CollectionFieldChangeProposal."
            )
        self.proposal.validate()
        if not isinstance(self.status, CollectionChangePolicyStatus):
            raise TypeError(
                "status must be a CollectionChangePolicyStatus."
            )
        expected = _status_for(self.proposal)
        if self.status is not expected:
            raise InvalidCollectionChangePolicyContextError(
                "Assessment status does not match proposal operation."
            )


@dataclass(frozen=True, slots=True)
class CollectionChangePlanPolicyAssessment:
    """Complete deterministic policy evidence for one immutable plan."""

    plan: CollectionChangePlan
    assessments: tuple[CollectionChangePolicyAssessment, ...]
    contains_blocked_items: bool
    contains_approval_required_items: bool
    contains_only_safe_no_ops: bool

    def validate(self) -> None:
        if not isinstance(self.plan, CollectionChangePlan):
            raise TypeError("plan must be a CollectionChangePlan.")
        self.plan.validate()
        if not isinstance(self.assessments, tuple):
            raise TypeError("assessments must be a tuple.")
        if len(self.assessments) != len(self.plan.proposals):
            raise InvalidCollectionChangePolicyContextError(
                "Assessments must cover every plan proposal exactly once."
            )
        if any(
            not isinstance(item, CollectionChangePolicyAssessment)
            for item in self.assessments
        ):
            raise TypeError(
                "assessments must contain "
                "CollectionChangePolicyAssessment values."
            )
        for assessment, proposal in zip(
            self.assessments,
            self.plan.proposals,
        ):
            assessment.validate()
            if assessment.proposal is not proposal:
                raise InvalidCollectionChangePolicyContextError(
                    "Assessment proposal must be the exact plan proposal."
                )
        for value, name in (
            (self.contains_blocked_items, "contains_blocked_items"),
            (
                self.contains_approval_required_items,
                "contains_approval_required_items",
            ),
            (
                self.contains_only_safe_no_ops,
                "contains_only_safe_no_ops",
            ),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be a boolean.")

        statuses = tuple(item.status for item in self.assessments)
        expected_blocked = (
            CollectionChangePolicyStatus.BLOCKED_CONFLICT in statuses
        )
        expected_approval = (
            CollectionChangePolicyStatus.REQUIRES_APPROVAL in statuses
        )
        expected_safe_only = all(
            status is CollectionChangePolicyStatus.SAFE_NO_OP
            for status in statuses
        )
        if self.contains_blocked_items is not expected_blocked:
            raise InvalidCollectionChangePolicyContextError(
                "contains_blocked_items is inconsistent with assessments."
            )
        if (
            self.contains_approval_required_items
            is not expected_approval
        ):
            raise InvalidCollectionChangePolicyContextError(
                "contains_approval_required_items is inconsistent with "
                "assessments."
            )
        if self.contains_only_safe_no_ops is not expected_safe_only:
            raise InvalidCollectionChangePolicyContextError(
                "contains_only_safe_no_ops is inconsistent with "
                "assessments."
            )


class CollectionChangePolicyAssessor:
    """Stateless diagnostic assessor for complete Unit 1A plans."""

    __slots__ = ()

    def assess(
        self,
        plan: CollectionChangePlan,
    ) -> CollectionChangePlanPolicyAssessment:
        if not isinstance(plan, CollectionChangePlan):
            raise TypeError("plan must be a CollectionChangePlan.")
        plan.validate()

        assessments: list[CollectionChangePolicyAssessment] = []
        for proposal in plan.proposals:
            assessment = CollectionChangePolicyAssessment(
                proposal=proposal,
                status=_status_for(proposal),
            )
            assessment.validate()
            assessments.append(assessment)

        statuses = tuple(item.status for item in assessments)
        result = CollectionChangePlanPolicyAssessment(
            plan=plan,
            assessments=tuple(assessments),
            contains_blocked_items=(
                CollectionChangePolicyStatus.BLOCKED_CONFLICT in statuses
            ),
            contains_approval_required_items=(
                CollectionChangePolicyStatus.REQUIRES_APPROVAL in statuses
            ),
            contains_only_safe_no_ops=all(
                status is CollectionChangePolicyStatus.SAFE_NO_OP
                for status in statuses
            ),
        )
        result.validate()
        return result


def assess_collection_change_plan(
    plan: CollectionChangePlan,
) -> CollectionChangePlanPolicyAssessment:
    """Return complete diagnostic policy evidence for one plan."""

    return CollectionChangePolicyAssessor().assess(plan)


def require_unblocked_collection_change_plan(
    plan: CollectionChangePlan,
) -> CollectionChangePlanPolicyAssessment:
    """Return assessment or fail when conflict resolution is required.

    This helper does not satisfy REQUIRES_APPROVAL entries and returns no
    approval or execution authority.
    """

    assessment = assess_collection_change_plan(plan)
    if assessment.contains_blocked_items:
        blocked_fields = tuple(
            item.proposal.target_field
            for item in assessment.assessments
            if (
                item.status
                is CollectionChangePolicyStatus.BLOCKED_CONFLICT
            )
        )
        raise BlockedCollectionChangePlanError(
            record_id=plan.target_record.record_id,
            target_fields=blocked_fields,
        )
    return assessment


def _status_for(
    proposal: CollectionFieldChangeProposal,
) -> CollectionChangePolicyStatus:
    status = _OPERATION_POLICY.get(proposal.operation)
    if status is None:
        raise UnsupportedCollectionChangePolicyOperationError(
            proposal.operation,
            proposal.target_field,
        )
    return status
