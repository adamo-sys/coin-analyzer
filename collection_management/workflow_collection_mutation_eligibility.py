"""Compose approval and freshness diagnostics into mutation eligibility.

Eligibility is a transient proposal-level diagnostic for a future mutation
command builder.  It is not execution authorization, does not prove current
repository state, and performs no approval or freshness revalidation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from collection_management.workflow_collection_change_approval_compatibility import (
    CollectionChangeApprovalCompatibilityFinding,
    CollectionChangeApprovalCompatibilityReason,
    CollectionChangeApprovalCompatibilityStatus,
    CollectionChangePlanApprovalCompatibility,
)
from collection_management.workflow_collection_change_plan_models import (
    CollectionFieldChangeProposal,
)
from collection_management.workflow_collection_change_policy import (
    CollectionChangePolicyStatus,
)
from collection_management.workflow_collection_freshness_compatibility import (
    CollectionChangePlanFreshnessCompatibility,
    CollectionFreshnessCompatibilityFinding,
    CollectionFreshnessCompatibilityStatus,
)


class CollectionMutationEligibilityError(ValueError):
    """Mutation eligibility diagnostics cannot be composed."""


class InvalidCollectionMutationEligibilityContextError(
    CollectionMutationEligibilityError
):
    """Eligibility inputs or reconstructed diagnostics are invalid."""


class MismatchedCollectionMutationEligibilityPlanError(
    CollectionMutationEligibilityError
):
    """Approval and freshness diagnostics describe different durable plans."""


class MisalignedCollectionMutationEligibilityFindingError(
    CollectionMutationEligibilityError
):
    """Proposal-level approval and freshness findings do not align."""


class CollectionMutationEligibilityStatus(str, Enum):
    """Proposal disposition without command or execution authority."""

    ELIGIBLE = "ELIGIBLE"
    NO_CHANGE = "NO_CHANGE"
    EXCLUDED = "EXCLUDED"
    BLOCKED = "BLOCKED"
    UNRESOLVED = "UNRESOLVED"


class CollectionMutationEligibilityReason(str, Enum):
    """Primary bounded reason for one eligibility disposition."""

    SAFE_NO_OP = "SAFE_NO_OP"
    APPROVED_AND_FRESHNESS_MATCHED = "APPROVED_AND_FRESHNESS_MATCHED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    APPROVAL_DEFERRED = "APPROVAL_DEFERRED"
    APPROVAL_MISSING = "APPROVAL_MISSING"
    APPROVAL_INCOMPATIBLE = "APPROVAL_INCOMPATIBLE"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    FRESHNESS_MISMATCHED = "FRESHNESS_MISMATCHED"
    FRESHNESS_UNAVAILABLE = "FRESHNESS_UNAVAILABLE"
    FRESHNESS_MISSING = "FRESHNESS_MISSING"


_Eligibility = tuple[
    CollectionMutationEligibilityStatus,
    CollectionMutationEligibilityReason,
]


@dataclass(frozen=True, slots=True)
class CollectionMutationEligibilityFinding:
    """One aligned pair of authoritative upstream diagnostic findings."""

    approval_finding: CollectionChangeApprovalCompatibilityFinding
    freshness_finding: CollectionFreshnessCompatibilityFinding
    status: CollectionMutationEligibilityStatus
    reason: CollectionMutationEligibilityReason

    @property
    def proposal(self) -> CollectionFieldChangeProposal:
        """Return the approval diagnostic's exact proposal object."""

        return self.approval_finding.policy_assessment.proposal

    def validate(self) -> None:
        if not isinstance(
            self.approval_finding,
            CollectionChangeApprovalCompatibilityFinding,
        ):
            raise InvalidCollectionMutationEligibilityContextError(
                "approval_finding must be a "
                "CollectionChangeApprovalCompatibilityFinding."
            )
        if not isinstance(
            self.freshness_finding,
            CollectionFreshnessCompatibilityFinding,
        ):
            raise InvalidCollectionMutationEligibilityContextError(
                "freshness_finding must be a "
                "CollectionFreshnessCompatibilityFinding."
            )
        self.approval_finding.validate()
        self.freshness_finding.validate()
        _validate_finding_alignment(
            self.approval_finding,
            self.freshness_finding,
        )
        if not isinstance(self.status, CollectionMutationEligibilityStatus):
            raise InvalidCollectionMutationEligibilityContextError(
                "status must be a CollectionMutationEligibilityStatus."
            )
        if not isinstance(self.reason, CollectionMutationEligibilityReason):
            raise InvalidCollectionMutationEligibilityContextError(
                "reason must be a CollectionMutationEligibilityReason."
            )
        expected = _classify(
            self.approval_finding,
            self.freshness_finding,
        )
        if (self.status, self.reason) != expected:
            raise InvalidCollectionMutationEligibilityContextError(
                "Finding status and reason do not match the supplied "
                "approval and freshness diagnostics."
            )


@dataclass(frozen=True, slots=True)
class CollectionChangePlanMutationEligibility:
    """Complete transient eligibility diagnostics in plan proposal order."""

    approval_compatibility: CollectionChangePlanApprovalCompatibility
    freshness_compatibility: CollectionChangePlanFreshnessCompatibility
    findings: tuple[CollectionMutationEligibilityFinding, ...]
    contains_eligible_items: bool
    contains_no_change_items: bool
    contains_excluded_items: bool
    contains_blocked_items: bool
    contains_unresolved_items: bool

    def validate(self) -> None:
        _validate_inputs(
            self.approval_compatibility,
            self.freshness_compatibility,
        )
        _validate_plan_alignment(
            self.approval_compatibility,
            self.freshness_compatibility,
        )
        if not isinstance(self.findings, tuple):
            raise InvalidCollectionMutationEligibilityContextError(
                "findings must be a tuple."
            )
        approval_findings = self.approval_compatibility.findings
        freshness_findings = self.freshness_compatibility.findings
        if len(self.findings) != len(approval_findings):
            raise InvalidCollectionMutationEligibilityContextError(
                "Findings must cover every plan proposal exactly once."
            )
        if any(
            not isinstance(item, CollectionMutationEligibilityFinding)
            for item in self.findings
        ):
            raise InvalidCollectionMutationEligibilityContextError(
                "findings must contain "
                "CollectionMutationEligibilityFinding values."
            )

        seen_fields: set[str] = set()
        for finding, approval_finding, freshness_finding in zip(
            self.findings,
            approval_findings,
            freshness_findings,
        ):
            finding.validate()
            if finding.approval_finding is not approval_finding:
                raise InvalidCollectionMutationEligibilityContextError(
                    "Finding must retain the exact approval finding."
                )
            if finding.freshness_finding is not freshness_finding:
                raise InvalidCollectionMutationEligibilityContextError(
                    "Finding must retain the exact freshness finding."
                )
            target_field = finding.proposal.target_field
            if target_field in seen_fields:
                raise InvalidCollectionMutationEligibilityContextError(
                    "Eligibility findings contain a duplicate target field."
                )
            seen_fields.add(target_field)

        actual = (
            self.contains_eligible_items,
            self.contains_no_change_items,
            self.contains_excluded_items,
            self.contains_blocked_items,
            self.contains_unresolved_items,
        )
        if any(not isinstance(value, bool) for value in actual):
            raise InvalidCollectionMutationEligibilityContextError(
                "Eligibility summaries must be booleans."
            )
        if actual != _summaries(self.findings):
            raise InvalidCollectionMutationEligibilityContextError(
                "Eligibility summaries are inconsistent with findings."
            )


class CollectionMutationEligibilityComposer:
    """Stateless composition of already-computed compatibility diagnostics."""

    __slots__ = ()

    def compose(
        self,
        approval_compatibility: CollectionChangePlanApprovalCompatibility,
        freshness_compatibility: CollectionChangePlanFreshnessCompatibility,
    ) -> CollectionChangePlanMutationEligibility:
        _validate_inputs(approval_compatibility, freshness_compatibility)
        _validate_plan_alignment(
            approval_compatibility,
            freshness_compatibility,
        )

        findings: list[CollectionMutationEligibilityFinding] = []
        for approval_finding, freshness_finding in zip(
            approval_compatibility.findings,
            freshness_compatibility.findings,
        ):
            _validate_finding_alignment(
                approval_finding,
                freshness_finding,
            )
            status, reason = _classify(
                approval_finding,
                freshness_finding,
            )
            finding = CollectionMutationEligibilityFinding(
                approval_finding=approval_finding,
                freshness_finding=freshness_finding,
                status=status,
                reason=reason,
            )
            finding.validate()
            findings.append(finding)

        finding_tuple = tuple(findings)
        summaries = _summaries(finding_tuple)
        result = CollectionChangePlanMutationEligibility(
            approval_compatibility=approval_compatibility,
            freshness_compatibility=freshness_compatibility,
            findings=finding_tuple,
            contains_eligible_items=summaries[0],
            contains_no_change_items=summaries[1],
            contains_excluded_items=summaries[2],
            contains_blocked_items=summaries[3],
            contains_unresolved_items=summaries[4],
        )
        result.validate()
        return result


def compose_collection_mutation_eligibility(
    approval_compatibility: CollectionChangePlanApprovalCompatibility,
    freshness_compatibility: CollectionChangePlanFreshnessCompatibility,
) -> CollectionChangePlanMutationEligibility:
    """Return eligibility diagnostics without constructing a command."""

    return CollectionMutationEligibilityComposer().compose(
        approval_compatibility,
        freshness_compatibility,
    )


def _validate_inputs(
    approval_compatibility: object,
    freshness_compatibility: object,
) -> None:
    if not isinstance(
        approval_compatibility,
        CollectionChangePlanApprovalCompatibility,
    ):
        raise InvalidCollectionMutationEligibilityContextError(
            "approval_compatibility must be a "
            "CollectionChangePlanApprovalCompatibility."
        )
    if not isinstance(
        freshness_compatibility,
        CollectionChangePlanFreshnessCompatibility,
    ):
        raise InvalidCollectionMutationEligibilityContextError(
            "freshness_compatibility must be a "
            "CollectionChangePlanFreshnessCompatibility."
        )
    approval_compatibility.validate()
    freshness_compatibility.validate()


def _validate_plan_alignment(
    approval_compatibility: CollectionChangePlanApprovalCompatibility,
    freshness_compatibility: CollectionChangePlanFreshnessCompatibility,
) -> None:
    approval_plan = approval_compatibility.policy_assessment.plan
    freshness_plan = freshness_compatibility.plan
    if approval_plan != freshness_plan:
        raise MismatchedCollectionMutationEligibilityPlanError(
            "Approval and freshness diagnostics must describe the same "
            "durable collection change plan."
        )
    if (
        len(approval_compatibility.findings)
        != len(freshness_compatibility.findings)
    ):
        raise MisalignedCollectionMutationEligibilityFindingError(
            "Approval and freshness findings must cover the same proposals."
        )


def _validate_finding_alignment(
    approval_finding: CollectionChangeApprovalCompatibilityFinding,
    freshness_finding: CollectionFreshnessCompatibilityFinding,
) -> None:
    approval_proposal = approval_finding.policy_assessment.proposal
    freshness_proposal = freshness_finding.proposal
    if approval_proposal != freshness_proposal:
        raise MisalignedCollectionMutationEligibilityFindingError(
            "Approval and freshness findings must describe the same durable "
            "proposal."
        )


def _classify(
    approval: CollectionChangeApprovalCompatibilityFinding,
    freshness: CollectionFreshnessCompatibilityFinding,
) -> _Eligibility:
    policy_status = approval.policy_assessment.status
    approval_status = approval.status
    approval_reason = approval.reason
    freshness_status = freshness.status

    if policy_status is CollectionChangePolicyStatus.BLOCKED_CONFLICT:
        return (
            CollectionMutationEligibilityStatus.BLOCKED,
            CollectionMutationEligibilityReason.POLICY_BLOCKED,
        )
    if (
        approval_reason
        is CollectionChangeApprovalCompatibilityReason.MISSING_REQUIRED_DECISION
    ):
        return (
            CollectionMutationEligibilityStatus.UNRESOLVED,
            CollectionMutationEligibilityReason.APPROVAL_MISSING,
        )
    if (
        approval_status
        is CollectionChangeApprovalCompatibilityStatus.INCOMPATIBLE
    ):
        return (
            CollectionMutationEligibilityStatus.EXCLUDED,
            CollectionMutationEligibilityReason.APPROVAL_INCOMPATIBLE,
        )
    if approval_reason in {
        CollectionChangeApprovalCompatibilityReason.APPROVAL_REQUIRED_REJECTED,
    }:
        return (
            CollectionMutationEligibilityStatus.EXCLUDED,
            CollectionMutationEligibilityReason.APPROVAL_REJECTED,
        )
    if approval_reason in {
        CollectionChangeApprovalCompatibilityReason.APPROVAL_REQUIRED_DEFERRED,
    }:
        return (
            CollectionMutationEligibilityStatus.UNRESOLVED,
            CollectionMutationEligibilityReason.APPROVAL_DEFERRED,
        )
    if freshness_status is CollectionFreshnessCompatibilityStatus.MISMATCHED:
        return (
            CollectionMutationEligibilityStatus.EXCLUDED,
            CollectionMutationEligibilityReason.FRESHNESS_MISMATCHED,
        )
    if freshness_status is CollectionFreshnessCompatibilityStatus.UNAVAILABLE:
        return (
            CollectionMutationEligibilityStatus.UNRESOLVED,
            CollectionMutationEligibilityReason.FRESHNESS_UNAVAILABLE,
        )
    if freshness_status is CollectionFreshnessCompatibilityStatus.MISSING:
        return (
            CollectionMutationEligibilityStatus.UNRESOLVED,
            CollectionMutationEligibilityReason.FRESHNESS_MISSING,
        )
    if (
        approval_reason
        is CollectionChangeApprovalCompatibilityReason.SAFE_NO_OP_WITHOUT_DECISION
    ):
        return (
            CollectionMutationEligibilityStatus.NO_CHANGE,
            CollectionMutationEligibilityReason.SAFE_NO_OP,
        )
    if (
        approval_reason
        is CollectionChangeApprovalCompatibilityReason.APPROVAL_REQUIRED_APPROVED
        and freshness_status is CollectionFreshnessCompatibilityStatus.MATCHED
    ):
        return (
            CollectionMutationEligibilityStatus.ELIGIBLE,
            CollectionMutationEligibilityReason.APPROVED_AND_FRESHNESS_MATCHED,
        )
    raise InvalidCollectionMutationEligibilityContextError(
        "Approval and freshness diagnostics have no explicit eligibility "
        "rule."
    )


def _summaries(
    findings: tuple[CollectionMutationEligibilityFinding, ...],
) -> tuple[bool, bool, bool, bool, bool]:
    statuses = tuple(item.status for item in findings)
    return tuple(
        status in statuses
        for status in (
            CollectionMutationEligibilityStatus.ELIGIBLE,
            CollectionMutationEligibilityStatus.NO_CHANGE,
            CollectionMutationEligibilityStatus.EXCLUDED,
            CollectionMutationEligibilityStatus.BLOCKED,
            CollectionMutationEligibilityStatus.UNRESOLVED,
        )
    )  # type: ignore[return-value]
