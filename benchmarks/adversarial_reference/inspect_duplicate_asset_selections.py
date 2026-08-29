#!/usr/bin/env python3
"""Inspect downloaded duplicate-hash selections with their selected URLs and metadata.

Diagnostic only. Reads downloaded_ranked_asset_candidates.json and prints every member of
any duplicate SHA-256 group with the actual selected source/final URL, content type, byte
count, local path, and retained candidate metadata. Does not mutate source_inventory_v1.json
or run retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "downloaded_ranked_asset_candidates.json"
OUTPUT = ROOT / "duplicate_asset_selection_inspection.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    payload = _load(INPUT)
    duplicate_map = payload.get("duplicate_sha256") or {}
    if not isinstance(duplicate_map, dict):
        duplicate_map = {}

    by_key: dict[tuple[str, str], dict] = {}
    for row in payload.get("results", []):
        if not isinstance(row, dict):
            continue
        key = (str(row.get("case_id") or ""), str(row.get("side") or ""))
        by_key[key] = row

    groups = []
    for index, (sha256, refs) in enumerate(sorted(duplicate_map.items()), 1):
        members = []
        print(f"[{index}/{len(duplicate_map)}] sha256={sha256}")
        for ref in refs if isinstance(refs, list) else []:
            if not isinstance(ref, dict):
                continue
            case_id = str(ref.get("case_id") or "")
            side = str(ref.get("side") or "")
            row = by_key.get((case_id, side), {})
            selected = row.get("selected") if isinstance(row, dict) else None
            if not isinstance(selected, dict):
                selected = {}
            member = {
                "case_id": case_id,
                "side": side,
                "rank": selected.get("rank"),
                "source_url": selected.get("source_url"),
                "final_url": selected.get("final_url"),
                "content_type": selected.get("content_type"),
                "bytes": selected.get("bytes"),
                "local_path": selected.get("local_path"),
                "candidate": selected.get("candidate"),
            }
            members.append(member)
            print(
                f"  - {case_id}.{side} | rank={member['rank']} | bytes={member['bytes']} | "
                f"type={member['content_type']}\n"
                f"    source={member['source_url']}\n"
                f"    final={member['final_url']}"
            )
        groups.append({"sha256": sha256, "members": members})

    result = {
        "schema": "coin-analyzer-duplicate-asset-selection-inspection-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "groups": groups,
        "summary": {
            "duplicate_sha256_groups": len(groups),
            "duplicate_members": sum(len(group["members"]) for group in groups),
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Duplicate SHA-256 groups inspected: {result['summary']['duplicate_sha256_groups']}")
    print(f"Duplicate memberships inspected: {result['summary']['duplicate_members']}")
    print(f"Wrote selection inspection: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
