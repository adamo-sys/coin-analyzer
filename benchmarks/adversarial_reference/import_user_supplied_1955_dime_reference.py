#!/usr/bin/env python3
"""Import the manually supplied independent Canada 10 cents 1955 reference asset.

The user supplied the image in ChatGPT from the cited Imaginaire product page after
the previously accepted Coins and Canada page returned HTTP 403. This bounded step
verifies the exact bytes against the SHA-256 recorded at handoff, copies them into the
adversarial benchmark asset directory, and writes a provenance sidecar. It does not
mutate source_inventory_v1.json and does not run retrieval scoring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / "manual_assets"
OUTPUT = ROOT / "canada_10_cents_1955_reference_manual_asset.json"
EXPECTED_SHA256 = "93365bd57eb8aef4b8fa4897cefe1267f337f7b46e9744e1a7d0c18b3ce36ef3"
EXPECTED_BYTES = 516150
SOURCE_PAGE = "https://imaginaire.com/en/coins-and-paper-money/10-cent-1955-10-cent-au-1955-canadian-coins.html"
CASE_ID = "canada-10-cents-1955"
SIDE = "reference"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path, help="Path to the exact user-supplied 1955 dime image")
    args = parser.parse_args()
    source = args.image.resolve()
    if not source.is_file():
        raise SystemExit(f"Image not found: {source}")

    data = source.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    if sha256 != EXPECTED_SHA256:
        raise SystemExit(f"SHA-256 mismatch: expected {EXPECTED_SHA256}, got {sha256}")
    if len(data) != EXPECTED_BYTES:
        raise SystemExit(f"Byte-size mismatch: expected {EXPECTED_BYTES}, got {len(data)}")

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() or ".png"
    destination = ASSET_DIR / f"{CASE_ID}-{SIDE}{suffix}"
    shutil.copyfile(source, destination)

    record = {
        "schema": "coin-analyzer-manual-reference-asset-v1",
        "case_id": CASE_ID,
        "side": SIDE,
        "identity": "Canada 10 cents 1955",
        "provider": "Imaginaire",
        "source_page_url": SOURCE_PAGE,
        "acquisition": "user-supplied image from cited source page",
        "sha256": sha256,
        "bytes": len(data),
        "local_path": str(destination.relative_to(ROOT)),
        "identity_visually_confirmed_at_handoff": True,
        "license_status": "not independently established by this importer",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
    }
    OUTPUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    print(f"Imported: {CASE_ID}.{SIDE}")
    print(f"SHA-256: {sha256}")
    print(f"Bytes: {len(data)}")
    print(f"Asset: {destination}")
    print(f"Provenance: {SOURCE_PAGE}")
    print(f"Wrote manual asset record: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
