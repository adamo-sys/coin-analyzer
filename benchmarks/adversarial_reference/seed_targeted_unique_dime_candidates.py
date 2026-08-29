#!/usr/bin/env python3
"""Seed targeted pre-retrieval candidate URLs for unresolved Canadian dime slots.

This helper is intentionally bounded to the four unresolved slots reported by
report_unresolved_unique_asset_slots.py. It does not alter the frozen case set,
does not run retrieval scoring, and does not mutate source_inventory_v1.json.

The purpose is to add alternate image candidates from already-known identity pages
or independent public source pages so unique-byte selection can continue without
reusing the shared Numista miniature asset.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "final_asset_candidate_plan.json"
OUTPUT = ROOT / "targeted_unique_dime_candidate_plan.json"

TARGETS = {
    ("canada-10-cents-1954", "reference"),
    ("canada-10-cents-1955", "reference"),
    ("canada-10-cents-1956", "query"),
    ("canada-10-cents-1956", "reference"),
}

# Only public page candidates are recorded here. Direct image URLs are deliberately
# not guessed. A later extractor/downloader can resolve image assets from these pages.
PAGE_CANDIDATES = {
    ("canada-10-cents-1954", "reference"): [
        {
            "source_page_url": "https://coinsandcanada.com/coins-prices.php?coin=10-cents-1954&currency=CAD&years=10-cents-1953-1964",
            "provider": "Coins and Canada",
            "reason": "Independent Canadian numismatic identity page; alternate source needed because shared Numista miniature duplicated across dime slots.",
        }
    ],
    ("canada-10-cents-1955", "reference"): [
        {
            "source_page_url": "https://imaginaire.com/en/coins-and-paper-money/10-cent-1955-10-cent-au-1955-canadian-coins.html",
            "provider": "Imaginaire",
            "reason": "User-supplied manual image already imported and hash-verified; retain provenance page for assembly repair.",
        }
    ],
    ("canada-10-cents-1956", "query"): [
        {
            "source_page_url": "https://coinsandcanada.com/coins-prices.php?coin=10-cents-1956&currency=CAD&years=10-cents-1953-1964",
            "provider": "Coins and Canada",
            "reason": "Independent Canadian numismatic identity page; alternate source needed because shared Numista miniature duplicated across dime slots.",
        }
    ],
    ("canada-10-cents-1956", "reference"): [
        {
            "source_page_url": "https://en.numista.com/catalogue/pieces385.html",
            "provider": "Numista",
            "reason": "Identity page only; downstream extraction must reject the already-seen shared miniature hash and seek a different full-size image asset.",
        }
    ],
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    payload = _load(INPUT)
    rows = payload.get("slots") or []
    if not isinstance(rows, list):
        raise SystemExit("final_asset_candidate_plan.json does not contain a slots list")

    out = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("case_id") or ""), str(row.get("side") or ""))
        if key not in TARGETS:
            continue
        seen.add(key)
        out.append({
            "case_id": key[0],
            "side": key[1],
            "existing_mode": row.get("mode"),
            "existing_candidates": row.get("candidates") or [],
            "manual_asset": row.get("manual_asset"),
            "targeted_page_candidates": PAGE_CANDIDATES.get(key, []),
        })

    missing = sorted(TARGETS - seen)
    result = {
        "schema": "coin-analyzer-targeted-unique-dime-candidate-plan-v1",
        "frozen_case_set_modified": False,
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "targets": out,
        "missing_targets": [{"case_id": c, "side": s} for c, s in missing],
        "summary": {
            "target_count": len(TARGETS),
            "targets_found": len(out),
            "targets_missing": len(missing),
            "page_candidates_added": sum(len(x.get("targeted_page_candidates") or []) for x in out),
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    s = result["summary"]
    print(f"Targeted unresolved slots: {s['target_count']}")
    print(f"Targets found in final plan: {s['targets_found']}")
    print(f"Targets missing: {s['targets_missing']}")
    print(f"Targeted page candidates added: {s['page_candidates_added']}")
    print(f"Wrote targeted candidate plan: {OUTPUT}")
    print("Frozen case set unchanged; source_inventory_v1.json unchanged; no retrieval scoring run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
