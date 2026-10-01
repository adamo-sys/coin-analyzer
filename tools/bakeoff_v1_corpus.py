"""Validate the immutable local Bake-Off v1 replay corpus declaration."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any


class CorpusValidationError(ValueError):
    """Raised when the Bake-Off v1 corpus is malformed or inconsistent."""


_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TASK_IDS = ("BO1-TASK-PACKETS", "BO1-TAMPER-BATCH")
_TOP_LEVEL = frozenset({"benchmark_id", "benchmark_version", "freeze", "integrity_root_sha256", "tasks"})
_TASK_FIELDS = frozenset(
    {
        "task_id",
        "task_packet",
        "benchmark_class",
        "starting_sha",
        "source_history",
        "objective_source",
        "acceptance_evidence",
        "allowed_scope",
        "forbidden_benchmark_mutations",
        "network_provider_policy",
        "required_validation",
        "ground_truth_evidence",
        "provenance_sources",
    }
)
_TASK_PACKET_FIELDS = frozenset(
    {
        "schema_version",
        "benchmark_version",
        "task_id",
        "benchmark_class",
        "objective",
        "starting_sha",
        "reference_end_sha",
        "reference_changed_paths",
        "reference_diff_fingerprint",
        "expected_implementation_paths",
        "allowed_scope",
        "forbidden_benchmark_mutations",
        "required_validation",
        "network_provider_policy",
        "historical_provenance",
    }
)


def _require_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise CorpusValidationError(f"{name} must be a non-empty string")
    return value


def _require_strings(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise CorpusValidationError(f"{name} must be a non-empty list of strings")
    return value


def _assert_commit_exists(commit_sha: str, repository: Path, field: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repository), "cat-file", "-e", f"{commit_sha}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise CorpusValidationError(f"{field} is not a local commit: {commit_sha}")


def _git_output(repository: Path, arguments: list[str], *, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        input=input_bytes,
        check=False,
    )
    if result.returncode:
        raise CorpusValidationError(f"Git command failed: {' '.join(arguments)}")
    return result.stdout


def _validate_integrity_root(manifest_path: Path, expected_digest: str) -> dict[str, str]:
    if not _SHA256.fullmatch(expected_digest):
        raise CorpusValidationError("integrity_root_sha256 must be a lowercase SHA-256")
    integrity_path = manifest_path.parent / "integrity.json"
    raw = integrity_path.read_bytes()
    if sha256(raw).hexdigest() != expected_digest:
        raise CorpusValidationError("integrity root SHA-256 does not match manifest")
    try:
        integrity = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CorpusValidationError("integrity root is not valid JSON") from exc
    if not isinstance(integrity, dict) or set(integrity) != {"schema_version", "artifacts"}:
        raise CorpusValidationError("integrity root has an invalid field set")
    if integrity["schema_version"] != "1" or not isinstance(integrity["artifacts"], list):
        raise CorpusValidationError("integrity root declaration is invalid")
    artifacts: dict[str, str] = {}
    for artifact in integrity["artifacts"]:
        if not isinstance(artifact, dict) or set(artifact) != {"path", "sha256"}:
            raise CorpusValidationError("integrity artifact has an invalid field set")
        path = _require_string(artifact["path"], "integrity artifact path")
        digest = _require_string(artifact["sha256"], "integrity artifact sha256")
        if not _SHA256.fullmatch(digest) or path in artifacts:
            raise CorpusValidationError("integrity artifact declaration is invalid")
        artifacts[path] = digest
    return artifacts


def _validate_task_packet(task: dict[str, Any], artifact_root: Path, repository: Path, artifacts: Mapping[str, str]) -> None:
    packet_path_value = _require_string(task["task_packet"], "task_packet")
    expected_path = f"benchmarks/bakeoff-v1/tasks/{task['task_id']}.json"
    if packet_path_value != expected_path:
        raise CorpusValidationError("task packet path must use the frozen task location")
    if packet_path_value not in artifacts:
        raise CorpusValidationError("task packet is not covered by the integrity root")
    packet_path = artifact_root / packet_path_value
    raw = packet_path.read_bytes()
    if sha256(raw).hexdigest() != artifacts[packet_path_value]:
        raise CorpusValidationError("task packet SHA-256 does not match integrity root")
    try:
        packet = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CorpusValidationError("task packet is not valid JSON") from exc
    if not isinstance(packet, dict) or set(packet) != _TASK_PACKET_FIELDS:
        raise CorpusValidationError("task packet has an invalid field set")
    for field in ("task_id", "benchmark_class", "starting_sha", "required_validation", "network_provider_policy"):
        if packet[field] != task[field]:
            raise CorpusValidationError(f"task packet {field} does not match manifest")
    if set(packet["allowed_scope"]) != set(task["allowed_scope"]):
        raise CorpusValidationError("task packet allowed_scope does not match manifest")
    if packet["schema_version"] != "1" or packet["benchmark_version"] != "1.0":
        raise CorpusValidationError("task packet schema/version is invalid")
    _require_string(packet["objective"], "task packet objective")
    reference_end_sha = _require_string(packet["reference_end_sha"], "reference_end_sha")
    if not _SHA.fullmatch(reference_end_sha):
        raise CorpusValidationError("reference_end_sha must be a full SHA")
    _assert_commit_exists(reference_end_sha, repository, "reference_end_sha")
    ancestry = subprocess.run(
        ["git", "-C", str(repository), "merge-base", "--is-ancestor", task["starting_sha"], reference_end_sha],
        capture_output=True,
        check=False,
    )
    if ancestry.returncode:
        raise CorpusValidationError("starting_sha must be an ancestor of reference_end_sha")
    changed_paths = _git_output(repository, ["diff", "--no-ext-diff", "--name-only", task["starting_sha"], reference_end_sha]).decode("utf-8").splitlines()
    if packet["reference_changed_paths"] != changed_paths:
        raise CorpusValidationError("reference changed paths do not match Git derivation")
    reference_diff = _git_output(repository, ["diff", "--no-ext-diff", "--binary", task["starting_sha"], reference_end_sha])
    fingerprint = _git_output(repository, ["hash-object", "--stdin"], input_bytes=reference_diff).decode("ascii").strip()
    if packet["reference_diff_fingerprint"] != fingerprint:
        raise CorpusValidationError("reference diff fingerprint does not match Git derivation")
    if not _SHA.fullmatch(packet["reference_diff_fingerprint"]):
        raise CorpusValidationError("reference diff fingerprint must be a Git object SHA")
    for field in ("reference_changed_paths", "allowed_scope", "forbidden_benchmark_mutations", "required_validation", "historical_provenance"):
        _require_strings(packet[field], f"task packet {field}")
    expected_implementations = packet["expected_implementation_paths"]
    if not isinstance(expected_implementations, dict) or set(expected_implementations) != {
        path for path in packet["reference_changed_paths"] if path.startswith(("tests/", "test_"))
    }:
        raise CorpusValidationError("task packet expected implementation paths are invalid")
    for test_path, implementation_paths in expected_implementations.items():
        if not isinstance(test_path, str) or not test_path:
            raise CorpusValidationError("task packet expected implementation test path is invalid")
        _require_strings(implementation_paths, "task packet expected implementation paths")
        if any(path not in packet["allowed_scope"] or path.startswith(("tests/", "test_")) for path in implementation_paths):
            raise CorpusValidationError("task packet expected implementation path is outside implementation scope")


def _apply_overrides(payload: dict[str, Any], overrides: Mapping[str, object] | None) -> None:
    for dotted_path, value in (overrides or {}).items():
        parts = dotted_path.split(".")
        target: object = payload
        for part in parts[:-1]:
            if isinstance(target, dict):
                target = target[part]
            elif isinstance(target, list) and part.isdigit():
                target = target[int(part)]
            else:
                raise CorpusValidationError(f"invalid override path: {dotted_path}")
        if isinstance(target, dict):
            target[parts[-1]] = value
        elif isinstance(target, list) and parts[-1].isdigit():
            target[int(parts[-1])] = value
        else:
            raise CorpusValidationError(f"invalid override path: {dotted_path}")


def validate_corpus(
    manifest_path: Path,
    sidecar_path: Path,
    *,
    overrides: Mapping[str, object] | None = None,
    repository: Path | None = None,
) -> dict[str, Any]:
    """Validate internal corpus consistency only; this does not establish freeze identity."""
    raw = manifest_path.read_bytes()
    expected_digest = sidecar_path.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise CorpusValidationError("manifest sidecar must contain one lowercase SHA-256")
    if sha256(raw).hexdigest() != expected_digest:
        raise CorpusValidationError("manifest SHA-256 does not match sidecar")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CorpusValidationError("manifest is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise CorpusValidationError("manifest must be an object")
    payload = deepcopy(payload)
    _apply_overrides(payload, overrides)
    if set(payload) != _TOP_LEVEL:
        raise CorpusValidationError("manifest has an invalid top-level field set")
    if payload.get("benchmark_id") != "coin-analyzer-bakeoff-v1":
        raise CorpusValidationError("unexpected benchmark_id")
    if payload.get("benchmark_version") != "1.0":
        raise CorpusValidationError("unexpected benchmark_version")
    freeze = payload.get("freeze")
    if not isinstance(freeze, dict) or set(freeze) != {"manifest_integrity", "static_control_integrity", "authoritative_artifact"}:
        raise CorpusValidationError("freeze declaration is invalid")
    if freeze["manifest_integrity"] != "sha256-sidecar-raw-bytes-v1":
        raise CorpusValidationError("unexpected manifest integrity method")
    _require_string(freeze["authoritative_artifact"], "freeze.authoritative_artifact")
    if freeze["static_control_integrity"] != "manifest-sidecar-plus-integrity-root-v1":
        raise CorpusValidationError("unexpected static control integrity method")
    artifacts = _validate_integrity_root(manifest_path, _require_string(payload["integrity_root_sha256"], "integrity_root_sha256"))
    artifact_root = manifest_path.parents[2]
    for artifact_path, expected_artifact_digest in artifacts.items():
        relative = Path(artifact_path)
        resolved = (artifact_root / relative).resolve()
        if relative.is_absolute() or artifact_root.resolve() not in resolved.parents or not resolved.is_file():
            raise CorpusValidationError("integrity artifact path is unavailable or unsafe")
        if sha256(resolved.read_bytes()).hexdigest() != expected_artifact_digest:
            raise CorpusValidationError("integrity artifact SHA-256 does not match integrity root")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != len(_TASK_IDS):
        raise CorpusValidationError("manifest must contain exactly the selected V1 tasks")
    if tuple(task.get("task_id") if isinstance(task, dict) else None for task in tasks) != _TASK_IDS:
        raise CorpusValidationError("manifest task IDs must be unique and in frozen V1 order")
    repository = repository or artifact_root
    for task in tasks:
        if not isinstance(task, dict) or set(task) != _TASK_FIELDS:
            raise CorpusValidationError("task has an invalid field set")
        if task["benchmark_class"] != "replay_known_history":
            raise CorpusValidationError("task contamination classification must be replay_known_history")
        starting_sha = _require_string(task["starting_sha"], "starting_sha")
        if not _SHA.fullmatch(starting_sha):
            raise CorpusValidationError("starting_sha must be a full SHA")
        _assert_commit_exists(starting_sha, repository, "starting_sha")
        if task["network_provider_policy"] != "network_and_provider_access_forbidden":
            raise CorpusValidationError("network/provider policy must be explicit and forbidden")
        for field in (
            "source_history",
            "objective_source",
            "acceptance_evidence",
            "allowed_scope",
            "forbidden_benchmark_mutations",
            "required_validation",
            "ground_truth_evidence",
            "provenance_sources",
        ):
            _require_strings(task[field], field)
        _validate_task_packet(task, artifact_root, repository, artifacts)
    return payload


def calculate_corpus_seal(
    manifest_path: Path,
    sidecar_path: Path,
    *,
    repository: Path | None = None,
) -> str:
    """Return the canonical V1 corpus identity digest after internal validation."""
    corpus = validate_corpus(manifest_path, sidecar_path, repository=repository)
    artifact_root = manifest_path.parents[2]
    repository = repository or artifact_root
    tasks: list[dict[str, object]] = []
    for task in corpus["tasks"]:
        packet_path = artifact_root / str(task["task_packet"])
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        reference_end_sha = str(packet["reference_end_sha"])
        test_blobs = []
        for path in packet["reference_changed_paths"]:
            if path.startswith(("tests/", "test_")):
                blob_sha = _git_output(repository, ["rev-parse", f"{reference_end_sha}:{path}"]).decode("ascii").strip()
                test_blobs.append({"path": path, "blob_sha": blob_sha})
        tasks.append(
            {
                "task_id": task["task_id"],
                "starting_sha": task["starting_sha"],
                "task_packet_sha256": sha256(packet_path.read_bytes()).hexdigest(),
                "reference_end_sha": reference_end_sha,
                "reference_diff_fingerprint": packet["reference_diff_fingerprint"],
                "reference_test_blobs": test_blobs,
            }
        )
    integrity_path = manifest_path.parent / "integrity.json"
    material = {
        "schema_version": "bakeoff-v1-corpus-seal-v1",
        "manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
        "integrity_root_sha256": sha256(integrity_path.read_bytes()).hexdigest(),
        "tasks": tasks,
    }
    return _canonical_sha256(material)


def _canonical_sha256(value: Mapping[str, object]) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def validate_frozen_corpus(
    manifest_path: Path,
    sidecar_path: Path,
    *,
    expected_seal: str | None,
    repository: Path | None = None,
) -> dict[str, Any]:
    """Validate internal consistency and an operator-supplied external corpus seal."""
    if not isinstance(expected_seal, str) or not _SHA256.fullmatch(expected_seal):
        raise CorpusValidationError("freeze-grade validation requires a lowercase external corpus seal")
    corpus = validate_corpus(manifest_path, sidecar_path, repository=repository)
    actual_seal = calculate_corpus_seal(manifest_path, sidecar_path, repository=repository)
    if actual_seal != expected_seal:
        raise CorpusValidationError("external corpus seal does not match the validated corpus")
    return corpus


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("benchmarks/bakeoff-v1/manifest.json"))
    parser.add_argument("--sidecar", type=Path, default=Path("benchmarks/bakeoff-v1/manifest.sha256"))
    parser.add_argument("--freeze-grade", action="store_true", help="require an externally supplied expected corpus seal")
    parser.add_argument("--expected-corpus-seal", help="external expected seal; never source this from the corpus directory")
    parser.add_argument("--print-corpus-seal", action="store_true", help="print the current candidate seal after internal validation")
    args = parser.parse_args(arguments)
    try:
        if args.freeze_grade:
            validate_frozen_corpus(args.manifest, args.sidecar, expected_seal=args.expected_corpus_seal)
            print("valid externally anchored Bake-Off v1 corpus")
        elif args.expected_corpus_seal is not None:
            raise CorpusValidationError("--expected-corpus-seal requires --freeze-grade")
        else:
            validate_corpus(args.manifest, args.sidecar)
            print("valid internally consistent Bake-Off v1 corpus")
        if args.print_corpus_seal:
            print(calculate_corpus_seal(args.manifest, args.sidecar))
    except (CorpusValidationError, OSError) as exc:
        print(f"invalid Bake-Off v1 corpus: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
