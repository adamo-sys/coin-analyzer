#!/usr/bin/env python3
"""Expand Commons acquisition using numismatic query variants.

Acquisition only: no retrieval scoring, no benchmark mutation. This script targets
unresolved source slots with denomination/common-name aliases and preserves a
reviewable, deduplicated candidate catalogue.
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
DEFAULT_OUTPUT = ROOT / "commons_source_candidates_expanded.json"
API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "CoinAnalyzer-AdversarialBenchmark/1.0 (source discovery; contact via GitHub repository)"

CASE_ALIASES = {
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
    "switzerland-2-francs-1979": ["Swiss 2 francs 1979 Helvetia", "Switzerland two francs 1979"],
    "switzerland-2-francs-1980": ["Swiss 2 francs 1980 Helvetia", "Switzerland two francs 1980"],
    "switzerland-2-francs-1981": ["Swiss 2 francs 1981 Helvetia", "Switzerland two francs 1981"],
    "us-spanish-trail-half-dollar-1935": ["Old Spanish Trail half dollar 1935", "Spanish Trail commemorative half dollar"],
    "us-columbia-half-dollar-1936": ["Columbia South Carolina half dollar 1936", "Columbia commemorative half dollar 1936"],
    "us-elgin-half-dollar-1936": ["Elgin Centennial half dollar 1936", "Elgin commemorative half dollar"],
    "us-pilgrim-half-dollar-1920": ["Pilgrim Tercentenary half dollar 1920", "Pilgrim commemorative half dollar 1920"],
    "us-oregon-trail-half-dollar-1926": ["Oregon Trail half dollar 1926", "Oregon Trail commemorative half dollar"],
    "australia-sixpence-1910": ["Australian sixpence 1910 Edward VII", "Australia 6d 1910"],
    "australia-sixpence-1911": ["Australian sixpence 1911 George V", "Australia 6d 1911"],
    "indonesia-100-rupiah-1995": ["Indonesia 100 rupiah 1995 karapan sapi", "Indonesian 100 rupiah 1995"],
    "france-1-centime-1797": ["France 1 centime 1797 Dupré", "French one centime an 6"],
    "liberia-1-cent-1896": ["Liberia one cent 1896", "Liberian 1 cent 1896"],
    "philippines-10-pesos-2015": ["Philippines 10 piso 2015", "Philippine 10 pesos 2015 Bonifacio Mabini"],
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _request(params: dict) -> dict:
    request = Request(API + "?" + urlencode(params), headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def _discover(query: str, limit: int) -> list[dict]:
    payload = _request({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 960,
    })
    rows = []
    for page in payload.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        ext = info.get("extmetadata") or {}
        def val(name: str) -> str:
            raw = ext.get(name)
            return str(raw.get("value", "")) if isinstance(raw, dict) else ""
        rows.append({
            "title": page.get("title"),
            "description_url": info.get("descriptionurl"),
            "original_url": info.get("url"),
            "thumbnail_url": info.get("thumburl"),
            "artist": val("Artist"),
            "credit": val("Credit"),
            "license": val("LicenseShortName"),
            "description": val("ImageDescription"),
            "search_query": query,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    manifest = _load(args.manifest)
    inventory = _load(args.inventory)
    inv_cases = inventory.get("case_sources", {})
    out = {
        "schema": "coin-analyzer-commons-source-candidates-expanded-v1",
        "retrieval_results_inspected": False,
        "selection_performed": False,
        "cases": {},
    }

    total_rows = 0
    cases_with_rows = 0
    for case in manifest.get("cases", []):
        case_id = case["id"]
        inv = inv_cases.get(case_id, {}) if isinstance(inv_cases, dict) else {}
        sides_needed = []
        for side in ("query", "reference"):
            slot = inv.get(side) if isinstance(inv, dict) else None
            if not isinstance(slot, dict) or slot.get("status") != "seeded":
                sides_needed.append(side)
        if not sides_needed:
            continue
        expected = case.get("expected") or {}
        base = f"{expected.get('country','')} {expected.get('denomination','')} {expected.get('year','')} coin".strip()
        queries = [base, *CASE_ALIASES.get(case_id, [])]
        dedup: dict[str, dict] = {}
        errors = []
        for query in queries:
            print(f"{case_id}: {query}", flush=True)
            try:
                rows = _discover(query, args.limit)
            except Exception as error:
                errors.append(f"{query}: {type(error).__name__}: {error}")
            else:
                for row in rows:
                    key = row.get("original_url") or row.get("description_url") or row.get("title")
                    if key and key not in dedup:
                        dedup[key] = row
            time.sleep(max(0.0, args.delay))
        candidates = list(dedup.values())
        candidates.sort(key=lambda row: row.get("title") or "")
        out["cases"][case_id] = {
            "expected": expected,
            "sides_needed": sides_needed,
            "queries": queries,
            "errors": errors,
            "candidates": candidates,
        }
        total_rows += len(candidates)
        if candidates:
            cases_with_rows += 1

    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote expanded candidate catalogue: {args.output}")
    print(f"Cases with expanded candidates: {cases_with_rows}/{len(out['cases'])}")
    print(f"Deduplicated candidate rows: {total_rows}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
