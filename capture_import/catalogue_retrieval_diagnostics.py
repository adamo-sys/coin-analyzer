"""Deterministic diagnostics for bounded catalogue retrieval results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .catalogue_retrieval import CatalogueRetrievalResult
from .evidence_candidate_resolver import NormalizedEvidence, normalize_denomination, normalize_year


class RetrievalDisposition(str, Enum):
    """Shape of a retrieval result before candidate verification."""

    NO_MATCH = "no_match"
    SINGLE = "single"
    NARROW = "narrow"
    BROAD = "broad"


@dataclass(frozen=True, slots=True)
class RetrievalDiagnostics:
    """Candidate-set diagnostics; never an identity acceptance decision."""

    disposition: RetrievalDisposition
    candidate_count: int
    year_match_count: int
    denomination_match_count: int
    joint_match_count: int
    candidate_ids: tuple[str, ...]
    needs_verification: bool


def diagnose_retrieval(
    result: CatalogueRetrievalResult,
    evidence: NormalizedEvidence,
) -> RetrievalDiagnostics:
    """Describe candidate-set ambiguity using deterministic evidence matches."""

    if not isinstance(result, CatalogueRetrievalResult):
        raise TypeError("result must be CatalogueRetrievalResult.")
    if not isinstance(evidence, NormalizedEvidence):
        raise TypeError("evidence must be NormalizedEvidence.")

    candidates = result.candidates
    count = len(candidates)
    if count == 0:
        disposition = RetrievalDisposition.NO_MATCH
    elif count == 1:
        disposition = RetrievalDisposition.SINGLE
    elif count <= 5:
        disposition = RetrievalDisposition.NARROW
    else:
        disposition = RetrievalDisposition.BROAD

    year_matches = 0
    denomination_matches = 0
    joint_matches = 0
    for candidate in candidates:
        year_match = (
            evidence.year is not None
            and normalize_year(candidate.year) == evidence.year
        )
        denomination_match = (
            evidence.denomination is not None
            and normalize_denomination(candidate.denomination)
            == evidence.denomination
        )
        year_matches += int(year_match)
        denomination_matches += int(denomination_match)

        supplied_fields = int(evidence.year is not None) + int(
            evidence.denomination is not None
        )
        if supplied_fields and (
            (evidence.year is None or year_match)
            and (evidence.denomination is None or denomination_match)
        ):
            joint_matches += 1

    return RetrievalDiagnostics(
        disposition=disposition,
        candidate_count=count,
        year_match_count=year_matches,
        denomination_match_count=denomination_matches,
        joint_match_count=joint_matches,
        candidate_ids=tuple(candidate.candidate_id for candidate in candidates),
        needs_verification=count > 0,
    )
