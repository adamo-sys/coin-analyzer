#!/usr/bin/env python3
"""Propose conservative Openverse source selections for unresolved benchmark slots.

Acquisition-only tooling. Uses provenance and lexical identity evidence only.
It does not run retrieval scoring and does not modify source_inventory_v1.json.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_REVIEW = ROOT / "openverse_source_review.json"
DEFAULT_INVENTORY = ROOT / "source_inventory_v1.json"
DEFAULT_OUTPUT = ROOT / "proposed_openverse_source_selections.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parts = urlsplit(value.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def _tokens(value: object) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {t for t in re.findall(r"[a-z0-9]+", value.lower()) if len(t) >= 2}


def _identity_terms(expected: dict) -> tuple[set[str], str]:
    country = str(expected.get("country") or "").lower()
    denom = str(expected.get("denomination") or "").lower()
    year = str(expected.get("year") or "").lower()
    text = f"{country} {denom} {year}"
    return _tokens(text), year


def _row_text(row: dict) -> str:
    parts = [
        row.get("title"), row.get("creator"), row.get("provider"), row.get("source"),
        row.get("foreign_landing_url"), row.get("license"),
    ]
    return " ".join(str(p) for p in parts if p)


def _passes_identity_gate(expected: dict, row: dict) -> bool:
    expected_tokens, year = _identity_terms(expected)
    row_tokens = _tokens(_row_text(row))
    if year and year not in row_tokens:
        return False
    non_year = {t for t in expected_tokens if t != year}
    overlap = non_year & row_tokens
    return len(overlap) >= 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    review = _load(args.review)
    inventory = _load(args.inventory)
    inv_cases = inventory.get("case_sources", {})

    artifact = {
        "schema": "coin-analyzer-openverse-source-proposals-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "selection_policy": "provenance + lexical identity only; no retrieval-score selection",
        "cases": {},
        "summary": {
            "cases_reviewed": 0,
            "source_slots_proposed": 0,
            "source_slots_unresolved": 0,
            "rows_rejected_collision": 0,
            "rows_rejected_identity": 0,
        },
    }

    for case_id, case in (review.get("cases") or {}).items():
        expected = case.get("expected") or {}
        inv = inv_cases.get(case_id, {}) if isinstance(inv_cases, dict) else {}
        sides_needed = case.get("sides_needed") or ["query", "reference"]
        proposals: dict[str, dict | None] = {}

        seeded_urls = set()
        if isinstance(inv, dict):
            for side in ("query", "reference"):
                slot = inv.get(side)
                if isinstance(slot, dict):
                    for key in ("asset_url", "source_page_url"):
                        u = _norm_url(slot.get(key))
                        if u:
                            seeded_urls.add(u)

        viable = []
        for row in case.get("candidates", []):
            candidate_urls = {
                u for u in (
                    _norm_url(row.get("url")),
                    _norm_url(row.get("thumbnail")),
                    _norm_url(row.get("foreign_landing_url")),
                ) if u
            }
            if seeded_urls & candidate_urls:
                artifact["summary"]["rows_rejected_collision"] += 1
                continue
            if not _passes_identity_gate(expected, row):
                artifact["summary"]["rows_rejected_identity"] += 1
                continue
            viable.append(row)

        used_urls = set()
        for side in sides_needed:
            selected = None
            for row in viable:
                primary = _norm_url(row.get("url")) or _norm_url(row.get("foreign_landing_url"))
                if primary and primary in used_urls:
                    continue
                selected = {
                    "provider": "Openverse",
                    "source_page_url": row.get("foreign_landing_url"),
                    "asset_url": row.get("url"),
                    "thumbnail_url": row.get("thumbnail"),
                    "creator_or_credit": row.get("creator"),
                    "license_or_usage_note": row.get("license"),
                    "source_name": row.get("source"),
                    "provenance_status": "proposal-only",
                    "independence_rationale": "Proposed from Openverse candidate pool using provenance and lexical identity checks only; retrieval scores were not inspected.",
                }
                if primary:
                    used_urls.add(primary)
                break
            proposals[side] = selected
            if selected:
                artifact["summary"]["source_slots_proposed"] += 1
            else:
                artifact["summary"]["source_slots_unresolved"] += 1

        artifact["cases"][case_id] = {
            "expected": expected,
            "sides_needed": sides_needed,
            "proposals": proposals,
        }
        artifact["summary"]["cases_reviewed"] += 1

    args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    s = artifact["summary"]
    print(f"Cases reviewed for Openverse proposals: {s['cases_reviewed']}")
    print(f"Source slots proposed: {s['source_slots_proposed']}")
    print(f"Source slots still unresolved: {s['source_slots_unresolved']}")
    print(f"Rows rejected for seeded/source collision: {s['rows_rejected_collision']}")
    print(f"Rows rejected by conservative identity gate: {s['rows_rejected_identity']}")
    print(f"Wrote proposal artifact: {args.output}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
