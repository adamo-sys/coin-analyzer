"""Batch CLI for comparing local Ollama resolver models on synthetic cases."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from collections.abc import Callable, Iterable

from capture_import.local_llm_resolver import LocalLLMResolver, ResolverEvidence, ResolverResult
from capture_import.local_llm_resolver_benchmark import (
    ResolverBenchmarkCase,
    run_local_resolver_benchmark,
)
from capture_import.ollama_local_resolver_runtime import OllamaLocalResolverRuntime

DEFAULT_MODELS = ("qwen3:8b", "qwen-coin:latest")


def synthetic_cases() -> tuple[ResolverBenchmarkCase, ...]:
    """Return a small provenance-safe synthetic benchmark set."""
    return (
        ResolverBenchmarkCase(
            case_id="obvious-1937-10c",
            evidence=ResolverEvidence(
                ocr_text=("CANADA", "10 CENTS", "1937"),
                candidate_countries=("Canada",),
                candidate_denominations=("10 cents",),
                candidate_years=("1937", "1957"),
            ),
            expected={"country": "Canada", "denomination": "10 cents", "year": "1937"},
            identity_certain=True,
        ),
        ResolverBenchmarkCase(
            case_id="conflicting-year-1957",
            evidence=ResolverEvidence(
                ocr_text=("CANADA", "10 CENTS", "1957"),
                candidate_countries=("Canada",),
                candidate_denominations=("10 cents",),
                candidate_years=("1937", "1957"),
            ),
            expected={"country": "Canada", "denomination": "10 cents", "year": "1957"},
            identity_certain=True,
        ),
        ResolverBenchmarkCase(
            case_id="noisy-1967-25c",
            evidence=ResolverEvidence(
                ocr_text=("CANAOA", "25 C?NTS", "1967"),
                candidate_countries=("Canada",),
                candidate_denominations=("25 cents", "10 cents"),
                candidate_years=("1967", "1987"),
            ),
            expected={"country": "Canada", "denomination": "25 cents", "year": "1967"},
            identity_certain=True,
        ),
        ResolverBenchmarkCase(
            case_id="candidate-conflict-1965-5c",
            evidence=ResolverEvidence(
                ocr_text=("CANADA", "5 CENTS", "1965"),
                candidate_countries=("Canada",),
                candidate_denominations=("10 cents", "5 cents"),
                candidate_years=("1965",),
            ),
            expected={"country": "Canada", "denomination": "5 cents", "year": "1965"},
            identity_certain=True,
        ),
        ResolverBenchmarkCase(
            case_id="ambiguous-year-unknown",
            evidence=ResolverEvidence(
                ocr_text=("CANADA", "10 CENTS", "19?7"),
                candidate_countries=("Canada",),
                candidate_denominations=("10 cents",),
                candidate_years=("1937", "1957"),
            ),
            expected={"country": "Canada", "denomination": "10 cents", "year": "1937"},
            identity_certain=False,
        ),
        ResolverBenchmarkCase(
            case_id="insufficient-evidence",
            evidence=ResolverEvidence(ocr_text=("CANADA",)),
            expected={"country": "Canada", "denomination": "10 cents", "year": "1937"},
            identity_certain=False,
        ),
    )


def _serialize_report(report: dict[str, object]) -> dict[str, object]:
    rows_out: list[dict[str, object]] = []
    for row in report["rows"]:  # type: ignore[index]
        row_dict = dict(row)
        result = row_dict.get("result")
        if isinstance(result, ResolverResult):
            row_dict["result"] = asdict(result)
        rows_out.append(row_dict)
    return {
        "schema": report["schema"],
        "rows": rows_out,
        "metrics": report["metrics"],
    }


def run_model_benchmarks(
    models: Iterable[str],
    *,
    timeout_seconds: float,
    runtime_factory: Callable[..., object] = OllamaLocalResolverRuntime,
) -> dict[str, object]:
    comparisons: dict[str, object] = {}
    for model in models:
        runtime = runtime_factory(model=model, timeout_seconds=timeout_seconds)
        resolver = LocalLLMResolver(runtime, enabled=True)  # type: ignore[arg-type]
        report = run_local_resolver_benchmark(synthetic_cases(), resolver=resolver)
        comparisons[model] = _serialize_report(report)
    return {
        "schema": "coin-analyzer-local-resolver-model-comparison-v1",
        "models": comparisons,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare local Ollama resolver models on a small synthetic benchmark."
    )
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Local Ollama model tag; repeatable. Defaults to qwen3:8b and qwen-coin:latest.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Per-case local Ollama timeout in seconds",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    models = tuple(args.model) or DEFAULT_MODELS
    try:
        output = run_model_benchmarks(models, timeout_seconds=args.timeout)
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "error": type(exc).__name__, "message": str(exc)},
                indent=2,
            )
        )
        return 1

    print(json.dumps({"ok": True, **output}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
