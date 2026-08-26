#!/usr/bin/env python3
"""Select unique final adversarial assets from the frozen candidate plan.

This bounded pre-retrieval selector resolves manual assets from the assembled plan,
accepts explicitly selected targeted assets when present, and rejects SHA-256 values
already assigned to another slot so later pre-ranked candidates can be tried. It does
not use retrieval scores, mutate source_inventory_v1.json, or change case identities.
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
OUTPUT = ROOT / "unique_final_assets.json"
ASSET_DIR = ROOT / "unique_final_assets"
TARGETED_1956 = ROOT / "selected_numista_1956_reference.json"
USER_AGENT = "coin-analyzer-adversarial-benchmark/1.0"
TIMEOUT = 30
MAX_BYTES = 20 * 1024 * 1024
TARGETED_KEY = ("canada-10-cents-1956", "reference")


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


def _manual_from_row(row: dict) -> dict | None:
    manual = row.get("manual_asset") if isinstance(row.get("manual_asset"), dict) else None
    if manual:
        return manual
    if str(row.get("mode") or "") == "manual-local-asset":
        return {
            "local_path": row.get("local_path"),
            "sha256": row.get("sha256"),
            "bytes": row.get("bytes"),
            "source_page_url": row.get("source_page_url"),
            "provider": row.get("provider"),
        }
    return None


def _manual_path(manual: dict) -> Path | None:
    rel = str(manual.get("local_path") or "")
    if not rel:
        return None
    raw = Path(rel)
    candidates = [raw] if raw.is_absolute() else [ROOT / raw, ROOT / "manual_assets" / raw.name]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return None


def _targeted_1956_candidate() -> dict | None:
    if not TARGETED_1956.is_file():
        return None
    payload = _load(TARGETED_1956)
    selection = payload.get("selected") if isinstance(payload.get("selected"), dict) else payload
    case_id = str(payload.get("case_id") or selection.get("case_id") or "canada-10-cents-1956")
    side = str(payload.get("side") or selection.get("side") or "reference")
    if (case_id, side) != TARGETED_KEY:
        return None
    url = str(selection.get("asset_url") or selection.get("final_url") or selection.get("source_url") or "")
    if not url.startswith(("http://", "https://")):
        return None
    return {
        "case_id": case_id,
        "side": side,
        "asset_url": url,
        "sha256": selection.get("sha256") or payload.get("sha256"),
        "bytes": selection.get("bytes") or payload.get("bytes"),
    }


def main() -> int:
    payload = _load(INPUT)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    used_hashes: dict[str, dict] = {}
    results = []
    attempts = 0
    failed_attempts = 0
    duplicate_rejections = 0
    targeted = _targeted_1956_candidate()

    rows = list(_iter_slots(payload))
    for index, row in enumerate(rows, 1):
        case_id = str(row.get("case_id") or row.get("id") or "")
        side = str(row.get("side") or "")
        mode = str(row.get("mode") or row.get("source_mode") or "")
        print(f"[{index}/{len(rows)}] {case_id}.{side} | mode={mode}")
        selected = None
        attempt_rows = []

        manual = _manual_from_row(row)
        if manual:
            path = _manual_path(manual)
            if path is not None:
                data = path.read_bytes()
                sha = hashlib.sha256(data).hexdigest()
                expected_sha = str(manual.get("sha256") or "")
                if expected_sha and sha != expected_sha:
                    attempt_rows.append({"status": "manual-sha-mismatch", "expected": expected_sha, "actual": sha})
                else:
                    prior = used_hashes.get(sha)
                    if prior is None:
                        selected = {
                            "mode": "manual",
                            "local_path": str(path),
                            "sha256": sha,
                            "bytes": len(data),
                            "source_page_url": manual.get("source_page_url"),
                            "provider": manual.get("provider"),
                        }
                        used_hashes[sha] = {"case_id": case_id, "side": side}
                        attempt_rows.append({"status": "manual-verified", "sha256": sha})
                    else:
                        duplicate_rejections += 1
                        attempt_rows.append({"status": "manual-duplicate-rejected", "sha256": sha, "conflicts_with": prior})
            else:
                attempt_rows.append({"status": "manual-missing", "local_path": manual.get("local_path")})

        explicit_candidates: list[dict] = []
        if selected is None and (case_id, side) == TARGETED_KEY and targeted:
            explicit_candidates.append({
                "asset_url": targeted.get("asset_url"),
                "expected_sha256": targeted.get("sha256"),
                "expected_bytes": targeted.get("bytes"),
                "source": "selected-numista-1956-reference",
            })
        candidates = explicit_candidates + [c for c in (row.get("candidates") or []) if isinstance(c, dict)]

        if selected is None and candidates:
            for rank, candidate in enumerate(candidates, 1):
                url = _candidate_url(candidate)
                if not url:
                    continue
                attempts += 1
                try:
                    data, content_type, final_url = _download(url)
                    sha = hashlib.sha256(data).hexdigest()
                    expected_sha = str(candidate.get("expected_sha256") or "")
                    if expected_sha and sha != expected_sha:
                        attempt_rows.append({"rank": rank, "status": "expected-sha-mismatch", "url": url, "expected": expected_sha, "actual": sha})
                        continue
                    prior = used_hashes.get(sha)
                    if prior is not None:
                        duplicate_rejections += 1
                        attempt_rows.append({"rank": rank, "status": "duplicate-rejected", "url": url, "sha256": sha, "conflicts_with": prior})
                        continue
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
                    used_hashes[sha] = {"case_id": case_id, "side": side}
                    attempt_rows.append({"rank": rank, "status": "selected", "url": url, "sha256": sha})
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

    output = {
        "schema": "coin-analyzer-unique-final-assets-v4",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "selection_policy": "assembled manual assets + explicit pre-retrieval targeted selections + pre-ranked candidate order with global SHA-256 uniqueness; no retrieval score used",
        "results": results,
        "summary": {
            "slots_seen": len(results),
            "slots_selected": sum(1 for r in results if r["status"] == "selected"),
            "slots_unresolved": sum(1 for r in results if r["status"] != "selected"),
            "download_attempts": attempts,
            "failed_download_attempts": failed_attempts,
            "duplicate_candidates_rejected": duplicate_rejections,
            "selected_unique_sha256": len(used_hashes),
        },
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    s = output["summary"]
    print(f"Slots seen: {s['slots_seen']}")
    print(f"Slots selected: {s['slots_selected']}")
    print(f"Slots unresolved: {s['slots_unresolved']}")
    print(f"Download attempts: {s['download_attempts']}")
    print(f"Failed download attempts: {s['failed_download_attempts']}")
    print(f"Duplicate candidates rejected: {s['duplicate_candidates_rejected']}")
    print(f"Selected unique SHA-256: {s['selected_unique_sha256']}")
    print(f"Wrote unique final asset audit: {OUTPUT}")
    print("source_inventory_v1.json was not modified and no retrieval scoring was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
