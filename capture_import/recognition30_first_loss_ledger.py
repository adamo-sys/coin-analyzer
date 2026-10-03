"""Offline, provenance-preserving terminal ledger for Recognition30 v2 reports."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

_SOURCE_SCHEMA = "coin-analyzer-recognition30-grounded-v1"
_DATASET_VERSION = "recognition30_v2"
_EXPECTED_CASE_COUNT = 30
_CLASSES = (
    "IDENTIFIED",
    "CONFLICTING_EVIDENCE_BEFORE_RETRIEVAL",
    "NO_CANDIDATES",
    "NONE_VERIFIED",
    "PROVIDER_OBSERVATION_FAILURE",
    "UNCLASSIFIED",
)
_IDENTIFIED_REASON = "unique_verified_candidate_with_two_side_support"
_CONFLICT_REASON = "conflicting evidence cannot be sent to catalogue retrieval."


def build_first_loss_ledger(report: Mapping[str, object]) -> dict[str, object]:
    """Classify only terminal outcomes explicitly supported by a v2 report.

    This function never invokes a provider and never reads images. Rows with
    contradictory or incomplete terminal traces remain ``UNCLASSIFIED``.
    """

    if not isinstance(report, Mapping):
        raise TypeError("report must be a mapping.")
    if report.get("schema") != _SOURCE_SCHEMA:
        raise ValueError("report schema is not a grounded Recognition30 report.")
    if report.get("dataset_version") != _DATASET_VERSION:
        raise ValueError("report dataset_version must be recognition30_v2.")

    source_rows = _mapping_sequence(report.get("rows"), "report.rows")
    if len(source_rows) != _EXPECTED_CASE_COUNT:
        raise ValueError("report must contain exactly 30 rows.")

    case_ids = tuple(_nonempty_string(row.get("case_id"), "row.case_id") for row in source_rows)
    if len(set(case_ids)) != _EXPECTED_CASE_COUNT:
        raise ValueError("report case IDs must be unique.")

    rows = [
        _classify_row(row, source_row_index=index)
        for index, row in enumerate(source_rows, start=1)
    ]
    counts = Counter(str(row["terminal_classification"]) for row in rows)
    return {
        "schema": "coin-analyzer-recognition30-first-loss-ledger-v1",
        "source": {
            "schema": _SOURCE_SCHEMA,
            "dataset_version": _DATASET_VERSION,
        },
        "rows": rows,
        "summary": {
            "total_cases": len(rows),
            "classes": {classification: counts[classification] for classification in _CLASSES},
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Materialize an offline ledger from one retained grounded report."""

    parser = argparse.ArgumentParser(
        prog="coin-analyzer-recognition30-first-loss-ledger",
        description="Classify explicit Recognition30 v2 terminal evidence offline.",
    )
    parser.add_argument("input_report", type=Path)
    parser.add_argument("output_ledger", type=Path)
    args = parser.parse_args(argv)

    with args.input_report.open(encoding="utf-8") as handle:
        source = json.load(handle)
    ledger = build_first_loss_ledger(source)
    args.output_ledger.parent.mkdir(parents=True, exist_ok=True)
    args.output_ledger.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


def _classify_row(row: Mapping[str, object], *, source_row_index: int) -> dict[str, object]:
    case_id = _nonempty_string(row.get("case_id"), "row.case_id")
    decision = _nonempty_string(row.get("decision"), "row.decision")
    reason = _nonempty_string(row.get("reason"), "row.reason")
    retrieved_ids = _string_sequence(row.get("retrieved_candidate_ids"), "retrieved_candidate_ids")
    verified_ids = _string_sequence(row.get("verified_candidate_ids"), "verified_candidate_ids")
    verification_rows = _mapping_sequence(row.get("verification_rows"), "verification_rows")
    provider_failures = _mapping_sequence(row.get("provider_failures"), "provider_failures")
    predicted_candidate_id = _optional_string(
        row.get("predicted_candidate_id"), "predicted_candidate_id"
    )

    classification, unclassified_reason = _terminal_classification(
        decision=decision,
        reason=reason,
        retrieved_ids=retrieved_ids,
        verified_ids=verified_ids,
        verification_rows=verification_rows,
        provider_failures=provider_failures,
        predicted_candidate_id=predicted_candidate_id,
    )
    result: dict[str, object] = {
        "case_id": case_id,
        "terminal_classification": classification,
        "provenance": {
            "source_row_index": source_row_index,
            "decision": decision,
            "reason": reason,
            "retriever_id": _optional_string(row.get("retriever_id"), "retriever_id"),
            "query_id": _optional_string(row.get("query_id"), "query_id"),
            "predicted_candidate_id": predicted_candidate_id,
            "retrieved_candidate_ids": list(retrieved_ids),
            "verified_candidate_ids": list(verified_ids),
            "verification_row_count": len(verification_rows),
            "observed_roles": _observation_roles(row.get("observations")),
            "provider_failure_kinds": _failure_kinds(provider_failures),
        },
    }
    if unclassified_reason is not None:
        result["unclassified_reason"] = unclassified_reason
    return result


def _terminal_classification(
    *,
    decision: str,
    reason: str,
    retrieved_ids: tuple[str, ...],
    verified_ids: tuple[str, ...],
    verification_rows: tuple[Mapping[str, object], ...],
    provider_failures: tuple[Mapping[str, object], ...],
    predicted_candidate_id: str | None,
) -> tuple[str, str | None]:
    statuses = _verification_statuses(retrieved_ids, verification_rows)
    if decision == "identify" and reason == _IDENTIFIED_REASON:
        positively_verified_ids = (
            tuple(candidate_id for candidate_id, verified in statuses.items() if verified)
            if statuses is not None
            else ()
        )
        if (
            statuses is not None
            and predicted_candidate_id is not None
            and len(verified_ids) == 1
            and verified_ids[0] == predicted_candidate_id
            and statuses.get(predicted_candidate_id) is True
            and positively_verified_ids == (predicted_candidate_id,)
        ):
            return "IDENTIFIED", None
        return "UNCLASSIFIED", "identified_without_consistent_verified_candidate"
    if (
        decision == "abstain"
        and reason == "provider_observation_failure"
        and provider_failures
        and not retrieved_ids
        and not verified_ids
        and not verification_rows
    ):
        return "PROVIDER_OBSERVATION_FAILURE", None
    if (
        decision == "abstain"
        and reason == _CONFLICT_REASON
        and not retrieved_ids
        and not verified_ids
        and not verification_rows
        and not provider_failures
    ):
        return "CONFLICTING_EVIDENCE_BEFORE_RETRIEVAL", None
    if decision == "abstain" and reason == "no_candidates":
        if verified_ids or verification_rows:
            return "UNCLASSIFIED", "no_candidates_with_verification_evidence"
        if provider_failures:
            return "UNCLASSIFIED", "no_candidates_with_provider_failures"
        if not retrieved_ids:
            return "NO_CANDIDATES", None
        return "UNCLASSIFIED", "no_candidates_with_retrieved_candidates"
    if decision == "abstain" and reason == "none_verified":
        if (
            statuses is not None
            and retrieved_ids
            and not verified_ids
            and not any(statuses.values())
            and not provider_failures
        ):
            return "NONE_VERIFIED", None
        return "UNCLASSIFIED", "none_verified_without_complete_verification_trace"
    return "UNCLASSIFIED", "terminal_evidence_not_classified"


def _mapping_sequence(value: object, name: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a sequence of mappings.")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{name} must contain only mappings.")
    return tuple(value)


def _string_sequence(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a sequence of strings.")
    return tuple(_nonempty_string(item, name) for item in value)


def _observation_roles(value: object) -> list[str]:
    observations = _mapping_sequence(value, "observations")
    return [_nonempty_string(item.get("role"), "observations.role") for item in observations]


def _failure_kinds(failures: tuple[Mapping[str, object], ...]) -> list[str]:
    return [
        _nonempty_string(failure.get("failure_kind"), "provider_failures.failure_kind")
        for failure in failures
    ]


def _verification_statuses(
    retrieved_ids: tuple[str, ...],
    verification_rows: tuple[Mapping[str, object], ...],
) -> dict[str, bool] | None:
    if len(set(retrieved_ids)) != len(retrieved_ids):
        return None
    statuses: dict[str, bool] = {}
    for row in verification_rows:
        candidate_id = row.get("candidate_id")
        verified = row.get("verified")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id.strip()
            or not isinstance(verified, bool)
            or candidate_id in statuses
        ):
            return None
        statuses[candidate_id] = verified
    if set(statuses) != set(retrieved_ids):
        return None
    return statuses


def _nonempty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value, name)


if __name__ == "__main__":
    raise SystemExit(main())
