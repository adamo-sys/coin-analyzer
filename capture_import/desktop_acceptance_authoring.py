"""Pre-freeze authoring and readiness checks for desktop acceptance v1.

This module is intentionally separate from :mod:`desktop_acceptance_set`.  Authoring
plans may contain unresolved operational state; frozen manifests may not.  A plan
being ``ready_for_freeze`` means only that the human-review/provenance/capture
preconditions represented here are complete enough to start the byte-freeze step.
It is not approval to execute recognition or score the benchmark.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Mapping, Sequence


AUTHORING_SCHEMA = "coin-analyzer-desktop-acceptance-authoring-plan"
AUTHORING_VERSION = "1.0.0"
DESKTOP_ACCEPTANCE_V1_CASE_COUNT = 30
FREEZE_PREPARATION_SCHEMA = "coin-analyzer-desktop-acceptance-freeze-preparation"
FREEZE_PREPARATION_VERSION = "1.0.0"
EXPECTED_ACTIONS = frozenset({"identify", "abstain"})
APPROVAL_STATES = frozenset({"unresolved", "approved", "rejected"})
REVIEW_DECISION_STATES = frozenset({"unresolved", "complete"})
CAPTURE_STATES = frozenset({"not_started", "incomplete", "complete"})
NEAR_DUPLICATE_STATES = frozenset({"not_started", "incomplete", "complete"})
CAPTURE_FIELDS = ("background", "device", "distance", "lighting", "orientation")
_CASE_ID = re.compile(r"^case-[0-9]{3}$")
_SPECIMEN_ID = re.compile(r"^specimen-[0-9]{3}$")


class DesktopAcceptanceAuthoringError(ValueError):
    """The authoring plan is malformed or is not ready for the requested step."""


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    ready_for_freeze: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    summary: Mapping[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "ready_for_freeze": self.ready_for_freeze,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "summary": dict(self.summary),
        }


def load_authoring_plan(path: str | Path) -> Mapping[str, object]:
    """Load an authoring plan without pretending incomplete state is frozen state."""
    plan_path = Path(path)
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DesktopAcceptanceAuthoringError(f"cannot read authoring plan: {error}") from error
    return validate_authoring_plan(payload)


def validate_authoring_plan(payload: object) -> Mapping[str, object]:
    """Validate an in-memory authoring plan using the authoritative shape contract."""
    _validate_plan_shape(payload)
    assert isinstance(payload, Mapping)
    return payload


def evaluate_readiness(payload: Mapping[str, object]) -> ReadinessReport:
    """Return deterministic fail-closed readiness diagnostics for an authoring plan."""
    validate_authoring_plan(payload)
    blockers: set[str] = set()
    warnings: set[str] = set()
    cases = payload["cases"]
    assert isinstance(cases, list)
    stability_cohorts = payload["stability_relevant_cohorts"]
    assert isinstance(stability_cohorts, list)

    if len(cases) != DESKTOP_ACCEPTANCE_V1_CASE_COUNT:
        blockers.add(
            "corpus requires exactly "
            f"{DESKTOP_ACCEPTANCE_V1_CASE_COUNT} cases; found {len(cases)}"
        )

    case_ids: list[str] = []
    actions: Counter[str] = Counter()
    by_specimen: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    stability_cases: list[Mapping[str, object]] = []
    completed_gt = 0
    completed_action = 0
    completed_capture = 0
    completed_near_duplicate = 0
    approved_eligibility = 0

    for index, raw in enumerate(cases):
        assert isinstance(raw, Mapping)
        label = f"cases[{index}]"
        case_id = raw["case_id"]
        specimen_id = raw["specimen_id"]
        action = raw["expected_action"]

        if not isinstance(case_id, str) or not _CASE_ID.fullmatch(case_id):
            blockers.add(f"{label}.case_id must match case-NNN")
            case_label = label
        else:
            case_ids.append(case_id)
            case_label = case_id

        if not isinstance(specimen_id, str) or not _SPECIMEN_ID.fullmatch(specimen_id):
            blockers.add(f"{case_label}.specimen_id must match specimen-NNN")
        else:
            by_specimen[specimen_id].append(raw)

        if action not in EXPECTED_ACTIONS:
            blockers.add(f"{case_label}.expected_action is unresolved or unsupported")
        else:
            actions[action] += 1

        identity = raw["candidate_identity"]
        assert isinstance(identity, Mapping)
        if not _complete_identity(identity):
            blockers.add(f"{case_label}.candidate_identity is incomplete")
        if action == "abstain" and not _complete_identity(identity):
            blockers.add(f"{case_label}.abstain case requires complete known identity")

        cohorts = raw["cohorts"]
        if not isinstance(cohorts, list) or not cohorts or not all(_nonempty_text(v) for v in cohorts):
            blockers.add(f"{case_label}.cohorts must contain at least one non-empty cohort")

        provenance = raw["provenance"]
        assert isinstance(provenance, Mapping)
        if not _nonempty_text(provenance["ownership_or_source"]):
            blockers.add(f"{case_label}.provenance ownership/source is unresolved")
        if not _nonempty_text(provenance["evidence_reference"]):
            blockers.add(f"{case_label}.provenance evidence is unresolved")

        eligibility = raw["provider_eligibility"]
        assert isinstance(eligibility, Mapping)
        eligibility_ok = True
        for field in ("privacy", "licensing", "provider_authorization"):
            state = eligibility[field]
            if state not in APPROVAL_STATES:
                blockers.add(f"{case_label}.provider_eligibility.{field} has invalid state")
                eligibility_ok = False
            elif state != "approved":
                blockers.add(f"{case_label}.provider_eligibility.{field} is not approved")
                eligibility_ok = False
        if eligibility_ok:
            approved_eligibility += 1

        gt_review = raw["ground_truth_review"]
        action_review = raw["action_review"]
        assert isinstance(gt_review, Mapping) and isinstance(action_review, Mapping)
        gt_ok, gt_resolved, gt_errors = _review_resolution(gt_review, "identity")
        for error in gt_errors:
            blockers.add(f"{case_label}.ground_truth_review {error}")
        if gt_ok:
            completed_gt += 1
            if gt_resolved != _identity_projection(identity):
                blockers.add(f"{case_label}.ground_truth_review does not resolve to candidate identity")
        action_ok, action_resolved, action_errors = _review_resolution(action_review, "action")
        for error in action_errors:
            blockers.add(f"{case_label}.action_review {error}")
        if action_ok:
            completed_action += 1
            if action_resolved != action:
                blockers.add(f"{case_label}.action_review does not resolve to expected_action")

        capture = raw["capture"]
        assert isinstance(capture, Mapping)
        capture_ok = _capture_complete(capture)
        if not capture_ok:
            blockers.add(f"{case_label}.capture is incomplete")
        else:
            completed_capture += 1

        duplicate_review = raw["near_duplicate_review"]
        assert isinstance(duplicate_review, Mapping)
        if duplicate_review["status"] != "complete" or not _nonempty_text(duplicate_review["evidence_reference"]):
            blockers.add(f"{case_label}.near_duplicate_review is incomplete")
        else:
            completed_near_duplicate += 1

        if raw["stability"] is True:
            stability_cases.append(raw)
        elif raw["stability"] is not False:
            blockers.add(f"{case_label}.stability must be boolean")

    if len(case_ids) != len(set(case_ids)):
        blockers.add("case IDs must be unique")
    if case_ids != sorted(case_ids):
        blockers.add("case IDs must be sorted")
    if actions != Counter({"identify": 24, "abstain": 6}):
        blockers.add(
            f"corpus requires 24 identify and 6 abstain cases; found "
            f"{actions['identify']} identify and {actions['abstain']} abstain"
        )

    if len(by_specimen) < 24:
        blockers.add(f"corpus requires at least 24 specimens; found {len(by_specimen)}")
    for specimen_id, rows in sorted(by_specimen.items()):
        if len(rows) > 2:
            blockers.add(f"{specimen_id} appears in {len(rows)} cases; maximum is 2")
        elif len(rows) == 1:
            repeated = rows[0]["repeated_capture"]
            assert isinstance(repeated, Mapping)
            if (
                repeated["repeated_case_id"] is not None
                or repeated["capture_difference_fields"] != []
                or repeated["capture_difference_rationale"] != ""
            ):
                case_id = rows[0]["case_id"]
                blockers.add(f"{case_id} singleton case cannot declare repetition")
        elif len(rows) == 2:
            first_capture = rows[0]["capture"]
            second_capture = rows[1]["capture"]
            assert isinstance(first_capture, Mapping) and isinstance(second_capture, Mapping)
            if not _capture_complete(first_capture) or not _capture_complete(second_capture):
                blockers.add(f"{specimen_id} repeated cases require complete capture metadata")
            elif _capture_conditions(first_capture) == _capture_conditions(second_capture):
                blockers.add(f"{specimen_id} repeated cases require materially different capture conditions")

            first_id = rows[0]["case_id"]
            second_id = rows[1]["case_id"]
            first_repeat = rows[0]["repeated_capture"]
            second_repeat = rows[1]["repeated_capture"]
            assert isinstance(first_repeat, Mapping) and isinstance(second_repeat, Mapping)

            if first_repeat["repeated_case_id"] != second_id or second_repeat["repeated_case_id"] != first_id:
                blockers.add(f"{specimen_id} repeated cases must declare reciprocal repeated_case_id values")

            if not _nonempty_text(first_repeat["capture_difference_rationale"]) or not _nonempty_text(
                second_repeat["capture_difference_rationale"]
            ):
                blockers.add(f"{specimen_id} repeated cases require capture difference rationale")

            if _capture_complete(first_capture) and _capture_complete(second_capture):
                first_conditions = first_capture["capture_conditions"]
                second_conditions = second_capture["capture_conditions"]
                assert isinstance(first_conditions, Mapping) and isinstance(second_conditions, Mapping)
                actual_differences = [
                    field
                    for field in CAPTURE_FIELDS
                    if first_conditions[field] != second_conditions[field]
                ]
                for row, metadata in ((rows[0], first_repeat), (rows[1], second_repeat)):
                    declared = metadata["capture_difference_fields"]
                    if declared != actual_differences:
                        blockers.add(
                            f"{row['case_id']}.repeated_capture.capture_difference_fields "
                            "must exactly match differing capture conditions"
                        )

    if len(stability_cases) != 10:
        blockers.add(f"stability subset requires exactly 10 cases; found {len(stability_cases)}")
    stability_specimens = [row["specimen_id"] for row in stability_cases]
    if len(stability_specimens) != len(set(stability_specimens)):
        blockers.add("stability subset must use distinct specimens")
    stability_actions = {row["expected_action"] for row in stability_cases}
    if not EXPECTED_ACTIONS.issubset(stability_actions):
        blockers.add("stability subset must include both identify and abstain")
    covered_cohorts = {
        cohort
        for row in stability_cases
        for cohort in row["cohorts"]
        if isinstance(cohort, str)
    }
    missing_cohorts = sorted(set(stability_cohorts) - covered_cohorts)
    if missing_cohorts:
        blockers.add("stability subset misses required cohorts: " + ", ".join(missing_cohorts))

    if not stability_cohorts:
        warnings.add("no stability-relevant cohorts are declared")

    summary = {
        "cases": len(cases),
        "identify_cases": actions["identify"],
        "abstain_cases": actions["abstain"],
        "specimens": len(by_specimen),
        "stability_cases": len(stability_cases),
        "ground_truth_reviews_complete": completed_gt,
        "action_reviews_complete": completed_action,
        "captures_complete": completed_capture,
        "near_duplicate_reviews_complete": completed_near_duplicate,
        "provider_eligibility_approved": approved_eligibility,
    }
    ordered_blockers = tuple(sorted(blockers))
    ordered_warnings = tuple(sorted(warnings))
    return ReadinessReport(
        ready_for_freeze=not ordered_blockers,
        blockers=ordered_blockers,
        warnings=ordered_warnings,
        summary=summary,
    )


def prepare_for_freeze(payload: Mapping[str, object]) -> dict[str, object]:
    """Create a deterministic pre-freeze handoff; never invent frozen digests."""
    report = evaluate_readiness(payload)
    if not report.ready_for_freeze:
        raise DesktopAcceptanceAuthoringError(
            "authoring plan is not ready for freeze: " + "; ".join(report.blockers)
        )

    prepared_cases: list[dict[str, object]] = []
    cases = payload["cases"]
    assert isinstance(cases, list)
    for raw in cases:
        assert isinstance(raw, Mapping)
        gt_ok, gt_identity, _ = _review_resolution(raw["ground_truth_review"], "identity")
        action_ok, reviewed_action, _ = _review_resolution(raw["action_review"], "action")
        if not gt_ok or not action_ok:
            raise DesktopAcceptanceAuthoringError("ready plan lost resolved review state")
        capture = raw["capture"]
        assert isinstance(capture, Mapping)
        prepared_cases.append(
            {
                "case_id": raw["case_id"],
                "specimen_id": raw["specimen_id"],
                "expected_action": reviewed_action,
                "expected_identity": gt_identity,
                "cohorts": list(raw["cohorts"]),
                "stability": raw["stability"],
                "provenance": dict(raw["provenance"]),
                "provider_eligibility": dict(raw["provider_eligibility"]),
                "capture": {
                    "obverse_path": capture["obverse_path"],
                    "reverse_path": capture["reverse_path"],
                    "capture_conditions": dict(capture["capture_conditions"]),
                },
                "ground_truth_review": _copy_json_value(raw["ground_truth_review"]),
                "action_review": _copy_json_value(raw["action_review"]),
                "repeated_capture": _copy_json_value(raw["repeated_capture"]),
                "near_duplicate_review": dict(raw["near_duplicate_review"]),
                "notes": raw["notes"],
            }
        )

    return {
        "schema": FREEZE_PREPARATION_SCHEMA,
        "version": FREEZE_PREPARATION_VERSION,
        "source_authoring_schema": AUTHORING_SCHEMA,
        "source_authoring_version": AUTHORING_VERSION,
        "stability_relevant_cohorts": list(payload["stability_relevant_cohorts"]),
        "cases": prepared_cases,
        "required_next_steps": [
            "freeze exact obverse/reverse image bytes",
            "compute and record SHA-256 image digests",
            "complete frozen transformation ledger",
            "bind canonicalization policy digest",
            "compute frozen schema/ground-truth/action/transformation/manifest digests",
            "validate the resulting artifact with the strict frozen desktop acceptance loader",
        ],
        "benchmark_execution_approved": False,
    }


def readiness_json(payload: Mapping[str, object]) -> str:
    """Serialize readiness deterministically for CLI/automation consumption."""
    return json.dumps(
        evaluate_readiness(payload).as_dict(),
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate_plan_shape(payload: object) -> None:
    if not isinstance(payload, Mapping):
        raise DesktopAcceptanceAuthoringError("authoring plan must be an object")
    required = {"schema", "version", "stability_relevant_cohorts", "cases"}
    if set(payload) != required:
        raise DesktopAcceptanceAuthoringError("authoring plan has unexpected or missing top-level fields")
    if payload["schema"] != AUTHORING_SCHEMA or payload["version"] != AUTHORING_VERSION:
        raise DesktopAcceptanceAuthoringError("unsupported authoring schema/version")
    cohorts = payload["stability_relevant_cohorts"]
    if not isinstance(cohorts, list) or not all(_nonempty_text(v) for v in cohorts):
        raise DesktopAcceptanceAuthoringError("stability_relevant_cohorts must be an array of strings")
    cases = payload["cases"]
    if not isinstance(cases, list):
        raise DesktopAcceptanceAuthoringError("cases must be an array")
    for index, raw in enumerate(cases):
        _validate_case_shape(raw, index)


def _validate_case_shape(raw: object, index: int) -> None:
    if not isinstance(raw, Mapping):
        raise DesktopAcceptanceAuthoringError(f"cases[{index}] must be an object")
    required = {
        "case_id", "specimen_id", "expected_action", "candidate_identity", "cohorts",
        "provenance", "provider_eligibility", "ground_truth_review", "action_review",
        "capture", "repeated_capture", "near_duplicate_review", "stability", "notes",
    }
    if set(raw) != required:
        raise DesktopAcceptanceAuthoringError(f"cases[{index}] has unexpected or missing fields")
    identity = raw["candidate_identity"]
    if not isinstance(identity, Mapping) or set(identity) != {"country", "denomination", "year"}:
        raise DesktopAcceptanceAuthoringError(f"cases[{index}].candidate_identity has invalid shape")
    for name in ("country", "denomination", "year"):
        if identity[name] is not None and not isinstance(identity[name], str):
            raise DesktopAcceptanceAuthoringError(f"cases[{index}].candidate_identity.{name} must be string or null")
    provenance = raw["provenance"]
    if not isinstance(provenance, Mapping) or set(provenance) != {"ownership_or_source", "evidence_reference", "notes"}:
        raise DesktopAcceptanceAuthoringError(f"cases[{index}].provenance has invalid shape")
    eligibility = raw["provider_eligibility"]
    if not isinstance(eligibility, Mapping) or set(eligibility) != {"privacy", "licensing", "provider_authorization"}:
        raise DesktopAcceptanceAuthoringError(f"cases[{index}].provider_eligibility has invalid shape")
    _validate_review_shape(raw["ground_truth_review"], f"cases[{index}].ground_truth_review")
    _validate_review_shape(raw["action_review"], f"cases[{index}].action_review")
    capture = raw["capture"]
    if not isinstance(capture, Mapping) or set(capture) != {"status", "obverse_path", "reverse_path", "capture_conditions"}:
        raise DesktopAcceptanceAuthoringError(f"cases[{index}].capture has invalid shape")
    conditions = capture["capture_conditions"]
    if not isinstance(conditions, Mapping) or set(conditions) != set(CAPTURE_FIELDS):
        raise DesktopAcceptanceAuthoringError(f"cases[{index}].capture.capture_conditions has invalid shape")
    repeated = raw["repeated_capture"]
    if not isinstance(repeated, Mapping) or set(repeated) != {
        "repeated_case_id", "capture_difference_fields", "capture_difference_rationale"
    }:
        raise DesktopAcceptanceAuthoringError(f"cases[{index}].repeated_capture has invalid shape")
    repeated_case_id = repeated["repeated_case_id"]
    if repeated_case_id is not None and (
        not isinstance(repeated_case_id, str) or not _CASE_ID.fullmatch(repeated_case_id)
    ):
        raise DesktopAcceptanceAuthoringError(f"cases[{index}].repeated_capture.repeated_case_id is invalid")
    difference_fields = repeated["capture_difference_fields"]
    if (
        not isinstance(difference_fields, list)
        or any(field not in CAPTURE_FIELDS for field in difference_fields)
        or len(difference_fields) != len(set(difference_fields))
    ):
        raise DesktopAcceptanceAuthoringError(
            f"cases[{index}].repeated_capture.capture_difference_fields is invalid"
        )
    if not isinstance(repeated["capture_difference_rationale"], str):
        raise DesktopAcceptanceAuthoringError(
            f"cases[{index}].repeated_capture.capture_difference_rationale must be a string"
        )
    duplicate = raw["near_duplicate_review"]
    if not isinstance(duplicate, Mapping) or set(duplicate) != {"status", "evidence_reference"}:
        raise DesktopAcceptanceAuthoringError(f"cases[{index}].near_duplicate_review has invalid shape")
    if not isinstance(raw["notes"], str):
        raise DesktopAcceptanceAuthoringError(f"cases[{index}].notes must be a string")


def _validate_review_shape(review: object, label: str) -> None:
    if not isinstance(review, Mapping) or set(review) != {"state", "reviewers", "adjudication"}:
        raise DesktopAcceptanceAuthoringError(f"{label} has invalid shape")
    if review["state"] not in REVIEW_DECISION_STATES:
        raise DesktopAcceptanceAuthoringError(f"{label}.state is unsupported")
    reviewers = review["reviewers"]
    if not isinstance(reviewers, list):
        raise DesktopAcceptanceAuthoringError(f"{label}.reviewers must be an array")
    for reviewer in reviewers:
        if not isinstance(reviewer, Mapping) or set(reviewer) != {"reviewer_id", "decision", "evidence_reference"}:
            raise DesktopAcceptanceAuthoringError(f"{label}.reviewers entry has invalid shape")
    adjudication = review["adjudication"]
    if adjudication is not None:
        if not isinstance(adjudication, Mapping) or set(adjudication) != {
            "reviewer_id", "decision", "evidence_reference", "rationale"
        }:
            raise DesktopAcceptanceAuthoringError(f"{label}.adjudication has invalid shape")


def _review_resolution(review: object, kind: str) -> tuple[bool, object | None, tuple[str, ...]]:
    assert isinstance(review, Mapping)
    errors: list[str] = []
    if review["state"] != "complete":
        return False, None, ("is incomplete",)
    reviewers = review["reviewers"]
    assert isinstance(reviewers, list)
    if len(reviewers) != 2:
        return False, None, ("requires exactly two reviewers",)
    reviewer_ids: list[str] = []
    decisions: list[object] = []
    for position, reviewer in enumerate(reviewers):
        assert isinstance(reviewer, Mapping)
        reviewer_id = reviewer["reviewer_id"]
        evidence = reviewer["evidence_reference"]
        decision = reviewer["decision"]
        if not _nonempty_text(reviewer_id):
            errors.append(f"reviewer {position + 1} has no reviewer_id")
        else:
            reviewer_ids.append(reviewer_id)
        if not _nonempty_text(evidence):
            errors.append(f"reviewer {position + 1} has no evidence_reference")
        if not _valid_decision(decision, kind):
            errors.append(f"reviewer {position + 1} has invalid decision")
        decisions.append(_normalized_decision(decision, kind))
    if len(reviewer_ids) == 2 and reviewer_ids[0] == reviewer_ids[1]:
        errors.append("requires two distinct reviewers")
    if errors:
        return False, None, tuple(errors)

    if decisions[0] == decisions[1]:
        if review["adjudication"] is not None:
            errors.append("must not include adjudication when reviewers agree")
        return not errors, decisions[0], tuple(errors)

    adjudication = review["adjudication"]
    if adjudication is None:
        return False, None, ("reviewer disagreement requires adjudication",)
    assert isinstance(adjudication, Mapping)
    adjudicator = adjudication["reviewer_id"]
    if not _nonempty_text(adjudicator) or adjudicator in reviewer_ids:
        errors.append("adjudicator must be a distinct third reviewer")
    if not _nonempty_text(adjudication["evidence_reference"]):
        errors.append("adjudication requires evidence_reference")
    if not _nonempty_text(adjudication["rationale"]):
        errors.append("adjudication requires rationale")
    if not _valid_decision(adjudication["decision"], kind):
        errors.append("adjudication has invalid decision")
    resolved = _normalized_decision(adjudication["decision"], kind)
    return not errors, resolved if not errors else None, tuple(errors)


def _valid_decision(value: object, kind: str) -> bool:
    if kind == "action":
        return value in EXPECTED_ACTIONS
    return isinstance(value, Mapping) and _complete_identity(value)


def _normalized_decision(value: object, kind: str) -> object:
    if kind == "action":
        return value
    if isinstance(value, Mapping):
        return _identity_projection(value)
    return value


def _identity_projection(value: Mapping[str, object]) -> dict[str, object]:
    return {key: value.get(key) for key in ("country", "denomination", "year")}


def _complete_identity(value: Mapping[str, object]) -> bool:
    return set(value) == {"country", "denomination", "year"} and all(
        _nonempty_text(value.get(key)) for key in ("country", "denomination", "year")
    )


def _capture_complete(capture: Mapping[str, object]) -> bool:
    if capture["status"] not in CAPTURE_STATES or capture["status"] != "complete":
        return False
    if not _nonempty_text(capture["obverse_path"]) or not _nonempty_text(capture["reverse_path"]):
        return False
    conditions = capture["capture_conditions"]
    return isinstance(conditions, Mapping) and all(_nonempty_text(conditions.get(field)) for field in CAPTURE_FIELDS)


def _capture_conditions(capture: Mapping[str, object]) -> tuple[object, ...]:
    conditions = capture["capture_conditions"]
    assert isinstance(conditions, Mapping)
    return tuple(conditions[field] for field in CAPTURE_FIELDS)


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _copy_json_value(value: object) -> object:
    return json.loads(json.dumps(value, allow_nan=False, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    """Small readiness CLI.  Use ``--json`` for deterministic machine output."""
    import argparse

    parser = argparse.ArgumentParser(description="Audit desktop acceptance authoring readiness")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    payload = load_authoring_plan(args.plan)
    report = evaluate_readiness(payload)
    if args.as_json:
        print(readiness_json(payload))
    else:
        print(f"ready_for_freeze: {str(report.ready_for_freeze).lower()}")
        for key, value in report.summary.items():
            print(f"{key}: {value}")
        for blocker in report.blockers:
            print(f"BLOCKER: {blocker}")
        for warning in report.warnings:
            print(f"WARNING: {warning}")
    return 0 if report.ready_for_freeze else 2


if __name__ == "__main__":
    raise SystemExit(main())
