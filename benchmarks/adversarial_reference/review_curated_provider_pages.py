#!/usr/bin/env python3
"""Review manually curated provider page candidates against the unresolved queue.

This script validates page-level identity coverage only. It does not download images,
mutate source_inventory_v1.json, or run retrieval scoring. Query/reference image
independence must still be established later at the asset level.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "unresolved_source_queue.json"
CURATED = ROOT / "curated_provider_page_candidates.json"
OUTPUT = ROOT / "curated_provider_page_review.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    queue = _load(QUEUE)
    curated = _load(CURATED)
    actionable = set()
    for key in ("slots", "items", "queue", "actionable_slots"):
        value = queue.get(key)
        if isinstance(value, list):
            for row in value:
                if isinstance(row, dict):
                    actionable.add((str(row.get("case_id") or row.get("id")), str(row.get("side"))))
            break
    if not actionable:
        cases = queue.get("cases") or {}
        if isinstance(cases, dict):
            for case_id, case in cases.items():
                if not isinstance(case, dict):
                    continue
                for side in ("query", "reference"):
                    slot = case.get(side)
                    if isinstance(slot, dict) and slot.get("status") in {"unresolved", "conflict"}:
                        actionable.add((case_id, side))

    accepted = []
    rejected = []
    seen = set()
    for row in curated.get("items", []):
        key = (str(row.get("case_id")), str(row.get("side")))
        if key not in actionable:
            rejected.append({**row, "reason": "slot not actionable"})
            continue
        if key in seen:
            rejected.append({**row, "reason": "duplicate curated slot"})
            continue
        if not str(row.get("url") or "").startswith(("http://", "https://")):
            rejected.append({**row, "reason": "invalid page URL"})
            continue
        seen.add(key)
        accepted.append({**row, "status": "page-confirmed-asset-pending"})

    result = {
        "schema": "coin-analyzer-curated-provider-page-review-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "accepted": accepted,
        "rejected": rejected,
        "summary": {
            "actionable_slots": len(actionable),
            "curated_rows": len(curated.get("items", [])),
            "accepted_page_candidates": len(accepted),
            "rejected_rows": len(rejected),
            "remaining_without_curated_page": max(0, len(actionable) - len(accepted)),
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    s = result["summary"]
    print(f"Actionable source slots: {s['actionable_slots']}")
    print(f"Curated provider page rows: {s['curated_rows']}")
    print(f"Accepted page candidates: {s['accepted_page_candidates']}")
    print(f"Rejected curated rows: {s['rejected_rows']}")
    print(f"Remaining slots without curated page: {s['remaining_without_curated_page']}")
    print(f"Wrote curated review: {OUTPUT}")
    print("Asset-level independence remains pending; no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
