#!/usr/bin/env python3
"""Discover licensed image candidates from Openverse for unresolved benchmark slots.

Acquisition-only tooling. This script does not run retrieval scoring, does not select
sources, and does not modify source_inventory_v1.json. Openverse is used as a second
source pool because it aggregates explicitly licensed/public-domain media from many
providers while preserving attribution and source-page metadata.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "manifest_v1.json"
DEFAULT_INVENTORY = ROOT / "source_inventory_v1.json"
DEFAULT_OUTPUT = ROOT / "openverse_source_candidates.json"
API = "https://api.openverse.org/v1/images/"
USER_AGENT = "CoinAnalyzer-AdversarialBenchmark/1.0 (source discovery; contact via GitHub repository)"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _query_terms(case_id: str, expected: dict) -> list[str]:
    country = str(expected.get("country") or "").strip()
    denomination = str(expected.get("denomination") or "").strip()
    year = str(expected.get("year") or "").strip()
    base = f"{country} {denomination} {year} coin".strip()
    variants = [base]

    aliases = {
        "canada-5-cents-1964": ["Canada nickel 1964", "Canadian five cents 1964"],
        "canada-10-cents-1954": ["Canada dime 1954", "Canadian ten cents 1954 Bluenose"],
        "canada-10-cents-1955": ["Canada dime 1955", "Canadian ten cents 1955 Bluenose"],
        "canada-10-cents-1956": ["Canada dime 1956", "Canadian ten cents 1956 Bluenose"],
        "canada-25-cents-1965": ["Canada quarter 1965", "Canadian twenty five cents 1965"],
        "canada-25-cents-1966": ["Canada quarter 1966", "Canadian twenty five cents 1966"],
        "canada-25-cents-1967": ["Canada quarter 1967 bobcat", "Canadian Centennial quarter 1967"],
        "india-10-paise-1965": ["India ten paise 1965", "Indian 10 paise 1965 scalloped"],
        "india-1-rupee-1917": ["British India rupee 1917 George V", "India silver rupee 1917"],
        "india-1-rupee-1918": ["British India rupee 1918 George V", "India silver rupee 1918"],
        "india-1-rupee-1919": ["British India rupee 1919 George V", "India silver rupee 1919"],
        "switzerland-2-francs-1979": ["Swiss 2 francs 1979 Helvetia"],
        "switzerland-2-francs-1980": ["Swiss 2 francs 1980 Helvetia"],
        "switzerland-2-francs-1981": ["Swiss 2 francs 1981 Helvetia"],
        "us-spanish-trail-half-dollar-1935": ["Old Spanish Trail half dollar 1935"],
        "us-columbia-half-dollar-1936": ["Columbia South Carolina half dollar 1936"],
        "us-elgin-half-dollar-1936": ["Elgin Centennial half dollar 1936"],
        "us-pilgrim-half-dollar-1920": ["Pilgrim Tercentenary half dollar 1920"],
        "us-oregon-trail-half-dollar-1926": ["Oregon Trail half dollar 1926"],
        "australia-sixpence-1910": ["Australian sixpence 1910 Edward VII"],
        "australia-sixpence-1911": ["Australian sixpence 1911 George V"],
        "indonesia-100-rupiah-1995": ["Indonesia 100 rupiah 1995 karapan sapi"],
        "france-1-centime-1797": ["France 1 centime 1797 Dupre", "French one centime an 6"],
        "liberia-1-cent-1896": ["Liberia one cent 1896"],
        "philippines-10-pesos-2015": ["Philippines 10 piso 2015", "Philippine 10 pesos 2015 Bonifacio Mabini"],
    }
    variants.extend(aliases.get(case_id, []))
    seen: set[str] = set()
    return [q for q in variants if q and not (q.casefold() in seen or seen.add(q.casefold()))]


def _request(query: str, page_size: int) -> list[dict]:
    url = API + "?" + urlencode({"q": query, "page_size": page_size})
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)
    rows = []
    for item in payload.get("results") or []:
        rows.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "creator": item.get("creator"),
            "creator_url": item.get("creator_url"),
            "license": item.get("license"),
            "license_version": item.get("license_version"),
            "license_url": item.get("license_url"),
            "source": item.get("source"),
            "provider": item.get("provider"),
            "foreign_landing_url": item.get("foreign_landing_url"),
            "url": item.get("url"),
            "thumbnail": item.get("thumbnail"),
            "width": item.get("width"),
            "height": item.get("height"),
            "attribution": item.get("attribution"),
        })
    return rows


def _row_key(row: dict) -> str:
    return str(row.get("foreign_landing_url") or row.get("url") or row.get("id") or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    manifest = _load(args.manifest)
    inventory = _load(args.inventory)
    sources = inventory.get("case_sources") or {}
    catalogue = {
        "schema": "coin-analyzer-openverse-source-candidates-v1",
        "frozen_manifest": args.manifest.name,
        "retrieval_results_inspected": False,
        "selection_performed": False,
        "provider": "Openverse",
        "cases": {},
    }

    total_rows = 0
    cases_with_candidates = 0
    for case in manifest.get("cases", []):
        case_id = case["id"]
        entry = sources.get(case_id, {}) if isinstance(sources, dict) else {}
        sides_needed = []
        for side in ("query", "reference"):
            slot = entry.get(side) if isinstance(entry, dict) else None
            if not isinstance(slot, dict) or slot.get("status") != "seeded":
                sides_needed.append(side)
        if not sides_needed:
            continue

        expected = case.get("expected") or {}
        queries = _query_terms(case_id, expected)
        merged: dict[str, dict] = {}
        errors: list[str] = []
        for query in queries:
            print(f"{case_id}: {query}", flush=True)
            try:
                rows = _request(query, args.page_size)
            except Exception as error:
                errors.append(f"{query}: {type(error).__name__}: {error}")
            else:
                for row in rows:
                    key = _row_key(row)
                    if key and key not in merged:
                        merged[key] = row
            time.sleep(max(0.0, args.delay))

        candidates = list(merged.values())
        catalogue["cases"][case_id] = {
            "expected": expected,
            "sides_needed": sides_needed,
            "search_queries": queries,
            "errors": errors,
            "candidates": candidates,
        }
        total_rows += len(candidates)
        if candidates:
            cases_with_candidates += 1

    args.output.write_text(json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote Openverse candidate catalogue: {args.output}")
    print(f"Cases with Openverse candidates: {cases_with_candidates}/{len(catalogue['cases'])}")
    print(f"Deduplicated Openverse candidate rows: {total_rows}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
