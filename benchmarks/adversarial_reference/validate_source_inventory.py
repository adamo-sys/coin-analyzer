#!/usr/bin/env python3
"""Validate adversarial reference acquisition metadata before benchmark freeze.

This tool deliberately does not run retrieval. It checks that the source inventory
matches the frozen identity manifest and that each query/reference slot has enough
provenance to permit a later FREEZE.json build.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "manifest_v1.json"
DEFAULT_INVENTORY = ROOT / "source_inventory_v1.json"
REQUIRED_FIELDS = (
    "source_page_url",
    "asset_url",
    "provider",
    "creator_or_credit",
    "license_or_usage_note",
    "retrieved_at",
    "independence_rationale",
)


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _valid_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _slot_errors(case_id: str, side: str, slot: object) -> list[str]:
    prefix = f"{case_id}.{side}"
    if not isinstance(slot, dict):
        return [f"{prefix}: missing provenance object"]
    if slot.get("status") == "unavailable":
        reason = slot.get("unavailable_reason")
        return [] if isinstance(reason, str) and reason.strip() else [f"{prefix}: unavailable without reason"]
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        value = slot.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{prefix}: missing {field}")
    for field in ("source_page_url", "asset_url"):
        value = slot.get(field)
        if value and not _valid_url(value):
            errors.append(f"{prefix}: invalid {field}")
    return errors


def validate(manifest: dict, inventory: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    frozen_ids = [case["id"] for case in manifest.get("cases", [])]
    entries = inventory.get("case_sources", {})
    if not isinstance(entries, dict):
        return ["inventory.case_sources must be an object keyed by frozen case ID"], warnings
    inventory_ids = list(entries)
    missing = [case_id for case_id in frozen_ids if case_id not in entries]
    extra = [case_id for case_id in inventory_ids if case_id not in set(frozen_ids)]
    if missing:
        errors.append("missing frozen cases: " + ", ".join(missing))
    if extra:
        errors.append("unexpected cases: " + ", ".join(extra))
    for case_id in frozen_ids:
        entry = entries.get(case_id)
        if not isinstance(entry, dict):
            continue
        errors.extend(_slot_errors(case_id, "query", entry.get("query")))
        errors.extend(_slot_errors(case_id, "reference", entry.get("reference")))
        query = entry.get("query") if isinstance(entry.get("query"), dict) else {}
        reference = entry.get("reference") if isinstance(entry.get("reference"), dict) else {}
        q_asset = query.get("asset_url")
        r_asset = reference.get("asset_url")
        if q_asset and r_asset and q_asset == r_asset:
            errors.append(f"{case_id}: query/reference asset_url is identical")
        if query.get("source_asset_sha256") and query.get("source_asset_sha256") == reference.get("source_asset_sha256"):
            errors.append(f"{case_id}: query/reference source_asset_sha256 is identical")
        if query.get("status") == "unavailable" or reference.get("status") == "unavailable":
            warnings.append(f"{case_id}: unavailable source recorded; benchmark cannot yet freeze at 25/25")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    args = parser.parse_args()
    manifest = _load(args.manifest)
    inventory = _load(args.inventory)
    errors, warnings = validate(manifest, inventory)
    print(f"Frozen cases: {len(manifest.get('cases', []))}")
    print(f"Inventory entries: {len(inventory.get('case_sources', {}))}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        print(f"Source inventory NOT freeze-ready: {len(errors)} issue(s)")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Source inventory is provenance-complete and eligible for freeze generation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
