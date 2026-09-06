"""Desktop acceptance evaluation bridge with explicit missing-result reasons."""

from __future__ import annotations

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationCase,
    EvaluationCaseOutcome,
    EvaluationOutcomeClassification,
)
from ai_evaluation_evaluator import evaluate_observed_result
from capture_import.desktop_acceptance_ai_evaluation_adapter import (
    adapt_desktop_acceptance_result,
)
from capture_import.desktop_acceptance_scoring import DesktopAcceptanceResult


def evaluate_desktop_acceptance_result(
    case: EvaluationCase,
    result: DesktopAcceptanceResult,
    *,
    candidate_id: str | None = None,
    evidence_refs: tuple[str, ...] = (),
) -> EvaluationCaseOutcome:
    """Evaluate one frozen desktop acceptance result with preserved failure reason."""

    if not isinstance(case, EvaluationCase):
        raise TypeError("case must be an EvaluationCase.")

    case.validate()

    if not isinstance(result, DesktopAcceptanceResult):
        raise TypeError("result must be a DesktopAcceptanceResult.")

    if result.case_id != case.case_id:
        raise ValueError(
            "Desktop acceptance result case_id does not match "
            "the authoritative evaluation case."
        )

    if result.observed_action == "unavailable":
        if candidate_id is not None:
            raise ValueError(
                "candidate_id must not be supplied for unavailable results."
            )

        outcome = EvaluationCaseOutcome(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=case.case_id,
            classification=(
                EvaluationOutcomeClassification.INVALID_OR_MISSING
            ),
            evidence_refs=evidence_refs,
            reason_codes=("provider_unavailable",),
        )
        outcome.validate()
        return outcome

    if result.observed_action == "infrastructure_failure":
        if candidate_id is not None:
            raise ValueError(
                "candidate_id must not be supplied for infrastructure failures."
            )

        outcome = EvaluationCaseOutcome(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=case.case_id,
            classification=(
                EvaluationOutcomeClassification.INVALID_OR_MISSING
            ),
            evidence_refs=evidence_refs,
            reason_codes=("infrastructure_failure",),
        )
        outcome.validate()
        return outcome

    observed = adapt_desktop_acceptance_result(
        result,
        candidate_id=candidate_id,
        evidence_refs=evidence_refs,
    )
    return evaluate_observed_result(case, observed)
