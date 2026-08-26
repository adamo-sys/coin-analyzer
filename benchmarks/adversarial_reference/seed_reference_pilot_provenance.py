#!/usr/bin/env python3
"""Seed reference-side provenance from the existing independent-reference pilot.

This reuses only provenance already recorded by the independent reference catalogue.
It does not run retrieval or alter the frozen 25-case identity set. Cases whose
reference asset URL collides with the frozen query asset are skipped rather than
silently accepted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent.parent
DEFAULT_INVENTORY = ROOT / "source_inventory_v1.json"
DEFAULT_PILOT = REPO_ROOT / "benchmarks" / "v2" / "reference_pilot" / "manifest.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _first_nonempty(values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


def _flatten_provenance(candidate: dict) -> list[dict]:
    rows: list[dict] = []
    provenance = candidate.get("provenance") if isinstance(candidate.get("provenance"), dict) else {}
    for role in ("obverse", "reverse"):
        role_rows = provenance.get(role)
        if isinstance(role_rows, list):
            rows.extend(row for row in role_rows if isinstance(row, dict))
    unique: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("commons_source_page") or row.get("fallback_source_page") or ""), str(row.get("retrieved_file_url") or row.get("commons_file_url") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--pilot", type=Path, default=DEFAULT_PILOT)
    args = parser.parse_args()

    if not args.pilot.exists():
        print(f"Independent reference pilot manifest not found: {args.pilot}")
        print("Run benchmarks/v2/prepare_reference_pilot.py first; no inventory changes made.")
        return 2

    inventory = _load(args.inventory)
    pilot = _load(args.pilot)
    entries = inventory.get("case_sources")
    if not isinstance(entries, dict):
        raise SystemExit("Inventory must contain case_sources object; run build_source_inventory.py first.")

    seeded = 0
    skipped_collision = 0
    skipped_missing = 0
    for candidate in pilot.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        case_id = candidate.get("id")
        if case_id not in entries:
            continue
        assets = _flatten_provenance(candidate)
        if not assets:
            skipped_missing += 1
            continue

        query = entries[case_id].get("query") if isinstance(entries[case_id].get("query"), dict) else {}
        query_asset = str(query.get("asset_url") or "")
        reference_urls = [str(row.get("retrieved_file_url") or row.get("commons_file_url") or "") for row in assets]
        if query_asset and query_asset in reference_urls:
            print(f"SKIP collision: {case_id} reference asset matches frozen query asset")
            skipped_collision += 1
            continue

        primary = assets[0]
        source_page = _first_nonempty([
            primary.get("commons_source_page"),
            primary.get("fallback_source_page"),
        ])
        asset_url = _first_nonempty([
            primary.get("retrieved_file_url"),
            primary.get("commons_file_url"),
        ])
        provider = _first_nonempty([primary.get("retrieval_source")])
        creator = _first_nonempty([primary.get("author"), primary.get("credit")])
        license_note = _first_nonempty([primary.get("license")])
        retrieved_at = _first_nonempty([primary.get("retrieved_at")])

        entries[case_id]["reference"] = {
            "status": "seeded-independent-reference-pilot",
            "source_page_url": source_page,
            "asset_url": asset_url,
            "provider": provider,
            "creator_or_credit": creator,
            "license_or_usage_note": license_note,
            "retrieved_at": retrieved_at,
            "source_asset_sha256": None,
            "independence_rationale": "Reference imagery comes from the separately prepared independent-reference pilot catalogue and uses asset URLs distinct from the frozen Benchmark v2 query asset.",
            "paired_reference_assets": assets,
        }
        seeded += 1

    inventory["case_sources"] = entries
    inventory["reference_pilot_provenance_seeded"] = seeded
    args.inventory.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Seeded independent-reference pilot provenance: {seeded}")
    print(f"Skipped query/reference URL collisions: {skipped_collision}")
    print(f"Skipped candidates lacking provenance: {skipped_missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
