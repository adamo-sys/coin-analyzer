#!/usr/bin/env python3
"""Reject obvious lexical false positives from Commons two-side curation.

Scoring blind: this validator does not decode images or run retrieval. It inspects
candidate metadata only and requires numismatic evidence in the candidate title
before a provisionally selected role can move forward.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CURATED = ROOT / "two_side_gap_commons_curated.json"
OUTPUT = ROOT / "two_side_gap_commons_validated.json"

COIN_TERMS = {
    "coin", "cent", "cents", "centime", "dime", "quarter", "franc", "francs",
    "rupee", "rupees", "rupiah", "peso", "pesos", "sixpence", "half dollar",
    "dollar", "paise", "paisa", "nickel", "obverse", "reverse", "medal",
}
NON_NUMISMATIC_TERMS = {
    "parliament", "medical newsletter", "newsletter", ".pdf", "acts of the",
    "navy medical", "chapter 1-54",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value: object) -> str:
    return " ".join(re.sub(r"[^a-z0-9.]+", " ", str(value or "").casefold()).split())


def looks_numismatic(title: str) -> tuple[bool, str]:
    text = norm(title)
    if any(term in text for term in NON_NUMISMATIC_TERMS):
        return False, "obvious non-numismatic document/title"
    if any(term in text for term in COIN_TERMS):
        return True, "numismatic title term present"
    return False, "no numismatic title evidence"


def main() -> int:
    if not CURATED.is_file():
        raise SystemExit(f"missing curated candidates: {CURATED}")
    payload = load(CURATED)
    rows = payload.get("rows") or payload.get("results") or []
    if not isinstance(rows, list):
        raise SystemExit("curated artifact requires rows list")

    out_rows = []
    accepted = 0
    rejected = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "")
        candidate = row.get("selected") if isinstance(row.get("selected"), dict) else row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
        title = str(candidate.get("title") or candidate.get("page_title") or row.get("title") or "")
        if status not in {"selected", "provisionally-selected", "provisional"}:
            out_rows.append({**row, "validation_status": "not-selected"})
            continue
        ok, reason = looks_numismatic(title)
        if ok:
            accepted += 1
            out_rows.append({**row, "validation_status": "accepted-for-manual-provenance-review", "validation_reason": reason})
        else:
            rejected += 1
            out_rows.append({**row, "validation_status": "rejected-false-positive", "validation_reason": reason})

    artifact = {
        "schema": "coin-analyzer-two-side-gap-commons-validated-v1",
        "retrieval_scoring_run": False,
        "rows": out_rows,
        "summary": {
            "rows": len(out_rows),
            "accepted_for_manual_provenance_review": accepted,
            "rejected_false_positives": rejected,
        },
    }
    OUTPUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Commons curated candidate validation")
    print("Scoring blind: retrieval backend was NOT run.")
    print(f"Accepted for manual provenance review: {accepted}")
    print(f"Rejected lexical false positives: {rejected}")
    for row in out_rows:
        if row.get("validation_status") == "rejected-false-positive":
            cid = row.get("case_id")
            role = row.get("asset_role") or f"{row.get('source_group')}.{row.get('coin_side')}"
            candidate = row.get("selected") if isinstance(row.get("selected"), dict) else row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
            print(f"  - {cid} | {role} | {candidate.get('title') or candidate.get('page_title') or row.get('title')}")
    print(f"Wrote validation: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
