#!/usr/bin/env python3
"""Acquire explicitly paired obverse/reverse assets for the frozen adversarial benchmark gaps.

This step is scoring-blind. It consumes the two-side gap acquisition queue and
attempts only source acquisition / metadata resolution. It does not invoke the
frozen retrieval backend and does not alter the frozen case identities.

Design goals:
- fill only roles listed in two_side_gap_acquisition_queue.json;
- preserve each case identity and role exactly;
- prefer explicit obverse/reverse URLs or metadata already present in local
  acquisition artifacts;
- never split a single image heuristically;
- write a resumable acquisition artifact and leave unresolved roles explicit.

The actual network fetches happen only when this script is run locally.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "two_side_gap_acquisition_queue.json"
SOURCE_INVENTORY = ROOT / "source_inventory_v1.json"
OUTPUT = ROOT / "two_side_gap_acquisition_results.json"
ASSET_ROOT = ROOT / "two_side_gap_assets"
USER_AGENT = "CoinAnalyzerAdversarialTwoSideAcquisition/1.0"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate_urls(entry: dict, role: str) -> list[dict]:
    """Extract only role-explicit candidate URLs from known inventory metadata.

    This intentionally does not reinterpret generic one-asset URLs as obverse or
    reverse. Candidates must carry explicit role/side metadata or be nested under
    an explicit role key.
    """
    found: list[dict] = []

    def add(url: object, source_page: object = None, provider: object = None, note: str | None = None) -> None:
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            found.append({
                "url": url,
                "source_page_url": source_page if isinstance(source_page, str) else None,
                "provider": provider if isinstance(provider, str) else None,
                "note": note,
            })

    for key in (role, f"{role}_asset", f"{role}_image", f"{role}_source"):
        value = entry.get(key)
        if isinstance(value, dict):
            for url_key in ("asset_url", "source_url", "final_url", "url", "source_file_url"):
                add(value.get(url_key), value.get("source_page_url") or value.get("source_page"), value.get("provider"), f"inventory.{key}")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    for url_key in ("asset_url", "source_url", "final_url", "url", "source_file_url"):
                        add(item.get(url_key), item.get("source_page_url") or item.get("source_page"), item.get("provider"), f"inventory.{key}[]")

    candidates = entry.get("candidates")
    if isinstance(candidates, list):
        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_role = str(item.get("role") or item.get("side") or "").casefold()
            if item_role != role:
                continue
            for url_key in ("asset_url", "source_url", "final_url", "url", "source_file_url"):
                add(item.get(url_key), item.get("source_page_url") or item.get("source_page"), item.get("provider"), "inventory.candidates[]")

    deduped: list[dict] = []
    seen: set[str] = set()
    for row in found:
        if row["url"] not in seen:
            seen.add(row["url"])
            deduped.append(row)
    return deduped


def inventory_by_case() -> dict[str, dict]:
    if not SOURCE_INVENTORY.is_file():
        return {}
    payload = load(SOURCE_INVENTORY)
    rows = payload.get("cases") or payload.get("rows") or payload.get("results") or []
    out: dict[str, dict] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            cid = str(row.get("case_id") or row.get("id") or "")
            if cid:
                out[cid] = row
    return out


def fetch(url: str) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as response:
        data = response.read()
        final_url = response.geturl()
    if not data:
        raise RuntimeError("empty response")
    return data, final_url


def infer_suffix(url: str) -> str:
    suffix = Path(url.split("?", 1)[0]).suffix.casefold()
    return suffix if suffix in IMAGE_SUFFIXES else ".img"


def normalize_queue_row(row: dict) -> tuple[str, str, str]:
    case_id = str(row.get("case_id") or "")
    side = str(row.get("side") or row.get("source_group") or "")
    role = str(row.get("role") or row.get("coin_side") or "")
    asset_role = str(row.get("asset_role") or "")
    if asset_role in {"query.obverse", "query.reverse", "reference.obverse", "reference.reverse"}:
        parsed_side, parsed_role = asset_role.split(".", 1)
        side = side or parsed_side
        role = role or parsed_role
    return case_id, side, role


def main() -> int:
    if not QUEUE.is_file():
        raise SystemExit(f"missing acquisition queue: {QUEUE}")

    queue = load(QUEUE)
    inventory = inventory_by_case()
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)

    previous: dict[tuple[str, str, str], dict] = {}
    if OUTPUT.is_file():
        old = load(OUTPUT)
        for row in old.get("results", []):
            if isinstance(row, dict):
                key = (str(row.get("case_id") or ""), str(row.get("side") or ""), str(row.get("role") or ""))
                if all(key):
                    previous[key] = row

    results: list[dict] = []
    attempts = 0
    downloaded = 0
    reused = 0

    rows = queue.get("rows") or queue.get("queue") or queue.get("items") or []
    if not isinstance(rows, list):
        raise SystemExit("acquisition queue requires a list of rows")

    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id, side, role = normalize_queue_row(row)
        if side not in {"query", "reference"} or role not in {"obverse", "reverse"} or not case_id:
            continue
        key = (case_id, side, role)
        old = previous.get(key)
        if old and old.get("status") == "downloaded":
            raw = old.get("local_path")
            if isinstance(raw, str) and Path(raw).is_file():
                results.append(old)
                reused += 1
                continue

        inv = inventory.get(case_id, {})
        candidates = candidate_urls(inv, role)
        record = {
            "case_id": case_id,
            "side": side,
            "role": role,
            "status": "unresolved",
            "candidate_count": len(candidates),
            "attempts": [],
        }

        for candidate in candidates:
            attempts += 1
            url = candidate["url"]
            try:
                data, final_url = fetch(url)
            except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
                record["attempts"].append({"url": url, "ok": False, "error": str(exc)[:300]})
                continue
            suffix = infer_suffix(final_url)
            dest = ASSET_ROOT / safe_name(case_id) / side
            dest.mkdir(parents=True, exist_ok=True)
            path = dest / f"{role}{suffix}"
            path.write_bytes(data)
            record.update({
                "status": "downloaded",
                "local_path": str(path.resolve()),
                "sha256": sha256_bytes(data),
                "bytes": len(data),
                "asset_url": url,
                "final_url": final_url,
                "source_page_url": candidate.get("source_page_url"),
                "provider": candidate.get("provider"),
                "source_note": candidate.get("note"),
            })
            record["attempts"].append({"url": url, "ok": True, "bytes": len(data)})
            downloaded += 1
            break

        results.append(record)

    unresolved = [r for r in results if r.get("status") != "downloaded"]
    summary = {
        "roles_requested": len(results),
        "roles_downloaded": sum(r.get("status") == "downloaded" for r in results),
        "roles_unresolved": len(unresolved),
        "network_attempts": attempts,
        "downloads_this_run": downloaded,
        "reused_existing_downloads": reused,
        "retrieval_scoring_run": False,
    }
    OUTPUT.write_text(json.dumps({
        "schema": "coin-analyzer-two-side-gap-acquisition-results-v1",
        "results": results,
        "summary": summary,
    }, indent=2) + "\n", encoding="utf-8")

    print("Two-side gap asset acquisition")
    print("Scoring blind: retrieval backend was NOT run.")
    print(f"Roles requested: {summary['roles_requested']}")
    print(f"Roles downloaded: {summary['roles_downloaded']}")
    print(f"Roles unresolved: {summary['roles_unresolved']}")
    print(f"Network attempts: {summary['network_attempts']}")
    print(f"Downloads this run: {summary['downloads_this_run']}")
    print(f"Reused existing downloads: {summary['reused_existing_downloads']}")
    if unresolved:
        print("Unresolved roles:")
        for row in unresolved:
            print(f"  - {row['case_id']} | {row['side']}.{row['role']} | candidates={row['candidate_count']}")
    print(f"Wrote acquisition results: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
