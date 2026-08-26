#!/usr/bin/env python3
"""Download ranked adversarial asset candidates and record hashes/provenance.

This script consumes ranked_page_asset_candidates.json, downloads at most one ranked
candidate per slot in rank order until a valid image response is obtained, records
SHA-256/content metadata, and writes a local asset download audit. It does not mutate
source_inventory_v1.json and does not run retrieval scoring.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "ranked_page_asset_candidates.json"
OUTPUT = ROOT / "downloaded_ranked_asset_candidates.json"
ASSET_DIR = ROOT / "downloaded_assets"
USER_AGENT = "coin-analyzer-adversarial-benchmark/1.0"
TIMEOUT = 30
MAX_BYTES = 20 * 1024 * 1024


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_slots(payload: dict):
    for key in ("slots", "items", "ranked", "results"):
        rows = payload.get(key)
        if isinstance(rows, list):
            yield from rows
            return
    cases = payload.get("cases")
    if isinstance(cases, dict):
        for case_id, case in cases.items():
            if not isinstance(case, dict):
                continue
            for side in ("query", "reference"):
                slot = case.get(side)
                if isinstance(slot, dict):
                    yield {"case_id": case_id, "side": side, **slot}


def _candidates(row: dict) -> list[dict]:
    for key in ("candidates", "ranked_candidates", "top_candidates", "assets"):
        value = row.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def _url(candidate: dict) -> str:
    for key in ("url", "asset_url", "src", "image_url"):
        value = candidate.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return ""


def _extension(url: str, content_type: str) -> str:
    ext = mimetypes.guess_extension(content_type.split(";", 1)[0].strip()) or ""
    if ext in {".jpe", ".jpeg"}:
        ext = ".jpg"
    if ext:
        return ext
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".img"


def _download(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        content_type = str(resp.headers.get("Content-Type") or "")
        final_url = str(resp.geturl() or url)
        data = resp.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError(f"asset exceeds {MAX_BYTES} bytes")
        if not data:
            raise ValueError("empty response")
        if content_type and not content_type.lower().startswith("image/"):
            raise ValueError(f"non-image content type: {content_type}")
        return data, content_type, final_url


def main() -> int:
    payload = _load(INPUT)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    attempts = 0
    downloaded = 0
    failures = 0
    slots_without_candidates = 0

    rows = list(_iter_slots(payload))
    for index, row in enumerate(rows, 1):
        case_id = str(row.get("case_id") or row.get("id") or "")
        side = str(row.get("side") or "")
        candidates = _candidates(row)
        print(f"[{index}/{len(rows)}] {case_id}.{side}")
        if not candidates:
            slots_without_candidates += 1
            results.append({"case_id": case_id, "side": side, "status": "no-ranked-candidates", "attempts": []})
            continue

        attempt_rows = []
        selected = None
        for rank, candidate in enumerate(candidates, 1):
            url = _url(candidate)
            if not url:
                attempt_rows.append({"rank": rank, "status": "invalid-url"})
                continue
            attempts += 1
            try:
                data, content_type, final_url = _download(url)
                sha = hashlib.sha256(data).hexdigest()
                ext = _extension(final_url, content_type)
                filename = f"{case_id}__{side}__rank{rank}__{sha[:16]}{ext}"
                path = ASSET_DIR / filename
                path.write_bytes(data)
                selected = {
                    "rank": rank,
                    "source_url": url,
                    "final_url": final_url,
                    "content_type": content_type,
                    "bytes": len(data),
                    "sha256": sha,
                    "local_path": str(path),
                    "candidate": candidate,
                }
                attempt_rows.append({"rank": rank, "status": "downloaded", "url": url, "sha256": sha})
                downloaded += 1
                break
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as exc:
                failures += 1
                attempt_rows.append({"rank": rank, "status": "failed", "url": url, "error": str(exc)})
            time.sleep(0.15)

        results.append({
            "case_id": case_id,
            "side": side,
            "status": "downloaded" if selected else "all-candidates-failed",
            "selected": selected,
            "attempts": attempt_rows,
        })

    hashes: dict[str, list[dict]] = {}
    for row in results:
        selected = row.get("selected")
        if isinstance(selected, dict) and selected.get("sha256"):
            hashes.setdefault(str(selected["sha256"]), []).append({"case_id": row["case_id"], "side": row["side"]})
    duplicate_hashes = {sha: refs for sha, refs in hashes.items() if len(refs) > 1}

    output = {
        "schema": "coin-analyzer-ranked-asset-download-audit-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "results": results,
        "duplicate_sha256": duplicate_hashes,
        "summary": {
            "slots_seen": len(rows),
            "slots_without_ranked_candidates": slots_without_candidates,
            "slots_downloaded": downloaded,
            "slots_all_candidates_failed": sum(1 for r in results if r["status"] == "all-candidates-failed"),
            "download_attempts": attempts,
            "failed_download_attempts": failures,
            "duplicate_hash_groups": len(duplicate_hashes),
        },
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    s = output["summary"]
    print(f"Slots seen: {s['slots_seen']}")
    print(f"Slots downloaded: {s['slots_downloaded']}")
    print(f"Slots without ranked candidates: {s['slots_without_ranked_candidates']}")
    print(f"Slots where all candidates failed: {s['slots_all_candidates_failed']}")
    print(f"Download attempts: {s['download_attempts']}")
    print(f"Failed download attempts: {s['failed_download_attempts']}")
    print(f"Duplicate SHA-256 groups: {s['duplicate_hash_groups']}")
    print(f"Wrote asset download audit: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
