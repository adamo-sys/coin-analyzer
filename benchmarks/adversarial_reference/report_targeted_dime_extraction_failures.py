#!/usr/bin/env python3
"""Report targeted Canadian dime extraction failures without running retrieval scoring."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "targeted_unique_dime_asset_candidates.json"
OUTPUT = ROOT / "targeted_unique_dime_extraction_failures.json"


def main() -> int:
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    rows = payload.get("results") or []
    failures = []
    successes = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = {
            "case_id": row.get("case_id"),
            "side": row.get("side"),
            "status": row.get("status"),
            "source_page_url": row.get("source_page_url"),
            "final_page_url": row.get("final_page_url"),
            "error": row.get("error"),
            "candidate_count": len(row.get("candidates") or []),
        }
        if row.get("candidates"):
            successes.append(item)
        else:
            failures.append(item)

    result = {
        "schema": "coin-analyzer-targeted-dime-extraction-failures-v1",
        "failures": failures,
        "successes": successes,
        "summary": {"failures": len(failures), "successes": len(successes)},
        "inventory_modified": False,
        "retrieval_scoring_run": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Failures: {len(failures)}")
    for i, row in enumerate(failures, 1):
        print(f"[{i}/{len(failures)}] {row['case_id']}.{row['side']} | status={row['status']}")
        print(f"  page={row['source_page_url']}")
        print(f"  error={row['error']}")
    print(f"Successes: {len(successes)}")
    for i, row in enumerate(successes, 1):
        print(f"[{i}/{len(successes)}] {row['case_id']}.{row['side']} | candidates={row['candidate_count']} | page={row['source_page_url']}")
    print(f"Wrote report: {OUTPUT}")
    print("Frozen case set unchanged; source_inventory_v1.json unchanged; no retrieval scoring run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
