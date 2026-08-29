#!/usr/bin/env python3
"""Audit combined page-level coverage across all adversarial source-curation passes.

This is a bookkeeping-only step. It combines the original curated-page review,
web-curated Canadian gap review, and final-gap review so stale per-pass queues do
not masquerade as unresolved work. It never downloads images, mutates
source_inventory_v1.json, or runs retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "unresolved_source_queue.json"
CURATED = ROOT / "curated_provider_page_review.json"
WEB = ROOT / "web_curated_gap_page_review.json"
FINAL = ROOT / "final_gap_page_review.json"
OUTPUT = ROOT / "combined_page_coverage_audit.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _actionable(payload: dict) -> set[tuple[str, str]]:
    rows = None
    for key in ("slots", "items", "queue", "actionable_slots"):
        value = payload.get(key)
        if isinstance(value, list):
            rows = value
            break
    keys: set[tuple[str, str]] = set()
    if rows is not None:
        for row in rows:
            if not isinstance(row, dict):
                continue
            case_id = str(row.get("case_id") or row.get("id") or "")
            side = str(row.get("side") or "")
            if case_id and side:
                keys.add((case_id, side))
        return keys

    cases = payload.get("cases") or {}
    if isinstance(cases, dict):
        for case_id, case in cases.items():
            if not isinstance(case, dict):
                continue
            for side in ("query", "reference"):
                slot = case.get(side)
                if isinstance(slot, dict) and slot.get("status") in {"unresolved", "conflict"}:
                    keys.add((str(case_id), side))
    return keys


def _accepted_keys(payload: dict) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for row in payload.get("accepted", []) or []:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or row.get("id") or "")
        side = str(row.get("side") or "")
        if case_id and side:
            keys.add((case_id, side))
    return keys


def main() -> int:
    actionable = _actionable(_load(QUEUE))
    curated = _accepted_keys(_load(CURATED))
    web = _accepted_keys(_load(WEB))
    final = _accepted_keys(_load(FINAL))
    covered = (curated | web | final) & actionable
    remaining = sorted(actionable - covered)

    result = {
        "schema": "coin-analyzer-combined-page-coverage-audit-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "actionable_slots": len(actionable),
        "accepted_by_pass": {
            "curated_provider": len(curated & actionable),
            "web_curated": len(web & actionable),
            "final_gap": len(final & actionable),
        },
        "covered_unique_slots": len(covered),
        "remaining_without_page_candidate": [
            {"case_id": case_id, "side": side} for case_id, side in remaining
        ],
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Actionable source slots: {len(actionable)}")
    print(f"Unique slots with accepted page candidate: {len(covered)}")
    print(f"Remaining without page candidate: {len(remaining)}")
    for idx, (case_id, side) in enumerate(remaining, start=1):
        print(f"[{idx}/{len(remaining)}] {case_id}.{side}")
    print(f"Wrote combined page coverage audit: {OUTPUT}")
    print("No images were downloaded, source_inventory_v1.json was not modified, and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
