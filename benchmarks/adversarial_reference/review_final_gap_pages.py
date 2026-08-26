#!/usr/bin/env python3
"""Review the hand-curated page candidates for the final adversarial source gaps.

Page identity only. This script does not download images, mutate source_inventory_v1.json,
or run retrieval scoring. Asset-level provenance, exact-year confirmation, and query/reference
independence remain mandatory before freeze.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GAPS = ROOT / "remaining_gap_identities.json"
CANDIDATES = ROOT / "final_gap_page_candidates.json"
OUTPUT = ROOT / "final_gap_page_review.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _gap_keys(payload: dict) -> set[tuple[str, str]]:
    rows = payload.get("items") or payload.get("gaps") or payload.get("slots") or []
    keys: set[tuple[str, str]] = set()
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                case_id = str(row.get("case_id") or row.get("id") or "")
                side = str(row.get("side") or "")
                if case_id and side:
                    keys.add((case_id, side))
    return keys


def main() -> int:
    gaps = _load(GAPS)
    candidates = _load(CANDIDATES)
    gap_keys = _gap_keys(gaps)
    accepted = []
    rejected = []
    covered: set[tuple[str, str]] = set()

    for row in candidates.get("items", []):
        if not isinstance(row, dict):
            continue
        key = (str(row.get("case_id") or ""), str(row.get("side") or ""))
        if key not in gap_keys:
            rejected.append({**row, "reason": "not in final gap queue"})
            continue
        url = str(row.get("url") or "")
        if not url.startswith(("http://", "https://")):
            rejected.append({**row, "reason": "invalid page URL"})
            continue
        accepted.append({**row, "review_status": "page-identity-accepted-asset-pending"})
        covered.add(key)

    missing = sorted(gap_keys - covered)
    result = {
        "schema": "coin-analyzer-final-gap-page-review-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "accepted": accepted,
        "rejected": rejected,
        "missing": [{"case_id": case_id, "side": side} for case_id, side in missing],
        "summary": {
            "final_gap_slots": len(gap_keys),
            "page_candidates": len(candidates.get("items", [])),
            "accepted_page_candidates": len(accepted),
            "rejected_page_candidates": len(rejected),
            "remaining_without_page_candidate": len(missing),
            "asset_level_pending": len(accepted),
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    s = result["summary"]
    print(f"Final gap slots: {s['final_gap_slots']}")
    print(f"Final page candidates: {s['page_candidates']}")
    print(f"Accepted final page candidates: {s['accepted_page_candidates']}")
    print(f"Rejected final page candidates: {s['rejected_page_candidates']}")
    print(f"Remaining without page candidate: {s['remaining_without_page_candidate']}")
    print(f"Accepted slots still pending asset-level proof: {s['asset_level_pending']}")
    print(f"Wrote final gap review: {OUTPUT}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
