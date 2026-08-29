#!/usr/bin/env python3
"""Build a targeted, scoring-blind acquisition manifest from known page provenance.

This replaces broad provider-search sweeps with identity-specific page reuse.
It consumes the 54-role two-side gap queue generated locally and merges page-level
provenance already curated during earlier adversarial-source work.

It does not download images, decode benchmark images, change frozen case IDs, or
invoke retrieval scoring. It simply tells the next acquisition step which known
identity-specific pages should be inspected for each missing obverse/reverse role.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "two_side_gap_acquisition_queue.json"
OUTPUT = ROOT / "targeted_two_side_acquisition_manifest.json"

SOURCES = (
    (ROOT / "curated_provider_page_review.json", "accepted", "curated-provider-review"),
    (ROOT / "web_curated_gap_page_review.json", "accepted", "web-curated-review"),
    (ROOT / "final_gap_page_review.json", "accepted", "final-gap-review"),
    # Fall back to static candidates when a generated review artifact is absent.
    (ROOT / "curated_provider_page_candidates.json", "items", "curated-provider-candidates"),
    (ROOT / "web_curated_gap_pages.json", "items", "web-curated-candidates"),
    (ROOT / "final_gap_page_candidates.json", "items", "final-gap-candidates"),
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_pages(sources: tuple[tuple[Path, str, str], ...] = SOURCES) -> dict[tuple[str, str], list[dict]]:
    pages: dict[tuple[str, str], list[dict]] = {}
    seen: set[tuple[str, str, str]] = set()
    for path, key, source_artifact in sources:
        if not path.is_file():
            continue
        payload = load(path)
        rows = payload.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            case_id = str(row.get("case_id") or row.get("id") or "")
            side = str(row.get("side") or "")
            url = str(row.get("url") or row.get("source_page_url") or "")
            if not case_id or side not in {"query", "reference"} or not url.startswith(("http://", "https://")):
                continue
            dedupe = (case_id, side, url)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            required_coin_sides = row.get("required_coin_sides")
            if not isinstance(required_coin_sides, list):
                required_coin_sides = None
            pages.setdefault((case_id, side), []).append({
                "provider": row.get("provider"),
                "source_page_url": url,
                "identity_evidence": row.get("identity_evidence") or row.get("identity_note"),
                "asset_note": row.get("asset_note") or row.get("independence_note"),
                "license_or_permitted_use": row.get("license_or_permitted_use") or row.get("usage_note"),
                "provenance_retrieved_at": row.get("provenance_retrieved_at") or row.get("retrieved_at"),
                "source_record_id": row.get("source_record_id"),
                "required_coin_sides": required_coin_sides,
                "source_artifact": source_artifact,
            })
    return pages


def build_artifact(queue: dict, pages: dict[tuple[str, str], list[dict]]) -> dict:
    rows = queue.get("queue") or []
    if not isinstance(rows, list):
        raise ValueError("two_side_gap_acquisition_queue.json requires queue[]")

    manifest_rows = []
    roles_with_pages = 0
    roles_without_pages = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        source_group = str(row.get("source_group") or "")
        coin_side = str(row.get("coin_side") or "")
        if source_group not in {"query", "reference"} or coin_side not in {"obverse", "reverse"}:
            continue
        candidates = pages.get((case_id, source_group), [])
        status = "known-page-target" if candidates else "page-discovery-still-required"
        if candidates:
            roles_with_pages += 1
        else:
            roles_without_pages += 1
        manifest_rows.append({
            "case_id": case_id,
            "expected": row.get("expected"),
            "source_group": source_group,
            "coin_side": coin_side,
            "asset_role": row.get("asset_role") or f"{source_group}.{coin_side}",
            "status": status,
            "page_candidates": candidates,
            "requirements": {
                "explicit_coin_side_required": True,
                "exact_identity_or_year_specific_asset_required": True,
                "source_page_required": True,
                "direct_asset_url_required_before_import": True,
                "query_reference_independence_required": True,
                "no_heuristic_split": True,
                "retrieval_blind": True,
            },
        })

    cases_with_known_pages = sorted({r["case_id"] for r in manifest_rows if r["page_candidates"]})
    cases_without_known_pages = sorted({r["case_id"] for r in manifest_rows if not r["page_candidates"]})
    return {
        "schema": "coin-analyzer-targeted-two-side-acquisition-manifest-v1",
        "retrieval_scoring_run": False,
        "broad_search_sweep_required": False,
        "roles": manifest_rows,
        "summary": {
            "roles": len(manifest_rows),
            "roles_with_known_page_candidates": roles_with_pages,
            "roles_without_known_page_candidates": roles_without_pages,
            "cases_with_known_page_candidates": len(cases_with_known_pages),
            "case_ids_with_known_pages": cases_with_known_pages,
            "cases_still_requiring_page_discovery": len(cases_without_known_pages),
            "case_ids_still_requiring_page_discovery": cases_without_known_pages,
        },
    }


def main() -> int:
    if not QUEUE.is_file():
        raise SystemExit(f"missing two-side gap queue: {QUEUE}")

    queue = load(QUEUE)
    try:
        artifact = build_artifact(queue, collect_pages())
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    OUTPUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    s = artifact["summary"]
    print("Targeted two-side acquisition manifest")
    print("Scoring blind: no images were decoded/downloaded and retrieval was NOT run.")
    print(f"Missing roles represented: {s['roles']}")
    print(f"Roles with known identity-specific page candidates: {s['roles_with_known_page_candidates']}")
    print(f"Roles still requiring page discovery: {s['roles_without_known_page_candidates']}")
    print(f"Cases with known page candidates: {s['cases_with_known_page_candidates']}")
    print(f"Cases still requiring page discovery: {s['cases_still_requiring_page_discovery']}")
    if s["case_ids_still_requiring_page_discovery"]:
        print("Cases still needing page discovery:")
        for case_id in s["case_ids_still_requiring_page_discovery"]:
            print(f"  - {case_id}")
    print(f"Wrote targeted manifest: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
