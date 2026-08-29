#!/usr/bin/env python3
"""Report exact query/reference sides missing from the pre-freeze similarity audit.

This is diagnostic bookkeeping only. It does not mutate benchmark inputs and does
not run retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "selected_asset_similarity_audit.json"
OUTPUT = ROOT / "similarity_coverage_gaps.json"


def main() -> int:
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    gaps = []
    for row in payload.get("rows", []):
        if not isinstance(row, dict) or row.get("status") != "not-compared":
            continue
        missing = [x for x in (row.get("missing") or []) if x in {"query", "reference"}]
        if not missing:
            continue
        gaps.append({"case_id": row.get("case_id"), "missing": missing})

    result = {
        "schema": "coin-analyzer-similarity-coverage-gaps-v1",
        "retrieval_scoring_run": False,
        "gaps": gaps,
        "summary": {
            "cases_with_gaps": len(gaps),
            "missing_query_sides": sum("query" in g["missing"] for g in gaps),
            "missing_reference_sides": sum("reference" in g["missing"] for g in gaps),
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    s = result["summary"]
    print(f"Cases with similarity coverage gaps: {s['cases_with_gaps']}")
    print(f"Missing query sides: {s['missing_query_sides']}")
    print(f"Missing reference sides: {s['missing_reference_sides']}")
    for i, gap in enumerate(gaps, 1):
        print(f"[{i}/{len(gaps)}] {gap['case_id']} | missing={','.join(gap['missing'])}")
    print(f"Wrote coverage gap report: {OUTPUT}")
    print("No retrieval scoring was run and no benchmark input was modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
