"""Separate append-only persistence for privacy-bounded AI execution audits.

The store is observational only. It never writes collection state, invokes a
provider, authorizes persistence, captures prompts/images, or exposes mutation
or deletion APIs for prior audit records.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
from typing import Any

from ai_evaluation_contracts import EvaluationOutcomeClassification
from ai_execution_audit import (
    AI_EXECUTION_AUDIT_SCHEMA_VERSION,
    AIExecutionAuditRecord,
    HumanDisposition,
    PersistenceDisposition,
    serialize_ai_execution_audit_record,
)
from capture_import.errors import ImportLocked, RecoveryRequired
from capture_import.lock import PackageImportLock


MAX_AUDIT_STORE_BYTES = 16 * 1024 * 1024
MAX_AUDIT_RECORDS = 10_000

_EXPECTED_KEYS = frozenset(
    {
        "schema_version",
        "execution_id",
        "occurred_at",
        "workflow_id",
        "executor_id",
        "case_id",
        "evidence_refs",
        "authorized_candidate_ids",
        "selected_candidate_id",
        "abstained",
        "verifier_accepted",
        "verifier_reason_codes",
        "evaluation_classification",
        "evaluation_reason_codes",
        "human_disposition",
        "persistence_disposition",
    }
)


class AIExecutionAuditStoreError(RuntimeError):
    """Base error for audit-store read/write failures."""


class AIExecutionAuditStoreLocked(AIExecutionAuditStoreError):
    """Another cooperating writer currently holds the store lease."""


class AIExecutionAuditStoreCorrupt(AIExecutionAuditStoreError):
    """Existing audit bytes are malformed, unsupported, or inconsistent."""


class AIExecutionAuditStoreFull(AIExecutionAuditStoreError):
    """The bounded audit store cannot accept another record."""


class AIExecutionAuditDuplicateExecution(AIExecutionAuditStoreError):
    """The execution ID already exists in the audit store."""


def _strict_json_object(text: str) -> dict[str, Any]:
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key!r}")
            result[key] = value
        return result

    value = json.loads(text, object_pairs_hook=pairs_hook)
    if not isinstance(value, dict):
        raise ValueError("audit record must be a JSON object")
    return value


def _require_string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a bool")
    return value


def _require_string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a JSON array")
    if any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must contain strings only")
    return tuple(value)


def parse_ai_execution_audit_record(text: str) -> AIExecutionAuditRecord:
    """Strictly reconstruct one schema-v1 record from one JSONL line."""

    if not isinstance(text, str):
        raise TypeError("text must be a string.")
    try:
        data = _strict_json_object(text)
        keys = frozenset(data)
        if keys != _EXPECTED_KEYS:
            missing = tuple(sorted(_EXPECTED_KEYS - keys))
            unknown = tuple(sorted(keys - _EXPECTED_KEYS))
            raise ValueError(
                f"audit record fields differ; missing={missing!r}, unknown={unknown!r}"
            )

        selected = data["selected_candidate_id"]
        if selected is not None and not isinstance(selected, str):
            raise ValueError("selected_candidate_id must be a string or null")

        record = AIExecutionAuditRecord(
            schema_version=_require_string(data["schema_version"], "schema_version"),
            execution_id=_require_string(data["execution_id"], "execution_id"),
            occurred_at=_require_string(data["occurred_at"], "occurred_at"),
            workflow_id=_require_string(data["workflow_id"], "workflow_id"),
            executor_id=_require_string(data["executor_id"], "executor_id"),
            case_id=_require_string(data["case_id"], "case_id"),
            evidence_refs=_require_string_tuple(data["evidence_refs"], "evidence_refs"),
            authorized_candidate_ids=_require_string_tuple(
                data["authorized_candidate_ids"], "authorized_candidate_ids"
            ),
            selected_candidate_id=selected,
            abstained=_require_bool(data["abstained"], "abstained"),
            verifier_accepted=_require_bool(
                data["verifier_accepted"], "verifier_accepted"
            ),
            verifier_reason_codes=_require_string_tuple(
                data["verifier_reason_codes"], "verifier_reason_codes"
            ),
            evaluation_classification=EvaluationOutcomeClassification(
                _require_string(
                    data["evaluation_classification"], "evaluation_classification"
                )
            ),
            evaluation_reason_codes=_require_string_tuple(
                data["evaluation_reason_codes"], "evaluation_reason_codes"
            ),
            human_disposition=HumanDisposition(
                _require_string(data["human_disposition"], "human_disposition")
            ),
            persistence_disposition=PersistenceDisposition(
                _require_string(
                    data["persistence_disposition"], "persistence_disposition"
                )
            ),
        )
        if record.schema_version != AI_EXECUTION_AUDIT_SCHEMA_VERSION:
            raise ValueError("unsupported audit schema version")
        record.validate()
        return record
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AIExecutionAuditStoreCorrupt(str(exc)) from exc


def _read_records_from_bytes(raw: bytes) -> tuple[AIExecutionAuditRecord, ...]:
    if len(raw) > MAX_AUDIT_STORE_BYTES:
        raise AIExecutionAuditStoreFull("audit store exceeds its byte limit")
    if not raw:
        return ()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AIExecutionAuditStoreCorrupt("audit store is not valid UTF-8") from exc
    if not text.endswith("\n"):
        raise AIExecutionAuditStoreCorrupt("audit store must end with a newline")

    lines = text.splitlines()
    if len(lines) > MAX_AUDIT_RECORDS:
        raise AIExecutionAuditStoreFull("audit store exceeds its record limit")
    if any(not line for line in lines):
        raise AIExecutionAuditStoreCorrupt("audit store must not contain blank lines")

    records = tuple(parse_ai_execution_audit_record(line) for line in lines)
    execution_ids = tuple(record.execution_id for record in records)
    if len(execution_ids) != len(set(execution_ids)):
        raise AIExecutionAuditStoreCorrupt("audit store contains duplicate execution_id")
    return records


def _read_plain_file(path: Path) -> bytes:
    if path.is_symlink():
        raise AIExecutionAuditStoreCorrupt("audit store path must be a plain file")
    if not path.exists():
        return b""
    if not path.is_file():
        raise AIExecutionAuditStoreCorrupt("audit store path must be a plain file")
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_AUDIT_STORE_BYTES + 1)
    except OSError as exc:
        raise AIExecutionAuditStoreError("audit store could not be read") from exc
    if len(raw) > MAX_AUDIT_STORE_BYTES:
        raise AIExecutionAuditStoreFull("audit store exceeds its byte limit")
    return raw


def _fsync_parent(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@dataclass(frozen=True, slots=True)
class AIExecutionAuditStore:
    """Bounded JSONL store with read validation and atomic whole-file append."""

    path: Path

    def __init__(self, path: str | os.PathLike[str]) -> None:
        object.__setattr__(self, "path", Path(path).absolute())

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.lock")

    def read_all(self) -> tuple[AIExecutionAuditRecord, ...]:
        """Read and strictly validate all currently stored records."""

        return _read_records_from_bytes(_read_plain_file(self.path))

    def append(self, record: AIExecutionAuditRecord) -> None:
        """Atomically append one validated record without collection authority."""

        if not isinstance(record, AIExecutionAuditRecord):
            raise TypeError("record must be an AIExecutionAuditRecord.")
        record.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)

        try:
            lease = PackageImportLock.acquire(self.lock_path)
        except ImportLocked as exc:
            raise AIExecutionAuditStoreLocked("audit store is locked") from exc
        except RecoveryRequired as exc:
            raise AIExecutionAuditStoreError("audit-store lock could not be acquired") from exc

        with lease:
            existing = _read_plain_file(self.path)
            records = _read_records_from_bytes(existing)
            if len(records) >= MAX_AUDIT_RECORDS:
                raise AIExecutionAuditStoreFull("audit store reached its record limit")
            if any(item.execution_id == record.execution_id for item in records):
                raise AIExecutionAuditDuplicateExecution(record.execution_id)

            line = (serialize_ai_execution_audit_record(record) + "\n").encode("ascii")
            prospective = existing + line
            if len(prospective) > MAX_AUDIT_STORE_BYTES:
                raise AIExecutionAuditStoreFull("audit store reached its byte limit")

            temporary = self.path.with_name(
                f".{self.path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}"
            )
            if temporary.exists():
                raise AIExecutionAuditStoreError("audit temporary path already exists")
            try:
                with temporary.open("xb") as handle:
                    handle.write(prospective)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
                _fsync_parent(self.path)
            except OSError as exc:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
                raise AIExecutionAuditStoreError("audit record was not committed") from exc
