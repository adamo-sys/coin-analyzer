#!/usr/bin/env python3
"""Report only final gap slots still lacking any accepted page candidate.

This is acquisition bookkeeping only. It does not fetch images, mutate source inventory,
or inspect retrieval scores.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / "final_gap_page_review.json"
OUTPUT = ROOT / "uncovered_final_gap_slots.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    review = _load(REVIEW)
    missing = review.get("missing") or []
    rows = [row for row in missing if isinstance(row, dict)]

    result = {
        "schema": "coin-analyzer-uncovered-final-gap-slots-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "items": rows,
        "summary": {"uncovered_slots": len(rows)},
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Uncovered final gap slots: {len(rows)}")
    for i, row in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] {row.get('case_id')}.{row.get('side')}")
    print(f"Wrote uncovered final gap report: {OUTPUT}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
