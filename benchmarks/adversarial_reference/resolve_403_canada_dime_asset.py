#!/usr/bin/env python3
"""Resolve the last 403-blocked Canada 10 cents 1955 reference asset slot.

This bounded helper does not scrape around the block. It records the 403 as a provider
transport limitation and prepares a manual/direct-asset resolution record so the benchmark
can preserve provenance without mutating source_inventory_v1.json or running retrieval
scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FETCH_REPORT = ROOT / "targeted_asset_fetch_failure_report.json"
OUTPUT = ROOT / "canada_10_cents_1955_reference_resolution.json"

TARGET = ("canada-10-cents-1955", "reference")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    payload = _load(FETCH_REPORT)
    rows = payload.get("results") or payload.get("items") or []
    target = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("case_id") or ""), str(row.get("side") or ""))
        if key == TARGET:
            target = row
            break

    if target is None:
        print("Target slot not found in fetch report.")
        return 1

    error = str(target.get("error") or "")
    page_url = str(target.get("page_url") or "")
    if "403" not in error:
        print(f"Target exists but is not a 403 failure: {error}")
        return 1

    result = {
        "schema": "coin-analyzer-manual-asset-resolution-v1",
        "case_id": TARGET[0],
        "side": TARGET[1],
        "identity": "Canada 10 cents 1955",
        "accepted_identity_page": page_url,
        "provider_transport_status": "http-403-forbidden",
        "resolution_status": "manual-or-independent-direct-asset-required",
        "requirements": {
            "must_be_coin_specific": True,
            "must_match_exact_identity": True,
            "must_not_reuse_frozen_wikimedia_query_asset": True,
            "must_record_source_page_url": True,
            "must_record_asset_url": True,
            "must_record_creator": True,
            "must_record_license": True,
            "must_record_retrieved_at": True,
            "must_record_sha256": True,
            "must_pass_same_source_page_guard": True,
            "must_pass_asset_hash_independence_guard": True,
        },
        "notes": "Do not bypass the provider block with spoofing or search-engine scraping. Use a defensible independent direct asset or a manually verified public/licensed image source for the same frozen identity.",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Canada 10 cents 1955.reference transport status: HTTP 403")
    print("Resolution path: manual or independent direct asset required")
    print(f"Accepted identity page: {page_url}")
    print(f"Wrote resolution record: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
