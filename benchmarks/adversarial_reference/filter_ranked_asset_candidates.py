#!/usr/bin/env python3
"""Filter ranked adversarial asset candidates using observed duplicate/provider-artifact evidence.

This script is intentionally pre-retrieval. It consumes ranked_page_asset_candidates.json
and downloaded_ranked_asset_candidates.json, rejects candidates that are known duplicate
provider/site assets or obvious UI/catalogue thumbnails, and writes a filtered shortlist.
It does not mutate source_inventory_v1.json and does not run retrieval scoring.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
RANKED = ROOT / "ranked_page_asset_candidates.json"
DOWNLOADED = ROOT / "downloaded_ranked_asset_candidates.json"
OUTPUT = ROOT / "filtered_ranked_asset_candidates.json"

# SHA groups observed to be non-coin/provider artifacts in the first asset download pass.
REJECTED_SHA256 = {
    "4493b34f3fbb614b84fa4addcf2e7d2a94c7e3478dd603ca0428ca1cc1040a99",
    "421d5fa9b87f4fbbb828f86a073691c43517eebc9d31c567e6c8d12b5beab6f9",
    "c13ff8ed28d0330d8a354b056c81bf89003f82aaad857e9889660ac251969389",
    "6dbff9723bae9a788d6f01be0a13e3cb7aea416394397cc9188f03b732b12bd5",
    "39e77a86cdf5f97164765e5f18190e4856510ad1e893d34af98568a68e030240",
}

BAD_URL_TOKENS = (
    "/medias/btn_",
    "/catalogue/catalogues/",
    "/catalogue/images/miniatures/",
    "sprite",
    "logo",
    "icon",
    "button",
    "search.jpg",
    "search.png",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_slots(payload: dict):
    for key in ("slots", "items", "ranked", "results"):
        rows = payload.get(key)
        if isinstance(rows, list):
            yield from rows
            return


def _candidates(row: dict) -> list[dict]:
    for key in ("candidates", "ranked_candidates", "top_candidates", "assets"):
        value = row.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def _candidate_url(candidate: dict) -> str:
    for key in ("url", "asset_url", "src", "image_url"):
        value = candidate.get(key)
        if isinstance(value, str):
            return value
    return ""


def _download_sha_lookup(payload: dict) -> dict[tuple[str, str, str], str]:
    lookup: dict[tuple[str, str, str], str] = {}
    for row in payload.get("results", []):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        side = str(row.get("side") or "")
        for attempt in row.get("attempts", []):
            if not isinstance(attempt, dict):
                continue
            url = str(attempt.get("url") or "")
            sha = str(attempt.get("sha256") or "")
            if case_id and side and url and sha:
                lookup[(case_id, side, url)] = sha
    return lookup


def _reject_reason(case_id: str, side: str, candidate: dict, sha_lookup: dict[tuple[str, str, str], str]) -> str | None:
    url = _candidate_url(candidate)
    lower = url.lower()
    sha = sha_lookup.get((case_id, side, url))
    if sha in REJECTED_SHA256:
        return "known duplicate/provider artifact sha256"
    if any(token in lower for token in BAD_URL_TOKENS):
        return "provider UI/catalogue thumbnail URL pattern"
    path = urlparse(url).path.lower()
    if path.endswith(("/favicon.ico", "/favicon.png")):
        return "favicon"
    return None


def main() -> int:
    ranked = _load(RANKED)
    downloaded = _load(DOWNLOADED)
    sha_lookup = _download_sha_lookup(downloaded)

    output_rows = []
    rejected_total = 0
    slots_with_candidates = 0
    slots_empty_after_filter = 0

    rows = list(_iter_slots(ranked))
    for row in rows:
        case_id = str(row.get("case_id") or row.get("id") or "")
        side = str(row.get("side") or "")
        kept = []
        rejected = []
        for candidate in _candidates(row):
            reason = _reject_reason(case_id, side, candidate, sha_lookup)
            if reason:
                rejected.append({"candidate": candidate, "reason": reason})
                rejected_total += 1
            else:
                kept.append(candidate)
        if kept:
            slots_with_candidates += 1
        else:
            slots_empty_after_filter += 1
        output_rows.append({
            "case_id": case_id,
            "side": side,
            "candidates": kept,
            "rejected": rejected,
        })

    result = {
        "schema": "coin-analyzer-filtered-ranked-asset-candidates-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "filter_basis": {
            "known_bad_sha256_count": len(REJECTED_SHA256),
            "bad_url_tokens": list(BAD_URL_TOKENS),
            "notes": "Known-bad hashes were identified from pre-retrieval duplicate diagnostics. No retrieval score was used to choose or reject candidates.",
        },
        "slots": output_rows,
        "summary": {
            "slots_seen": len(output_rows),
            "slots_with_candidates_after_filter": slots_with_candidates,
            "slots_empty_after_filter": slots_empty_after_filter,
            "candidates_rejected": rejected_total,
            "candidates_retained": sum(len(row["candidates"]) for row in output_rows),
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    s = result["summary"]
    print(f"Slots seen: {s['slots_seen']}")
    print(f"Slots with candidates after filter: {s['slots_with_candidates_after_filter']}")
    print(f"Slots empty after filter: {s['slots_empty_after_filter']}")
    print(f"Candidates rejected: {s['candidates_rejected']}")
    print(f"Candidates retained: {s['candidates_retained']}")
    print(f"Wrote filtered candidate shortlist: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
