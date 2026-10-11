"""Fail-closed final acceptance over retained Bake-Off evidence; never regrades a run.

Authority comes from an operator-controlled external workflow. Structural validity,
identifiers, locations and digests do not authenticate anyone or establish custody.
Inputs are UTF-8 JSON bytes; byte digests include whitespace and final newlines.
"""
from __future__ import annotations

import argparse
import json
import re
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

_AUTHORITY_NOTICE = (
    "Operator authority is established outside this tool. A structurally valid "
    "attestation is not proof of operator identity, cryptographic authenticity, "
    "reviewer authenticity, or historical custody. Contestant-controlled evidence "
    "must never supply the operator attestation."
)
_RUN_FIELDS = ("task_id", "run_id", "starting_sha", "corpus_manifest_sha256")
_CONFIRMATIONS = {
    "reviewer_independently_authorized", "reviewer_not_contestant",
    "operator_approved_review", "operator_accepts_authority_responsibility",
}


class AcceptanceEvidenceError(ValueError):
    """Malformed, incomplete, contradictory or mismatched supplied evidence."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise AcceptanceEvidenceError(reason)


def _object(value: Any, label: str) -> dict[str, Any]:
    _require(isinstance(value, dict), f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{label} must be a nonempty string")
    return value


def _hash(value: Any, length: int, label: str) -> str:
    _require(isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value) is not None,
             f"{label} must be a lowercase {length}-digit digest")
    return value


def _fields(value: dict[str, Any], expected: set[str], label: str) -> None:
    _require(set(value) == expected, f"{label} has missing or unexpected fields")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise AcceptanceEvidenceError(f"nonfinite JSON number: {value}")


def _parse(raw: bytes | None, label: str) -> dict[str, Any]:
    _require(isinstance(raw, bytes), f"{label} is missing or is not JSON bytes")
    return _object(json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_nonfinite), label)


def _canonical_digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                             allow_nan=False).encode("utf-8")).hexdigest()


def _paths(value: Any, label: str) -> list[str]:
    _require(isinstance(value, list), f"{label} must be a list")
    for path in value:
        _text(path, label)
        parts = PurePosixPath(path)
        _require(bool(parts.parts) and not parts.is_absolute() and ".." not in parts.parts and "\\" not in path
                 and ":" not in path and path == parts.as_posix(), f"{label} contains an unsafe path")
    _require(len(value) == len(set(value)), f"{label} contains duplicate paths")
    return value


def _name_status_paths(lines: list[str]) -> list[str]:
    """Match Git --name-only semantics: rename/copy destinations, all other paths."""
    changed: list[str] = []
    for line in lines:
        parts = line.split("\t")
        status = parts[0]
        if re.fullmatch(r"[RC][0-9]{1,3}", status):
            _require(len(parts) == 3 and int(status[1:]) <= 100, "invalid rename/copy name_status")
        else:
            _require(status in ("A", "D", "M", "T", "U", "X", "B") and len(parts) == 2,
                     "invalid candidate name_status")
        _paths(parts[1:], "name_status paths")
        changed.append(parts[-1])
    _require(len(changed) == len(set(changed)), "duplicate name_status changed path")
    return changed

def _identity(result: dict[str, Any], evidence: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    run = {key: evidence.get(key) for key in _RUN_FIELDS}
    for key in _RUN_FIELDS:
        _text(run[key], f"run {key}")
    _hash(run["starting_sha"], 40, "starting_sha")
    _hash(run["corpus_manifest_sha256"], 64, "corpus_manifest_sha256")
    for key in ("task_id", "run_id", "corpus_manifest_sha256"):
        _require(result.get(key) == run[key], f"result/evidence {key} mismatch")
    candidate = _object(evidence.get("candidate"), "candidate")
    _require(isinstance(candidate.get("name_status"), list)
             and all(isinstance(line, str) and "\t" in line for line in candidate["name_status"]),
             "malformed candidate name_status")
    _require(isinstance(candidate.get("git_status"), list)
             and all(isinstance(line, str) for line in candidate["git_status"]), "malformed candidate git_status")
    if "candidate_state_sha256" in candidate:
        value = _hash(candidate["candidate_state_sha256"], 64, "candidate_state_sha256")
        _require(result.get("execution_protocol_version") == "1.1"
                 and result.get("candidate_state_sha256") == value and "ending_sha" not in candidate,
                 "result/evidence protocol v1.1 candidate mismatch")
        _require(candidate.get("diff_fingerprint") == value, "candidate state/diff identity mismatch")
        identity = {"kind": "candidate_state_sha256", "value": value}
    else:
        _require("execution_protocol_version" not in result and "candidate_state_sha256" not in result,
                 "contradictory candidate protocol")
        _require(candidate["git_status"] == [], "Protocol v1.0 candidate must be clean")
        _hash(candidate.get("tree_sha"), 40, "candidate tree_sha")
        _hash(candidate.get("diff_fingerprint"), 40, "candidate diff_fingerprint")
        identity = {"kind": "ending_sha", "value": _hash(candidate.get("ending_sha"), 40, "ending_sha")}
    return run, identity


def _review_authority(review: dict[str, Any], attestation: dict[str, Any], bindings: dict[str, Any],
                      review_bytes: bytes) -> list[dict[str, Any]]:
    _fields(review, {"schema_version", "reviewer_id", "bindings", "findings"}, "review")
    _fields(attestation, {"schema_version", "operator_id", "workflow_reference", "bindings", "review_sha256"}
            | _CONFIRMATIONS, "operator attestation")
    _require(review["schema_version"] == attestation["schema_version"] == "1", "unsupported review/attestation version")
    _text(review["reviewer_id"], "reviewer_id")
    _text(attestation["operator_id"], "operator_id")
    _text(attestation["workflow_reference"], "workflow_reference")
    _require(review["bindings"] == bindings, "review binding mismatch")
    _require(attestation["bindings"] == bindings, "operator attestation binding mismatch")
    _require(attestation["review_sha256"] == sha256(review_bytes).hexdigest(), "operator attestation review digest mismatch")
    for key in sorted(_CONFIRMATIONS):
        _require(attestation[key] is True, f"operator attestation does not explicitly confirm {key}")
    findings = review["findings"]
    _require(isinstance(findings, list), "review findings must be a list")
    ids: set[str] = set()
    technical_ids: set[str] = set()
    for finding in findings:
        finding = _object(finding, "review finding")
        _fields(finding, {"finding_id", "severity", "evidence_reference", "violated_rule", "smallest_correction",
                          "disposition", "technical_finding_sha256"}, "review finding")
        for key in ("finding_id", "evidence_reference", "violated_rule", "smallest_correction"):
            _text(finding[key], key)
        _require(finding["finding_id"] not in ids, "duplicate review finding identifier")
        ids.add(finding["finding_id"])
        disposition = finding["disposition"]
        _require(disposition in ("nonblocking", "blocking", "ambiguous", "prohibited_shortcut"), "unknown finding disposition")
        severity = finding["severity"]
        _require((disposition == "nonblocking" and severity in ("info", "note"))
                 or (disposition != "nonblocking" and severity == "blocking"), "contradictory severity/disposition")
        technical_id = finding["technical_finding_sha256"]
        if technical_id is not None:
            _hash(technical_id, 64, "technical_finding_sha256")
            _require(technical_id not in technical_ids, "duplicate technical finding disposition")
            technical_ids.add(technical_id)
    return findings


def _check_set(checks: Any, expected: list[str], identity: dict[str, str], *, oracle: bool,
               packet: dict[str, Any]) -> list[str]:
    _require(isinstance(checks, list) and bool(checks), "required check evidence is missing")
    _require([_object(item, "check").get("check_id") for item in checks] == expected,
             "incomplete, duplicate or reordered required check set")
    failed: list[str] = []
    identity_key = "candidate_state_sha256" if identity["kind"] == "candidate_state_sha256" else "candidate_ending_sha"
    other_identity = "candidate_ending_sha" if identity_key == "candidate_state_sha256" else "candidate_state_sha256"
    for order, check in enumerate(checks):
        check_fields = {"check_id", "execution_order", identity_key, "status", "exit_code", "output_sha256", "provenance", "error"}
        if oracle:
            check_fields |= {"test_path", "source", "source_blob_sha", "source_content_sha256", "candidate_module_provenance",
                             "expected_implementation_paths", "observed_implementation_paths", "outside_implementation_paths",
                             "provenance_validation", "candidate_import_root"}
        else:
            check_fields.add("command")
        _fields(check, check_fields, "check")
        _require(check.get(identity_key) == identity["value"] and other_identity not in check, "check candidate identity mismatch")
        _require(type(check.get("execution_order")) is int and check["execution_order"] == order, "invalid check execution order")
        status = check.get("status")
        _require(status in ("passed", "failed", "timed_out", "unavailable"), "invalid check status")
        _require(check.get("exit_code") is None or type(check.get("exit_code")) is int, "invalid check exit code")
        _require(status != "passed" or check.get("exit_code") == 0, "contradictory passed check exit code")
        _require(status != "failed" or check.get("exit_code") != 0, "contradictory failed check exit code")
        _require(status != "passed" or check.get("error") is None, "passed check has an error")
        if status == "passed":
            _hash(check.get("output_sha256"), 64, "check output_sha256")
        if not oracle:
            _require(check.get("command") == check["check_id"] and check.get("provenance") == "trusted_local_execution",
                     "unverified required-check provenance")
        else:
            path = expected[order].removeprefix("reference-acceptance:")
            _require(check.get("test_path") == path and check.get("source") == f"{packet['reference_end_sha']}:{path}",
                     "immutable acceptance source mismatch")
            _require(check.get("provenance") == "frozen_reference_test_blob_against_candidate", "unverified immutable acceptance provenance")
            implementation = _paths(packet["expected_implementation_paths"].get(path), "expected implementation paths")
            _require(bool(implementation) and check.get("expected_implementation_paths") == implementation,
                     "immutable acceptance expected implementation mismatch")
            if status == "passed":
                _hash(check.get("source_blob_sha"), 40, "source_blob_sha")
                _hash(check.get("source_content_sha256"), 64, "source_content_sha256")
                _require(check.get("provenance_validation") == "passed" and check.get("outside_implementation_paths") == [],
                         "immutable acceptance implementation provenance unavailable")
                observed = _paths(check.get("observed_implementation_paths"), "observed implementation paths")
                _require(set(observed) == set(implementation), "immutable acceptance implementation missing")
                modules = check.get("candidate_module_provenance")
                _require(isinstance(modules, list), "immutable acceptance module provenance missing")
                for module in modules:
                    _require(isinstance(module, list) and len(module) == 3 and isinstance(module[0], str)
                             and isinstance(module[1], str) and type(module[2]) is bool, "malformed module provenance")
                inside = {module[1] for module in modules if module[2] is True}
                derived_observed = sorted(inside & set(implementation))
                expected_names = {PurePosixPath(path).name for path in implementation}
                derived_outside = sorted({module[1] for module in modules if module[2] is False
                                          and PurePosixPath(module[1].replace("\\", "/")).name in expected_names})
                _require(observed == derived_observed and check["outside_implementation_paths"] == derived_outside
                         and not derived_outside, "contradictory immutable implementation provenance")
                _require(set(implementation) <= inside, "immutable acceptance module provenance incomplete")
        if status != "passed":
            failed.append(check["check_id"])
    return failed


def _technical(result: dict[str, Any], evidence: dict[str, Any], packet: dict[str, Any],
               identity: dict[str, str], findings: list[dict[str, Any]]) -> list[str]:
    result_fields = {"schema_version", "grader_id", "grader_implementation", "checked_at_utc", "task_id", "run_id",
                     "corpus_manifest_sha256", "status", "task_success", "required_validation", "scope", "anti_gaming",
                     "invalid_reasons", "evidence"}
    if identity["kind"] == "candidate_state_sha256":
        result_fields |= {"candidate_state_sha256", "execution_protocol_version"}
    _fields(result, result_fields, "grading result")
    _fields(evidence, {"schema_version", "grader_id", "grader_implementation", "corpus_manifest_sha256", "task_id", "run_id",
                       "starting_sha", "candidate", "required_checks", "independent_acceptance", "unverified_claim_mismatches",
                       "evidence_sha256"}, "grading evidence")
    for key, expected in (("schema_version", "1"), ("grader_id", "bakeoff-v1-deterministic-grader"),
                          ("grader_implementation", "evidence-bound-v2")):
        _require(result.get(key) == evidence.get(key) == expected, f"unsupported technical {key}")
    _text(result["checked_at_utc"], "checked_at_utc")
    _require(packet.get("task_id") == evidence["task_id"] and packet.get("starting_sha") == evidence["starting_sha"],
             "Task Packet run identity mismatch")
    _hash(packet.get("reference_end_sha"), 40, "reference_end_sha")
    required = packet.get("required_validation")
    _require(isinstance(required, list) and bool(required) and all(isinstance(item, str) and item.strip() for item in required),
             "Task Packet required validation missing")
    _require(len(required) == len(set(required)), "duplicate frozen required validation")
    reference_paths = _paths(packet.get("reference_changed_paths"), "reference changed paths")
    acceptance_ids = [f"reference-acceptance:{path}" for path in reference_paths if path.startswith(("tests/", "test_"))]
    _require(bool(acceptance_ids), "frozen immutable acceptance set unavailable")
    _object(packet.get("expected_implementation_paths"), "expected_implementation_paths")
    unsigned = {key: value for key, value in evidence.items() if key != "evidence_sha256"}
    _require(evidence["evidence_sha256"] == _canonical_digest(unsigned), "grading evidence identity checksum mismatch")
    summary = _object(result["evidence"], "result evidence")
    _fields(summary, {"evidence_sha256", "claims"}, "result evidence")
    _object(evidence["unverified_claim_mismatches"], "unverified claims")
    _require(summary == {"evidence_sha256": evidence["evidence_sha256"], "claims": evidence["unverified_claim_mismatches"]},
             "grading result evidence mismatch")
    failed = _check_set(evidence["required_checks"], required, identity, oracle=False, packet=packet)
    failed += _check_set(evidence["independent_acceptance"], acceptance_ids, identity, oracle=True, packet=packet)
    validation = _object(result["required_validation"], "required validation")
    _fields(validation, {"missing_or_failed", "evidence"}, "required validation")
    _require(validation == {"missing_or_failed": failed, "evidence": evidence["required_checks"]}, "required validation summary mismatch")
    expected_status, expected_success = ("FAILED_TASK", "failed") if failed else ("VALID_WITH_FINDINGS", "passed")
    _require(result["status"] == expected_status and result["task_success"] == expected_success, "contradictory technical status/task_success")
    _require(result["invalid_reasons"] == [], "non-invalid technical result contains invalid reasons")
    scope = _object(result["scope"], "scope")
    _fields(scope, {"changed_paths", "name_status", "diff_fingerprint", "findings"}, "scope")
    candidate = evidence["candidate"]
    changed = _paths(candidate.get("changed_paths"), "candidate changed paths")
    _require(_name_status_paths(candidate["name_status"]) == changed, "candidate changed_paths/name_status mismatch")
    for key in ("changed_paths", "name_status", "diff_fingerprint"):
        _require(scope[key] == candidate.get(key), f"scope/candidate {key} mismatch")
    allowed = _paths(packet.get("allowed_scope"), "allowed scope")
    protected = _paths(packet.get("forbidden_benchmark_mutations"), "protected paths")
    expected_findings = []
    for path in changed:
        if path in protected or path.startswith(("benchmarks/bakeoff-v1/", "tools/bakeoff_v1_grader")):
            expected_findings.append({"kind": "prohibited_benchmark_mutation", "path": path})
        elif path not in allowed:
            expected_findings.append({"kind": "out_of_scope_change", "path": path})
    anti_gaming = _object(result["anti_gaming"], "anti_gaming")
    _fields(anti_gaming, {"tamper_status", "findings"}, "anti_gaming")
    _require(anti_gaming["tamper_status"] == "not_detected", "contradictory tamper status")
    _require(scope["findings"] == anti_gaming["findings"] == expected_findings, "missing or contradictory technical scope findings")
    technical_ids = {_canonical_digest(item) for item in expected_findings}
    dispositions = {item["technical_finding_sha256"] for item in findings if item["technical_finding_sha256"] is not None}
    _require(dispositions == technical_ids, "missing or unmatched technical finding dispositions")
    for item in findings:
        if item["technical_finding_sha256"] in {
            _canonical_digest(raw) for raw in expected_findings if raw["kind"] == "prohibited_benchmark_mutation"
        }:
            _require(item["disposition"] == "prohibited_shortcut", "prohibited mutation cannot be downgraded")
    return [f"required acceptance did not pass: {check_id}" for check_id in failed]


def evaluate_final_acceptance(grading_result: bytes, grading_evidence: bytes, task_packet: bytes,
                              review_record: bytes | None, operator_attestation: bytes | None) -> dict[str, Any]:
    """Return a separate verdict; never mutate input, execute checks or authenticate people.

    The first three records form the technical input set. Supply their genuine
    retained bytes from the authorized grading workflow, including its frozen
    Task Packet. Review and attestation are separate logical inputs. Only an
    operator-controlled external workflow may supply the attestation.
    """
    output: dict[str, Any] = {"schema_version": "1", "verdict": "FAIL", "reasons": [], "bindings": None,
                              "authority_status": "unverified", "authority_notice": _AUTHORITY_NOTICE, "findings": []}
    try:
        result = _parse(grading_result, "grading result")
        _require(result.get("schema_version") == "1", "unsupported grading result version")
        # An explicit technical INVALID must never become ordinary task failure.
        if result.get("status") == "INVALID":
            output["verdict"] = "INVALID_RUN"
            output["reasons"] = ["technical grader reports INVALID; no successful acceptance is permitted"]
            return output
        evidence = _parse(grading_evidence, "grading evidence")
        packet = _parse(task_packet, "Task Packet")
        run, candidate = _identity(result, evidence)
        bindings = {"grading_result_sha256": sha256(grading_result).hexdigest(),
                    "grading_evidence_sha256": sha256(grading_evidence).hexdigest(),
                    "task_packet_sha256": sha256(task_packet).hexdigest(),
                    "run_identity": run, "candidate_identity": candidate}
        output["bindings"] = bindings
        review = _parse(review_record, "independent review")
        attestation = _parse(operator_attestation, "operator attestation")
        findings = _review_authority(review, attestation, bindings, review_record)
        output["authority_status"] = "externally_attested_structurally_valid"
        output["findings"] = findings
        prohibited = any(item["disposition"] == "prohibited_shortcut" for item in findings)
        if prohibited:
            output["verdict"] = "INVALID_RUN"
            output["reasons"].append("operator-approved independent review confirms a prohibited shortcut")
        reasons = _technical(result, evidence, packet, candidate, findings)
        reasons.extend(f"unresolved {item['disposition']} finding: {item['finding_id']}" for item in findings
                       if item["disposition"] in ("blocking", "ambiguous"))
        output["reasons"].extend(reasons)
        if not prohibited and not reasons:
            output["verdict"] = "PASS_WITH_NOTES" if findings else "PASS"
            output["reasons"] = ["all required technical gates passed and operator-attested independent review has no blockers"]
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        output["reasons"].append(f"evidence rejected: {exc}")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, epilog=_AUTHORITY_NOTICE)
    for name in ("grading-result", "grading-evidence", "task-packet", "review", "operator-attestation"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(argv)
    paths = [getattr(args, name) for name in ("grading_result", "grading_evidence", "task_packet", "review", "operator_attestation")]
    try:
        _require(len({path.resolve() for path in paths}) == len(paths), "inputs must be separate records")
        inputs = []
        read_errors = []
        for path in paths:
            try:
                inputs.append(path.read_bytes())
            except OSError as exc:
                inputs.append(None)
                read_errors.append(f"input unavailable: {exc}")
        output = evaluate_final_acceptance(*inputs)
        output["reasons"].extend(read_errors)
    except (OSError, ValueError) as exc:
        output = {"schema_version": "1", "verdict": "FAIL", "reasons": [f"input rejected: {exc}"],
                  "authority_status": "unverified", "authority_notice": _AUTHORITY_NOTICE}
    print(json.dumps(output, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0 if output["verdict"] in ("PASS", "PASS_WITH_NOTES") else 1


if __name__ == "__main__":
    raise SystemExit(main())
