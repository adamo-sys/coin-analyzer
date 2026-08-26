#!/usr/bin/env python3
"""Export only actionable slots still lacking an accepted curated provider page.

Acquisition-only tooling. It reads the frozen unresolved queue plus the curated
page review and writes a narrower follow-up queue. It does not mutate the source
inventory, inspect retrieval results, download images, or alter benchmark cases.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_QUEUE = ROOT / "unresolved_source_queue.json"
DEFAULT_REVIEW = ROOT / "curated_provider_page_review.json"
DEFAULT_OUTPUT = ROOT / "remaining_curated_gap_queue.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _queue_items(payload: dict) -> list[dict]:
    for key in ("slots", "items", "queue", "actionable_slots"):
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
                if isinstance(slot, dict) and slot.get("status") in {"unresolved", "conflict"}:
                    rows.append({
                        "case_id": case_id,
                        "side": side,
                        "status": slot.get("status"),
                        "expected": expected,
                    })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    queue = _load(args.queue)
    review = _load(args.review)
    accepted = {
        (str(row.get("case_id")), str(row.get("side")))
        for row in review.get("accepted", [])
        if isinstance(row, dict)
    }

    remaining: list[dict] = []
    for row in _queue_items(queue):
        key = (str(row.get("case_id") or row.get("id")), str(row.get("side")))
        if key in accepted:
            continue
        remaining.append(row)

    artifact = {
        "schema": "coin-analyzer-remaining-curated-gap-queue-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "source_queue": args.queue.name,
        "curated_review": args.review.name,
        "items": remaining,
        "summary": {
            "original_actionable_slots": len(_queue_items(queue)),
            "slots_with_curated_page": len(accepted),
            "remaining_slots": len(remaining),
            "remaining_conflicts": sum(1 for row in remaining if row.get("status") == "conflict"),
        },
    }
    args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    s = artifact["summary"]
    print(f"Original actionable source slots: {s['original_actionable_slots']}")
    print(f"Slots with accepted curated page: {s['slots_with_curated_page']}")
    print(f"Remaining curated source gaps: {s['remaining_slots']}")
    print(f"Remaining conflict slots: {s['remaining_conflicts']}")
    print(f"Wrote remaining-gap queue: {args.output}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
