"""Post-execution, ground-truth-isolated evaluation for Experiment 5."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Iterable, Mapping, Sequence


_SPACE = re.compile(r"\s+")
_FIELD_TO_TRUTH = {"date_like": "year", "denomination_mark": "denomination"}


def evaluate_saved_records(
    records: Iterable[Mapping[str, object]],
    ground_truth: Mapping[str, Mapping[str, str]],
    *,
    target_case_ids: Sequence[str],
) -> dict[str, object]:
    """Score already-saved results; this code has no provider dependency."""

    target_ids = frozenset(target_case_ids)
    arms: dict[str, dict[str, int]] = {}
    for record in records:
        arm = _required_text(record, "arm")
        case_id = _required_text(record, "case_id")
        metrics = arms.setdefault(
            arm,
            {
                "attempted_call_count": 0,
                "malformed_call_count": 0,
                "wrong_structured_field_count": 0,
                "complete_correct_field_cells": 0,
            },
        )
        metrics["attempted_call_count"] += 1
        if record.get("status") != "success":
            if record.get("status") == "malformed_output":
                metrics["malformed_call_count"] += 1
            continue
        expected = ground_truth.get(case_id)
        if expected is None:
            raise ValueError(f"missing frozen ground truth for {case_id}")
        for field_name, truth_name in _FIELD_TO_TRUTH.items():
            value = record.get(field_name)
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string or null")
            correct = _comparison_key(value) == _comparison_key(expected[truth_name])
            if correct and case_id in target_ids:
                metrics["complete_correct_field_cells"] += 1
            elif not correct:
                metrics["wrong_structured_field_count"] += 1
    return {"schema": "coin-analyzer-recognition30-observation-evaluation-v1", "arms": arms}


def _required_text(record: Mapping[str, object], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"record {name} must be non-empty text")
    return value


def _comparison_key(value: str) -> str:
    return _SPACE.sub(" ", value.strip()).casefold()


def main(argv: list[str] | None = None) -> int:
    """Evaluate saved experiment output after provider execution has ended."""

    parser = argparse.ArgumentParser(
        prog="coin-analyzer-recognition30-observation-contract-evaluate"
    )
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-case-id", action="append", required=True)
    args = parser.parse_args(argv)
    records = tuple(
        json.loads(line)
        for line in args.records.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    with args.ground_truth.open("r", encoding="utf-8-sig", newline="") as handle:
        truth = {
            row["case_id"].strip(): {
                "year": row["year"].strip(),
                "denomination": row["denomination"].strip(),
            }
            for row in csv.DictReader(handle)
        }
    result = evaluate_saved_records(records, truth, target_case_ids=args.target_case_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
