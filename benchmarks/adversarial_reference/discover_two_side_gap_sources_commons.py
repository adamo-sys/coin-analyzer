#!/usr/bin/env python3
"""Discover explicit-side Wikimedia Commons candidates for unresolved two-side roles.

Scoring blind: this script never invokes the frozen retrieval backend and never
opens benchmark images. It queries Wikimedia Commons metadata only and writes a
candidate catalogue for later provenance review / acquisition.

Each unresolved role is searched independently using the frozen expected identity
plus an explicit obverse/reverse token. Candidates are ranked lexically; nothing
is automatically accepted.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
PLAN = ROOT / "two_side_gap_source_discovery_plan.json"
OUTPUT = ROOT / "two_side_gap_commons_candidates.json"
USER_AGENT = "CoinAnalyzerTwoSideCommonsDiscovery/1.0"
API = "https://commons.wikimedia.org/w/api.php"
MAX_RESULTS = 12


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def text(value: object) -> str:
    return str(value or "").strip()


def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def build_query(expected: dict, role: str) -> str:
    country = text(expected.get("country"))
    denomination = text(expected.get("denomination"))
    year = text(expected.get("year"))
    parts = [country, denomination, year, role, "coin"]
    return " ".join(p for p in parts if p)


def api_search(query: str) -> list[dict]:
    params = (
        "action=query&format=json&formatversion=2&generator=search&gsrnamespace=6"
        f"&gsrlimit={MAX_RESULTS}&gsrsearch={quote(query)}"
        "&prop=imageinfo&iiprop=url%7Cextmetadata"
    )
    req = Request(API + "?" + params, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as response:
        payload = json.load(response)
    pages = payload.get("query", {}).get("pages", [])
    return pages if isinstance(pages, list) else []


def score_candidate(title: str, query: str, role: str, expected: dict) -> float:
    tt = tokens(title)
    qq = tokens(query)
    score = 0.0
    score += 2.0 * len(tt & qq)
    if role in tt:
        score += 5.0
    year = text(expected.get("year"))
    if year and year.casefold() in title.casefold():
        score += 4.0
    denom = tokens(text(expected.get("denomination")))
    score += 1.5 * len(tt & denom)
    country = tokens(text(expected.get("country")))
    score += 1.0 * len(tt & country)
    # Penalize obviously generic or non-coin visual assets.
    lower = title.casefold()
    for bad in ("logo", "icon", "map", "flag", "coat of arms", "diagram"):
        if bad in lower:
            score -= 6.0
    return score


def clean_extmetadata(info: dict) -> dict:
    ext = info.get("extmetadata") if isinstance(info.get("extmetadata"), dict) else {}
    def v(key: str):
        item = ext.get(key)
        if isinstance(item, dict):
            return item.get("value")
        return None
    return {
        "artist": v("Artist"),
        "credit": v("Credit"),
        "license": v("LicenseShortName"),
        "usage_terms": v("UsageTerms"),
    }


def normalize_plan_rows(payload: dict) -> list[dict]:
    rows = payload.get("roles") or payload.get("rows") or payload.get("queue") or payload.get("items") or []
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        case_id = text(row.get("case_id"))
        side = text(row.get("source_group") or row.get("side"))
        role = text(row.get("coin_side") or row.get("role"))
        expected = row.get("expected") if isinstance(row.get("expected"), dict) else {}
        if case_id and side in {"query", "reference"} and role in {"obverse", "reverse"}:
            out.append({"case_id": case_id, "side": side, "role": role, "expected": expected})
    return out


def main() -> int:
    if not PLAN.is_file():
        raise SystemExit(f"missing discovery plan: {PLAN}")
    rows = normalize_plan_rows(load(PLAN))
    results = []
    searched = 0
    errors = 0

    for idx, row in enumerate(rows, 1):
        query = build_query(row["expected"], row["role"])
        candidates = []
        try:
            pages = api_search(query)
            searched += 1
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            errors += 1
            results.append({**row, "query": query, "status": "search-error", "error": str(exc)[:300], "candidates": []})
            print(f"[{idx}/{len(rows)}] {row['case_id']} {row['side']}.{row['role']} | search-error", flush=True)
            continue

        for page in pages:
            if not isinstance(page, dict):
                continue
            title = text(page.get("title"))
            info_list = page.get("imageinfo") if isinstance(page.get("imageinfo"), list) else []
            info = info_list[0] if info_list and isinstance(info_list[0], dict) else {}
            asset_url = text(info.get("thumburl") or info.get("url"))
            source_page = text(info.get("descriptionurl"))
            if not title or not asset_url:
                continue
            candidates.append({
                "title": title,
                "score": score_candidate(title, query, row["role"], row["expected"]),
                "asset_url": asset_url,
                "source_page_url": source_page,
                "original_url": text(info.get("url")),
                **clean_extmetadata(info),
            })
        candidates.sort(key=lambda c: (-float(c["score"]), c["title"].casefold()))
        results.append({**row, "query": query, "status": "candidates-found" if candidates else "no-candidates", "candidates": candidates})
        best = candidates[0]["score"] if candidates else None
        print(f"[{idx}/{len(rows)}] {row['case_id']} {row['side']}.{row['role']} | candidates={len(candidates)} best={best}", flush=True)

    roles_with_candidates = sum(bool(r.get("candidates")) for r in results)
    total_candidates = sum(len(r.get("candidates") or []) for r in results)
    artifact = {
        "schema": "coin-analyzer-two-side-gap-commons-candidates-v1",
        "retrieval_scoring_run": False,
        "auto_accept": False,
        "results": results,
        "summary": {
            "roles": len(results),
            "searches_completed": searched,
            "search_errors": errors,
            "roles_with_candidates": roles_with_candidates,
            "roles_without_candidates": len(results) - roles_with_candidates,
            "candidate_rows": total_candidates,
        },
    }
    OUTPUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    s = artifact["summary"]
    print("Commons two-side candidate discovery")
    print("Scoring blind: no retrieval was run and no benchmark images were decoded.")
    print(f"Roles searched: {s['roles']}")
    print(f"Roles with candidates: {s['roles_with_candidates']}")
    print(f"Roles without candidates: {s['roles_without_candidates']}")
    print(f"Candidate rows: {s['candidate_rows']}")
    print(f"Search errors: {s['search_errors']}")
    print(f"Wrote candidates: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
