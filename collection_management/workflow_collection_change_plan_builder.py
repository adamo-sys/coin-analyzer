"""Build the durable Unit 1A plan from validated Unit 1D proposals.

This is an aggregation boundary only.  It preserves the complete proposal
tuple and linkage without reinterpreting operations, approval requirements,
reason codes, values, or source evidence.  It performs no policy selection,
persistence, stale-state validation, approval, execution, or mutation.
"""

from __future__ import annotations

from collection_management.workflow_collection_change_plan_models import (
    CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
    CollectionChangePlan,
)
from collection_management.workflow_collection_change_proposal_builder import (
    CollectionChangeProposalBuildError,
    CollectionChangeProposalBuildResult,
)


class CollectionChangePlanBuildError(ValueError):
    """A validated proposal result cannot be aggregated into a plan."""


class InvalidCollectionChangePlanBuildContextError(
    CollectionChangePlanBuildError
):
    """The supplied Unit 1D result has inconsistent aggregate linkage."""


class CollectionChangePlanBuilder:
    """Stateless direct conversion from Unit 1D result to Unit 1A plan."""

    __slots__ = ()

    def build(
        self,
        proposal_result: CollectionChangeProposalBuildResult,
    ) -> CollectionChangePlan:
        if not isinstance(
            proposal_result,
            CollectionChangeProposalBuildResult,
        ):
            raise TypeError(
                "proposal_result must be a "
                "CollectionChangeProposalBuildResult."
            )
        try:
            proposal_result.validate()
        except CollectionChangeProposalBuildError as error:
            raise InvalidCollectionChangePlanBuildContextError(
                str(error)
            ) from error

        plan = CollectionChangePlan(
            schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
            target_record=proposal_result.target_record,
            source_coin_id=proposal_result.source_coin_id,
            proposals=proposal_result.proposals,
            review_session_id=proposal_result.review_session_id,
            source_fingerprint=proposal_result.source_fingerprint,
        )
        plan.validate()
        return plan


def build_collection_change_plan(
    proposal_result: CollectionChangeProposalBuildResult,
) -> CollectionChangePlan:
    """Build one durable plan without retaining service state."""

    return CollectionChangePlanBuilder().build(proposal_result)
