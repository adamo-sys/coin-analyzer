"""Deterministic quality metrics for already-collected grounded view reports."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping

from .denomination_mark_extraction import extract_denomination_marks
from .date_numeral_extraction import extract_date_numerals
from .grounded_visual_observation import GroundedVisualObservation


@dataclass(frozen=True, slots=True)
class ViewQuality:
    view: str
    observations: int
    observations_with_text: int
    unique_text_items: int
    date_yield: int
    denomination_yield: int
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class ObservationExecutionAccounting:
    cases: int
    successful_calls: int
    failed_calls: int
    attempted_calls: int
    maximum_two_view_calls: int
    avoided_calls: int
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class SecondaryViewPolicyEvaluation:
    paired_roles: int
    secondary_requested: int
    secondary_avoided: int
    useful_secondary: int
    useful_secondary_rate: float | None
    secondary_input_tokens: int
    useful_secondary_input_tokens: int


@dataclass(frozen=True, slots=True)
class ViewPairQuality:
    role: str
    primary_view: str
    comparison_view: str
    primary_text: tuple[str, ...]
    comparison_text: tuple[str, ...]
    incremental_comparison_text: tuple[str, ...]
    shared_text: tuple[str, ...]
    primary_date: str | None
    comparison_date: str | None
    date_agreement: bool | None
    primary_denomination: str | None
    comparison_denomination: str | None
    denomination_agreement: bool | None
    primary_input_tokens: int
    comparison_input_tokens: int


def evaluate_view_quality(
    provenance: Iterable[Mapping[str, object]],
) -> tuple[ViewQuality, ...]:
    buckets: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in provenance:
        buckets[str(row["view"])].append(row)

    results = []
    for view in sorted(buckets):
        rows = buckets[view]
        unique_text = {
            text.casefold()
            for row in rows
            for text in _text(row)
        }
        results.append(
            ViewQuality(
                view=view,
                observations=len(rows),
                observations_with_text=sum(bool(_text(row)) for row in rows),
                unique_text_items=len(unique_text),
                date_yield=sum(_date(row) is not None for row in rows),
                denomination_yield=sum(
                    _denomination(row) is not None for row in rows
                ),
                input_tokens=sum(int(row.get("input_tokens") or 0) for row in rows),
                output_tokens=sum(int(row.get("output_tokens") or 0) for row in rows),
            )
        )
    return tuple(results)


def compare_view_pairs(
    provenance: Iterable[Mapping[str, object]],
    *,
    primary_view: str = "full_face",
    comparison_view: str = "rim",
) -> tuple[ViewPairQuality, ...]:
    by_role_view: dict[tuple[str, str], Mapping[str, object]] = {}
    for row in provenance:
        by_role_view[(str(row["role"]), str(row["view"]))] = row

    pairs = []
    roles = sorted({role for role, _ in by_role_view})
    for role in roles:
        primary = by_role_view.get((role, primary_view))
        comparison = by_role_view.get((role, comparison_view))
        if primary is None or comparison is None:
            continue
        p_text = _text(primary)
        c_text = _text(comparison)
        p_keys = {value.casefold() for value in p_text}
        c_keys = {value.casefold() for value in c_text}
        pairs.append(
            ViewPairQuality(
                role=role,
                primary_view=primary_view,
                comparison_view=comparison_view,
                primary_text=p_text,
                comparison_text=c_text,
                incremental_comparison_text=tuple(
                    value for value in c_text if value.casefold() not in p_keys
                ),
                shared_text=tuple(
                    value for value in c_text if value.casefold() in p_keys
                ),
                primary_date=_date(primary),
                comparison_date=_date(comparison),
                date_agreement=_agreement(_date(primary), _date(comparison)),
                primary_denomination=_denomination(primary),
                comparison_denomination=_denomination(comparison),
                denomination_agreement=_agreement(
                    _denomination(primary), _denomination(comparison)
                ),
                primary_input_tokens=int(primary.get("input_tokens") or 0),
                comparison_input_tokens=int(comparison.get("input_tokens") or 0),
            )
        )
    return tuple(pairs)


def _observation(row: Mapping[str, object]) -> GroundedVisualObservation:
    return GroundedVisualObservation(
        role=str(row["role"]),
        visible_text=tuple(str(value) for value in row.get("visible_text") or ()),
        date_like=(
            str(row["date_like"]) if row.get("date_like") is not None else None
        ),
        denomination_mark=(
            str(row["denomination_mark"])
            if row.get("denomination_mark") is not None
            else None
        ),
    )


def _text(row: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(str(value) for value in row.get("visible_text") or ())


def _date(row: Mapping[str, object]) -> str | None:
    return extract_date_numerals((_observation(row),)).resolved_value


def _denomination(row: Mapping[str, object]) -> str | None:
    return extract_denomination_marks((_observation(row),)).resolved_value


def _agreement(left: str | None, right: str | None) -> bool | None:
    if left is None or right is None:
        return None
    return left.casefold() == right.casefold()


def evaluate_execution_accounting(
    rows: Iterable[Mapping[str, object]],
) -> ObservationExecutionAccounting:
    """Account for provider work from persisted benchmark evidence only.

    The Recognition30 multiview contract permits at most two views for each of
    two physical sides, so four calls per case is the deterministic ceiling.
    Successful calls come from view provenance; failed calls come from the
    explicit provider-failure ledger. No provider calls are made here.
    """

    materialized = tuple(rows)
    provenance = tuple(
        item
        for row in materialized
        for item in row.get("view_provenance", ())
        if isinstance(item, Mapping)
    )
    failures = tuple(
        item
        for row in materialized
        for item in row.get("provider_failures", ())
        if isinstance(item, Mapping)
    )
    successful = len(provenance)
    failed = len(failures)
    attempted = successful + failed
    maximum = len(materialized) * 4
    return ObservationExecutionAccounting(
        cases=len(materialized),
        successful_calls=successful,
        failed_calls=failed,
        attempted_calls=attempted,
        maximum_two_view_calls=maximum,
        avoided_calls=max(0, maximum - attempted),
        input_tokens=sum(int(item.get("input_tokens") or 0) for item in provenance),
        output_tokens=sum(int(item.get("output_tokens") or 0) for item in provenance),
    )


def evaluate_secondary_view_policy(
    provenance: Iterable[Mapping[str, object]],
    *,
    primary_view: str = "full_face",
    secondary_view: str = "rim",
) -> SecondaryViewPolicyEvaluation:
    """Replay the current adaptive policy over already-collected paired views.

    This is counterfactual/offline: the primary determines whether the policy
    would request the secondary, while the persisted secondary is used only to
    measure whether that request added literal/numeral evidence.
    """

    from .adaptive_grounded_observation import decide_secondary_observation

    pairs = compare_view_pairs(
        provenance, primary_view=primary_view, comparison_view=secondary_view
    )
    requested = 0
    useful = 0
    secondary_tokens = 0
    useful_tokens = 0
    for pair in pairs:
        primary = GroundedVisualObservation(
            role=pair.role,
            visible_text=pair.primary_text,
            date_like=pair.primary_date,
            denomination_mark=pair.primary_denomination,
        )
        if not decide_secondary_observation(primary).request_secondary:
            continue
        requested += 1
        secondary_tokens += pair.comparison_input_tokens
        added = bool(pair.incremental_comparison_text)
        added = added or (
            pair.primary_date is None and pair.comparison_date is not None
        )
        added = added or (
            pair.primary_denomination is None
            and pair.comparison_denomination is not None
        )
        if added:
            useful += 1
            useful_tokens += pair.comparison_input_tokens

    return SecondaryViewPolicyEvaluation(
        paired_roles=len(pairs),
        secondary_requested=requested,
        secondary_avoided=len(pairs) - requested,
        useful_secondary=useful,
        useful_secondary_rate=(useful / requested if requested else None),
        secondary_input_tokens=secondary_tokens,
        useful_secondary_input_tokens=useful_tokens,
    )
