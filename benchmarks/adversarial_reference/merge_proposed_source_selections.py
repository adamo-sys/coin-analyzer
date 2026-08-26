#!/usr/bin/env python3
"""Merge conservative source proposals into a review-only combined proposal artifact.

This tool never mutates source_inventory_v1.json and never runs retrieval scoring.
It combines Commons and Openverse proposal artifacts, preserves unresolved slots,
and refuses conflicting proposals for the same case/side unless they point to the
same normalized source page/asset.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "manifest_v1.json"
DEFAULT_INVENTORY = ROOT / "source_inventory_v1.json"
DEFAULT_COMMONS = ROOT / "proposed_source_selections.json"
DEFAULT_OPENVERSE = ROOT / "proposed_openverse_source_selections.json"
DEFAULT_OUTPUT = ROOT / "proposed_source_selections_combined.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parts = urlsplit(value.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def _slot_key(slot: dict) -> tuple[str | None, str | None]:
    return (_norm_url(slot.get("source_page_url")), _norm_url(slot.get("asset_url")))


def _extract_cases(payload: dict) -> dict:
    for key in ("case_sources", "cases", "proposals"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _proposal_slot(case_entry: dict, side: str) -> dict | None:
    value = case_entry.get(side)
    if isinstance(value, dict):
        if value.get("status") in {"proposed", "seeded", "selected"}:
            return value
        if value.get("source_page_url") or value.get("asset_url"):
            return value
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--commons", type=Path, default=DEFAULT_COMMONS)
    parser.add_argument("--openverse", type=Path, default=DEFAULT_OPENVERSE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest = _load(args.manifest)
    inventory = _load(args.inventory)
    commons = _extract_cases(_load(args.commons))
    openverse = _extract_cases(_load(args.openverse))
    inventory_cases = inventory.get("case_sources", {}) if isinstance(inventory, dict) else {}

    result = {
        "schema": "coin-analyzer-combined-source-proposals-v1",
        "retrieval_results_inspected": False,
        "inventory_mutated": False,
        "selection_policy": "combine pre-existing conservative proposals only; no retrieval-score feedback",
        "cases": {},
        "summary": {
            "cases": 0,
            "already_seeded_slots": 0,
            "combined_proposed_slots": 0,
            "unresolved_slots": 0,
            "conflicting_slots": 0,
            "commons_slots_used": 0,
            "openverse_slots_used": 0,
        },
    }

    for case in manifest.get("cases", []):
        case_id = case["id"]
        result["summary"]["cases"] += 1
        inv_case = inventory_cases.get(case_id, {}) if isinstance(inventory_cases, dict) else {}
        commons_case = commons.get(case_id, {}) if isinstance(commons, dict) else {}
        openverse_case = openverse.get(case_id, {}) if isinstance(openverse, dict) else {}
        out_case = {"expected": case.get("expected"), "query": None, "reference": None}

        for side in ("query", "reference"):
            inv_slot = inv_case.get(side) if isinstance(inv_case, dict) else None
            if isinstance(inv_slot, dict) and inv_slot.get("status") == "seeded":
                out_case[side] = {"status": "already_seeded"}
                result["summary"]["already_seeded_slots"] += 1
                continue

            candidates: list[tuple[str, dict]] = []
            cslot = _proposal_slot(commons_case, side) if isinstance(commons_case, dict) else None
            oslot = _proposal_slot(openverse_case, side) if isinstance(openverse_case, dict) else None
            if cslot:
                candidates.append(("commons", cslot))
            if oslot:
                candidates.append(("openverse", oslot))

            if not candidates:
                out_case[side] = {"status": "unresolved"}
                result["summary"]["unresolved_slots"] += 1
                continue

            if len(candidates) == 2 and _slot_key(candidates[0][1]) != _slot_key(candidates[1][1]):
                out_case[side] = {
                    "status": "conflict",
                    "proposals": [
                        {"provider": provider, "source_page_url": slot.get("source_page_url"), "asset_url": slot.get("asset_url")}
                        for provider, slot in candidates
                    ],
                }
                result["summary"]["conflicting_slots"] += 1
                continue

            provider, slot = candidates[0]
            out_case[side] = {
                "status": "proposed",
                "provider": provider,
                "source_page_url": slot.get("source_page_url"),
                "asset_url": slot.get("asset_url"),
                "creator_or_credit": slot.get("creator_or_credit"),
                "license_or_usage_note": slot.get("license_or_usage_note"),
                "retrieved_at": slot.get("retrieved_at"),
                "independence_rationale": slot.get("independence_rationale"),
            }
            result["summary"]["combined_proposed_slots"] += 1
            result["summary"][f"{provider}_slots_used"] += 1

        result["cases"][case_id] = out_case

    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = result["summary"]
    print(f"Cases reviewed: {summary['cases']}")
    print(f"Already-seeded source slots: {summary['already_seeded_slots']}")
    print(f"Combined proposed source slots: {summary['combined_proposed_slots']}")
    print(f"Unresolved source slots: {summary['unresolved_slots']}")
    print(f"Conflicting source slots: {summary['conflicting_slots']}")
    print(f"Commons proposals used: {summary['commons_slots_used']}")
    print(f"Openverse proposals used: {summary['openverse_slots_used']}")
    print(f"Wrote combined proposal artifact: {args.output}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
