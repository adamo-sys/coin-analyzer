"""Deterministic verification of retrieved catalogue candidates against coin-side evidence."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .catalogue_retrieval import CatalogueRetrievalResult
from .evidence_candidate_resolver import (
    CatalogueCandidate,
    NormalizedEvidence,
    normalize_country,
    normalize_denomination,
    normalize_year,
)
from .grounded_visual_observation import GroundedVisualObservation
from .numeral_evidence_envelope import build_numeral_evidence_envelope


_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class CandidateVerification:
    """Evidence agreement for one candidate; never an acceptance decision."""

    candidate: CatalogueCandidate
    matched_fields: tuple[str, ...]
    conflicting_fields: tuple[str, ...]
    supporting_roles: tuple[str, ...]
    supporting_text: tuple[str, ...]
    verified: bool


@dataclass(frozen=True, slots=True)
class CandidateVerificationReport:
    """Ordered verification rows for a retrieved candidate set."""

    rows: tuple[CandidateVerification, ...]
    observation_roles: tuple[str, ...]
    has_evidence_conflict: bool


def verify_retrieved_candidates(
    result: CatalogueRetrievalResult,
    observations: Iterable[GroundedVisualObservation],
) -> CandidateVerificationReport:
    """Verify candidates against grounded evidence from one or two unique sides."""

    if not isinstance(result, CatalogueRetrievalResult):
        raise TypeError("result must be CatalogueRetrievalResult.")
    sides = tuple(observations)
    envelope = build_numeral_evidence_envelope(sides)
    if envelope.has_conflict:
        return CandidateVerificationReport(
            rows=(),
            observation_roles=tuple(side.role for side in sides),
            has_evidence_conflict=True,
        )

    evidence = envelope.normalized
    rows = tuple(_verify(candidate, sides, evidence) for candidate in result.candidates)
    return CandidateVerificationReport(
        rows=rows,
        observation_roles=tuple(side.role for side in sides),
        has_evidence_conflict=False,
    )



def _verify(
    candidate: CatalogueCandidate,
    sides: tuple[GroundedVisualObservation, ...],
    evidence: NormalizedEvidence,
) -> CandidateVerification:
    matched: list[str] = []
    conflicts: list[str] = []

    candidate_year = normalize_year(candidate.year)
    candidate_denomination = normalize_denomination(candidate.denomination)
    candidate_country = normalize_country(candidate.country)

    if evidence.year is not None:
        if candidate_year == evidence.year:
            matched.append("year")
        else:
            conflicts.append("year")

    if evidence.denomination is not None:
        if candidate_denomination == evidence.denomination:
            matched.append("denomination")
        else:
            conflicts.append("denomination")

    legend_tokens = {
        token
        for legend in candidate.legends
        for token in _tokens(legend)
        if len(token) >= 2
    }
    excluded_text_tokens = set()
    if evidence.year is not None:
        excluded_text_tokens.update(_tokens(evidence.year))
    if evidence.denomination is not None:
        excluded_text_tokens.update(_tokens(evidence.denomination))

    supporting_roles: list[str] = []
    supporting_text: list[str] = []
    text_supported = False
    for side in sides:
        side_supported = False

        # Structured evidence retains its side provenance. A matching date or
        # denomination therefore counts as support from the side that supplied it.
        if side.date_like is not None and normalize_year(side.date_like) == candidate_year:
            side_supported = True
        if (
            side.denomination_mark is not None
            and normalize_denomination(side.denomination_mark) == candidate_denomination
        ):
            side_supported = True

        for text in side.visible_text:
            tokens = {
                token for token in _tokens(text)
                if len(token) >= 2 and token not in excluded_text_tokens
            }
            if not tokens:
                continue

            legend_match = bool(tokens & legend_tokens)
            country_match = (
                candidate_country is not None
                and normalize_country(text) == candidate_country
            )
            if legend_match or country_match:
                side_supported = True
                text_supported = True
                if text not in supporting_text:
                    supporting_text.append(text)

        if side_supported:
            supporting_roles.append(side.role)

    if text_supported:
        matched.append("visible_text")

    # Verification requires conflict-free structured agreement plus independent
    # textual catalogue support. supporting_roles records all sides that supplied
    # candidate-consistent evidence, not merely the sides with matching text.
    strong_match = "year" in matched or "denomination" in matched
    verified = not conflicts and strong_match and text_supported

    return CandidateVerification(
        candidate=candidate,
        matched_fields=tuple(matched),
        conflicting_fields=tuple(conflicts),
        supporting_roles=tuple(supporting_roles),
        supporting_text=tuple(supporting_text),
        verified=verified,
    )

def _tokens(value: object) -> tuple[str, ...]:
    return tuple(_TOKEN.findall(str(value).casefold()))
