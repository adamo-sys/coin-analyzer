#!/usr/bin/env python3
"""Seed query provenance for adversarial cases that reuse frozen Benchmark v2 queries.

This only copies already-frozen query-side provenance. It does not acquire references,
run retrieval, or alter the frozen 25-case identity manifest.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_INVENTORY = ROOT / "source_inventory_v1.json"
DEFAULT_V2_MANIFEST = ROOT.parent / "v2" / "manifest.json"


def _provider(source_page: str) -> str:
    if "wikimedia.org" in source_page:
        return "Wikimedia Commons"
    return "Benchmark v2 frozen source"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--v2-manifest", type=Path, default=DEFAULT_V2_MANIFEST)
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    v2 = json.loads(args.v2_manifest.read_text(encoding="utf-8"))
    v2_by_id = {case["id"]: case for case in v2.get("cases", [])}

    seeded = 0
    skipped = 0
    for case_id, entry in inventory.get("case_sources", {}).items():
        source_status = str(entry.get("source_status") or "")
        if not source_status.startswith("reuse-frozen-v2-query"):
            continue
        case = v2_by_id.get(case_id)
        if not case:
            print(f"WARNING: {case_id}: marked as frozen-v2 query but absent from Benchmark v2")
            skipped += 1
            continue
        obverse = case.get("obverse") or {}
        reverse = case.get("reverse") or {}
        source_page = str(obverse.get("source_page") or reverse.get("source_page") or "")
        source_file_url = str(obverse.get("source_file_url") or reverse.get("source_file_url") or "")
        author = str(obverse.get("author") or reverse.get("author") or "unknown / not recorded")
        license_note = str(obverse.get("license") or reverse.get("license") or "unknown / not recorded")
        retrieved_at = str(obverse.get("retrieved_at") or reverse.get("retrieved_at") or "")
        sha = str(obverse.get("source_sha256") or reverse.get("source_sha256") or "") or None
        entry["query"] = {
            "status": "ready",
            "source_page_url": source_page,
            "asset_url": source_file_url,
            "provider": _provider(source_page),
            "creator_or_credit": author,
            "license_or_usage_note": license_note,
            "retrieved_at": retrieved_at,
            "source_asset_sha256": sha,
            "independence_rationale": "Query is the pre-existing frozen Benchmark v2 asset. The adversarial reference must be acquired from an independently sourced asset and must not share this source URL or source hash.",
            "benchmark_v2_paths": {
                "obverse": obverse.get("path"),
                "reverse": reverse.get("path"),
            },
        }
        seeded += 1

    args.inventory.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(f"Seeded frozen Benchmark v2 query provenance: {seeded}")
    print(f"Skipped inconsistent frozen-v2 cases: {skipped}")
    return 0 if skipped == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
