#!/usr/bin/env python3
"""Report unresolved slots and duplicate SHA groups from the final adversarial download pass.

Diagnostic only. Does not mutate source_inventory_v1.json and does not run retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "final_downloaded_assets.json"
OUTPUT = ROOT / "final_download_anomalies.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    payload = _load(INPUT)
    results = payload.get("results") or payload.get("slots") or []
    unresolved = []
    if isinstance(results, list):
        for row in results:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "")
            selected = row.get("selected")
            if status not in {"selected", "downloaded", "manual-selected", "ok"} and not isinstance(selected, dict):
                unresolved.append(row)

    groups = payload.get("duplicate_sha256") or payload.get("duplicate_sha256_groups") or payload.get("duplicate_hash_groups") or {}
    if isinstance(groups, dict):
        duplicate_groups = [
            {"sha256": sha, "members": members if isinstance(members, list) else []}
            for sha, members in groups.items()
        ]
    elif isinstance(groups, list):
        duplicate_groups = [g for g in groups if isinstance(g, dict)]
    else:
        duplicate_groups = []

    print(f"Unresolved slots: {len(unresolved)}")
    for idx, row in enumerate(unresolved, 1):
        case_id = row.get("case_id") or row.get("id")
        side = row.get("side")
        status = row.get("status")
        error = row.get("error")
        print(f"[{idx}/{len(unresolved)}] {case_id}.{side} | status={status} | error={error}")

    print(f"Duplicate SHA-256 groups: {len(duplicate_groups)}")
    for idx, group in enumerate(duplicate_groups, 1):
        sha = group.get("sha256") or group.get("hash")
        members = group.get("members") or group.get("slots") or group.get("items") or []
        print(f"[{idx}/{len(duplicate_groups)}] sha256={sha} members={len(members) if isinstance(members, list) else 0}")
        if isinstance(members, list):
            for member in members:
                if not isinstance(member, dict):
                    continue
                print(
                    "  - "
                    f"{member.get('case_id') or member.get('id')}.{member.get('side')} | "
                    f"url={member.get('final_url') or member.get('source_url') or member.get('asset_url') or member.get('url')} | "
                    f"path={member.get('local_path') or member.get('path')}"
                )

    output = {
        "schema": "coin-analyzer-final-download-anomalies-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "unresolved": unresolved,
        "duplicate_groups": duplicate_groups,
        "summary": {
            "unresolved_slots": len(unresolved),
            "duplicate_sha256_groups": len(duplicate_groups),
        },
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote anomaly report: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
