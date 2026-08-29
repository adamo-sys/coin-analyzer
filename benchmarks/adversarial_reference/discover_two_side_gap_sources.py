#!/usr/bin/env python3
"""Create a targeted, scoring-blind discovery plan for unresolved two-side assets.

This does not download images and does not invoke retrieval. It converts the
54 unresolved query/reference side roles into explicit web/source-search tasks
while preserving frozen identities and side roles exactly.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "two_side_gap_acquisition_queue.json"
RESULTS = ROOT / "two_side_gap_acquisition_results.json"
OUTPUT = ROOT / "two_side_gap_source_discovery_plan.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not QUEUE.is_file() or not RESULTS.is_file():
        raise SystemExit("two_side_gap_acquisition_queue.json and two_side_gap_acquisition_results.json are required")

    queue = load(QUEUE)
    results = load(RESULTS)
    unresolved_keys = {
        (str(r.get("case_id") or ""), str(r.get("side") or ""), str(r.get("role") or ""))
        for r in results.get("results", [])
        if isinstance(r, dict) and r.get("status") != "downloaded"
    }

    rows = []
    for item in queue.get("queue", []):
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or "")
        source_group = str(item.get("source_group") or "")
        coin_side = str(item.get("coin_side") or "")
        key = (case_id, source_group, coin_side)
        if key not in unresolved_keys:
            continue
        expected = item.get("expected") if isinstance(item.get("expected"), dict) else {}
        country = str(expected.get("country") or "").strip()
        denomination = str(expected.get("denomination") or "").strip()
        year = str(expected.get("year") or "").strip()
        identity = " ".join(part for part in (country, year, denomination) if part)
        side_word = "obverse" if coin_side == "obverse" else "reverse"
        query = f'"{identity}" coin {side_word}'
        rows.append({
            "case_id": case_id,
            "source_group": source_group,
            "coin_side": coin_side,
            "expected": expected,
            "search_query": query,
            "search_hints": [
                f"Wikimedia Commons {query}",
                f"Numista {query}",
                f"Coins and Canada {query}" if country == "Canada" else None,
                f"uCoin {query}",
            ],
            "browser_search_url": "https://www.google.com/search?q=" + quote_plus(query),
            "requirements": {
                "explicit_side_identity": True,
                "source_page_required": True,
                "direct_asset_url_required": True,
                "query_reference_independence_required": True,
                "no_heuristic_split": True,
                "no_retrieval_scoring": True,
            },
            "status": "needs-targeted-source-discovery",
        })

    for row in rows:
        row["search_hints"] = [v for v in row["search_hints"] if v]

    payload = {
        "schema": "coin-analyzer-two-side-gap-source-discovery-plan-v1",
        "retrieval_scoring_run": False,
        "rows": rows,
        "summary": {
            "roles_needing_discovery": len(rows),
            "query_roles": sum(r["source_group"] == "query" for r in rows),
            "reference_roles": sum(r["source_group"] == "reference" for r in rows),
            "cases": len({r["case_id"] for r in rows}),
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    s = payload["summary"]
    print("Targeted two-side source discovery plan")
    print("Scoring blind: no retrieval was run and no images were downloaded.")
    print(f"Roles needing source discovery: {s['roles_needing_discovery']}")
    print(f"  Query roles: {s['query_roles']}")
    print(f"  Reference roles: {s['reference_roles']}")
    print(f"Cases represented: {s['cases']}")
    print(f"Wrote discovery plan: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
