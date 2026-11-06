"""C07-P1 P13 reconciliation of explicit, scanner-independent synthetic records.

This module performs no IO, scanning, exception approval or qualification. The
caller must supply an independently trusted, predeclared plan and authenticated
execution evidence. Structural equality cannot establish their provenance, prove
predeclaration, or prove a scanner ran. Counts returned here are engineering
results only. Never adapt an ambiguous scanner field by guessing its meaning.

Canonical input schema (plain dictionaries/lists only; unknown fields rejected):

plan = {schema: "c07-findings-v1", criterion_sha256: CRITERION_SHA256,
        cases: [{case_id, snapshot_sha256, baseline_execution_id,
                 candidate_execution_id, expected_baseline: [finding, ...],
                 exceptions: [finding, ...]}, ...]}
reports = [{case_id, snapshot_sha256, baseline: execution,
            candidate: execution}, ...]
execution = {execution_id, status: "completed", started_at, finished_at,
             exit_code, findings: [finding, ...]}
finding = {rule, path, commit, start_line, end_line, value,
           start_column?, end_column?}

Every unmarked field is required. All identifiers and exact extracted inert
values are nonempty strings, compared verbatim. Commit identifiers are opaque:
no abbreviation resolution, case folding or missing-commit substitution occurs.
Snapshots use 64 lowercase hexadecimal SHA-256 characters; execution IDs must
be unique across the entire plan, including B/C. Timestamps use UTC seconds
(YYYY-MM-DDTHH:MM:SSZ), with finish >= start. Only completed executions with
exit 0 for empty findings or exit 2 for nonempty findings are eligible.

Paths are repository-relative; ONLY backslashes become forward slashes.
Absolute/drive paths, empty/dot/parent segments and NUL are rejected. Case,
Unicode and all other characters remain exact. Lines/columns are positive
integers (never booleans); line ranges and same-line column ranges are ordered.
Each column is independently optional: absent is distinct from present, null
is invalid, and available columns participate in identity. No field is inferred.

The plan lists each authorized E(case) occurrence explicitly, with multiplicity.
It grants no exception authority. Empty B is valid only for a predeclared clean
case with empty E; it cannot validate suppression. Any missing case, incomplete
record, inapplicable E, or multiset mismatch raises ReconciliationError. Errors
contain structural locations only, never finding values or supplied identifiers.
"""

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import cast

CRITERION_SHA256 = "B85ACAB6B686F63665947E546F54C1586D5DEE4BCCCD405CA6A53B03D61B14D8"


class ReconciliationError(ValueError):
    """Ineligible or mismatched synthetic evidence; no success is returned."""


@dataclass(frozen=True)
class Summary:
    """Sanitized totals from complete multiset reconciliation, not acceptance."""

    cases: int
    baseline: int
    candidate: int
    suppressed: int


@dataclass(frozen=True, repr=False)
class _Finding:
    rule: str
    path: str
    commit: str
    start_line: int
    end_line: int
    start_column: int | None
    end_column: int | None
    value: str


def _reject(where: str, reason: str) -> None:
    raise ReconciliationError(f"{where}: {reason}")


def _fields(value: object, required: set[str], where: str,
            optional: frozenset[str] = frozenset()) -> dict[str, object]:
    if type(value) is not dict:
        _reject(where, "expected an object")
    result = cast(dict[str, object], value)
    if not required <= result.keys() or not result.keys() <= required | optional:
        _reject(where, "missing or unknown fields")
    return result


def _items(value: object, where: str) -> list[object]:
    if type(value) is not list:
        _reject(where, "expected a list")
    return cast(list[object], value)


def _text(value: object, where: str) -> str:
    if type(value) is not str or not value or "\x00" in value:
        _reject(where, "expected a nonempty NUL-free string")
    return cast(str, value)


def _positive(value: object, where: str) -> int:
    if type(value) is not int or cast(int, value) < 1:
        _reject(where, "expected a positive integer")
    return cast(int, value)


def _snapshot(value: object, where: str) -> str:
    result = _text(value, where)
    if re.fullmatch(r"[0-9a-f]{64}", result) is None:
        _reject(where, "expected lowercase SHA-256")
    return result


def _timestamp(value: object, where: str) -> datetime:
    result = _text(value, where)
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", result) is None:
        _reject(where, "expected UTC timestamp in seconds")
    try:
        return datetime.strptime(result, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        raise ReconciliationError(f"{where}: invalid UTC timestamp") from None


def _findings(value: object, where: str) -> Counter[_Finding]:
    result: Counter[_Finding] = Counter()
    for index, raw in enumerate(_items(value, where)):
        location = f"{where}[{index}]"
        item = _fields(raw, {"rule", "path", "commit", "start_line", "end_line", "value"},
                       location, frozenset({"start_column", "end_column"}))
        path = _text(item["path"], location).replace("\\", "/")
        if ":" in path or any(part in ("", ".", "..") for part in path.split("/")):
            _reject(location, "expected an unambiguous relative path")
        start = _positive(item["start_line"], location)
        end = _positive(item["end_line"], location)
        start_column = _positive(item["start_column"], location) if "start_column" in item else None
        end_column = _positive(item["end_column"], location) if "end_column" in item else None
        if end < start or (start == end and start_column is not None and
                           end_column is not None and end_column < start_column):
            _reject(location, "reversed finding range")
        result[_Finding(_text(item["rule"], location), path, _text(item["commit"], location),
                        start, end, start_column, end_column, _text(item["value"], location))] += 1
    return result


def _execution(value: object, execution_id: str, where: str) -> Counter[_Finding]:
    item = _fields(value, {"execution_id", "status", "started_at", "finished_at",
                           "exit_code", "findings"}, where)
    if _text(item["execution_id"], where) != execution_id:
        _reject(where, "stale or incorrect execution binding")
    if type(item["status"]) is not str or item["status"] != "completed":
        _reject(where, "execution is not completed")
    start = _timestamp(item["started_at"], where)
    end = _timestamp(item["finished_at"], where)
    if end < start:
        _reject(where, "reversed execution interval")
    findings = _findings(item["findings"], f"{where}.findings")
    if type(item["exit_code"]) is not int or item["exit_code"] != (2 if findings else 0):
        _reject(where, "exit code inconsistent with a complete clean/detection report")
    return findings


def reconcile(plan: object, reports: object) -> Summary:
    """Require complete B == expected B and C == B - E for every declared case.

    Inputs are not modified. The trusted plan, not observed counts or reports,
    determines coverage and E. Validation is deterministic and stops on the first
    failure. No partial success or missing-field defaults are returned.
    """
    declaration = _fields(plan, {"schema", "criterion_sha256", "cases"}, "plan")
    if (type(declaration["schema"]) is not str or declaration["schema"] != "c07-findings-v1" or
            type(declaration["criterion_sha256"]) is not str or
            declaration["criterion_sha256"] != CRITERION_SHA256):
        _reject("plan", "unsupported schema or criterion binding")
    cases = _items(declaration["cases"], "plan.cases")
    if not cases:
        _reject("plan.cases", "at least one predeclared case is required")

    expected: dict[str, tuple[str, str, str, Counter[_Finding], Counter[_Finding]]] = {}
    execution_ids: set[str] = set()
    for index, raw in enumerate(cases):
        where = f"plan.cases[{index}]"
        case = _fields(raw, {"case_id", "snapshot_sha256", "baseline_execution_id",
                             "candidate_execution_id", "expected_baseline", "exceptions"}, where)
        case_id = _text(case["case_id"], where)
        snapshot = _snapshot(case["snapshot_sha256"], where)
        baseline_id = _text(case["baseline_execution_id"], where)
        candidate_id = _text(case["candidate_execution_id"], where)
        if case_id in expected:
            _reject(where, "duplicate case declaration")
        if baseline_id == candidate_id or execution_ids.intersection((baseline_id, candidate_id)):
            _reject(where, "reused execution binding")
        execution_ids.update((baseline_id, candidate_id))
        baseline = _findings(case["expected_baseline"], f"{where}.expected_baseline")
        exceptions = _findings(case["exceptions"], f"{where}.exceptions")
        # Check before Counter subtraction: it would otherwise discard deficits.
        if exceptions - baseline:
            _reject(where, "exception occurrence absent or inapplicable to expected baseline")
        expected[case_id] = (snapshot, baseline_id, candidate_id, baseline, exceptions)

    seen: set[str] = set()
    baseline_count = candidate_count = suppressed_count = 0
    for index, raw in enumerate(_items(reports, "reports")):
        where = f"reports[{index}]"
        report = _fields(raw, {"case_id", "snapshot_sha256", "baseline", "candidate"}, where)
        case_id = _text(report["case_id"], where)
        if case_id not in expected or case_id in seen:
            _reject(where, "unexpected or duplicate case report")
        seen.add(case_id)
        snapshot, baseline_id, candidate_id, baseline, exceptions = expected[case_id]
        if _snapshot(report["snapshot_sha256"], where) != snapshot:
            _reject(where, "stale or incorrect snapshot binding")
        observed_b = _execution(report["baseline"], baseline_id, f"{where}.baseline")
        observed_c = _execution(report["candidate"], candidate_id, f"{where}.candidate")
        if observed_b != baseline:
            _reject(where, "observed baseline differs from predeclared baseline")
        if observed_c != baseline - exceptions:
            _reject(where, "candidate differs from baseline minus declared exceptions")
        baseline_count += baseline.total()
        candidate_count += observed_c.total()
        suppressed_count += exceptions.total()
    if seen != expected.keys():
        _reject("reports", "missing required case execution")
    return Summary(len(cases), baseline_count, candidate_count, suppressed_count)
