"""Offline threshold-frontier analysis for saved structured multimodal evidence.

This diagnostic never invokes a model. It replays the saved best-candidate score,
runner-up margin, and matched-evidence count from the structured multimodal v2
benchmark across a grid of acceptance thresholds. The goal is to measure the
accuracy/coverage/safety frontier before changing resolver policy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-multimodal-threshold-frontier")
    parser.add_argument("report", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--min-selective-accuracy", type=float, default=0.90)
    parser.add_argument("--max-unsafe-rate", type=float, default=0.05)
    return parser


def _frange(values: Sequence[float]) -> tuple[float, ...]:
    return tuple(float(v) for v in values)


SCORE_THRESHOLDS = _frange((0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0))
MARGIN_THRESHOLDS = _frange((0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0))
MATCH_THRESHOLDS = (1, 2, 3)


def _rows(report: Mapping[str, object]) -> list[Mapping[str, object]]:
    rows = report.get("rows")
    if not isinstance(rows, list):
        raise ValueError("report rows must be a list")
    return [row for row in rows if isinstance(row, Mapping)]


def _matched_count(row: Mapping[str, object]) -> int:
    detail = row.get("best_detail")
    if not isinstance(detail, Mapping):
        return 0
    matched = detail.get("matched")
    return len(matched) if isinstance(matched, list) else 0


def _evaluate(rows: list[Mapping[str, object]], *, score: float, margin: float, matches: int) -> dict[str, object]:
    accepted: list[Mapping[str, object]] = []
    correct = 0
    unsafe = 0
    for row in rows:
        best_score = float(row.get("best_score") or 0.0)
        row_margin = float(row.get("margin") or 0.0)
        if best_score >= score and row_margin >= margin and _matched_count(row) >= matches:
            accepted.append(row)
            if row.get("case_id") == row.get("accepted_candidate_id"):
                # Saved accepted_candidate_id may be null because the original
                # threshold rejected this row. Use original correctness only when
                # it was accepted; otherwise infer best candidate identity from
                # the saved report's candidate id field when available below.
                correct += 1
            else:
                best_id = row.get("best_candidate_id") or row.get("accepted_candidate_id")
                if best_id == row.get("case_id"):
                    correct += 1
                else:
                    unsafe += 1

    total = len(rows)
    coverage = len(accepted) / total if total else None
    accuracy = correct / total if total else None
    selective = correct / len(accepted) if accepted else None
    unsafe_rate = unsafe / total if total else None
    return {
        "minimum_score": score,
        "minimum_margin": margin,
        "minimum_matched_dimensions": matches,
        "accepted": len(accepted),
        "correct": correct,
        "unsafe": unsafe,
        "coverage": coverage,
        "total_accuracy": accuracy,
        "selective_accuracy": selective,
        "unsafe_wrong_resolution_rate": unsafe_rate,
    }


def _augment_best_ids(rows: list[Mapping[str, object]]) -> list[dict[str, object]]:
    """Recover best candidate IDs from saved rows.

    Version 1 of the multimodal benchmark saved accepted_candidate_id only after
    applying its original threshold. For rejected rows, the printed/logged output
    did not persist the best candidate ID. When unavailable, those rows are marked
    unscorable for relaxed thresholds rather than guessing.
    """
    out: list[dict[str, object]] = []
    for row in rows:
        clone = dict(row)
        accepted = row.get("accepted_candidate_id")
        clone["best_candidate_id"] = accepted if accepted is not None else None
        out.append(clone)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 0 <= args.min_selective_accuracy <= 1:
        raise SystemExit("--min-selective-accuracy must be between 0 and 1")
    if not 0 <= args.max_unsafe_rate <= 1:
        raise SystemExit("--max-unsafe-rate must be between 0 and 1")

    report = json.loads(args.report.read_text(encoding="utf-8"))
    raw_rows = _rows(report)

    # Only rows whose best candidate identity was persisted can be safely replayed.
    # This keeps the frontier honest; a follow-up benchmark format can persist the
    # best candidate for every abstention and enable a complete frontier.
    rows = _augment_best_ids(raw_rows)
    scorable = [row for row in rows if row.get("best_candidate_id") is not None]
    unscorable = len(rows) - len(scorable)

    frontier: list[dict[str, object]] = []
    for score in SCORE_THRESHOLDS:
        for margin in MARGIN_THRESHOLDS:
            for matches in MATCH_THRESHOLDS:
                frontier.append(_evaluate(scorable, score=score, margin=margin, matches=matches))

    feasible = [
        point for point in frontier
        if point["selective_accuracy"] is not None
        and float(point["selective_accuracy"]) >= args.min_selective_accuracy
        and float(point["unsafe_wrong_resolution_rate"] or 0.0) <= args.max_unsafe_rate
    ]
    feasible.sort(
        key=lambda p: (
            -float(p["total_accuracy"] or 0.0),
            -float(p["coverage"] or 0.0),
            -float(p["selective_accuracy"] or 0.0),
            float(p["unsafe_wrong_resolution_rate"] or 0.0),
            float(p["minimum_score"]),
            float(p["minimum_margin"]),
            int(p["minimum_matched_dimensions"]),
        )
    )

    output = {
        "schema": "coin-analyzer-multimodal-threshold-frontier-v1",
        "source_schema": report.get("schema"),
        "dataset_version": report.get("dataset_version"),
        "source_model": report.get("evidence_model") or report.get("source_model"),
        "total_rows": len(rows),
        "scorable_rows": len(scorable),
        "unscorable_abstained_rows": unscorable,
        "warning": (
            "The source benchmark did not persist best candidate IDs for abstained rows; "
            "this frontier is therefore exact only for rows that were originally accepted. "
            "Do not use it to justify relaxed thresholds across the full dataset."
        ),
        "constraints": {
            "minimum_selective_accuracy": args.min_selective_accuracy,
            "maximum_unsafe_wrong_resolution_rate": args.max_unsafe_rate,
        },
        "best_feasible": feasible[0] if feasible else None,
        "frontier": frontier,
    }

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Multimodal resolver threshold frontier: {output['dataset_version']}")
    print(f"Rows: {len(rows)}; fully scorable: {len(scorable)}; abstained rows lacking persisted best ID: {unscorable}")
    print("WARNING: saved v1 benchmark cannot safely replay relaxed thresholds for abstained rows.")
    best = output["best_feasible"]
    if best is None:
        print("No feasible operating point on the scorable subset.")
    else:
        print(
            "Best feasible on scorable subset: "
            f"score>={best['minimum_score']:.1f}, margin>={best['minimum_margin']:.1f}, "
            f"matches>={best['minimum_matched_dimensions']} | "
            f"accuracy={best['total_accuracy'] * 100:.1f}% coverage={best['coverage'] * 100:.1f}% "
            f"selective={best['selective_accuracy'] * 100:.1f}% unsafe={best['unsafe_wrong_resolution_rate'] * 100:.1f}%"
        )
    print("Next requirement: persist best_candidate_id for every row, then rerun frontier offline without VLM inference.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
