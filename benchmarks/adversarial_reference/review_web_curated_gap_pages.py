#!/usr/bin/env python3
"""Review direct web-curated page candidates against the remaining-gap queue.

Page-level identity coverage only. No image asset is accepted here, no inventory is
mutated, and retrieval scoring is never invoked. Asset-level provenance and
query/reference independence remain mandatory before freeze.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "remaining_curated_gap_queue.json"
CURATED = ROOT / "web_curated_gap_pages.json"
OUTPUT = ROOT / "web_curated_gap_page_review.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _queue_items(payload: dict) -> list[dict]:
    for key in ("slots", "items", "queue", "actionable_slots"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def main() -> int:
    queue = _load(QUEUE)
    curated = _load(CURATED)
    actionable = {
        (str(row.get("case_id") or row.get("id")), str(row.get("side")))
        for row in _queue_items(queue)
    }

    accepted = []
    rejected = []
    seen = set()
    for row in curated.get("items", []):
        key = (str(row.get("case_id")), str(row.get("side")))
        if key not in actionable:
            rejected.append({**row, "reason": "slot not in remaining-gap queue"})
            continue
        if key in seen:
            rejected.append({**row, "reason": "duplicate slot"})
            continue
        url = str(row.get("url") or "")
        if not url.startswith(("http://", "https://")):
            rejected.append({**row, "reason": "invalid URL"})
            continue
        if not str(row.get("identity_evidence") or "").strip():
            rejected.append({**row, "reason": "missing page-level identity evidence"})
            continue
        seen.add(key)
        accepted.append({**row, "status": "page-confirmed-asset-pending"})

    remaining = sorted(actionable - seen)
    result = {
        "schema": "coin-analyzer-web-curated-gap-page-review-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "accepted": accepted,
        "rejected": rejected,
        "remaining": [{"case_id": c, "side": s} for c, s in remaining],
        "summary": {
            "remaining_gap_slots_before": len(actionable),
            "curated_rows": len(curated.get("items", [])),
            "accepted_page_candidates": len(accepted),
            "rejected_rows": len(rejected),
            "remaining_gap_slots_after": len(remaining),
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    s = result["summary"]
    print(f"Remaining gap slots before web curation: {s['remaining_gap_slots_before']}")
    print(f"Web-curated page rows: {s['curated_rows']}")
    print(f"Accepted page candidates: {s['accepted_page_candidates']}")
    print(f"Rejected curated rows: {s['rejected_rows']}")
    print(f"Remaining gap slots after web curation: {s['remaining_gap_slots_after']}")
    print(f"Wrote web-curated review: {OUTPUT}")
    print("Asset-level independence remains pending; no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
