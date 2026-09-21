"""Provider-neutral contract for bounded catalogue candidate retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .evidence_candidate_resolver import CatalogueCandidate, NormalizedEvidence
from .numeral_evidence_envelope import NumeralEvidenceEnvelope


_MAX_RETRIEVAL_RESULTS = 25


class CatalogueRetrievalContractError(ValueError):
    """Catalogue retrieval input or output violates the bounded contract."""


@dataclass(frozen=True, slots=True)
class CatalogueRetrievalRequest:
    """Conflict-free grounded evidence supplied to a catalogue retriever."""

    evidence: NormalizedEvidence
    limit: int = 10

    def __post_init__(self) -> None:
        if not isinstance(self.evidence, NormalizedEvidence):
            raise CatalogueRetrievalContractError(
                "evidence must be NormalizedEvidence."
            )
        if isinstance(self.limit, bool) or not isinstance(self.limit, int):
            raise CatalogueRetrievalContractError("limit must be an integer.")
        if not 1 <= self.limit <= _MAX_RETRIEVAL_RESULTS:
            raise CatalogueRetrievalContractError(
                f"limit must be between 1 and {_MAX_RETRIEVAL_RESULTS}."
            )
        if not _has_retrieval_evidence(self.evidence):
            raise CatalogueRetrievalContractError(
                "at least one year, denomination, or visible-text signal is required."
            )


@dataclass(frozen=True, slots=True)
class CatalogueRetrievalResult:
    """Ordered catalogue candidates plus retriever provenance."""

    candidates: tuple[CatalogueCandidate, ...]
    retriever_id: str
    query_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidates, tuple):
            raise CatalogueRetrievalContractError("candidates must be a tuple.")
        if len(self.candidates) > _MAX_RETRIEVAL_RESULTS:
            raise CatalogueRetrievalContractError(
                f"at most {_MAX_RETRIEVAL_RESULTS} candidates are allowed."
            )
        if any(not isinstance(item, CatalogueCandidate) for item in self.candidates):
            raise CatalogueRetrievalContractError(
                "all candidates must be CatalogueCandidate."
            )
        candidate_ids = [item.candidate_id for item in self.candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise CatalogueRetrievalContractError(
                "candidate IDs must be unique within a retrieval result."
            )
        _nonempty(self.retriever_id, "retriever_id")
        if self.query_id is not None:
            _nonempty(self.query_id, "query_id")


@runtime_checkable
class CatalogueRetriever(Protocol):
    """Provider-neutral interface for candidate retrieval only."""

    @property
    def retriever_id(self) -> str: ...

    def retrieve(
        self, request: CatalogueRetrievalRequest
    ) -> CatalogueRetrievalResult: ...


def request_from_numeral_envelope(
    envelope: NumeralEvidenceEnvelope,
    *,
    limit: int = 10,
) -> CatalogueRetrievalRequest:
    """Build a retrieval request only from a conflict-free ready envelope."""

    if not isinstance(envelope, NumeralEvidenceEnvelope):
        raise TypeError("envelope must be NumeralEvidenceEnvelope.")
    if envelope.has_conflict:
        raise CatalogueRetrievalContractError(
            "conflicting evidence cannot be sent to catalogue retrieval."
        )
    if not envelope.retrieval_ready:
        raise CatalogueRetrievalContractError(
            "evidence envelope is not retrieval-ready."
        )
    return CatalogueRetrievalRequest(evidence=envelope.normalized, limit=limit)


def _has_retrieval_evidence(evidence: NormalizedEvidence) -> bool:
    return bool(
        evidence.year is not None
        or evidence.denomination is not None
        or evidence.visible_text
    )


def _nonempty(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CatalogueRetrievalContractError(
            f"{name} must be a non-empty string."
        )
