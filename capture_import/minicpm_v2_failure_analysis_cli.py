"""Analyze a saved MiniCPM two-side Benchmark v2 report.

This is diagnostic-only. It classifies benchmark outcomes without changing
recognition, merge, UI, persistence, or production behavior.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

REQUIRED_FIELDS = ("country", "denomination", "year")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-minicpm-v2-failure-analysis")
    parser.add_argument("report", type=Path)
    parser.add_argument("--json", type=Path)
    return parser


def _classify(row: Mapping[str, object]) -> list[str]:
    if row.get("infrastructure_failure") is True:
        return ["infrastructure_failure"]
    if row.get("model_output_failure") is True:
        return ["model_output_failure"]
    if row.get("full_required_identity_exact") is True:
        return ["correct_full_identity"]

    exact = row.get("exact") if isinstance(row.get("exact"), Mapping) else {}
    identity = row.get("identity") if isinstance(row.get("identity"), Mapping) else {}
    classes: list[str] = []

    if row.get("abstain") is True:
        classes.append("safe_abstention")
    for field in REQUIRED_FIELDS:
        if not bool(exact.get(field)):
            classes.append(f"wrong_or_missing_{field}")
    emitted = [identity.get(field) for field in REQUIRED_FIELDS]
    wrong_emitted = any(value is not None and not bool(exact.get(field)) for field, value in zip(REQUIRED_FIELDS, emitted))
    if row.get("abstain") is not True and wrong_emitted:
        classes.append("unsafe_incorrect_resolution")
    if row.get("abstain") is not True and sum(bool(exact.get(field)) for field in REQUIRED_FIELDS) == 0:
        classes.append("catastrophic_hallucination")
    return classes or ["incomplete_identity"]


def analyze(report: Mapping[str, object]) -> dict[str, object]:
    rows = report.get("rows")
    if not isinstance(rows, list):
        raise ValueError("report rows must be a list")
    counts: Counter[str] = Counter()
    cases: list[dict[str, object]] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        classes = _classify(raw)
        counts.update(classes)
        cases.append({
            "case_id": raw.get("case_id"),
            "classes": classes,
            "abstain": raw.get("abstain"),
            "expected": raw.get("expected"),
            "identity": raw.get("identity"),
            "exact": raw.get("exact"),
            "side_failure_classes": raw.get("side_failure_classes"),
            "conflicts": raw.get("conflicts"),
            "rejected_weaker_evidence": raw.get("rejected_weaker_evidence"),
        })
    return {
        "schema": "coin-analyzer-minicpm-v2-failure-analysis-v1",
        "source_schema": report.get("schema"),
        "dataset_version": report.get("dataset_version"),
        "model": report.get("model"),
        "case_count": len(cases),
        "class_counts": dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))),
        "cases": cases,
    }


def _render(analysis: Mapping[str, object]) -> str:
    lines = [
        f"MiniCPM v2 failure analysis: {analysis.get('dataset_version')}",
        f"Model: {analysis.get('model')}",
        f"Cases: {analysis.get('case_count')}",
        "Failure/outcome classes:",
    ]
    counts = analysis.get("class_counts")
    if isinstance(counts, Mapping):
        for name, count in counts.items():
            lines.append(f"  {name}: {count}")
    lines.append("Case diagnostics:")
    cases = analysis.get("cases")
    if isinstance(cases, list):
        for case in cases:
            if not isinstance(case, Mapping):
                continue
            classes = case.get("classes") or []
            if classes == ["correct_full_identity"]:
                continue
            identity = case.get("identity") if isinstance(case.get("identity"), Mapping) else {}
            lines.append(
                f"  {case.get('case_id')}: {', '.join(str(x) for x in classes)} | "
                f"{identity.get('country')} / {identity.get('denomination')} / {identity.get('year')}"
            )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    analysis = analyze(report)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(_render(analysis), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
