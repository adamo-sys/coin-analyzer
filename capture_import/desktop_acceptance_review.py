"""Strict review-execution records for desktop acceptance v1.

This module validates human-originated review records.  It does not generate
packets, reconcile decisions with the authoring plan, mutate authoring state, or
authorize recognition, photography, or benchmark execution.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Mapping, TypeAlias
from urllib.parse import unquote, urlsplit


REVIEW_EXECUTION_SCHEMA = "coin-analyzer-desktop-acceptance-review-execution"
REVIEW_EXECUTION_VERSION = "1.0.0"
REVIEW_STATES = frozenset({"unresolved", "complete"})
ELIGIBILITY_STATES = frozenset({"unresolved", "approved", "rejected"})
EXPECTED_ACTIONS = frozenset({"identify", "abstain"})
ELIGIBILITY_FIELDS = ("privacy", "licensing", "provider_authorization")

_CASE_ID = re.compile(r"^case-[0-9]{3}$")
_SPECIMEN_ID = re.compile(r"^specimen-[0-9]{3}$")
_SAFE_REVIEWER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:")
_OBVIOUS_CREDENTIAL = re.compile(
    r"(?:^|[.:_-])(?:password|passwd|secret|api[_-]?key|credential|bearer)(?:$|[=:._-])",
    re.IGNORECASE,
)


class DesktopAcceptanceReviewError(ValueError):
    """A review execution record is unreadable, malformed, or inconsistent."""


@dataclass(frozen=True, slots=True)
class IdentityDecision:
    country: str
    denomination: str
    year: str

    def as_dict(self) -> dict[str, str]:
        return {
            "country": self.country,
            "denomination": self.denomination,
            "year": self.year,
        }


ReviewDecision: TypeAlias = IdentityDecision | str


@dataclass(frozen=True, slots=True)
class ReviewSubmission:
    reviewer_id: str
    decision: ReviewDecision
    evidence_references: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "reviewer_id": self.reviewer_id,
            "decision": _decision_as_json(self.decision),
            "evidence_references": list(self.evidence_references),
        }


@dataclass(frozen=True, slots=True)
class ReviewAdjudication:
    reviewer_id: str
    decision: ReviewDecision
    evidence_references: tuple[str, ...]
    rationale: str

    def as_dict(self) -> dict[str, object]:
        return {
            "reviewer_id": self.reviewer_id,
            "decision": _decision_as_json(self.decision),
            "evidence_references": list(self.evidence_references),
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class ReviewTrack:
    state: str
    submissions: tuple[ReviewSubmission, ...]
    adjudication: ReviewAdjudication | None

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "submissions": [submission.as_dict() for submission in self.submissions],
            "adjudication": None if self.adjudication is None else self.adjudication.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    state: str
    evidence_references: tuple[str, ...]

    @property
    def approved(self) -> bool:
        return self.state == "approved"

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "evidence_references": list(self.evidence_references),
        }


@dataclass(frozen=True, slots=True)
class ProviderEligibility:
    privacy: EligibilityDecision
    licensing: EligibilityDecision
    provider_authorization: EligibilityDecision

    @property
    def approved(self) -> bool:
        return all(getattr(self, field).approved for field in ELIGIBILITY_FIELDS)

    def as_dict(self) -> dict[str, object]:
        return {field: getattr(self, field).as_dict() for field in ELIGIBILITY_FIELDS}


@dataclass(frozen=True, slots=True)
class ReviewCaseRecord:
    case_id: str
    specimen_id: str
    ground_truth_review: ReviewTrack
    action_review: ReviewTrack
    provider_eligibility: ProviderEligibility

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "specimen_id": self.specimen_id,
            "ground_truth_review": self.ground_truth_review.as_dict(),
            "action_review": self.action_review.as_dict(),
            "provider_eligibility": self.provider_eligibility.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class ReviewExecutionRecord:
    schema: str
    version: str
    cases: tuple[ReviewCaseRecord, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "cases": [case.as_dict() for case in self.cases],
        }


def load_review_execution_record(
    path: str | Path, authoring_state: Mapping[str, object]
) -> ReviewExecutionRecord:
    """Load and strictly validate a UTF-8 JSON review execution record."""
    record_path = Path(path)
    try:
        payload = json.loads(
            record_path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except DesktopAcceptanceReviewError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DesktopAcceptanceReviewError(
            f"cannot read review execution record: {error}"
        ) from error
    return validate_review_execution_record(payload, authoring_state)


def validate_review_execution_record(
    payload: object, authoring_state: Mapping[str, object]
) -> ReviewExecutionRecord:
    """Return an immutable, deterministically ordered record or fail closed."""
    authoring_roster = _authoring_roster(authoring_state)
    root = _require_mapping(payload, "review execution record")
    _require_exact_keys(root, {"schema", "version", "cases"}, "review execution record")
    if root["schema"] != REVIEW_EXECUTION_SCHEMA or root["version"] != REVIEW_EXECUTION_VERSION:
        raise DesktopAcceptanceReviewError("unsupported review execution schema/version")

    raw_cases = root["cases"]
    if not isinstance(raw_cases, list):
        raise DesktopAcceptanceReviewError("cases must be an array")

    cases: list[ReviewCaseRecord] = []
    seen_case_ids: set[str] = set()
    for index, raw_case in enumerate(raw_cases):
        case = _validate_case(raw_case, f"cases[{index}]", authoring_roster)
        if case.case_id in seen_case_ids:
            raise DesktopAcceptanceReviewError(f"duplicate case record: {case.case_id}")
        seen_case_ids.add(case.case_id)
        cases.append(case)

    expected = set(authoring_roster)
    missing = sorted(expected - seen_case_ids)
    unsupported = sorted(seen_case_ids - expected)
    if missing or unsupported:
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unsupported:
            details.append("unsupported " + ", ".join(unsupported))
        raise DesktopAcceptanceReviewError("case roster mismatch: " + "; ".join(details))

    return ReviewExecutionRecord(
        schema=REVIEW_EXECUTION_SCHEMA,
        version=REVIEW_EXECUTION_VERSION,
        cases=tuple(sorted(cases, key=lambda case: case.case_id)),
    )


def normalized_review_execution_json(
    record: ReviewExecutionRecord, authoring_state: Mapping[str, object]
) -> str:
    """Serialize a validated record in one deterministic JSON representation."""
    if not isinstance(record, ReviewExecutionRecord):
        raise TypeError("record must be a ReviewExecutionRecord")
    validated = validate_review_execution_record(record.as_dict(), authoring_state)
    return json.dumps(
        validated.as_dict(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"


def _authoring_roster(authoring_state: object) -> dict[str, str]:
    raw = _require_mapping(authoring_state, "authoring state")
    raw_cases = raw.get("cases")
    if not isinstance(raw_cases, list):
        raise DesktopAcceptanceReviewError("authoring state cases must be an array")
    roster: dict[str, str] = {}
    for index, value in enumerate(raw_cases):
        case = _require_mapping(value, f"authoring state cases[{index}]")
        if "case_id" not in case or "specimen_id" not in case:
            raise DesktopAcceptanceReviewError(
                f"authoring state cases[{index}] requires case_id and specimen_id"
            )
        case_id = _require_matching_text(
            case["case_id"], _CASE_ID, f"authoring state cases[{index}].case_id"
        )
        specimen_id = _require_matching_text(
            case["specimen_id"],
            _SPECIMEN_ID,
            f"authoring state cases[{index}].specimen_id",
        )
        if case_id in roster:
            raise DesktopAcceptanceReviewError(f"duplicate authoring case: {case_id}")
        roster[case_id] = specimen_id
    return roster


def _validate_case(
    value: object, label: str, authoring_roster: Mapping[str, str]
) -> ReviewCaseRecord:
    raw = _require_mapping(value, label)
    _require_exact_keys(
        raw,
        {"case_id", "specimen_id", "ground_truth_review", "action_review", "provider_eligibility"},
        label,
    )
    case_id = _require_matching_text(raw["case_id"], _CASE_ID, f"{label}.case_id")
    specimen_id = _require_matching_text(raw["specimen_id"], _SPECIMEN_ID, f"{label}.specimen_id")
    expected_specimen = authoring_roster.get(case_id)
    if expected_specimen is not None and specimen_id != expected_specimen:
        raise DesktopAcceptanceReviewError(
            f"{case_id}.specimen_id must be {expected_specimen}; found {specimen_id}"
        )

    ground_truth = _validate_track(raw["ground_truth_review"], "identity", f"{case_id}.ground_truth_review")
    action = _validate_track(raw["action_review"], "action", f"{case_id}.action_review")
    if action.submissions and ground_truth.state != "complete":
        raise DesktopAcceptanceReviewError(
            f"{case_id}.action_review cannot contain submissions before ground truth is complete"
        )

    eligibility = _validate_provider_eligibility(
        raw["provider_eligibility"], f"{case_id}.provider_eligibility"
    )
    return ReviewCaseRecord(case_id, specimen_id, ground_truth, action, eligibility)


def _validate_track(value: object, kind: str, label: str) -> ReviewTrack:
    raw = _require_mapping(value, label)
    _require_exact_keys(raw, {"state", "submissions", "adjudication"}, label)
    state = raw["state"]
    if not isinstance(state, str) or state not in REVIEW_STATES:
        raise DesktopAcceptanceReviewError(f"{label}.state is unsupported")
    raw_submissions = raw["submissions"]
    if not isinstance(raw_submissions, list):
        raise DesktopAcceptanceReviewError(f"{label}.submissions must be an array")
    if len(raw_submissions) > 2:
        raise DesktopAcceptanceReviewError(f"{label} cannot contain more than two submissions")

    submissions = [
        _validate_submission(item, kind, f"{label}.submissions[{index}]")
        for index, item in enumerate(raw_submissions)
    ]
    reviewer_ids = [submission.reviewer_id for submission in submissions]
    if len(reviewer_ids) != len(set(reviewer_ids)):
        raise DesktopAcceptanceReviewError(f"{label} requires distinct reviewer IDs")

    adjudication = _validate_optional_adjudication(raw["adjudication"], kind, f"{label}.adjudication")
    if adjudication is not None:
        if len(submissions) != 2 or submissions[0].decision == submissions[1].decision:
            raise DesktopAcceptanceReviewError(
                f"{label}.adjudication is allowed only for two disagreeing submissions"
            )
        if adjudication.reviewer_id in reviewer_ids:
            raise DesktopAcceptanceReviewError(f"{label}.adjudicator must be a distinct reviewer")

    if state == "complete":
        if len(submissions) != 2:
            raise DesktopAcceptanceReviewError(
                f"{label}.complete state requires exactly two submissions"
            )
        disagree = submissions[0].decision != submissions[1].decision
        if disagree and adjudication is None:
            raise DesktopAcceptanceReviewError(
                f"{label}.complete disagreement requires adjudication"
            )

    return ReviewTrack(
        state=state,
        submissions=tuple(sorted(submissions, key=lambda submission: submission.reviewer_id)),
        adjudication=adjudication,
    )


def _validate_submission(value: object, kind: str, label: str) -> ReviewSubmission:
    raw = _require_mapping(value, label)
    _require_exact_keys(raw, {"reviewer_id", "decision", "evidence_references"}, label)
    return ReviewSubmission(
        reviewer_id=_validate_reviewer_id(raw["reviewer_id"], f"{label}.reviewer_id"),
        decision=_validate_decision(raw["decision"], kind, f"{label}.decision"),
        evidence_references=_validate_evidence_references(
            raw["evidence_references"], f"{label}.evidence_references", required=True
        ),
    )


def _validate_optional_adjudication(
    value: object, kind: str, label: str
) -> ReviewAdjudication | None:
    if value is None:
        return None
    raw = _require_mapping(value, label)
    _require_exact_keys(
        raw, {"reviewer_id", "decision", "evidence_references", "rationale"}, label
    )
    return ReviewAdjudication(
        reviewer_id=_validate_reviewer_id(raw["reviewer_id"], f"{label}.reviewer_id"),
        decision=_validate_decision(raw["decision"], kind, f"{label}.decision"),
        evidence_references=_validate_evidence_references(
            raw["evidence_references"], f"{label}.evidence_references", required=True
        ),
        rationale=_require_clean_text(raw["rationale"], f"{label}.rationale"),
    )


def _validate_decision(value: object, kind: str, label: str) -> ReviewDecision:
    if kind == "action":
        if not isinstance(value, str) or value not in EXPECTED_ACTIONS:
            raise DesktopAcceptanceReviewError(f"{label} must be identify or abstain")
        return value

    raw = _require_mapping(value, label)
    _require_exact_keys(raw, {"country", "denomination", "year"}, label)
    return IdentityDecision(
        country=_require_clean_text(raw["country"], f"{label}.country"),
        denomination=_require_clean_text(raw["denomination"], f"{label}.denomination"),
        year=_require_clean_text(raw["year"], f"{label}.year"),
    )


def _validate_provider_eligibility(value: object, label: str) -> ProviderEligibility:
    raw = _require_mapping(value, label)
    _require_exact_keys(raw, set(ELIGIBILITY_FIELDS), label)
    decisions = {
        field: _validate_eligibility_decision(raw[field], f"{label}.{field}")
        for field in ELIGIBILITY_FIELDS
    }
    return ProviderEligibility(**decisions)


def _validate_eligibility_decision(value: object, label: str) -> EligibilityDecision:
    raw = _require_mapping(value, label)
    _require_exact_keys(raw, {"state", "evidence_references"}, label)
    state = raw["state"]
    if not isinstance(state, str) or state not in ELIGIBILITY_STATES:
        raise DesktopAcceptanceReviewError(f"{label}.state is unsupported")
    evidence = _validate_evidence_references(
        raw["evidence_references"],
        f"{label}.evidence_references",
        required=state == "approved",
    )
    return EligibilityDecision(state=state, evidence_references=evidence)


def _validate_evidence_references(value: object, label: str, *, required: bool) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise DesktopAcceptanceReviewError(f"{label} must be an array")
    references: list[str] = []
    for index, item in enumerate(value):
        references.append(_validate_evidence_reference(item, f"{label}[{index}]"))
    if len(references) != len(set(references)):
        raise DesktopAcceptanceReviewError(f"{label} contains duplicate references")
    if required and not references:
        raise DesktopAcceptanceReviewError(f"{label} requires supporting evidence")
    return tuple(sorted(references))


def _validate_reviewer_id(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DesktopAcceptanceReviewError(f"{label} must be an opaque sanitized reviewer ID")
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        raise DesktopAcceptanceReviewError(f"{label} must be an opaque sanitized reviewer ID")
    if not _SAFE_REVIEWER_ID.fullmatch(value):
        raise DesktopAcceptanceReviewError(f"{label} must be an opaque sanitized reviewer ID")
    if (
        "@" in value
        or "/" in value
        or "\\" in value
        or ".." in value
        or "://" in value
        or _WINDOWS_DRIVE_PATH.match(value)
        or _OBVIOUS_CREDENTIAL.search(value)
    ):
        raise DesktopAcceptanceReviewError(f"{label} must be an opaque sanitized reviewer ID")
    return value


def _validate_evidence_reference(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")
    lower_value = value.lower()
    if "\\" in value or "@" in value or _OBVIOUS_CREDENTIAL.search(value):
        raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")
    if (
        value.startswith(("/", "~", "./", "../", "$", "%"))
        or _WINDOWS_DRIVE_PATH.match(value)
        or re.search(r"(?:^|:)[A-Za-z]:/", value)
        or lower_value.startswith(("file:", "private:"))
    ):
        raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")

    parsed = urlsplit(value)
    if parsed.scheme and "://" in value:
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")
        path_to_check = unquote(parsed.path)
    else:
        if value.startswith("//") or "://" in value:
            raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")
        path_to_check = unquote(value.split("#", 1)[0].split("?", 1)[0])

    if any(segment == ".." for segment in path_to_check.split("/")):
        raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")
    return value


def _require_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DesktopAcceptanceReviewError(f"{label} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise DesktopAcceptanceReviewError(f"{label} contains a non-string key")
    return value


def _require_exact_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unsupported " + ", ".join(extra))
        raise DesktopAcceptanceReviewError(f"{label} has invalid fields: " + "; ".join(details))


def _require_clean_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DesktopAcceptanceReviewError(f"{label} must be non-empty normalized text")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise DesktopAcceptanceReviewError(f"{label} contains control characters")
    return value


def _require_matching_text(value: object, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise DesktopAcceptanceReviewError(f"{label} has invalid format")
    return value


def _decision_as_json(decision: ReviewDecision) -> object:
    return decision.as_dict() if isinstance(decision, IdentityDecision) else decision


def _object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DesktopAcceptanceReviewError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_non_json_constant(value: str) -> object:
    raise DesktopAcceptanceReviewError(f"unsupported JSON constant: {value}")
