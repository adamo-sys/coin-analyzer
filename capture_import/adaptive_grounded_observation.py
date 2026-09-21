"""Deterministic routing policy for optional secondary grounded observations."""

from __future__ import annotations

from dataclasses import dataclass

from .grounded_visual_observation import GroundedVisualObservation
from .numeral_evidence_envelope import build_numeral_evidence_envelope


@dataclass(frozen=True, slots=True)
class SecondaryObservationDecision:
    request_secondary: bool
    reason: str


def decide_secondary_observation(
    observation: GroundedVisualObservation,
) -> SecondaryObservationDecision:
    """Request another view only when the primary observation is evidence-starved.

    This policy is deliberately independent of candidate identity, retrieval
    ranking, model confidence, and benchmark truth.
    """

    envelope = build_numeral_evidence_envelope((observation,))
    if envelope.has_conflict:
        return SecondaryObservationDecision(True, "primary_evidence_conflict")
    if not observation.visible_text:
        return SecondaryObservationDecision(True, "primary_no_visible_text")
    if (
        envelope.normalized.year is None
        and envelope.normalized.denomination is None
    ):
        return SecondaryObservationDecision(True, "primary_literal_text_only")
    return SecondaryObservationDecision(False, "primary_structured_evidence_sufficient")
