"""Benchmark-only candidate-resolution experiment over saved MiniCPM v2 output.

The frozen v2 expected identities are projected into a tiny in-memory catalogue,
then the model's per-side structured evidence is normalized and resolved against
that catalogue. This is an oracle-catalogue experiment: it measures whether a
bounded candidate layer can recover noisy visual evidence when the correct entry
is present. It does not measure candidate retrieval and must not be reported as
open-world recognition accuracy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

from .evidence_candidate_resolver import (
    CatalogueCandidate,
    normalize_evidence,
    resolve_candidates,
)

REQUIRED_FIELDS = ("country", "denomination", "year")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-candidate-resolution-benchmark")
    parser.add_argument("report", type=Path)
    parser.add_argument("--minimum-score", type=float, default=7.0)
    parser.add_argument("--minimum-margin", type=float, default=2.0)
    parser.add_argument("--json", type=Path)
    return parser


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.1f}%"


def _load_report(path: Path) -> Mapping[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("benchmark report must be a JSON object")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("benchmark report rows must be a non-empty list")
    return payload


def _catalogue(rows: Sequence[object]) -> tuple[CatalogueCandidate, ...]:
    candidates: list[CatalogueCandidate] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        case_id = raw.get("case_id")
        expected = raw.get("expected")
        if not isinstance(case_id, str) or not isinstance(expected, Mapping):
            continue
        required = [expected.get(field) for field in REQUIRED_FIELDS]
        if not all(isinstance(value, str) and value.strip() for value in required):
            continue
        type_design = expected.get("type_design")
        candidates.append(
            CatalogueCandidate(
                candidate_id=case_id,
                country=str(expected["country"]),
                denomination=str(expected["denomination"]),
                year=str(expected["year"]),
                type_design=str(type_design) if isinstance(type_design, str) and type_design.strip() else None,
                legends=(),
            )
        )
    return tuple(candidates)


def _side_evidence(row: Mapping[str, object]):
    side_results = row.get("side_results")
    if not isinstance(side_results, Mapping):
        return ()
    evidence = []
    for role in ("obverse", "reverse"):
        side = side_results.get(role)
        if not isinstance(side, Mapping) or side.get("ok") is not True:
            continue
        result = side.get("result")
        if isinstance(result, Mapping):
            evidence.append(normalize_evidence(result, source=role))
    return tuple(evidence)


def _baseline_correct(row: Mapping[str, object]) -> bool:
    if row.get("full_required_identity_exact") is True:
        return True
    return row.get("full_identity_exact") is True


def run_benchmark(
    report: Mapping[str, object],
    *,
    minimum_score: float,
    minimum_margin: float,
) -> dict[str, object]:
    raw_rows = report.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("benchmark report rows must be a list")
    candidates = _catalogue(raw_rows)
    if not candidates:
        raise ValueError("benchmark report did not yield catalogue candidates")

    rows: list[dict[str, object]] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            continue
        case_id = raw.get("case_id")
        if not isinstance(case_id, str):
            continue
        evidence = _side_evidence(raw)
        resolution = resolve_candidates(
            candidates,
            evidence,
            minimum_score=minimum_score,
            minimum_margin=minimum_margin,
        )
        accepted_id = resolution.accepted.candidate_id if resolution.accepted is not None else None
        accepted_correct = accepted_id == case_id
        ranked = [
            {
                "candidate_id": item.candidate.candidate_id,
                "score": item.score,
                "matched_fields": list(item.matched_fields),
                "mismatched_fields": list(item.mismatched_fields),
                "supporting_text": list(item.supporting_text),
            }
            for item in resolution.ranked[:5]
        ]
        best_score = resolution.ranked[0].score if resolution.ranked else None
        runner_up_score = resolution.ranked[1].score if len(resolution.ranked) > 1 else None
        score_margin = (
            best_score - runner_up_score
            if best_score is not None and runner_up_score is not None
            else None
        )
        rows.append(
            {
                "case_id": case_id,
                "baseline_full_required_exact": _baseline_correct(raw),
                "baseline_abstain": raw.get("abstain") is True,
                "baseline_identity": raw.get("identity"),
                "evidence_count": len(evidence),
                "candidate_accepted": accepted_id is not None,
                "accepted_candidate_id": accepted_id,
                "accepted_correct": accepted_correct,
                "resolver_abstain": resolution.abstain,
                "resolver_reason": resolution.reason,
                "best_score": best_score,
                "runner_up_score": runner_up_score,
                "score_margin": score_margin,
                "ranked_top5": ranked,
            }
        )

    total = len(rows)
    accepted = [row for row in rows if row["candidate_accepted"]]
    correct = [row for row in accepted if row["accepted_correct"]]
    unsafe = [row for row in accepted if not row["accepted_correct"]]
    baseline_correct = sum(bool(row["baseline_full_required_exact"]) for row in rows)
    recovered = sum(
        bool(row["accepted_correct"]) and not bool(row["baseline_full_required_exact"])
        for row in rows
    )
    regressed = sum(
        bool(row["baseline_full_required_exact"]) and not bool(row["accepted_correct"])
        for row in rows
    )
    metrics = {
        "total_cases": total,
        "catalogue_candidates": len(candidates),
        "baseline_full_required_exact_accuracy": _rate(baseline_correct, total),
        "candidate_resolved_accuracy": _rate(len(correct), total),
        "candidate_coverage": _rate(len(accepted), total),
        "candidate_selective_accuracy": _rate(len(correct), len(accepted)),
        "candidate_abstention_rate": _rate(total - len(accepted), total),
        "unsafe_wrong_resolution_rate": _rate(len(unsafe), total),
        "unsafe_wrong_resolutions": len(unsafe),
        "recovered_from_baseline": recovered,
        "regressed_from_baseline": regressed,
    }
    return {
        "schema": "coin-analyzer-candidate-resolution-benchmark-v1",
        "source_schema": report.get("schema"),
        "dataset_version": report.get("dataset_version"),
        "model": report.get("model"),
        "experiment": "oracle catalogue: correct v2 identity is guaranteed present; candidate retrieval is not evaluated",
        "minimum_score": minimum_score,
        "minimum_margin": minimum_margin,
        "metrics": metrics,
        "rows": rows,
    }


def _render(result: Mapping[str, object]) -> str:
    metrics = result["metrics"]
    lines = [
        f"Candidate-resolution benchmark: {result.get('dataset_version')}",
        f"Source model: {result.get('model')}",
        "Experiment: oracle catalogue (retrieval not evaluated)",
        f"Cases/candidates: {metrics['total_cases']}/{metrics['catalogue_candidates']}",
        f"Baseline full required identity: {_pct(metrics['baseline_full_required_exact_accuracy'])}",
        f"Candidate-resolved accuracy: {_pct(metrics['candidate_resolved_accuracy'])}",
        f"Candidate coverage: {_pct(metrics['candidate_coverage'])}",
        f"Candidate selective accuracy: {_pct(metrics['candidate_selective_accuracy'])}",
        f"Candidate abstention rate: {_pct(metrics['candidate_abstention_rate'])}",
        f"Unsafe wrong-resolution rate: {_pct(metrics['unsafe_wrong_resolution_rate'])}",
        f"Recovered from baseline: {metrics['recovered_from_baseline']}",
        f"Regressed from baseline: {metrics['regressed_from_baseline']}",
        "Case changes:",
    ]
    for row in result["rows"]:
        if row["baseline_full_required_exact"] == row["accepted_correct"]:
            continue
        lines.append(
            f"  {row['case_id']}: baseline_correct={row['baseline_full_required_exact']} -> "
            f"accepted={row['accepted_candidate_id']} correct={row['accepted_correct']} | "
            f"score={row['best_score']} margin={row['score_margin']} | {row['resolver_reason']}"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.minimum_margin < 0:
        raise SystemExit("--minimum-margin must be non-negative")
    report = _load_report(args.report)
    result = run_benchmark(
        report,
        minimum_score=float(args.minimum_score),
        minimum_margin=float(args.minimum_margin),
    )
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(_render(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
