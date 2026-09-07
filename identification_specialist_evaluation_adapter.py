"""Adapter from the identification specialist into frozen evaluation output."""

from __future__ import annotations

from ai_evaluation_contracts import ObservedEvaluationResult
from identification_specialist import IdentificationSpecialistResult


def adapt_identification_specialist_result(
    result: IdentificationSpecialistResult,
) -> ObservedEvaluationResult:
    """Adapt one validated specialist result without changing its meaning."""

    if not isinstance(result, IdentificationSpecialistResult):
        raise TypeError(
            "result must be an IdentificationSpecialistResult."
        )

    result.validate()

    observed = ObservedEvaluationResult(
        schema_version=result.schema_version,
        case_id=result.case_id,
        candidate_id=result.candidate_id,
        abstained=result.abstained,
        evidence_refs=result.evidence_refs,
    )
    observed.validate()
    return observed
