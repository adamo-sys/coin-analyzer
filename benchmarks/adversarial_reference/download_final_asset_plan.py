#!/usr/bin/env python3
"""Download the final adversarial asset candidate plan and record hashes.

Consumes final_asset_candidate_plan.json. For download-candidate slots, tries candidates in
order until a valid image is obtained. For manual slots, verifies the referenced local file
exists and hashes it. Writes a final 25-slot asset download audit without mutating
source_inventory_v1.json or running retrieval scoring.
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
INPUT = ROOT / "final_asset_candidate_plan.json"
OUTPUT = ROOT / "final_downloaded_assets.json"
ASSET_DIR = ROOT / "final_downloaded_assets"
USER_AGENT = "coin-analyzer-adversarial-benchmark/1.0"
TIMEOUT = 30
MAX_BYTES = 20 * 1024 * 1024


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_slots(payload: dict):
    for key in ("slots", "items", "results"):
        rows = payload.get(key)
        if isinstance(rows, list):
            yield from rows
            return


def _candidate_url(candidate: dict) -> str:
    for key in ("url", "asset_url", "src", "image_url"):
        value = candidate.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return ""


def _download(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        content_type = str(resp.headers.get("Content-Type") or "")
        final_url = str(resp.geturl() or url)
        data = resp.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("asset too large")
        if not data:
            raise ValueError("empty response")
        if content_type and not content_type.lower().startswith("image/"):
            raise ValueError(f"non-image content type: {content_type}")
        return data, content_type, final_url


def _ext(url: str, content_type: str) -> str:
    ext = mimetypes.guess_extension(content_type.split(";", 1)[0].strip()) or ""
    if ext in {".jpe", ".jpeg"}:
        ext = ".jpg"
    if ext:
        return ext
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".img"


def main() -> int:
    payload = _load(INPUT)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    attempts = 0
    failed_attempts = 0

    rows = list(_iter_slots(payload))
    for index, row in enumerate(rows, 1):
        case_id = str(row.get("case_id") or row.get("id") or "")
        side = str(row.get("side") or "")
        mode = str(row.get("mode") or row.get("source_mode") or "")
        print(f"[{index}/{len(rows)}] {case_id}.{side} | mode={mode}")
        selected = None
        attempt_rows = []

        manual = row.get("manual_asset") if isinstance(row.get("manual_asset"), dict) else None
        if manual:
            rel = str(manual.get("local_path") or "")
            path = (ROOT / rel).resolve() if rel else Path()
            if rel and path.is_file():
                data = path.read_bytes()
                sha = hashlib.sha256(data).hexdigest()
                selected = {
                    "mode": "manual",
                    "local_path": str(path),
                    "sha256": sha,
                    "bytes": len(data),
                    "source_page_url": manual.get("source_page_url"),
                    "provider": manual.get("provider"),
                }
                attempt_rows.append({"status": "manual-verified", "sha256": sha})
            else:
                attempt_rows.append({"status": "manual-missing", "local_path": rel})

        if selected is None:
            candidates = row.get("candidates") or []
            if not isinstance(candidates, list):
                candidates = []
            for rank, candidate in enumerate(candidates, 1):
                if not isinstance(candidate, dict):
                    continue
                url = _candidate_url(candidate)
                if not url:
                    continue
                attempts += 1
                try:
                    data, content_type, final_url = _download(url)
                    sha = hashlib.sha256(data).hexdigest()
                    ext = _ext(final_url, content_type)
                    filename = f"{case_id}__{side}__rank{rank}__{sha[:16]}{ext}"
                    path = ASSET_DIR / filename
                    path.write_bytes(data)
                    selected = {
                        "mode": "download",
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
                    break
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as exc:
                    failed_attempts += 1
                    attempt_rows.append({"rank": rank, "status": "failed", "url": url, "error": str(exc)})

        results.append({
            "case_id": case_id,
            "side": side,
            "status": "selected" if selected else "unresolved",
            "selected": selected,
            "attempts": attempt_rows,
        })

    hashes: dict[str, list[dict]] = {}
    for row in results:
        selected = row.get("selected")
        if isinstance(selected, dict) and selected.get("sha256"):
            hashes.setdefault(str(selected["sha256"]), []).append({"case_id": row["case_id"], "side": row["side"]})
    duplicates = {sha: members for sha, members in hashes.items() if len(members) > 1}

    output = {
        "schema": "coin-analyzer-final-downloaded-assets-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "results": results,
        "duplicate_sha256": duplicates,
        "summary": {
            "slots_seen": len(results),
            "slots_selected": sum(1 for r in results if r["status"] == "selected"),
            "slots_unresolved": sum(1 for r in results if r["status"] != "selected"),
            "download_attempts": attempts,
            "failed_download_attempts": failed_attempts,
            "duplicate_sha256_groups": len(duplicates),
        },
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    s = output["summary"]
    print(f"Slots seen: {s['slots_seen']}")
    print(f"Slots selected: {s['slots_selected']}")
    print(f"Slots unresolved: {s['slots_unresolved']}")
    print(f"Download attempts: {s['download_attempts']}")
    print(f"Failed download attempts: {s['failed_download_attempts']}")
    print(f"Duplicate SHA-256 groups: {s['duplicate_sha256_groups']}")
    print(f"Wrote final download audit: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
