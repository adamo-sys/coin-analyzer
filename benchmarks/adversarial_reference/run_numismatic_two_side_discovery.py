#!/usr/bin/env python3
"""Run bounded, provider-specific discovery for unresolved two-side benchmark roles.

Scoring blind: this script does not decode benchmark images and never invokes the
retrieval backend. It consumes the provider-specific discovery plan and performs
small, throttled HTML searches only against the listed numismatic/authoritative
provider sites, preserving unresolved roles when no explicit side evidence is
found.

The output is a candidate catalogue for later provenance review. No candidate is
accepted into the benchmark by this step.
"""
from __future__ import annotations

import json
import re
import time
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
PLAN = ROOT / "two_side_gap_numismatic_discovery_plan.json"
OUTPUT = ROOT / "two_side_gap_numismatic_candidates.json"
USER_AGENT = "CoinAnalyzerAdversarialNumismaticDiscovery/1.0"
REQUEST_DELAY = 1.25
MAX_SEARCHES = 486


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urlopen(req, timeout=45) as response:
        data = response.read()
    return data.decode("utf-8", errors="ignore")


def extract_links(html: str, provider_domain: str) -> list[str]:
    links = []
    seen = set()
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html, flags=re.I):
        raw = unescape(match.group(1)).strip()
        if not raw.startswith(("http://", "https://")):
            continue
        host = urlparse(raw).netloc.casefold()
        if provider_domain.casefold() not in host:
            continue
        if raw not in seen:
            seen.add(raw)
            links.append(raw)
    return links[:8]


def search_url(query: str) -> str:
    # DuckDuckGo HTML endpoint is used only as a bounded locator for exact
    # provider-domain queries; the result catalogue still requires manual
    # provenance review and explicit side verification before acceptance.
    return "https://html.duckduckgo.com/html/?q=" + quote(query)


def main() -> int:
    if not PLAN.is_file():
        raise SystemExit(f"missing discovery plan: {PLAN}")

    plan = load(PLAN)
    searches = plan.get("searches") or plan.get("rows") or []
    if not isinstance(searches, list):
        raise SystemExit("discovery plan requires a list of searches")

    results = []
    attempted = 0
    succeeded = 0
    failed = 0
    with_candidates = 0

    for index, row in enumerate(searches[:MAX_SEARCHES], 1):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        source_group = str(row.get("source_group") or row.get("side") or "")
        coin_side = str(row.get("coin_side") or row.get("role") or "")
        provider = str(row.get("provider") or "")
        domain = str(row.get("domain") or "")
        query = str(row.get("query") or "")
        if not query or not domain:
            continue

        attempted += 1
        record = {
            "case_id": case_id,
            "source_group": source_group,
            "coin_side": coin_side,
            "provider": provider,
            "domain": domain,
            "query": query,
            "status": "search-error",
            "candidate_urls": [],
        }
        try:
            html = fetch_text(search_url(query))
            candidates = extract_links(html, domain)
            record["candidate_urls"] = candidates
            record["status"] = "candidates" if candidates else "no-candidates"
            succeeded += 1
            if candidates:
                with_candidates += 1
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            record["error"] = str(exc)[:300]
            failed += 1
        results.append(record)
        print(
            f"[{index}/{min(len(searches), MAX_SEARCHES)}] {case_id} "
            f"{source_group}.{coin_side} | {provider} | {record['status']} "
            f"| candidates={len(record['candidate_urls'])}",
            flush=True,
        )
        time.sleep(REQUEST_DELAY)

    artifact = {
        "schema": "coin-analyzer-numismatic-two-side-candidates-v1",
        "retrieval_scoring_run": False,
        "candidate_acceptance_run": False,
        "results": results,
        "summary": {
            "searches_planned": len(searches),
            "searches_attempted": attempted,
            "searches_succeeded": succeeded,
            "searches_failed": failed,
            "searches_with_candidates": with_candidates,
            "candidate_urls": sum(len(r.get("candidate_urls", [])) for r in results),
        },
    }
    OUTPUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("Numismatic two-side provider discovery")
    print("Scoring blind: retrieval backend was NOT run and no candidate was accepted.")
    print(f"Searches planned: {artifact['summary']['searches_planned']}")
    print(f"Searches attempted: {attempted}")
    print(f"Searches succeeded: {succeeded}")
    print(f"Searches failed: {failed}")
    print(f"Searches with candidates: {with_candidates}")
    print(f"Candidate URLs: {artifact['summary']['candidate_urls']}")
    print(f"Wrote candidates: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
