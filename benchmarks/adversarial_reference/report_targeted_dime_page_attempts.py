#!/usr/bin/env python3
"""Report page-level targeted dime extraction attempts.

Reads targeted_unique_dime_asset_candidates.json and prints every page attempt, including
fetch errors and per-page candidate counts. This is diagnostic only: no frozen benchmark
content is modified and no retrieval scoring is run.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "targeted_unique_dime_asset_candidates.json"
OUTPUT = ROOT / "targeted_unique_dime_page_attempts.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    payload = _load(INPUT)
    rows = payload.get("results") or []
    out = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        side = str(row.get("side") or "")
        pages = row.get("page_attempts") or row.get("pages") or row.get("attempts") or []
        if not isinstance(pages, list):
            pages = []
        print(f"{case_id}.{side} | status={row.get('status')} | candidates={len(row.get('candidates') or [])}")
        if not pages:
            print("  page-attempt details unavailable in artifact")
            out.append({
                "case_id": case_id,
                "side": side,
                "status": row.get("status"),
                "page_attempts": [],
                "note": "page-attempt details unavailable in artifact",
            })
            continue
        clean_pages = []
        for i, page in enumerate(pages, 1):
            if not isinstance(page, dict):
                continue
            url = page.get("source_page_url") or page.get("page_url") or page.get("url")
            status = page.get("status")
            error = page.get("error")
            cand_count = len(page.get("candidates") or []) if isinstance(page.get("candidates"), list) else page.get("candidate_count")
            print(f"  [{i}] status={status} candidates={cand_count} page={url}")
            if error:
                print(f"      error={error}")
            clean_pages.append({
                "url": url,
                "status": status,
                "error": error,
                "candidate_count": cand_count,
            })
        out.append({
            "case_id": case_id,
            "side": side,
            "status": row.get("status"),
            "page_attempts": clean_pages,
        })

    result = {
        "schema": "coin-analyzer-targeted-dime-page-attempt-report-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "results": out,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote page-attempt report: {OUTPUT}")
    print("Frozen case set unchanged; source_inventory_v1.json unchanged; no retrieval scoring run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
