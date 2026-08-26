#!/usr/bin/env python3
"""Seed remaining pre-freeze query/reference gaps from independently located public images.

This is a bounded acquisition step. It downloads only the frozen identities listed
below, records provenance, and never runs retrieval scoring or mutates
source_inventory_v1.json.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "selected_remaining_pair_gap_assets.json"
ASSET_DIR = ROOT / "remaining_pair_gap_assets"
UA = "coin-analyzer-adversarial-benchmark/1.0"
TIMEOUT = 30
MAX_BYTES = 20 * 1024 * 1024

TARGETS = [
    {
        "case_id": "india-10-paise-1965", "side": "reference", "provider": "VCoins / NumisCorner",
        "source_page_url": "https://www.vcoins.com/en/stores/numiscorner/239/product/coin_indiarepublic_10_paise_1965__coppernickel_km25/1337754/Default.aspx",
        "asset_url": "https://images.vcoins.com/product_image/239/S/S8y4wY2gT9iz3qFoxHj874dLYJ5n6q.jpg",
        "usage_note": "public dealer photograph; local benchmark use only",
    },
    {
        "case_id": "switzerland-2-francs-1979", "side": "query", "provider": "VCoins / NumisCorner",
        "source_page_url": "https://www.vcoins.com/de/stores/numiscorner/239/product/coin_switzerland_2_francs_1979/1852582/Default.aspx",
        "asset_url": "https://cdn.numiscorner.com/13/01/860/1301860A.jpg",
        "usage_note": "public dealer photograph; local benchmark use only",
    },
    {
        "case_id": "switzerland-2-francs-1981", "side": "query", "provider": "NumisCorner",
        "source_page_url": "https://www.numiscorner.com/es/products/405553-coin-switzerland-2-francs-1981-bern-au-55-58-copper-nickel-km-21a-1",
        "asset_url": "https://www.numiscorner.com/cdn/shop/files/405553A_400x400%402x.progressive.jpg?v=1712495695",
        "usage_note": "public dealer photograph; local benchmark use only",
    },
    {
        "case_id": "us-elgin-half-dollar-1936", "side": "reference", "provider": "CoinsCatalog.NET",
        "source_page_url": "https://coinscatalog.net/ru/usa/coin-silver-half-dollar-elgin-ill-centennial-km-180-commemorative-coins",
        "asset_url": "https://coinscatalog.net/images/big-4x/15/half-dollar-elgin-ill-centennial-1936-usa-r-14278.jpg",
        "usage_note": "public catalog photograph; local benchmark use only",
    },
    {
        "case_id": "us-pilgrim-half-dollar-1920", "side": "reference", "provider": "Money Metals",
        "source_page_url": "https://www.moneymetals.com/1920-pilgrim-half-dollar-almost-uncirculated-90-silver-3617-oz-asw/2337",
        "asset_url": "https://www.moneymetals.com/images/products/1920-90percent-silver-half-dollar-pilgrim-almost-uncirculated-obverse.jpg",
        "usage_note": "public dealer photograph; local benchmark use only",
    },
    {
        "case_id": "france-1-centime-1797", "side": "reference", "provider": "Katz Auction",
        "source_page_url": "https://katzauction.com/lot/494980",
        "asset_url": "https://katzauction.b-cdn.net/imgs/109/111p_vzp59.jpg",
        "usage_note": "public auction photograph; local benchmark use only",
    },
    {
        "case_id": "india-1-rupee-1918", "side": "reference", "provider": "NumisPoint",
        "source_page_url": "https://www.numispoint.com/product/1918-one-rupee-king-george-v-calcutta-mint-aunc-gk-1037/",
        "asset_url": "https://np-wp-images.s3.ap-south-1.amazonaws.com/2021/06/1918-One-Rupee-King-George-V-Calcutta-Mint-AUNC-GK-1037-rev.jpg",
        "usage_note": "public dealer photograph; local benchmark use only",
    },
    {
        "case_id": "india-1-rupee-1919", "side": "reference", "provider": "NumisPoint",
        "source_page_url": "https://www.numispoint.com/product/1919-one-rupee-king-george-v-calcutta-mint-unc-coin-gk-1039/",
        "asset_url": "https://np-wp-images.s3.ap-south-1.amazonaws.com/2023/10/1919-one-rupee-cal-2-rev.jpg",
        "usage_note": "public dealer photograph; local benchmark use only",
    },
    {
        "case_id": "switzerland-2-francs-1979", "side": "reference", "provider": "Cristiano Coins",
        "source_page_url": "https://cristianocoins.it/it/europa-68/89253-switzerland-2-francs-1979.html",
        "asset_url": "https://cristianocoins.it/131260-large_default/switzerland-2-francs-1979.jpg",
        "usage_note": "public dealer photograph; local benchmark use only",
    },
    {
        "case_id": "switzerland-2-francs-1981", "side": "reference", "provider": "Monetnik",
        "source_page_url": "https://www.monetnik.ru/monety/mira/evropa/shvejcariya/shvejcariya-2-franka-844601/",
        "asset_url": "https://cdn.monetnik.ru/storage/market-lot/01/76/844601/2977744_mainViewLot_2x.jpg",
        "usage_note": "public dealer photograph; local benchmark use only",
    },
]


def download(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        ctype = str(resp.headers.get("Content-Type") or "")
        data = resp.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("asset too large")
        if not data:
            raise ValueError("empty response")
        if ctype and not ctype.lower().startswith("image/"):
            raise ValueError(f"non-image content type: {ctype}")
        return data, ctype, str(resp.geturl() or url)


def ext(url: str, ctype: str) -> str:
    value = mimetypes.guess_extension(ctype.split(";", 1)[0].strip()) or ""
    if value in {".jpe", ".jpeg"}:
        value = ".jpg"
    if value:
        return value
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    return suffix if suffix else ".img"


def main() -> int:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    selected, blocked = [], []
    for i, target in enumerate(TARGETS, 1):
        print(f"[{i}/{len(TARGETS)}] {target['case_id']}.{target['side']}")
        try:
            data, ctype, final_url = download(target["asset_url"])
            sha = hashlib.sha256(data).hexdigest()
            path = ASSET_DIR / f"{target['case_id']}__{target['side']}__{sha[:16]}{ext(final_url, ctype)}"
            path.write_bytes(data)
            row = dict(target)
            row.update({"final_url": final_url, "content_type": ctype, "sha256": sha, "bytes": len(data), "local_path": str(path)})
            selected.append(row)
            print(f"  SHA-256: {sha}")
            print(f"  Bytes: {len(data)}")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as exc:
            blocked.append({**target, "error": str(exc)})
            print(f"  BLOCKED: {exc}")
    artifact = {"schema": "coin-analyzer-remaining-pair-gap-assets-v2", "retrieval_scoring_run": False, "inventory_modified": False, "selections": selected, "blocked": blocked, "summary": {"targets": len(TARGETS), "selected": len(selected), "blocked": len(blocked)}}
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"Selected: {len(selected)}")
    print(f"Blocked: {len(blocked)}")
    print(f"Wrote selections: {OUT}")
    print("source_inventory_v1.json unchanged; no retrieval scoring run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
