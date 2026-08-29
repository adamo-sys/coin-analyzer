#!/usr/bin/env python3
"""Extract image-asset candidates from accepted adversarial source pages.

This phase is still acquisition-only. It consolidates the accepted page-level
coverage artifacts, fetches each source page, and extracts likely image URLs from
OpenGraph/Twitter metadata plus large <img> elements. It records transport errors
separately from no-image results. It never mutates source_inventory_v1.json and
never invokes retrieval scoring.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "page_asset_candidates.json"
USER_AGENT = "Mozilla/5.0 (compatible; CoinAnalyzer-BenchmarkAssetAcquisition/1.0; +https://github.com/adamo-sys/coin-analyzer)"

SOURCES = (
    ROOT / "curated_provider_page_review.json",
    ROOT / "web_curated_gap_page_review.json",
    ROOT / "final_gap_page_review.json",
)


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _accepted_rows(payload: dict) -> list[dict]:
    rows = payload.get("accepted")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _key(row: dict) -> tuple[str, str]:
    return (str(row.get("case_id") or ""), str(row.get("side") or ""))


def _page_url(row: dict) -> str | None:
    for key in ("url", "source_page_url", "page_url"):
        value = row.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return None


def _fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urlopen(request, timeout=45) as response:
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type.lower():
            raise ValueError(f"non-HTML response: {content_type}")
        return response.read().decode("utf-8", errors="replace")


def _attr(tag: str, name: str) -> str | None:
    pattern = re.compile(rf"\b{name}\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
    match = pattern.search(tag)
    return html.unescape(match.group(2)).strip() if match else None


def _extract_assets(page_url: str, body: str) -> list[dict]:
    candidates: list[dict] = []
    seen: set[str] = set()

    for tag in re.findall(r"<meta\b[^>]*>", body, flags=re.IGNORECASE | re.DOTALL):
        prop = (_attr(tag, "property") or _attr(tag, "name") or "").lower()
        if prop not in {"og:image", "og:image:url", "twitter:image", "twitter:image:src"}:
            continue
        value = _attr(tag, "content")
        if not value:
            continue
        url = urljoin(page_url, value)
        if url not in seen:
            seen.add(url)
            candidates.append({"url": url, "evidence": prop, "priority": 0})

    for tag in re.findall(r"<img\b[^>]*>", body, flags=re.IGNORECASE | re.DOTALL):
        src = _attr(tag, "src") or _attr(tag, "data-src") or _attr(tag, "data-lazy-src")
        if not src:
            continue
        url = urljoin(page_url, src)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        width = _attr(tag, "width")
        height = _attr(tag, "height")
        alt = _attr(tag, "alt") or ""
        try:
            area = int(width or 0) * int(height or 0)
        except ValueError:
            area = 0
        lower = url.lower()
        if any(token in lower for token in ("logo", "icon", "avatar", "sprite", "banner")):
            continue
        if url in seen:
            continue
        seen.add(url)
        candidates.append({
            "url": url,
            "evidence": "img",
            "width": width,
            "height": height,
            "alt": alt,
            "priority": 1 if area >= 90000 else 2,
        })

    candidates.sort(key=lambda row: (row.get("priority", 9), -(int(row.get("width") or 0) * int(row.get("height") or 0)) if str(row.get("width") or "").isdigit() and str(row.get("height") or "").isdigit() else 0))
    return candidates[:20]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    accepted: dict[tuple[str, str], dict] = {}
    for source in SOURCES:
        for row in _accepted_rows(_load(source)):
            key = _key(row)
            if key[0] and key[1]:
                accepted[key] = {**row, "coverage_artifact": source.name}

    artifact = {
        "schema": "coin-analyzer-page-asset-candidates-v1",
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "items": [],
        "summary": {
            "accepted_page_slots": len(accepted),
            "pages_fetched": 0,
            "pages_with_asset_candidates": 0,
            "pages_without_asset_candidates": 0,
            "transport_errors": 0,
            "asset_candidates": 0,
        },
    }

    for index, ((case_id, side), row) in enumerate(sorted(accepted.items()), start=1):
        page_url = _page_url(row)
        print(f"[{index}/{len(accepted)}] {case_id}.{side}", flush=True)
        item = {
            "case_id": case_id,
            "side": side,
            "page_url": page_url,
            "coverage_artifact": row.get("coverage_artifact"),
            "provider": row.get("provider"),
            "candidates": [],
            "error": None,
        }
        if not page_url:
            item["error"] = "missing page URL"
            artifact["summary"]["transport_errors"] += 1
        else:
            try:
                body = _fetch(page_url)
                artifact["summary"]["pages_fetched"] += 1
                item["candidates"] = _extract_assets(page_url, body)
            except Exception as error:
                item["error"] = f"{type(error).__name__}: {error}"
                artifact["summary"]["transport_errors"] += 1

        count = len(item["candidates"])
        artifact["summary"]["asset_candidates"] += count
        if count:
            artifact["summary"]["pages_with_asset_candidates"] += 1
        elif not item["error"]:
            artifact["summary"]["pages_without_asset_candidates"] += 1
        artifact["items"].append(item)

    args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    s = artifact["summary"]
    print(f"Accepted page slots: {s['accepted_page_slots']}")
    print(f"Pages fetched: {s['pages_fetched']}")
    print(f"Pages with asset candidates: {s['pages_with_asset_candidates']}")
    print(f"Pages without asset candidates: {s['pages_without_asset_candidates']}")
    print(f"Transport errors: {s['transport_errors']}")
    print(f"Asset candidates extracted: {s['asset_candidates']}")
    print(f"Wrote asset candidate catalogue: {args.output}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
