#!/usr/bin/env python3
"""Create the immutable pre-retrieval freeze record for the 25-case benchmark.

This script is intentionally scoring-blind. It consumes only the frozen identity
manifest, assembled query/reference pair set, and the two pre-freeze audits. It
records exact local asset hashes and provenance so the first retrieval result can
be attributed to a fixed dataset and fixed evaluation policy.

If FREEZE.json already exists, the proposed stable freeze content must match it.
The script never silently overwrites a different freeze.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
MANIFEST = ROOT / "manifest_v1.json"
PAIR_SET = ROOT / "full_pair_asset_set.json"
PROVENANCE_AUDIT = ROOT / "source_asset_independence_audit.json"
SIMILARITY_AUDIT = ROOT / "selected_asset_similarity_audit.json"
OUTPUT = ROOT / "FREEZE.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def selected(slot: object) -> dict:
    if not isinstance(slot, dict):
        return {}
    nested = slot.get("selected")
    return nested if isinstance(nested, dict) else slot


def first(mapping: dict, *keys: str):
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def local_asset_path(slot: object) -> Path:
    s = selected(slot)
    raw = first(s, "local_path", "path", "asset_path", "file")
    if not isinstance(raw, str) or not raw:
        raise RuntimeError("selected slot has no local asset path")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if not path.is_file():
        raise RuntimeError(f"selected local asset missing: {path}")
    return path


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def provenance(slot: object) -> dict:
    s = selected(slot)
    candidate = s.get("candidate") if isinstance(s.get("candidate"), dict) else {}
    page = first(s, "source_page_url", "source_page", "page_url") or first(
        candidate, "source_page_url", "source_page", "page_url"
    )
    asset = first(s, "source_url", "asset_url", "final_url", "source_file_url") or first(
        candidate, "asset_url", "url", "src", "image_url", "source_file_url"
    )
    upstream_sha = first(s, "source_sha256", "source_asset_sha256") or first(
        candidate, "source_sha256", "source_asset_sha256"
    )
    provider = first(s, "provider") or first(candidate, "provider")
    return {
        "source_page_url": page if isinstance(page, str) else None,
        "asset_url": asset if isinstance(asset, str) else None,
        "provider": provider if isinstance(provider, str) else None,
        "upstream_source_sha256": upstream_sha.lower() if isinstance(upstream_sha, str) else None,
    }


def git_head() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        value = proc.stdout.strip()
        return value or None
    except (OSError, subprocess.SubprocessError):
        return None


def validate(manifest: dict, pair_set: dict, provenance_audit: dict, similarity_audit: dict) -> None:
    if int(manifest.get("target_cases") or 0) != 25:
        raise RuntimeError("manifest target_cases is not 25")
    cases = manifest.get("cases") or []
    if not isinstance(cases, list) or len(cases) != 25:
        raise RuntimeError("manifest does not contain exactly 25 frozen cases")

    pair_summary = pair_set.get("summary") or {}
    if int(pair_summary.get("cases") or 0) != 25:
        raise RuntimeError("full pair set does not contain 25 cases")
    if int(pair_summary.get("complete_pairs") or 0) != 25 or int(pair_summary.get("incomplete_pairs") or 0) != 0:
        raise RuntimeError("full pair set is not 25/25 complete")

    prov = provenance_audit.get("summary") or {}
    if int(prov.get("cases") or 0) != 25 or int(prov.get("independence_clear") or 0) != 25:
        raise RuntimeError("provenance audit is not clear for all 25 cases")
    if any(int(prov.get(key) or 0) for key in (
        "independence_pending", "collisions", "selected_hash_collisions",
        "asset_url_collisions", "source_page_collisions", "source_hash_collisions",
    )):
        raise RuntimeError("provenance audit contains a pending case or collision")

    sim = similarity_audit.get("summary") or {}
    if int(sim.get("cases_expected") or 0) != 25 or int(sim.get("pairs_compared") or 0) != 25:
        raise RuntimeError("similarity audit does not cover all 25 pairs")
    if int(sim.get("suspicious_pairs") or 0) or int(sim.get("pairs_not_compared") or 0):
        raise RuntimeError("similarity audit contains suspicious or untested pairs")


def main() -> int:
    for path in (MANIFEST, PAIR_SET, PROVENANCE_AUDIT, SIMILARITY_AUDIT):
        if not path.is_file():
            raise SystemExit(f"Required pre-freeze artifact missing: {path}")

    manifest = load(MANIFEST)
    pair_set = load(PAIR_SET)
    provenance_audit = load(PROVENANCE_AUDIT)
    similarity_audit = load(SIMILARITY_AUDIT)
    validate(manifest, pair_set, provenance_audit, similarity_audit)

    expected_by_id = {
        str(row.get("id") or row.get("case_id")): row
        for row in manifest.get("cases", []) if isinstance(row, dict)
    }
    frozen_cases = []
    side_count = 0
    for row in pair_set.get("rows", []):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "")
        if case_id not in expected_by_id:
            raise SystemExit(f"Pair set contains non-frozen case: {case_id}")
        frozen = {"case_id": case_id, "expected": expected_by_id[case_id].get("expected"), "sides": {}}
        for side in ("query", "reference"):
            slot = row.get(side)
            path = local_asset_path(slot)
            prov = provenance(slot)
            frozen["sides"][side] = {
                "local_path": repo_relative(path),
                "selected_sha256": sha256_file(path),
                **prov,
            }
            side_count += 1
        frozen_cases.append(frozen)

    if len(frozen_cases) != 25 or side_count != 50:
        raise SystemExit(f"Unexpected frozen asset cardinality: cases={len(frozen_cases)} sides={side_count}")

    artifact_hashes = {
        path.name: sha256_file(path)
        for path in (MANIFEST, PAIR_SET, PROVENANCE_AUDIT, SIMILARITY_AUDIT)
    }
    freeze = {
        "schema": "coin-analyzer-adversarial-reference-freeze-v1",
        "status": "frozen-before-primary-retrieval-evaluation",
        "retrieval_scoring_run": False,
        "retrieval_results_inspected": False,
        "source_inventory_modified": False,
        "git_head": git_head(),
        "success_gate": manifest.get("success_gate"),
        "evaluation_policy": manifest.get("evaluation_policy"),
        "artifact_sha256": artifact_hashes,
        "pre_freeze_audits": {
            "provenance_summary": provenance_audit.get("summary"),
            "similarity_summary": similarity_audit.get("summary"),
        },
        "cases": frozen_cases,
        "summary": {"cases": 25, "asset_sides": 50, "complete_pairs": 25},
    }

    encoded = json.dumps(freeze, indent=2, ensure_ascii=False) + "\n"
    if OUTPUT.is_file():
        existing = load(OUTPUT)
        if existing != freeze:
            print("BLOCKED: FREEZE.json already exists and differs from the current proposed freeze.")
            print("Do not overwrite it after evaluation inputs have been frozen.")
            return 2
        print(f"Freeze already matches: {OUTPUT}")
    else:
        OUTPUT.write_text(encoded, encoding="utf-8")
        print(f"Wrote freeze: {OUTPUT}")

    print("Freeze cases: 25")
    print("Frozen asset sides: 50")
    print("Provenance clear: 25")
    print("Similarity clear: 25")
    print("Retrieval scoring was NOT run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
