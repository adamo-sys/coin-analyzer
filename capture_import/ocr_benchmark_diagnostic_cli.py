"""Read-only diagnostics for OCR benchmark evaluation reports."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Mapping, Sequence


_REPORT_SCHEMA = "coin-analyzer-ocr-evaluation-report"
_REQUIRED_FIELDS = ("country", "denomination", "year")


def _norm(value: object) -> str:
    return " ".join(str(value).strip().casefold().split())


def _expected_token_presence(
    observations: list[Mapping[str, object]], expected: Mapping[str, object]
) -> dict[str, bool]:
    """Diagnostic-only token presence; never feeds recognition or resolver input."""

    haystack = _norm(" ".join(str(item.get("raw_text", "")) for item in observations))
    result: dict[str, bool] = {}
    for field in _REQUIRED_FIELDS:
        value = expected.get(field)
        result[field] = bool(value is not None and _norm(value) in haystack)
    return result


def _classify_bottleneck(
    *,
    observations: list[Mapping[str, object]],
    candidates: list[Mapping[str, object]],
    conflicts: list[Mapping[str, object]],
    expected_presence: Mapping[str, bool],
) -> str:
    if conflicts:
        return "candidate_conflict"
    if candidates:
        unresolved_expected = [field for field in _REQUIRED_FIELDS if not expected_presence.get(field, False)]
        return "partial_signal_or_candidate_gap" if unresolved_expected else "candidate_projection_gap"
    if any(expected_presence.values()):
        return "signal_present_candidate_missing"
    if any(str(item.get("raw_text", "")).strip() for item in observations):
        return "ocr_signal_missing"
    return "no_ocr_text"


def diagnose_report(report: Mapping[str, object]) -> dict[str, object]:
    if report.get("schema") != _REPORT_SCHEMA:
        raise ValueError(f"schema must be {_REPORT_SCHEMA!r}")
    raw_cases = report.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("cases must be a list")

    rows: list[dict[str, object]] = []
    classes = Counter()
    for raw in raw_cases:
        if not isinstance(raw, Mapping) or raw.get("ocr_evaluated") is not True:
            continue
        observations = [item for item in raw.get("raw_observations", []) if isinstance(item, Mapping)]
        candidates = [item for item in raw.get("raw_candidates", []) if isinstance(item, Mapping)]
        conflicts = [item for item in raw.get("raw_conflicts", []) if isinstance(item, Mapping)]
        expected = raw.get("expected") if isinstance(raw.get("expected"), Mapping) else {}
        presence = _expected_token_presence(observations, expected)
        candidate_counts = Counter(
            str(item.get("field_name"))
            for item in candidates
            if item.get("field_name") in _REQUIRED_FIELDS
        )
        bottleneck = _classify_bottleneck(
            observations=observations,
            candidates=candidates,
            conflicts=conflicts,
            expected_presence=presence,
        )
        classes[bottleneck] += 1
        rows.append(
            {
                "case_id": raw.get("case_id"),
                "identity_certain": raw.get("identity_certain"),
                "difficulty": list(raw.get("difficulty", [])) if isinstance(raw.get("difficulty"), list) else [],
                "observations": [
                    {
                        "image_role": item.get("image_role"),
                        "confidence_score": item.get("confidence_score"),
                        "raw_text": item.get("raw_text"),
                    }
                    for item in observations
                ],
                "expected_token_presence_diagnostic_only": presence,
                "candidate_counts_by_field": {
                    field: candidate_counts.get(field, 0) for field in _REQUIRED_FIELDS
                },
                "candidate_count": len(candidates),
                "conflict_count": len(conflicts),
                "unresolved_fields": list(raw.get("unresolved_fields", []))
                if isinstance(raw.get("unresolved_fields"), list)
                else [],
                "bottleneck": bottleneck,
            }
        )

    return {
        "schema": "coin-analyzer-ocr-diagnostic-v1",
        "source_dataset_version": report.get("dataset_version"),
        "case_count": len(rows),
        "bottleneck_counts": dict(sorted(classes.items())),
        "cases": rows,
        "warning": (
            "expected_token_presence_diagnostic_only compares benchmark ground truth to raw OCR "
            "for diagnosis only; it must never feed recognition, resolver, or production flow"
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-ocr-diagnostic")
    parser.add_argument("report", type=Path)
    parser.add_argument("--json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    diagnostics = diagnose_report(report)
    rendered = json.dumps(diagnostics, indent=2, ensure_ascii=False)
    print(rendered)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
