#!/usr/bin/env python3
"""Prepare targeted acquisition metadata for the two remaining empty adversarial asset slots.

This is a bounded diagnostic/planning step. It reads the empty filtered slot report and emits
provider-specific acquisition hints for the known remaining cases without downloading assets,
mutating source_inventory_v1.json, or running retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "empty_filtered_asset_slots.json"
OUTPUT = ROOT / "target_empty_asset_slots.json"

TARGETS = {
    ("canada-10-cents-1955", "reference"): {
        "identity": "Canada 10 cents 1955",
        "preferred_provider": "Coins and Canada",
        "strategy": "inspect page HTML for coin-photo src/srcset or background-image URLs; reject UI assets",
        "notes": "Existing page candidate is identity-accepted; need a coin-specific asset distinct from frozen Wikimedia query source.",
    },
    ("switzerland-2-francs-1980", "reference"): {
        "identity": "Switzerland 2 francs 1980",
        "preferred_provider": "Numista or independent auction/archive page",
        "strategy": "extract coin-specific catalogue image; reject generic catalogue thumbnails and shared assets",
        "notes": "Existing page candidate is identity-accepted; require independent asset provenance from frozen query source.",
    },
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_empty(payload: dict):
    for key in ("empty_slots", "items", "slots", "missing"):
        rows = payload.get(key)
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    yield row
            return


def main() -> int:
    payload = _load(INPUT)
    rows = []
    unknown = []
    for row in _iter_empty(payload):
        case_id = str(row.get("case_id") or row.get("id") or "")
        side = str(row.get("side") or "")
        key = (case_id, side)
        target = TARGETS.get(key)
        if target is None:
            unknown.append({"case_id": case_id, "side": side})
            continue
        rows.append({
            "case_id": case_id,
            "side": side,
            **target,
            "status": "targeted-asset-acquisition-required",
        })

    result = {
        "schema": "coin-analyzer-target-empty-asset-slots-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "targets": rows,
        "unknown_empty_slots": unknown,
        "summary": {
            "targeted_slots": len(rows),
            "unknown_empty_slots": len(unknown),
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Targeted empty asset slots: {len(rows)}")
    for idx, row in enumerate(rows, 1):
        print(f"[{idx}/{len(rows)}] {row['case_id']}.{row['side']} | {row['preferred_provider']}")
        print(f"  strategy={row['strategy']}")
    print(f"Unknown empty slots: {len(unknown)}")
    print(f"Wrote targeted acquisition plan: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
