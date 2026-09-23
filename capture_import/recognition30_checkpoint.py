"""Durable, execution-only checkpoints for Recognition30 benchmark runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping, Sequence


_SCHEMA = "coin-analyzer-recognition30-checkpoint-v1"
_IDENTITY_FILE = "run.json"
_JOURNAL_FILE = "checkpoints.jsonl"
_EXPECTED_CASE_IDS = frozenset(
    f"CA-R30-{number:03d}" for number in range(1, 31)
)
_RECOGNITION_TERMINAL_OUTCOMES = frozenset({"IDENTIFY", "ABSTAIN"})
_PIPELINE_FAILURE = "PIPELINE_FAILURE"


class CheckpointValidationError(ValueError):
    """A checkpoint run is incomplete, corrupt, or incompatible."""


@dataclass(frozen=True, slots=True)
class Recognition30RunIdentity:
    run_id: str
    dataset_version: str
    dataset_fingerprint_scheme: str
    dataset_fingerprint: str
    provider_id: str
    model_id: str
    recognition_semantics: Mapping[str, object]
    execution_metadata: Mapping[str, object]
    parent_run_id: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "run_id",
            "dataset_version",
            "dataset_fingerprint_scheme",
            "dataset_fingerprint",
            "provider_id",
            "model_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise CheckpointValidationError(f"{name} must be non-empty.")
        if not isinstance(self.recognition_semantics, Mapping):
            raise CheckpointValidationError("recognition_semantics must be a mapping.")
        if not isinstance(self.execution_metadata, Mapping):
            raise CheckpointValidationError("execution_metadata must be a mapping.")

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> "Recognition30RunIdentity":
        if not isinstance(value, Mapping):
            raise CheckpointValidationError("malformed run identity.")
        try:
            return cls(
                run_id=value["run_id"],
                dataset_version=value["dataset_version"],
                dataset_fingerprint_scheme=value["dataset_fingerprint_scheme"],
                dataset_fingerprint=value["dataset_fingerprint"],
                provider_id=value["provider_id"],
                model_id=value["model_id"],
                recognition_semantics=value["recognition_semantics"],
                execution_metadata=value["execution_metadata"],
                parent_run_id=value.get("parent_run_id"),
            )
        except (KeyError, TypeError) as exc:
            raise CheckpointValidationError("malformed run identity.") from exc


@dataclass(frozen=True, slots=True)
class Recognition30ReplacementAuthorization:
    """Run-specific approval to substitute named invalid terminal records."""

    original_run_id: str
    replacement_run_id: str
    case_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        for name in ("original_run_id", "replacement_run_id", "reason"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise CheckpointValidationError(f"replacement authorization {name} is invalid.")
        if not self.case_ids or len(set(self.case_ids)) != len(self.case_ids):
            raise CheckpointValidationError("replacement authorization case IDs are invalid.")
        if any(
            not isinstance(case_id, str)
            or not case_id.strip()
            or case_id not in _EXPECTED_CASE_IDS
            for case_id in self.case_ids
        ):
            raise CheckpointValidationError("replacement authorization case IDs are invalid.")


def _durable_write(path: Path, data: bytes) -> None:
    with path.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _load_identity(root: Path) -> Recognition30RunIdentity:
    path = root / _IDENTITY_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointValidationError("malformed run identity.") from exc
    if not isinstance(raw, Mapping) or raw.get("schema") != _SCHEMA:
        raise CheckpointValidationError("malformed run identity.")
    return Recognition30RunIdentity.from_dict(raw.get("identity"))


def _validate_identity_compatibility(
    parent: Recognition30RunIdentity, candidate: Recognition30RunIdentity
) -> None:
    if parent.dataset_version != candidate.dataset_version:
        raise CheckpointValidationError("dataset version is incompatible.")
    if parent.dataset_fingerprint_scheme != candidate.dataset_fingerprint_scheme:
        raise CheckpointValidationError("dataset fingerprint scheme is incompatible.")
    if parent.dataset_fingerprint != candidate.dataset_fingerprint:
        raise CheckpointValidationError("dataset fingerprint is incompatible.")
    if parent.provider_id != candidate.provider_id:
        raise CheckpointValidationError("provider is incompatible.")
    if parent.model_id != candidate.model_id:
        raise CheckpointValidationError("model is incompatible.")
    if dict(parent.recognition_semantics) != dict(candidate.recognition_semantics):
        raise CheckpointValidationError("recognition semantics are incompatible.")


def _validate_reconciliation_identity_compatibility(
    original: Recognition30RunIdentity, replacement: Recognition30RunIdentity
) -> None:
    _validate_identity_compatibility(original, replacement)
    if dict(original.execution_metadata) != dict(replacement.execution_metadata):
        raise CheckpointValidationError("execution metadata is incompatible.")


def _validate_record(value: object, identity: Recognition30RunIdentity) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise CheckpointValidationError("malformed checkpoint record.")
    case_id = value.get("case_id")
    outcome = value.get("terminal_outcome")
    if not isinstance(case_id, str) or not case_id.strip():
        raise CheckpointValidationError("malformed checkpoint record case_id.")
    if not isinstance(outcome, str) or not outcome.strip():
        raise CheckpointValidationError("malformed checkpoint terminal outcome.")
    completion_order = value.get("completion_order")
    if (
        isinstance(completion_order, bool)
        or not isinstance(completion_order, int)
        or completion_order < 1
    ):
        raise CheckpointValidationError("malformed checkpoint completion order.")
    for name in ("execution_metadata", "diagnostics", "provenance"):
        if not isinstance(value.get(name), Mapping):
            raise CheckpointValidationError(f"malformed checkpoint {name}.")
    if value.get("run_identity") != identity.as_dict():
        raise CheckpointValidationError("checkpoint run identity is incompatible.")
    return dict(value)


def load_checkpoint_records(root: Path) -> tuple[dict[str, object], ...]:
    """Load every terminal checkpoint, rejecting malformed or partial JSONL."""

    root = Path(root)
    identity = _load_identity(root)
    journal = root / _JOURNAL_FILE
    if not journal.is_file():
        return ()
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    with journal.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.endswith("\n"):
                raise CheckpointValidationError(
                    f"malformed checkpoint record at line {line_number}."
                )
            try:
                record = _validate_record(json.loads(line), identity)
            except json.JSONDecodeError as exc:
                raise CheckpointValidationError(
                    f"malformed checkpoint record at line {line_number}."
                ) from exc
            case_id = str(record["case_id"])
            if case_id in seen:
                raise CheckpointValidationError("duplicate completed case ID.")
            seen.add(case_id)
            records.append(record)
    return tuple(records)


def _artifact_hashes(root: Path) -> dict[str, str]:
    root = Path(root)
    hashes: dict[str, str] = {}
    for name in (_IDENTITY_FILE, _JOURNAL_FILE):
        path = root / name
        if not path.is_file():
            raise CheckpointValidationError(f"missing checkpoint artifact: {name}.")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _require_complete_case_set(records: Sequence[Mapping[str, object]]) -> None:
    case_ids = [str(record["case_id"]) for record in records]
    if len(set(case_ids)) != len(case_ids):
        raise CheckpointValidationError("duplicate completed case ID.")
    unexpected = set(case_ids) - _EXPECTED_CASE_IDS
    missing = _EXPECTED_CASE_IDS - set(case_ids)
    if unexpected:
        raise CheckpointValidationError("unexpected Recognition30 case ID.")
    if missing:
        raise CheckpointValidationError("missing Recognition30 case ID.")
    if len(case_ids) != 30:
        raise CheckpointValidationError("Recognition30 reconciliation requires exactly 30 cases.")


def _provider_failures(record: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    diagnostics = record.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        raise CheckpointValidationError("malformed checkpoint diagnostics.")
    failures = diagnostics.get("provider_failures", ())
    if not isinstance(failures, Sequence) or isinstance(failures, (str, bytes)):
        raise CheckpointValidationError("malformed provider failure diagnostics.")
    if any(not isinstance(failure, Mapping) for failure in failures):
        raise CheckpointValidationError("malformed provider failure diagnostics.")
    return tuple(failures)


def _is_authorized_provider_failure(record: Mapping[str, object]) -> bool:
    diagnostics = record.get("diagnostics")
    return (
        record.get("terminal_outcome") == _PIPELINE_FAILURE
        and isinstance(diagnostics, Mapping)
        and diagnostics.get("reason") == "provider_observation_failure"
        and bool(_provider_failures(record))
    )


def _validate_replacement_record(record: Mapping[str, object]) -> None:
    if record.get("terminal_outcome") not in _RECOGNITION_TERMINAL_OUTCOMES:
        raise CheckpointValidationError("replacement must be a valid terminal recognition outcome.")
    if _provider_failures(record):
        raise CheckpointValidationError("replacement is infrastructure-invalid.")


def _validate_original_record(
    record: Mapping[str, object], authorized_case_ids: frozenset[str]
) -> None:
    case_id = str(record["case_id"])
    outcome = record.get("terminal_outcome")
    if outcome in _RECOGNITION_TERMINAL_OUTCOMES:
        if _provider_failures(record):
            raise CheckpointValidationError("valid original record is infrastructure-invalid.")
        return
    if outcome != _PIPELINE_FAILURE or not _is_authorized_provider_failure(record):
        raise CheckpointValidationError("original record is not a valid terminal outcome.")
    if case_id not in authorized_case_ids:
        raise CheckpointValidationError("infrastructure-invalid original is not authorized for replacement.")


def reconcile_checkpoint_runs(
    original_root: Path,
    replacement_root: Path,
    authorization: Recognition30ReplacementAuthorization,
) -> dict[str, object]:
    """Return an immutable, deterministic effective 30-case reconciliation."""

    if not isinstance(authorization, Recognition30ReplacementAuthorization):
        raise TypeError("authorization must be Recognition30ReplacementAuthorization.")
    original_root = Path(original_root)
    replacement_root = Path(replacement_root)
    original_identity = _load_identity(original_root)
    replacement_identity = _load_identity(replacement_root)
    if original_identity.run_id != authorization.original_run_id:
        raise CheckpointValidationError("original run ID is not authorized.")
    if replacement_identity.run_id != authorization.replacement_run_id:
        raise CheckpointValidationError("replacement run ID is not authorized.")
    _validate_reconciliation_identity_compatibility(original_identity, replacement_identity)

    original_records = load_checkpoint_records(original_root)
    replacement_records = load_checkpoint_records(replacement_root)
    _require_complete_case_set(original_records)
    authorized_case_ids = frozenset(authorization.case_ids)
    replacement_case_ids = [str(record["case_id"]) for record in replacement_records]
    if len(set(replacement_case_ids)) != len(replacement_case_ids):
        raise CheckpointValidationError("duplicate replacement case ID.")
    if set(replacement_case_ids) != authorized_case_ids:
        raise CheckpointValidationError("replacement cases do not exactly match authorization.")

    originals_by_case_id = {
        str(record["case_id"]): record for record in original_records
    }
    replacements_by_case_id = {
        str(record["case_id"]): record for record in replacement_records
    }
    for original in originals_by_case_id.values():
        _validate_original_record(original, authorized_case_ids)
    effective_records: list[dict[str, object]] = []
    for case_id in sorted(_EXPECTED_CASE_IDS):
        original = originals_by_case_id[case_id]
        replacement = replacements_by_case_id.get(case_id)
        if replacement is not None:
            if not _is_authorized_provider_failure(original):
                raise CheckpointValidationError(
                    "only infrastructure-invalid provider failures may be replaced."
                )
            _validate_replacement_record(replacement)
            effective = dict(replacement)
        else:
            effective = dict(original)
        effective["provenance"] = {
            "reconciliation": "recognition30-checkpoint-reconciliation-v1",
            "original_record": original,
            "replacement_record": replacement,
            "replacement_authorization_reason": (
                authorization.reason if replacement is not None else None
            ),
        }
        effective_records.append(effective)

    effective_case_ids = [str(record["case_id"]) for record in effective_records]
    if len(set(effective_case_ids)) != 30 or set(effective_case_ids) != _EXPECTED_CASE_IDS:
        raise CheckpointValidationError("reconciliation requires exactly 30 unique effective cases.")
    terminal_outcome_counts = {
        outcome: sum(
            record["terminal_outcome"] == outcome for record in effective_records
        )
        for outcome in ("IDENTIFY", "ABSTAIN", _PIPELINE_FAILURE)
    }
    return {
        "schema": "coin-analyzer-recognition30-checkpoint-reconciliation-v1",
        "dataset_version": original_identity.dataset_version,
        "dataset_fingerprint_scheme": original_identity.dataset_fingerprint_scheme,
        "dataset_fingerprint": original_identity.dataset_fingerprint,
        "original_run_id": original_identity.run_id,
        "replacement_run_id": replacement_identity.run_id,
        "input_artifact_hashes": {
            "original": _artifact_hashes(original_root),
            "replacement": _artifact_hashes(replacement_root),
        },
        "replacement_case_ids": list(authorization.case_ids),
        "effective_case_count": len(effective_records),
        "terminal_outcome_counts": terminal_outcome_counts,
        "correctness_breakdown": "unavailable",
        "effective_records": effective_records,
    }


class CheckpointJournal:
    """Append-only terminal-case journal with one fsync boundary per record."""

    def __init__(self, root: Path, identity: Recognition30RunIdentity) -> None:
        self.root = Path(root)
        self.identity = identity
        if self.root.exists():
            if any(self.root.iterdir()):
                raise CheckpointValidationError("checkpoint run directory already exists.")
        else:
            self.root.mkdir(parents=True)
        _durable_write(
            self.root / _IDENTITY_FILE,
            (
                json.dumps(
                    {
                        "schema": _SCHEMA,
                        "identity": identity.as_dict(),
                        "parent_run_id": identity.parent_run_id,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8"),
        )
        self._completed = {
            str(record["case_id"]) for record in load_checkpoint_records(self.root)
        }

    def append_terminal(self, record: Mapping[str, object]) -> None:
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise CheckpointValidationError("malformed checkpoint record case_id.")
        if case_id in self._completed:
            raise CheckpointValidationError("duplicate completed case ID.")
        durable_record = dict(record)
        durable_record["schema"] = _SCHEMA
        durable_record["run_identity"] = self.identity.as_dict()
        _validate_record(durable_record, self.identity)
        with (self.root / _JOURNAL_FILE).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(durable_record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._completed.add(case_id)


def create_continuation(
    parent_root: Path, new_root: Path, identity: Recognition30RunIdentity
) -> tuple[CheckpointJournal, frozenset[str]]:
    """Create a new immutable segment after validating terminal parent records."""

    parent_root = Path(parent_root)
    new_root = Path(new_root)
    if new_root.exists():
        raise CheckpointValidationError("continuation run directory already exists.")
    parent_identity = _load_identity(parent_root)
    _validate_identity_compatibility(parent_identity, identity)
    parent_records = load_checkpoint_records(parent_root)
    child_identity = Recognition30RunIdentity(
        run_id=identity.run_id,
        dataset_version=identity.dataset_version,
        dataset_fingerprint_scheme=identity.dataset_fingerprint_scheme,
        dataset_fingerprint=identity.dataset_fingerprint,
        provider_id=identity.provider_id,
        model_id=identity.model_id,
        recognition_semantics=dict(identity.recognition_semantics),
        execution_metadata=dict(identity.execution_metadata),
        parent_run_id=parent_identity.run_id,
    )
    return CheckpointJournal(new_root, child_identity), frozenset(
        str(record["case_id"]) for record in parent_records
    )


def join_checkpoint_runs(run_roots: Sequence[Path]) -> dict[str, object]:
    """Validate complete Recognition30 segments and return their logical union."""

    if not run_roots:
        raise CheckpointValidationError("at least one checkpoint segment is required.")
    identities = [_load_identity(Path(root)) for root in run_roots]
    for identity in identities[1:]:
        _validate_identity_compatibility(identities[0], identity)
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for root in run_roots:
        for record in load_checkpoint_records(Path(root)):
            case_id = str(record["case_id"])
            if case_id in seen:
                raise CheckpointValidationError("duplicate completed case ID.")
            seen.add(case_id)
            records.append(record)
    unexpected = seen - _EXPECTED_CASE_IDS
    missing = _EXPECTED_CASE_IDS - seen
    if unexpected:
        raise CheckpointValidationError("unexpected Recognition30 case ID.")
    if missing:
        raise CheckpointValidationError("missing Recognition30 case ID.")
    if len(records) != 30:
        raise CheckpointValidationError("Recognition30 join requires exactly 30 cases.")
    records.sort(key=lambda record: str(record["case_id"]))
    return {
        "schema": _SCHEMA,
        "dataset_version": identities[0].dataset_version,
        "dataset_fingerprint_scheme": identities[0].dataset_fingerprint_scheme,
        "dataset_fingerprint": identities[0].dataset_fingerprint,
        "recognition_semantics": dict(identities[0].recognition_semantics),
        "segments": [identity.run_id for identity in identities],
        "records": records,
    }
