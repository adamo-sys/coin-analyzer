"""Deterministic batch evaluation for frozen desktop acceptance results."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ai_evaluation_contracts import (
    EvaluationAggregate,
    EvaluationCase,
    EvaluationCaseOutcome,
    aggregate_evaluation_outcomes,
)
from capture_import.desktop_acceptance_ai_evaluation_bridge import (
    evaluate_desktop_acceptance_result,
)
from capture_import.desktop_acceptance_scoring import DesktopAcceptanceResult


@dataclass(frozen=True, slots=True)
class DesktopAcceptanceAIEvaluationBatchReport:
    """Deterministic outcomes and their validated aggregate."""

    outcomes: tuple[EvaluationCaseOutcome, ...]
    aggregate: EvaluationAggregate

    def validate(self) -> None:
        if not isinstance(self.outcomes, tuple):
            raise TypeError("outcomes must be a tuple.")

        if not isinstance(self.aggregate, EvaluationAggregate):
            raise TypeError("aggregate must be an EvaluationAggregate.")

        expected = aggregate_evaluation_outcomes(self.outcomes)
        if self.aggregate != expected:
            raise ValueError(
                "aggregate must exactly match the supplied evaluation outcomes."
            )


def evaluate_desktop_acceptance_batch(
    cases: tuple[EvaluationCase, ...],
    results: tuple[DesktopAcceptanceResult, ...],
    *,
    candidate_ids_by_case: Mapping[str, str],
    evidence_refs_by_case: Mapping[str, tuple[str, ...]] | None = None,
) -> DesktopAcceptanceAIEvaluationBatchReport:
    """Evaluate one exact frozen result for every authoritative case."""

    if not isinstance(cases, tuple):
        raise TypeError("cases must be a tuple.")

    if not isinstance(results, tuple):
        raise TypeError("results must be a tuple.")

    if not isinstance(candidate_ids_by_case, Mapping):
        raise TypeError("candidate_ids_by_case must be a mapping.")

    if (
        evidence_refs_by_case is not None
        and not isinstance(evidence_refs_by_case, Mapping)
    ):
        raise TypeError("evidence_refs_by_case must be a mapping or None.")

    case_ids = tuple(case.case_id for case in cases)
    result_ids = tuple(result.case_id for result in results)

    if case_ids != tuple(sorted(case_ids)):
        raise ValueError("evaluation case IDs must be sorted.")

    if len(case_ids) != len(set(case_ids)):
        raise ValueError("evaluation case IDs must be unique.")

    if result_ids != tuple(sorted(result_ids)):
        raise ValueError("desktop acceptance result IDs must be sorted.")

    if len(result_ids) != len(set(result_ids)):
        raise ValueError("desktop acceptance result IDs must be unique.")

    if case_ids != result_ids:
        raise ValueError(
            "cases and desktop acceptance results must contain exactly "
            "the same ordered case IDs."
        )

    for case in cases:
        if not isinstance(case, EvaluationCase):
            raise TypeError("cases must contain EvaluationCase values.")
        case.validate()

    for result in results:
        if not isinstance(result, DesktopAcceptanceResult):
            raise TypeError(
                "results must contain DesktopAcceptanceResult values."
            )

    identify_case_ids = {
        result.case_id
        for result in results
        if result.observed_action == "identify"
    }

    supplied_candidate_ids = set(candidate_ids_by_case)

    if supplied_candidate_ids != identify_case_ids:
        missing = tuple(sorted(identify_case_ids - supplied_candidate_ids))
        extra = tuple(sorted(supplied_candidate_ids - identify_case_ids))
        raise ValueError(
            "candidate_ids_by_case must contain exactly the identify result "
            f"case IDs; missing={missing!r}, extra={extra!r}."
        )

    evidence_mapping = (
        {} if evidence_refs_by_case is None else evidence_refs_by_case
    )

    extra_evidence_ids = set(evidence_mapping) - set(case_ids)
    if extra_evidence_ids:
        raise ValueError(
            "evidence_refs_by_case contains unknown case IDs: "
            f"{tuple(sorted(extra_evidence_ids))!r}."
        )

    outcomes: list[EvaluationCaseOutcome] = []

    for case, result in zip(cases, results, strict=True):
        candidate_id = candidate_ids_by_case.get(case.case_id)
        evidence_refs = evidence_mapping.get(case.case_id, ())

        outcome = evaluate_desktop_acceptance_result(
            case,
            result,
            candidate_id=candidate_id,
            evidence_refs=evidence_refs,
        )
        outcomes.append(outcome)

    frozen_outcomes = tuple(outcomes)
    aggregate = aggregate_evaluation_outcomes(frozen_outcomes)

    report = DesktopAcceptanceAIEvaluationBatchReport(
        outcomes=frozen_outcomes,
        aggregate=aggregate,
    )
    report.validate()
    return report
