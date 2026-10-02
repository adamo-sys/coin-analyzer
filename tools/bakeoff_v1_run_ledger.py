"""Offline validation for contestant-neutral Bake-Off v1 run records."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.bakeoff_v1_corpus import CorpusValidationError, validate_frozen_corpus


class RunLedgerValidationError(ValueError):
    """Raised when a normalized run record is malformed or corpus-inconsistent."""


_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_AVAILABILITY = frozenset({"measured", "derived", "unavailable", "not_applicable", "not_yet_graded"})
_TERMINAL_STATUS = frozenset({"completed", "failed", "timed_out", "interrupted", "invalid_run"})
_OPTIONAL_LAYERS = ("model", "harness", "memory_layer", "skills_or_instructions_layer", "control_orchestration_layer")


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RunLedgerValidationError(f"{name} must be a non-empty string")
    return value


def _timestamp(value: object, name: str) -> datetime:
    value = _string(value, name)
    if not _TIMESTAMP.fullmatch(value):
        raise RunLedgerValidationError(f"{name} must be a UTC RFC3339 timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise RunLedgerValidationError(f"{name} must be a valid timestamp") from exc


def _string_list(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise RunLedgerValidationError(f"{name} must be a list of non-empty strings")
    return value


def _measurement(value: object, name: str) -> None:
    if not isinstance(value, dict) or set(value) != {"availability", "value", "provenance"}:
        raise RunLedgerValidationError(f"measurement {name} has an invalid field set")
    availability = value["availability"]
    if availability not in _AVAILABILITY:
        raise RunLedgerValidationError(f"measurement {name} has an invalid availability state")
    provenance = _string_list(value["provenance"], f"measurement {name}.provenance")
    if availability in {"unavailable", "not_applicable", "not_yet_graded"}:
        if value["value"] is not None or provenance:
            raise RunLedgerValidationError(f"measurement {name} is {availability} and must not carry a value or provenance")
    elif value["value"] is None or not provenance:
        raise RunLedgerValidationError(f"measurement {name} is {availability} and requires value and provenance")


def _contestant(value: object) -> None:
    if not isinstance(value, dict):
        raise RunLedgerValidationError("contestant must be an object")
    required = {
        "contestant_id", *_OPTIONAL_LAYERS, "tool_permissions", "network_policy", "context_policy", "environment_metadata"
    }
    if set(value) != required:
        raise RunLedgerValidationError("contestant has an invalid field set")
    _string(value["contestant_id"], "contestant_id")
    for name in _OPTIONAL_LAYERS:
        if value[name] is not None and (not isinstance(value[name], str) or not value[name]):
            raise RunLedgerValidationError(f"contestant.{name} must be null or a non-empty string")
    _string_list(value["tool_permissions"], "tool_permissions")
    _string(value["network_policy"], "network_policy")
    _string(value["context_policy"], "context_policy")
    if not isinstance(value["environment_metadata"], dict):
        raise RunLedgerValidationError("environment_metadata must be an object")


def _interventions(value: object, started: datetime, ended: datetime) -> None:
    if not isinstance(value, list):
        raise RunLedgerValidationError("human_interventions must be a list")
    for intervention in value:
        if not isinstance(intervention, dict) or set(intervention) != {
            "timestamp_utc", "intervention_type", "reason", "actor_category", "execution_changed"
        }:
            raise RunLedgerValidationError("human intervention has an invalid field set")
        occurred = _timestamp(intervention["timestamp_utc"], "human intervention timestamp")
        if occurred < started or occurred > ended:
            raise RunLedgerValidationError("human intervention timestamp must fall within the run")
        for name in ("intervention_type", "reason", "actor_category"):
            _string(intervention[name], f"human intervention {name}")
        if not isinstance(intervention["execution_changed"], bool):
            raise RunLedgerValidationError("human intervention execution_changed must be bool")


def _v11_candidate_state(record: Mapping[str, object]) -> None:
    if record["execution_protocol_version"] != "1.1":
        raise RunLedgerValidationError("execution_protocol_version is invalid")
    for field in ("candidate_state_sha256", "candidate_state_manifest_sha256", "materialization_policy_sha256"):
        if not isinstance(record[field], str) or not _SHA256.fullmatch(record[field]):
            raise RunLedgerValidationError(f"{field} must be a lowercase SHA-256")
    if record["candidate_state_manifest_sha256"] != record["candidate_state_sha256"]:
        raise RunLedgerValidationError("candidate_state_manifest_sha256 must identify the frozen candidate state")
    if record["candidate_head"] != record["starting_sha"]:
        raise RunLedgerValidationError("candidate_head must match the uncommitted task start")
    if record["candidate_worktree_status"] not in {"clean", "dirty"}:
        raise RunLedgerValidationError("candidate_worktree_status is invalid")
    changes = record["candidate_changes"]
    if not isinstance(changes, dict) or set(changes) != {"added", "modified", "deleted"}:
        raise RunLedgerValidationError("candidate_changes has an invalid field set")
    for name, paths in changes.items():
        values = _string_list(paths, f"candidate_changes.{name}") if paths else []
        if len(values) != len(set(values)):
            raise RunLedgerValidationError("candidate_changes contains duplicate paths")
    freezer = record["freezer"]
    if not isinstance(freezer, dict) or set(freezer) != {"status", "failure_reason"}:
        raise RunLedgerValidationError("freezer has an invalid field set")
    if freezer["status"] not in {"frozen", "failed"}:
        raise RunLedgerValidationError("freezer status is invalid")
    if freezer["status"] == "frozen" and freezer["failure_reason"] is not None:
        raise RunLedgerValidationError("frozen freezer state must not carry a failure reason")
    if freezer["status"] == "failed" and (not isinstance(freezer["failure_reason"], str) or not freezer["failure_reason"]):
        raise RunLedgerValidationError("failed freezer state requires a reason")


def validate_run_record(
    record: Mapping[str, object],
    manifest_path: Path,
    sidecar_path: Path,
    *,
    expected_corpus_seal: str | None = None,
    known_run_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Validate one offline run record against an externally anchored V1 corpus."""
    if not isinstance(record, dict):
        raise RunLedgerValidationError("run record must be an object")
    v10_fields = {
        "schema_version", "benchmark_version", "corpus_manifest_sha256", "task_id", "contestant", "run_id",
        "starting_sha", "ending_sha", "started_at_utc", "ended_at_utc", "terminal_status", "measurements",
        "human_interventions", "artifacts",
    }
    v11_fields = v10_fields | {
        "execution_protocol_version", "candidate_state_sha256", "candidate_state_manifest_sha256", "candidate_head",
        "materialization_policy_sha256", "candidate_worktree_status", "candidate_changes", "freezer",
    }
    schema_version = record.get("schema_version")
    if schema_version == "1":
        expected_fields = v10_fields
    elif schema_version == "1.1":
        expected_fields = v11_fields
    else:
        raise RunLedgerValidationError("run record schema or benchmark version is invalid")
    if set(record) != expected_fields:
        raise RunLedgerValidationError("run record has an invalid field set")
    try:
        corpus = validate_frozen_corpus(manifest_path, sidecar_path, expected_seal=expected_corpus_seal)
    except CorpusValidationError as exc:
        raise RunLedgerValidationError(str(exc)) from exc
    if record["benchmark_version"] != corpus["benchmark_version"]:
        raise RunLedgerValidationError("run record schema or benchmark version is invalid")
    sidecar_digest = sidecar_path.read_text(encoding="ascii").strip()
    if record["corpus_manifest_sha256"] != sidecar_digest:
        raise RunLedgerValidationError("run record corpus manifest fingerprint does not match")
    task_id = _string(record["task_id"], "task_id")
    task = next((item for item in corpus["tasks"] if item["task_id"] == task_id), None)
    if task is None:
        raise RunLedgerValidationError("run record task_id is not in the frozen corpus")
    if record["starting_sha"] != task["starting_sha"]:
        raise RunLedgerValidationError("run record starting_sha does not match frozen task")
    if schema_version == "1.1":
        _v11_candidate_state(record)
    _contestant(record["contestant"])
    run_id = _string(record["run_id"], "run_id")
    if known_run_ids is not None and run_id in known_run_ids:
        raise RunLedgerValidationError("duplicate run_id in validation context")
    if record["ending_sha"] is not None:
        ending_sha = _string(record["ending_sha"], "ending_sha")
        if not _GIT_SHA.fullmatch(ending_sha):
            raise RunLedgerValidationError("ending_sha must be a full Git commit SHA or null")
    started = _timestamp(record["started_at_utc"], "started_at_utc")
    ended = _timestamp(record["ended_at_utc"], "ended_at_utc")
    if ended < started:
        raise RunLedgerValidationError("run end timestamp must not precede start timestamp")
    if record["terminal_status"] not in _TERMINAL_STATUS:
        raise RunLedgerValidationError("terminal_status is invalid")
    if not isinstance(record["measurements"], dict) or not record["measurements"]:
        raise RunLedgerValidationError("measurements must be a non-empty object")
    for name, measurement in record["measurements"].items():
        _string(name, "measurement name")
        _measurement(measurement, name)
    _interventions(record["human_interventions"], started, ended)
    _string_list(record["artifacts"], "artifacts")
    return dict(record)


def canonical_record_bytes(record: Mapping[str, object]) -> bytes:
    """Serialize a prevalidated record deterministically for one-file-per-run storage."""
    import json

    return (json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")
