"""Build a fail-closed E7 gallery-readiness matrix from a metadata audit.

This module performs no network I/O, image downloads, or model inference.
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


def _rights_eligible(references: object) -> bool:
    if not isinstance(references, list) or not references:
        return False
    return all(
        isinstance(ref, Mapping)
        and bool(ref.get("picture_url"))
        and bool(ref.get("license_name"))
        and bool(ref.get("license_url"))
        for ref in references
    )


def _leakage_clear(references: object) -> bool:
    """Require explicit boolean False for every leakage assertion on every side."""
    if not isinstance(references, list) or not references:
        return False
    return all(
        isinstance(ref, Mapping)
        and all(ref.get(field) is False for field in LEAKAGE_FIELDS)
        for ref in references
    )


def build_readiness_matrix(audit: Mapping[str, object]) -> dict[str, object]:
    rows = audit.get("rows")
    if not isinstance(rows, list):
        raise ValueError("audit rows must be a list")

    matrix: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("audit row must be an object")
        identity = row.get("identity")
        if not isinstance(identity, Mapping):
            raise ValueError("audit row identity must be an object")
        case_id = str(identity.get("case_id") or "")
        if not case_id or case_id in seen:
            raise ValueError("case IDs must be present and unique")
        seen.add(case_id)

        selected = row.get("selected")
        identity_resolved = (
            isinstance(row.get("resolution"), str)
            and str(row["resolution"]).startswith("AUTO_")
            and isinstance(selected, Mapping)
        )
        references = selected.get("references") if isinstance(selected, Mapping) else None
        rights_eligible = identity_resolved and _rights_eligible(references)
        leakage_audited_clear = identity_resolved and _leakage_clear(references)
        execution_ready = identity_resolved and rights_eligible and leakage_audited_clear

        blockers: list[str] = []
        if not identity_resolved:
            blockers.append("IDENTITY_UNRESOLVED")
        if identity_resolved and not rights_eligible:
            blockers.append("RIGHTS_INELIGIBLE_OR_INCOMPLETE")
        if identity_resolved and not leakage_audited_clear:
            blockers.append("LEAKAGE_NOT_CLEARED")

        matrix.append(
            {
                "case_id": case_id,
                "country": identity.get("country"),
                "denomination": identity.get("denomination"),
                "year": identity.get("year"),
                "type_design": identity.get("type_design"),
                "resolution": row.get("resolution"),
                "numista_type_id": selected.get("numista_type_id")
                if isinstance(selected, Mapping)
                else None,
                "identity_resolved": identity_resolved,
                "rights_eligible": rights_eligible,
                "leakage_audited_clear": leakage_audited_clear,
                "execution_ready": execution_ready,
                "blockers": blockers,
            }
        )

    expected_cases = audit.get("cases")
    if isinstance(expected_cases, int) and len(matrix) != expected_cases:
        raise ValueError("matrix row count does not match audit case count")

    return {
        "schema": "coin-analyzer-recognition30-e7-gallery-readiness-v1",
        "source_schema": audit.get("schema"),
        "mode": "OFFLINE_METADATA_READINESS_ONLY",
        "cases": len(matrix),
        "identity_resolved_cases": sum(bool(r["identity_resolved"]) for r in matrix),
        "rights_eligible_cases": sum(bool(r["rights_eligible"]) for r in matrix),
        "leakage_audited_clear_cases": sum(bool(r["leakage_audited_clear"]) for r in matrix),
        "execution_ready_cases": sum(bool(r["execution_ready"]) for r in matrix),
        "execution_authorized": False,
        "rows": matrix,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_json", type=Path)
    parser.add_argument("--json", required=True, dest="output_json", type=Path)
    args = parser.parse_args(argv)

    audit = json.loads(args.audit_json.read_text(encoding="utf-8"))
    result = build_readiness_matrix(audit)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
