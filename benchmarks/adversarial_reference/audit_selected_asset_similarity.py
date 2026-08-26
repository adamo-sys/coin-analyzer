#!/usr/bin/env python3
"""Conservative perceptual-similarity audit for the assembled full pair asset set.

This pre-freeze diagnostic never runs retrieval scoring and never mutates
source_inventory_v1.json. It compares query/reference assets from the frozen 25-case
pair assembly and reports possible derivative-image reuse.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "full_pair_asset_set.json"
OUTPUT = ROOT / "selected_asset_similarity_audit.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    p = Path(value)
    if not p.is_absolute():
        p = ROOT / p
    return p if p.is_file() else None


def local_path(row: dict | None) -> Path | None:
    if not isinstance(row, dict):
        return None
    selected = row.get("selected") if isinstance(row.get("selected"), dict) else {}
    for source in (selected, row):
        for key in ("path", "asset_path", "local_path", "selected_path", "file"):
            p = resolve_path(source.get(key))
            if p:
                return p
    return None


def main() -> int:
    payload = load(INPUT)
    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        rows = []

    out_rows = []
    compared = suspicious = unavailable = represented = 0
    try:
        from PIL import Image
    except Exception:
        Image = None

    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        query = row.get("query") if isinstance(row.get("query"), dict) else None
        reference = row.get("reference") if isinstance(row.get("reference"), dict) else None
        if query or reference:
            represented += 1
        q = local_path(query)
        r = local_path(reference)
        if not q or not r or Image is None:
            missing = []
            if not q:
                missing.append("query")
            if not r:
                missing.append("reference")
            if Image is None:
                missing.append("pillow")
            out_rows.append({"case_id": case_id, "status": "not-compared", "missing": missing, "query_path": str(q) if q else None, "reference_path": str(r) if r else None})
            unavailable += 1
            continue
        try:
            def ahash(path: Path) -> int:
                with Image.open(path) as im:
                    im = im.convert("L").resize((16, 16))
                    getter = getattr(im, "get_flattened_data", None)
                    vals = list(getter()) if callable(getter) else list(im.getdata())
                mean = sum(vals) / len(vals)
                bits = 0
                for v in vals:
                    bits = (bits << 1) | int(v >= mean)
                return bits
            distance = (ahash(q) ^ ahash(r)).bit_count()
            compared += 1
            status = "suspicious-similarity" if distance <= 12 else "clear-by-ahash"
            if status.startswith("suspicious"):
                suspicious += 1
            out_rows.append({"case_id": case_id, "status": status, "ahash_distance_256": distance, "query_path": str(q), "reference_path": str(r)})
        except Exception as exc:
            unavailable += 1
            out_rows.append({"case_id": case_id, "status": "compare-error", "error": str(exc), "query_path": str(q), "reference_path": str(r)})

    artifact = {
        "schema": "coin-analyzer-selected-asset-similarity-audit-v5",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "rows": out_rows,
        "summary": {
            "cases_expected": len(rows),
            "cases_with_selected_slots": represented,
            "pairs_compared": compared,
            "suspicious_pairs": suspicious,
            "pairs_not_compared": unavailable,
        },
    }
    OUTPUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"Cases expected from frozen pair assembly: {len(rows)}")
    print(f"Cases represented in assembled assets: {represented}")
    print(f"Query/reference pairs compared: {compared}")
    print(f"Suspicious perceptual-similarity pairs: {suspicious}")
    print(f"Pairs not compared: {unavailable}")
    print(f"Wrote similarity audit: {OUTPUT}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 1 if suspicious else 0


if __name__ == "__main__":
    raise SystemExit(main())
