"""Build the E7 zero-download leakage-review manifest.

Consumes an existing metadata audit and readiness matrix. Performs no network
I/O, image downloads, hashing of image bytes, or model inference.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence


LEAKAGE_FIELDS = (
    "same_image_as_query",
    "derived_from_query",
    "same_physical_specimen_as_query",
)


def build_leakage_manifest(
    audit: Mapping[str, object], readiness: Mapping[str, object]
) -> dict[str, object]:
    audit_rows = audit.get("rows")
    readiness_rows = readiness.get("rows")
    if not isinstance(audit_rows, list) or not isinstance(readiness_rows, list):
        raise ValueError("audit and readiness rows must be lists")

    audit_by_case: dict[str, Mapping[str, object]] = {}
    for row in audit_rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("identity"), Mapping):
            raise ValueError("invalid audit row")
        case_id = str(row["identity"].get("case_id") or "")
        if not case_id or case_id in audit_by_case:
            raise ValueError("audit case IDs must be present and unique")
        audit_by_case[case_id] = row

    rows: list[dict[str, object]] = []
    for ready in readiness_rows:
        if not isinstance(ready, Mapping):
            raise ValueError("invalid readiness row")
        case_id = str(ready.get("case_id") or "")
        if not case_id:
            raise ValueError("readiness case ID missing")
        if not (ready.get("identity_resolved") is True and ready.get("rights_eligible") is True):
            continue
        source = audit_by_case.get(case_id)
        if source is None:
            raise ValueError(f"readiness case missing from audit: {case_id}")
        selected = source.get("selected")
        identity = source.get("identity")
        if not isinstance(selected, Mapping) or not isinstance(identity, Mapping):
            raise ValueError(f"eligible case lacks selected identity: {case_id}")
        refs = selected.get("references")
        if not isinstance(refs, list) or not refs:
            raise ValueError(f"eligible case lacks references: {case_id}")

        manifest_refs: list[dict[str, object]] = []
        for ref in refs:
            if not isinstance(ref, Mapping):
                raise ValueError(f"invalid reference for {case_id}")
            # Preserve metadata only. Never copy or manufacture an image digest.
            manifest_refs.append(
                {
                    "role": ref.get("role"),
                    "picture_url": ref.get("picture_url"),
                    "thumbnail_url": ref.get("thumbnail_url"),
                    "copyright": ref.get("copyright"),
                    "license_name": ref.get("license_name"),
                    "license_url": ref.get("license_url"),
                    "reference_image_bytes_downloaded": False,
                    "query_sha256": None,
                    "reference_sha256": None,
                    "automated_duplicate_or_derivative_signals": [],
                    "provenance_evidence": [],
                    "specimen_level_evidence": [],
                    "reviewer_or_method": None,
                    "same_image_as_query": "NOT_AUDITED",
                    "same_image_reason": None,
                    "derived_from_query": "NOT_AUDITED",
                    "derived_from_query_reason": None,
                    "same_physical_specimen_as_query": "NOT_AUDITED",
                    "same_physical_specimen_reason": None,
                }
            )

        rows.append(
            {
                "case_id": case_id,
                "identity": dict(identity),
                "resolution": source.get("resolution"),
                "numista_type_id": selected.get("numista_type_id"),
                "numista_url": selected.get("numista_url"),
                "selected_title": selected.get("title"),
                "references": manifest_refs,
            }
        )

    expected = int(readiness.get("rights_eligible_cases", -1))
    if expected < 0 or len(rows) != expected:
        raise ValueError(
            f"manifest scope mismatch: expected {expected} rights-eligible cases, got {len(rows)}"
        )

    return {
        "schema": "coin-analyzer-recognition30-e7-leakage-manifest-v1",
        "source_audit_schema": audit.get("schema"),
        "source_readiness_schema": readiness.get("schema"),
        "mode": "ZERO_DOWNLOAD_LEAKAGE_REVIEW_SURFACE",
        "cases": len(rows),
        "reference_sides": sum(len(row["references"]) for row in rows),
        "reference_image_bytes_downloaded": 0,
        "image_hashing_run": False,
        "embedding_inference_run": False,
        "execution_authorized": False,
        "rows": rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_json", type=Path)
    parser.add_argument("readiness_json", type=Path)
    parser.add_argument("--json", required=True, dest="output_json", type=Path)
    args = parser.parse_args(argv)

    audit = json.loads(args.audit_json.read_text(encoding="utf-8"))
    readiness = json.loads(args.readiness_json.read_text(encoding="utf-8"))
    result = build_leakage_manifest(audit, readiness)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
