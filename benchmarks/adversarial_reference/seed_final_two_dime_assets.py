#!/usr/bin/env python3
"""Seed explicit independent assets for the final two unresolved Canadian dime slots.

This is a bounded pre-retrieval acquisition step. It records two direct public image
assets discovered independently of retrieval scoring, downloads and hashes them, and
writes a local selection artifact consumed by the unique selector. It does not mutate
source_inventory_v1.json and does not run retrieval scoring.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / "targeted_final_two_assets"
OUTPUT = ROOT / "selected_final_two_dime_assets.json"
USER_AGENT = "coin-analyzer-adversarial-benchmark/1.0"
TIMEOUT = 30
MAX_BYTES = 20 * 1024 * 1024

TARGETS = [
    {
        "case_id": "canada-10-cents-1954",
        "side": "reference",
        "provider": "Florinus",
        "source_page_url": "https://www.florinus.lt/en/10-cents-elizabeth-ii-1953-1964-canada-silver-coin-type-4",
        "asset_url": "https://www.florinus.lt/resized/7af5cec5fffb6cf6723662df8dfad8da-500x500-transparent/10-cents-elizabeth-ii-1953-1964-canada-silver-coin-type-4-.png",
        "reason": "Independent public 1954 reverse image; selected before retrieval scoring to replace shared provider miniature.",
    },
    {
        "case_id": "canada-10-cents-1956",
        "side": "query",
        "provider": "Coins and Canada / Numicanada CDN",
        "source_page_url": "https://www.coinsandcanada.com/coins-prices.php?coin=10-cents-1956&years=10-cents-1953-1964",
        "asset_url": "https://www.numicanada.com/medias/pieces-de-monnaie/image-10-cents-1956-g.jpg",
        "reason": "Direct 1956 reverse image surfaced by the independent public source; selected before retrieval scoring to replace shared provider miniature.",
    },
]


def _download(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        ctype = str(resp.headers.get("Content-Type") or "")
        final_url = str(resp.geturl() or url)
        data = resp.read(MAX_BYTES + 1)
        if not data or len(data) > MAX_BYTES:
            raise ValueError("invalid asset size")
        if ctype and not ctype.lower().startswith("image/"):
            raise ValueError(f"non-image content type: {ctype}")
        return data, ctype, final_url


def _ext(url: str, ctype: str) -> str:
    ext = mimetypes.guess_extension(ctype.split(";", 1)[0].strip()) or ""
    if ext in {".jpe", ".jpeg"}:
        ext = ".jpg"
    if ext:
        return ext
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    return suffix if suffix else ".img"


def main() -> int:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    selected = []
    for i, target in enumerate(TARGETS, 1):
        print(f"[{i}/{len(TARGETS)}] {target['case_id']}.{target['side']}")
        data, ctype, final_url = _download(target["asset_url"])
        sha = hashlib.sha256(data).hexdigest()
        ext = _ext(final_url, ctype)
        path = ASSET_DIR / f"{target['case_id']}__{target['side']}__{sha[:16]}{ext}"
        path.write_bytes(data)
        row = dict(target)
        row.update({
            "final_url": final_url,
            "content_type": ctype,
            "sha256": sha,
            "bytes": len(data),
            "local_path": str(path),
        })
        selected.append(row)
        print(f"  SHA-256: {sha}")
        print(f"  Bytes: {len(data)}")
        print(f"  Asset: {path}")

    output = {
        "schema": "coin-analyzer-selected-final-two-dime-assets-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "selections": selected,
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote selections: {OUTPUT}")
    print("source_inventory_v1.json unchanged; no retrieval scoring run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
