"""Standalone benchmark runner for the local LLM resolver experiment."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from time import perf_counter

from .local_llm_resolver import LocalLLMResolver, LocalResolverError, ResolverEvidence, ResolverResult
from .local_llm_resolver_metrics import score_local_resolver_results


@dataclass(frozen=True, slots=True)
class ResolverBenchmarkCase:
    case_id: str
    evidence: ResolverEvidence
    expected: Mapping[str, str]
    identity_certain: bool


def run_local_resolver_benchmark(
    cases: Iterable[ResolverBenchmarkCase],
    *,
    resolver: LocalLLMResolver,
    clock: Callable[[], float] = perf_counter,
) -> dict[str, object]:
    """Run resolver-only benchmark cases and return rows plus aggregate metrics.

    The runner is intentionally headless and does not invoke OCR, UI, persistence,
    or production workflow composition. Each case supplies already-produced bounded
    evidence plus separate provenance-backed expected identity for scoring only.
    """

    rows: list[dict[str, object]] = []
    for case in cases:
        started = clock()
        result: ResolverResult | None = None
        failure: dict[str, str] | None = None
        try:
            result = resolver.resolve(case.evidence)
        except LocalResolverError as exc:
            failure = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            latency_seconds = clock() - started

        rows.append(
            {
                "case_id": case.case_id,
                "expected": dict(case.expected),
                "identity_certain": case.identity_certain,
                "result": result,
                "resolver_failure": failure,
                "latency_seconds": latency_seconds,
            }
        )

    return {
        "schema": "coin-analyzer-local-resolver-benchmark-v1",
        "rows": rows,
        "metrics": score_local_resolver_results(rows),
    }
