"""Optional Phoenix/OpenTelemetry bridge for bounded self-improvement traces.

This module is intentionally advisory. It is never invoked by the Stage 11
runtime automatically, and failures to initialize or emit observability data
must not change self-improvement decisions or promotion authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Callable, Mapping, Tuple

from specialized_parallel_experiment import SpecializedParallelExperimentResult


@dataclass(frozen=True)
class PhoenixTraceSnapshot:
    experiment_id: str
    experiment_state: str
    candidate_ids: Tuple[str, ...]
    viable_candidate_ids: Tuple[str, ...]
    preferred_candidate_id: str | None
    human_review_required: bool
    strategies: Tuple[str, ...]


@dataclass(frozen=True)
class PhoenixEmissionReport:
    emitted: bool
    reason: str | None


def snapshot_specialized_experiment(
    result: SpecializedParallelExperimentResult,
) -> PhoenixTraceSnapshot:
    """Project one Stage 11 result into a bounded, non-content trace snapshot."""
    experiment = result.experiment
    return PhoenixTraceSnapshot(
        experiment_id=str(experiment.experiment_id),
        experiment_state=str(experiment.state.value),
        candidate_ids=tuple(str(item) for item in experiment.candidate_ids),
        viable_candidate_ids=tuple(str(item) for item in experiment.viable_candidate_ids),
        preferred_candidate_id=(
            str(experiment.preferred_candidate_id)
            if experiment.preferred_candidate_id is not None
            else None
        ),
        human_review_required=bool(experiment.human_review_required),
        strategies=tuple(str(item.strategy.value) for item in result.strategy_metadata),
    )


def _attributes(snapshot: PhoenixTraceSnapshot) -> Mapping[str, object]:
    """Return bounded scalar attributes suitable for OpenTelemetry spans."""
    return {
        "coin_analyzer.experiment_id": snapshot.experiment_id,
        "coin_analyzer.experiment_state": snapshot.experiment_state,
        "coin_analyzer.candidate_ids": ",".join(snapshot.candidate_ids),
        "coin_analyzer.viable_candidate_ids": ",".join(snapshot.viable_candidate_ids),
        "coin_analyzer.preferred_candidate_id": snapshot.preferred_candidate_id or "",
        "coin_analyzer.human_review_required": snapshot.human_review_required,
        "coin_analyzer.strategies": ",".join(snapshot.strategies),
    }


def emit_to_phoenix(
    snapshot: PhoenixTraceSnapshot,
    *,
    project_name: str = "coin-analyzer-self-improvement",
    register_fn: Callable[..., object] | None = None,
) -> PhoenixEmissionReport:
    """Emit one advisory span when Phoenix is installed; otherwise fail open.

    ``register_fn`` is injectable for deterministic tests. The default path
    lazily imports ``phoenix.otel.register`` so Phoenix remains an optional
    local dependency rather than a core runtime requirement.
    """
    try:
        if register_fn is None:
            register_fn = getattr(import_module("phoenix.otel"), "register")
        tracer_provider = register_fn(
            project_name=project_name,
            auto_instrument=False,
            set_global_tracer_provider=False,
        )
        tracer = tracer_provider.get_tracer("coin-analyzer.self-improvement")
        with tracer.start_as_current_span("stage11.specialized_parallel_experiment") as span:
            for key, value in _attributes(snapshot).items():
                span.set_attribute(key, value)
        return PhoenixEmissionReport(True, None)
    except Exception as error:
        return PhoenixEmissionReport(False, error.__class__.__name__)
