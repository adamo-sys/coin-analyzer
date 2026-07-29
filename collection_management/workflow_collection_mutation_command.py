"""Construct immutable collection mutation commands from Unit 1E diagnostics.

A CollectionMutationCommand is an immutable description of proposed field
changes and expected prior values.  It is not authorization to write and does
not prove repository state remains current.
"""

from __future__ import annotations

from dataclasses import dataclass

from collection_management.workflow_collection_change_plan_models import (
    CollectionChangeOperation,
    CollectionChangePlan,
    CollectionFieldChangeProposal,
    CollectionRecordReference,
)
from collection_management.workflow_collection_mutation_eligibility import (
    CollectionChangePlanMutationEligibility,
    CollectionMutationEligibilityError,
    CollectionMutationEligibilityFinding,
    CollectionMutationEligibilityStatus,
)


class CollectionMutationCommandError(ValueError):
    """A mutation command cannot be constructed from supplied diagnostics."""


class InvalidCollectionMutationCommandContextError(
    CollectionMutationCommandError
):
    """The command input or reconstructed command is invalid."""


class NonConstructibleCollectionMutationCommandError(
    CollectionMutationCommandError
):
    """Eligibility diagnostics cannot produce a complete command."""

    def __init__(
        self,
        *,
        excluded_fields: tuple[str, ...],
        blocked_fields: tuple[str, ...],
        unresolved_fields: tuple[str, ...],
        no_eligible_items: bool,
    ) -> None:
        self.excluded_fields = excluded_fields
        self.blocked_fields = blocked_fields
        self.unresolved_fields = unresolved_fields
        self.no_eligible_items = no_eligible_items
        super().__init__(
            "Collection mutation command is nonconstructible; "
            f"excluded={excluded_fields!r}, "
            f"blocked={blocked_fields!r}, "
            f"unresolved={unresolved_fields!r}, "
            f"no_eligible_items={no_eligible_items!r}."
        )


class InvalidCollectionMutationCommandItemError(
    CollectionMutationCommandError
):
    """One reconstructed command item is invalid."""


_MUTATING_OPERATIONS = frozenset(
    {
        CollectionChangeOperation.ADD,
        CollectionChangeOperation.UPDATE,
        CollectionChangeOperation.CLEAR,
    }
)


@dataclass(frozen=True, slots=True)
class CollectionMutationCommandItem:
    """One exact eligible finding exposed as expected and desired state."""

    eligibility_finding: CollectionMutationEligibilityFinding

    @property
    def proposal(self) -> CollectionFieldChangeProposal:
        """Return the exact proposal retained by the source finding."""

        return self.eligibility_finding.proposal

    @property
    def target_field(self) -> str:
        return self.proposal.target_field

    @property
    def operation(self) -> CollectionChangeOperation:
        return self.proposal.operation

    @property
    def expected_current_value(self) -> str | None:
        """Return None for expected absence, otherwise the exact value."""

        return self.proposal.current_value

    @property
    def desired_value(self) -> str | None:
        """Return None for clearing, otherwise the exact desired value."""

        return self.proposal.proposed_value

    def validate(self) -> None:
        if not isinstance(
            self.eligibility_finding,
            CollectionMutationEligibilityFinding,
        ):
            raise InvalidCollectionMutationCommandItemError(
                "eligibility_finding must be a "
                "CollectionMutationEligibilityFinding."
            )
        try:
            self.eligibility_finding.validate()
        except (CollectionMutationEligibilityError, TypeError, ValueError) as error:
            raise InvalidCollectionMutationCommandItemError(
                str(error)
            ) from error
        if (
            self.eligibility_finding.status
            is not CollectionMutationEligibilityStatus.ELIGIBLE
        ):
            raise InvalidCollectionMutationCommandItemError(
                "Command items require an ELIGIBLE source finding."
            )
        if self.operation not in _MUTATING_OPERATIONS:
            raise InvalidCollectionMutationCommandItemError(
                "Command items require an explicit mutating operation."
            )


@dataclass(frozen=True, slots=True)
class CollectionMutationCommand:
    """A nonempty transient command with exact Unit 1E traceability."""

    eligibility: CollectionChangePlanMutationEligibility
    items: tuple[CollectionMutationCommandItem, ...]

    @property
    def plan(self) -> CollectionChangePlan:
        """Return the exact source plan retained by approval diagnostics."""

        return self.eligibility.approval_compatibility.policy_assessment.plan

    @property
    def target_record(self) -> CollectionRecordReference:
        return self.plan.target_record

    @property
    def target_fields(self) -> tuple[str, ...]:
        return tuple(item.target_field for item in self.items)

    def validate(self) -> None:
        _validate_eligibility(self.eligibility)
        _require_constructible(self.eligibility)
        if not isinstance(self.items, tuple):
            raise InvalidCollectionMutationCommandContextError(
                "items must be a tuple."
            )
        if not self.items:
            raise InvalidCollectionMutationCommandContextError(
                "items must contain at least one command item."
            )
        if any(
            not isinstance(item, CollectionMutationCommandItem)
            for item in self.items
        ):
            raise InvalidCollectionMutationCommandContextError(
                "items must contain CollectionMutationCommandItem values."
            )

        expected = tuple(
            finding
            for finding in self.eligibility.findings
            if finding.status is CollectionMutationEligibilityStatus.ELIGIBLE
        )
        if len(self.items) != len(expected):
            raise InvalidCollectionMutationCommandContextError(
                "Items must cover every eligible finding exactly once."
            )
        seen_fields: set[str] = set()
        for item, finding in zip(self.items, expected):
            item.validate()
            if item.eligibility_finding is not finding:
                raise InvalidCollectionMutationCommandContextError(
                    "Items must retain exact eligible findings in plan order."
                )
            if item.target_field in seen_fields:
                raise InvalidCollectionMutationCommandContextError(
                    "Command items contain a duplicate target field."
                )
            seen_fields.add(item.target_field)


class CollectionMutationCommandBuilder:
    """Stateless construction with no repository or execution behavior."""

    __slots__ = ()

    def build(
        self,
        eligibility: CollectionChangePlanMutationEligibility,
    ) -> CollectionMutationCommand:
        _validate_eligibility(eligibility)
        _require_constructible(eligibility)

        items: list[CollectionMutationCommandItem] = []
        for finding in eligibility.findings:
            if finding.status is CollectionMutationEligibilityStatus.ELIGIBLE:
                item = CollectionMutationCommandItem(
                    eligibility_finding=finding,
                )
                item.validate()
                items.append(item)

        result = CollectionMutationCommand(
            eligibility=eligibility,
            items=tuple(items),
        )
        result.validate()
        return result


def build_collection_mutation_command(
    eligibility: CollectionChangePlanMutationEligibility,
) -> CollectionMutationCommand:
    """Build data only; no write authority or execution is produced."""

    return CollectionMutationCommandBuilder().build(eligibility)


def _validate_eligibility(eligibility: object) -> None:
    if not isinstance(eligibility, CollectionChangePlanMutationEligibility):
        raise InvalidCollectionMutationCommandContextError(
            "eligibility must be a CollectionChangePlanMutationEligibility."
        )
    try:
        eligibility.validate()
    except (CollectionMutationEligibilityError, TypeError, ValueError) as error:
        raise InvalidCollectionMutationCommandContextError(str(error)) from error


def _require_constructible(
    eligibility: CollectionChangePlanMutationEligibility,
) -> None:
    excluded: list[str] = []
    blocked: list[str] = []
    unresolved: list[str] = []
    eligible_count = 0
    for finding in eligibility.findings:
        status = finding.status
        if status is CollectionMutationEligibilityStatus.ELIGIBLE:
            eligible_count += 1
        elif status is CollectionMutationEligibilityStatus.NO_CHANGE:
            continue
        elif status is CollectionMutationEligibilityStatus.EXCLUDED:
            excluded.append(finding.proposal.target_field)
        elif status is CollectionMutationEligibilityStatus.BLOCKED:
            blocked.append(finding.proposal.target_field)
        elif status is CollectionMutationEligibilityStatus.UNRESOLVED:
            unresolved.append(finding.proposal.target_field)
        else:
            raise InvalidCollectionMutationCommandContextError(
                "Eligibility status has no explicit command policy."
            )
    if excluded or blocked or unresolved or eligible_count == 0:
        raise NonConstructibleCollectionMutationCommandError(
            excluded_fields=tuple(excluded),
            blocked_fields=tuple(blocked),
            unresolved_fields=tuple(unresolved),
            no_eligible_items=eligible_count == 0,
        )
