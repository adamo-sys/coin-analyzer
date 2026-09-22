"""Deterministic in-memory catalogue retriever for grounded evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable

from .catalogue_retrieval import (
    CatalogueRetrievalContractError,
    CatalogueRetrievalRequest,
    CatalogueRetrievalResult,
)
from .evidence_candidate_resolver import (
    CatalogueCandidate,
    normalize_denomination,
    normalize_year,
)


_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class _RetrievalScore:
    candidate: CatalogueCandidate
    score: int


class InMemoryCatalogueRetriever:
    """Rank a supplied bounded catalogue without model calls or external I/O."""

    def __init__(
        self,
        candidates: Iterable[CatalogueCandidate],
        *,
        retriever_id: str = "in-memory-catalogue-v1",
    ) -> None:
        rows = tuple(candidates)
        if any(not isinstance(item, CatalogueCandidate) for item in rows):
            raise CatalogueRetrievalContractError(
                "all catalogue rows must be CatalogueCandidate."
            )
        ids = [item.candidate_id for item in rows]
        if len(set(ids)) != len(ids):
            raise CatalogueRetrievalContractError(
                "catalogue candidate IDs must be unique."
            )
        if not isinstance(retriever_id, str) or not retriever_id.strip():
            raise CatalogueRetrievalContractError(
                "retriever_id must be a non-empty string."
            )
        self._candidates = rows
        self._retriever_id = retriever_id

    @property
    def retriever_id(self) -> str:
        return self._retriever_id

    def retrieve(
        self, request: CatalogueRetrievalRequest
    ) -> CatalogueRetrievalResult:
        if not isinstance(request, CatalogueRetrievalRequest):
            raise TypeError("request must be CatalogueRetrievalRequest.")

        ranked = sorted(
            (
                _RetrievalScore(candidate, _score(candidate, request))
                for candidate in self._candidates
            ),
            key=lambda row: (-row.score, row.candidate.candidate_id),
        )
        # A zero score means the catalogue row shares no grounded signal with
        # the request and is therefore not a retrieval candidate.
        matches = tuple(
            row.candidate for row in ranked if row.score > 0
        )[: request.limit]
        return CatalogueRetrievalResult(
            candidates=matches,
            retriever_id=self.retriever_id,
            query_id=_query_id(request),
        )


def _score(
    candidate: CatalogueCandidate,
    request: CatalogueRetrievalRequest,
) -> int:
    evidence = request.evidence
    score = 0

    if evidence.year is not None:
        if normalize_year(candidate.year) == evidence.year:
            score += 4

    if evidence.denomination is not None:
        if normalize_denomination(candidate.denomination) == evidence.denomination:
            score += 3

    observed_tokens = {
        token
        for text in evidence.visible_text
        for token in _tokens(text)
        if len(token) >= 2
    }
    if observed_tokens:
        catalogue_tokens = set()
        for value in (
            candidate.country,
            candidate.denomination,
            candidate.year,
            *candidate.legends,
        ):
            catalogue_tokens.update(_tokens(value))
        score += min(3, len(observed_tokens & catalogue_tokens))

    return score


def _tokens(value: object) -> tuple[str, ...]:
    return tuple(_TOKEN.findall(str(value).casefold()))


def _query_id(request: CatalogueRetrievalRequest) -> str:
    payload = {
        "country": request.evidence.country,
        "denomination": request.evidence.denomination,
        "year": request.evidence.year,
        "visible_text": request.evidence.visible_text,
        "limit": request.limit,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "catalogue-" + hashlib.sha256(encoded).hexdigest()[:16]
