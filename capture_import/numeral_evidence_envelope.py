"""Compose RQ-02 numeral extractors into a provider-neutral evidence envelope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .date_numeral_extraction import DateNumeralExtraction, extract_date_numerals
from .denomination_mark_extraction import (
    DenominationMarkExtraction,
    extract_denomination_marks,
)
from .evidence_candidate_resolver import (
    NormalizedEvidence,
    normalize_denomination,
    normalize_observed_country_alias,
)
from .grounded_visual_observation import GroundedVisualObservation


@dataclass(frozen=True, slots=True)
class NumeralEvidenceEnvelope:
    """Date and denomination evidence ready for later catalogue retrieval."""

    date: DateNumeralExtraction
    denomination: DenominationMarkExtraction
    normalized: NormalizedEvidence
    has_conflict: bool
    retrieval_ready: bool


def build_numeral_evidence_envelope(
    observations: Iterable[GroundedVisualObservation],
) -> NumeralEvidenceEnvelope:
    """Compose literal extractors without inventing country or coin identity."""

    rows = tuple(observations)
    date = extract_date_numerals(rows)
    denomination = extract_denomination_marks(rows)
    has_conflict = date.conflict or denomination.conflict

    normalized_denomination = (
        normalize_denomination(denomination.resolved_value)
        if denomination.resolved_value is not None
        else None
    )
    raw_visible_text = tuple(
        dict.fromkeys(text for row in rows for text in row.visible_text)
    )
    country_aliases = tuple(
        dict.fromkeys(
            alias
            for text in raw_visible_text
            if (alias := normalize_observed_country_alias(text)) is not None
        )
    )
    visible_text = raw_visible_text + tuple(
        alias for alias in country_aliases if alias not in raw_visible_text
    )
    normalized = NormalizedEvidence(
        country=country_aliases[0] if len(country_aliases) == 1 else None,
        denomination=normalized_denomination,
        year=date.resolved_value,
        visible_text=visible_text,
        source="grounded_numeral_extraction",
    )

    # This only means there is conflict-free structured evidence worth handing
    # to a future catalogue retriever. It is not an identity acceptance signal.
    retrieval_ready = (
        not has_conflict
        and (
            normalized.year is not None
            or normalized.denomination is not None
            or bool(normalized.visible_text)
        )
    )
    return NumeralEvidenceEnvelope(
        date=date,
        denomination=denomination,
        normalized=normalized,
        has_conflict=has_conflict,
        retrieval_ready=retrieval_ready,
    )
