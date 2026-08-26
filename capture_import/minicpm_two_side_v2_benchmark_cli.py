"""Benchmark-only MiniCPM two-side Benchmark v2 runner.

Runs the side-aware MiniCPM evidence extractor independently on obverse/reverse,
merges evidence deterministically, and scores required identity fields against the
frozen visual Benchmark v2 manifest. This remains outside production OCR, UI,
review, persistence, and default recognition composition.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
from time import perf_counter
from typing import Mapping, Sequence

from .minicpm_structured_visual_probe_cli import DEFAULT_MODEL, DEFAULT_URL, _probe
from .minicpm_two_side_evidence_probe_cli import _merge_side_results
from .visual_evaluation_harness import load_visual_manifest


REQUIRED_FIELDS = ("country", "denomination", "year")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-minicpm-two-side-v2")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--json", type=Path)
    return parser


def _norm(value: object) -> str:
    return " ".join(str(value).strip().casefold().split())


def _canonical(field: str, value: object) -> str:
    text = _norm(value)
    if field == "denomination":
        text = text.replace("cents", "cent")
        text = text.replace("francs", "franc")
        text = text.replace("rupees", "rupee")
        text = text.replace("pesos", "peso")
    return text


def _rate(n: int, d: int) -> float | None:
    return None if d == 0 else n / d


def _latency(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean_seconds": None, "median_seconds": None, "p95_seconds": None}
    ordered = sorted(values)
    return {
        "mean_seconds": statistics.fmean(ordered),
        "median_seconds": statistics.median(ordered),
        "p95_seconds": ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)],
    }


def _select_cases(manifest, case_ids: Sequence[str] | None):
    if not case_ids:
        return manifest.cases
    requested = list(dict.fromkeys(case_ids))
    by_id = {case.case_id: case for case in manifest.cases}
    missing = [case_id for case_id in requested if case_id not in by_id]
    if missing:
        available = ", ".join(by_id)
        raise SystemExit(f"unknown --case-id(s): {', '.join(missing)}; available: {available}")
    return tuple(by_id[case_id] for case_id in requested)


def _case_row(case, *, model: str, url: str, timeout: float) -> dict[str, object]:
    started = perf_counter()
    common = {"model": model, "url": url, "timeout": timeout}
    obverse = _probe(case, role="obverse", **common)
    reverse = _probe(case, role="reverse", **common)
    merged = _merge_side_results(obverse, reverse)
    identity = merged.get("identity") if isinstance(merged, Mapping) else None
    identity = identity if isinstance(identity, Mapping) else {}
    infrastructure_failure = obverse.get("ok") is not True or reverse.get("ok") is not True
    abstain = bool(merged.get("abstain")) if not infrastructure_failure else False

    exact = {}
    canonical = {}
    for field in REQUIRED_FIELDS:
        predicted = identity.get(field)
        expected = case.expected[field]
        exact[field] = predicted is not None and _norm(predicted) == _norm(expected)
        canonical[field] = predicted is not None and _canonical(field, predicted) == _canonical(field, expected)

    return {
        "case_id": case.case_id,
        "expected": dict(case.expected),
        "identity_certain": case.identity_certain,
        "difficulty": list(case.difficulty),
        "model": model,
        "infrastructure_failure": infrastructure_failure,
        "abstain": abstain,
        "identity": {field: identity.get(field) for field in (*REQUIRED_FIELDS, "type_design")},
        "exact": exact,
        "canonical": canonical,
        "full_identity_exact": all(exact.values()) and not abstain and not infrastructure_failure,
        "full_identity_canonical": all(canonical.values()) and not abstain and not infrastructure_failure,
        "latency_seconds": max(0.0, perf_counter() - started),
        "side_latency_seconds": {
            "obverse": obverse.get("latency_seconds"),
            "reverse": reverse.get("latency_seconds"),
        },
        "provenance": merged.get("provenance"),
        "conflicts": merged.get("conflicts"),
        "rejected_weaker_evidence": merged.get("rejected_weaker_evidence"),
        "side_results": {"obverse": obverse, "reverse": reverse},
    }


def _metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    scored = [row for row in rows if row.get("identity_certain") is True]
    noninfra = [row for row in scored if row.get("infrastructure_failure") is not True]
    supplied = [row for row in noninfra if row.get("abstain") is not True]
    exact_counts = {
        field: sum(bool(row.get("exact", {}).get(field)) for row in scored)
        for field in REQUIRED_FIELDS
    }
    canonical_counts = {
        field: sum(bool(row.get("canonical", {}).get(field)) for row in scored)
        for field in REQUIRED_FIELDS
    }
    latency_values = [float(row["latency_seconds"]) for row in rows]
    return {
        "total_cases": len(rows),
        "certain_scored_cases": len(scored),
        "infrastructure_failures": sum(row.get("infrastructure_failure") is True for row in rows),
        "infrastructure_failure_rate": _rate(sum(row.get("infrastructure_failure") is True for row in rows), len(rows)),
        "abstentions": sum(row.get("abstain") is True for row in noninfra),
        "abstention_rate_noninfra": _rate(sum(row.get("abstain") is True for row in noninfra), len(noninfra)),
        "coverage_noninfra": _rate(len(supplied), len(noninfra)),
        "exact_accuracy": {field: _rate(exact_counts[field], len(scored)) for field in REQUIRED_FIELDS},
        "canonical_accuracy": {field: _rate(canonical_counts[field], len(scored)) for field in REQUIRED_FIELDS},
        "full_identity_exact_accuracy": _rate(sum(row.get("full_identity_exact") is True for row in scored), len(scored)),
        "full_identity_canonical_accuracy": _rate(sum(row.get("full_identity_canonical") is True for row in scored), len(scored)),
        "selective_full_identity_exact_accuracy": _rate(sum(row.get("full_identity_exact") is True for row in supplied), len(supplied)),
        "selective_full_identity_canonical_accuracy": _rate(sum(row.get("full_identity_canonical") is True for row in supplied), len(supplied)),
        "latency": _latency(latency_values),
    }


def _pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.1f}%"


def _render(report: Mapping[str, object]) -> str:
    m = report["metrics"]
    exact = m["exact_accuracy"]
    canon = m["canonical_accuracy"]
    latency = m["latency"]
    lines = [
        f"MiniCPM two-side visual benchmark: {report['dataset_version']}",
        f"Model: {report['model']}",
        f"Cases: {m['total_cases']}",
        f"Infrastructure failures: {m['infrastructure_failures']} ({_pct(m['infrastructure_failure_rate'])})",
        f"Abstention rate (non-infra): {_pct(m['abstention_rate_noninfra'])}",
        f"Coverage (non-infra): {_pct(m['coverage_noninfra'])}",
        f"Exact country accuracy: {_pct(exact['country'])}",
        f"Exact denomination accuracy: {_pct(exact['denomination'])}",
        f"Exact year accuracy: {_pct(exact['year'])}",
        f"Exact full required identity: {_pct(m['full_identity_exact_accuracy'])}",
        f"Canonical country accuracy: {_pct(canon['country'])}",
        f"Canonical denomination accuracy: {_pct(canon['denomination'])}",
        f"Canonical year accuracy: {_pct(canon['year'])}",
        f"Canonical full required identity: {_pct(m['full_identity_canonical_accuracy'])}",
        f"Selective exact full identity: {_pct(m['selective_full_identity_exact_accuracy'])}",
        f"Latency mean/median/p95: {latency['mean_seconds']:.3f}s / {latency['median_seconds']:.3f}s / {latency['p95_seconds']:.3f}s",
    ]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    manifest = load_visual_manifest(args.manifest)
    cases = _select_cases(manifest, args.case_ids)
    model = str(args.model).strip()
    url = str(args.url).strip()
    rows: list[dict[str, object]] = []
    for case in cases:
        row = _case_row(case, model=model, url=url, timeout=float(args.timeout))
        rows.append(row)
        identity = row["identity"]
        print(
            f"{case.case_id} | infra={row['infrastructure_failure']} | abstain={row['abstain']} | "
            f"{identity.get('country')} / {identity.get('denomination')} / {identity.get('year')} | "
            f"{row['latency_seconds']:.3f}s",
            flush=True,
        )
    report = {
        "schema": "coin-analyzer-minicpm-two-side-v2-benchmark-v1",
        "dataset_version": manifest.version,
        "model": model,
        "rows": rows,
        "metrics": _metrics(rows),
    }
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(_render(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
