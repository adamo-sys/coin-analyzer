#!/usr/bin/env python3
"""Verify that a frozen adversarial dataset is structurally compatible with 36766dd.

The historical backend's candidate score is a geometric mean of independently
scored obverse and reverse images. A freeze containing only one query image and
one reference image per identity cannot be evaluated by that backend unchanged.

This guard is scoring-blind: it opens JSON metadata only and never decodes images
or computes retrieval scores.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FREEZE = ROOT / "FREEZE.json"
PAIR_SET = ROOT / "full_pair_asset_set.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def has_two_sides(slot: object) -> bool:
    if not isinstance(slot, dict):
        return False
    # Accept either direct obverse/reverse keys or a nested selected record.
    obj = slot.get("selected") if isinstance(slot.get("selected"), dict) else slot
    return bool(obj.get("obverse")) and bool(obj.get("reverse"))


def main() -> int:
    print("Frozen backend compatibility check")
    print("Scoring blind: no benchmark image bytes will be decoded.")

    if not FREEZE.is_file():
        print(f"BLOCKED: missing freeze: {FREEZE}")
        return 2
    if not PAIR_SET.is_file():
        print(f"BLOCKED: missing pair set: {PAIR_SET}")
        return 2

    freeze = load(FREEZE)
    pair_set = load(PAIR_SET)

    policy = freeze.get("evaluation_policy") or {}
    expected_backend = str(policy.get("retrieval_backend_frozen") or "")
    if expected_backend != "opencv-orb-plus-hsv-histogram-rotation-invariant":
        print(f"BLOCKED: unexpected frozen backend policy: {expected_backend!r}")
        return 2

    rows = pair_set.get("rows") or []
    incompatible: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "<unknown>")
        query = row.get("query")
        reference = row.get("reference")
        if not has_two_sides(query) or not has_two_sides(reference):
            incompatible.append(case_id)

    print(f"Frozen cases inspected: {len(rows) if isinstance(rows, list) else 0}")
    print(f"Cases structurally compatible with two-side scorer: {len(rows) - len(incompatible) if isinstance(rows, list) else 0}")
    print(f"Cases incompatible with two-side scorer: {len(incompatible)}")

    if incompatible:
        print("\nPROTOCOL MISMATCH DETECTED")
        print("The recovered 36766dd backend computes:")
        print("  sqrt(obverse_similarity * reverse_similarity)")
        print("but the current frozen pair set stores one query asset and one reference asset per identity.")
        print("Running Top-1 now would require changing the historical backend or inventing a side split,")
        print("which would violate the frozen 'unchanged backend' policy.")
        print("\nAffected cases:")
        for case_id in incompatible:
            print(f"  - {case_id}")
        print("\nRetrieval scoring remains BLOCKED.")
        print("Required correction: create a new pre-score freeze version with explicit obverse/reverse")
        print("query and reference assets for every identity, then rerun provenance/similarity gates.")
        return 3

    print("Compatibility clear: all cases expose query/reference obverse and reverse assets.")
    print("The recovered 36766dd backend can be used unchanged.")
    print("Retrieval scoring was NOT run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
