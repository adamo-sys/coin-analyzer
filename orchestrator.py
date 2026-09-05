"""Deterministic Stage 9 coordinator for one bounded self-improvement run.

The orchestrator composes the existing diagnostic, remediation, implementation,
and independent-review contracts. It does not retry, repair, expand scope,
select new work, merge, deploy, release, or promote changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Tuple

from diagnostic_agent import DiagnosticFinding
from improvement_agent import (
    ImprovementResult,
    ImprovementReview,
    ImprovementStatus,
    RemediationPackage,
    build_remediation_package,
)
from operational_handoff import (
    CodexExecutionRole,
    OperationalHandoffReport,
    execute_operational_handoff,
)
from reviewer_agent import InvariantEvidence, ReviewerReport, ReviewRecommendation


class OrchestratorState(str, Enum):
    PENDING = "pending"
    DIAGNOSED = "diagnosed"
    PACKAGE_FROZEN = "package_frozen"
    IMPLEMENTATION_COMPLETE = "implementation_complete"
    REVIEW_COMPLETE = "review_complete"
    READY_FOR_HUMAN_REVIEW = "ready_for_human_review"
    STOPPED = "stopped"


@dataclass(frozen=True)
class OrchestratorTransition:
    from_state: OrchestratorState
    to_state: OrchestratorState
    event: str
    evidence_type: str


@dataclass(frozen=True)
class OrchestratorRequest:
    run_id: str
    finding: DiagnosticFinding
    objective: str
    allowed_paths: Tuple[str, ...]
    invariants: Tuple[str, ...]
    focused_tests: Tuple[str, ...]
    required_gates: Tuple[str, ...]


@dataclass(frozen=True)
class OrchestratorRun:
    run_id: str
    state: OrchestratorState
    diagnostic_finding: DiagnosticFinding | None
    remediation_package: RemediationPackage | None
    implementation_result: ImprovementResult | None
    implementation_review: ImprovementReview | None
    reviewer_report: ReviewerReport | None
    transitions: Tuple[OrchestratorTransition, ...]
    terminal_reason: str | None
    human_review_required: bool

    @property
    def ready_for_human_review(self) -> bool:
        return self.state is OrchestratorState.READY_FOR_HUMAN_REVIEW


def _transition(
    history: list[OrchestratorTransition],
    current: OrchestratorState,
    target: OrchestratorState,
    *,
    event: str,
    evidence_type: str,
) -> OrchestratorState:
    if current is OrchestratorState.STOPPED:
        raise RuntimeError("STOPPED is terminal")

    allowed = {
        OrchestratorState.PENDING: {OrchestratorState.DIAGNOSED, OrchestratorState.STOPPED},
        OrchestratorState.DIAGNOSED: {
            OrchestratorState.PACKAGE_FROZEN,
            OrchestratorState.STOPPED,
        },
        OrchestratorState.PACKAGE_FROZEN: {
            OrchestratorState.IMPLEMENTATION_COMPLETE,
            OrchestratorState.STOPPED,
        },
        OrchestratorState.IMPLEMENTATION_COMPLETE: {
            OrchestratorState.REVIEW_COMPLETE,
            OrchestratorState.STOPPED,
        },
        OrchestratorState.REVIEW_COMPLETE: {
            OrchestratorState.READY_FOR_HUMAN_REVIEW,
            OrchestratorState.STOPPED,
        },
        OrchestratorState.READY_FOR_HUMAN_REVIEW: set(),
        OrchestratorState.STOPPED: set(),
    }
    if target not in allowed[current]:
        raise RuntimeError(f"invalid orchestrator transition: {current.value} -> {target.value}")

    history.append(
        OrchestratorTransition(
            from_state=current,
            to_state=target,
            event=event,
            evidence_type=evidence_type,
        )
    )
    return target


def _stopped_run(
    *,
    run_id: str,
    current: OrchestratorState,
    history: list[OrchestratorTransition],
    reason: str,
    evidence_type: str,
    finding: DiagnosticFinding | None,
    package: RemediationPackage | None,
    handoff: OperationalHandoffReport | None,
) -> OrchestratorRun:
    state = _transition(
        history,
        current,
        OrchestratorState.STOPPED,
        event=reason,
        evidence_type=evidence_type,
    )
    return OrchestratorRun(
        run_id=run_id,
        state=state,
        diagnostic_finding=finding,
        remediation_package=package,
        implementation_result=(handoff.implementation_result if handoff else None),
        implementation_review=(handoff.implementation_review if handoff else None),
        reviewer_report=(handoff.reviewer_report if handoff else None),
        transitions=tuple(history),
        terminal_reason=reason,
        human_review_required=False,
    )


def execute_orchestrator_run(
    request: OrchestratorRequest,
    executor: CodexExecutionRole,
    invariant_evidence: Iterable[InvariantEvidence],
) -> OrchestratorRun:
    """Run exactly one bounded Stage 9 sequence.

    The run is single-shot and fail-closed. No retry, repair, scope expansion,
    automatic resume, target selection, or promotion action is performed.
    """

    history: list[OrchestratorTransition] = []
    state = OrchestratorState.PENDING
    package: RemediationPackage | None = None
    handoff: OperationalHandoffReport | None = None

    run_id = str(request.run_id).strip()
    if not run_id:
        return _stopped_run(
            run_id="",
            current=state,
            history=history,
            reason="run_id must be non-empty",
            evidence_type="request",
            finding=None,
            package=None,
            handoff=None,
        )

    if not isinstance(request.finding, DiagnosticFinding):
        return _stopped_run(
            run_id=run_id,
            current=state,
            history=history,
            reason="diagnostic finding is missing or malformed",
            evidence_type="diagnostic",
            finding=None,
            package=None,
            handoff=None,
        )

    state = _transition(
        history,
        state,
        OrchestratorState.DIAGNOSED,
        event="bounded diagnostic finding accepted",
        evidence_type="DiagnosticFinding",
    )

    try:
        package = build_remediation_package(
            request.finding,
            objective=request.objective,
            allowed_paths=request.allowed_paths,
            invariants=request.invariants,
            focused_tests=request.focused_tests,
            required_gates=request.required_gates,
        )
    except (TypeError, ValueError) as exc:
        return _stopped_run(
            run_id=run_id,
            current=state,
            history=history,
            reason=f"invalid remediation package: {exc}",
            evidence_type="RemediationPackage",
            finding=request.finding,
            package=None,
            handoff=None,
        )

    state = _transition(
        history,
        state,
        OrchestratorState.PACKAGE_FROZEN,
        event="remediation package frozen",
        evidence_type="RemediationPackage",
    )

    handoff = execute_operational_handoff(
        package,
        executor,
        tuple(invariant_evidence),
    )

    result = handoff.implementation_result
    if (
        result.status is not ImprovementStatus.COMPLETED
        or not handoff.implementation_review.acceptable
        or handoff.execution_error is not None
    ):
        reason = handoff.execution_error or "; ".join(
            handoff.implementation_review.violations
        ) or "implementation did not complete successfully"
        return _stopped_run(
            run_id=run_id,
            current=state,
            history=history,
            reason=reason,
            evidence_type="ImprovementResult",
            finding=request.finding,
            package=package,
            handoff=handoff,
        )

    state = _transition(
        history,
        state,
        OrchestratorState.IMPLEMENTATION_COMPLETE,
        event="bounded implementation completed and passed Stage 7 review",
        evidence_type="ImprovementReview",
    )

    if handoff.reviewer_report.recommendation is not ReviewRecommendation.PASS:
        reason = "; ".join(handoff.reviewer_report.findings) or "independent reviewer failed"
        return _stopped_run(
            run_id=run_id,
            current=state,
            history=history,
            reason=reason,
            evidence_type="ReviewerReport",
            finding=request.finding,
            package=package,
            handoff=handoff,
        )

    state = _transition(
        history,
        state,
        OrchestratorState.REVIEW_COMPLETE,
        event="independent review passed",
        evidence_type="ReviewerReport",
    )
    state = _transition(
        history,
        state,
        OrchestratorState.READY_FOR_HUMAN_REVIEW,
        event="machine-side pipeline complete; human review required",
        evidence_type="orchestrator",
    )

    return OrchestratorRun(
        run_id=run_id,
        state=state,
        diagnostic_finding=request.finding,
        remediation_package=package,
        implementation_result=handoff.implementation_result,
        implementation_review=handoff.implementation_review,
        reviewer_report=handoff.reviewer_report,
        transitions=tuple(history),
        terminal_reason=None,
        human_review_required=True,
    )
