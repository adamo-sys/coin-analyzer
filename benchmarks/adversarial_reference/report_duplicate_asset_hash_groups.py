#!/usr/bin/env python3
"""Report duplicate SHA-256 groups from downloaded adversarial source assets.

Diagnostic only: does not mutate source_inventory_v1.json and does not run retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "downloaded_ranked_asset_candidates.json"
OUTPUT = ROOT / "duplicate_asset_hash_groups.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _groups(payload: dict) -> list[dict]:
    # Current downloader writes a mapping under duplicate_sha256. Older diagnostics
    # used alternate field names; keep those fallbacks so locally generated audits
    # remain readable across revisions.
    groups = (
        payload.get("duplicate_sha256")
        or payload.get("duplicate_sha256_groups")
        or payload.get("duplicate_hash_groups")
        or []
    )
    if isinstance(groups, dict):
        return [
            {"sha256": sha256, "members": members}
            for sha256, members in groups.items()
        ]
    return groups if isinstance(groups, list) else []


def main() -> int:
    payload = _load(INPUT)
    groups = _groups(payload)

    normalized = []
    for idx, group in enumerate(groups, start=1):
        if not isinstance(group, dict):
            continue
        sha256 = str(group.get("sha256") or group.get("hash") or "")
        members = group.get("members") or group.get("slots") or group.get("items") or []
        if not isinstance(members, list):
            members = []
        cleaned = []
        for member in members:
            if not isinstance(member, dict):
                continue
            cleaned.append({
                "case_id": member.get("case_id") or member.get("id"),
                "side": member.get("side"),
                "source_page_url": member.get("source_page_url") or member.get("page_url"),
                "asset_url": member.get("asset_url") or member.get("final_url") or member.get("url"),
                "local_path": member.get("local_path") or member.get("path"),
            })
        normalized.append({"sha256": sha256, "members": cleaned})
        print(f"[{idx}/{len(groups)}] sha256={sha256} members={len(cleaned)}")
        for member in cleaned:
            print(
                "  - "
                f"{member.get('case_id')}.{member.get('side')} | "
                f"page={member.get('source_page_url')} | asset={member.get('asset_url')}"
            )

    result = {
        "schema": "coin-analyzer-duplicate-asset-hash-report-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "duplicate_groups": normalized,
        "summary": {
            "duplicate_sha256_groups": len(normalized),
            "duplicate_members": sum(len(group["members"]) for group in normalized),
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Duplicate SHA-256 groups: {result['summary']['duplicate_sha256_groups']}")
    print(f"Duplicate asset memberships: {result['summary']['duplicate_members']}")
    print(f"Wrote duplicate hash report: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
