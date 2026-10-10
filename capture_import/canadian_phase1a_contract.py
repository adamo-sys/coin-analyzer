"""Supplemental Canadian Phase 1A contracts and offline recorded-outcome scoring.

No recognizer, provider, image reader, production canonicalization, approval,
HUMAN VERIFY, whole-identity ACCEPT, save, or collection mutation lives here.
Readiness validates declarations; it cannot authenticate external source/review
claims. Synthetic diagnostics never establish real metadata or holdout truth.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

_ROOT = Path(__file__).resolve().parents[1] / "benchmarks/canadian_common_coin_phase1a"
_FIELDS = ("country", "denomination", "year", "monarch", "reverse_design", "variety")
_EXECUTIONS = ("SUCCESS", "MALFORMED_OUTPUT", "RUNTIME_FAILURE", "UNATTEMPTED")
_EXACT_YEAR = re.compile(r"[0-9]{4}\Z")


@dataclass(frozen=True, order=True)
class Diagnostic:
    code: str
    path: str
    severity: str = "ERROR"


@dataclass(frozen=True)
class Readiness:
    valid: bool
    ready: bool
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True)
class FieldScore:
    field: str
    truth_count: int
    supported: int
    correct_supported: int
    false_supported: int
    correct_routes: int
    abstentions: int
    precision: float | None
    coverage: float | None
    routing_accuracy: float | None
    gate_pass: bool


@dataclass(frozen=True)
class ScoreReport:
    synthetic: bool
    evaluation_ready: bool
    evaluation_pass: bool
    fields: tuple[FieldScore, ...]
    execution_counts: tuple[tuple[str, int], ...]
    false_supported_years: int
    false_standard_designs: int
    conflict_evidence_loss: int
    outcomes_sha256: str | None
    diagnostics: tuple[Diagnostic, ...]
    recorded_outcomes: Any


def normalize_document(value: Any) -> Any:
    """NFC/whitespace normalization; unordered arrays retain every duplicate.

    This supplemental normalization has no CanadianIssue/canonical identity
    aliases and never repairs dates. Arrays in these contracts are sets of
    declarations, not sequences of execution instructions.
    """
    if isinstance(value, str):
        return " ".join(unicodedata.normalize("NFC", value).split())
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, list):
        return sorted((normalize_document(item) for item in value), key=_json)
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {key: normalize_document(value[key]) for key in sorted(value)}
    raise ValueError("Only finite JSON values with string keys are accepted.")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def canonical_digest(value: Any) -> str:
    """Immutable SHA-256 identity of the supplemental normalized JSON value."""
    return hashlib.sha256(_json(normalize_document(value)).encode("utf-8")).hexdigest()


def benchmark_digest(benchmark: dict[str, Any]) -> str:
    """Hash all manifest content except its self-referential manifest hash."""
    value = copy.deepcopy(benchmark)
    value["freeze"].pop("manifest_sha256", None)
    return canonical_digest(value)


def _schema(name: str) -> dict[str, Any]:
    # Fixed, bundled local files only; $schema/$id URIs are never fetched.
    return json.loads((_ROOT / name).read_text(encoding="utf-8"))


def _schema_errors(value: Any, spec: dict[str, Any], root: dict[str, Any], path: str) -> list[Diagnostic]:
    """Evaluate exactly the assertion subset used by the two bundled schemas.

    This is deliberately not a general-purpose JSON Schema implementation.
    Unknown assertion keywords and references fail closed.
    """
    allowed = {"$schema", "$id", "$defs", "title", "description", "$ref", "type", "const", "enum",
               "required", "properties", "additionalProperties", "items", "minItems", "maxItems",
               "minLength", "maxLength", "pattern", "minimum", "maximum"}
    if set(spec) - allowed:
        return [Diagnostic("UNKNOWN_SCHEMA_ASSERTION", path)]
    if "$ref" in spec:
        target = spec["$ref"]
        if target.startswith("metadata.schema.json#/$defs/"):
            root = _schema("metadata.schema.json")
            name = target.split("/")[-1]
        elif target.startswith("#/$defs/"):
            name = target.split("/")[-1]
        else:
            return [Diagnostic("UNKNOWN_SCHEMA_REFERENCE", path)]
        return _schema_errors(value, root["$defs"][name], root, path)
    errors: list[Diagnostic] = []
    if "const" in spec and (type(value) is not type(spec["const"]) or value != spec["const"]):
        errors.append(Diagnostic("UNKNOWN_VERSION_OR_POLICY", path))
    if "enum" in spec and value not in spec["enum"]:
        errors.append(Diagnostic("INVALID_ENUM", path))
    types = spec.get("type", [])
    types = [types] if isinstance(types, str) else types
    checks = {"object": isinstance(value, dict), "array": isinstance(value, list),
              "string": isinstance(value, str), "integer": type(value) is int,
              "number": type(value) is int or (type(value) is float and math.isfinite(value)),
              "boolean": type(value) is bool, "null": value is None}
    if types and not any(checks.get(t, False) for t in types):
        return errors + [Diagnostic("INVALID_TYPE", path)]
    if isinstance(value, dict):
        for name in spec.get("required", []):
            if name not in value:
                errors.append(Diagnostic("MISSING_REQUIRED", f"{path}.{name}"))
        props = spec.get("properties", {})
        for name, child in value.items():
            if name in props:
                errors.extend(_schema_errors(child, props[name], root, f"{path}.{name}"))
            elif spec.get("additionalProperties") is False:
                errors.append(Diagnostic("UNKNOWN_PROPERTY", f"{path}.{name}"))
    if isinstance(value, list):
        if not spec.get("minItems", 0) <= len(value) <= spec.get("maxItems", len(value)):
            errors.append(Diagnostic("INVALID_ARRAY_SIZE", path))
        for i, child in enumerate(value):
            errors.extend(_schema_errors(child, spec.get("items", {}), root, f"{path}[{i}]"))
    if isinstance(value, str):
        if not spec.get("minLength", 0) <= len(value) <= spec.get("maxLength", len(value)):
            errors.append(Diagnostic("INVALID_TEXT_SIZE", path))
        if "pattern" in spec and re.search(spec["pattern"], value) is None:
            errors.append(Diagnostic("INVALID_TEXT_FORMAT", path))
    if type(value) in (int, float):
        if value < spec.get("minimum", value) or value > spec.get("maximum", value):
            errors.append(Diagnostic("INVALID_NUMBER_RANGE", path))
    return errors


def _document(value: Any, schema_name: str) -> tuple[dict[str, Any] | None, list[Diagnostic]]:
    try:
        normalized = normalize_document(value)
    except (ValueError, TypeError, RecursionError):
        return None, [Diagnostic("MALFORMED_DOCUMENT", "$")]
    schema = _schema(schema_name)
    errors = _schema_errors(normalized, schema, schema, "$")
    return (None if errors else normalized), errors


def _review_errors(review: dict[str, Any], path: str) -> list[Diagnostic]:
    errors = []
    if review["state"] != "APPROVED":
        errors.append(Diagnostic("UNRESOLVED_REVIEW", path))
    if review["author"].casefold() == review["reviewer"].casefold():
        errors.append(Diagnostic("NOT_INDEPENDENT_REVIEW", path))
    try:
        datetime.strptime(review["reviewed_at"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        errors.append(Diagnostic("INVALID_REVIEW_DATE", path))
    return errors


def _source_errors(sources: list[dict[str, Any]], synthetic: bool) -> list[Diagnostic]:
    errors = _duplicate_errors(sources, "source_id", "$.sources")
    for source in sources:
        path = "$.sources." + source["source_id"]
        errors.extend(_review_errors(source["review"], path + ".review"))
        if source["permission"] != "LOCAL_METADATA":
            errors.append(Diagnostic("LICENSING_UNRESOLVED", path))
        try:
            datetime.strptime(source["retrieved_at"], "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            errors.append(Diagnostic("INVALID_RETRIEVAL_DATE", path))
        marker = source["kind"] == "SYNTHETIC" or any(
            "synthetic" in source[key].casefold() for key in ("locator", "title", "licence", "attribution"))
        if marker != synthetic or (synthetic and source["kind"] != "SYNTHETIC"):
            errors.append(Diagnostic("CLASSIFICATION_MISMATCH", path))
    return errors


def _duplicate_errors(rows: list[dict[str, Any]], key: str, path: str) -> list[Diagnostic]:
    ids = [row[key] for row in rows]
    return [Diagnostic("DUPLICATE_ID", path + "." + str(item)) for item in sorted(set(ids)) if ids.count(item) > 1]


def _ref_errors(refs: list[dict[str, Any]], sources: list[dict[str, Any]], fields: set[str], path: str) -> list[Diagnostic]:
    errors: list[Diagnostic] = []
    source_ids = {s["source_id"] for s in sources}
    if not fields <= {r["field"] for r in refs}:
        errors.append(Diagnostic("MISSING_FIELD_PROVENANCE", path))
    for reference in refs:
        if reference["source_id"] not in source_ids:
            errors.append(Diagnostic("UNKNOWN_SOURCE_REFERENCE", path + "." + reference["source_id"]))
    return errors


def _historical_support(row: dict[str, Any]) -> bool:
    lo, hi, denom, monarch = row["year_start"], row["year_end"], row["denomination"], row["monarch"]
    if lo > hi or (denom == "$1" and lo < 1987) or (denom == "$2" and lo < 1996):
        return False
    if monarch == "CHARLES_III":
        return denom != "1c" and lo >= 2023
    return lo >= 1953 and hi <= 2023 and (denom != "1c" or hi <= 2012)


def _readiness(errors: list[Diagnostic], synthetic: bool) -> Readiness:
    if synthetic:
        errors = errors + [Diagnostic("SYNTHETIC_NOT_REAL_EVIDENCE", "$", "INFO")]
    diagnostics = tuple(sorted(set(errors)))
    valid = not any(e.severity == "ERROR" for e in diagnostics)
    return Readiness(valid, valid and not synthetic, diagnostics)


def validate_metadata(metadata: Any) -> Readiness:
    """Validate strict supplemental issue/design/source and coverage declarations."""
    data, errors = _document(metadata, "metadata.schema.json")
    if data is None:
        return _readiness(errors, False)
    synthetic = data["classification"] == "SYNTHETIC"
    errors.extend(_source_errors(data["sources"], synthetic))
    errors.extend(_duplicate_errors(data["issues"], "issue_id", "$.issues"))
    issue_map = {row["issue_id"]: row for row in data["issues"]}
    required = {"denomination", "monarch", "years", "obverse_design", "reverse_design", "disposition"}
    for row in data["issues"]:
        path = "$.issues." + row["issue_id"]
        errors.extend(_review_errors(row["review"], path))
        errors.extend(_ref_errors(row["source_refs"], data["sources"], required, path))
        if not _historical_support(row) and not row["unsupported"]:
            errors.append(Diagnostic("UNSUPPORTED_COMBINATION", path))
        if row["year_start"] > row["year_end"]:
            errors.append(Diagnostic("INVALID_DATE_RANGE", path))
        if row["disposition"] == "UNRESOLVED" and not row["unsupported"]:
            errors.append(Diagnostic("UNRESOLVED_DESIGN", path))
    covered: set[str] = set()
    for i, declaration in enumerate(data["coverage"]):
        path = f"$.coverage[{i}]"
        refs = declaration["issue_ids"]
        if len(set(refs)) != len(refs) or any(key not in issue_map for key in refs):
            errors.append(Diagnostic("INVALID_COVERAGE_REFERENCE", path))
            continue
        if declaration["year_start"] > declaration["year_end"]:
            errors.append(Diagnostic("INVALID_DATE_RANGE", path))
        if declaration["state"] != "COVERED":
            if refs:
                errors.append(Diagnostic("COVERAGE_MISMATCH", path))
            continue
        eligible = [issue_map[key] for key in refs]
        if not eligible or any(row["unsupported"] or any(row[key] != declaration[key] for key in
                ("denomination", "monarch", "disposition")) for row in eligible):
            errors.append(Diagnostic("COVERAGE_MISMATCH", path))
            continue
        # Interval union, never exact-year evidence or materialized inferred years.
        end = declaration["year_start"] - 1
        for row in sorted(eligible, key=lambda r: (r["year_start"], r["year_end"])):
            if row["year_start"] > end + 1:
                break
            end = max(end, row["year_end"])
        if end < declaration["year_end"]:
            errors.append(Diagnostic("COVERAGE_MISMATCH", path))
        else:
            covered.update(refs)
    for row in data["issues"]:
        if not row["unsupported"] and row["issue_id"] not in covered:
            errors.append(Diagnostic("UNDECLARED_COVERAGE", "$.issues." + row["issue_id"]))
    return _readiness(errors, synthetic)


def _safe_relative(reference: str) -> bool:
    parts = PurePosixPath(reference).parts
    return bool(parts) and not reference.startswith("/") and not any(
        token in reference for token in ("\\", ":", "%", "\x00")) and all(p not in (".", "..") for p in reference.split("/"))


def _truth_eligible(field: dict[str, Any], sources: list[dict[str, Any]]) -> bool:
    truth = field["truth"]
    if truth["state"] != "VERIFIED" or _review_errors(truth["review"], "truth"):
        return False
    if _ref_errors(truth["source_refs"], sources, {field["field"]}, "truth"):
        return False
    used = {ref["source_id"] for ref in truth["source_refs"]}
    return all(not _source_errors([s], s["kind"] == "SYNTHETIC") for s in sources if s["source_id"] in used)


def validate_benchmark(metadata: Any, benchmark: Any) -> Readiness:
    """Check truth review, split integrity, policy declarations and freeze hashes."""
    meta_report = validate_metadata(metadata)
    data, errors = _document(benchmark, "benchmark.schema.json")
    errors.extend(meta_report.diagnostics)
    if data is None:
        return _readiness(errors, False)
    synthetic = data["classification"] == "SYNTHETIC"
    errors.extend(_source_errors(data["sources"], synthetic))
    errors.extend(_review_errors(data["policy"]["review"], "$.policy.review"))
    errors.extend(_duplicate_errors(data["policy"]["thresholds"], "field", "$.policy.thresholds"))
    errors.extend(_duplicate_errors(data["cases"], "case_id", "$.cases"))
    meta, _ = _document(metadata, "metadata.schema.json")
    if meta is not None:
        if (meta["classification"] == "SYNTHETIC") != synthetic:
            errors.append(Diagnostic("CLASSIFICATION_MISMATCH", "$.classification"))
        if canonical_digest(meta) != data["freeze"]["metadata_sha256"]:
            errors.append(Diagnostic("FREEZE_MISMATCH", "$.freeze.metadata_sha256"))
    if canonical_digest(data["policy"]) != data["freeze"]["policy_sha256"] or benchmark_digest(data) != data["freeze"]["manifest_sha256"]:
        errors.append(Diagnostic("FREEZE_MISMATCH", "$.freeze"))
    issue_ids = set() if meta is None else {row["issue_id"] for row in meta["issues"]}
    split_keys: dict[tuple[str, str], str] = {}
    thresholds = {p["field"] for p in data["policy"]["thresholds"]}
    holdout_fields: set[str] = set()
    for case in data["cases"]:
        path = "$.cases." + case["case_id"]
        if not _safe_relative(case["input_ref"]):
            errors.append(Diagnostic("UNSAFE_INPUT_REFERENCE", path))
        if (case["privacy"] == "SYNTHETIC") != synthetic:
            errors.append(Diagnostic("CLASSIFICATION_MISMATCH", path))
        for key in ("coin_group_id", "capture_group_id", "input_ref", "input_sha256"):
            identity = (key, case[key])
            if identity in split_keys and split_keys[identity] != case["split"]:
                errors.append(Diagnostic("SPLIT_LEAKAGE", path + "." + key))
            split_keys[identity] = case["split"]
        if len(set(case["issue_ids"])) != len(case["issue_ids"]) or not set(case["issue_ids"]) <= issue_ids:
            errors.append(Diagnostic("UNKNOWN_ISSUE_REFERENCE", path))
        errors.extend(_duplicate_errors(case["fields"], "field", path + ".fields"))
        for field in case["fields"]:
            fp = path + "." + field["field"]
            if case["split"] == "HOLDOUT":
                holdout_fields.add(field["field"])
            if not _truth_eligible(field, data["sources"]):
                errors.append(Diagnostic("UNSCORABLE_TRUTH", fp))
            selected = field["expected_state"] == "SUPPORTED"
            if selected != (field["truth"]["value"] is not None):
                errors.append(Diagnostic("INVALID_EXPECTED_VALUE", fp))
            errors.extend(_duplicate_errors(field["required_evidence"], "evidence_id", fp))
            if field["field"] == "variety" and field["expected_state"] != "ABSTAIN":
                errors.append(Diagnostic("VARIETY_DISABLED", fp))
            if selected and meta is not None:
                proposed = {"field": field["field"], "state": "SUPPORTED", "value": field["truth"]["value"],
                            "candidate_ids": case["issue_ids"], "evidence": field["required_evidence"]}
                if _support_errors(proposed, case, meta):
                    errors.append(Diagnostic("UNSAFE_EXPECTED_SUPPORT", fp))
            if field["expected_state"] == "CONFLICTING" and len(field["required_evidence"]) < 2:
                errors.append(Diagnostic("MISSING_CONFLICT_EVIDENCE", fp))
    if not thresholds <= holdout_fields:
        errors.append(Diagnostic("MISSING_HOLDOUT_FIELDS", "$.cases"))
    return _readiness(errors, synthetic)


def _year_compatible(value: str, evidence: str) -> bool:
    if _EXACT_YEAR.fullmatch(evidence):
        return value == evidence
    match = re.fullmatch(r"([0-9]{4})-([0-9]{4})", evidence)
    return bool(match and int(match[1]) <= int(value) <= int(match[2]))


def _support_errors(field: dict[str, Any], case: dict[str, Any], meta: dict[str, Any]) -> list[str]:
    if field["state"] != "SUPPORTED":
        return []
    name, value, evidence = field["field"], field["value"], field["evidence"]
    direct = [e for e in evidence if e["origin"] == "DIRECT"]
    sided_direct = [e for e in direct if e["side"] != "NONE"]
    ids = field["candidate_ids"]
    issue_map = {row["issue_id"]: row for row in meta["issues"]}
    rows = [issue_map[key] for key in ids if key in issue_map]
    errors: list[str] = []
    if not value or not evidence:
        return ["MISSING_SUPPORT_EVIDENCE"]
    if len(set(ids)) != len(ids) or len(rows) != len(ids) or not set(ids) <= set(case["issue_ids"]):
        errors.append("UNRESOLVED_CANDIDATES")
    if any(row["unsupported"] or row["disposition"] == "UNRESOLVED" for row in rows):
        errors.append("UNSUPPORTED_ISSUE")
    if name == "year":
        if not _EXACT_YEAR.fullmatch(value) or not sided_direct or any(e["value"] != value for e in direct):
            errors.append("UNSAFE_YEAR_SUPPORT")
        elif any(not _year_compatible(value, e["value"]) for e in evidence if e["origin"] == "CANDIDATE_METADATA") or any(
                not row["year_start"] <= int(value) <= row["year_end"] for row in rows):
            errors.append("CONFLICTING_YEAR_METADATA")
    elif name in ("monarch", "reverse_design"):
        side = "OBVERSE" if name == "monarch" else "REVERSE"
        expected = (lambda r: r["monarch"]) if name == "monarch" else (lambda r: r["reverse_design"])
        if len(rows) != 1 or not any(e["side"] == side and e["value"] == value for e in sided_direct):
            errors.append("UNRESOLVED_OR_WRONG_SIDE_DESIGN")
        if any(expected(row) != value for row in rows) or any(e["value"] != value for e in evidence):
            errors.append("CONFLICTING_DESIGN_EVIDENCE")
        if name == "reverse_design" and (case["design_disposition"] == "UNRESOLVED" or any(
                r["disposition"] != case["design_disposition"] for r in rows)):
            errors.append("UNRESOLVED_DESIGN_DISPOSITION")
    elif name == "variety":
        errors.append("VARIETY_DISABLED")
    else:
        if not sided_direct or any(e["value"] != value for e in evidence):
            errors.append("UNSUPPORTED_DIRECT_FIELD")
        if name == "denomination" and any(row["denomination"] != value for row in rows):
            errors.append("CONFLICTING_FIELD_METADATA")
        if name == "country" and rows and value != "Canada":
            errors.append("CONFLICTING_FIELD_METADATA")
    return errors


def _record_errors(row: dict[str, Any], case: dict[str, Any]) -> list[Diagnostic]:
    schema = _schema("benchmark.schema.json")
    errors = _schema_errors(row, schema["$defs"]["recorded_case"], schema, "$.outcomes." + case["case_id"])
    if errors:
        return errors
    expected = {f["field"] for f in case["fields"]}
    if row["execution"] != "SUCCESS":
        if row["fields"]:
            errors.append(Diagnostic("FIELDS_ON_NON_SUCCESS", case["case_id"]))
        return errors
    if {f["field"] for f in row["fields"]} != expected:
        errors.append(Diagnostic("MISSING_OR_EXTRA_RECORDED_FIELD", case["case_id"]))
    errors.extend(_duplicate_errors(row["fields"], "field", case["case_id"]))
    for field in row["fields"]:
        if (field["state"] == "SUPPORTED") != (field["value"] is not None):
            errors.append(Diagnostic("INVALID_RECORDED_VALUE", case["case_id"] + "." + field["field"]))
        errors.extend(_duplicate_errors(field["evidence"], "evidence_id", case["case_id"] + "." + field["field"]))
    return errors


def score_recorded_outcomes(metadata: Any, benchmark: Any, outcomes: Any) -> ScoreReport:
    """Score recorded fields only; no proposal generation, captures or providers.

    Thresholds are owner declarations. Safety counters cover every holdout field,
    including unscorable truth; precision/coverage use eligible field truth only.
    Non-success execution is never silently converted to an abstention.
    """
    readiness = validate_benchmark(metadata, benchmark)
    meta, meta_errors = _document(metadata, "metadata.schema.json")
    bench, bench_errors = _document(benchmark, "benchmark.schema.json")
    diagnostics = list(readiness.diagnostics)
    recorded = copy.deepcopy(outcomes)
    try:
        normalized = normalize_document(outcomes)
        digest = canonical_digest(normalized)
        recorded = copy.deepcopy(normalized)
    except (ValueError, TypeError, RecursionError):
        normalized, digest = None, None
    counts = {execution: 0 for execution in _EXECUTIONS}
    if meta is None or bench is None:
        diagnostics.extend(meta_errors + bench_errors)
        return ScoreReport(True, False, False, (), tuple(counts.items()), 0, 0, 0, digest,
                           tuple(sorted(set(diagnostics))), recorded)
    synthetic = bench["classification"] == "SYNTHETIC"
    schema = _schema("benchmark.schema.json")
    envelope = copy.deepcopy(normalized)
    if isinstance(envelope, dict):
        envelope["cases"] = []
    root_errors = _schema_errors(envelope, schema["$defs"]["outcomes"], schema, "$.outcomes")
    if not isinstance(normalized, dict) or not isinstance(normalized.get("cases"), list):
        root_errors.append(Diagnostic("MALFORMED_OUTPUT_ENVELOPE", "$.outcomes"))
    elif normalized.get("producer_ref") != bench["freeze"]["producer_ref"] or normalized.get("manifest_sha256") != bench["freeze"]["manifest_sha256"]:
        root_errors.append(Diagnostic("OUTCOMES_FREEZE_MISMATCH", "$.outcomes"))
    diagnostics.extend(root_errors)
    outcome_map: dict[str, dict[str, Any]] = {}
    if isinstance(normalized, dict) and isinstance(normalized.get("cases"), list):
        known = {case["case_id"] for case in bench["cases"]}
        for row in normalized["cases"]:
            if not isinstance(row, dict) or not isinstance(row.get("case_id"), str):
                root_errors.append(Diagnostic("MALFORMED_OUTPUT_CASE", "$.outcomes"))
                continue
            key = row["case_id"]
            if key in outcome_map or key not in known:
                root_errors.append(Diagnostic("DUPLICATE_OR_UNKNOWN_OUTPUT_CASE", key))
            outcome_map[key] = row
    stats = {name: dict(truth=0, supported=0, correct=0, false=0, routes=0, abstentions=0) for name in _FIELDS}
    false_years = false_standard = conflict_loss = 0
    for case in bench["cases"]:
        if case["split"] != "HOLDOUT":
            continue
        row = outcome_map.get(case["case_id"])
        execution = "UNATTEMPTED" if row is None else row.get("execution", "MALFORMED_OUTPUT")
        row_errors = [] if row is None else _record_errors(row, case)
        if root_errors or row_errors:
            execution = "MALFORMED_OUTPUT"
        diagnostics.extend(row_errors)
        counts[execution] += 1
        actual = {} if execution != "SUCCESS" else {f["field"]: f for f in row["fields"]}  # type: ignore[index]
        for expected in case["fields"]:
            name = expected["field"]
            stat = stats[name]
            eligible = _truth_eligible(expected, bench["sources"])
            stat["truth"] += int(eligible)
            field = actual.get(name)
            loss = 0
            # A state label never permits contradictory required records to
            # disappear. Successful outputs must retain all required evidence;
            # failed/unattempted outputs still expose loss of conflict records.
            if field is not None or expected["expected_state"] in {"CONFLICTING", "AMBIGUOUS"}:
                retained = [] if field is None else field["evidence"]
                loss = sum(e not in retained for e in expected["required_evidence"])
                conflict_loss += loss
                if loss:
                    diagnostics.append(Diagnostic("CONFLICT_EVIDENCE_LOSS", case["case_id"] + "." + name))
            if field is None:
                continue
            unsafe = _support_errors(field, case, meta)
            for code in unsafe:
                diagnostics.append(Diagnostic(code, case["case_id"] + "." + name))
            supported = field["state"] == "SUPPORTED"
            correct = eligible and supported and expected["expected_state"] == "SUPPORTED" and field["value"] == expected["truth"]["value"] and not unsafe and not loss
            if supported and not eligible:
                diagnostics.append(Diagnostic("UNSCORABLE_SUPPORTED", case["case_id"] + "." + name))
            if supported and (unsafe or (eligible and not correct)):
                false_years += int(name == "year")
                false_standard += int(name == "reverse_design" and case["design_disposition"] == "ALTERNATE")
            if eligible:
                stat["supported"] += int(supported)
                stat["correct"] += int(correct)
                stat["false"] += int(supported and not correct)
                stat["abstentions"] += int(field["state"] == "ABSTAIN")
                stat["routes"] += int(field["state"] == expected["expected_state"] and not loss and
                                      (correct if supported else True))
    scores = []
    policy = {p["field"]: p for p in bench["policy"]["thresholds"]}
    for name in _FIELDS:
        s = stats[name]
        if name not in policy and not s["truth"] and not s["supported"]:
            continue
        precision = s["correct"] / s["supported"] if s["supported"] else None
        coverage = s["correct"] / s["truth"] if s["truth"] else None
        routing = s["routes"] / s["truth"] if s["truth"] else None
        threshold = policy.get(name)
        gate = bool(threshold and precision is not None and coverage is not None and
                    s["truth"] >= threshold["min_truth"] and s["supported"] >= threshold["min_supported"] and
                    precision >= threshold["min_precision"] and coverage >= threshold["min_coverage"] and
                    not s["false"] and s["routes"] == s["truth"])
        scores.append(FieldScore(name, s["truth"], s["supported"], s["correct"], s["false"], s["routes"],
                                 s["abstentions"], precision, coverage, routing, gate))
    diagnostics.extend(root_errors)
    ready = readiness.ready and not root_errors
    passed = ready and all(score.gate_pass for score in scores if score.field in policy) and bool(scores) and not (
        false_years or false_standard or conflict_loss or any(e.severity == "ERROR" for e in diagnostics))
    return ScoreReport(synthetic, ready, passed, tuple(scores), tuple(counts.items()), false_years,
                       false_standard, conflict_loss, digest, tuple(sorted(set(diagnostics))), recorded)
