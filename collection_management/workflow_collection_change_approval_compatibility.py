"""Pure compatibility validation for policy assessments and approval evidence.

Compatibility describes whether recorded decisions fit Sprint 14 policy and
cover every approval-required proposal.  It does not establish freshness,
authorize execution, persist evidence, or mutate collection state.  Decision
resolution and policy blocking remain separate axes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from collection_management.workflow_collection_change_approval_models import (
    CollectionChangeApprovalDecision,
    CollectionChangePlanApproval,
    CollectionChangeProposalApproval,
    CollectionChangeProposalReference,
    create_collection_change_proposal_reference,
)
from collection_management.workflow_collection_change_policy import (
    CollectionChangePlanPolicyAssessment,
    CollectionChangePolicyAssessment,
    CollectionChangePolicyStatus,
)


class CollectionChangeApprovalCompatibilityError(ValueError):
    """Approval evidence cannot be evaluated under current compatibility."""


class MismatchedCollectionChangeApprovalPlanError(
    CollectionChangeApprovalCompatibilityError
):
    """The approval record does not belong to the assessed plan."""


class UnmatchedCollectionChangeApprovalDecisionError(
    CollectionChangeApprovalCompatibilityError
):
    """A recorded decision does not match an assessed proposal."""

    def __init__(self, target_field: str) -> None:
        self.target_field = target_field
        super().__init__(
            f"Approval decision for target field {target_field!r} does not "
            "match an assessed proposal."
        )


class InvalidCollectionChangeApprovalCompatibilityContextError(
    CollectionChangeApprovalCompatibilityError
):
    """Compatibility evidence is internally inconsistent."""


class IncompatibleCollectionChangeApprovalError(
    CollectionChangeApprovalCompatibilityError
):
    """Strict validation found incompatible approval evidence."""

    def __init__(self, target_fields: tuple[str, ...]) -> None:
        self.target_fields = target_fields
        super().__init__(
            "Collection-change approval is incompatible on target fields "
            f"{target_fields!r}."
        )


class UnresolvedCollectionChangeApprovalError(
    CollectionChangeApprovalCompatibilityError
):
    """Strict resolution validation found unresolved decisions."""

    def __init__(self, target_fields: tuple[str, ...]) -> None:
        self.target_fields = target_fields
        super().__init__(
            "Collection-change approval is unresolved on target fields "
            f"{target_fields!r}."
        )


class CollectionChangeApprovalCompatibilityStatus(str, Enum):
    """Bounded compatibility state without execution authority."""

    COMPATIBLE_RESOLVED = "COMPATIBLE_RESOLVED"
    COMPATIBLE_UNRESOLVED = "COMPATIBLE_UNRESOLVED"
    INCOMPATIBLE = "INCOMPATIBLE"


class CollectionChangeApprovalCompatibilityReason(str, Enum):
    """Exact reason for one proposal-level compatibility finding."""

    SAFE_NO_OP_WITHOUT_DECISION = "SAFE_NO_OP_WITHOUT_DECISION"
    UNEXPECTED_APPROVAL_FOR_SAFE_NO_OP = (
        "UNEXPECTED_APPROVAL_FOR_SAFE_NO_OP"
    )
    UNEXPECTED_REJECTION_FOR_SAFE_NO_OP = (
        "UNEXPECTED_REJECTION_FOR_SAFE_NO_OP"
    )
    UNEXPECTED_DEFERRAL_FOR_SAFE_NO_OP = (
        "UNEXPECTED_DEFERRAL_FOR_SAFE_NO_OP"
    )
    APPROVAL_REQUIRED_APPROVED = "APPROVAL_REQUIRED_APPROVED"
    APPROVAL_REQUIRED_REJECTED = "APPROVAL_REQUIRED_REJECTED"
    APPROVAL_REQUIRED_DEFERRED = "APPROVAL_REQUIRED_DEFERRED"
    MISSING_REQUIRED_DECISION = "MISSING_REQUIRED_DECISION"
    BLOCKED_WITHOUT_DECISION = "BLOCKED_WITHOUT_DECISION"
    BLOCKED_REJECTED = "BLOCKED_REJECTED"
    BLOCKED_DEFERRED = "BLOCKED_DEFERRED"
    FORBIDDEN_APPROVAL_FOR_BLOCKED = "FORBIDDEN_APPROVAL_FOR_BLOCKED"


_Compatibility = tuple[
    CollectionChangeApprovalCompatibilityStatus,
    CollectionChangeApprovalCompatibilityReason,
]
_POLICY_MATRIX: MappingProxyType[
    tuple[
        CollectionChangePolicyStatus,
        CollectionChangeApprovalDecision | None,
    ],
    _Compatibility,
] = MappingProxyType(
    {
        (
            CollectionChangePolicyStatus.SAFE_NO_OP,
            None,
        ): (
            CollectionChangeApprovalCompatibilityStatus.COMPATIBLE_RESOLVED,
            CollectionChangeApprovalCompatibilityReason.SAFE_NO_OP_WITHOUT_DECISION,
        ),
        (
            CollectionChangePolicyStatus.SAFE_NO_OP,
            CollectionChangeApprovalDecision.APPROVE,
        ): (
            CollectionChangeApprovalCompatibilityStatus.INCOMPATIBLE,
            CollectionChangeApprovalCompatibilityReason.UNEXPECTED_APPROVAL_FOR_SAFE_NO_OP,
        ),
        (
            CollectionChangePolicyStatus.SAFE_NO_OP,
            CollectionChangeApprovalDecision.REJECT,
        ): (
            CollectionChangeApprovalCompatibilityStatus.INCOMPATIBLE,
            CollectionChangeApprovalCompatibilityReason.UNEXPECTED_REJECTION_FOR_SAFE_NO_OP,
        ),
        (
            CollectionChangePolicyStatus.SAFE_NO_OP,
            CollectionChangeApprovalDecision.DEFER,
        ): (
            CollectionChangeApprovalCompatibilityStatus.INCOMPATIBLE,
            CollectionChangeApprovalCompatibilityReason.UNEXPECTED_DEFERRAL_FOR_SAFE_NO_OP,
        ),
        (
            CollectionChangePolicyStatus.REQUIRES_APPROVAL,
            None,
        ): (
            CollectionChangeApprovalCompatibilityStatus.INCOMPATIBLE,
            CollectionChangeApprovalCompatibilityReason.MISSING_REQUIRED_DECISION,
        ),
        (
            CollectionChangePolicyStatus.REQUIRES_APPROVAL,
            CollectionChangeApprovalDecision.APPROVE,
        ): (
            CollectionChangeApprovalCompatibilityStatus.COMPATIBLE_RESOLVED,
            CollectionChangeApprovalCompatibilityReason.APPROVAL_REQUIRED_APPROVED,
        ),
        (
            CollectionChangePolicyStatus.REQUIRES_APPROVAL,
            CollectionChangeApprovalDecision.REJECT,
        ): (
            CollectionChangeApprovalCompatibilityStatus.COMPATIBLE_RESOLVED,
            CollectionChangeApprovalCompatibilityReason.APPROVAL_REQUIRED_REJECTED,
        ),
        (
            CollectionChangePolicyStatus.REQUIRES_APPROVAL,
            CollectionChangeApprovalDecision.DEFER,
        ): (
            CollectionChangeApprovalCompatibilityStatus.COMPATIBLE_UNRESOLVED,
            CollectionChangeApprovalCompatibilityReason.APPROVAL_REQUIRED_DEFERRED,
        ),
        (
            CollectionChangePolicyStatus.BLOCKED_CONFLICT,
            None,
        ): (
            CollectionChangeApprovalCompatibilityStatus.COMPATIBLE_UNRESOLVED,
            CollectionChangeApprovalCompatibilityReason.BLOCKED_WITHOUT_DECISION,
        ),
        (
            CollectionChangePolicyStatus.BLOCKED_CONFLICT,
            CollectionChangeApprovalDecision.APPROVE,
        ): (
            CollectionChangeApprovalCompatibilityStatus.INCOMPATIBLE,
            CollectionChangeApprovalCompatibilityReason.FORBIDDEN_APPROVAL_FOR_BLOCKED,
        ),
        (
            CollectionChangePolicyStatus.BLOCKED_CONFLICT,
            CollectionChangeApprovalDecision.REJECT,
        ): (
            CollectionChangeApprovalCompatibilityStatus.COMPATIBLE_RESOLVED,
            CollectionChangeApprovalCompatibilityReason.BLOCKED_REJECTED,
        ),
        (
            CollectionChangePolicyStatus.BLOCKED_CONFLICT,
            CollectionChangeApprovalDecision.DEFER,
        ): (
            CollectionChangeApprovalCompatibilityStatus.COMPATIBLE_UNRESOLVED,
            CollectionChangeApprovalCompatibilityReason.BLOCKED_DEFERRED,
        ),
    }
)


@dataclass(frozen=True, slots=True)
class CollectionChangeApprovalCompatibilityFinding:
    """One exact proposal assessment and its optional recorded decision."""

    policy_assessment: CollectionChangePolicyAssessment
    approval_decision: CollectionChangeProposalApproval | None
    status: CollectionChangeApprovalCompatibilityStatus
    reason: CollectionChangeApprovalCompatibilityReason

    def validate(self) -> None:
        if not isinstance(
            self.policy_assessment,
            CollectionChangePolicyAssessment,
        ):
            raise TypeError(
                "policy_assessment must be a "
                "CollectionChangePolicyAssessment."
            )
        self.policy_assessment.validate()
        if (
            self.approval_decision is not None
            and not isinstance(
                self.approval_decision,
                CollectionChangeProposalApproval,
            )
        ):
            raise TypeError(
                "approval_decision must be a "
                "CollectionChangeProposalApproval or None."
            )
        if self.approval_decision is not None:
            self.approval_decision.validate()
            proposal = self.policy_assessment.proposal
            reference = self.approval_decision.proposal_reference
            if (
                reference.target_field != proposal.target_field
                or reference.proposal_schema_version
                != proposal.schema_version
                or reference.operation is not proposal.operation
                or reference.current_value != proposal.current_value
                or reference.proposed_value != proposal.proposed_value
                or reference.source_field_name
                != proposal.source_observation.field_name
            ):
                raise InvalidCollectionChangeApprovalCompatibilityContextError(
                    "Finding approval decision must reference its exact "
                    "policy proposal."
                )
        if not isinstance(
            self.status,
            CollectionChangeApprovalCompatibilityStatus,
        ):
            raise TypeError(
                "status must be a "
                "CollectionChangeApprovalCompatibilityStatus."
            )
        if not isinstance(
            self.reason,
            CollectionChangeApprovalCompatibilityReason,
        ):
            raise TypeError(
                "reason must be a "
                "CollectionChangeApprovalCompatibilityReason."
            )
        expected = _classify(
            self.policy_assessment.status,
            (
                None
                if self.approval_decision is None
                else self.approval_decision.decision
            ),
        )
        if (self.status, self.reason) != expected:
            raise InvalidCollectionChangeApprovalCompatibilityContextError(
                "Finding status and reason do not match policy and decision."
            )


@dataclass(frozen=True, slots=True)
class CollectionChangePlanApprovalCompatibility:
    """Complete transient diagnostics for one assessed plan and record."""

    policy_assessment: CollectionChangePlanPolicyAssessment
    approval_record: CollectionChangePlanApproval
    findings: tuple[CollectionChangeApprovalCompatibilityFinding, ...]
    contains_incompatible_items: bool
    contains_unresolved_items: bool
    contains_blocked_items: bool
    required_decisions_complete: bool
    contains_approve_decisions: bool
    contains_reject_decisions: bool
    contains_defer_decisions: bool

    def validate(self) -> None:
        if not isinstance(
            self.policy_assessment,
            CollectionChangePlanPolicyAssessment,
        ):
            raise TypeError(
                "policy_assessment must be a "
                "CollectionChangePlanPolicyAssessment."
            )
        self.policy_assessment.validate()
        if not isinstance(
            self.approval_record,
            CollectionChangePlanApproval,
        ):
            raise TypeError(
                "approval_record must be a CollectionChangePlanApproval."
            )
        self.approval_record.validate()
        _validate_plan_linkage(
            self.policy_assessment,
            self.approval_record,
        )
        if not isinstance(self.findings, tuple):
            raise TypeError("findings must be a tuple.")
        if len(self.findings) != len(
            self.policy_assessment.assessments
        ):
            raise InvalidCollectionChangeApprovalCompatibilityContextError(
                "Findings must cover every policy assessment exactly once."
            )
        if any(
            not isinstance(
                item,
                CollectionChangeApprovalCompatibilityFinding,
            )
            for item in self.findings
        ):
            raise TypeError(
                "findings must contain "
                "CollectionChangeApprovalCompatibilityFinding values."
            )
        for finding, assessment in zip(
            self.findings,
            self.policy_assessment.assessments,
        ):
            finding.validate()
            if finding.policy_assessment is not assessment:
                raise InvalidCollectionChangeApprovalCompatibilityContextError(
                    "Finding must retain the exact policy assessment."
                )
            if finding.approval_decision is not None:
                expected_reference = (
                    create_collection_change_proposal_reference(
                        self.policy_assessment.plan,
                        assessment.proposal,
                    )
                )
                if (
                    finding.approval_decision.proposal_reference
                    != expected_reference
                ):
                    raise InvalidCollectionChangeApprovalCompatibilityContextError(
                        "Finding approval decision must reference its exact "
                        "policy proposal."
                    )

        expected_decisions = tuple(
            finding.approval_decision
            for finding in self.findings
            if finding.approval_decision is not None
        )
        if expected_decisions != self.approval_record.decisions:
            raise InvalidCollectionChangeApprovalCompatibilityContextError(
                "Findings must retain every approval decision in plan order."
            )

        expected = _summaries(self.findings)
        actual = (
            self.contains_incompatible_items,
            self.contains_unresolved_items,
            self.contains_blocked_items,
            self.required_decisions_complete,
            self.contains_approve_decisions,
            self.contains_reject_decisions,
            self.contains_defer_decisions,
        )
        if any(not isinstance(value, bool) for value in actual):
            raise TypeError("Compatibility summaries must be booleans.")
        if actual != expected:
            raise InvalidCollectionChangeApprovalCompatibilityContextError(
                "Compatibility summaries are inconsistent with findings."
            )


class CollectionChangeApprovalCompatibilityValidator:
    """Stateless validator with no authorization or freshness behavior."""

    __slots__ = ()

    def validate(
        self,
        policy_assessment: CollectionChangePlanPolicyAssessment,
        approval_record: CollectionChangePlanApproval,
    ) -> CollectionChangePlanApprovalCompatibility:
        if not isinstance(
            policy_assessment,
            CollectionChangePlanPolicyAssessment,
        ):
            raise TypeError(
                "policy_assessment must be a "
                "CollectionChangePlanPolicyAssessment."
            )
        if not isinstance(
            approval_record,
            CollectionChangePlanApproval,
        ):
            raise TypeError(
                "approval_record must be a CollectionChangePlanApproval."
            )
        policy_assessment.validate()
        approval_record.validate()
        _validate_plan_linkage(policy_assessment, approval_record)

        expected_references = tuple(
            create_collection_change_proposal_reference(
                policy_assessment.plan,
                item.proposal,
            )
            for item in policy_assessment.assessments
        )
        expected_set = frozenset(expected_references)
        decision_by_reference: dict[
            CollectionChangeProposalReference,
            CollectionChangeProposalApproval,
        ] = {}
        for decision in approval_record.decisions:
            reference = decision.proposal_reference
            if reference not in expected_set:
                raise UnmatchedCollectionChangeApprovalDecisionError(
                    reference.target_field
                )
            if reference in decision_by_reference:
                raise InvalidCollectionChangeApprovalCompatibilityContextError(
                    "Approval decisions must not contain duplicate "
                    "proposal references."
                )
            decision_by_reference[reference] = decision

        findings: list[CollectionChangeApprovalCompatibilityFinding] = []
        for assessment, reference in zip(
            policy_assessment.assessments,
            expected_references,
        ):
            decision = decision_by_reference.get(reference)
            status, reason = _classify(
                assessment.status,
                None if decision is None else decision.decision,
            )
            finding = CollectionChangeApprovalCompatibilityFinding(
                policy_assessment=assessment,
                approval_decision=decision,
                status=status,
                reason=reason,
            )
            finding.validate()
            findings.append(finding)

        finding_tuple = tuple(findings)
        summaries = _summaries(finding_tuple)
        result = CollectionChangePlanApprovalCompatibility(
            policy_assessment=policy_assessment,
            approval_record=approval_record,
            findings=finding_tuple,
            contains_incompatible_items=summaries[0],
            contains_unresolved_items=summaries[1],
            contains_blocked_items=summaries[2],
            required_decisions_complete=summaries[3],
            contains_approve_decisions=summaries[4],
            contains_reject_decisions=summaries[5],
            contains_defer_decisions=summaries[6],
        )
        result.validate()
        return result


def validate_collection_change_approval_compatibility(
    policy_assessment: CollectionChangePlanPolicyAssessment,
    approval_record: CollectionChangePlanApproval,
) -> CollectionChangePlanApprovalCompatibility:
    """Return complete diagnostics without granting execution authority."""

    return CollectionChangeApprovalCompatibilityValidator().validate(
        policy_assessment,
        approval_record,
    )


def require_compatible_collection_change_approval(
    policy_assessment: CollectionChangePlanPolicyAssessment,
    approval_record: CollectionChangePlanApproval,
) -> CollectionChangePlanApprovalCompatibility:
    """Require compatible evidence; unresolved evidence may still return."""

    result = validate_collection_change_approval_compatibility(
        policy_assessment,
        approval_record,
    )
    if result.contains_incompatible_items:
        raise IncompatibleCollectionChangeApprovalError(
            tuple(
                item.policy_assessment.proposal.target_field
                for item in result.findings
                if (
                    item.status
                    is CollectionChangeApprovalCompatibilityStatus.INCOMPATIBLE
                )
            )
        )
    return result


def require_resolved_collection_change_approval(
    policy_assessment: CollectionChangePlanPolicyAssessment,
    approval_record: CollectionChangePlanApproval,
) -> CollectionChangePlanApprovalCompatibility:
    """Require compatible, resolved decisions without authorizing mutation.

    Resolution describes only decision state.  It is independent from policy
    blocking, rejection, freshness, and execution eligibility.
    """

    result = require_compatible_collection_change_approval(
        policy_assessment,
        approval_record,
    )
    if result.contains_unresolved_items:
        raise UnresolvedCollectionChangeApprovalError(
            tuple(
                item.policy_assessment.proposal.target_field
                for item in result.findings
                if (
                    item.status
                    is CollectionChangeApprovalCompatibilityStatus.COMPATIBLE_UNRESOLVED
                )
            )
        )
    return result


def _validate_plan_linkage(
    policy_assessment: CollectionChangePlanPolicyAssessment,
    approval_record: CollectionChangePlanApproval,
) -> None:
    plan = policy_assessment.plan
    if (
        approval_record.target_record != plan.target_record
        or approval_record.source_coin_id != plan.source_coin_id
        or approval_record.review_session_id != plan.review_session_id
        or approval_record.source_fingerprint != plan.source_fingerprint
        or approval_record.plan_schema_version != plan.schema_version
    ):
        raise MismatchedCollectionChangeApprovalPlanError(
            "Approval record does not match the assessed plan linkage."
        )


def _classify(
    policy_status: CollectionChangePolicyStatus,
    decision: CollectionChangeApprovalDecision | None,
) -> _Compatibility:
    result = _POLICY_MATRIX.get((policy_status, decision))
    if result is None:
        raise InvalidCollectionChangeApprovalCompatibilityContextError(
            "Policy status and approval decision have no explicit "
            "compatibility rule."
        )
    return result


def _summaries(
    findings: tuple[CollectionChangeApprovalCompatibilityFinding, ...],
) -> tuple[bool, bool, bool, bool, bool, bool, bool]:
    statuses = tuple(item.status for item in findings)
    decisions = tuple(
        item.approval_decision.decision
        for item in findings
        if item.approval_decision is not None
    )
    required_complete = all(
        (
            item.policy_assessment.status
            is not CollectionChangePolicyStatus.REQUIRES_APPROVAL
        )
        or (
            item.approval_decision is not None
            and item.approval_decision.decision
            is not CollectionChangeApprovalDecision.DEFER
        )
        for item in findings
    )
    return (
        CollectionChangeApprovalCompatibilityStatus.INCOMPATIBLE in statuses,
        (
            CollectionChangeApprovalCompatibilityStatus.COMPATIBLE_UNRESOLVED
            in statuses
        ),
        any(
            item.policy_assessment.status
            is CollectionChangePolicyStatus.BLOCKED_CONFLICT
            for item in findings
        ),
        required_complete,
        CollectionChangeApprovalDecision.APPROVE in decisions,
        CollectionChangeApprovalDecision.REJECT in decisions,
        CollectionChangeApprovalDecision.DEFER in decisions,
    )
