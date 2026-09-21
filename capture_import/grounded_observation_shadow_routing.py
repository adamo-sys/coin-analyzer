"""Shadow-only routing projection for grounded observation evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .grounded_observation_quality import (
    EvidenceQualityDecision,
    ObservationEvidenceQuality,
    assess_coin_evidence,
)
from .grounded_visual_observation import GroundedVisualObservationReport


class ShadowRoute(str, Enum):
    """Route a future active router could take; never executed here."""

    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"


@dataclass(frozen=True, slots=True)
class ShadowRoutingProjection:
    """Auditable projection with provider and token provenance."""

    route: ShadowRoute
    quality: ObservationEvidenceQuality
    source_provider_ids: tuple[str, ...]
    source_model_ids: tuple[str, ...]
    input_tokens: int | None
    output_tokens: int | None

    @property
    def would_escalate(self) -> bool:
        return self.route is ShadowRoute.PREMIUM

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": "shadow",
            "route": self.route.value,
            "would_escalate": self.would_escalate,
            "quality_decision": self.quality.decision.value,
            "quality_score": self.quality.score,
            "quality_reasons": list(self.quality.reasons),
            "source_provider_ids": list(self.source_provider_ids),
            "source_model_ids": list(self.source_model_ids),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


def project_shadow_route(
    reports: Iterable[GroundedVisualObservationReport],
) -> ShadowRoutingProjection:
    """Project standard vs premium routing without invoking another provider."""

    rows = tuple(reports)
    if not rows:
        raise ValueError("at least one observation report is required.")
    if len(rows) > 2:
        raise ValueError("at most two observation reports are supported.")
    if any(not isinstance(row, GroundedVisualObservationReport) for row in rows):
        raise TypeError("all reports must be GroundedVisualObservationReport.")

    quality = assess_coin_evidence(row.observation for row in rows)
    route = (
        ShadowRoute.PREMIUM
        if quality.decision is EvidenceQualityDecision.ESCALATE
        else ShadowRoute.STANDARD
    )

    return ShadowRoutingProjection(
        route=route,
        quality=quality,
        source_provider_ids=_ordered_unique(row.provider_id for row in rows),
        source_model_ids=_ordered_unique(row.model_id for row in rows),
        input_tokens=_sum_optional(row.input_tokens for row in rows),
        output_tokens=_sum_optional(row.output_tokens for row in rows),
    )


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return tuple(result)


def _sum_optional(values: Iterable[int | None]) -> int | None:
    rows = tuple(values)
    if any(value is None for value in rows):
        return None
    return sum(value for value in rows if value is not None)
