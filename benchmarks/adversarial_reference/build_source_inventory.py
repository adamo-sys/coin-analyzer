#!/usr/bin/env python3
"""Create/refresh empty provenance slots for every frozen adversarial case.

Existing per-case metadata is preserved. Retrieval is never invoked here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "manifest_v1.json"
DEFAULT_OUTPUT = ROOT / "source_inventory_v1.json"


def _empty_slot() -> dict:
    return {
        "status": "pending",
        "source_page_url": None,
        "asset_url": None,
        "provider": None,
        "creator_or_credit": None,
        "license_or_usage_note": None,
        "retrieved_at": None,
        "source_asset_sha256": None,
        "independence_rationale": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    previous = {}
    if args.output.exists():
        previous = json.loads(args.output.read_text(encoding="utf-8")).get("case_sources", {})
    case_sources = {}
    for case in manifest["cases"]:
        case_id = case["id"]
        old = previous.get(case_id, {}) if isinstance(previous.get(case_id), dict) else {}
        case_sources[case_id] = {
            "expected": case.get("expected"),
            "source_status": case.get("source_status"),
            "query": old.get("query", _empty_slot()),
            "reference": old.get("reference", _empty_slot()),
        }
    payload = {
        "schema": "coin-analyzer-adversarial-reference-source-inventory-v2",
        "protocol_version": "v1.0",
        "frozen_manifest": args.manifest.name,
        "retrieval_results_inspected": False,
        "case_sources": case_sources,
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Frozen source slots: {len(case_sources)} cases / {len(case_sources) * 2} sides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
