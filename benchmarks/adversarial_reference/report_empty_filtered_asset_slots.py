#!/usr/bin/env python3
"""Report adversarial source slots left without candidates after provider-artifact filtering.

Diagnostic only. Does not mutate source_inventory_v1.json and does not run retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "filtered_ranked_asset_candidates.json"
OUTPUT = ROOT / "empty_filtered_asset_slots.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_slots(payload: dict):
    for key in ("slots", "items", "ranked", "results"):
        rows = payload.get(key)
        if isinstance(rows, list):
            yield from rows
            return
    cases = payload.get("cases")
    if isinstance(cases, dict):
        for case_id, case in cases.items():
            if not isinstance(case, dict):
                continue
            for side in ("query", "reference"):
                slot = case.get(side)
                if isinstance(slot, dict):
                    yield {"case_id": case_id, "side": side, **slot}


def _candidate_count(row: dict) -> int:
    for key in ("candidates", "ranked_candidates", "top_candidates", "assets"):
        value = row.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


def main() -> int:
    payload = _load(INPUT)
    empty = []
    total = 0
    for row in _iter_slots(payload):
        total += 1
        if _candidate_count(row) == 0:
            empty.append({
                "case_id": str(row.get("case_id") or row.get("id") or ""),
                "side": str(row.get("side") or ""),
                "source_page_url": row.get("source_page_url") or row.get("page_url") or row.get("url"),
                "reason": row.get("empty_reason") or row.get("status") or "no candidates after filtering",
            })

    result = {
        "schema": "coin-analyzer-empty-filtered-asset-slots-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "empty_slots": empty,
        "summary": {"slots_seen": total, "empty_slots": len(empty)},
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Slots seen: {total}")
    print(f"Empty slots after filter: {len(empty)}")
    for idx, row in enumerate(empty, 1):
        print(f"[{idx}/{len(empty)}] {row['case_id']}.{row['side']} | page={row.get('source_page_url')} | reason={row.get('reason')}")
    print(f"Wrote empty-slot report: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
