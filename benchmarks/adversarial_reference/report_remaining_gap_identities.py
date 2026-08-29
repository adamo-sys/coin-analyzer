#!/usr/bin/env python3
"""Print the exact remaining adversarial source gaps for targeted manual acquisition.

Reads remaining_curated_gap_queue.json and emits a compact, stable list of the
remaining case/side identities plus provider search hints. This is acquisition-only:
it does not mutate source_inventory_v1.json and never runs retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "remaining_curated_gap_queue.json"
OUTPUT = ROOT / "remaining_gap_identities.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _items(payload: dict) -> list[dict]:
    for key in ("slots", "items", "queue", "actionable_slots", "remaining"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    rows: list[dict] = []
    cases = payload.get("cases")
    if isinstance(cases, dict):
        for case_id, case in cases.items():
            if not isinstance(case, dict):
                continue
            expected = case.get("expected") or {}
            for side in ("query", "reference"):
                slot = case.get(side)
                if isinstance(slot, dict) and slot.get("status") in {"unresolved", "conflict", "gap"}:
                    rows.append({
                        "case_id": case_id,
                        "side": side,
                        "status": slot.get("status"),
                        "expected": expected,
                    })
    return rows


def _identity(expected: dict) -> str:
    country = str(expected.get("country") or "").strip()
    denomination = str(expected.get("denomination") or "").strip()
    year = str(expected.get("year") or "").strip()
    type_design = str(expected.get("type_design") or "").strip()
    return " ".join(part for part in (country, denomination, year, type_design) if part)


def main() -> int:
    payload = _load(QUEUE)
    items = _items(payload)
    rows = []
    for index, item in enumerate(items, start=1):
        expected = item.get("expected") or {}
        identity = _identity(expected)
        row = {
            "index": index,
            "case_id": str(item.get("case_id") or item.get("id") or "unknown"),
            "side": str(item.get("side") or "unknown"),
            "status": item.get("status"),
            "identity": identity,
            "expected": expected,
            "search_queries": [
                identity,
                f"{identity} Numista",
                f"{identity} NGC",
                f"{identity} PCGS",
                f"{identity} museum coin",
                f"{identity} auction archive",
            ],
        }
        rows.append(row)
        print(f"[{index}/{len(items)}] {row['case_id']}.{row['side']} | {identity} | status={row['status']}")

    artifact = {
        "schema": "coin-analyzer-remaining-gap-identities-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "remaining_slots": len(rows),
        "items": rows,
    }
    OUTPUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Remaining source gaps reported: {len(rows)}")
    print(f"Wrote gap identity report: {OUTPUT}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
