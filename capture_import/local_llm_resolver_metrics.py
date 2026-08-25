"""Standalone scoring for the local LLM resolver experiment."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import math
import statistics

from .local_llm_resolver import ResolverResult


_REQUIRED_FIELDS = ("country", "denomination", "year")


def _normalized(value: object) -> str:
    return " ".join(str(value).strip().casefold().split())


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _nearest_rank_p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _field_match(actual: str | None, expected: object) -> bool:
    return actual is not None and _normalized(actual) == _normalized(expected)


def score_local_resolver_results(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Score resolver-only outcomes without mixing them into OCR baseline metrics.

    Expected row keys:
    - ``expected``: mapping containing country, denomination, year
    - ``identity_certain``: bool
    - ``result``: ResolverResult, or None when the resolver failed
    - ``latency_seconds``: numeric resolver-call latency when attempted
    - ``resolver_failure``: optional failure payload/string
    """

    data = list(rows)
    certain = [row for row in data if row.get("identity_certain") is True]
    successes = [row for row in data if isinstance(row.get("result"), ResolverResult)]
    failures = sum(row.get("resolver_failure") is not None for row in data)

    correct = {field: 0 for field in _REQUIRED_FIELDS}
    full_correct = 0
    false_positives = 0
    non_abstaining_certain = 0

    for row in certain:
        expected = row.get("expected")
        result = row.get("result")
        if not isinstance(expected, Mapping) or not isinstance(result, ResolverResult):
            continue
        if result.abstain:
            continue

        non_abstaining_certain += 1
        field_matches = {
            field: _field_match(getattr(result, field), expected.get(field))
            for field in _REQUIRED_FIELDS
        }
        for field, matched in field_matches.items():
            correct[field] += int(matched)
        is_full_correct = all(field_matches.values())
        full_correct += int(is_full_correct)
        false_positives += int(not is_full_correct)

    unresolved = sum(
        isinstance(row.get("result"), ResolverResult) and row["result"].abstain
        for row in data
    ) + failures

    latencies = [
        float(row["latency_seconds"])
        for row in data
        if isinstance(row.get("latency_seconds"), (int, float))
        and not isinstance(row.get("latency_seconds"), bool)
    ]

    certain_denominator = len(certain)
    return {
        "total_cases": len(data),
        "certain_scored_cases": certain_denominator,
        "resolver_successes": len(successes),
        "resolver_failures": failures,
        "country_accuracy": _rate(correct["country"], certain_denominator),
        "denomination_accuracy": _rate(correct["denomination"], certain_denominator),
        "year_accuracy": _rate(correct["year"], certain_denominator),
        "full_identity_accuracy": _rate(full_correct, certain_denominator),
        "unresolved_rate": _rate(unresolved, len(data)),
        "false_positive_rate": _rate(false_positives, non_abstaining_certain),
        "latency": {
            "mean_seconds": statistics.fmean(latencies) if latencies else None,
            "median_seconds": statistics.median(latencies) if latencies else None,
            "p95_seconds": _nearest_rank_p95(latencies),
        },
    }
