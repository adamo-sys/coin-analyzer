"""Deterministic extraction of date-like numeral evidence from grounded observations."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .grounded_visual_observation import GroundedVisualObservation


_DATE_TOKEN = re.compile(r"(?<![0-9A-Za-z])([0-9?]{4})(?![0-9A-Za-z])")
_MAX_CANDIDATES = 8


@dataclass(frozen=True, slots=True)
class DateNumeralEvidence:
    """One directly observed date-like token with explicit provenance."""

    value: str
    role: str
    source_field: str
    uncertain: bool


@dataclass(frozen=True, slots=True)
class DateNumeralExtraction:
    """Deterministic date-like evidence envelope; never an inferred coin year."""

    candidates: tuple[DateNumeralEvidence, ...]
    resolved_value: str | None
    conflict: bool
    unresolved: bool


def extract_date_numerals(
    observations: Iterable[GroundedVisualObservation],
) -> DateNumeralExtraction:
    """Extract literal four-character date-like tokens without repairing them."""

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

    candidates: list[DateNumeralEvidence] = []
    seen: set[tuple[str, str, str]] = set()
    for observation in rows:
        visible_tokens = tuple(
            token
            for text in observation.visible_text
            for token in _date_tokens(text)
        )
        structured_tokens = (
            _date_tokens(observation.date_like)
            if observation.date_like is not None
            else ()
        )
        retained_structured = tuple(
            token
            for token in structured_tokens
            if not visible_tokens
            or any(_compatible(token, visible) for visible in visible_tokens)
        )
        if retained_structured:
            _append_tokens(
                candidates,
                seen,
                observation.date_like or "",
                role=observation.role,
                source_field="date_like",
            )
        for text in observation.visible_text:
            _append_tokens(
                candidates,
                seen,
                text,
                role=observation.role,
                source_field="visible_text",
                skip_values=frozenset(retained_structured),
            )

    exact_values = {item.value for item in candidates if not item.uncertain}
    uncertain_values = {item.value for item in candidates if item.uncertain}
    conflict = len(exact_values) > 1
    resolved_value = next(iter(exact_values)) if len(exact_values) == 1 else None

    # An uncertain token cannot resolve a year. If it disagrees structurally with
    # an exact token, preserve it as evidence but do not manufacture a conflict:
    # only two incompatible exact readings constitute a deterministic conflict.
    unresolved = resolved_value is None
    if not exact_values and len(uncertain_values) > 1:
        unresolved = True

    return DateNumeralExtraction(
        candidates=tuple(candidates),
        resolved_value=resolved_value,
        conflict=conflict,
        unresolved=unresolved,
    )


def _append_tokens(
    candidates: list[DateNumeralEvidence],
    seen: set[tuple[str, str, str]],
    text: str,
    *,
    role: str,
    source_field: str,
    skip_values: frozenset[str] = frozenset(),
) -> None:
    for value in _date_tokens(text):
        if value in skip_values:
            continue
        key = (value, role, source_field)
        if key in seen:
            continue
        if len(candidates) >= _MAX_CANDIDATES:
            return
        seen.add(key)
        candidates.append(
            DateNumeralEvidence(
                value=value,
                role=role,
                source_field=source_field,
                uncertain="?" in value,
            )
        )


def _date_tokens(text: str) -> tuple[str, ...]:
    return tuple(match.group(1) for match in _DATE_TOKEN.finditer(text))


def _compatible(left: str, right: str) -> bool:
    return all(
        left_digit == right_digit or "?" in (left_digit, right_digit)
        for left_digit, right_digit in zip(left, right)
    )
