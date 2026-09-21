"""Deterministic quality gate for grounded coin-side observations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable

from .grounded_visual_observation import GroundedVisualObservation


_DATE_LIKE_PATTERN = re.compile(r"^[0-9?]{3,6}$")
_DENOMINATION_MARK_PATTERN = re.compile(
    r"^(?=.*[0-9])(?=.*(?:[A-Za-z]|[./½¼¾]))[0-9A-Za-z./½¼¾ -]{1,16}$"
)


class EvidenceQualityDecision(str, Enum):
    """Routing-neutral result of deterministic evidence assessment."""

    CONTINUE = "CONTINUE"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True, slots=True)
class ObservationEvidenceQuality:
    """Auditable evidence features and a deterministic routing recommendation."""

    decision: EvidenceQualityDecision
    score: int
    reasons: tuple[str, ...]
    useful_text_count: int
    motif_count: int
    has_script: bool
    has_portrait: bool
    has_construction: bool
    has_shape: bool
    has_date_like: bool
    has_denomination_mark: bool

    @property
    def should_escalate(self) -> bool:
        return self.decision is EvidenceQualityDecision.ESCALATE


def assess_observation_evidence(
    observation: GroundedVisualObservation,
) -> ObservationEvidenceQuality:
    """Assess one observation without model confidence or identity inference.

    This is intentionally conservative and routing-neutral.  It measures only
    evidence already present in the grounded observation.  It never guesses
    missing evidence and never accepts a coin identity.
    """

    if not isinstance(observation, GroundedVisualObservation):
        raise TypeError("observation must be GroundedVisualObservation.")

    useful_text = tuple(
        item for item in observation.visible_text if _is_useful_visible_text(item)
    )
    has_date = _is_date_like(observation.date_like)
    has_denomination = _is_denomination_mark(observation.denomination_mark)

    score = 0
    score += min(len(useful_text), 3)
    score += 2 if has_date else 0
    score += 2 if has_denomination else 0
    score += 1 if observation.script is not None else 0
    score += 1 if observation.portrait is not None else 0
    score += 1 if observation.motifs else 0
    score += 1 if observation.construction is not None else 0
    score += 1 if observation.shape is not None else 0

    reasons: list[str] = []
    if not useful_text:
        reasons.append("no_useful_visible_text")
    if not has_date:
        reasons.append("no_valid_date_like")
    if not has_denomination:
        reasons.append("no_valid_denomination_mark")

    # A single strong discriminator can keep a case on the normal path.
    has_strong_discriminator = has_date or has_denomination
    # Otherwise require several independent weak clues rather than one vague
    # descriptive field.
    weak_signal_count = sum(
        (
            bool(useful_text),
            observation.script is not None,
            observation.portrait is not None,
            bool(observation.motifs),
            observation.construction is not None,
            observation.shape is not None,
        )
    )
    continue_normally = has_strong_discriminator or weak_signal_count >= 3
    if not continue_normally:
        reasons.append("insufficient_independent_evidence")

    return ObservationEvidenceQuality(
        decision=(
            EvidenceQualityDecision.CONTINUE
            if continue_normally
            else EvidenceQualityDecision.ESCALATE
        ),
        score=score,
        reasons=tuple(reasons),
        useful_text_count=len(useful_text),
        motif_count=len(observation.motifs),
        has_script=observation.script is not None,
        has_portrait=observation.portrait is not None,
        has_construction=observation.construction is not None,
        has_shape=observation.shape is not None,
        has_date_like=has_date,
        has_denomination_mark=has_denomination,
    )


def assess_coin_evidence(
    observations: Iterable[GroundedVisualObservation],
) -> ObservationEvidenceQuality:
    """Assess both available sides as one deterministic evidence envelope."""

    rows = tuple(observations)
    if not rows:
        raise ValueError("at least one observation is required.")
    if len(rows) > 2:
        raise ValueError("at most two coin-side observations are supported.")
    if any(not isinstance(row, GroundedVisualObservation) for row in rows):
        raise TypeError("all observations must be GroundedVisualObservation.")
    roles = [row.role for row in rows]
    if len(set(roles)) != len(roles):
        raise ValueError("coin-side observation roles must be unique.")

    useful_text = tuple(
        text
        for row in rows
        for text in row.visible_text
        if _is_useful_visible_text(text)
    )
    motifs = tuple(motif for row in rows for motif in row.motifs)
    has_date = any(_is_date_like(row.date_like) for row in rows)
    has_denomination = any(
        _is_denomination_mark(row.denomination_mark) for row in rows
    )
    has_script = any(row.script is not None for row in rows)
    has_portrait = any(row.portrait is not None for row in rows)
    has_construction = any(row.construction is not None for row in rows)
    has_shape = any(row.shape is not None for row in rows)

    score = min(len(set(useful_text)), 4)
    score += 2 if has_date else 0
    score += 2 if has_denomination else 0
    score += 1 if has_script else 0
    score += 1 if has_portrait else 0
    score += 1 if motifs else 0
    score += 1 if has_construction else 0
    score += 1 if has_shape else 0
    score += 1 if len(rows) == 2 and any(_has_substantive_evidence(row) for row in rows) else 0

    reasons: list[str] = []
    if not useful_text:
        reasons.append("no_useful_visible_text")
    if not has_date:
        reasons.append("no_valid_date_like")
    if not has_denomination:
        reasons.append("no_valid_denomination_mark")

    weak_signal_count = sum(
        (
            bool(useful_text),
            has_script,
            has_portrait,
            bool(motifs),
            has_construction,
            has_shape,
        )
    )
    continue_normally = has_date or has_denomination or weak_signal_count >= 3
    if not continue_normally:
        reasons.append("insufficient_independent_evidence")

    return ObservationEvidenceQuality(
        decision=(
            EvidenceQualityDecision.CONTINUE
            if continue_normally
            else EvidenceQualityDecision.ESCALATE
        ),
        score=score,
        reasons=tuple(reasons),
        useful_text_count=len(set(useful_text)),
        motif_count=len(motifs),
        has_script=has_script,
        has_portrait=has_portrait,
        has_construction=has_construction,
        has_shape=has_shape,
        has_date_like=has_date,
        has_denomination_mark=has_denomination,
    )


def _is_useful_visible_text(value: str) -> bool:
    compact = "".join(character for character in value if character.isalnum())
    return len(compact) >= 2


def _is_date_like(value: str | None) -> bool:
    if value is None:
        return False
    compact = value.replace(" ", "")
    return _DATE_LIKE_PATTERN.fullmatch(compact) is not None


def _is_denomination_mark(value: str | None) -> bool:
    if value is None:
        return False
    return _DENOMINATION_MARK_PATTERN.fullmatch(value.strip()) is not None


def _has_substantive_evidence(observation: GroundedVisualObservation) -> bool:
    return any(
        (
            any(_is_useful_visible_text(item) for item in observation.visible_text),
            observation.script is not None,
            observation.portrait is not None,
            bool(observation.motifs),
            observation.construction is not None,
            observation.shape is not None,
            _is_date_like(observation.date_like),
            _is_denomination_mark(observation.denomination_mark),
        )
    )
