#!/usr/bin/env python3
"""Diagnose why targeted empty-slot extraction found zero pages to fetch.

Read-only diagnostic. Compares the two bounded target keys against page URLs in the
three underlying accepted-page review artifacts and against the combined coverage audit.
Does not download assets, mutate source_inventory_v1.json, or run retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGETS = ROOT / "target_empty_asset_slots.json"
CURATED = ROOT / "curated_provider_page_review.json"
WEB = ROOT / "web_curated_gap_page_review.json"
FINAL = ROOT / "final_gap_page_review.json"
COMBINED = ROOT / "combined_page_coverage_audit.json"
OUTPUT = ROOT / "targeted_page_lookup_failure_report.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _accepted_map(payload: dict) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for row in payload.get("accepted", []) or []:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or row.get("id") or "")
        side = str(row.get("side") or "")
        url = str(row.get("url") or row.get("page_url") or row.get("source_page_url") or "")
        if case_id and side and url:
            out[(case_id, side)] = url
    return out


def main() -> int:
    targets = _load(TARGETS).get("targets") or []
    maps = {
        "curated_provider": _accepted_map(_load(CURATED)),
        "web_curated": _accepted_map(_load(WEB)),
        "final_gap": _accepted_map(_load(FINAL)),
    }
    rows = []
    for row in targets:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("case_id") or ""), str(row.get("side") or ""))
        matches = {name: mapping.get(key) for name, mapping in maps.items() if mapping.get(key)}
        rows.append({"case_id": key[0], "side": key[1], "page_matches": matches})

    combined = _load(COMBINED)
    result = {
        "schema": "coin-analyzer-targeted-page-lookup-failure-report-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "combined_coverage_summary": {
            "covered_unique_slots": combined.get("covered_unique_slots"),
            "remaining_without_page_candidate": combined.get("remaining_without_page_candidate"),
        },
        "targets": rows,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Targeted slots: {len(rows)}")
    for idx, row in enumerate(rows, start=1):
        matches = row["page_matches"]
        print(f"[{idx}/{len(rows)}] {row['case_id']}.{row['side']} | page matches={len(matches)}")
        for source, url in matches.items():
            print(f"  {source}: {url}")
    print(f"Combined covered unique slots: {combined.get('covered_unique_slots')}")
    print(f"Wrote lookup failure report: {OUTPUT}")
    print("No pages were fetched, source_inventory_v1.json was not modified, and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
