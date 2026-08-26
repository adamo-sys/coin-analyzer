#!/usr/bin/env python3
"""Assemble the final pre-retrieval adversarial asset candidate plan.

Combines the filtered ranked shortlist for the 23 automatically covered slots,
the targeted Swiss 2 francs 1980 candidates, and the manually imported Canada
10 cents 1955 reference asset. This is bookkeeping only: no retrieval scoring is
run and source_inventory_v1.json is not modified.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILTERED = ROOT / "filtered_ranked_asset_candidates.json"
TARGETED = ROOT / "targeted_empty_asset_candidates.json"
MANUAL = ROOT / "canada_10_cents_1955_reference_manual_asset.json"
OUTPUT = ROOT / "final_asset_candidate_plan.json"

MANUAL_KEY = ("canada-10-cents-1955", "reference")
TARGETED_KEY = ("switzerland-2-francs-1980", "reference")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    filtered = _load(FILTERED)
    targeted = _load(TARGETED)
    manual = _load(MANUAL)

    slots: dict[tuple[str, str], dict] = {}

    for row in filtered.get("slots", []):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        side = str(row.get("side") or "")
        if not case_id or not side:
            continue
        candidates = [c for c in (row.get("candidates") or []) if isinstance(c, dict)]
        slots[(case_id, side)] = {
            "case_id": case_id,
            "side": side,
            "mode": "download-candidate",
            "candidates": candidates,
            "source": "filtered-ranked-shortlist",
        }

    # Replace the Swiss empty slot with the provider-targeted candidates.
    for row in targeted.get("results", []):
        if not isinstance(row, dict):
            continue
        key = (str(row.get("case_id") or ""), str(row.get("side") or ""))
        if key != TARGETED_KEY:
            continue
        candidates = [c for c in (row.get("candidates") or []) if isinstance(c, dict)]
        slots[key] = {
            "case_id": key[0],
            "side": key[1],
            "mode": "download-candidate",
            "candidates": candidates,
            "source": "targeted-empty-slot-extractor",
            "page_url": row.get("page_url"),
        }

    # Replace the blocked Canada dime slot with the exact manual asset record.
    manual_key = (str(manual.get("case_id") or ""), str(manual.get("side") or ""))
    if manual_key != MANUAL_KEY:
        raise SystemExit(f"Unexpected manual asset identity: {manual_key}")
    manual_path = ROOT / str(manual.get("local_path") or "")
    if not manual_path.is_file():
        raise SystemExit(f"Manual asset missing: {manual_path}")
    slots[MANUAL_KEY] = {
        "case_id": MANUAL_KEY[0],
        "side": MANUAL_KEY[1],
        "mode": "manual-local-asset",
        "local_path": str(manual_path),
        "sha256": manual.get("sha256"),
        "bytes": manual.get("bytes"),
        "source_page_url": manual.get("source_page_url"),
        "provider": manual.get("provider"),
        "source": "manual-import",
    }

    rows = [slots[key] for key in sorted(slots)]
    empty = [
        {"case_id": r["case_id"], "side": r["side"]}
        for r in rows
        if r["mode"] == "download-candidate" and not r.get("candidates")
    ]

    result = {
        "schema": "coin-analyzer-final-asset-candidate-plan-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "slots": rows,
        "summary": {
            "slots_total": len(rows),
            "download_candidate_slots": sum(1 for r in rows if r["mode"] == "download-candidate"),
            "manual_asset_slots": sum(1 for r in rows if r["mode"] == "manual-local-asset"),
            "slots_without_candidates": len(empty),
            "candidate_count": sum(len(r.get("candidates") or []) for r in rows),
        },
        "slots_without_candidates": empty,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    s = result["summary"]
    print(f"Final asset slots: {s['slots_total']}")
    print(f"Download-candidate slots: {s['download_candidate_slots']}")
    print(f"Manual asset slots: {s['manual_asset_slots']}")
    print(f"Slots without candidates: {s['slots_without_candidates']}")
    print(f"Candidate URLs retained: {s['candidate_count']}")
    print(f"Wrote final asset candidate plan: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
