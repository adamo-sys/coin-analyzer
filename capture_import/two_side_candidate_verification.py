"""Deterministic verification of retrieved catalogue candidates against coin-side evidence."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .catalogue_retrieval import CatalogueRetrievalResult
from .evidence_candidate_resolver import CatalogueCandidate, normalize_denomination, normalize_year
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


def _verify(candidate, sides, evidence):
    matched: list[str] = []
    conflicts: list[str] = []

    if evidence.year is not None:
        if normalize_year(candidate.year) == evidence.year:
            matched.append("year")
        else:
            conflicts.append("year")

    if evidence.denomination is not None:
        if normalize_denomination(candidate.denomination) == evidence.denomination:
            matched.append("denomination")
        else:
            conflicts.append("denomination")

    catalogue_tokens = set()
    for value in (candidate.country, candidate.denomination, candidate.year, *candidate.legends):
        catalogue_tokens.update(_tokens(value))

    supporting_roles: list[str] = []
    supporting_text: list[str] = []
    for side in sides:
        side_supported = False
        for text in side.visible_text:
            tokens = {token for token in _tokens(text) if len(token) >= 2}
            if tokens and tokens & catalogue_tokens:
                side_supported = True
                if text not in supporting_text:
                    supporting_text.append(text)
        if side_supported:
            supporting_roles.append(side.role)

    if supporting_text:
        matched.append("visible_text")

    # "verified" means conflict-free candidate/evidence agreement with at least
    # one strong structured match and grounded text support. It is deliberately
    # not an identity acceptance decision.
    strong_match = "year" in matched or "denomination" in matched
    verified = not conflicts and strong_match and bool(supporting_text)

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
