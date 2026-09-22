"""Deterministic extraction of denomination-like marks from grounded observations."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .grounded_visual_observation import GroundedVisualObservation


_MAX_CANDIDATES = 8
_SPACE = re.compile(r"\s+")
_ALLOWED = re.compile(r"^[0-9A-Za-z./½¼¾$¢€£¥₹₱₽₩₫₦₵₡₲₴₸₺₼₾₿ -]{1,32}$")
_NUMBER = re.compile(r"\d+(?:[./]\d+)?|[½¼¾]")
_CURRENCY_SYMBOLS = frozenset("$¢€£¥₹₱₽₩₫₦₵₡₲₴₸₺₼₾₿")
_UNIT_TOKEN = re.compile(
    r"(?<![A-Za-z])(?:cent(?:s)?|dollar(?:s)?|fr\.?|franc(?:s)?|"
    r"piso|peso(?:s)?|rp|rupiah|rupee(?:s)?)(?![A-Za-z])",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DenominationMarkEvidence:
    """One literal denomination-like mark with side and field provenance."""

    value: str
    role: str
    source_field: str


@dataclass(frozen=True, slots=True)
class DenominationMarkExtraction:
    """Conservative denomination-mark envelope; never a denomination identity."""

    candidates: tuple[DenominationMarkEvidence, ...]
    resolved_value: str | None
    conflict: bool
    unresolved: bool


def extract_denomination_marks(
    observations: Iterable[GroundedVisualObservation],
) -> DenominationMarkExtraction:
    """Extract explicit numeric/unit marks without currency normalization."""

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

    candidates: list[DenominationMarkEvidence] = []
    seen: set[tuple[str, str, str]] = set()
    for observation in rows:
        visible_marks = tuple(
            value
            for text in observation.visible_text
            if (value := _explicit_mark(text)) is not None
        )
        structured_mark = (
            _explicit_mark(observation.denomination_mark)
            if observation.denomination_mark is not None
            else None
        )
        retain_structured = (
            structured_mark is not None
            and (
                not visible_marks
                or any(
                    _comparison_key(structured_mark) == _comparison_key(visible)
                    for visible in visible_marks
                )
            )
        )
        if retain_structured:
            _append_if_mark(
                candidates,
                seen,
                observation.denomination_mark or "",
                role=observation.role,
                source_field="denomination_mark",
            )
        for text in observation.visible_text:
            _append_if_mark(
                candidates,
                seen,
                text,
                role=observation.role,
                source_field="visible_text",
                skip_keys=(
                    frozenset({_comparison_key(structured_mark)})
                    if retain_structured and structured_mark is not None
                    else frozenset()
                ),
            )

    values = {_comparison_key(item.value) for item in candidates}
    conflict = len(values) > 1
    resolved_value = candidates[0].value if len(values) == 1 and candidates else None
    return DenominationMarkExtraction(
        candidates=tuple(candidates),
        resolved_value=resolved_value,
        conflict=conflict,
        unresolved=resolved_value is None,
    )


def _append_if_mark(
    candidates: list[DenominationMarkEvidence],
    seen: set[tuple[str, str, str]],
    text: str,
    *,
    role: str,
    source_field: str,
    skip_keys: frozenset[str] = frozenset(),
) -> None:
    value = _explicit_mark(text)
    if value is None:
        return
    key = (_comparison_key(value), role, source_field)
    if key[0] in skip_keys or key in seen or len(candidates) >= _MAX_CANDIDATES:
        return
    seen.add(key)
    candidates.append(
        DenominationMarkEvidence(
            value=value,
            role=role,
            source_field=source_field,
        )
    )


def _is_explicit_mark(value: str) -> bool:
    if not value or _ALLOWED.fullmatch(value) is None:
        return False
    # Bare numerals such as "25" are ambiguous: they may be dates, mint marks,
    # catalogue annotations, or denomination numerals. Require a numeric
    # component plus either a supported currency symbol or a recognized unit
    # token; an arbitrary Latin letter is not denomination evidence.
    return _NUMBER.search(value) is not None and (
        bool(_CURRENCY_SYMBOLS.intersection(value))
        or _UNIT_TOKEN.search(value) is not None
    )


def _explicit_mark(text: str) -> str | None:
    value = _SPACE.sub(" ", text.strip())
    return value if _is_explicit_mark(value) else None


def _comparison_key(value: str) -> str:
    # Comparison only: preserve the first literal spelling in resolved_value.
    return _SPACE.sub(" ", value.strip()).casefold()
