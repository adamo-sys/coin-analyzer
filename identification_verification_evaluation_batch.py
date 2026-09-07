"""Deterministic batch reporting for identification verification/evaluation.

The batch layer preserves two independent authorities:

- specialist verification measures compliance with caller-authorized policy;
- evaluation measures correctness against caller-supplied authoritative cases.

These are aggregated independently and must never be reinterpreted as one
another.

This module is local-only, deterministic, read-only, and advisory.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_evaluation_contracts import (
    EvaluationAggregate,
    EvaluationCase,
    aggregate_evaluation_outcomes,
)
from identification_specialist import (
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
)
from identification_verification_evaluation_report import (
    IdentificationVerificationEvaluationReport,
    compare_identification_verification_and_evaluation,
)


BatchItem = tuple[
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
    EvaluationCase,
]


@dataclass(frozen=True, slots=True)
class IdentificationVerificationEvaluationBatchReport:
    """Immutable ordered batch of verification/evaluation comparison reports."""

    reports: tuple[IdentificationVerificationEvaluationReport, ...]
    verifier_accepted: int
    verifier_rejected: int
    evaluation_aggregate: EvaluationAggregate

    def validate(self) -> None:
        """Validate batch structure and recomputable aggregate invariants."""

        if not isinstance(self.reports, tuple):
            raise TypeError("reports must be a tuple.")

        if not self.reports:
            raise ValueError("reports must not be empty.")

        seen_case_ids: set[str] = set()

        for report in self.reports:
            if not isinstance(
                report,
                IdentificationVerificationEvaluationReport,
            ):
                raise TypeError(
                    "reports must contain "
                    "IdentificationVerificationEvaluationReport values."
                )

            report.validate()

            case_id = report.specialist_result.case_id
            if case_id in seen_case_ids:
                raise ValueError(
                    f"Duplicate batch case_id: {case_id!r}."
                )
            seen_case_ids.add(case_id)

        for name, value in (
            ("verifier_accepted", self.verifier_accepted),
            ("verifier_rejected", self.verifier_rejected),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer.")
            if value < 0:
                raise ValueError(f"{name} must not be negative.")

        if (
            self.verifier_accepted
            + self.verifier_rejected
            != len(self.reports)
        ):
            raise ValueError(
                "Verifier counts must sum exactly to report count."
            )

        expected_accepted = sum(
            1
            for report in self.reports
            if report.verification.accepted
        )
        expected_rejected = len(self.reports) - expected_accepted

        if self.verifier_accepted != expected_accepted:
            raise ValueError(
                "verifier_accepted does not match reports."
            )

        if self.verifier_rejected != expected_rejected:
            raise ValueError(
                "verifier_rejected does not match reports."
            )

        if not isinstance(
            self.evaluation_aggregate,
            EvaluationAggregate,
        ):
            raise TypeError(
                "evaluation_aggregate must be an EvaluationAggregate."
            )

        self.evaluation_aggregate.validate()

        expected_evaluation_aggregate = aggregate_evaluation_outcomes(
            tuple(
                report.evaluation_outcome
                for report in self.reports
            )
        )

        if self.evaluation_aggregate != expected_evaluation_aggregate:
            raise ValueError(
                "evaluation_aggregate does not match report outcomes."
            )


def compare_identification_batch(
    items: tuple[BatchItem, ...],
) -> IdentificationVerificationEvaluationBatchReport:
    """Compare an ordered batch using the existing single-case seam."""

    if not isinstance(items, tuple):
        raise TypeError("items must be a tuple.")

    if not items:
        raise ValueError("items must not be empty.")

    validated_items: list[BatchItem] = []
    seen_case_ids: set[str] = set()

    for index, item in enumerate(items):
        if not isinstance(item, tuple):
            raise TypeError(
                f"items[{index}] must be a tuple."
            )

        if len(item) != 3:
            raise ValueError(
                f"items[{index}] must contain exactly 3 values."
            )

        request, result, evaluation_case = item

        if not isinstance(
            request,
            IdentificationSpecialistRequest,
        ):
            raise TypeError(
                f"items[{index}][0] must be an "
                "IdentificationSpecialistRequest."
            )

        if not isinstance(
            result,
            IdentificationSpecialistResult,
        ):
            raise TypeError(
                f"items[{index}][1] must be an "
                "IdentificationSpecialistResult."
            )

        if not isinstance(evaluation_case, EvaluationCase):
            raise TypeError(
                f"items[{index}][2] must be an EvaluationCase."
            )

        request.validate()
        result.validate()
        evaluation_case.validate()

        if request.case_id in seen_case_ids:
            raise ValueError(
                f"Duplicate batch case_id: {request.case_id!r}."
            )

        seen_case_ids.add(request.case_id)
        validated_items.append(
            (request, result, evaluation_case)
        )

    reports = tuple(
        compare_identification_verification_and_evaluation(
            request,
            result,
            evaluation_case,
        )
        for request, result, evaluation_case in validated_items
    )

    verifier_accepted = sum(
        1
        for report in reports
        if report.verification.accepted
    )
    verifier_rejected = len(reports) - verifier_accepted

    evaluation_aggregate = aggregate_evaluation_outcomes(
        tuple(
            report.evaluation_outcome
            for report in reports
        )
    )

    batch = IdentificationVerificationEvaluationBatchReport(
        reports=reports,
        verifier_accepted=verifier_accepted,
        verifier_rejected=verifier_rejected,
        evaluation_aggregate=evaluation_aggregate,
    )
    batch.validate()
    return batch
