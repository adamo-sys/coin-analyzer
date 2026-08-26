#!/usr/bin/env python3
"""Isolate the final page-discovery gaps for the corrected two-side benchmark.

Scoring blind: no images are decoded or downloaded and retrieval is not run.
This script consumes targeted_two_side_acquisition_manifest.json and emits only
roles still lacking an identity-specific page candidate. It groups them by case
so the remaining web work can be done surgically rather than through another
large search sweep.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "targeted_two_side_acquisition_manifest.json"
OUTPUT = ROOT / "final_four_page_discovery_plan.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not INPUT.is_file():
        raise SystemExit(f"missing targeted manifest: {INPUT}")

    payload = load(INPUT)
    roles = payload.get("roles") or []
    if not isinstance(roles, list):
        raise SystemExit("targeted manifest requires roles[]")

    unresolved = []
    for row in roles:
        if not isinstance(row, dict):
            continue
        if row.get("status") != "page-discovery-still-required":
            continue
        unresolved.append({
            "case_id": row.get("case_id"),
            "expected": row.get("expected"),
            "source_group": row.get("source_group"),
            "coin_side": row.get("coin_side"),
            "asset_role": row.get("asset_role"),
            "requirements": row.get("requirements"),
        })

    cases: dict[str, dict] = {}
    for row in unresolved:
        case_id = str(row.get("case_id") or "")
        if not case_id:
            continue
        case = cases.setdefault(case_id, {
            "case_id": case_id,
            "expected": row.get("expected"),
            "missing_roles": [],
            "discovery_guidance": {
                "prefer_identity_specific_numismatic_page": True,
                "prefer_exact_year_page_or_listing": True,
                "explicit_obverse_reverse_evidence_required_before_asset_import": True,
                "query_reference_independence_required": True,
                "do_not_use_retrieval_scores": True,
            },
        })
        case["missing_roles"].append(row.get("asset_role"))

    ordered = [cases[key] for key in sorted(cases)]
    artifact = {
        "schema": "coin-analyzer-final-four-page-discovery-plan-v1",
        "retrieval_scoring_run": False,
        "roles": unresolved,
        "cases": ordered,
        "summary": {
            "unresolved_roles": len(unresolved),
            "unresolved_cases": len(ordered),
            "case_ids": [row["case_id"] for row in ordered],
        },
    }
    OUTPUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    s = artifact["summary"]
    print("Final four page-discovery planner")
    print("Scoring blind: no images were decoded/downloaded and retrieval was NOT run.")
    print(f"Unresolved roles: {s['unresolved_roles']}")
    print(f"Unresolved cases: {s['unresolved_cases']}")
    for case in ordered:
        print(f"  - {case['case_id']} | missing={','.join(case['missing_roles'])}")
    print(f"Wrote plan: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
