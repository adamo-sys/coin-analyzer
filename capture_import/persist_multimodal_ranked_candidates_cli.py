"""Offline enrichment of structured multimodal benchmark artifacts.

Recomputes the deterministic candidate ranking from already-saved obverse/reverse
multimodal evidence, so no additional VLM inference is required. Persists the
best candidate ID and top ranked candidates for every row, including abstentions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

from .structured_multimodal_evidence_benchmark_cli import _candidate_score
from .visual_evaluation_harness import load_visual_manifest


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="coin-analyzer-persist-multimodal-ranked-candidates")
    p.add_argument("manifest", type=Path)
    p.add_argument("report", type=Path)
    p.add_argument("--json", type=Path, required=True)
    p.add_argument("--top-k", type=int, default=5)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.top_k < 2:
        raise SystemExit("--top-k must be at least 2")

    manifest = load_visual_manifest(args.manifest)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    rows = report.get("rows")
    if not isinstance(rows, list):
        raise ValueError("report rows must be a list")

    enriched: list[dict[str, object]] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        obverse = row.get("obverse") if isinstance(row.get("obverse"), Mapping) else {}
        reverse = row.get("reverse") if isinstance(row.get("reverse"), Mapping) else {}
        evidence = (obverse, reverse)
        ranked: list[tuple[float, str, Mapping[str, object]]] = []
        for candidate in manifest.cases:
            score, detail = _candidate_score(candidate, evidence)
            ranked.append((score, candidate.case_id, detail))
        ranked.sort(key=lambda item: (-item[0], item[1]))

        best_score, best_id, best_detail = ranked[0]
        runner_score = ranked[1][0] if len(ranked) > 1 else float("-inf")
        row["best_candidate_id"] = best_id
        row["best_score"] = best_score
        row["runner_up_score"] = runner_score
        row["margin"] = best_score - runner_score
        row["best_detail"] = dict(best_detail)
        row["ranked_candidates"] = [
            {
                "candidate_id": candidate_id,
                "score": score,
                "matched": list(detail.get("matched", [])),
            }
            for score, candidate_id, detail in ranked[: args.top_k]
        ]
        enriched.append(row)
        print(
            f"{row.get('case_id')} | best={best_id} | score={best_score:.2f} | "
            f"margin={row['margin']:.2f} | accepted={row.get('accepted_candidate_id')}",
            flush=True,
        )

    output = dict(report)
    output["schema"] = "coin-analyzer-structured-multimodal-evidence-benchmark-v2"
    output["rows"] = enriched
    output["ranking_enrichment"] = {
        "source_report": str(args.report),
        "top_k": args.top_k,
        "model_inference_performed": False,
        "note": "Candidate rankings recomputed offline from persisted multimodal evidence.",
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote enriched multimodal artifact: {args.json}")
    print(f"Rows with persisted best candidate IDs: {len(enriched)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
