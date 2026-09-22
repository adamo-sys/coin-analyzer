"""Durable, execution-only checkpoints for Recognition30 benchmark runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
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
