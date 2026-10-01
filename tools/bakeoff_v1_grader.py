"""Deterministic, contestant-independent Bake-Off v1 grading checks."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import sys
from typing import Any, Mapping

from tools.bakeoff_v1_corpus import validate_frozen_corpus
from tools.bakeoff_v1_run_ledger import RunLedgerValidationError, validate_run_record


class GradingEvidenceError(ValueError):
    """Raised when independently collected candidate evidence is invalid."""


_CHECK_TIMEOUT_SECONDS = 5


def _canonical_digest(value: Mapping[str, object]) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _git(repository: Path, arguments: list[str], *, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(["git", "-C", str(repository), *arguments], input=input_bytes, capture_output=True, check=False)
    if result.returncode:
        raise GradingEvidenceError(f"candidate Git command failed: {' '.join(arguments)}")
    return result.stdout


def _frozen_packet(task: Mapping[str, object], manifest: Path) -> dict[str, Any]:
    root = manifest.parents[2]
    try:
        packet = json.loads((root / str(task["task_packet"])).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GradingEvidenceError("frozen task packet is unavailable") from exc
    if not isinstance(packet, dict):
        raise GradingEvidenceError("frozen task packet is invalid")
    return packet


def _candidate_identity(repository: Path, starting_sha: str, ending_sha: object) -> dict[str, object]:
    if not repository.is_dir():
        raise GradingEvidenceError("candidate repository path is not a directory")
    if not isinstance(ending_sha, str) or len(ending_sha) != 40:
        raise GradingEvidenceError("grading requires a full committed ending_sha")
    ending_commit = _git(repository, ["rev-parse", f"{ending_sha}^{{commit}}"]).decode("ascii").strip()
    if ending_commit != ending_sha:
        raise GradingEvidenceError("candidate ending_sha does not resolve to the claimed full commit")
    head = _git(repository, ["rev-parse", "HEAD^{commit}"]).decode("ascii").strip()
    if head != ending_sha:
        raise GradingEvidenceError("candidate HEAD does not match ending_sha")
    ancestry = subprocess.run(["git", "-C", str(repository), "merge-base", "--is-ancestor", starting_sha, ending_sha], capture_output=True, check=False)
    if ancestry.returncode:
        raise GradingEvidenceError("candidate ending_sha is not descended from frozen starting_sha")
    if _git(repository, ["status", "--porcelain=v1"]):
        raise GradingEvidenceError("candidate worktree is dirty; commit the candidate state before grading")
    name_status = _git(repository, ["diff", "--no-ext-diff", "--name-status", "--find-renames", starting_sha, ending_sha]).decode("utf-8").splitlines()
    changed_paths = _git(repository, ["diff", "--no-ext-diff", "--name-only", "--find-renames", starting_sha, ending_sha]).decode("utf-8").splitlines()
    binary_diff = _git(repository, ["diff", "--no-ext-diff", "--binary", starting_sha, ending_sha])
    diff_fingerprint = _git(repository, ["hash-object", "--stdin"], input_bytes=binary_diff).decode("ascii").strip()
    return {"ending_sha": ending_sha, "tree_sha": _git(repository, ["rev-parse", f"{ending_sha}^{{tree}}"]).decode("ascii").strip(), "git_status": [], "name_status": name_status, "changed_paths": changed_paths, "diff_fingerprint": diff_fingerprint}


def _command_arguments(command: str, candidate_repository: Path, inputs: Mapping[str, Mapping[str, str]] | None) -> list[str]:
    replacements = (inputs or {}).get(command, {})
    if not isinstance(replacements, Mapping):
        raise GradingEvidenceError("required-check inputs must be a mapping")
    resolved: list[str] = []
    for argument in shlex.split(command, posix=True):
        if argument.startswith("<") and argument.endswith(">"):
            supplied = replacements.get(argument)
            if not isinstance(supplied, str):
                raise GradingEvidenceError(f"required check input is missing for {argument}")
            relative = PurePosixPath(supplied)
            if relative.is_absolute() or ".." in relative.parts:
                raise GradingEvidenceError("required check input must be a safe candidate-relative path")
            path = (candidate_repository / Path(*relative.parts)).resolve()
            if candidate_repository.resolve() not in path.parents or not path.is_file():
                raise GradingEvidenceError("required check input must identify an existing candidate file")
            resolved.append(str(path))
        else:
            resolved.append(argument)
    return resolved


def _execute_checks(packet: Mapping[str, object], candidate_repository: Path, candidate: Mapping[str, object], check_inputs: Mapping[str, Mapping[str, str]] | None) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for order, command in enumerate(packet["required_validation"]):
        if not isinstance(command, str):
            raise GradingEvidenceError("frozen required check command is invalid")
        try:
            arguments = _command_arguments(command, candidate_repository, check_inputs)
            result = subprocess.run(arguments, cwd=candidate_repository, capture_output=True, check=False, timeout=_CHECK_TIMEOUT_SECONDS)
            output_digest = sha256(result.stdout + b"\0" + result.stderr).hexdigest()
            status, error = ("passed" if result.returncode == 0 else "failed"), None
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or b"") + b"\0" + (exc.stderr or b"")
            result, output_digest, status, error = None, sha256(output).hexdigest(), "timed_out", str(exc)
        except (GradingEvidenceError, OSError) as exc:
            result, output_digest, status, error = None, None, "unavailable", str(exc)
        checks.append({"check_id": command, "command": command, "execution_order": order, "candidate_ending_sha": candidate["ending_sha"], "status": status, "exit_code": None if result is None else result.returncode, "output_sha256": output_digest, "provenance": "trusted_local_execution", "error": error})
    return checks


def _validate_implementation_provenance(expected_paths: list[str], resolved_modules: list[tuple[str, str, bool]]) -> tuple[str, list[str], list[str]]:
    """Require the frozen implementation paths, excluding synthetic test modules."""
    observed = sorted({path for _, path, inside_candidate in resolved_modules if inside_candidate and path in expected_paths})
    expected_names = {PurePosixPath(path).name for path in expected_paths}
    outside = sorted({path for _, path, inside_candidate in resolved_modules if not inside_candidate and Path(path).name in expected_names})
    if outside:
        return "outside_candidate_implementation", observed, outside
    if set(observed) != set(expected_paths):
        return "missing_expected_implementation", observed, outside
    return "passed", observed, outside


def _independent_acceptance(packet: Mapping[str, object], candidate_repository: Path, candidate: Mapping[str, object]) -> list[dict[str, object]]:
    """Run immutable reference-test blobs while importing code from the candidate tree."""
    paths = [path for path in packet["reference_changed_paths"] if path.startswith("tests/") or path.startswith("test_")]
    results: list[dict[str, object]] = []
    runner = "import json, os, sys, types; test_path, candidate_root = sys.argv[1:3]; root = os.path.realpath(candidate_root); sys.argv[:] = [sys.argv[0]]; sys.path.insert(0, root); module = types.ModuleType('__main__'); module.__file__ = test_path; sys.modules['__main__'] = module; code = 0\ntry:\n exec(compile(sys.stdin.buffer.read(), test_path, 'exec'), module.__dict__)\nexcept SystemExit as exc:\n code = exc.code or 0\npaths = []\nfor name, value in {**sys.modules, **module.__dict__}.items():\n file = getattr(value, '__file__', None)\n if isinstance(file, str) and file.endswith('.py'):\n  resolved = os.path.realpath(file)\n  inside = resolved.startswith(root + os.sep)\n  location = os.path.relpath(resolved, root).replace('\\\\', '/') if inside else resolved\n  paths.append((str(name), location, inside))\nprint('__BAKEOFF_PROVENANCE__' + json.dumps(sorted(set(paths))))\nraise SystemExit(code)"
    for order, path in enumerate(paths):
        blob_sha = content_sha256 = None
        provenance: list[tuple[str, str, bool]] = []
        expected_paths = packet["expected_implementation_paths"][path]
        try:
            source = _git(candidate_repository, ["show", f"{packet['reference_end_sha']}:{path}"])
            blob_sha = _git(candidate_repository, ["rev-parse", f"{packet['reference_end_sha']}:{path}"]).decode("ascii").strip()
            content_sha256 = sha256(source).hexdigest()
            result = subprocess.run([sys.executable, "-c", runner, str(candidate_repository / path), str(candidate_repository)], cwd=candidate_repository, input=source, capture_output=True, check=False, timeout=_CHECK_TIMEOUT_SECONDS)
            digest = sha256(result.stdout + b"\0" + result.stderr).hexdigest()
            status, error = ("passed" if result.returncode == 0 else "failed"), None
            marker = b"__BAKEOFF_PROVENANCE__"
            if marker in result.stdout:
                provenance = [tuple(item) for item in json.loads(result.stdout.split(marker)[-1].splitlines()[0])]
            provenance_status, observed_paths, outside_paths = _validate_implementation_provenance(expected_paths, provenance)
            if provenance_status != "passed":
                status, error = "unavailable", provenance_status
        except subprocess.TimeoutExpired as exc:
            result, digest, status, error = None, sha256((exc.stdout or b"") + b"\0" + (exc.stderr or b"")).hexdigest(), "timed_out", str(exc)
            provenance_status, observed_paths, outside_paths = "unavailable", [], []
        except (GradingEvidenceError, OSError) as exc:
            result, digest, status, error = None, None, "unavailable", str(exc)
            provenance_status, observed_paths, outside_paths = "unavailable", [], []
        results.append({"check_id": f"reference-acceptance:{path}", "test_path": path, "source": f"{packet['reference_end_sha']}:{path}", "source_blob_sha": blob_sha, "source_content_sha256": content_sha256, "execution_order": order, "candidate_ending_sha": candidate["ending_sha"], "status": status, "exit_code": None if result is None else result.returncode, "output_sha256": digest, "provenance": "frozen_reference_test_blob_against_candidate", "candidate_module_provenance": provenance, "expected_implementation_paths": expected_paths, "observed_implementation_paths": observed_paths, "outside_implementation_paths": outside_paths, "provenance_validation": provenance_status, "candidate_import_root": str(candidate_repository.resolve()), "error": error})
    return results


def collect_grading_evidence(record: Mapping[str, object], manifest: Path, sidecar: Path, *, candidate_repository: Path, expected_corpus_seal: str | None = None, check_inputs: Mapping[str, Mapping[str, str]] | None = None, claimed_changed_paths: list[str] | None = None, claimed_required_checks: Mapping[str, str] | None = None) -> dict[str, object]:
    """Bind independently derived Git state and local frozen-check results to one run."""
    run = validate_run_record(record, manifest, sidecar, expected_corpus_seal=expected_corpus_seal)
    corpus = validate_frozen_corpus(manifest, sidecar, expected_seal=expected_corpus_seal)
    task = next(item for item in corpus["tasks"] if item["task_id"] == run["task_id"])
    candidate = _candidate_identity(candidate_repository, str(run["starting_sha"]), run["ending_sha"])
    packet = _frozen_packet(task, manifest)
    checks = _execute_checks(packet, candidate_repository, candidate, check_inputs)
    acceptance = _independent_acceptance(packet, candidate_repository, candidate)
    claims: dict[str, object] = {}
    if claimed_changed_paths is not None and claimed_changed_paths != candidate["changed_paths"]:
        claims["changed_paths_mismatch"] = True
    if claimed_required_checks is not None:
        actual = {str(item["check_id"]): str(item["status"]) for item in checks}
        if dict(claimed_required_checks) != actual:
            claims["required_checks_mismatch"] = True
    evidence: dict[str, object] = {"schema_version": "1", "grader_id": "bakeoff-v1-deterministic-grader", "grader_implementation": "evidence-bound-v2", "corpus_manifest_sha256": run["corpus_manifest_sha256"], "task_id": run["task_id"], "run_id": run["run_id"], "starting_sha": run["starting_sha"], "candidate": candidate, "required_checks": checks, "independent_acceptance": acceptance, "unverified_claim_mismatches": claims}
    evidence["evidence_sha256"] = _canonical_digest(evidence)
    return evidence


def _validate_complete_evidence_set(evidence: Mapping[str, object], packet: Mapping[str, object]) -> None:
    expected_checks = list(packet["required_validation"])
    checks = evidence.get("required_checks")
    if not isinstance(checks, list):
        raise GradingEvidenceError("grading evidence required checks are invalid")
    if [item.get("check_id") if isinstance(item, Mapping) else None for item in checks] != expected_checks:
        raise GradingEvidenceError("grading evidence does not contain the complete frozen required-check set")
    if [item.get("command") if isinstance(item, Mapping) else None for item in checks] != expected_checks:
        raise GradingEvidenceError("grading evidence required-check commands do not match the frozen set")
    expected_acceptance_paths = [path for path in packet["reference_changed_paths"] if path.startswith("tests/") or path.startswith("test_")]
    acceptance = evidence.get("independent_acceptance")
    if not isinstance(acceptance, list):
        raise GradingEvidenceError("grading evidence independent acceptance is invalid")
    expected_ids = [f"reference-acceptance:{path}" for path in expected_acceptance_paths]
    expected_sources = [f"{packet['reference_end_sha']}:{path}" for path in expected_acceptance_paths]
    if [item.get("check_id") if isinstance(item, Mapping) else None for item in acceptance] != expected_ids:
        raise GradingEvidenceError("grading evidence does not contain the complete frozen independent-acceptance set")
    if [item.get("source") if isinstance(item, Mapping) else None for item in acceptance] != expected_sources:
        raise GradingEvidenceError("grading evidence independent-acceptance sources do not match the frozen set")


def _grade_collected_evidence(record: Mapping[str, object], manifest: Path, sidecar: Path, evidence: Mapping[str, object], *, expected_corpus_seal: str | None = None) -> dict[str, object]:
    """Internal evaluation for evidence produced by collect_grading_evidence()."""
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        run = validate_run_record(record, manifest, sidecar, expected_corpus_seal=expected_corpus_seal)
        corpus = validate_frozen_corpus(manifest, sidecar, expected_seal=expected_corpus_seal)
        expected = {"schema_version", "grader_id", "grader_implementation", "corpus_manifest_sha256", "task_id", "run_id", "starting_sha", "candidate", "required_checks", "independent_acceptance", "unverified_claim_mismatches", "evidence_sha256"}
        if not isinstance(evidence, Mapping) or set(evidence) != expected:
            raise GradingEvidenceError("grading evidence has an invalid field set")
        unsigned = dict(evidence)
        fingerprint = unsigned.pop("evidence_sha256")
        if not isinstance(fingerprint, str) or fingerprint != _canonical_digest(unsigned):
            raise GradingEvidenceError("grading evidence fingerprint is invalid")
        for field in ("corpus_manifest_sha256", "task_id", "run_id", "starting_sha"):
            if evidence[field] != run[field]:
                raise GradingEvidenceError(f"grading evidence {field} does not match run record")
        candidate = evidence["candidate"]
        if not isinstance(candidate, Mapping) or candidate.get("ending_sha") != run["ending_sha"]:
            raise GradingEvidenceError("grading evidence candidate identity does not match run record")
        task = next(item for item in corpus["tasks"] if item["task_id"] == run["task_id"])
        _validate_complete_evidence_set(evidence, _frozen_packet(task, manifest))
    except (RunLedgerValidationError, GradingEvidenceError, ValueError) as exc:
        return {"schema_version": "1", "status": "INVALID", "invalid_reasons": [str(exc)], "findings": [], "checked_at_utc": checked_at}
    findings: list[dict[str, str]] = []
    for path in candidate["changed_paths"]:
        if path in task["forbidden_benchmark_mutations"] or path.startswith("benchmarks/bakeoff-v1/") or path.startswith("tools/bakeoff_v1_grader"):
            findings.append({"kind": "prohibited_benchmark_mutation", "path": path})
        elif path not in task["allowed_scope"]:
            findings.append({"kind": "out_of_scope_change", "path": path})
    checks = evidence["required_checks"]
    failed = [item["check_id"] for item in checks if item["status"] != "passed"] + [item["check_id"] for item in evidence["independent_acceptance"] if item["status"] != "passed"]
    if any(item["kind"] == "prohibited_benchmark_mutation" for item in findings):
        status, success = "INVALID", "unavailable"
    elif failed:
        status, success = "FAILED_TASK", "failed"
    else:
        status, success = "VALID_WITH_FINDINGS", "passed"
    return {"schema_version": "1", "grader_id": "bakeoff-v1-deterministic-grader", "grader_implementation": "evidence-bound-v2", "checked_at_utc": checked_at, "task_id": run["task_id"], "run_id": run["run_id"], "corpus_manifest_sha256": run["corpus_manifest_sha256"], "status": status, "task_success": success, "required_validation": {"missing_or_failed": failed, "evidence": checks}, "scope": {"changed_paths": candidate["changed_paths"], "name_status": candidate["name_status"], "diff_fingerprint": candidate["diff_fingerprint"], "findings": findings}, "anti_gaming": {"tamper_status": "failed" if status == "INVALID" else "not_detected", "findings": findings}, "invalid_reasons": [item["path"] for item in findings if item["kind"] == "prohibited_benchmark_mutation"], "evidence": {"evidence_sha256": evidence["evidence_sha256"], "claims": evidence["unverified_claim_mismatches"]}}


def grade_run(record: Mapping[str, object], manifest: Path, sidecar: Path, *, candidate_repository: Path, expected_corpus_seal: str | None = None, check_inputs: Mapping[str, Mapping[str, str]] | None = None, claimed_changed_paths: list[str] | None = None, claimed_required_checks: Mapping[str, str] | None = None) -> dict[str, object]:
    """Collect independent candidate evidence, then grade it; claims never control success."""
    try:
        evidence = collect_grading_evidence(record, manifest, sidecar, candidate_repository=candidate_repository, expected_corpus_seal=expected_corpus_seal, check_inputs=check_inputs, claimed_changed_paths=claimed_changed_paths, claimed_required_checks=claimed_required_checks)
    except (RunLedgerValidationError, GradingEvidenceError, ValueError) as exc:
        return {"schema_version": "1", "status": "INVALID", "invalid_reasons": [str(exc)], "findings": [], "checked_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    return _grade_collected_evidence(record, manifest, sidecar, evidence, expected_corpus_seal=expected_corpus_seal)
