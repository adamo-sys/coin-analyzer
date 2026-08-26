#!/usr/bin/env python3
"""Assemble a full local query/reference asset set for the frozen 25-case benchmark.

This bounded pre-retrieval step combines:
- frozen Benchmark v2 query images for reused identities;
- query/reference assets already selected by the adversarial preparation flow.

It does not alter case identities, mutate source_inventory_v1.json, or run retrieval
scoring. Missing frozen-v2 query images remain explicit blockers.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
MANIFEST = ROOT / "manifest_v1.json"
SELECTED = ROOT / "unique_final_assets.json"
V2_MANIFEST = REPO / "benchmarks" / "v2" / "manifest.json"
OUTPUT = ROOT / "full_pair_asset_set.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def selected_rows() -> dict[tuple[str, str], dict]:
    payload = load(SELECTED)
    rows = payload.get("results") or payload.get("slots") or payload.get("rows") or []
    out: dict[tuple[str, str], dict] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        side = str(row.get("side") or "")
        if case_id and side in {"query", "reference"} and row.get("status") == "selected":
            out[(case_id, side)] = row
    return out


def v2_queries() -> dict[str, dict]:
    if not V2_MANIFEST.is_file():
        return {}
    payload = load(V2_MANIFEST)
    rows = payload.get("cases") or []
    out: dict[str, dict] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("id") or row.get("case_id") or "")
        if not case_id:
            continue
        for role in ("obverse", "reverse"):
            entry = row.get(role)
            if not isinstance(entry, dict):
                continue
            rel = str(entry.get("path") or "")
            if not rel:
                continue
            path = (V2_MANIFEST.parent / rel).resolve()
            if path.is_file():
                out[case_id] = {
                    "mode": "frozen-v2-query",
                    "role": role,
                    "local_path": str(path),
                    "source_page_url": entry.get("source_page"),
                    "source_url": entry.get("source_file_url"),
                    "source_sha256": entry.get("source_sha256"),
                }
                break
    return out


def main() -> int:
    manifest = load(MANIFEST)
    selected = selected_rows()
    v2 = v2_queries()
    rows = []
    missing = []

    for case in manifest.get("cases", []):
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or case.get("case_id") or "")
        source_status = str(case.get("source_status") or "")
        query = selected.get((case_id, "query"))
        reference = selected.get((case_id, "reference"))

        if query is None and source_status.startswith("reuse-frozen-v2-query"):
            q = v2.get(case_id)
            if q:
                query = {"case_id": case_id, "side": "query", "status": "selected", "selected": q}

        missing_sides = []
        if query is None:
            missing_sides.append("query")
        if reference is None:
            missing_sides.append("reference")
        if missing_sides:
            missing.append({"case_id": case_id, "missing": missing_sides})

        rows.append({"case_id": case_id, "query": query, "reference": reference, "missing": missing_sides})

    artifact = {
        "schema": "coin-analyzer-full-pair-asset-set-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "rows": rows,
        "summary": {
            "cases": len(rows),
            "complete_pairs": sum(1 for r in rows if not r["missing"]),
            "incomplete_pairs": sum(1 for r in rows if r["missing"]),
            "missing_query_sides": sum("query" in r["missing"] for r in rows),
            "missing_reference_sides": sum("reference" in r["missing"] for r in rows),
        },
        "missing": missing,
    }
    OUTPUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    s = artifact["summary"]
    print(f"Frozen cases: {s['cases']}")
    print(f"Complete query/reference pairs: {s['complete_pairs']}")
    print(f"Incomplete pairs: {s['incomplete_pairs']}")
    print(f"Missing query sides: {s['missing_query_sides']}")
    print(f"Missing reference sides: {s['missing_reference_sides']}")
    for i, row in enumerate(missing, 1):
        print(f"[{i}/{len(missing)}] {row['case_id']} | missing={','.join(row['missing'])}")
    print(f"Wrote full pair asset set: {OUTPUT}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
