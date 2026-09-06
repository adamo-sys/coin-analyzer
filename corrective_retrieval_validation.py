"""Deterministic corrective retrieval validation for Issue #93 Slice D.

This module independently re-validates ranked retrieval results against the
caller-supplied retrieval context before downstream use. It can reject weak or
out-of-scope context and compact surviving ranks without changing evidence
content, provenance, or authority. It performs no persistence, network access,
model calls, GUI operations, collection mutation, or evidence promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re

from retrieval_contracts import (
    RankedRetrievalResult,
    RetrievalContext,
    RetrievalValidationDecision,
    RetrievalValidationOutcome,
)


_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_MAX_MINIMUM_SHARED_QUERY_TOKENS = 10_000

CANDIDATE_SCOPE_MISMATCH = "candidate_scope_mismatch"
INSUFFICIENT_QUERY_OVERLAP = "insufficient_query_overlap"
METADATA_FILTER_MISMATCH = "metadata_filter_mismatch"
SOURCE_TYPE_MISMATCH = "source_type_mismatch"


@dataclass(frozen=True, slots=True)
class CorrectiveRetrievalPolicy:
    """Explicit deterministic thresholds for corrective validation."""

    minimum_shared_query_tokens: int = 1

    def validate(self) -> None:
        value = self.minimum_shared_query_tokens
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("minimum_shared_query_tokens must be an integer.")
        if value < 1 or value > _MAX_MINIMUM_SHARED_QUERY_TOKENS:
            raise ValueError(
                "minimum_shared_query_tokens must be between 1 and "
                f"{_MAX_MINIMUM_SHARED_QUERY_TOKENS}."
            )


def _tokens(text: str) -> frozenset[str]:
    return frozenset(
        match.group(0).casefold()
        for match in _TOKEN_RE.finditer(text)
    )


def validate_ranked_retrieval_result(
    context: RetrievalContext,
    result: RankedRetrievalResult,
    *,
    policy: CorrectiveRetrievalPolicy | None = None,
) -> RetrievalValidationOutcome:
    """Return one explicit ACCEPT/REJECT decision without trusting rationale.

    ``RankedRetrievalResult.rationale`` is intentionally ignored because the
    frozen Slice A contract defines it as descriptive only. Validation is
    recomputed from the immutable query, result item, and explicit policy.
    """

    if not isinstance(context, RetrievalContext):
        raise TypeError("context must be a RetrievalContext.")
    context.validate()

    if not isinstance(result, RankedRetrievalResult):
        raise TypeError("result must be a RankedRetrievalResult.")
    result.validate()

    selected_policy = policy or CorrectiveRetrievalPolicy()
    if not isinstance(selected_policy, CorrectiveRetrievalPolicy):
        raise TypeError("policy must be a CorrectiveRetrievalPolicy.")
    selected_policy.validate()

    reasons: list[str] = []
    item = result.item
    query = context.query

    if context.candidate_item_ids and item.item_id not in context.candidate_item_ids:
        reasons.append(CANDIDATE_SCOPE_MISMATCH)

    if query.source_types and item.provenance.source_type not in query.source_types:
        reasons.append(SOURCE_TYPE_MISMATCH)

    if query.metadata_filters:
        metadata = dict(item.metadata)
        if any(metadata.get(key) != expected for key, expected in query.metadata_filters):
            reasons.append(METADATA_FILTER_MISMATCH)

    shared_query_tokens = _tokens(query.query_text).intersection(_tokens(item.text))
    if len(shared_query_tokens) < selected_policy.minimum_shared_query_tokens:
        reasons.append(INSUFFICIENT_QUERY_OVERLAP)

    reason_codes = tuple(sorted(reasons))
    outcome = RetrievalValidationOutcome(
        item_id=item.item_id,
        decision=(
            RetrievalValidationDecision.REJECT
            if reason_codes
            else RetrievalValidationDecision.ACCEPT
        ),
        reason_codes=reason_codes,
    )
    outcome.validate()
    return outcome


def validate_and_rerank_retrieval_results(
    context: RetrievalContext,
    results: tuple[RankedRetrievalResult, ...],
    *,
    policy: CorrectiveRetrievalPolicy | None = None,
) -> tuple[tuple[RankedRetrievalResult, ...], tuple[RetrievalValidationOutcome, ...]]:
    """Filter rejected results and compact surviving ranks deterministically.

    Input ordering must agree with strictly increasing, unique source ranks.
    Accepted results retain their original item and rationale verbatim; only the
    rank is compacted after rejected context is removed.
    """

    if not isinstance(results, tuple):
        raise TypeError("results must be a tuple.")
    if not isinstance(context, RetrievalContext):
        raise TypeError("context must be a RetrievalContext.")
    context.validate()

    selected_policy = policy or CorrectiveRetrievalPolicy()
    if not isinstance(selected_policy, CorrectiveRetrievalPolicy):
        raise TypeError("policy must be a CorrectiveRetrievalPolicy.")
    selected_policy.validate()

    seen_item_ids: set[str] = set()
    previous_rank = 0
    outcomes: list[RetrievalValidationOutcome] = []
    accepted: list[RankedRetrievalResult] = []

    for result in results:
        if not isinstance(result, RankedRetrievalResult):
            raise TypeError("results must contain RankedRetrievalResult values.")
        result.validate()

        if result.item.item_id in seen_item_ids:
            raise ValueError("results must not contain duplicate item IDs.")
        seen_item_ids.add(result.item.item_id)

        if result.rank <= previous_rank:
            raise ValueError("results must be ordered by strictly increasing rank.")
        previous_rank = result.rank

        outcome = validate_ranked_retrieval_result(
            context,
            result,
            policy=selected_policy,
        )
        outcomes.append(outcome)

        if outcome.decision is RetrievalValidationDecision.ACCEPT:
            accepted.append(replace(result, rank=len(accepted) + 1))

    for result in accepted:
        result.validate()
    for outcome in outcomes:
        outcome.validate()

    return tuple(accepted), tuple(outcomes)
