#!/usr/bin/env python3
"""Audit provenance independence for the assembled frozen query/reference pairs.

This is the final pre-freeze provenance gate. It consumes full_pair_asset_set.json,
not the sparse acquisition inventory. It never runs retrieval scoring and never
mutates source_inventory_v1.json.

For every frozen case it checks the assembled query and reference for:
- exact selected-byte SHA collision;
- exact upstream/source SHA collision when available;
- exact asset URL reuse;
- normalized same source-page reuse.

A pair is clear when both sides are present, have usable provenance, and none of
those collision checks fire. Incomplete provenance remains a blocker rather than
being silently accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "full_pair_asset_set.json"
DEFAULT_OUTPUT = ROOT / "source_asset_independence_audit.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    p = urlsplit(value.strip())
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", ""))


def _selected(slot: object) -> dict:
    if not isinstance(slot, dict):
        return {}
    nested = slot.get("selected")
    return nested if isinstance(nested, dict) else slot


def _first(mapping: dict, *keys: str) -> object:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _local_sha256(slot: dict) -> str | None:
    selected = _selected(slot)
    declared = _first(selected, "sha256", "selected_sha256")
    if isinstance(declared, str) and declared:
        return declared.lower()
    raw_path = _first(selected, "local_path", "path", "asset_path", "file")
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _provenance(slot: object) -> dict:
    selected = _selected(slot)
    candidate = selected.get("candidate") if isinstance(selected.get("candidate"), dict) else {}

    page = _first(
        selected,
        "source_page_url",
        "source_page",
        "page_url",
    ) or _first(candidate, "source_page_url", "source_page", "page_url")

    asset = _first(
        selected,
        "source_url",
        "asset_url",
        "final_url",
        "source_file_url",
    ) or _first(candidate, "asset_url", "url", "src", "image_url", "source_file_url")

    upstream_sha = _first(selected, "source_sha256", "source_asset_sha256") or _first(
        candidate, "source_sha256", "source_asset_sha256"
    )

    provider = _first(selected, "provider") or _first(candidate, "provider")

    return {
        "source_page_url": page if isinstance(page, str) else None,
        "asset_url": asset if isinstance(asset, str) else None,
        "source_sha256": upstream_sha.lower() if isinstance(upstream_sha, str) else None,
        "selected_sha256": _local_sha256(slot if isinstance(slot, dict) else {}),
        "provider": provider if isinstance(provider, str) else None,
    }


def _present(slot: object) -> bool:
    return isinstance(slot, dict) and bool(_selected(slot))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = _load(args.input)
    cases = payload.get("rows") or []
    rows = []
    summary = {
        "cases": 0,
        "cases_with_both_slots": 0,
        "selected_hash_collisions": 0,
        "asset_url_collisions": 0,
        "source_page_collisions": 0,
        "source_hash_collisions": 0,
        "independence_clear": 0,
        "independence_pending": 0,
        "collisions": 0,
    }

    for case in cases if isinstance(cases, list) else []:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("case_id") or "")
        summary["cases"] += 1
        query = case.get("query")
        reference = case.get("reference")

        if not (_present(query) and _present(reference)):
            rows.append({"case_id": case_id, "status": "pending-missing-slot", "issues": ["missing-slot"]})
            summary["independence_pending"] += 1
            continue

        summary["cases_with_both_slots"] += 1
        q = _provenance(query)
        r = _provenance(reference)
        issues: list[str] = []

        if q["selected_sha256"] and r["selected_sha256"] and q["selected_sha256"] == r["selected_sha256"]:
            issues.append("same-selected-sha256")
            summary["selected_hash_collisions"] += 1
        if q["source_sha256"] and r["source_sha256"] and q["source_sha256"] == r["source_sha256"]:
            issues.append("same-source-sha256")
            summary["source_hash_collisions"] += 1

        q_asset = _norm_url(q["asset_url"])
        r_asset = _norm_url(r["asset_url"])
        if q_asset and r_asset and q_asset == r_asset:
            issues.append("same-asset-url")
            summary["asset_url_collisions"] += 1

        q_page = _norm_url(q["source_page_url"])
        r_page = _norm_url(r["source_page_url"])
        if q_page and r_page and q_page == r_page:
            issues.append("same-source-page")
            summary["source_page_collisions"] += 1

        if issues:
            status = "collision"
            summary["collisions"] += 1
        else:
            # Each side must carry at least a selected hash plus a page or asset URL.
            q_complete = bool(q["selected_sha256"] and (q_page or q_asset))
            r_complete = bool(r["selected_sha256"] and (r_page or r_asset))
            if q_complete and r_complete:
                status = "clear-by-provenance"
                summary["independence_clear"] += 1
            else:
                status = "pending-incomplete-provenance"
                summary["independence_pending"] += 1

        rows.append({
            "case_id": case_id,
            "status": status,
            "issues": issues,
            "query": q,
            "reference": r,
        })

    artifact = {
        "schema": "coin-analyzer-source-asset-independence-audit-v2",
        "input": str(args.input),
        "retrieval_results_inspected": False,
        "inventory_modified": False,
        "rows": rows,
        "summary": summary,
    }
    args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Cases audited from full pair set: {summary['cases']}")
    print(f"Cases with both source slots populated: {summary['cases_with_both_slots']}")
    print(f"Selected-byte SHA collisions: {summary['selected_hash_collisions']}")
    print(f"Asset URL collisions: {summary['asset_url_collisions']}")
    print(f"Same source-page collisions: {summary['source_page_collisions']}")
    print(f"Upstream source SHA collisions: {summary['source_hash_collisions']}")
    print(f"Independence clear by provenance: {summary['independence_clear']}")
    print(f"Independence pending: {summary['independence_pending']}")
    print(f"Wrote independence audit: {args.output}")
    print("No retrieval scoring was run and source_inventory_v1.json was not modified.")

    return 1 if (summary["collisions"] or summary["independence_pending"] or summary["cases"] != 25) else 0


if __name__ == "__main__":
    raise SystemExit(main())
