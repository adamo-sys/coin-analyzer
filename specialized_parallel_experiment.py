"""Stage 11 specialized two-candidate runtime.

Adds explicit strategy intent to the existing bounded Stage 10 experiment without
changing candidate count, package scope, validation/review authority, or human
promotion boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from improvement_agent import RemediationPackage
from operational_handoff import CodexExecutionRole
from parallel_experiment import CandidateSpec, ParallelExperimentResult, execute_parallel_experiment
from reviewer_agent import InvariantEvidence


class StrategyKind(str, Enum):
    MINIMAL_CHANGE = "minimal_change"
    ALTERNATIVE_DESIGN = "alternative_design"


@dataclass(frozen=True)
class SpecializedCandidateSpec:
    candidate_id: str
    strategy: StrategyKind
    executor: CodexExecutionRole
    invariant_evidence: Tuple[InvariantEvidence, ...]
    strategy_summary: str = ""


@dataclass(frozen=True)
class SpecializedCandidateMetadata:
    candidate_id: str
    strategy: StrategyKind
    strategy_summary: str


@dataclass(frozen=True)
class SpecializedParallelExperimentResult:
    experiment: ParallelExperimentResult
    strategy_metadata: Tuple[SpecializedCandidateMetadata, SpecializedCandidateMetadata]


class _StrategyExecutor:
    def __init__(self, strategy: StrategyKind, executor: CodexExecutionRole):
        self._strategy = strategy
        self._executor = executor

    def execute(self, task: str, package: RemediationPackage):
        if self._strategy is StrategyKind.MINIMAL_CHANGE:
            strategy_instruction = (
                "\n\nSTAGE 11 STRATEGY: MINIMAL_CHANGE\n"
                "Prefer the smallest compliant implementation surface, minimize changed files, "
                "reuse existing abstractions where reasonable, and avoid speculative refactors. "
                "Do not alter scope, allowed paths, invariants, tests, or required gates."
            )
        else:
            strategy_instruction = (
                "\n\nSTAGE 11 STRATEGY: ALTERNATIVE_DESIGN\n"
                "Pursue a materially different bounded implementation structure when one exists, "
                "while preserving exactly the same scope, allowed paths, invariants, tests, and required gates. "
                "Do not expand architecture merely to appear different."
            )
        return self._executor.execute(task + strategy_instruction, package)


def execute_specialized_parallel_experiment(
    experiment_id: str,
    package: RemediationPackage,
    candidates: Tuple[SpecializedCandidateSpec, SpecializedCandidateSpec],
) -> SpecializedParallelExperimentResult:
    """Execute one fixed MINIMAL_CHANGE + ALTERNATIVE_DESIGN experiment."""
    if len(candidates) != 2:
        base = execute_parallel_experiment(experiment_id, package, ())
        return SpecializedParallelExperimentResult(base, ())  # type: ignore[arg-type]

    strategies = tuple(candidate.strategy for candidate in candidates)
    expected = {StrategyKind.MINIMAL_CHANGE, StrategyKind.ALTERNATIVE_DESIGN}
    if set(strategies) != expected or len(set(strategies)) != 2:
        # Reuse Stage 10's fail-closed STOPPED artifact by deliberately passing duplicate IDs.
        duplicate = CandidateSpec("invalid-strategy", _StrategyExecutor(candidates[0].strategy, candidates[0].executor), tuple(candidates[0].invariant_evidence))
        base = execute_parallel_experiment(experiment_id, package, (duplicate, duplicate))
        metadata = tuple(
            SpecializedCandidateMetadata(c.candidate_id.strip(), c.strategy, c.strategy_summary.strip())
            for c in candidates
        )
        return SpecializedParallelExperimentResult(base, metadata)  # type: ignore[arg-type]

    frozen = tuple(
        SpecializedCandidateSpec(
            candidate_id=c.candidate_id.strip(),
            strategy=c.strategy,
            executor=c.executor,
            invariant_evidence=tuple(c.invariant_evidence),
            strategy_summary=c.strategy_summary.strip(),
        )
        for c in candidates
    )

    base_specs = tuple(
        CandidateSpec(
            candidate_id=c.candidate_id,
            executor=_StrategyExecutor(c.strategy, c.executor),
            invariant_evidence=tuple(c.invariant_evidence),
        )
        for c in frozen
    )
    base = execute_parallel_experiment(experiment_id, package, base_specs)  # type: ignore[arg-type]
    metadata = tuple(
        SpecializedCandidateMetadata(c.candidate_id, c.strategy, c.strategy_summary)
        for c in frozen
    )
    return SpecializedParallelExperimentResult(base, metadata)  # type: ignore[arg-type]
