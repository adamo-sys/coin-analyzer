#!/usr/bin/env python3
"""Propose conservative Commons sources without mutating the frozen inventory.

Selection uses provenance/lexical identity checks only. It never invokes image
retrieval, similarity scoring, or benchmark evaluation. Proposed query/reference
assets must be distinct and must not collide with already-seeded inventory URLs.
The output remains a review artifact; a later import step may apply approved rows.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_REVIEW = ROOT / "commons_source_review.json"
DEFAULT_INVENTORY = ROOT / "source_inventory_v1.json"
DEFAULT_OUTPUT = ROOT / "proposed_source_selections.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parts = urlsplit(value.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def _plain(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _tokens(value: object) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", _plain(value)))


def _identity_gate(expected: dict, row: dict) -> tuple[bool, list[str]]:
    haystack = " ".join(
        _plain(row.get(key))
        for key in ("title", "description", "description_url")
    )
    tokens = _tokens(haystack)
    reasons: list[str] = []

    year = str(expected.get("year") or "").strip().lower()
    if year and year not in haystack:
        reasons.append(f"year {year} not present")

    country_tokens = _tokens(expected.get("country"))
    if country_tokens and not (country_tokens & tokens):
        # Commons titles for US coins often say United States, U.S., or American.
        country = _plain(expected.get("country"))
        aliases = {
            "united states": {"us", "usa", "american", "united", "states"},
            "switzerland": {"swiss", "switzerland"},
            "philippines": {"philippine", "philippines"},
        }.get(country, set())
        if not (aliases & tokens):
            reasons.append("country token not present")

    denomination_tokens = {
        token for token in _tokens(expected.get("denomination"))
        if token not in {"cent", "cents", "pence", "francs", "rupee", "rupiah", "pesos"}
    }
    if denomination_tokens and not (denomination_tokens & tokens):
        reasons.append("denomination numeral/token not present")

    return not reasons, reasons


def _candidate_urls(row: dict) -> set[str]:
    return {
        value for value in (
            _norm_url(row.get("original_url")),
            _norm_url(row.get("thumbnail_url")),
            _norm_url(row.get("description_url")),
        ) if value
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    review = _load(args.review)
    inventory = _load(args.inventory)
    inv_cases = inventory.get("case_sources", {})
    output = {
        "schema": "coin-analyzer-proposed-source-selections-v1",
        "retrieval_results_inspected": False,
        "selection_basis": "Commons provenance plus conservative lexical identity gate only",
        "inventory_modified": False,
        "cases": {},
        "summary": {
            "cases": 0,
            "proposed_slots": 0,
            "unresolved_slots": 0,
            "rejected_collision_rows": 0,
            "rejected_identity_rows": 0,
        },
    }

    for case_id, case in (review.get("cases") or {}).items():
        expected = case.get("expected") or {}
        inv = inv_cases.get(case_id, {}) if isinstance(inv_cases, dict) else {}
        occupied_urls: set[str] = set()
        for side in ("query", "reference"):
            slot = inv.get(side) if isinstance(inv, dict) else None
            if isinstance(slot, dict) and slot.get("status") == "seeded":
                occupied_urls |= {
                    value for value in (
                        _norm_url(slot.get("asset_url")),
                        _norm_url(slot.get("source_page_url")),
                    ) if value
                }

        eligible: list[dict] = []
        rejected: list[dict] = []
        for row in case.get("candidates", []):
            urls = _candidate_urls(row)
            if row.get("obvious_query_collision") or (occupied_urls & urls):
                rejected.append({"title": row.get("title"), "reason": "seeded-source collision"})
                output["summary"]["rejected_collision_rows"] += 1
                continue
            ok, reasons = _identity_gate(expected, row)
            if not ok:
                rejected.append({"title": row.get("title"), "reason": "; ".join(reasons)})
                output["summary"]["rejected_identity_rows"] += 1
                continue
            eligible.append(row)

        proposals: dict[str, dict | None] = {}
        used_urls = set(occupied_urls)
        for side in case.get("sides_needed") or []:
            selected = None
            for row in eligible:
                urls = _candidate_urls(row)
                if not urls or used_urls & urls:
                    continue
                selected = {
                    "title": row.get("title"),
                    "source_page_url": row.get("description_url"),
                    "asset_url": row.get("thumbnail_url") or row.get("original_url"),
                    "original_url": row.get("original_url"),
                    "provider": "Wikimedia Commons",
                    "creator_or_credit": row.get("artist") or "unknown/see source page",
                    "license_or_usage_note": row.get("license") or "see source page",
                    "independence_rationale": "Selected without retrieval scoring; distinct from seeded and other proposed source URLs for this case.",
                    "review_required": True,
                }
                used_urls |= urls
                break
            proposals[side] = selected
            if selected:
                output["summary"]["proposed_slots"] += 1
            else:
                output["summary"]["unresolved_slots"] += 1

        output["cases"][case_id] = {
            "expected": expected,
            "proposals": proposals,
            "eligible_candidate_count": len(eligible),
            "rejected": rejected,
        }
        output["summary"]["cases"] += 1

    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = output["summary"]
    print(f"Cases reviewed for proposals: {summary['cases']}")
    print(f"Source slots proposed: {summary['proposed_slots']}")
    print(f"Source slots still unresolved: {summary['unresolved_slots']}")
    print(f"Rows rejected for seeded/source collision: {summary['rejected_collision_rows']}")
    print(f"Rows rejected by conservative identity gate: {summary['rejected_identity_rows']}")
    print(f"Wrote proposal artifact: {args.output}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
