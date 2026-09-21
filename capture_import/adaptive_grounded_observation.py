"""Deterministic routing policy for optional secondary grounded observations."""

from __future__ import annotations

from dataclasses import dataclass

from .grounded_visual_observation import GroundedVisualObservation
from .numeral_evidence_envelope import build_numeral_evidence_envelope


@dataclass(frozen=True, slots=True)
class SecondaryObservationDecision:
    request_secondary: bool
    reason: str
    missing_evidence: tuple[str, ...] = ()


def decide_secondary_observation(
    observation: GroundedVisualObservation,
) -> SecondaryObservationDecision:
    """Request another view only when it can target a deterministic evidence gap.

    The decision is deliberately independent of candidate identity, retrieval
    ranking, model confidence, and benchmark truth. missing_evidence makes the
    intended purpose of a secondary observation explicit and auditable.
    """

    envelope = build_numeral_evidence_envelope((observation,))
    missing = _missing_evidence(observation, envelope)

    if envelope.has_conflict:
        return SecondaryObservationDecision(True, "primary_evidence_conflict", missing)
    if "visible_text" in missing:
        return SecondaryObservationDecision(True, "primary_no_visible_text", missing)
    if {"year", "denomination"} <= set(missing):
        return SecondaryObservationDecision(True, "primary_literal_text_only", missing)
    return SecondaryObservationDecision(
        False,
        "primary_structured_evidence_sufficient",
        missing,
    )


def _missing_evidence(observation, envelope) -> tuple[str, ...]:
    missing = []
    if not observation.visible_text:
        missing.append("visible_text")
    if envelope.normalized.year is None:
        missing.append("year")
    if envelope.normalized.denomination is None:
        missing.append("denomination")
    return tuple(missing)
