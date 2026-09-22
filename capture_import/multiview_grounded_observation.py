"""Deterministic union of grounded observations from multiple image views."""

from __future__ import annotations

from dataclasses import dataclass

from .grounded_visual_observation import (
    GroundedVisualObservation,
    GroundedVisualObservationContractError,
    GroundedVisualObservationReport,
)


@dataclass(frozen=True, slots=True)
class GroundedObservationViewReport:
    """One provider report with deterministic image-view provenance."""

    view: str
    report: GroundedVisualObservationReport

    def __post_init__(self) -> None:
        if self.view not in {"source", "full_face", "rim"}:
            raise GroundedVisualObservationContractError(
                "view must be source, full_face, or rim."
            )


def union_grounded_observation_views(
    view_reports: tuple[GroundedObservationViewReport, ...],
) -> GroundedVisualObservation:
    """Union literal evidence; conflicting specialized readings are discarded."""

    if not view_reports:
        raise GroundedVisualObservationContractError(
            "at least one grounded observation view is required."
        )
    roles = {item.report.observation.role for item in view_reports}
    if len(roles) != 1:
        raise GroundedVisualObservationContractError(
            "all grounded observation views must describe the same side."
        )
    observations = tuple(item.report.observation for item in view_reports)
    return GroundedVisualObservation(
        role=next(iter(roles)),
        visible_text=_ordered_union(o.visible_text for o in observations),
        script=_consensus_optional(o.script for o in observations),
        portrait=_consensus_optional(o.portrait for o in observations),
        motifs=_ordered_union(o.motifs for o in observations),
        construction=_consensus_optional(o.construction for o in observations),
        shape=_consensus_optional(o.shape for o in observations),
        date_like=_consensus_optional(o.date_like for o in observations),
        denomination_mark=_consensus_optional(
            o.denomination_mark for o in observations
        ),
    )


def view_provenance(
    view_reports: tuple[GroundedObservationViewReport, ...],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "view": item.view,
            "role": item.report.observation.role,
            "visible_text": list(item.report.observation.visible_text),
            "date_like": item.report.observation.date_like,
            "denomination_mark": item.report.observation.denomination_mark,
            "response_id": item.report.response_id,
            "input_tokens": item.report.input_tokens,
            "output_tokens": item.report.output_tokens,
        }
        for item in view_reports
    )


def _ordered_union(groups) -> tuple[str, ...]:
    result = []
    seen = set()
    for group in groups:
        for value in group:
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                result.append(value)
    return tuple(result[:8])


def _consensus_optional(values) -> str | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    first = present[0]
    if all(value.casefold() == first.casefold() for value in present[1:]):
        return first
    return None
