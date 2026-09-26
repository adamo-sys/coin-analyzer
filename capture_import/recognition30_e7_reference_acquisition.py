"""Acquire the rights-cleared E7 reference batch and record byte-level evidence.

This is a bounded leakage-audit utility, not E7 retrieval execution. It downloads
only references already present in the approved leakage manifest, stores them
outside the repository, hashes query/reference bytes, and detects exact-byte
matches. It does not run embeddings or infer specimen independence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Callable, Mapping, Sequence


MAX_REFERENCE_BYTES = 25 * 1024 * 1024
USER_AGENT = "coin-analyzer-recognition30-e7-leakage-audit/1"
Fetch = Callable[[str], bytes]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dataset_images(dataset: Path) -> dict[str, tuple[Path, Path]]:
    pair_path = dataset / "pair_manifest.csv"
    images = dataset / "images"
    if not pair_path.is_file() or not images.is_dir():
        raise ValueError("dataset must contain pair_manifest.csv and images/")
    result: dict[str, tuple[Path, Path]] = {}
    with pair_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            case_id = (row.get("case_id") or "").strip()
            names = ((row.get("image_1") or "").strip(), (row.get("image_2") or "").strip())
            paths = tuple(images / name for name in names)
            if not case_id or case_id in result or not all(path.is_file() for path in paths):
                raise ValueError(f"invalid pair manifest row for {case_id!r}")
            result[case_id] = paths  # type: ignore[assignment]
    return result


def make_fetch() -> Fetch:
    def fetch(url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            content_type = response.headers.get_content_type()
            if not content_type.startswith("image/"):
                raise ValueError(f"reference is not an image: {url} ({content_type})")
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > MAX_REFERENCE_BYTES:
                raise ValueError(f"reference exceeds byte limit: {url}")
            data = response.read(MAX_REFERENCE_BYTES + 1)
        if len(data) > MAX_REFERENCE_BYTES:
            raise ValueError(f"reference exceeds byte limit: {url}")
        if not data:
            raise ValueError(f"empty reference image: {url}")
        return data
    return fetch


def acquire_batch(
    manifest: Mapping[str, object],
    dataset: Path,
    output_dir: Path,
    fetch: Fetch,
) -> dict[str, object]:
    rows = manifest.get("rows")
    if not isinstance(rows, list):
        raise ValueError("manifest rows must be a list")
    if manifest.get("execution_authorized") is not False:
        raise ValueError("expected fail-closed leakage manifest")

    query_images = _dataset_images(dataset)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache: dict[str, tuple[Path, str, int]] = {}
    report_rows: list[dict[str, object]] = []

    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("invalid manifest row")
        case_id = str(row.get("case_id") or "")
        if case_id not in query_images:
            raise ValueError(f"manifest case absent from dataset: {case_id}")
        refs = row.get("references")
        if not isinstance(refs, list) or not refs:
            raise ValueError(f"manifest case has no references: {case_id}")

        queries = [
            {
                "slot": f"image_{index}",
                "filename": path.name,
                "sha256": _sha256(path.read_bytes()),
            }
            for index, path in enumerate(query_images[case_id], start=1)
        ]
        acquired_refs: list[dict[str, object]] = []
        for ref in refs:
            if not isinstance(ref, Mapping):
                raise ValueError(f"invalid reference row: {case_id}")
            url = str(ref.get("picture_url") or "")
            role = str(ref.get("role") or "")
            if not url or not role or not ref.get("license_name") or not ref.get("license_url"):
                raise ValueError(f"reference lacks URL/rights metadata: {case_id}/{role}")

            if url not in cache:
                data = fetch(url)
                digest = _sha256(data)
                suffix = Path(urllib.request.urlparse(url).path).suffix.lower() or ".img"
                path = output_dir / f"{digest}{suffix}"
                path.write_bytes(data)
                cache[url] = (path, digest, len(data))
            path, digest, byte_count = cache[url]
            exact_slots = [q["slot"] for q in queries if q["sha256"] == digest]
            acquired_refs.append(
                {
                    "role": role,
                    "picture_url": url,
                    "copyright": ref.get("copyright"),
                    "license_name": ref.get("license_name"),
                    "license_url": ref.get("license_url"),
                    "local_filename": path.name,
                    "reference_sha256": digest,
                    "reference_bytes": byte_count,
                    "query_exact_sha256_matches": exact_slots,
                    "same_image_as_query": True if exact_slots else "REVIEW_REQUIRED",
                    "same_image_reason": (
                        "SHA-256 matches Recognition30 query bytes"
                        if exact_slots
                        else "Different SHA-256 proves only different byte streams; visual/provenance review required"
                    ),
                    "derived_from_query": "NOT_AUDITED",
                    "same_physical_specimen_as_query": "NOT_AUDITED",
                }
            )
        report_rows.append(
            {
                "case_id": case_id,
                "numista_type_id": row.get("numista_type_id"),
                "query_images": queries,
                "references": acquired_refs,
            }
        )

    expected_cases = int(manifest.get("cases", -1))
    expected_sides = int(manifest.get("reference_sides", -1))
    actual_sides = sum(len(row["references"]) for row in report_rows)
    if len(report_rows) != expected_cases or actual_sides != expected_sides:
        raise ValueError("acquired batch does not match manifest scope")

    return {
        "schema": "coin-analyzer-recognition30-e7-reference-acquisition-v1",
        "source_manifest_schema": manifest.get("schema"),
        "mode": "BOUNDED_RIGHTS_CLEARED_REFERENCE_ACQUISITION",
        "cases": len(report_rows),
        "reference_sides": actual_sides,
        "unique_reference_urls": len(cache),
        "reference_image_bytes_downloaded": sum(item[2] for item in cache.values()),
        "image_hashing_run": True,
        "embedding_inference_run": False,
        "specimen_independence_inferred": False,
        "execution_authorized": False,
        "rows": report_rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest_json", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--reference-dir", required=True, type=Path)
    parser.add_argument("--json", required=True, dest="output_json", type=Path)
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest_json.read_text(encoding="utf-8"))
    result = acquire_batch(manifest, args.dataset, args.reference_dir, make_fetch())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
