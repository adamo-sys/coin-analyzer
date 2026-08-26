#!/usr/bin/env python3
"""Summarize Commons discovery candidates without selecting benchmark sources.

This report is acquisition-only. It groups candidate files by frozen case, flags
obvious query-source collisions from the seeded inventory, and highlights cases
that likely need manual source review. It does not write source_inventory_v1.json
and it never runs retrieval scoring.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_CANDIDATES = ROOT / "commons_source_candidates.json"
DEFAULT_INVENTORY = ROOT / "source_inventory_v1.json"
DEFAULT_OUTPUT = ROOT / "commons_source_review.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parts = urlsplit(value.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


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
        "schema": "coin-analyzer-commons-source-review-v1",
        "retrieval_results_inspected": False,
        "selection_performed": False,
        "cases": {},
        "summary": {
            "cases": 0,
            "cases_with_candidates": 0,
            "cases_without_candidates": 0,
            "candidate_rows": 0,
            "obvious_query_collisions": 0,
        },
    }

    for case_id, case in (candidates.get("cases") or {}).items():
        inv = inventory_cases.get(case_id, {}) if isinstance(inventory_cases, dict) else {}
        query_slot = inv.get("query") if isinstance(inv, dict) else {}
        query_urls = {
            value
            for value in (
                _norm_url(query_slot.get("asset_url") if isinstance(query_slot, dict) else None),
                _norm_url(query_slot.get("source_page_url") if isinstance(query_slot, dict) else None),
            )
            if value
        }

        reviewed = []
        for row in case.get("candidates", []):
            candidate_urls = {
                value
                for value in (
                    _norm_url(row.get("original_url")),
                    _norm_url(row.get("thumbnail_url")),
                    _norm_url(row.get("description_url")),
                )
                if value
            }
            collision = bool(query_urls & candidate_urls)
            reviewed.append({
                "title": row.get("title"),
                "description_url": row.get("description_url"),
                "original_url": row.get("original_url"),
                "thumbnail_url": row.get("thumbnail_url"),
                "artist": row.get("artist"),
                "license": row.get("license"),
                "description": row.get("description"),
                "obvious_query_collision": collision,
            })
            report["summary"]["candidate_rows"] += 1
            if collision:
                report["summary"]["obvious_query_collisions"] += 1

        report["cases"][case_id] = {
            "expected": case.get("expected"),
            "sides_needed": case.get("sides_needed"),
            "search_query": case.get("search_query"),
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
    summary = report["summary"]
    print(f"Reviewed cases: {summary['cases']}")
    print(f"Cases with Commons candidates: {summary['cases_with_candidates']}")
    print(f"Cases without Commons candidates: {summary['cases_without_candidates']}")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Obvious seeded-query collisions flagged: {summary['obvious_query_collisions']}")
    print(f"Wrote review report: {args.output}")
    print("No sources were selected and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
