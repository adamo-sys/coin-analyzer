#!/usr/bin/env python3
"""Rank extracted page image candidates for manual asset selection.

This is a deterministic triage pass only. It does not download image bytes, mutate
source_inventory_v1.json, or run retrieval scoring. The goal is to reduce each
source slot to a short list that can be manually/provenance reviewed before hashing.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "page_asset_candidates.json"
OUTPUT = ROOT / "ranked_page_asset_candidates.json"

PREFERRED_HINTS = (
    "coin", "coins", "obverse", "reverse", "rupee", "peso", "franc",
    "cent", "cents", "sixpence", "dime", "quarter", "nickel", "half-dollar",
)
BAD_HINTS = (
    "logo", "icon", "sprite", "avatar", "banner", "header", "footer",
    "social", "facebook", "twitter", "instagram", "youtube", "placeholder",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _score(row: dict) -> tuple[float, list[str]]:
    url = str(row.get("url") or row.get("asset_url") or "")
    lower = url.lower()
    score = 0.0
    reasons: list[str] = []

    if any(h in lower for h in PREFERRED_HINTS):
        score += 3.0
        reasons.append("coin-identity-url-hint")
    if any(h in lower for h in BAD_HINTS):
        score -= 6.0
        reasons.append("non-coin-ui-url-hint")

    source = str(row.get("source") or row.get("kind") or row.get("method") or "").lower()
    if "og:image" in source or "open graph" in source:
        score += 1.5
        reasons.append("open-graph-image")
    if "twitter" in source:
        score += 0.5
        reasons.append("twitter-card-image")

    width = row.get("width")
    height = row.get("height")
    try:
        w = int(width) if width is not None else 0
        h = int(height) if height is not None else 0
    except (TypeError, ValueError):
        w = h = 0
    if w and h:
        area = w * h
        if area >= 250_000:
            score += 2.0
            reasons.append("large-image")
        elif area < 20_000:
            score -= 3.0
            reasons.append("tiny-image")
        ratio = max(w / h, h / w)
        if ratio <= 2.4:
            score += 0.5
            reasons.append("reasonable-aspect")

    try:
        path = urlparse(url).path.lower()
    except Exception:
        path = lower
    if path.endswith((".jpg", ".jpeg", ".png", ".webp")):
        score += 0.75
        reasons.append("direct-image-extension")

    return score, reasons


def _iter_slots(payload: dict):
    for key in ("items", "slots", "results", "pages"):
        rows = payload.get(key)
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    yield row
            return


def _candidate_rows(slot: dict) -> list[dict]:
    for key in ("asset_candidates", "candidates", "images", "assets"):
        rows = slot.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def main() -> int:
    payload = _load(INPUT)
    ranked_slots = []
    slots_with_candidates = 0
    total_candidates = 0

    for slot in _iter_slots(payload):
        candidates = _candidate_rows(slot)
        ranked = []
        for candidate in candidates:
            score, reasons = _score(candidate)
            ranked.append({**candidate, "triage_score": score, "triage_reasons": reasons})
        ranked.sort(key=lambda r: (-float(r.get("triage_score", 0)), str(r.get("url") or r.get("asset_url") or "")))
        if ranked:
            slots_with_candidates += 1
        total_candidates += len(ranked)
        ranked_slots.append({
            "case_id": slot.get("case_id") or slot.get("id"),
            "side": slot.get("side"),
            "page_url": slot.get("page_url") or slot.get("source_page_url") or slot.get("url"),
            "candidate_count": len(ranked),
            "top_candidates": ranked[:5],
        })

    result = {
        "schema": "coin-analyzer-ranked-page-asset-candidates-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "downloaded_image_bytes": False,
        "slots": ranked_slots,
        "summary": {
            "slots_ranked": len(ranked_slots),
            "slots_with_candidates": slots_with_candidates,
            "total_candidates_considered": total_candidates,
            "top_k_per_slot": 5,
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    s = result["summary"]
    print(f"Slots ranked: {s['slots_ranked']}")
    print(f"Slots with candidates: {s['slots_with_candidates']}")
    print(f"Candidates considered: {s['total_candidates_considered']}")
    print(f"Top candidates retained per slot: {s['top_k_per_slot']}")
    print(f"Wrote ranked asset candidates: {OUTPUT}")
    print("No image bytes were downloaded, source_inventory_v1.json was not modified, and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
