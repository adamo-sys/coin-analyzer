#!/usr/bin/env python3
"""Conservative perceptual-similarity audit for selected adversarial assets.

This pre-freeze diagnostic never runs retrieval scoring and never mutates
source_inventory_v1.json. It compares selected query/reference assets when both
local paths are available and reports possible derivative-image reuse. The frozen
25-case manifest defines the case universe so cases with only one selected slot in
unique_final_assets.json are still reported explicitly rather than disappearing.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "unique_final_assets.json"
MANIFEST = ROOT / "manifest_v1.json"
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


def local_path(row: dict) -> Path | None:
    selected = row.get("selected") if isinstance(row.get("selected"), dict) else {}
    for source in (selected, row):
        for key in ("path", "asset_path", "local_path", "selected_path", "file"):
            p = resolve_path(source.get(key))
            if p:
                return p
    return None


def case_and_side(row: dict) -> tuple[str, str]:
    case_id = str(row.get("case_id") or "")
    side = str(row.get("side") or "")
    if case_id and side in {"query", "reference"}:
        return case_id, side
    sid = str(row.get("slot_id") or row.get("slot") or row.get("id") or "")
    if sid.endswith(".query"):
        return sid[:-6], "query"
    if sid.endswith(".reference"):
        return sid[:-10], "reference"
    return "", ""


def manifest_case_ids() -> list[str]:
    if not MANIFEST.is_file():
        return []
    payload = load(MANIFEST)
    out: list[str] = []
    for key in ("cases", "items", "results"):
        rows = payload.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                case_id = str(row.get("case_id") or row.get("id") or "")
                if case_id and case_id not in out:
                    out.append(case_id)
        break
    return out


def main() -> int:
    payload = load(INPUT)
    rows = payload.get("rows") or payload.get("slots") or payload.get("results") or payload.get("selected") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    by_case: dict[str, dict[str, dict]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        case_id, side = case_and_side(row)
        if case_id and side:
            by_case.setdefault(case_id, {})[side] = row

    case_ids = manifest_case_ids()
    if not case_ids:
        case_ids = sorted(by_case)

    out_rows = []
    compared = suspicious = unavailable = 0
    try:
        from PIL import Image
    except Exception:
        Image = None

    for case_id in case_ids:
        pair = by_case.get(case_id, {})
        q = local_path(pair.get("query", {}))
        r = local_path(pair.get("reference", {}))
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
            a, b = ahash(q), ahash(r)
            distance = (a ^ b).bit_count()
            compared += 1
            status = "suspicious-similarity" if distance <= 12 else "clear-by-ahash"
            if status.startswith("suspicious"):
                suspicious += 1
            out_rows.append({"case_id": case_id, "status": status, "ahash_distance_256": distance, "query_path": str(q), "reference_path": str(r)})
        except Exception as exc:
            unavailable += 1
            out_rows.append({"case_id": case_id, "status": "compare-error", "error": str(exc), "query_path": str(q), "reference_path": str(r)})

    artifact = {"schema": "coin-analyzer-selected-asset-similarity-audit-v4", "retrieval_results_inspected": False, "inventory_modified": False, "rows": out_rows, "summary": {"cases_expected": len(case_ids), "cases_with_selected_slots": len(by_case), "pairs_compared": compared, "suspicious_pairs": suspicious, "pairs_not_compared": unavailable}}
    OUTPUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"Cases expected from frozen manifest: {len(case_ids)}")
    print(f"Cases represented in selected assets: {len(by_case)}")
    print(f"Query/reference pairs compared: {compared}")
    print(f"Suspicious perceptual-similarity pairs: {suspicious}")
    print(f"Pairs not compared: {unavailable}")
    print(f"Wrote similarity audit: {OUTPUT}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 1 if suspicious else 0


if __name__ == "__main__":
    raise SystemExit(main())
