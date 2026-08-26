#!/usr/bin/env python3
"""Report the unresolved slots from the unique final adversarial asset selection pass.

Diagnostic only. Reads unique_final_assets.json and prints unresolved slot identities plus
attempt diagnostics. It does not mutate source_inventory_v1.json and does not run retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "unique_final_assets.json"
OUTPUT = ROOT / "unresolved_unique_asset_slots.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    payload = _load(INPUT)
    rows = []
    for row in payload.get("results", []) or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "") == "selected":
            continue
        rows.append({
            "case_id": row.get("case_id"),
            "side": row.get("side"),
            "status": row.get("status"),
            "attempts": row.get("attempts") or [],
        })

    result = {
        "schema": "coin-analyzer-unresolved-unique-asset-slots-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "unresolved": rows,
        "summary": {"unresolved_slots": len(rows)},
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Unresolved unique asset slots: {len(rows)}")
    for idx, row in enumerate(rows, 1):
        print(f"[{idx}/{len(rows)}] {row.get('case_id')}.{row.get('side')} | status={row.get('status')}")
        attempts = row.get("attempts") or []
        print(f"  attempts={len(attempts)}")
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            print(
                "  - "
                f"rank={attempt.get('rank')} status={attempt.get('status')} "
                f"sha256={attempt.get('sha256')} url={attempt.get('url')}"
            )
    print(f"Wrote unresolved-slot report: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
