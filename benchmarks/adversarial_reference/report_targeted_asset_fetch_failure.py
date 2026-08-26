#!/usr/bin/env python3
"""Report which targeted empty asset slot failed to fetch and which succeeded.

Diagnostic only. Reads targeted_empty_asset_candidates.json and prints status/page/error
for the two bounded targets. Does not mutate source_inventory_v1.json or run retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "targeted_empty_asset_candidates.json"
OUTPUT = ROOT / "targeted_asset_fetch_failure_report.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    payload = _load(INPUT)
    rows = payload.get("results") or []
    report = []
    print(f"Targeted slot results: {len(rows)}")
    for idx, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        side = str(row.get("side") or "")
        status = str(row.get("status") or "")
        page_url = str(row.get("page_url") or "")
        error = str(row.get("error") or "")
        candidates = row.get("candidates") or []
        item = {
            "case_id": case_id,
            "side": side,
            "status": status,
            "page_url": page_url,
            "error": error,
            "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
        }
        report.append(item)
        print(f"[{idx}/{len(rows)}] {case_id}.{side} | status={status} | candidates={item['candidate_count']}")
        if page_url:
            print(f"  page={page_url}")
        if error:
            print(f"  error={error}")

    output = {
        "schema": "coin-analyzer-targeted-asset-fetch-failure-report-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "results": report,
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote targeted fetch report: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
