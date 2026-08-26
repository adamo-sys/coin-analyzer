#!/usr/bin/env python3
"""Report Numista candidates for the unresolved 1956 reference slot.

Reads targeted_unique_dime_asset_candidates.json and prints a compact ranked view
of candidate URLs, hashes, and byte sizes for canada-10-cents-1956.reference only.
This is a pre-retrieval diagnostic: it does not mutate source_inventory_v1.json and
does not run retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "targeted_unique_dime_asset_candidates.json"
TARGET = ("canada-10-cents-1956", "reference")


def main() -> int:
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    rows = payload.get("results") or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("case_id") or ""), str(row.get("side") or ""))
        if key != TARGET:
            continue
        candidates = [c for c in (row.get("candidates") or []) if isinstance(c, dict)]
        print(f"Target: {TARGET[0]}.{TARGET[1]}")
        print(f"Candidates: {len(candidates)}")
        for i, c in enumerate(candidates[:20], 1):
            print(
                f"[{i}] rank={c.get('rank')} bytes={c.get('bytes')} sha256={c.get('sha256')}\n"
                f"    asset_url={c.get('asset_url')}\n"
                f"    final_url={c.get('final_url')}"
            )
        print("source_inventory_v1.json unchanged; no retrieval scoring run.")
        return 0
    raise SystemExit("Target slot not found in targeted_unique_dime_asset_candidates.json")


if __name__ == "__main__":
    raise SystemExit(main())
