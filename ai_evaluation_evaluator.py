"""Deterministic evaluator for bounded AI evaluation contracts."""

from __future__ import annotations

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationCase,
    EvaluationCaseOutcome,
    EvaluationOutcomeClassification,
    ObservedEvaluationResult,
)


def evaluate_observed_result(
    case: EvaluationCase,
    observed: ObservedEvaluationResult | None,
) -> EvaluationCaseOutcome:
    """Evaluate one explicit observed result against caller-supplied truth.

    This function does not infer truth, call a model, interpret confidence,
    mutate state, or collapse abstention into correctness/incorrectness.
    """

    if not isinstance(case, EvaluationCase):
        raise TypeError("case must be an EvaluationCase.")

    case.validate()

    if observed is None:
        outcome = EvaluationCaseOutcome(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=case.case_id,
            classification=(
                EvaluationOutcomeClassification.INVALID_OR_MISSING
            ),
            reason_codes=("missing_observed_result",),
        )
        outcome.validate()
        return outcome

    if not isinstance(observed, ObservedEvaluationResult):
        raise TypeError(
            "observed must be an ObservedEvaluationResult or None."
        )

    if observed.case_id != case.case_id:
        raise ValueError(
            "Observed evaluation result case_id does not match "
            "the authoritative evaluation case."
        )

    try:
        observed.validate()
    except (TypeError, ValueError):
        outcome = EvaluationCaseOutcome(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=case.case_id,
            classification=(
                EvaluationOutcomeClassification.INVALID_OR_MISSING
            ),
            reason_codes=("invalid_observed_result",),
        )
        outcome.validate()
        return outcome

    if observed.abstained:
        outcome = EvaluationCaseOutcome(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=case.case_id,
            classification=EvaluationOutcomeClassification.ABSTAINED,
            evidence_refs=observed.evidence_refs,
        )
        outcome.validate()
        return outcome

    candidate_id = observed.candidate_id
    if candidate_id is None:
        raise AssertionError(
            "validated non-abstained result must contain candidate_id."
        )

    classification = (
        EvaluationOutcomeClassification.CORRECT
        if candidate_id in case.allowed_candidate_ids
        else EvaluationOutcomeClassification.INCORRECT
    )

    reason_codes = (
        ()
        if classification is EvaluationOutcomeClassification.CORRECT
        else ("candidate_not_allowed",)
    )

    outcome = EvaluationCaseOutcome(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id=case.case_id,
        classification=classification,
        observed_candidate_id=candidate_id,
        evidence_refs=observed.evidence_refs,
        reason_codes=reason_codes,
    )
    outcome.validate()
    return outcome