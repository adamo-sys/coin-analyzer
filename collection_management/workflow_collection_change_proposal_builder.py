"""Pure construction of immutable proposals from comparison evidence.

The builder translates Unit 1C evidence into Unit 1A field proposals.  It
does not decide whether a proposal should be accepted, construct a change
plan, read collection state, approve, persist, execute, or mutate anything.

Unavailable current values fail closed because Unit 1A cannot represent a
CONFLICT without a known current value.  CLEAR remains a valid Unit 1A
operation but is not emitted here because Unit 1B mapped values are strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from collection_management.workflow_collection_change_plan_models import (
    CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
    CollectionChangeApprovalRequirement,
    CollectionChangeOperation,
    CollectionChangeReasonCode,
    CollectionFieldChangeProposal,
    CollectionRecordReference,
)
from collection_management.workflow_collection_record_comparison import (
    CollectionFieldComparison,
    CollectionFieldComparisonOutcome,
    CollectionRecordComparisonResult,
)


class CollectionChangeProposalBuildError(ValueError):
    """Comparison evidence cannot produce a complete proposal result."""


class UnsupportedCollectionComparisonOutcomeError(
    CollectionChangeProposalBuildError
):
    """The comparison outcome has no explicit proposal policy."""

    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        rendered = (
            outcome.value
            if isinstance(outcome, CollectionFieldComparisonOutcome)
            else repr(outcome)
        )
        super().__init__(
            f"Unsupported collection comparison outcome: {rendered}."
        )


class UnavailableCollectionProposalSourceError(
    CollectionChangeProposalBuildError
):
    """A proposal cannot honestly represent an unknown current value."""

    def __init__(self, target_field: str) -> None:
        self.target_field = target_field
        super().__init__(
            "Current collection value is unavailable for target field "
            f"{target_field!r}; no proposal was built."
        )


class InvalidCollectionChangeProposalContextError(
    CollectionChangeProposalBuildError
):
    """The supplied comparison aggregate is structurally inconsistent."""


class DuplicateCollectionChangeProposalFieldError(
    CollectionChangeProposalBuildError
):
    """More than one proposal would target the same collection field."""

    def __init__(self, target_field: str) -> None:
        self.target_field = target_field
        super().__init__(
            f"Duplicate collection change proposal field: {target_field!r}."
        )


_OUTCOME_POLICY: MappingProxyType[
    CollectionFieldComparisonOutcome,
    tuple[
        CollectionChangeOperation,
        CollectionChangeApprovalRequirement,
        CollectionChangeReasonCode,
    ],
] = MappingProxyType(
    {
        CollectionFieldComparisonOutcome.ABSENT: (
            CollectionChangeOperation.ADD,
            CollectionChangeApprovalRequirement.REQUIRED,
            CollectionChangeReasonCode.NEW_VALUE,
        ),
        CollectionFieldComparisonOutcome.EMPTY: (
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalRequirement.REQUIRED,
            CollectionChangeReasonCode.DIFFERENT_VALUE,
        ),
        CollectionFieldComparisonOutcome.EXACT_MATCH: (
            CollectionChangeOperation.NO_CHANGE,
            CollectionChangeApprovalRequirement.NOT_REQUIRED,
            CollectionChangeReasonCode.EQUIVALENT_VALUE,
        ),
        CollectionFieldComparisonOutcome.DIFFERENT: (
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalRequirement.REQUIRED,
            CollectionChangeReasonCode.DIFFERENT_VALUE,
        ),
    }
)


@dataclass(frozen=True, slots=True)
class CollectionChangeProposalBuildResult:
    """Atomic in-memory proposals with preserved source linkage."""

    target_record: CollectionRecordReference
    source_coin_id: str
    reviewer_id: str
    proposals: tuple[CollectionFieldChangeProposal, ...]
    review_session_id: str | None = None
    source_fingerprint: str | None = None

    def validate(self) -> None:
        if not isinstance(self.target_record, CollectionRecordReference):
            raise TypeError(
                "target_record must be a CollectionRecordReference."
            )
        self.target_record.validate()
        _required_text(self.source_coin_id, "source_coin_id")
        _required_text(self.reviewer_id, "reviewer_id")
        _optional_text(self.review_session_id, "review_session_id")
        _optional_text(self.source_fingerprint, "source_fingerprint")
        if not isinstance(self.proposals, tuple):
            raise TypeError("proposals must be a tuple.")
        if not self.proposals:
            raise ValueError("proposals must contain at least one proposal.")
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

        targets: set[str] = set()
        source_fields: set[str] = set()
        for proposal in self.proposals:
            proposal.validate()
            if proposal.target_record != self.target_record:
                raise InvalidCollectionChangeProposalContextError(
                    "All proposals must use the result target_record."
                )
            observation = proposal.source_observation
            if observation.source_coin_id != self.source_coin_id:
                raise InvalidCollectionChangeProposalContextError(
                    "All proposals must use the result source_coin_id."
                )
            if observation.reviewer_id != self.reviewer_id:
                raise InvalidCollectionChangeProposalContextError(
                    "All proposals must use the result reviewer_id."
                )
            if proposal.target_field in targets:
                raise DuplicateCollectionChangeProposalFieldError(
                    proposal.target_field
                )
            targets.add(proposal.target_field)
            if observation.field_name in source_fields:
                raise InvalidCollectionChangeProposalContextError(
                    "Duplicate proposal source field."
                )
            source_fields.add(observation.field_name)


class CollectionChangeProposalBuilder:
    """Stateless structural translator from comparisons to proposals."""

    __slots__ = ()

    def build(
        self,
        comparison_result: CollectionRecordComparisonResult,
    ) -> CollectionChangeProposalBuildResult:
        if not isinstance(
            comparison_result,
            CollectionRecordComparisonResult,
        ):
            raise TypeError(
                "comparison_result must be a "
                "CollectionRecordComparisonResult."
            )
        try:
            comparison_result.validate()
        except CollectionChangeProposalBuildError:
            raise
        except (TypeError, ValueError) as error:
            raise InvalidCollectionChangeProposalContextError(
                str(error)
            ) from error

        mapping_result = comparison_result.mapping_result
        proposals: list[CollectionFieldChangeProposal] = []
        targets: set[str] = set()
        for comparison in comparison_result.comparisons:
            proposal = self._build_one(
                comparison,
                comparison_result.target_record,
            )
            if proposal.target_field in targets:
                raise DuplicateCollectionChangeProposalFieldError(
                    proposal.target_field
                )
            proposals.append(proposal)
            targets.add(proposal.target_field)

        result = CollectionChangeProposalBuildResult(
            target_record=comparison_result.target_record,
            source_coin_id=mapping_result.source_coin_id,
            reviewer_id=mapping_result.reviewer_id,
            proposals=tuple(
                sorted(proposals, key=lambda item: item.target_field)
            ),
            review_session_id=mapping_result.review_session_id,
            source_fingerprint=mapping_result.source_fingerprint,
        )
        result.validate()
        return result

    @staticmethod
    def _build_one(
        comparison: CollectionFieldComparison,
        target_record: CollectionRecordReference,
    ) -> CollectionFieldChangeProposal:
        if (
            comparison.outcome
            is CollectionFieldComparisonOutcome.UNAVAILABLE
        ):
            raise UnavailableCollectionProposalSourceError(
                comparison.target_field.value
            )
        policy = _OUTCOME_POLICY.get(comparison.outcome)
        if policy is None:
            raise UnsupportedCollectionComparisonOutcomeError(
                comparison.outcome
            )
        operation, approval, reason = policy
        proposal = CollectionFieldChangeProposal(
            schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
            target_record=target_record,
            target_field=comparison.target_field.value,
            current_value=comparison.current_value,
            proposed_value=comparison.mapped_value,
            operation=operation,
            approval_requirement=approval,
            source_observation=comparison.mapping.source_observation,
            reason_code=reason,
            rationale=comparison.mapping.source_observation.rationale,
        )
        proposal.validate()
        return proposal


def build_collection_change_proposals(
    comparison_result: CollectionRecordComparisonResult,
) -> CollectionChangeProposalBuildResult:
    """Build proposals without retaining service state."""

    return CollectionChangeProposalBuilder().build(comparison_result)


def _required_text(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value.strip():
        raise ValueError(f"{name} must not be blank.")


def _optional_text(value: object, name: str) -> None:
    if value is None:
        return
    _required_text(value, name)
