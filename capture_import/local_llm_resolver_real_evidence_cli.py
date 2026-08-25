"""Run the local resolver against evidence captured by the real OCR benchmark."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from .local_llm_resolver import LocalLLMResolver, ResolverEvidence
from .local_llm_resolver_benchmark import ResolverBenchmarkCase, run_local_resolver_benchmark
from .ollama_local_resolver_runtime import OllamaLocalResolverRuntime

_REPORT_SCHEMA = "coin-analyzer-ocr-evaluation-report"
_REQUIRED_FIELDS = ("country", "denomination", "year")


def _nonempty_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _evidence_from_row(row: Mapping[str, object]) -> ResolverEvidence:
    observations = row.get("raw_observations", [])
    candidates = row.get("raw_candidates", [])

    ocr_text: list[str] = []
    if isinstance(observations, list):
        for item in observations:
            if isinstance(item, Mapping):
                text = _nonempty_text(item.get("raw_text"))
                if text is not None:
                    ocr_text.append(text)

    by_field: dict[str, list[str]] = {field: [] for field in _REQUIRED_FIELDS}
    if isinstance(candidates, list):
        for item in candidates:
            if not isinstance(item, Mapping):
                continue
            field = item.get("field_name")
            value = _nonempty_text(item.get("normalized_value"))
            if field in by_field and value is not None:
                by_field[str(field)].append(value)

    return ResolverEvidence(
        ocr_text=_unique(ocr_text),
        candidate_countries=_unique(by_field["country"]),
        candidate_denominations=_unique(by_field["denomination"]),
        candidate_years=_unique(by_field["year"]),
    )


def cases_from_evaluation_report(report: Mapping[str, object]) -> tuple[ResolverBenchmarkCase, ...]:
    if report.get("schema") != _REPORT_SCHEMA:
        raise ValueError(f"evaluation report schema must be {_REPORT_SCHEMA!r}")
    raw_cases = report.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("evaluation report cases must be a list")

    cases: list[ResolverBenchmarkCase] = []
    for index, row in enumerate(raw_cases):
        if not isinstance(row, Mapping):
            raise ValueError(f"cases[{index}] must be an object")
        if row.get("ocr_evaluated") is not True:
            continue
        case_id = _nonempty_text(row.get("case_id"))
        expected = row.get("expected")
        certain = row.get("identity_certain")
        if case_id is None or not isinstance(expected, Mapping) or not isinstance(certain, bool):
            raise ValueError(f"cases[{index}] is missing benchmark identity metadata")
        required_expected: dict[str, str] = {}
        for field in _REQUIRED_FIELDS:
            value = _nonempty_text(expected.get(field))
            if value is None:
                raise ValueError(f"cases[{index}].expected.{field} must be non-empty")
            required_expected[field] = value
        cases.append(
            ResolverBenchmarkCase(
                case_id=case_id,
                evidence=_evidence_from_row(row),
                expected=required_expected,
                identity_certain=certain,
            )
        )
    return tuple(cases)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve real OCR benchmark evidence from an existing evaluation report."
    )
    parser.add_argument("report", type=Path, help="JSON report produced by capture_import.evaluation_cli")
    parser.add_argument("--model", default="qwen3:8b", help="Local Ollama model tag")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-call Ollama timeout")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        if not isinstance(report, Mapping):
            raise ValueError("evaluation report root must be a JSON object")
        cases = cases_from_evaluation_report(report)
        resolver = LocalLLMResolver(
            OllamaLocalResolverRuntime(model=args.model, timeout_seconds=args.timeout),
            enabled=True,
        )
        result = run_local_resolver_benchmark(cases, resolver=resolver)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}, indent=2))
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "schema": "coin-analyzer-local-resolver-real-evidence-v1",
                "source_dataset_version": report.get("dataset_version"),
                "model": args.model,
                "benchmark": result,
            },
            indent=2,
            default=lambda value: value.__dict__ if hasattr(value, "__dict__") else {
                "country": value.country,
                "denomination": value.denomination,
                "year": value.year,
                "candidate_id": value.candidate_id,
                "confidence": value.confidence,
                "reason": value.reason,
                "abstain": value.abstain,
            },
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
