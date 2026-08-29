#!/usr/bin/env python3
"""Inventory explicit two-side assets already present locally without scoring.

Scoring blind: this script reads JSON metadata and filesystem paths only. It does
not decode benchmark images and does not invoke the frozen retrieval backend.

Sources inspected:
- Benchmark v2 manifest for explicit query obverse/reverse pairs.
- Legacy independent-reference pilot manifests/caches when present.
- Current one-asset freeze only as provenance context, never as a side split.

The output is a gap inventory for the corrected two-side freeze. Ambiguous
single-image assets remain unresolved rather than being split heuristically.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
MANIFEST = ROOT / "manifest_v1.json"
V2 = REPO / "benchmarks" / "v2" / "manifest.json"
REF_MANIFEST = REPO / "benchmarks" / "v2" / "reference_pilot" / "manifest.json"
OUTPUT = ROOT / "two_side_existing_asset_inventory.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(raw: str, base: Path) -> str | None:
    path = Path(raw)
    if not path.is_absolute():
        path = (base / path).resolve()
    else:
        path = path.resolve()
    return str(path) if path.is_file() else None


def v2_queries() -> dict[str, dict]:
    if not V2.is_file():
        return {}
    out: dict[str, dict] = {}
    for row in load(V2).get("cases", []):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("id") or row.get("case_id") or "")
        obv = row.get("obverse") if isinstance(row.get("obverse"), dict) else {}
        rev = row.get("reverse") if isinstance(row.get("reverse"), dict) else {}
        op = obv.get("path")
        rp = rev.get("path")
        if not case_id or not isinstance(op, str) or not isinstance(rp, str):
            continue
        opath = resolve(op, V2.parent)
        rpath = resolve(rp, V2.parent)
        if opath and rpath:
            out[case_id] = {
                "obverse": opath,
                "reverse": rpath,
                "source": "benchmarks/v2/manifest.json",
            }
    return out


def legacy_references() -> dict[str, dict]:
    if not REF_MANIFEST.is_file():
        return {}
    payload = load(REF_MANIFEST)
    root = REF_MANIFEST.parent
    out: dict[str, dict] = {}
    for row in payload.get("candidates", []):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("id") or "")
        obv = row.get("obverse")
        rev = row.get("reverse")
        if not case_id or not isinstance(obv, list) or not isinstance(rev, list) or not obv or not rev:
            continue
        obv_paths = [resolve(str(p), root) for p in obv]
        rev_paths = [resolve(str(p), root) for p in rev]
        obv_paths = [p for p in obv_paths if p]
        rev_paths = [p for p in rev_paths if p]
        if obv_paths and rev_paths:
            out[case_id] = {
                "obverse": obv_paths,
                "reverse": rev_paths,
                "source": "benchmarks/v2/reference_pilot/manifest.json",
            }
    return out


def main() -> int:
    if not MANIFEST.is_file():
        raise SystemExit(f"missing frozen manifest: {MANIFEST}")
    frozen = load(MANIFEST).get("cases", [])
    q = v2_queries()
    r = legacy_references()
    rows = []
    for case in frozen:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or "")
        query_pair = q.get(case_id)
        reference_pair = r.get(case_id)
        missing = []
        if not query_pair:
            missing += ["query.obverse", "query.reverse"]
        if not reference_pair:
            missing += ["reference.obverse", "reference.reverse"]
        rows.append({
            "case_id": case_id,
            "query_pair": query_pair,
            "reference_pair": reference_pair,
            "missing": missing,
        })
    summary = {
        "cases": len(rows),
        "query_pairs_resolved": sum(bool(row["query_pair"]) for row in rows),
        "reference_pairs_resolved": sum(bool(row["reference_pair"]) for row in rows),
        "fully_two_side_ready": sum(bool(row["query_pair"]) and bool(row["reference_pair"]) for row in rows),
        "cases_with_gaps": sum(bool(row["missing"]) for row in rows),
        "retrieval_scoring_run": False,
    }
    OUTPUT.write_text(json.dumps({"schema":"coin-analyzer-existing-two-side-asset-inventory-v1","rows":rows,"summary":summary}, indent=2) + "\n", encoding="utf-8")
    print("Existing two-side asset inventory")
    print("Scoring blind: no benchmark image bytes were decoded.")
    print(f"Frozen cases: {summary['cases']}")
    print(f"Query pairs resolved: {summary['query_pairs_resolved']}")
    print(f"Reference pairs resolved: {summary['reference_pairs_resolved']}")
    print(f"Fully two-side ready: {summary['fully_two_side_ready']}")
    print(f"Cases with gaps: {summary['cases_with_gaps']}")
    for row in rows:
        if row["missing"]:
            print(f"  - {row['case_id']} | missing={','.join(row['missing'])}")
    print(f"Wrote inventory: {OUTPUT}")
    print("Retrieval scoring was NOT run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
