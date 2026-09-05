"""Operational bridge for one bounded Codex implementation handoff.

This module connects the existing Stage 7 remediation package to one caller-
supplied execution role and then routes the structured result through the
existing Stage 7 fail-closed review and Stage 8 independent reviewer.

It deliberately does not implement orchestration, retries, autonomous loops,
repository merge/promotion, or scope expansion. The executor is injected so the
repository contract remains deterministic and testable while the caller owns the
actual Codex transport/invocation mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Protocol, Tuple, runtime_checkable

from improvement_agent import (
    ImprovementResult,
    ImprovementReview,
    ImprovementStatus,
    RemediationPackage,
    render_codex_task,
    review_improvement_result,
)
from reviewer_agent import (
    InvariantEvidence,
    ReviewerReport,
    ReviewRecommendation,
    review_candidate,
)


@runtime_checkable
class CodexExecutionRole(Protocol):
    """Single-shot execution boundary supplied by the operational caller."""

    def execute(self, task: str, package: RemediationPackage) -> ImprovementResult:
        """Execute exactly one bounded task and return structured evidence."""


class HandoffStatus(str, Enum):
    """Terminal status for one operational handoff attempt."""

    READY_FOR_HUMAN_REVIEW = "ready_for_human_review"
    STOPPED = "stopped"


@dataclass(frozen=True)
class OperationalHandoffReport:
    """Structured terminal evidence for one bounded execution attempt."""

    status: HandoffStatus
    task: str
    implementation_result: ImprovementResult
    implementation_review: ImprovementReview
    reviewer_report: ReviewerReport
    execution_error: str | None = None

    @property
    def ready_for_human_review(self) -> bool:
        """Whether all machine-side evidence passed for human review.

        This is not merge or promotion authority.
        """

        return self.status is HandoffStatus.READY_FOR_HUMAN_REVIEW


def _stopped_result(reason: str) -> ImprovementResult:
    return ImprovementResult(
        status=ImprovementStatus.STOPPED,
        changed_files=(),
        validation=(),
        unresolved_issues=(reason,),
        stopped_gate="codex-execution",
    )


def execute_operational_handoff(
    package: RemediationPackage,
    executor: CodexExecutionRole,
    invariant_evidence: Iterable[InvariantEvidence],
) -> OperationalHandoffReport:
    """Execute and review exactly one bounded implementation package.

    The executor is invoked once. Any execution exception, malformed result,
    Stage 7 review failure, or Stage 8 review failure stops the handoff. The
    function never retries, repairs, broadens scope, merges, or promotes.
    """

    task = render_codex_task(package)
    supplied_invariants: Tuple[InvariantEvidence, ...] = tuple(invariant_evidence)
    execution_error: str | None = None

    try:
        result = executor.execute(task, package)
    except Exception as exc:  # noqa: BLE001 - fail-closed transport boundary
        execution_error = f"{type(exc).__name__}: {exc}"
        result = _stopped_result(f"Codex execution failed: {execution_error}")

    if not isinstance(result, ImprovementResult):
        execution_error = "executor returned malformed result"
        result = _stopped_result(execution_error)

    implementation_review = review_improvement_result(package, result)
    reviewer_report = review_candidate(package, result, supplied_invariants)

    ready = (
        execution_error is None
        and implementation_review.acceptable
        and reviewer_report.recommendation is ReviewRecommendation.PASS
    )

    return OperationalHandoffReport(
        status=(
            HandoffStatus.READY_FOR_HUMAN_REVIEW if ready else HandoffStatus.STOPPED
        ),
        task=task,
        implementation_result=result,
        implementation_review=implementation_review,
        reviewer_report=reviewer_report,
        execution_error=execution_error,
    )
