"""Provider-neutral, advisory identification execution; see the approved amendment.

Execution validates structure and identity, never policy compliance or truth.
Injected callables are trusted application code, not a sandbox boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re

from ai_evaluation_contracts import EvaluationCase
from identification_specialist import (
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
    run_identification_specialist,
)
from identification_verification_evaluation_report import (
    IdentificationVerificationEvaluationReport,
    compare_identification_verification_and_evaluation,
)


def _validate_executor_id(executor_id: str) -> None:
    if not isinstance(executor_id, str):
        raise TypeError("executor_id must be a string.")
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", executor_id) is None:
        raise ValueError("executor_id must be 1-128 ASCII label characters.")


def _validate_request(request: IdentificationSpecialistRequest) -> None:
    if not isinstance(request, IdentificationSpecialistRequest):
        raise TypeError("request must be an IdentificationSpecialistRequest.")
    request.validate()


@dataclass(frozen=True, slots=True)
class IdentificationSpecialistExecutor:
    """Explicit implementation label and synchronous injectable callable."""

    executor_id: str
    execute: Callable[[IdentificationSpecialistRequest], IdentificationSpecialistResult]

    def validate(self) -> None:
        _validate_executor_id(self.executor_id)
        if not callable(self.execute):
            raise TypeError("execute must be callable.")


# Adapt directly: the existing function remains the sole source of policy.
DETERMINISTIC_IDENTIFICATION_EXECUTOR = IdentificationSpecialistExecutor(
    executor_id="deterministic-identification-v1",
    execute=run_identification_specialist,
)


@dataclass(frozen=True, slots=True)
class IdentificationSpecialistExecution:
    """Original result with caller-declared, non-authenticated provenance."""

    executor_id: str
    specialist_result: IdentificationSpecialistResult

    def validate(self, request: IdentificationSpecialistRequest) -> None:
        _validate_request(request)
        _validate_executor_id(self.executor_id)
        if not isinstance(self.specialist_result, IdentificationSpecialistResult):
            raise TypeError("specialist_result must be an IdentificationSpecialistResult.")
        self.specialist_result.validate()
        if self.specialist_result.case_id != request.case_id:
            raise ValueError("specialist_result case_id must match request case_id.")
        if self.specialist_result.evidence_refs != request.evidence_refs:
            raise ValueError("specialist_result evidence_refs must match request exactly.")
        # Candidate-policy violations deliberately remain verifier decisions.


def execute_identification_specialist(
    request: IdentificationSpecialistRequest,
    executor: IdentificationSpecialistExecutor,
) -> IdentificationSpecialistExecution:
    """Invoke once, preserve the result, and reject incompatible output."""

    _validate_request(request)
    if not isinstance(executor, IdentificationSpecialistExecutor):
        raise TypeError("executor must be an IdentificationSpecialistExecutor.")
    executor.validate()
    result = executor.execute(request)
    execution = IdentificationSpecialistExecution(executor.executor_id, result)
    execution.validate(request)
    return execution


@dataclass(frozen=True, slots=True)
class IdentificationSpecialistExecutionReport:
    """Execution provenance alongside independent policy and truth findings."""

    execution: IdentificationSpecialistExecution
    comparison: IdentificationVerificationEvaluationReport

    def validate(
        self,
        request: IdentificationSpecialistRequest,
        evaluation_case: EvaluationCase,
    ) -> None:
        """Recompute comparison from authoritative inputs, never re-execute."""

        if not isinstance(self.execution, IdentificationSpecialistExecution):
            raise TypeError("execution must be an IdentificationSpecialistExecution.")
        self.execution.validate(request)
        if not isinstance(self.comparison, IdentificationVerificationEvaluationReport):
            raise TypeError(
                "comparison must be an IdentificationVerificationEvaluationReport."
            )
        self.comparison.validate()
        expected = compare_identification_verification_and_evaluation(
            request, self.execution.specialist_result, evaluation_case,
        )
        if self.comparison != expected:
            raise ValueError("comparison does not match execution and authoritative inputs.")


def execute_and_compare_identification(
    request: IdentificationSpecialistRequest,
    executor: IdentificationSpecialistExecutor,
    evaluation_case: EvaluationCase,
) -> IdentificationSpecialistExecutionReport:
    """Execute without exposing evaluation truth, then reuse comparison."""

    _validate_request(request)
    if not isinstance(evaluation_case, EvaluationCase):
        raise TypeError("evaluation_case must be an EvaluationCase.")
    evaluation_case.validate()
    if evaluation_case.case_id != request.case_id:
        raise ValueError("evaluation_case case_id must match request case_id.")
    execution = execute_identification_specialist(request, executor)
    comparison = compare_identification_verification_and_evaluation(
        request, execution.specialist_result, evaluation_case,
    )
    # Both components have already been validated by their existing boundaries.
    return IdentificationSpecialistExecutionReport(execution, comparison)
