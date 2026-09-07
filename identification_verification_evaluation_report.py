"""Compare identification-policy verification with evaluation correctness.

This module intentionally keeps two independent questions separate:

1. Did the specialist result obey the caller-authorized deterministic policy?
2. Was the observed result correct against an explicit authoritative
   evaluation case?

Verifier acceptance MUST NOT be interpreted as evaluation correctness.
Evaluation correctness MUST NOT be interpreted as verifier acceptance.

The module is deterministic, local-only, read-only, and advisory.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_evaluation_contracts import (
    EvaluationCase,
    EvaluationCaseOutcome,
)
from ai_evaluation_evaluator import evaluate_observed_result
from identification_specialist import (
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
)
from identification_specialist_evaluation_adapter import (
    adapt_identification_specialist_result,
)
from identification_specialist_verifier import (
    IdentificationSpecialistVerification,
    verify_identification_specialist_result,
)


@dataclass(frozen=True, slots=True)
class IdentificationVerificationEvaluationReport:
    """Immutable comparison of policy verification and evaluation outcome."""

    specialist_result: IdentificationSpecialistResult
    verification: IdentificationSpecialistVerification
    evaluation_outcome: EvaluationCaseOutcome

    def validate(self) -> None:
        """Validate report structure without recomputing either verdict."""

        if not isinstance(
            self.specialist_result,
            IdentificationSpecialistResult,
        ):
            raise TypeError(
                "specialist_result must be an IdentificationSpecialistResult."
            )

        if not isinstance(
            self.verification,
            IdentificationSpecialistVerification,
        ):
            raise TypeError(
                "verification must be an "
                "IdentificationSpecialistVerification."
            )

        if not isinstance(
            self.evaluation_outcome,
            EvaluationCaseOutcome,
        ):
            raise TypeError(
                "evaluation_outcome must be an EvaluationCaseOutcome."
            )

        self.specialist_result.validate()
        self.verification.validate()
        self.evaluation_outcome.validate()

        if (
            self.evaluation_outcome.case_id
            != self.specialist_result.case_id
        ):
            raise ValueError(
                "evaluation_outcome case_id must match "
                "specialist_result case_id."
            )


def compare_identification_verification_and_evaluation(
    request: IdentificationSpecialistRequest,
    result: IdentificationSpecialistResult,
    evaluation_case: EvaluationCase,
) -> IdentificationVerificationEvaluationReport:
    """Verify one specialist result and evaluate it independently.

    The verifier checks policy compliance against the request.

    The evaluator checks correctness against the separately supplied
    authoritative evaluation case.

    Neither verdict is derived from the other.
    """

    if not isinstance(request, IdentificationSpecialistRequest):
        raise TypeError(
            "request must be an IdentificationSpecialistRequest."
        )

    if not isinstance(result, IdentificationSpecialistResult):
        raise TypeError(
            "result must be an IdentificationSpecialistResult."
        )

    if not isinstance(evaluation_case, EvaluationCase):
        raise TypeError("evaluation_case must be an EvaluationCase.")

    request.validate()
    result.validate()
    evaluation_case.validate()

    if evaluation_case.case_id != request.case_id:
        raise ValueError(
            "evaluation_case case_id must match request case_id."
        )

    if evaluation_case.case_id != result.case_id:
        raise ValueError(
            "evaluation_case case_id must match result case_id."
        )

    verification = verify_identification_specialist_result(
        request,
        result,
    )

    observed = adapt_identification_specialist_result(result)

    evaluation_outcome = evaluate_observed_result(
        evaluation_case,
        observed,
    )

    report = IdentificationVerificationEvaluationReport(
        specialist_result=result,
        verification=verification,
        evaluation_outcome=evaluation_outcome,
    )
    report.validate()
    return report
