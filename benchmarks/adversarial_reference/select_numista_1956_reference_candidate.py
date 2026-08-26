#!/usr/bin/env python3
"""Select a defensible Numista full-size candidate for Canada 10 cents 1956.reference.

Consumes targeted_unique_dime_asset_candidates.json. Selects the full-size Numista
`catalogue/photo385.jpeg` asset when present, rejecting analytics/UI/thumbnails.
This remains a pre-retrieval bookkeeping step: no scoring and no inventory mutation.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "targeted_unique_dime_asset_candidates.json"
OUTPUT = ROOT / "selected_numista_1956_reference.json"
TARGET = ("canada-10-cents-1956", "reference")
PREFERRED_SUFFIX = "/catalogue/photo385.jpeg"


def main() -> int:
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    rows = payload.get("results") or []
    selected = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("case_id") or ""), str(row.get("side") or ""))
        if key != TARGET:
            continue
        for cand in row.get("candidates") or []:
            if not isinstance(cand, dict):
                continue
            url = str(cand.get("asset_url") or cand.get("final_url") or "")
            if url.endswith(PREFERRED_SUFFIX):
                selected = {
                    "case_id": TARGET[0],
                    "side": TARGET[1],
                    "provider": "Numista",
                    "source_page_url": "https://en.numista.com/catalogue/pieces385.html",
                    "asset_url": cand.get("asset_url"),
                    "final_url": cand.get("final_url"),
                    "sha256": cand.get("sha256"),
                    "bytes": cand.get("bytes"),
                    "selection_reason": "Full-size catalogue image chosen pre-retrieval; thumbnail variants, analytics pixels, and UI assets excluded.",
                }
                break
        break

    if selected is None:
        raise SystemExit("Preferred Numista full-size candidate not found")

    result = {
        "schema": "coin-analyzer-selected-numista-1956-reference-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "selected": selected,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Selected: {selected['case_id']}.{selected['side']}")
    print(f"Asset URL: {selected['asset_url']}")
    print(f"SHA-256: {selected['sha256']}")
    print(f"Bytes: {selected['bytes']}")
    print(f"Wrote selection: {OUTPUT}")
    print("source_inventory_v1.json unchanged; no retrieval scoring run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
