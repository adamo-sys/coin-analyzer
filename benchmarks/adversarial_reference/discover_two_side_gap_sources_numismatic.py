#!/usr/bin/env python3
"""Build a targeted, scoring-blind numismatic source-discovery queue.

Consumes the frozen two-side gap acquisition queue and emits a provider-specific
search plan for unresolved roles. This script does not download images, decode
benchmark images, alter frozen identities, or invoke retrieval scoring.

It deliberately avoids broad search-engine scraping. Each role receives compact
queries for known numismatic providers and authoritative collections so later
acquisition can be bounded and provenance-aware.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "two_side_gap_acquisition_queue.json"
OUTPUT = ROOT / "two_side_gap_numismatic_discovery_plan.json"

PROVIDERS = (
    ("numista", "en.numista.com"),
    ("coinsandcanada", "coinsandcanada.com"),
    ("numicanada", "numicanada.com"),
    ("ucoin", "en.ucoin.net"),
    ("ngc", "ngccoin.com"),
    ("pcgs", "pcgs.com"),
    ("usmint", "usmint.gov"),
    ("royalmintmuseum", "royalmintmuseum.org.uk"),
    ("museum", "collections"),
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def identity_terms(expected: dict) -> str:
    country = str(expected.get("country") or "").strip()
    denomination = str(expected.get("denomination") or "").strip()
    year = str(expected.get("year") or "").strip()
    return " ".join(x for x in (country, denomination, year) if x)


def main() -> int:
    if not QUEUE.is_file():
        raise SystemExit(f"missing queue: {QUEUE}")
    payload = load(QUEUE)
    rows = payload.get("queue") or []
    if not isinstance(rows, list):
        raise SystemExit("queue must contain a list under 'queue'")

    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        expected = row.get("expected") if isinstance(row.get("expected"), dict) else {}
        source_group = str(row.get("source_group") or "")
        coin_side = str(row.get("coin_side") or "")
        if source_group not in {"query", "reference"} or coin_side not in {"obverse", "reverse"}:
            continue
        terms = identity_terms(expected)
        queries = []
        for provider, domain in PROVIDERS:
            queries.append({
                "provider": provider,
                "domain_hint": domain,
                "query": f'{terms} {coin_side} coin',
                "requirements": {
                    "must_match_identity": True,
                    "must_show_explicit_side": coin_side,
                    "source_page_required": True,
                    "asset_url_required": True,
                    "query_reference_independence_required": True,
                    "no_composite_split_without_explicit_source_metadata": True,
                },
            })
        out.append({
            "case_id": case_id,
            "source_group": source_group,
            "coin_side": coin_side,
            "expected": expected,
            "queries": queries,
            "status": "targeted-source-discovery-required",
        })

    artifact = {
        "schema": "coin-analyzer-two-side-numismatic-discovery-plan-v1",
        "retrieval_scoring_run": False,
        "broad_search_engine_scraping_forbidden": True,
        "roles": out,
        "summary": {
            "roles": len(out),
            "query_roles": sum(r["source_group"] == "query" for r in out),
            "reference_roles": sum(r["source_group"] == "reference" for r in out),
            "provider_queries": sum(len(r["queries"]) for r in out),
        },
    }
    OUTPUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    s = artifact["summary"]
    print("Targeted numismatic two-side source discovery plan")
    print("Scoring blind: retrieval backend was NOT run and no images were downloaded.")
    print(f"Roles planned: {s['roles']}")
    print(f"  Query roles: {s['query_roles']}")
    print(f"  Reference roles: {s['reference_roles']}")
    print(f"Provider-specific searches planned: {s['provider_queries']}")
    print(f"Wrote plan: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
