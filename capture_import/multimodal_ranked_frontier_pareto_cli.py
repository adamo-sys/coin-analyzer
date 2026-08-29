"""Report useful Pareto operating points from a ranked multimodal threshold frontier.

Offline diagnostic only: no VLM inference and no production resolver changes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="coin-analyzer-multimodal-ranked-frontier-pareto")
    p.add_argument("frontier_report", type=Path)
    p.add_argument("--json", type=Path)
    return p


def _points(report: Mapping[str, object]) -> list[dict[str, object]]:
    raw = report.get("frontier")
    if not isinstance(raw, list):
        raise ValueError("frontier report must contain a frontier list")
    return [dict(x) for x in raw if isinstance(x, Mapping)]


def _dominates(a: Mapping[str, object], b: Mapping[str, object]) -> bool:
    aa = float(a.get("total_accuracy") or 0.0)
    ac = float(a.get("coverage") or 0.0)
    ass = float(a.get("selective_accuracy") or 0.0)
    au = float(a.get("unsafe_wrong_resolution_rate") or 0.0)
    ba = float(b.get("total_accuracy") or 0.0)
    bc = float(b.get("coverage") or 0.0)
    bss = float(b.get("selective_accuracy") or 0.0)
    bu = float(b.get("unsafe_wrong_resolution_rate") or 0.0)
    no_worse = aa >= ba and ac >= bc and ass >= bss and au <= bu
    strictly = aa > ba or ac > bc or ass > bss or au < bu
    return no_worse and strictly


def _pareto(points: list[dict[str, object]]) -> list[dict[str, object]]:
    out=[]
    for p in points:
        if p.get("selective_accuracy") is None:
            continue
        if not any(_dominates(q,p) for q in points if q is not p and q.get("selective_accuracy") is not None):
            out.append(p)
    out.sort(key=lambda p:(-float(p.get("total_accuracy") or 0),-float(p.get("coverage") or 0),float(p.get("unsafe_wrong_resolution_rate") or 0),-float(p.get("selective_accuracy") or 0)))
    return out


def _best(points: list[dict[str, object]], *, min_selective: float, max_unsafe: float) -> dict[str, object] | None:
    feasible=[p for p in points if p.get("selective_accuracy") is not None and float(p.get("selective_accuracy") or 0)>=min_selective and float(p.get("unsafe_wrong_resolution_rate") or 0)<=max_unsafe]
    feasible.sort(key=lambda p:(-float(p.get("total_accuracy") or 0),-float(p.get("coverage") or 0),-float(p.get("selective_accuracy") or 0),float(p.get("unsafe_wrong_resolution_rate") or 0),float(p.get("minimum_score") or 0),float(p.get("minimum_margin") or 0),int(p.get("minimum_matched_dimensions") or 0)))
    return feasible[0] if feasible else None


def _fmt(p: Mapping[str, object] | None) -> str:
    if p is None:
        return "none"
    return (
        f"score>={float(p['minimum_score']):.1f}, margin>={float(p['minimum_margin']):.1f}, "
        f"matches>={int(p['minimum_matched_dimensions'])} | "
        f"accuracy={float(p['total_accuracy'])*100:.1f}% coverage={float(p['coverage'])*100:.1f}% "
        f"selective={float(p['selective_accuracy'])*100:.1f}% unsafe={float(p['unsafe_wrong_resolution_rate'])*100:.1f}%"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args=build_parser().parse_args(argv)
    report=json.loads(args.frontier_report.read_text(encoding="utf-8"))
    points=_points(report)
    pareto=_pareto(points)
    tiers={
        "strict_zero_unsafe_100_selective": _best(points,min_selective=1.0,max_unsafe=0.0),
        "zero_unsafe_95_selective": _best(points,min_selective=0.95,max_unsafe=0.0),
        "zero_unsafe_90_selective": _best(points,min_selective=0.90,max_unsafe=0.0),
        "near_safe_95_selective_5_unsafe": _best(points,min_selective=0.95,max_unsafe=0.05),
        "near_safe_90_selective_5_unsafe": _best(points,min_selective=0.90,max_unsafe=0.05),
    }
    output={"schema":"coin-analyzer-multimodal-ranked-frontier-pareto-v1","source_schema":report.get("schema"),"dataset_version":report.get("dataset_version"),"pareto_count":len(pareto),"tiers":tiers,"pareto":pareto}
    if args.json is not None:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"Ranked multimodal frontier Pareto report: {output['dataset_version']}")
    print(f"Pareto points: {len(pareto)}")
    print(f"Strict (100% selective, 0% unsafe): {_fmt(tiers['strict_zero_unsafe_100_selective'])}")
    print(f"Safe (>=95% selective, 0% unsafe): {_fmt(tiers['zero_unsafe_95_selective'])}")
    print(f"Safe (>=90% selective, 0% unsafe): {_fmt(tiers['zero_unsafe_90_selective'])}")
    print(f"Near-safe (>=95% selective, <=5% unsafe): {_fmt(tiers['near_safe_95_selective_5_unsafe'])}")
    print(f"Near-safe (>=90% selective, <=5% unsafe): {_fmt(tiers['near_safe_90_selective_5_unsafe'])}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
