"""Bounded Stage 10 two-candidate experiment.

Runs exactly two caller-supplied candidate execution roles against one frozen
RemediationPackage. Candidates are independently validated/reviewed through the
existing Stage 7/8 handoff. This module does not retry, compose candidate code,
select new targets, merge, deploy, release, or promote changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from improvement_agent import RemediationPackage
from operational_handoff import CodexExecutionRole, OperationalHandoffReport, execute_operational_handoff
from reviewer_agent import InvariantEvidence, ReviewRecommendation


class CandidateState(str, Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    VALIDATED = "validated"
    REVIEWED = "reviewed"
    VIABLE = "viable"
    REJECTED = "rejected"


class ExperimentState(str, Enum):
    NO_VIABLE_CANDIDATES = "no_viable_candidates"
    ONE_VIABLE_CANDIDATE = "one_viable_candidate"
    MULTIPLE_VIABLE_CANDIDATES = "multiple_viable_candidates"
    STOPPED = "stopped"


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    executor: CodexExecutionRole
    invariant_evidence: Tuple[InvariantEvidence, ...]


@dataclass(frozen=True)
class CandidateOutcome:
    candidate_id: str
    state: CandidateState
    handoff: OperationalHandoffReport
    terminal_reason: str | None


@dataclass(frozen=True)
class ParallelExperimentResult:
    experiment_id: str
    package: RemediationPackage
    candidate_ids: Tuple[str, str]
    candidates: Tuple[CandidateOutcome, ...]
    state: ExperimentState
    viable_candidate_ids: Tuple[str, ...]
    preferred_candidate_id: str | None
    terminal_reason: str | None
    human_review_required: bool


def _candidate_reason(handoff: OperationalHandoffReport) -> str | None:
    if handoff.execution_error:
        return handoff.execution_error
    if not handoff.implementation_review.acceptable:
        return "; ".join(handoff.implementation_review.violations) or "implementation validation failed"
    if handoff.reviewer_report.recommendation is not ReviewRecommendation.PASS:
        return "; ".join(handoff.reviewer_report.findings) or "independent review failed"
    return None


def _run_candidate(package: RemediationPackage, spec: CandidateSpec) -> CandidateOutcome:
    handoff = execute_operational_handoff(package, spec.executor, tuple(spec.invariant_evidence))
    reason = _candidate_reason(handoff)
    if handoff.ready_for_human_review and reason is None:
        return CandidateOutcome(spec.candidate_id, CandidateState.VIABLE, handoff, None)
    return CandidateOutcome(spec.candidate_id, CandidateState.REJECTED, handoff, reason or "candidate rejected")


def _preference(outcomes: Tuple[CandidateOutcome, ...]) -> str | None:
    """Deterministic evidence-only comparison; ties remain unresolved."""
    viable = tuple(item for item in outcomes if item.state is CandidateState.VIABLE)
    if len(viable) != 2:
        return viable[0].candidate_id if len(viable) == 1 else None

    left, right = viable
    left_result = left.handoff.implementation_result
    right_result = right.handoff.implementation_result
    left_score = (len(left_result.changed_files), len(left_result.risks))
    right_score = (len(right_result.changed_files), len(right_result.risks))
    if left_score < right_score:
        return left.candidate_id
    if right_score < left_score:
        return right.candidate_id
    return None


def execute_parallel_experiment(
    experiment_id: str,
    package: RemediationPackage,
    candidates: Tuple[CandidateSpec, CandidateSpec],
) -> ParallelExperimentResult:
    """Execute one fixed two-candidate experiment, once per candidate."""
    normalized_id = str(experiment_id).strip()
    ids = tuple(str(item.candidate_id).strip() for item in candidates)

    if not normalized_id:
        return ParallelExperimentResult("", package, ids, (), ExperimentState.STOPPED, (), None, "experiment_id must be non-empty", False)
    if len(candidates) != 2:
        return ParallelExperimentResult(normalized_id, package, ids, (), ExperimentState.STOPPED, (), None, "exactly two candidates are required", False)
    if any(not item for item in ids) or len(set(ids)) != 2:
        return ParallelExperimentResult(normalized_id, package, ids, (), ExperimentState.STOPPED, (), None, "candidate identifiers must be non-empty and unique", False)

    # Snapshot both evidence sets before either executor runs so one candidate
    # cannot alter the other's authorized review evidence mid-experiment.
    frozen_specs = tuple(
        CandidateSpec(spec.candidate_id.strip(), spec.executor, tuple(spec.invariant_evidence))
        for spec in candidates
    )
    outcomes = tuple(_run_candidate(package, spec) for spec in frozen_specs)
    viable = tuple(item.candidate_id for item in outcomes if item.state is CandidateState.VIABLE)
    preferred = _preference(outcomes)

    if not viable:
        state = ExperimentState.NO_VIABLE_CANDIDATES
    elif len(viable) == 1:
        state = ExperimentState.ONE_VIABLE_CANDIDATE
    else:
        state = ExperimentState.MULTIPLE_VIABLE_CANDIDATES

    return ParallelExperimentResult(
        experiment_id=normalized_id,
        package=package,
        candidate_ids=(ids[0], ids[1]),
        candidates=outcomes,
        state=state,
        viable_candidate_ids=viable,
        preferred_candidate_id=preferred,
        terminal_reason=None,
        human_review_required=bool(viable),
    )
