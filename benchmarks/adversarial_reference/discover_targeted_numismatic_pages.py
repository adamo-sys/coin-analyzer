#!/usr/bin/env python3
"""Discover third-provider numismatic source pages for unresolved benchmark slots.

This acquisition-only pass consumes unresolved_source_queue.json and searches a
small set of numismatic/museum domains through DuckDuckGo's HTML results. It does
not download coin images, mutate source_inventory_v1.json, or run retrieval
scoring. Output is a reviewable page-candidate catalogue for later provenance and
licensing inspection.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DEFAULT_QUEUE = ROOT / "unresolved_source_queue.json"
DEFAULT_OUTPUT = ROOT / "targeted_numismatic_page_candidates.json"
SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/?q="
USER_AGENT = "Mozilla/5.0 (compatible; CoinAnalyzer-BenchmarkSourceDiscovery/1.0; +https://github.com/adamo-sys/coin-analyzer)"

PROVIDERS = {
    "numista": "numista.com",
    "ngc": "ngccoin.com",
    "pcgs": "pcgs.com",
    "british_museum": "britishmuseum.org",
    "smithsonian": "si.edu",
    "coinsandcanada": "coinsandcanada.com",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _plain(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _expected_query(expected: dict) -> str:
    country = str(expected.get("country") or "").strip()
    denomination = str(expected.get("denomination") or "").strip()
    year = str(expected.get("year") or "").strip()
    type_design = str(expected.get("type_design") or "").strip()
    return " ".join(part for part in (country, denomination, year, type_design) if part)


def _unwrap_ddg(href: str) -> str:
    href = html.unescape(href)
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc:
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return unquote(uddg[0])
    return href


def _search(query: str, limit: int) -> list[dict]:
    request = Request(SEARCH_ENDPOINT + quote_plus(query), headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8", errors="replace")

    pattern = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    rows: list[dict] = []
    seen: set[str] = set()
    for href, title_html in pattern.findall(body):
        url = _unwrap_ddg(href)
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        rows.append({"url": url, "title": _plain(title_html)})
        if len(rows) >= limit:
            break
    return rows


def _queue_items(payload: dict) -> list[dict]:
    for key in ("slots", "items", "queue", "actionable_slots"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    # Fallback for per-case queue formats.
    rows: list[dict] = []
    cases = payload.get("cases")
    if isinstance(cases, dict):
        for case_id, case in cases.items():
            if not isinstance(case, dict):
                continue
            expected = case.get("expected") or {}
            for side in ("query", "reference"):
                slot = case.get(side)
                if isinstance(slot, dict) and slot.get("status") in {"unresolved", "conflict"}:
                    rows.append({"case_id": case_id, "side": side, "status": slot.get("status"), "expected": expected})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--per-provider", type=int, default=4)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    queue = _load(args.queue)
    items = _queue_items(queue)
    artifact = {
        "schema": "coin-analyzer-targeted-numismatic-page-candidates-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "image_download_performed": False,
        "items": [],
        "summary": {
            "actionable_slots": len(items),
            "slots_with_page_candidates": 0,
            "slots_without_page_candidates": 0,
            "page_candidates": 0,
            "search_errors": 0,
        },
    }

    for index, item in enumerate(items, start=1):
        case_id = str(item.get("case_id") or item.get("id") or "unknown")
        side = str(item.get("side") or "unknown")
        expected = item.get("expected") or {}
        base = _expected_query(expected)
        print(f"[{index}/{len(items)}] {case_id}.{side}: {base}", flush=True)
        candidates: list[dict] = []
        errors: list[str] = []
        seen: set[str] = set()
        for provider, domain in PROVIDERS.items():
            query = f"site:{domain} {base} coin"
            try:
                rows = _search(query, args.per_provider)
            except Exception as error:
                errors.append(f"{provider}: {type(error).__name__}: {error}")
                artifact["summary"]["search_errors"] += 1
                continue
            for row in rows:
                url = row.get("url")
                if not isinstance(url, str) or url in seen:
                    continue
                seen.add(url)
                candidates.append({
                    "provider": provider,
                    "domain": domain,
                    "search_query": query,
                    "url": url,
                    "title": row.get("title"),
                    "review_required": True,
                })
            time.sleep(max(0.0, args.delay))

        artifact["items"].append({
            "case_id": case_id,
            "side": side,
            "status": item.get("status"),
            "expected": expected,
            "candidates": candidates,
            "errors": errors,
        })
        artifact["summary"]["page_candidates"] += len(candidates)
        if candidates:
            artifact["summary"]["slots_with_page_candidates"] += 1
        else:
            artifact["summary"]["slots_without_page_candidates"] += 1

    args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = artifact["summary"]
    print(f"Actionable source slots searched: {summary['actionable_slots']}")
    print(f"Slots with third-provider page candidates: {summary['slots_with_page_candidates']}")
    print(f"Slots without third-provider page candidates: {summary['slots_without_page_candidates']}")
    print(f"Third-provider page candidates: {summary['page_candidates']}")
    print(f"Search errors: {summary['search_errors']}")
    print(f"Wrote targeted page catalogue: {args.output}")
    print("No images were downloaded, source_inventory_v1.json was not modified, and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
