#!/usr/bin/env python3
"""Plan the correction from one-asset pairs to explicit two-side assets.

Scoring blind: this script does not decode benchmark images and does not run the
retrieval backend. It inspects only local JSON metadata and filesystem paths.

The historical 36766dd scorer requires:
  query.obverse, query.reverse, reference.obverse, reference.reverse
for every frozen identity. The current FREEZE.json instead contains one query
asset and one reference asset per identity.

This planner inventories what can be resolved from existing local benchmark
metadata without inventing a side split. It deliberately treats a single image
asset as ambiguous unless metadata explicitly names an obverse/reverse pair.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
MANIFEST = ROOT / "manifest_v1.json"
FREEZE = ROOT / "FREEZE.json"
V2 = REPO / "benchmarks" / "v2" / "manifest.json"
OUTPUT = ROOT / "two_side_freeze_correction_plan.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(path: Path, base: Path) -> str | None:
    if not path.is_absolute():
        path = (base / path).resolve()
    else:
        path = path.resolve()
    return str(path) if path.is_file() else None


def v2_query_pairs() -> dict[str, dict]:
    if not V2.is_file():
        return {}
    payload = load(V2)
    out: dict[str, dict] = {}
    for row in payload.get("cases", []):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("id") or row.get("case_id") or "")
        obv = row.get("obverse") if isinstance(row.get("obverse"), dict) else {}
        rev = row.get("reverse") if isinstance(row.get("reverse"), dict) else {}
        op = obv.get("path")
        rp = rev.get("path")
        if not case_id or not isinstance(op, str) or not isinstance(rp, str):
            continue
        opath = resolve(Path(op), V2.parent)
        rpath = resolve(Path(rp), V2.parent)
        if opath and rpath:
            out[case_id] = {
                "obverse": opath,
                "reverse": rpath,
                "source": "benchmarks/v2/manifest.json",
            }
    return out


def frozen_sides() -> dict[str, dict]:
    payload = load(FREEZE)
    out: dict[str, dict] = {}
    for row in payload.get("cases", []):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        sides = row.get("sides") if isinstance(row.get("sides"), dict) else {}
        out[case_id] = sides
    return out


def main() -> int:
    if not MANIFEST.is_file() or not FREEZE.is_file():
        raise SystemExit("manifest_v1.json and FREEZE.json are required")

    manifest = load(MANIFEST)
    frozen = frozen_sides()
    v2_pairs = v2_query_pairs()
    rows = []

    for case in manifest.get("cases", []):
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or case.get("case_id") or "")
        source_status = str(case.get("source_status") or "")
        query_pair = v2_pairs.get(case_id) if source_status.startswith("reuse-frozen-v2-query") else None
        frozen_row = frozen.get(case_id, {})
        rows.append({
            "case_id": case_id,
            "source_status": source_status,
            "query_pair": query_pair,
            "reference_pair": None,
            "current_one_asset_query": frozen_row.get("query"),
            "current_one_asset_reference": frozen_row.get("reference"),
            "missing": [
                *( [] if query_pair else ["query.obverse", "query.reverse"] ),
                "reference.obverse",
                "reference.reverse",
            ],
            "note": (
                "Reused v2 query has explicit obverse/reverse metadata; reference still requires explicit two-side assets."
                if query_pair else
                "Neither side can be inferred from the current one-asset freeze without an explicit split/source pair."
            ),
        })

    summary = {
        "cases": len(rows),
        "query_pairs_resolved_from_v2": sum(bool(r["query_pair"]) for r in rows),
        "query_pairs_unresolved": sum(not bool(r["query_pair"]) for r in rows),
        "reference_pairs_resolved": 0,
        "reference_pairs_unresolved": len(rows),
        "retrieval_scoring_run": False,
    }
    OUTPUT.write_text(json.dumps({"schema":"coin-analyzer-two-side-freeze-correction-plan-v1","rows":rows,"summary":summary}, indent=2) + "\n", encoding="utf-8")

    print("Two-side freeze correction planner")
    print("Scoring blind: no benchmark image bytes were decoded.")
    print(f"Frozen cases: {summary['cases']}")
    print(f"Query pairs resolved from Benchmark v2 metadata: {summary['query_pairs_resolved_from_v2']}")
    print(f"Query pairs still unresolved: {summary['query_pairs_unresolved']}")
    print(f"Reference pairs still unresolved: {summary['reference_pairs_unresolved']}")
    print(f"Wrote plan: {OUTPUT}")
    print("Retrieval scoring was NOT run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
