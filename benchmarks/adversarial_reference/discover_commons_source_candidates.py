#!/usr/bin/env python3
"""Discover Wikimedia Commons source candidates for unsourced adversarial cases.

This is acquisition-only tooling. It does not run image retrieval, score candidates,
or modify the frozen benchmark composition. It queries Commons for plausible files
using the expected identity fields and writes a reviewable candidate catalogue.
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
DEFAULT_OUTPUT = ROOT / "commons_source_candidates.json"
API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "CoinAnalyzer-AdversarialBenchmark/1.0 (source discovery; contact via GitHub repository)"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _request(params: dict) -> dict:
    url = API + "?" + urlencode(params)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def _search_terms(expected: dict) -> str:
    country = expected.get("country", "")
    denomination = expected.get("denomination", "")
    year = expected.get("year", "")
    return f"{country} {denomination} {year} coin".strip()


def _discover(query: str, limit: int) -> list[dict]:
    search = _request({
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 960,
    })
    pages = search.get("query", {}).get("pages", {})
    rows: list[dict] = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        ext = info.get("extmetadata") or {}
        def value(name: str) -> str:
            raw = ext.get(name)
            return str(raw.get("value", "")) if isinstance(raw, dict) else ""
        rows.append({
            "title": page.get("title"),
            "description_url": info.get("descriptionurl"),
            "original_url": info.get("url"),
            "thumbnail_url": info.get("thumburl"),
            "artist": value("Artist"),
            "credit": value("Credit"),
            "license": value("LicenseShortName"),
            "description": value("ImageDescription"),
        })
    rows.sort(key=lambda row: row.get("title") or "")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()

    manifest = _load(args.manifest)
    inventory = _load(args.inventory)
    sources = inventory.get("case_sources", {})
    catalogue = {
        "schema": "coin-analyzer-commons-source-candidates-v1",
        "frozen_manifest": args.manifest.name,
        "retrieval_results_inspected": False,
        "selection_policy": "manual provenance review only; do not select using retrieval scores",
        "cases": {},
    }

    pending = 0
    for case in manifest.get("cases", []):
        case_id = case["id"]
        entry = sources.get(case_id, {}) if isinstance(sources, dict) else {}
        expected = case.get("expected") or {}
        sides_needed = []
        for side in ("query", "reference"):
            slot = entry.get(side) if isinstance(entry, dict) else None
            if not isinstance(slot, dict) or slot.get("status") != "seeded":
                sides_needed.append(side)
        if not sides_needed:
            continue
        query = _search_terms(expected)
        print(f"{case_id}: searching Commons for {', '.join(sides_needed)} | {query}", flush=True)
        try:
            candidates = _discover(query, args.limit)
        except Exception as error:
            catalogue["cases"][case_id] = {
                "expected": expected,
                "sides_needed": sides_needed,
                "search_query": query,
                "error": f"{type(error).__name__}: {error}",
                "candidates": [],
            }
        else:
            catalogue["cases"][case_id] = {
                "expected": expected,
                "sides_needed": sides_needed,
                "search_query": query,
                "candidates": candidates,
            }
        pending += 1
        time.sleep(max(0.0, args.delay))

    args.output.write_text(json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote candidate catalogue: {args.output}")
    print(f"Cases requiring new source review: {pending}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
