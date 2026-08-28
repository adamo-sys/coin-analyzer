"""Fail-closed offline contract for the frozen desktop acceptance corpus."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Mapping

from .evaluation_case_contract import PRIVACY_CLASSIFICATIONS

SCHEMA = "coin-analyzer-real-world-desktop-acceptance-set"
VERSION = "1.0.0"
POLICY_ID = "coin-analyzer-desktop-acceptance-canonicalization"
POLICY_VERSION = "1.0.0"
EXPECTED_ACTIONS = frozenset({"identify", "abstain"})
IMAGE_ROLES = ("obverse", "reverse")
RESERVED_ATTRIBUTION_FIELDS = ("mint", "mint_mark", "variety", "catalog_reference")
CAPTURE_FIELDS = ("background", "device", "distance", "lighting", "orientation")
PERMITTED_TRANSFORMATIONS = frozenset(
    {"none", "format_conversion", "orientation_rotation", "color_profile_normalization"}
)
_CASE_ID = re.compile(r"^case-[0-9]{3}$")
_SPECIMEN_ID = re.compile(r"^specimen-[0-9]{3}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class DesktopAcceptanceManifestError(ValueError):
    """The desktop acceptance manifest is unsafe, stale, or malformed."""


@dataclass(frozen=True, slots=True)
class DesktopAcceptanceImage:
    role: str
    path: Path
    relative_path: str
    sha256: str
    provenance: Mapping[str, str]
    transformation: Mapping[str, object]
    provider_eligibility: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class DesktopAcceptanceCase:
    case_id: str
    specimen_id: str
    repeated_case_id: str | None
    expected_action: str
    expected_identity: Mapping[str, str]
    reserved_attribution: Mapping[str, None]
    capture_conditions: Mapping[str, str]
    capture_difference_fields: tuple[str, ...] | None
    capture_difference_rationale: str | None
    cohorts: tuple[str, ...]
    stability: bool
    privacy_classification: str
    prior_benchmark_use: Mapping[str, object]
    ground_truth_review: Mapping[str, object]
    action_review: Mapping[str, object]
    images: tuple[DesktopAcceptanceImage, DesktopAcceptanceImage]
    notes: str


@dataclass(frozen=True, slots=True)
class DesktopAcceptanceManifest:
    root: Path
    cases: tuple[DesktopAcceptanceCase, ...]
    canonicalization_policy: Mapping[str, str]
    freeze: Mapping[str, object]
    stability_relevant_cohorts: tuple[str, ...]
    schema: str = SCHEMA
    version: str = VERSION


def canonical_json_bytes(value: object) -> bytes:
    """Return the acceptance contract's deterministic JSON representation."""
    try:
        text = json.dumps(
            value, allow_nan=False, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise DesktopAcceptanceManifestError(
            f"manifest is not canonical-JSON compatible: {error}"
        ) from error
    return text.encode("utf-8")


def compute_desktop_acceptance_digests(
    payload: Mapping[str, object], schema_bytes: bytes
) -> dict[str, str]:
    """Compute v1 digests; the manifest projection omits its own digest."""
    cases = payload.get("cases")
    freeze = payload.get("freeze")
    if not isinstance(cases, list) or not isinstance(freeze, Mapping):
        raise DesktopAcceptanceManifestError("cannot compute digests for malformed manifest.")
    ground_truth = [
        {"case_id": case.get("case_id"), "expected_identity": case.get("expected_identity"),
         "ground_truth_review": case.get("ground_truth_review")}
        for case in cases if isinstance(case, Mapping)
    ]
    actions = [
        {"case_id": case.get("case_id"), "expected_action": case.get("expected_action"),
         "action_review": case.get("action_review")}
        for case in cases if isinstance(case, Mapping)
    ]
    transformations = [
        {"case_id": case.get("case_id"), "images": [
            {"role": image.get("role"), "sha256": image.get("sha256"),
             "transformation": image.get("transformation")}
            for image in case.get("images", []) if isinstance(image, Mapping)
        ]}
        for case in cases if isinstance(case, Mapping)
    ]
    digests = {
        "schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
        "ground_truth_sha256": _digest(ground_truth),
        "action_sha256": _digest(actions),
        "transformation_ledger_sha256": _digest(transformations),
    }
    projected = json.loads(json.dumps(payload))
    projected_freeze = projected.get("freeze")
    if isinstance(projected_freeze, dict):
        projected_freeze.pop("manifest_sha256", None)
        projected_freeze.update(digests)
    digests["manifest_sha256"] = _digest(projected)
    return digests


def load_desktop_acceptance_manifest(
    path: str | Path, *, schema_path: str | Path | None = None
) -> DesktopAcceptanceManifest:
    manifest_path = Path(path).resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DesktopAcceptanceManifestError(
            f"cannot read desktop acceptance manifest: {error}"
        ) from error
    if not isinstance(payload, Mapping):
        raise DesktopAcceptanceManifestError("manifest must be an object.")
    _exact_fields(payload, {"schema", "version", "canonicalization_policy", "freeze",
                            "stability_relevant_cohorts", "cases"}, "manifest")
    if payload["schema"] != SCHEMA or payload["version"] != VERSION:
        raise DesktopAcceptanceManifestError("manifest schema/version is unsupported.")
    root = manifest_path.parent
    policy = _policy(root, payload["canonicalization_policy"])
    stability_cohorts = _identifiers(
        payload["stability_relevant_cohorts"], "stability_relevant_cohorts"
    )
    if not stability_cohorts:
        raise DesktopAcceptanceManifestError("stability_relevant_cohorts must not be empty.")
    cases_raw = payload["cases"]
    if not isinstance(cases_raw, list):
        raise DesktopAcceptanceManifestError("cases must be an array.")
    cases = tuple(_case(root, raw, index) for index, raw in enumerate(cases_raw))
    _validate_corpus(cases, stability_cohorts)
    resolved_schema = Path(schema_path).resolve() if schema_path else root / "manifest.schema.json"
    try:
        schema_bytes = resolved_schema.read_bytes()
    except OSError as error:
        raise DesktopAcceptanceManifestError(f"cannot read manifest schema: {error}") from error
    freeze = _freeze(payload["freeze"])
    expected_digests = compute_desktop_acceptance_digests(payload, schema_bytes)
    for field, expected in expected_digests.items():
        if freeze[field] != expected:
            raise DesktopAcceptanceManifestError(f"freeze.{field} does not match frozen content.")
    return DesktopAcceptanceManifest(
        root, cases, policy, freeze, stability_cohorts,
    )


def audit_desktop_acceptance_manifest(
    manifest: DesktopAcceptanceManifest,
) -> dict[str, object]:
    actions = Counter(case.expected_action for case in manifest.cases)
    specimens = Counter(case.specimen_id for case in manifest.cases)
    cohorts = Counter(cohort for case in manifest.cases for cohort in case.cohorts)
    conditions: dict[str, Counter[str]] = defaultdict(Counter)
    for case in manifest.cases:
        for key, value in case.capture_conditions.items():
            conditions[key][value] += 1
    return {
        "schema": manifest.schema,
        "version": manifest.version,
        "cases": len(manifest.cases),
        "images": sum(len(case.images) for case in manifest.cases),
        "specimens": len(specimens),
        "repeated_specimens": sorted(key for key, count in specimens.items() if count == 2),
        "expected_actions": {key: actions[key] for key in sorted(EXPECTED_ACTIONS)},
        "cohorts": dict(sorted(cohorts.items())),
        "stability_cases": [case.case_id for case in manifest.cases if case.stability],
        "capture_conditions": {
            key: dict(sorted(counter.items())) for key, counter in sorted(conditions.items())
        },
        "freeze_digests": {
            key: manifest.freeze[key] for key in sorted(manifest.freeze) if key.endswith("_sha256")
        },
        "leakage_findings": [],
        "ready": True,
    }


def _case(root: Path, raw: object, index: int) -> DesktopAcceptanceCase:
    name = f"cases[{index}]"
    required = {"case_id", "specimen_id", "repeated_case_id", "expected_action",
                "expected_identity", "reserved_attribution", "capture_conditions",
                "capture_difference_fields", "capture_difference_rationale", "cohorts", "stability",
                "privacy_classification", "prior_benchmark_use", "ground_truth_review",
                "action_review", "images", "notes"}
    _exact_fields(raw, required, name)
    assert isinstance(raw, Mapping)
    case_id = _pattern(raw["case_id"], _CASE_ID, f"{name}.case_id")
    specimen_id = _pattern(raw["specimen_id"], _SPECIMEN_ID, f"{name}.specimen_id")
    repeated = _optional_pattern(raw["repeated_case_id"], _CASE_ID, f"{name}.repeated_case_id")
    action = raw["expected_action"]
    if action not in EXPECTED_ACTIONS:
        raise DesktopAcceptanceManifestError(f"{name}.expected_action is unsupported.")
    identity = _identity(raw["expected_identity"], name)
    attribution = _attribution(raw["reserved_attribution"], name)
    capture = _capture(raw["capture_conditions"], name)
    difference_fields = _optional_capture_fields(
        raw["capture_difference_fields"], f"{name}.capture_difference_fields"
    )
    difference = _optional_text(raw["capture_difference_rationale"], f"{name}.capture_difference_rationale")
    cohorts = _identifiers(raw["cohorts"], f"{name}.cohorts")
    if not cohorts:
        raise DesktopAcceptanceManifestError(f"{name}.cohorts must not be empty.")
    stability = raw["stability"]
    if not isinstance(stability, bool):
        raise DesktopAcceptanceManifestError(f"{name}.stability must be boolean.")
    privacy = raw["privacy_classification"]
    if privacy not in PRIVACY_CLASSIFICATIONS:
        raise DesktopAcceptanceManifestError(f"{name}.privacy_classification is unsupported.")
    prior_use = _prior_use(raw["prior_benchmark_use"], name)
    ground_review = _review(raw["ground_truth_review"], name, identity, "ground_truth")
    action_review = _review(raw["action_review"], name, action, "action")
    images_raw = raw["images"]
    if not isinstance(images_raw, list) or len(images_raw) != 2:
        raise DesktopAcceptanceManifestError(f"{name}.images must contain two entries.")
    images = tuple(_image(root, item, name, case_id, privacy) for item in images_raw)
    if tuple(image.role for image in images) != IMAGE_ROLES:
        raise DesktopAcceptanceManifestError(f"{name}.images must be ordered obverse then reverse.")
    notes = raw["notes"]
    if not isinstance(notes, str):
        raise DesktopAcceptanceManifestError(f"{name}.notes must be a string.")
    return DesktopAcceptanceCase(
        case_id, specimen_id, repeated, action, identity, attribution, capture,
        difference_fields, difference, cohorts, stability, privacy, prior_use, ground_review,
        action_review, images, notes,
    )


def _validate_corpus(
    cases: tuple[DesktopAcceptanceCase, ...], stability_cohorts: tuple[str, ...]
) -> None:
    if len(cases) != 30:
        raise DesktopAcceptanceManifestError("frozen v1 requires exactly 30 cases.")
    ids = tuple(case.case_id for case in cases)
    if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
        raise DesktopAcceptanceManifestError("case IDs must be unique and sorted.")
    actions = Counter(case.expected_action for case in cases)
    if actions != Counter({"identify": 24, "abstain": 6}):
        raise DesktopAcceptanceManifestError("frozen v1 requires 24 identify and 6 abstain cases.")
    by_specimen: dict[str, list[DesktopAcceptanceCase]] = defaultdict(list)
    for case in cases:
        by_specimen[case.specimen_id].append(case)
    if len(by_specimen) < 24 or any(len(items) > 2 for items in by_specimen.values()):
        raise DesktopAcceptanceManifestError("frozen v1 specimen limits are violated.")
    for items in by_specimen.values():
        if len(items) == 1:
            if (items[0].repeated_case_id is not None
                    or items[0].capture_difference_fields is not None
                    or items[0].capture_difference_rationale is not None):
                raise DesktopAcceptanceManifestError("single-specimen cases cannot declare repetition.")
        else:
            first, second = items
            if (first.repeated_case_id, second.repeated_case_id) != (second.case_id, first.case_id):
                raise DesktopAcceptanceManifestError("repeated-specimen declarations must be reciprocal.")
            if first.capture_conditions == second.capture_conditions:
                raise DesktopAcceptanceManifestError("repeated specimens require materially different capture conditions.")
            actual_differences = tuple(
                field for field in CAPTURE_FIELDS
                if first.capture_conditions[field] != second.capture_conditions[field]
            )
            if (first.capture_difference_fields != actual_differences
                    or second.capture_difference_fields != actual_differences):
                raise DesktopAcceptanceManifestError(
                    "repeated specimens must declare the exact differing capture fields."
                )
            if first.capture_difference_rationale is None or second.capture_difference_rationale is None:
                raise DesktopAcceptanceManifestError("repeated specimens require capture-difference rationale.")
    hashes = [image.sha256 for case in cases for image in case.images]
    if len(hashes) != len(set(hashes)):
        raise DesktopAcceptanceManifestError("frozen images must have unique bytes; reuse is forbidden.")
    pairs = [(case.images[0].sha256, case.images[1].sha256) for case in cases]
    if len(pairs) != len(set(pairs)):
        raise DesktopAcceptanceManifestError("frozen image pairs must be unique.")
    stability = [case for case in cases if case.stability]
    if len(stability) != 10 or len({case.specimen_id for case in stability}) != 10:
        raise DesktopAcceptanceManifestError("stability subset requires 10 distinct specimens.")
    if {case.expected_action for case in stability} != EXPECTED_ACTIONS:
        raise DesktopAcceptanceManifestError("stability subset must cover both expected actions.")
    covered = {cohort for case in stability for cohort in case.cohorts}
    if not set(stability_cohorts).issubset(covered):
        raise DesktopAcceptanceManifestError("stability subset does not cover relevant cohorts.")


def _image(
    root: Path, raw: object, name: str, case_id: str, privacy: str
) -> DesktopAcceptanceImage:
    required = {"role", "path", "sha256", "provenance", "transformation", "provider_eligibility"}
    _exact_fields(raw, required, f"{name}.images entry")
    assert isinstance(raw, Mapping)
    role = raw["role"]
    if role not in IMAGE_ROLES:
        raise DesktopAcceptanceManifestError(f"{name}.image role is unsupported.")
    relative = _safe_path(raw["path"], f"{name}.images.{role}.path")
    parts = PurePosixPath(relative).parts
    if len(parts) != 3 or parts[0] != "images" or parts[1] != case_id or Path(parts[2]).stem != role:
        raise DesktopAcceptanceManifestError(f"{name}.images.{role}.path is not a non-semantic frozen path.")
    digest = _sha256(raw["sha256"], f"{name}.images.{role}.sha256")
    path = (root / Path(*parts)).resolve()
    try:
        path.relative_to(root)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except (ValueError, OSError) as error:
        raise DesktopAcceptanceManifestError(f"{name}.images.{role} cannot be safely read: {error}") from error
    if actual != digest:
        raise DesktopAcceptanceManifestError(f"{name}.images.{role} SHA-256 does not match frozen bytes.")
    provenance = _string_object(
        raw["provenance"], {"author", "license", "source_reference", "capture_reference"},
        f"{name}.images.{role}.provenance",
    )
    for key in ("source_reference", "capture_reference"):
        _safe_reference(provenance[key], f"{name}.images.{role}.provenance.{key}")
    transformation = _transformation(raw["transformation"], f"{name}.images.{role}.transformation")
    eligibility = _eligibility(raw["provider_eligibility"], f"{name}.images.{role}.provider_eligibility", privacy)
    return DesktopAcceptanceImage(role, path, relative, digest, provenance, transformation, eligibility)


def _review(raw: object, name: str, expected: object, kind: str) -> Mapping[str, object]:
    _exact_fields(raw, {"reviewers", "adjudication"}, f"{name}.{kind}_review")
    assert isinstance(raw, Mapping)
    reviewers = raw["reviewers"]
    if not isinstance(reviewers, list) or len(reviewers) != 2:
        raise DesktopAcceptanceManifestError(f"{name}.{kind}_review requires two reviewers.")
    parsed = []
    for index, item in enumerate(reviewers):
        _exact_fields(item, {"reviewer_id", "decision", "evidence_reference"}, f"{name}.{kind}_review.reviewers[{index}]")
        assert isinstance(item, Mapping)
        reviewer_id = _identifier(item["reviewer_id"], f"{name}.{kind}.reviewer_id")
        evidence = _safe_reference(item["evidence_reference"], f"{name}.{kind}.evidence_reference")
        decision = item["decision"]
        if kind == "ground_truth":
            decision = _identity(decision, f"{name}.{kind}.decision")
        elif decision not in EXPECTED_ACTIONS:
            raise DesktopAcceptanceManifestError(f"{name}.{kind}.decision is unsupported.")
        parsed.append({"reviewer_id": reviewer_id, "decision": decision, "evidence_reference": evidence})
    if parsed[0]["reviewer_id"] == parsed[1]["reviewer_id"]:
        raise DesktopAcceptanceManifestError(f"{name}.{kind}_review reviewers must be independent.")
    decisions_agree = parsed[0]["decision"] == parsed[1]["decision"]
    adjudication = raw["adjudication"]
    final = parsed[0]["decision"] if decisions_agree else None
    if decisions_agree:
        if adjudication is not None:
            raise DesktopAcceptanceManifestError(f"{name}.{kind}_review cannot adjudicate agreement.")
    else:
        _exact_fields(adjudication, {"adjudicator_id", "decision", "rationale", "evidence_reference"}, f"{name}.{kind}_review.adjudication")
        assert isinstance(adjudication, Mapping)
        adjudicator = _identifier(adjudication["adjudicator_id"], f"{name}.{kind}.adjudicator_id")
        if adjudicator in {item["reviewer_id"] for item in parsed}:
            raise DesktopAcceptanceManifestError(f"{name}.{kind} adjudicator must be independent.")
        _text(adjudication["rationale"], f"{name}.{kind}.rationale")
        _safe_reference(adjudication["evidence_reference"], f"{name}.{kind}.adjudication.evidence_reference")
        final = adjudication["decision"]
        if kind == "ground_truth":
            final = _identity(final, f"{name}.{kind}.adjudication.decision")
        elif final not in EXPECTED_ACTIONS:
            raise DesktopAcceptanceManifestError(f"{name}.{kind}.adjudication.decision is unsupported.")
    if final != expected:
        raise DesktopAcceptanceManifestError(f"{name}.{kind}_review does not establish frozen value.")
    return {"reviewers": tuple(parsed), "adjudication": adjudication}


def _freeze(raw: object) -> Mapping[str, object]:
    fields = {"corpus_version", "frozen_at_utc", "manifest_sha256", "schema_sha256",
              "ground_truth_sha256", "action_sha256", "transformation_ledger_sha256",
              "near_duplicate_review"}
    _exact_fields(raw, fields, "freeze")
    assert isinstance(raw, Mapping)
    if raw["corpus_version"] != VERSION or not isinstance(raw["frozen_at_utc"], str) or _UTC.fullmatch(raw["frozen_at_utc"]) is None:
        raise DesktopAcceptanceManifestError("freeze version/timestamp is invalid.")
    for field in fields:
        if field.endswith("_sha256"):
            _sha256(raw[field], f"freeze.{field}")
    review = raw["near_duplicate_review"]
    _exact_fields(review, {"reviewer_id", "reviewed_at_utc", "method", "evidence_reference", "result"}, "freeze.near_duplicate_review")
    assert isinstance(review, Mapping)
    _identifier(review["reviewer_id"], "freeze.near_duplicate_review.reviewer_id")
    if not isinstance(review["reviewed_at_utc"], str) or _UTC.fullmatch(review["reviewed_at_utc"]) is None:
        raise DesktopAcceptanceManifestError("near-duplicate review timestamp is invalid.")
    _text(review["method"], "freeze.near_duplicate_review.method")
    _safe_reference(review["evidence_reference"], "freeze.near_duplicate_review.evidence_reference")
    if review["result"] != "no_unresolved_matches":
        raise DesktopAcceptanceManifestError("near-duplicate review has unresolved matches.")
    return dict(raw)


def _policy(root: Path, raw: object) -> Mapping[str, str]:
    _exact_fields(raw, {"policy_id", "version", "path", "sha256"}, "canonicalization_policy")
    assert isinstance(raw, Mapping)
    if raw["policy_id"] != POLICY_ID or raw["version"] != POLICY_VERSION:
        raise DesktopAcceptanceManifestError("canonicalization policy is unsupported.")
    relative = _safe_path(raw["path"], "canonicalization_policy.path")
    digest = _sha256(raw["sha256"], "canonicalization_policy.sha256")
    policy_path = (root / Path(*PurePosixPath(relative).parts)).resolve()
    try:
        policy_path.relative_to(root)
        actual = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    except (ValueError, OSError) as error:
        raise DesktopAcceptanceManifestError(
            f"cannot safely read canonicalization policy: {error}"
        ) from error
    if actual != digest:
        raise DesktopAcceptanceManifestError("canonicalization policy SHA-256 does not match.")
    return {"policy_id": POLICY_ID, "version": POLICY_VERSION, "path": relative, "sha256": digest}


def _identity(raw: object, name: str) -> Mapping[str, str]:
    return _string_object(raw, {"country", "denomination", "year"}, f"{name}.expected_identity")


def _attribution(raw: object, name: str) -> Mapping[str, None]:
    _exact_fields(raw, set(RESERVED_ATTRIBUTION_FIELDS), f"{name}.reserved_attribution")
    assert isinstance(raw, Mapping)
    if any(raw[field] is not None for field in RESERVED_ATTRIBUTION_FIELDS):
        raise DesktopAcceptanceManifestError(f"{name}.reserved_attribution fields must remain null.")
    return {field: None for field in RESERVED_ATTRIBUTION_FIELDS}


def _capture(raw: object, name: str) -> Mapping[str, str]:
    return dict(sorted(_string_object(raw, set(CAPTURE_FIELDS), f"{name}.capture_conditions").items()))


def _optional_capture_fields(raw: object, name: str) -> tuple[str, ...] | None:
    if raw is None:
        return None
    values = _identifiers(raw, name)
    if not values or any(value not in CAPTURE_FIELDS for value in values):
        raise DesktopAcceptanceManifestError(f"{name} contains unsupported capture fields.")
    return values


def _prior_use(raw: object, name: str) -> Mapping[str, object]:
    _exact_fields(raw, {"used", "details"}, f"{name}.prior_benchmark_use")
    assert isinstance(raw, Mapping)
    if not isinstance(raw["used"], bool):
        raise DesktopAcceptanceManifestError(f"{name}.prior_benchmark_use.used must be boolean.")
    details = _optional_text(raw["details"], f"{name}.prior_benchmark_use.details")
    if raw["used"] != (details is not None):
        raise DesktopAcceptanceManifestError(f"{name}.prior_benchmark_use details are inconsistent.")
    return {"used": raw["used"], "details": details}


def _transformation(raw: object, name: str) -> Mapping[str, object]:
    _exact_fields(raw, {"operation", "source_sha256", "parameters", "rationale"}, name)
    assert isinstance(raw, Mapping)
    operation = raw["operation"]
    if operation not in PERMITTED_TRANSFORMATIONS:
        raise DesktopAcceptanceManifestError(f"{name}.operation is forbidden.")
    if not isinstance(raw["parameters"], Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in raw["parameters"].items()):
        raise DesktopAcceptanceManifestError(f"{name}.parameters must be text pairs.")
    if operation == "none":
        if raw["source_sha256"] is not None or raw["parameters"] or raw["rationale"] != "original capture bytes":
            raise DesktopAcceptanceManifestError(f"{name} none record is inconsistent.")
    else:
        _sha256(raw["source_sha256"], f"{name}.source_sha256")
        _text(raw["rationale"], f"{name}.rationale")
    return dict(raw)


def _eligibility(raw: object, name: str, privacy: str) -> Mapping[str, object]:
    fields = {"eligible", "privacy_approved", "license_approved", "authorization_reference"}
    _exact_fields(raw, fields, name)
    assert isinstance(raw, Mapping)
    if any(raw[field] is not True for field in ("eligible", "privacy_approved", "license_approved")):
        raise DesktopAcceptanceManifestError(f"{name} must fail closed unless fully approved.")
    if privacy == "uncertain_local_only":
        raise DesktopAcceptanceManifestError(f"{name} cannot authorize uncertain-local input.")
    _safe_reference(raw["authorization_reference"], f"{name}.authorization_reference")
    return dict(raw)


def _exact_fields(raw: object, fields: set[str], name: str) -> None:
    if not isinstance(raw, Mapping) or set(raw) != fields:
        raise DesktopAcceptanceManifestError(f"{name} fields do not match schema.")


def _string_object(raw: object, fields: set[str], name: str) -> dict[str, str]:
    _exact_fields(raw, fields, name)
    assert isinstance(raw, Mapping)
    return {field: _text(raw[field], f"{name}.{field}") for field in sorted(fields)}


def _identifiers(raw: object, name: str) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise DesktopAcceptanceManifestError(f"{name} must be an array.")
    values = tuple(_identifier(value, f"{name}[]") for value in raw)
    if values != tuple(sorted(set(values))):
        raise DesktopAcceptanceManifestError(f"{name} must be unique and sorted.")
    return values


def _safe_path(value: object, name: str) -> str:
    text = _text(value, name)
    if "\\" in text:
        raise DesktopAcceptanceManifestError(f"{name} must use POSIX separators.")
    path = PurePosixPath(text)
    if path.is_absolute() or ":" in path.parts[0] or any(part in {"", ".", ".."} for part in path.parts):
        raise DesktopAcceptanceManifestError(f"{name} is unsafe.")
    return path.as_posix()


def _safe_reference(value: object, name: str) -> str:
    text = _text(value, name)
    lowered = text.casefold()
    if "\\" in text or text.startswith("/") or re.match(r"^[A-Za-z]:", text) or lowered.startswith("file:"):
        raise DesktopAcceptanceManifestError(f"{name} must not contain a local path.")
    return text


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DesktopAcceptanceManifestError(f"{name} must be non-empty text.")
    return value.strip()


def _optional_text(value: object, name: str) -> str | None:
    return None if value is None else _text(value, name)


def _identifier(value: object, name: str) -> str:
    return _pattern(value, _IDENTIFIER, name)


def _pattern(value: object, pattern: re.Pattern[str], name: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise DesktopAcceptanceManifestError(f"{name} is not a safe identifier.")
    return value


def _optional_pattern(value: object, pattern: re.Pattern[str], name: str) -> str | None:
    return None if value is None else _pattern(value, pattern, name)


def _sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise DesktopAcceptanceManifestError(f"{name} must be lowercase SHA-256.")
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
