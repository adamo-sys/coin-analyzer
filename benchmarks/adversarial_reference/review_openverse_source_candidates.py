#!/usr/bin/env python3
"""Review Openverse candidates conservatively without selecting benchmark sources.

Acquisition-only tooling. It summarizes candidate coverage, normalizes source URLs,
flags collisions against already-seeded query/reference provenance, and writes a
review artifact for later deterministic proposal logic. It does not mutate the
frozen source inventory and never runs retrieval scoring.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_CANDIDATES = ROOT / "openverse_source_candidates.json"
DEFAULT_INVENTORY = ROOT / "source_inventory_v1.json"
DEFAULT_OUTPUT = ROOT / "openverse_source_review.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parts = urlsplit(value.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def _candidate_urls(row: dict) -> set[str]:
    keys = (
        "url",
        "thumbnail",
        "foreign_landing_url",
        "detail_url",
        "source_url",
        "original_url",
        "asset_url",
    )
    out: set[str] = set()
    for key in keys:
        value = _norm_url(row.get(key))
        if value:
            out.add(value)
    return out


def _slot_urls(slot: object) -> set[str]:
    if not isinstance(slot, dict):
        return set()
    out: set[str] = set()
    for key in ("source_page_url", "asset_url"):
        value = _norm_url(slot.get(key))
        if value:
            out.add(value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    candidates = _load(args.candidates)
    inventory = _load(args.inventory)
    inventory_cases = inventory.get("case_sources", {})

    report = {
        "schema": "coin-analyzer-openverse-source-review-v1",
        "retrieval_results_inspected": False,
        "selection_performed": False,
        "cases": {},
        "summary": {
            "cases": 0,
            "cases_with_candidates": 0,
            "cases_without_candidates": 0,
            "candidate_rows": 0,
            "seeded_source_collisions": 0,
            "rows_with_license": 0,
            "rows_with_creator": 0,
        },
    }

    for case_id, case in (candidates.get("cases") or {}).items():
        inv = inventory_cases.get(case_id, {}) if isinstance(inventory_cases, dict) else {}
        seeded_urls = set()
        if isinstance(inv, dict):
            seeded_urls |= _slot_urls(inv.get("query"))
            seeded_urls |= _slot_urls(inv.get("reference"))

        reviewed = []
        for row in case.get("candidates", []):
            urls = _candidate_urls(row)
            collision = bool(seeded_urls & urls)
            license_value = row.get("license") or row.get("license_url") or row.get("license_version")
            creator_value = row.get("creator") or row.get("creator_url") or row.get("attribution")
            reviewed.append({
                "id": row.get("id"),
                "title": row.get("title"),
                "creator": row.get("creator"),
                "creator_url": row.get("creator_url"),
                "license": row.get("license"),
                "license_version": row.get("license_version"),
                "license_url": row.get("license_url"),
                "source": row.get("source"),
                "provider": row.get("provider"),
                "foreign_landing_url": row.get("foreign_landing_url"),
                "url": row.get("url"),
                "thumbnail": row.get("thumbnail"),
                "seeded_source_collision": collision,
            })
            report["summary"]["candidate_rows"] += 1
            if collision:
                report["summary"]["seeded_source_collisions"] += 1
            if license_value:
                report["summary"]["rows_with_license"] += 1
            if creator_value:
                report["summary"]["rows_with_creator"] += 1

        report["cases"][case_id] = {
            "expected": case.get("expected"),
            "sides_needed": case.get("sides_needed"),
            "search_queries": case.get("search_queries") or case.get("queries") or case.get("search_query"),
            "error": case.get("error"),
            "candidate_count": len(reviewed),
            "candidates": reviewed,
        }
        report["summary"]["cases"] += 1
        if reviewed:
            report["summary"]["cases_with_candidates"] += 1
        else:
            report["summary"]["cases_without_candidates"] += 1

    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    s = report["summary"]
    print(f"Reviewed Openverse cases: {s['cases']}")
    print(f"Cases with Openverse candidates: {s['cases_with_candidates']}")
    print(f"Cases without Openverse candidates: {s['cases_without_candidates']}")
    print(f"Openverse candidate rows: {s['candidate_rows']}")
    print(f"Seeded-source collisions flagged: {s['seeded_source_collisions']}")
    print(f"Rows carrying license metadata: {s['rows_with_license']}")
    print(f"Rows carrying creator metadata: {s['rows_with_creator']}")
    print(f"Wrote Openverse review report: {args.output}")
    print("No sources were selected and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
