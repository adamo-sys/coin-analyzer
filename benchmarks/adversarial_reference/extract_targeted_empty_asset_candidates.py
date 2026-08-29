#!/usr/bin/env python3
"""Extract coin-specific image candidates for the two remaining empty adversarial slots.

Bounded provider-specific extractor. It fetches the accepted source pages for only the
known empty slots, applies provider-aware URL heuristics, and emits candidate URLs for
later byte download/hash review. It does not mutate source_inventory_v1.json and does
not run retrieval scoring.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGETS = ROOT / "target_empty_asset_slots.json"
WEB_REVIEW = ROOT / "web_curated_gap_page_review.json"
FINAL_REVIEW = ROOT / "final_gap_page_review.json"
OUTPUT = ROOT / "targeted_empty_asset_candidates.json"
USER_AGENT = "coin-analyzer-adversarial-benchmark/1.0"
TIMEOUT = 30

KNOWN = {
    ("canada-10-cents-1955", "reference"),
    ("switzerland-2-francs-1980", "reference"),
}

BAD_TOKENS = (
    "btn_", "button", "logo", "icon", "sprite", "banner", "avatar", "catalogues/",
    "miniatures/", "favicon", "facebook", "twitter", "instagram", "youtube",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _page_map(*payloads: dict) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for payload in payloads:
        for key in ("accepted", "covered", "slots", "items", "results"):
            rows = payload.get(key)
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    case_id = str(row.get("case_id") or row.get("id") or "")
                    side = str(row.get("side") or "")
                    url = str(row.get("url") or row.get("page_url") or row.get("source_page_url") or "")
                    if case_id and side and url.startswith(("http://", "https://")):
                        out[(case_id, side)] = url
    return out


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def _urls(page_url: str, body: str) -> list[str]:
    found: list[str] = []
    patterns = [
        r'''(?:src|href)=["']([^"']+)["']''',
        r'''srcset=["']([^"']+)["']''',
        r'''url\((?:["']?)([^)"']+)(?:["']?)\)''',
        r'''content=["']([^"']+)["']''',
    ]
    for pattern in patterns:
        for match in re.findall(pattern, body, flags=re.I):
            for part in str(match).split(","):
                token = part.strip().split()[0] if part.strip() else ""
                if not token:
                    continue
                token = html.unescape(token)
                absolute = urllib.parse.urljoin(page_url, token)
                if absolute.startswith(("http://", "https://")):
                    found.append(absolute)
    dedup: list[str] = []
    seen = set()
    for url in found:
        if url not in seen:
            seen.add(url)
            dedup.append(url)
    return dedup


def _score(case_id: str, url: str) -> tuple[int, list[str]]:
    low = url.lower()
    score = 0
    reasons: list[str] = []
    if any(token in low for token in BAD_TOKENS):
        return -100, ["provider-ui-or-generic-asset"]
    if re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)", low):
        score += 4
        reasons.append("image-extension")
    if "catalogue/images/" in low and "catalogues/" not in low:
        score += 4
        reasons.append("numista-coin-image-path")
    if "coinsandcanada" in low and "/medias/" in low:
        score += 2
        reasons.append("coinsandcanada-media-path")
    year = case_id.rsplit("-", 1)[-1]
    if year in low:
        score += 3
        reasons.append("year-in-url")
    identity_tokens = [x for x in case_id.split("-") if len(x) > 2 and not x.isdigit()]
    matches = sum(1 for token in identity_tokens if token in low)
    if matches:
        score += min(matches, 3)
        reasons.append(f"identity-url-tokens={matches}")
    return score, reasons


def main() -> int:
    targets = _load(TARGETS)
    pages = _page_map(_load(WEB_REVIEW), _load(FINAL_REVIEW))
    results = []
    fetched = 0
    errors = 0

    rows = targets.get("targets") or []
    for index, row in enumerate(rows, 1):
        case_id = str(row.get("case_id") or "")
        side = str(row.get("side") or "")
        key = (case_id, side)
        print(f"[{index}/{len(rows)}] {case_id}.{side}")
        if key not in KNOWN:
            results.append({"case_id": case_id, "side": side, "status": "not-in-bounded-target-set", "candidates": []})
            continue
        page_url = pages.get(key, "")
        if not page_url:
            results.append({"case_id": case_id, "side": side, "status": "source-page-not-found-in-review-artifacts", "candidates": []})
            continue
        try:
            body = _fetch(page_url)
            fetched += 1
        except Exception as exc:
            errors += 1
            results.append({"case_id": case_id, "side": side, "page_url": page_url, "status": "fetch-error", "error": str(exc), "candidates": []})
            continue
        candidates = []
        for url in _urls(page_url, body):
            score, reasons = _score(case_id, url)
            if score <= 0:
                continue
            candidates.append({"url": url, "heuristic_score": score, "reasons": reasons})
        candidates.sort(key=lambda x: (-x["heuristic_score"], x["url"]))
        results.append({
            "case_id": case_id,
            "side": side,
            "page_url": page_url,
            "status": "candidates-found" if candidates else "no-coin-specific-candidates",
            "candidates": candidates[:20],
        })
        print(f"  candidates={len(candidates[:20])}")

    output = {
        "schema": "coin-analyzer-targeted-empty-asset-candidates-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "results": results,
        "summary": {
            "targeted_slots": len(rows),
            "pages_fetched": fetched,
            "fetch_errors": errors,
            "slots_with_candidates": sum(1 for r in results if r.get("candidates")),
            "slots_without_candidates": sum(1 for r in results if not r.get("candidates")),
            "candidates_retained": sum(len(r.get("candidates") or []) for r in results),
        },
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    s = output["summary"]
    print(f"Targeted slots: {s['targeted_slots']}")
    print(f"Pages fetched: {s['pages_fetched']}")
    print(f"Fetch errors: {s['fetch_errors']}")
    print(f"Slots with candidates: {s['slots_with_candidates']}")
    print(f"Slots without candidates: {s['slots_without_candidates']}")
    print(f"Candidates retained: {s['candidates_retained']}")
    print(f"Wrote targeted candidates: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
