"""Immutable capture-import journal schema.

The journal contract in this module is intentionally persistence-agnostic.  A
later sprint may supply atomic storage and transition coordination.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .audit import AuditSession
from .enums import ErrorCategory, HISTORY_PHASES, ImportPhase
from .limits import (
    JOURNAL_SCHEMA_VERSION,
    MAX_COINS_PER_PACKAGE,
    MAX_PACKAGE_SIZE,
    MISSING_COLLECTION_SENTINEL,
    SUPPORTED_SCHEMA_VERSION,
)
from .models import (
    _require_boolean,
    _enum_value,
    _require_fields,
    _require_integer,
    _require_object,
    _require_optional_string,
    _require_string,
    _require_unique_strings,
    _validate_basename,
    _validate_relative_path,
    _validate_sha256,
    _validate_timestamp,
    _validate_uuid,
)

_JOURNAL_FIELDS = frozenset(
    {
        "journal_schema_version",
        "import_id",
        "random_ownership_token",
        "phase",
        "created_at",
        "updated_at",
        "package_sha256",
        "package_version",
        "package_basename",
        "snapshot_relative_path",
        "snapshot_byte_length",
        "collection_baseline_sha256_or_sentinel",
        "collection_baseline_byte_length",
        "selected_source_coin_ids",
        "desktop_item_ids",
        "import_root_relative_path",
        "created_relative_paths",
        "expected_relative_paths",
        "committed_collection_item_ids",
        "proposed_count",
        "imported_count",
        "skipped_count",
        "error_category",
        "recovery_attempt_count",
        "cleanup_pending",
        "audit_finalization_pending",
        "terminal_audit",
    }
)

_SNAPSHOT_REQUIRED_PHASES = frozenset(
    {
        ImportPhase.PREPARED,
        ImportPhase.COPYING_IMAGES,
        ImportPhase.FILES_READY,
        ImportPhase.COMMITTING_COLLECTION,
        ImportPhase.COLLECTION_COMMITTED,
        ImportPhase.ROLLING_BACK,
    }
)

_UNCOMMITTED_PHASES = frozenset(
    {
        ImportPhase.PREPARED,
        ImportPhase.COPYING_IMAGES,
        ImportPhase.FILES_READY,
        ImportPhase.ROLLING_BACK,
        ImportPhase.ROLLED_BACK,
        ImportPhase.CANCELLED,
    }
)

_FILES_COMPLETE_PHASES = frozenset(
    {
        ImportPhase.FILES_READY,
        ImportPhase.COMMITTING_COLLECTION,
        ImportPhase.COLLECTION_COMMITTED,
        ImportPhase.SUCCEEDED,
    }
)

_NORMAL_PROGRESS_PHASES = frozenset(
    {
        ImportPhase.PREPARED,
        ImportPhase.COPYING_IMAGES,
        ImportPhase.FILES_READY,
        ImportPhase.COMMITTING_COLLECTION,
        ImportPhase.COLLECTION_COMMITTED,
        ImportPhase.SUCCEEDED,
    }
)

_IMMUTABLE_IDENTITY_FIELDS = (
    "import_id",
    "random_ownership_token",
    "created_at",
    "package_sha256",
    "package_version",
    "package_basename",
    "snapshot_byte_length",
    "collection_baseline_sha256_or_sentinel",
    "collection_baseline_byte_length",
    "selected_source_coin_ids",
    "desktop_item_ids",
    "import_root_relative_path",
    "expected_relative_paths",
    "proposed_count",
    "skipped_count",
)


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array.")
    result = tuple(value)
    _require_unique_strings(result, field_name)
    return result


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """One complete, versioned durable import-state record."""

    journal_schema_version: str
    import_id: str
    random_ownership_token: str
    phase: ImportPhase
    created_at: str
    updated_at: str
    package_sha256: str
    package_version: str
    package_basename: str
    snapshot_relative_path: str | None
    snapshot_byte_length: int
    collection_baseline_sha256_or_sentinel: str
    collection_baseline_byte_length: int
    selected_source_coin_ids: tuple[str, ...]
    desktop_item_ids: tuple[str, ...]
    import_root_relative_path: str
    created_relative_paths: tuple[str, ...]
    expected_relative_paths: tuple[str, ...]
    committed_collection_item_ids: tuple[str, ...]
    proposed_count: int
    imported_count: int
    skipped_count: int
    error_category: ErrorCategory | None
    recovery_attempt_count: int
    cleanup_pending: bool
    audit_finalization_pending: bool
    terminal_audit: AuditSession | None

    def validate(self) -> None:
        """Validate the complete journal schema and cross-field invariants."""

        if self.journal_schema_version != JOURNAL_SCHEMA_VERSION:
            raise ValueError("journal_schema_version is not supported.")
        _validate_uuid(self.import_id, "import_id")
        _validate_uuid(self.random_ownership_token, "random_ownership_token")
        if not isinstance(self.phase, ImportPhase):
            raise ValueError("phase must be an ImportPhase.")
        _validate_timestamp(self.created_at, "created_at")
        _validate_timestamp(self.updated_at, "updated_at")
        _validate_sha256(self.package_sha256, "package_sha256")
        if self.package_version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError("package_version is not supported.")
        basename = _validate_basename(self.package_basename, "package_basename")
        if not basename.lower().endswith(".ca-package"):
            raise ValueError("package_basename must end with .ca-package.")

        if self.snapshot_relative_path is not None:
            _validate_relative_path(
                self.snapshot_relative_path, "snapshot_relative_path"
            )
        if self.phase in _SNAPSHOT_REQUIRED_PHASES and self.snapshot_relative_path is None:
            raise ValueError("snapshot_relative_path is required in the active phase.")
        if self.phase in HISTORY_PHASES and self.snapshot_relative_path is not None:
            raise ValueError("Completed audit history must not retain a snapshot path.")
        _require_integer(
            self.snapshot_byte_length,
            "snapshot_byte_length",
            minimum=1,
            maximum=MAX_PACKAGE_SIZE,
        )

        if (
            self.collection_baseline_sha256_or_sentinel
            == MISSING_COLLECTION_SENTINEL
        ):
            if self.collection_baseline_byte_length != 0:
                raise ValueError("A missing collection baseline must have zero bytes.")
        else:
            _validate_sha256(
                self.collection_baseline_sha256_or_sentinel,
                "collection_baseline_sha256_or_sentinel",
            )
        _require_integer(
            self.collection_baseline_byte_length,
            "collection_baseline_byte_length",
        )

        _require_unique_strings(
            self.selected_source_coin_ids, "selected_source_coin_ids"
        )
        _require_unique_strings(self.desktop_item_ids, "desktop_item_ids")
        for desktop_id in self.desktop_item_ids:
            _validate_uuid(desktop_id, "desktop_item_ids")
        if len(self.selected_source_coin_ids) != len(self.desktop_item_ids):
            raise ValueError("Each selected source coin requires one desktop item ID.")

        _validate_relative_path(
            self.import_root_relative_path, "import_root_relative_path"
        )
        _require_unique_strings(self.created_relative_paths, "created_relative_paths")
        _require_unique_strings(
            self.expected_relative_paths, "expected_relative_paths"
        )
        if not self.expected_relative_paths:
            raise ValueError("expected_relative_paths must not be empty.")
        for path in self.created_relative_paths:
            _validate_relative_path(path, "created_relative_paths")
        for path in self.expected_relative_paths:
            _validate_relative_path(path, "expected_relative_paths")
        if not set(self.created_relative_paths).issubset(self.expected_relative_paths):
            raise ValueError("created_relative_paths must be expected paths.")

        _require_unique_strings(
            self.committed_collection_item_ids, "committed_collection_item_ids"
        )
        for desktop_id in self.committed_collection_item_ids:
            _validate_uuid(desktop_id, "committed_collection_item_ids")
        if self.committed_collection_item_ids not in ((), self.desktop_item_ids):
            raise ValueError(
                "Committed item IDs must be empty or the complete reserved ID sequence."
            )

        proposed = _require_integer(
            self.proposed_count,
            "proposed_count",
            maximum=MAX_COINS_PER_PACKAGE,
        )
        imported = _require_integer(
            self.imported_count,
            "imported_count",
            maximum=MAX_COINS_PER_PACKAGE,
        )
        skipped = _require_integer(
            self.skipped_count,
            "skipped_count",
            maximum=MAX_COINS_PER_PACKAGE,
        )
        if proposed < 1:
            raise ValueError("proposed_count must be positive.")
        if skipped != proposed - len(self.selected_source_coin_ids):
            raise ValueError(
                "skipped_count must account for every source coin not selected."
            )
        if imported != len(self.committed_collection_item_ids):
            raise ValueError("imported_count must equal committed item ID count.")

        if self.error_category is not None and not isinstance(
            self.error_category, ErrorCategory
        ):
            raise ValueError("error_category must be an ErrorCategory or null.")
        _require_integer(self.recovery_attempt_count, "recovery_attempt_count")
        _require_boolean(self.cleanup_pending, "cleanup_pending")
        _require_boolean(
            self.audit_finalization_pending, "audit_finalization_pending"
        )

        if self.phase in _NORMAL_PROGRESS_PHASES and self.error_category is not None:
            raise ValueError("Normal progress phases must not contain an error category.")
        if self.phase in {
            ImportPhase.RECOVERY_REQUIRED,
            ImportPhase.ROLLBACK_FAILED,
        } and self.error_category is None:
            raise ValueError("Recovery failure phases require an error category.")
        if self.phase is not ImportPhase.SUCCEEDED and self.cleanup_pending:
            raise ValueError("cleanup_pending is valid only in SUCCEEDED.")

        created_complete = self.created_relative_paths == self.expected_relative_paths
        committed_complete = self.committed_collection_item_ids == self.desktop_item_ids
        if self.phase is ImportPhase.PREPARED and self.created_relative_paths:
            raise ValueError("PREPARED cannot contain created paths.")
        if self.phase in _FILES_COMPLETE_PHASES and not created_complete:
            raise ValueError(f"{self.phase.value} requires all expected paths.")
        if self.phase in {ImportPhase.ROLLED_BACK, ImportPhase.CANCELLED} and (
            self.created_relative_paths
        ):
            raise ValueError(f"{self.phase.value} cannot retain created paths.")
        if self.phase in _UNCOMMITTED_PHASES and self.committed_collection_item_ids:
            raise ValueError(f"{self.phase.value} cannot contain committed item IDs.")
        if self.phase in {
            ImportPhase.COLLECTION_COMMITTED,
            ImportPhase.SUCCEEDED,
        } and not committed_complete:
            raise ValueError(f"{self.phase.value} requires all committed item IDs.")
        if self.phase is ImportPhase.COLLECTION_COMMITTED:
            if not self.audit_finalization_pending:
                raise ValueError(
                    "COLLECTION_COMMITTED requires audit_finalization_pending."
                )
        elif self.phase not in {
            ImportPhase.RECOVERY_REQUIRED,
            ImportPhase.ROLLBACK_FAILED,
        } and self.audit_finalization_pending:
            raise ValueError(
                f"{self.phase.value} cannot have audit_finalization_pending."
            )
        if self.audit_finalization_pending and not committed_complete:
            raise ValueError(
                "audit_finalization_pending requires complete committed item IDs."
            )
        if self.phase is ImportPhase.RECOVERY_REQUIRED:
            has_committed_records = bool(self.committed_collection_item_ids)
            if has_committed_records and (
                not created_complete or not self.audit_finalization_pending
            ):
                raise ValueError(
                    "Committed recovery requires complete files and pending audit finalization."
                )
            if not has_committed_records and self.audit_finalization_pending:
                raise ValueError(
                    "Uncommitted recovery cannot await audit finalization."
                )

        if self.phase in HISTORY_PHASES:
            if self.terminal_audit is None:
                raise ValueError("Completed audit history requires terminal_audit.")
            if not isinstance(self.terminal_audit, AuditSession):
                raise ValueError("terminal_audit must be an AuditSession or null.")
            self.terminal_audit.validate()
            if self.terminal_audit.import_id != self.import_id:
                raise ValueError("terminal_audit import_id does not match the journal.")
            if self.terminal_audit.phase is not self.phase:
                raise ValueError("terminal_audit phase does not match the journal.")
            if (
                self.terminal_audit.proposed_count != proposed
                or self.terminal_audit.imported_count != imported
                or self.terminal_audit.skipped_count != skipped
            ):
                raise ValueError("terminal_audit counts do not match the journal.")
            if self.phase is ImportPhase.SUCCEEDED and self.audit_finalization_pending:
                raise ValueError("Succeeded journals cannot await audit finalization.")
        elif self.terminal_audit is not None:
            raise ValueError("Non-history journal phases require terminal_audit null.")
    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "journal_schema_version": self.journal_schema_version,
            "import_id": self.import_id,
            "random_ownership_token": self.random_ownership_token,
            "phase": self.phase.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "package_sha256": self.package_sha256,
            "package_version": self.package_version,
            "package_basename": self.package_basename,
            "snapshot_relative_path": self.snapshot_relative_path,
            "snapshot_byte_length": self.snapshot_byte_length,
            "collection_baseline_sha256_or_sentinel": (
                self.collection_baseline_sha256_or_sentinel
            ),
            "collection_baseline_byte_length": self.collection_baseline_byte_length,
            "selected_source_coin_ids": list(self.selected_source_coin_ids),
            "desktop_item_ids": list(self.desktop_item_ids),
            "import_root_relative_path": self.import_root_relative_path,
            "created_relative_paths": list(self.created_relative_paths),
            "expected_relative_paths": list(self.expected_relative_paths),
            "committed_collection_item_ids": list(
                self.committed_collection_item_ids
            ),
            "proposed_count": self.proposed_count,
            "imported_count": self.imported_count,
            "skipped_count": self.skipped_count,
            "error_category": (
                None if self.error_category is None else self.error_category.value
            ),
            "recovery_attempt_count": self.recovery_attempt_count,
            "cleanup_pending": self.cleanup_pending,
            "audit_finalization_pending": self.audit_finalization_pending,
            "terminal_audit": (
                None if self.terminal_audit is None else self.terminal_audit.to_dict()
            ),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "JournalEntry":
        data = _require_object(value, "JournalEntry")
        _require_fields(data, _JOURNAL_FIELDS, "JournalEntry", allow_extra=False)
        snapshot_relative_path = _require_optional_string(
            data["snapshot_relative_path"], "snapshot_relative_path"
        )
        error_category = (
            None
            if data["error_category"] is None
            else _enum_value(ErrorCategory, data["error_category"], "error_category")
        )
        terminal_audit = (
            None
            if data["terminal_audit"] is None
            else AuditSession.from_dict(data["terminal_audit"])
        )
        result = cls(
            journal_schema_version=_require_string(
                data["journal_schema_version"], "journal_schema_version"
            ),
            import_id=_require_string(data["import_id"], "import_id"),
            random_ownership_token=_require_string(
                data["random_ownership_token"], "random_ownership_token"
            ),
            phase=_enum_value(ImportPhase, data["phase"], "phase"),
            created_at=_require_string(data["created_at"], "created_at"),
            updated_at=_require_string(data["updated_at"], "updated_at"),
            package_sha256=_require_string(data["package_sha256"], "package_sha256"),
            package_version=_require_string(data["package_version"], "package_version"),
            package_basename=_require_string(data["package_basename"], "package_basename"),
            snapshot_relative_path=snapshot_relative_path,
            snapshot_byte_length=_require_integer(
                data["snapshot_byte_length"], "snapshot_byte_length"
            ),
            collection_baseline_sha256_or_sentinel=_require_string(
                data["collection_baseline_sha256_or_sentinel"],
                "collection_baseline_sha256_or_sentinel",
            ),
            collection_baseline_byte_length=_require_integer(
                data["collection_baseline_byte_length"],
                "collection_baseline_byte_length",
            ),
            selected_source_coin_ids=_string_tuple(
                data["selected_source_coin_ids"], "selected_source_coin_ids"
            ),
            desktop_item_ids=_string_tuple(
                data["desktop_item_ids"], "desktop_item_ids"
            ),
            import_root_relative_path=_require_string(
                data["import_root_relative_path"], "import_root_relative_path"
            ),
            created_relative_paths=_string_tuple(
                data["created_relative_paths"], "created_relative_paths"
            ),
            expected_relative_paths=_string_tuple(
                data["expected_relative_paths"], "expected_relative_paths"
            ),
            committed_collection_item_ids=_string_tuple(
                data["committed_collection_item_ids"],
                "committed_collection_item_ids",
            ),
            proposed_count=_require_integer(data["proposed_count"], "proposed_count"),
            imported_count=_require_integer(data["imported_count"], "imported_count"),
            skipped_count=_require_integer(data["skipped_count"], "skipped_count"),
            error_category=error_category,
            recovery_attempt_count=_require_integer(
                data["recovery_attempt_count"], "recovery_attempt_count"
            ),
            cleanup_pending=_require_boolean(
                data["cleanup_pending"], "cleanup_pending"
            ),
            audit_finalization_pending=_require_boolean(
                data["audit_finalization_pending"], "audit_finalization_pending"
            ),
            terminal_audit=terminal_audit,
        )
        result.validate()
        return result


def validate_same_phase_update(previous: JournalEntry, current: JournalEntry) -> None:
    """Validate documented monotonic progress within one durable phase."""

    if not isinstance(previous, JournalEntry) or not isinstance(current, JournalEntry):
        raise ValueError("Journal updates require JournalEntry values.")
    previous.validate()
    current.validate()
    if previous.phase is not current.phase:
        raise ValueError("Same-phase validation requires matching phases.")
    for field_name in _IMMUTABLE_IDENTITY_FIELDS:
        if getattr(previous, field_name) != getattr(current, field_name):
            raise ValueError(f"Immutable journal field changed: {field_name}.")
    if previous.terminal_audit != current.terminal_audit:
        raise ValueError("terminal_audit is immutable once populated.")

    changed = {
        field_name
        for field_name in JournalEntry.__dataclass_fields__
        if getattr(previous, field_name) != getattr(current, field_name)
    }
    allowed = {"updated_at"}
    if current.phase is ImportPhase.COPYING_IMAGES:
        allowed.add("created_relative_paths")
        if not set(previous.created_relative_paths).issubset(
            current.created_relative_paths
        ):
            raise ValueError("COPYING_IMAGES cannot forget created paths.")
    elif current.phase is ImportPhase.COMMITTING_COLLECTION:
        allowed.update({"committed_collection_item_ids", "imported_count"})
        if previous.committed_collection_item_ids and (
            current.committed_collection_item_ids
            != previous.committed_collection_item_ids
        ):
            raise ValueError(
                "COMMITTING_COLLECTION cannot forget committed item IDs."
            )
    elif current.phase in {
        ImportPhase.RECOVERY_REQUIRED,
        ImportPhase.ROLLBACK_FAILED,
    }:
        allowed.update(
            {
                "recovery_attempt_count",
                "error_category",
                "created_relative_paths",
                "committed_collection_item_ids",
                "imported_count",
                "audit_finalization_pending",
            }
        )
        if current.recovery_attempt_count < previous.recovery_attempt_count:
            raise ValueError("recovery_attempt_count cannot decrease.")
    elif current.phase is ImportPhase.SUCCEEDED:
        allowed.add("cleanup_pending")
        if "cleanup_pending" in changed and (
            not previous.cleanup_pending or current.cleanup_pending
        ):
            raise ValueError("SUCCEEDED may only clear cleanup_pending.")
    unexpected = changed.difference(allowed)
    if unexpected:
        raise ValueError(
            "Same-phase update changed prohibited fields: "
            + ", ".join(sorted(unexpected))
            + "."
        )
