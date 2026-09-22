"""Benchmark-only contract for evaluating grounded Recognition30 decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .recognition_decision_gate import RecognitionDecision, RecognitionGateResult


@dataclass(frozen=True, slots=True)
class Recognition30CaseOutcome:
    case_id: str
    expected_candidate_id: str
    decision: RecognitionDecision
    predicted_candidate_id: str | None
    correct: bool
    abstain: bool
    unsafe_wrong_identification: bool
    reason: str


@dataclass(frozen=True, slots=True)
class Recognition30Metrics:
    total_cases: int
    identified_cases: int
    correct_cases: int
    abstained_cases: int
    unsafe_wrong_identifications: int
    full_identity_accuracy: float | None
    coverage: float | None
    selective_accuracy: float | None
    unsafe_wrong_identification_rate: float | None


def evaluate_case(
    *,
    case_id: str,
    expected_candidate_id: str,
    decision: RecognitionGateResult,
) -> Recognition30CaseOutcome:
    """Compare a final gate decision with benchmark truth only after inference."""

    _nonempty(case_id, "case_id")
    _nonempty(expected_candidate_id, "expected_candidate_id")
    if not isinstance(decision, RecognitionGateResult):
        raise TypeError("decision must be RecognitionGateResult.")

    identified = decision.decision is RecognitionDecision.IDENTIFY
    predicted = decision.candidate_id if identified else None
    correct = identified and predicted == expected_candidate_id
    unsafe = identified and not correct

    return Recognition30CaseOutcome(
        case_id=case_id,
        expected_candidate_id=expected_candidate_id,
        decision=decision.decision,
        predicted_candidate_id=predicted,
        correct=correct,
        abstain=not identified,
        unsafe_wrong_identification=unsafe,
        reason=decision.reason,
    )


def aggregate_metrics(
    outcomes: Iterable[Recognition30CaseOutcome],
) -> Recognition30Metrics:
    rows = tuple(outcomes)
    if any(not isinstance(row, Recognition30CaseOutcome) for row in rows):
        raise TypeError("outcomes must contain Recognition30CaseOutcome values.")

    case_ids = tuple(row.case_id for row in rows)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("case IDs must be unique.")

    total = len(rows)
    identified = sum(not row.abstain for row in rows)
    correct = sum(row.correct for row in rows)
    abstained = sum(row.abstain for row in rows)
    unsafe = sum(row.unsafe_wrong_identification for row in rows)

    return Recognition30Metrics(
        total_cases=total,
        identified_cases=identified,
        correct_cases=correct,
        abstained_cases=abstained,
        unsafe_wrong_identifications=unsafe,
        full_identity_accuracy=correct / total if total else None,
        coverage=identified / total if total else None,
        selective_accuracy=correct / identified if identified else None,
        unsafe_wrong_identification_rate=unsafe / total if total else None,
    )


def compare_to_baseline(
    metrics: Recognition30Metrics,
    *,
    baseline_correct: int = 1,
    baseline_total: int = 30,
) -> Mapping[str, float | int | None]:
    """Return descriptive deltas against the frozen identity baseline."""

    if not isinstance(metrics, Recognition30Metrics):
        raise TypeError("metrics must be Recognition30Metrics.")
    if (
        isinstance(baseline_correct, bool)
        or isinstance(baseline_total, bool)
        or not isinstance(baseline_correct, int)
        or not isinstance(baseline_total, int)
        or baseline_total <= 0
        or not 0 <= baseline_correct <= baseline_total
    ):
        raise ValueError("baseline counts are invalid.")

    baseline_accuracy = baseline_correct / baseline_total
    return {
        "baseline_correct": baseline_correct,
        "baseline_total": baseline_total,
        "baseline_accuracy": baseline_accuracy,
        "grounded_correct": metrics.correct_cases,
        "grounded_total": metrics.total_cases,
        "grounded_accuracy": metrics.full_identity_accuracy,
        "accuracy_delta": (
            metrics.full_identity_accuracy - baseline_accuracy
            if metrics.full_identity_accuracy is not None
            else None
        ),
        "coverage": metrics.coverage,
        "selective_accuracy": metrics.selective_accuracy,
        "unsafe_wrong_identification_rate": metrics.unsafe_wrong_identification_rate,
    }


def _nonempty(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
