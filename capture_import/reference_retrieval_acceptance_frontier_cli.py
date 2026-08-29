"""Sweep score/margin acceptance thresholds for saved reference retrieval results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

SCHEMA = "coin-analyzer-reference-image-retrieval-benchmark-v1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-reference-retrieval-acceptance-frontier")
    parser.add_argument("retrieval_json", type=Path)
    parser.add_argument("--json", type=Path)
    return parser


def _thresholds(values: list[float]) -> list[float]:
    if not values:
        return [0.0]
    # Include exact observed boundaries plus zero so the saved benchmark can be
    # replayed deterministically without rerunning image similarity.
    return sorted({0.0, *values})


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = json.loads(args.retrieval_json.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA:
        raise SystemExit(f"input schema must be {SCHEMA!r}")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("retrieval artifact requires non-empty rows")

    normalized: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise SystemExit(f"rows[{index}] must be an object")
        try:
            score = float(row["top1_score"])
            margin = float(row["margin"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SystemExit(f"rows[{index}] requires numeric top1_score and margin") from exc
        normalized.append({
            "case_id": str(row.get("case_id") or f"row-{index}"),
            "correct": bool(row.get("top1_correct")),
            "score": score,
            "margin": margin,
        })

    total = len(normalized)
    points: list[dict[str, object]] = []
    for score_min in _thresholds([float(row["score"]) for row in normalized]):
        for margin_min in _thresholds([float(row["margin"]) for row in normalized]):
            accepted = [row for row in normalized if float(row["score"]) >= score_min and float(row["margin"]) >= margin_min]
            correct = sum(bool(row["correct"]) for row in accepted)
            wrong = len(accepted) - correct
            coverage = len(accepted) / total
            selective = correct / len(accepted) if accepted else None
            points.append({
                "score_min": score_min,
                "margin_min": margin_min,
                "accepted": len(accepted),
                "correct": correct,
                "wrong": wrong,
                "coverage": coverage,
                "selective_accuracy": selective,
                "unsafe_rate": wrong / total,
            })

    # Pareto: retain points not dominated on coverage/selective accuracy/unsafe.
    pareto: list[dict[str, object]] = []
    for point in points:
        sel = point["selective_accuracy"]
        if sel is None:
            continue
        dominated = False
        for other in points:
            other_sel = other["selective_accuracy"]
            if other_sel is None or other is point:
                continue
            at_least = (
                float(other["coverage"]) >= float(point["coverage"])
                and float(other_sel) >= float(sel)
                and float(other["unsafe_rate"]) <= float(point["unsafe_rate"])
            )
            strictly = (
                float(other["coverage"]) > float(point["coverage"])
                or float(other_sel) > float(sel)
                or float(other["unsafe_rate"]) < float(point["unsafe_rate"])
            )
            if at_least and strictly:
                dominated = True
                break
        if not dominated:
            pareto.append(point)
    pareto.sort(key=lambda p: (-float(p["coverage"]), -float(p["selective_accuracy"]), float(p["unsafe_rate"]), float(p["score_min"]), float(p["margin_min"])))

    strict = [p for p in points if p["accepted"] and p["selective_accuracy"] == 1.0 and p["unsafe_rate"] == 0.0]
    strict.sort(key=lambda p: (-float(p["coverage"]), float(p["score_min"]), float(p["margin_min"])))
    best_strict = strict[0] if strict else None

    output = {
        "schema": "coin-analyzer-reference-retrieval-acceptance-frontier-v1",
        "source_schema": SCHEMA,
        "dataset_version": payload.get("dataset_version"),
        "reference_catalogue_version": payload.get("reference_catalogue_version"),
        "total_cases": total,
        "points": points,
        "pareto": pareto,
        "best_strict": best_strict,
        "warning": "Tiny pilots can make threshold frontiers look perfect; validate thresholds on a larger independent-reference set before production use.",
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("Reference retrieval acceptance frontier")
    print(f"Cases: {total}; threshold points: {len(points)}; Pareto points: {len(pareto)}")
    if best_strict:
        print(
            "Strict (100% selective, 0% unsafe): "
            f"score>={best_strict['score_min']:.4f}, margin>={best_strict['margin_min']:.4f} | "
            f"coverage={_pct(float(best_strict['coverage']))} | accepted={best_strict['accepted']}/{total}"
        )
    else:
        print("Strict (100% selective, 0% unsafe): none")
    print("WARNING: validate on a larger independent-reference set before treating this frontier as calibrated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
