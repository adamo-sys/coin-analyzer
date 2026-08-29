#!/usr/bin/env python3
"""Curate strong Commons side candidates without retrieval scoring.

Consumes two_side_gap_commons_candidates.json and emits only candidates that meet
conservative lexical confidence rules. This remains scoring-blind: it does not
decode benchmark images or invoke the frozen ORB/HSV backend.

The purpose is to reduce manual review and avoid accepting weak candidates from
broad Commons search. Low-confidence roles remain unresolved explicitly.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "two_side_gap_commons_candidates.json"
OUTPUT = ROOT / "two_side_gap_commons_curated.json"

MIN_SCORE = 6.0
MIN_MARGIN = 1.5


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not INPUT.is_file():
        raise SystemExit(f"missing Commons candidate artifact: {INPUT}")

    payload = load(INPUT)
    rows = payload.get("rows") or payload.get("results") or payload.get("roles") or []
    if not isinstance(rows, list):
        raise SystemExit("Commons candidate artifact requires a list of role rows")

    curated = []
    accepted = 0
    unresolved = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        side = str(row.get("side") or row.get("source_group") or "")
        role = str(row.get("role") or row.get("coin_side") or "")
        candidates = row.get("candidates") if isinstance(row.get("candidates"), list) else []

        ranked = [c for c in candidates if isinstance(c, dict)]
        ranked.sort(key=lambda c: (-float(c.get("score") or 0.0), str(c.get("title") or c.get("asset_url") or "")))
        best = ranked[0] if ranked else None
        second_score = float(ranked[1].get("score") or 0.0) if len(ranked) > 1 else 0.0
        best_score = float(best.get("score") or 0.0) if best else 0.0
        margin = best_score - second_score if best else 0.0

        status = "unresolved"
        reason = "no-candidates"
        selected = None
        if best is not None:
            if best_score < MIN_SCORE:
                reason = f"best-score-below-{MIN_SCORE:.1f}"
            elif len(ranked) > 1 and margin < MIN_MARGIN:
                reason = f"margin-below-{MIN_MARGIN:.1f}"
            else:
                status = "provisionally-selected"
                reason = "lexical-gate-passed"
                selected = best

        if status == "provisionally-selected":
            accepted += 1
        else:
            unresolved += 1

        curated.append({
            "case_id": case_id,
            "side": side,
            "role": role,
            "status": status,
            "reason": reason,
            "best_score": best_score,
            "runner_up_score": second_score,
            "margin": margin,
            "selected": selected,
            "candidate_count": len(ranked),
        })

    artifact = {
        "schema": "coin-analyzer-two-side-gap-commons-curated-v1",
        "scoring_blind": True,
        "retrieval_scoring_run": False,
        "gates": {"min_score": MIN_SCORE, "min_margin": MIN_MARGIN},
        "rows": curated,
        "summary": {
            "roles_reviewed": len(curated),
            "provisionally_selected": accepted,
            "unresolved": unresolved,
        },
    }
    OUTPUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("Commons two-side candidate curation")
    print("Scoring blind: retrieval backend was NOT run.")
    print(f"Roles reviewed: {len(curated)}")
    print(f"Provisionally selected: {accepted}")
    print(f"Unresolved: {unresolved}")
    for row in curated:
        if row["status"] == "provisionally-selected":
            selected = row["selected"] or {}
            print(
                f"  + {row['case_id']} | {row['side']}.{row['role']} | "
                f"score={row['best_score']:.1f} margin={row['margin']:.1f} | "
                f"{selected.get('title') or selected.get('asset_url') or 'candidate'}"
            )
    print(f"Wrote curated candidates: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
