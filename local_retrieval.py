"""Deterministic local text/metadata retrieval for Issue #93 Slice B.

This module consumes frozen retrieval contracts and returns advisory ranked
results only. It performs no persistence, network access, model calls, GUI
operations, collection mutation, or evidence promotion.
"""

from __future__ import annotations

from collections.abc import Iterable
import re

from retrieval_contracts import (
    RankedRetrievalResult,
    RetrievalContext,
    RetrievableEvidenceItem,
)


_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(text: str) -> frozenset[str]:
    return frozenset(
        match.group(0).casefold()
        for match in _TOKEN_RE.finditer(text)
    )


def _metadata_dict(
    item: RetrievableEvidenceItem,
) -> dict[str, str]:
    return dict(item.metadata)


def _matches_source_type(
    context: RetrievalContext,
    item: RetrievableEvidenceItem,
) -> bool:
    if not context.query.source_types:
        return True
    return item.provenance.source_type in context.query.source_types


def _matches_candidate_scope(
    context: RetrievalContext,
    item: RetrievableEvidenceItem,
) -> bool:
    if not context.candidate_item_ids:
        return True
    return item.item_id in context.candidate_item_ids


def _metadata_match_count(
    context: RetrievalContext,
    item: RetrievableEvidenceItem,
) -> int | None:
    if not context.query.metadata_filters:
        return 0

    metadata = _metadata_dict(item)
    matched = 0

    for key, expected in context.query.metadata_filters:
        if metadata.get(key) != expected:
            return None
        matched += 1

    return matched


def retrieve_local(
    context: RetrievalContext,
    items: Iterable[RetrievableEvidenceItem],
) -> tuple[RankedRetrievalResult, ...]:
    """Return bounded deterministic advisory retrieval results."""

    context.validate()

    query_tokens = _tokens(context.query.query_text)
    candidates: list[
        tuple[int, int, str, RetrievableEvidenceItem]
    ] = []

    seen_ids: set[str] = set()

    for item in items:
        if not isinstance(item, RetrievableEvidenceItem):
            raise TypeError(
                "items must contain RetrievableEvidenceItem values."
            )

        item.validate()

        if item.item_id in seen_ids:
            raise ValueError(
                f"Duplicate retrievable item_id: {item.item_id!r}."
            )
        seen_ids.add(item.item_id)

        if not _matches_candidate_scope(context, item):
            continue

        if not _matches_source_type(context, item):
            continue

        metadata_matches = _metadata_match_count(context, item)
        if metadata_matches is None:
            continue

        shared_tokens = query_tokens.intersection(_tokens(item.text))
        if not shared_tokens:
            continue

        candidates.append(
            (
                len(shared_tokens),
                metadata_matches,
                item.item_id,
                item,
            )
        )

    candidates.sort(
        key=lambda candidate: (
            -candidate[0],
            -candidate[1],
            candidate[2],
        )
    )

    limited = candidates[: context.query.max_results]

    results = tuple(
        RankedRetrievalResult(
            item=candidate[3],
            rank=index,
            rationale=(
                f"matched_query_tokens={candidate[0]};"
                f"matched_metadata_filters={candidate[1]}"
            ),
        )
        for index, candidate in enumerate(limited, start=1)
    )

    for result in results:
        result.validate()

    return results