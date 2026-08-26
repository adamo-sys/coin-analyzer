#!/usr/bin/env python3
"""Audit query/reference provenance for same-page and same-asset leakage.

This is a pre-freeze safety check. It never runs retrieval scoring and never
mutates source_inventory_v1.json. It reports exact URL collisions, normalized
same-page reuse, and identical source hashes when available. Proposed/curated
page rows may be supplied later, but page-level identity alone is not accepted as
asset independence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_INVENTORY = ROOT / "source_inventory_v1.json"
DEFAULT_OUTPUT = ROOT / "source_asset_independence_audit.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    p = urlsplit(value.strip())
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", ""))


def _present(slot: object) -> bool:
    return isinstance(slot, dict) and bool(slot.get("source_page_url") or slot.get("asset_url"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    inventory = _load(args.inventory)
    cases = inventory.get("case_sources", {})
    rows = []
    summary = {
        "cases": 0,
        "cases_with_both_slots": 0,
        "asset_url_collisions": 0,
        "source_page_collisions": 0,
        "source_hash_collisions": 0,
        "independence_clear": 0,
        "independence_pending": 0,
    }

    for case_id, case in cases.items() if isinstance(cases, dict) else []:
        summary["cases"] += 1
        query = case.get("query") if isinstance(case, dict) else None
        reference = case.get("reference") if isinstance(case, dict) else None
        if not (_present(query) and _present(reference)):
            rows.append({"case_id": case_id, "status": "pending-missing-slot"})
            summary["independence_pending"] += 1
            continue
        summary["cases_with_both_slots"] += 1

        q_asset = _norm(query.get("asset_url"))
        r_asset = _norm(reference.get("asset_url"))
        q_page = _norm(query.get("source_page_url"))
        r_page = _norm(reference.get("source_page_url"))
        q_hash = query.get("source_asset_sha256")
        r_hash = reference.get("source_asset_sha256")

        issues = []
        if q_asset and r_asset and q_asset == r_asset:
            issues.append("same-asset-url")
            summary["asset_url_collisions"] += 1
        if q_page and r_page and q_page == r_page:
            issues.append("same-source-page")
            summary["source_page_collisions"] += 1
        if q_hash and r_hash and q_hash == r_hash:
            issues.append("same-source-hash")
            summary["source_hash_collisions"] += 1

        if issues:
            status = "collision"
            summary["independence_pending"] += 1
        elif q_asset and r_asset and q_page and r_page:
            status = "clear-by-provenance"
            summary["independence_clear"] += 1
        else:
            status = "pending-incomplete-provenance"
            summary["independence_pending"] += 1

        rows.append({
            "case_id": case_id,
            "status": status,
            "issues": issues,
            "query_source_page_url": query.get("source_page_url"),
            "reference_source_page_url": reference.get("source_page_url"),
            "query_asset_url": query.get("asset_url"),
            "reference_asset_url": reference.get("asset_url"),
        })

    artifact = {
        "schema": "coin-analyzer-source-asset-independence-audit-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "rows": rows,
        "summary": summary,
    }
    args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Cases audited: {summary['cases']}")
    print(f"Cases with both source slots populated: {summary['cases_with_both_slots']}")
    print(f"Asset URL collisions: {summary['asset_url_collisions']}")
    print(f"Same source-page collisions: {summary['source_page_collisions']}")
    print(f"Source hash collisions: {summary['source_hash_collisions']}")
    print(f"Independence clear by provenance: {summary['independence_clear']}")
    print(f"Independence pending: {summary['independence_pending']}")
    print(f"Wrote independence audit: {args.output}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 1 if (summary['asset_url_collisions'] or summary['source_hash_collisions']) else 0


if __name__ == "__main__":
    raise SystemExit(main())
