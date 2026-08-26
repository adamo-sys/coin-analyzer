"""Deterministic evidence normalization and candidate-resolution scaffold.

This module is intentionally model-agnostic. It accepts raw evidence extracted
from OCR/VLM providers, normalizes common country/denomination/year forms, and
scores externally supplied catalogue candidates. It does not perform catalogue
I/O, model inference, UI mutation, or persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping, Sequence


COUNTRY_ALIASES = {
    "united states of america": "United States",
    "usa": "United States",
    "u s a": "United States",
    "helvetia": "Switzerland",
    "republique francaise": "France",
    "republic of the philippines": "Philippines",
    "pilipinas": "Philippines",
}

DENOMINATION_ALIASES = {
    "one rupee": "1 rupee",
    "1 rupees": "1 rupee",
    "two rupees": "2 rupees",
    "2 rupee": "2 rupees",
    "rp 100": "100 rupiah",
    "100 rp": "100 rupiah",
    "10 piso": "10 pesos",
    "half dollar": "50 cents",
    "half-dollar": "50 cents",
    "5 cents": "5 cents",
    "10 cents": "10 cents",
    "25 cents": "25 cents",
    "2 francs": "2 francs",
}


@dataclass(frozen=True, slots=True)
class NormalizedEvidence:
    country: str | None
    denomination: str | None
    year: str | None
    visible_text: tuple[str, ...] = ()
    source: str | None = None


@dataclass(frozen=True, slots=True)
class CatalogueCandidate:
    candidate_id: str
    country: str
    denomination: str
    year: str
    type_design: str | None = None
    legends: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateScore:
    candidate: CatalogueCandidate
    score: float
    matched_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    supporting_text: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateResolution:
    accepted: CatalogueCandidate | None
    ranked: tuple[CandidateScore, ...]
    abstain: bool
    reason: str


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def _key(value: object) -> str:
    text = _clean(value) or ""
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def normalize_country(value: object) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    key = _key(text)
    return COUNTRY_ALIASES.get(key, text)


def normalize_denomination(value: object) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    key = _key(text)
    if key in DENOMINATION_ALIASES:
        return DENOMINATION_ALIASES[key]
    # Normalize simple plural/unit variants without inventing a denomination.
    key = re.sub(r"\bfrancs\b", "franc", key)
    key = re.sub(r"\brupees\b", "rupee", key)
    key = re.sub(r"\bpesos\b", "peso", key)
    return key


def normalize_year(value: object) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    match = re.fullmatch(r"\d{4}", text)
    return match.group(0) if match else None


def normalize_evidence(raw: Mapping[str, object], *, source: str | None = None) -> NormalizedEvidence:
    visible = raw.get("visible_text")
    visible_text: list[str] = []
    if isinstance(visible, Sequence) and not isinstance(visible, (str, bytes)):
        for item in visible:
            text = _clean(item)
            if text and text not in visible_text:
                visible_text.append(text)
    return NormalizedEvidence(
        country=normalize_country(raw.get("country")),
        denomination=normalize_denomination(raw.get("denomination")),
        year=normalize_year(raw.get("year")),
        visible_text=tuple(visible_text),
        source=source,
    )


def _candidate_field_value(candidate: CatalogueCandidate, field: str) -> str | None:
    if field == "country":
        return normalize_country(candidate.country)
    if field == "denomination":
        return normalize_denomination(candidate.denomination)
    if field == "year":
        return normalize_year(candidate.year)
    raise ValueError(f"unsupported field: {field}")


def score_candidate(candidate: CatalogueCandidate, evidence: Iterable[NormalizedEvidence]) -> CandidateScore:
    matched: set[str] = set()
    mismatched: set[str] = set()
    supporting_text: list[str] = []
    field_weights = {"country": 3.0, "denomination": 3.0, "year": 4.0}
    score = 0.0

    evidence_rows = tuple(evidence)
    for field, weight in field_weights.items():
        expected = _candidate_field_value(candidate, field)
        observed = [getattr(row, field) for row in evidence_rows if getattr(row, field) is not None]
        if not observed:
            continue
        if expected in observed:
            score += weight
            matched.add(field)
        else:
            score -= weight
            mismatched.add(field)

    searchable_legends = tuple(_key(value) for value in candidate.legends if _key(value))
    for row in evidence_rows:
        for text in row.visible_text:
            tokenized = _key(text)
            if not tokenized:
                continue
            if any(tokenized in legend or legend in tokenized for legend in searchable_legends):
                score += 0.5
                if text not in supporting_text:
                    supporting_text.append(text)

    return CandidateScore(
        candidate=candidate,
        score=score,
        matched_fields=tuple(sorted(matched)),
        mismatched_fields=tuple(sorted(mismatched)),
        supporting_text=tuple(supporting_text),
    )


def resolve_candidates(
    candidates: Iterable[CatalogueCandidate],
    evidence: Iterable[NormalizedEvidence],
    *,
    minimum_score: float = 7.0,
    minimum_margin: float = 2.0,
) -> CandidateResolution:
    evidence_rows = tuple(evidence)
    ranked = tuple(
        sorted(
            (score_candidate(candidate, evidence_rows) for candidate in candidates),
            key=lambda item: (-item.score, item.candidate.candidate_id),
        )
    )
    if not ranked:
        return CandidateResolution(None, (), True, "no catalogue candidates")

    best = ranked[0]
    if best.score < minimum_score:
        return CandidateResolution(None, ranked, True, "best candidate below minimum score")
    if best.mismatched_fields:
        return CandidateResolution(None, ranked, True, "best candidate conflicts with observed identity evidence")
    if len(ranked) > 1 and best.score - ranked[1].score < minimum_margin:
        return CandidateResolution(None, ranked, True, "top candidates are not sufficiently separated")

    return CandidateResolution(best.candidate, ranked, False, "candidate accepted by deterministic evidence score")
