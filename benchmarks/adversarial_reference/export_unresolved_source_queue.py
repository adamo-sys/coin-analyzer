#!/usr/bin/env python3
"""Export unresolved/conflicting adversarial source slots for targeted acquisition.

This is acquisition-only tooling. It reads the combined conservative proposal audit,
identifies slots that still need a source decision, and emits provider-specific search
queries for manual/next-provider discovery. It does not run retrieval scoring and it
does not mutate source_inventory_v1.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "manifest_v1.json"
DEFAULT_COMBINED = ROOT / "proposed_source_selections_combined.json"
DEFAULT_OUTPUT = ROOT / "unresolved_source_queue.json"

TRUSTED_SEARCH_TARGETS = (
    ("Numista", "numista.com"),
    ("NGC", "ngccoin.com"),
    ("PCGS", "pcgs.com"),
    ("British Museum", "britishmuseum.org"),
    ("Coins and Canada", "coinsandcanada.com"),
    ("Smithsonian", "si.edu"),
)

ALIASES = {
    "canada-5-cents-1964": ["Canada 5 cents 1964", "Canada nickel 1964"],
    "canada-10-cents-1955": ["Canada 10 cents 1955", "Canada dime 1955"],
    "canada-25-cents-1967": ["Canada 25 cents 1967", "Canada Centennial quarter 1967 bobcat"],
    "canada-25-cents-1965": ["Canada 25 cents 1965", "Canada quarter 1965"],
    "canada-25-cents-1966": ["Canada 25 cents 1966", "Canada quarter 1966"],
    "canada-10-cents-1954": ["Canada 10 cents 1954", "Canada dime 1954"],
    "canada-10-cents-1956": ["Canada 10 cents 1956", "Canada dime 1956"],
    "india-10-paise-1965": ["India 10 paise 1965"],
    "india-1-rupee-1918": ["British India 1 rupee 1918 George V", "India silver rupee 1918"],
    "india-1-rupee-1917": ["British India 1 rupee 1917 George V", "India silver rupee 1917"],
    "india-1-rupee-1919": ["British India 1 rupee 1919 George V", "India silver rupee 1919"],
    "switzerland-2-francs-1980": ["Switzerland 2 francs 1980", "Swiss 2 francs 1980 Helvetia"],
    "switzerland-2-francs-1979": ["Switzerland 2 francs 1979", "Swiss 2 francs 1979 Helvetia"],
    "switzerland-2-francs-1981": ["Switzerland 2 francs 1981", "Swiss 2 francs 1981 Helvetia"],
    "us-spanish-trail-half-dollar-1935": ["Old Spanish Trail half dollar 1935"],
    "us-columbia-half-dollar-1936": ["Columbia South Carolina half dollar 1936"],
    "us-elgin-half-dollar-1936": ["Elgin Centennial half dollar 1936"],
    "us-pilgrim-half-dollar-1920": ["Pilgrim Tercentenary half dollar 1920"],
    "us-oregon-trail-half-dollar-1926": ["Oregon Trail half dollar 1926"],
    "australia-sixpence-1910": ["Australia sixpence 1910 Edward VII"],
    "australia-sixpence-1911": ["Australia sixpence 1911 George V"],
    "indonesia-100-rupiah-1995": ["Indonesia 100 rupiah 1995 karapan sapi"],
    "france-1-centime-1797": ["France 1 centime 1797", "French 1 centime an 6 Dupre"],
    "liberia-1-cent-1896": ["Liberia 1 cent 1896"],
    "philippines-10-pesos-2015": ["Philippines 10 pesos 2015 Bonifacio Mabini", "Philippines 10 piso 2015"],
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _generic_alias(expected: dict) -> str:
    return " ".join(str(expected.get(k) or "").strip() for k in ("country", "denomination", "year")).strip()


def _search_url(query: str, domain: str) -> str:
    # Deliberately emits a normal search-engine URL rather than scraping provider sites.
    return "https://www.google.com/search?q=" + quote_plus(f"site:{domain} {query} coin")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--combined", type=Path, default=DEFAULT_COMBINED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest = _load(args.manifest)
    combined = _load(args.combined)
    combined_cases = combined.get("cases", {})

    queue = {
        "schema": "coin-analyzer-unresolved-source-queue-v1",
        "retrieval_results_inspected": False,
        "inventory_mutated": False,
        "policy": {
            "identity_must_match_frozen_case": True,
            "query_reference_independence_required": True,
            "usage_rights_review_required_before_import": True,
            "do_not_choose_source_using_retrieval_scores": True,
        },
        "slots": [],
        "summary": {"unresolved": 0, "conflicts": 0, "total_actionable": 0},
    }

    expected_by_id = {case["id"]: case.get("expected") or {} for case in manifest.get("cases", [])}
    for case_id, case in combined_cases.items():
        expected = expected_by_id.get(case_id, case.get("expected") or {})
        aliases = ALIASES.get(case_id) or [_generic_alias(expected)]
        for side in ("query", "reference"):
            slot = case.get(side) if isinstance(case, dict) else None
            status = slot.get("status") if isinstance(slot, dict) else "unresolved"
            if status not in {"unresolved", "conflict"}:
                continue
            entry = {
                "case_id": case_id,
                "side": side,
                "status": status,
                "expected": expected,
                "aliases": aliases,
                "provider_searches": [],
            }
            if status == "conflict":
                entry["existing_conflict_proposals"] = slot.get("proposals") or []
                queue["summary"]["conflicts"] += 1
            else:
                queue["summary"]["unresolved"] += 1
            for provider, domain in TRUSTED_SEARCH_TARGETS:
                for alias in aliases:
                    entry["provider_searches"].append({
                        "provider": provider,
                        "domain": domain,
                        "query": alias,
                        "search_url": _search_url(alias, domain),
                    })
            queue["slots"].append(entry)

    queue["summary"]["total_actionable"] = len(queue["slots"])
    args.output.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Unresolved slots exported: {queue['summary']['unresolved']}")
    print(f"Conflict slots exported: {queue['summary']['conflicts']}")
    print(f"Total actionable source slots: {queue['summary']['total_actionable']}")
    print(f"Wrote acquisition queue: {args.output}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
