#!/usr/bin/env python3
"""Create a scoring-blind acquisition queue for unresolved two-side benchmark assets.

Consumes the explicit two-side inventory and emits only the missing query/reference
roles that still require independent side-specific assets. It does not decode
images, download assets, alter the frozen identity manifest, or run retrieval.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "two_side_existing_asset_inventory.json"
MANIFEST = ROOT / "manifest_v1.json"
OUTPUT = ROOT / "two_side_gap_acquisition_queue.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not INVENTORY.is_file() or not MANIFEST.is_file():
        raise SystemExit("two_side_existing_asset_inventory.json and manifest_v1.json are required")

    inventory = load(INVENTORY)
    manifest = load(MANIFEST)
    expected = {
        str(row.get("id") or row.get("case_id") or ""): row.get("expected")
        for row in manifest.get("cases", []) if isinstance(row, dict)
    }

    queue = []
    for row in inventory.get("rows", []):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        missing = row.get("missing") if isinstance(row.get("missing"), list) else []
        for role in missing:
            if role not in {
                "query.obverse", "query.reverse", "reference.obverse", "reference.reverse"
            }:
                continue
            side_group, coin_side = role.split(".", 1)
            queue.append({
                "case_id": case_id,
                "expected": expected.get(case_id),
                "asset_role": role,
                "source_group": side_group,
                "coin_side": coin_side,
                "requirements": {
                    "explicit_side_identity": True,
                    "independent_from_opposite_source_group": True,
                    "source_page_required": True,
                    "asset_url_required": True,
                    "provenance_review_required": True,
                    "no_heuristic_split": True,
                },
                "status": "unresolved-before-scoring",
            })

    by_group = {
        "query": sum(item["source_group"] == "query" for item in queue),
        "reference": sum(item["source_group"] == "reference" for item in queue),
    }
    cases_with_gaps = sorted({item["case_id"] for item in queue})
    artifact = {
        "schema": "coin-analyzer-two-side-gap-acquisition-queue-v1",
        "retrieval_scoring_run": False,
        "queue": queue,
        "summary": {
            "missing_asset_roles": len(queue),
            "missing_query_roles": by_group["query"],
            "missing_reference_roles": by_group["reference"],
            "cases_with_gaps": len(cases_with_gaps),
            "case_ids": cases_with_gaps,
        },
    }
    OUTPUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("Two-side gap acquisition planner")
    print("Scoring blind: no benchmark images were decoded and no retrieval was run.")
    print(f"Cases with gaps: {len(cases_with_gaps)}")
    print(f"Missing asset roles: {len(queue)}")
    print(f"  Query roles: {by_group['query']}")
    print(f"  Reference roles: {by_group['reference']}")
    print(f"Wrote acquisition queue: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
