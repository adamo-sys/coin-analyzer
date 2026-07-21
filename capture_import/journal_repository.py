"""Durable, transition-checked package-import journal persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Callable
from uuid import uuid4

from atomic_json import write_json_atomically

from ._filesystem import (
    ensure_plain_directory,
    exchange_paths_in_directory,
    handle_object_identity,
    handle_matches_path,
    open_plain_directory_handle,
    open_existing_binary_for_delete,
    open_exclusive_binary,
    path_object_identity,
    replace_open_file_in_directory,
    require_plain_directory,
    require_plain_regular_file,
)
from ._json import canonical_json_bytes, parse_bounded_json_object
from .enums import ImportPhase
from .errors import JournalCorrupt, RecoveryRequired
from .journal import JournalEntry, validate_same_phase_update
from .limits import MAX_JSON_BYTES

WriteJson = Callable[..., None]

_TRANSITIONS = {
    ImportPhase.PREPARED: {
        ImportPhase.COPYING_IMAGES,
        ImportPhase.ROLLING_BACK,
        ImportPhase.RECOVERY_REQUIRED,
        ImportPhase.ROLLBACK_FAILED,
    },
    ImportPhase.COPYING_IMAGES: {
        ImportPhase.FILES_READY,
        ImportPhase.ROLLING_BACK,
        ImportPhase.RECOVERY_REQUIRED,
        ImportPhase.ROLLBACK_FAILED,
    },
    ImportPhase.FILES_READY: {
        ImportPhase.COMMITTING_COLLECTION,
        ImportPhase.ROLLING_BACK,
        ImportPhase.RECOVERY_REQUIRED,
        ImportPhase.ROLLBACK_FAILED,
    },
    ImportPhase.COMMITTING_COLLECTION: {
        ImportPhase.COLLECTION_COMMITTED,
        ImportPhase.ROLLING_BACK,
        ImportPhase.RECOVERY_REQUIRED,
        ImportPhase.ROLLBACK_FAILED,
    },
    ImportPhase.COLLECTION_COMMITTED: {
        ImportPhase.SUCCEEDED,
        ImportPhase.RECOVERY_REQUIRED,
    },
    ImportPhase.ROLLING_BACK: {
        ImportPhase.ROLLED_BACK,
        ImportPhase.CANCELLED,
        ImportPhase.RECOVERY_REQUIRED,
        ImportPhase.ROLLBACK_FAILED,
    },
    ImportPhase.RECOVERY_REQUIRED: {
        ImportPhase.ROLLING_BACK,
        ImportPhase.COLLECTION_COMMITTED,
    },
    ImportPhase.ROLLBACK_FAILED: {ImportPhase.ROLLING_BACK},
    ImportPhase.SUCCEEDED: set(),
    ImportPhase.ROLLED_BACK: set(),
    ImportPhase.CANCELLED: set(),
}

_IMMUTABLE_FIELDS = (
    "journal_schema_version",
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


class PackageImportJournalRepository:
    """Persist one strict journal per import without silent overwrite."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        atomic_writer: WriteJson = write_json_atomically,
    ) -> None:
        self._root = Path(root).absolute()
        self._atomic_writer = atomic_writer

    @property
    def root(self) -> Path:
        return self._root

    def create(self, entry: JournalEntry) -> JournalEntry:
        """Exclusively create a PREPARED journal and flush it durably."""

        entry.validate()
        if entry.phase is not ImportPhase.PREPARED:
            raise ValueError("A new journal must begin in PREPARED.")
        path = self._path(entry.import_id)
        handle = None
        try:
            ensure_plain_directory(self._root)
            root_identity = self._directory_identity()
            handle = open_exclusive_binary(path)
            payload = canonical_json_bytes(entry.to_dict())
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            if (
                self._directory_identity() != root_identity
                or not handle_matches_path(handle, path)
            ):
                raise RecoveryRequired()
            handle.seek(0)
            if handle.read(len(payload) + 1) != payload:
                raise RecoveryRequired()
            handle.close()
            return entry
        except FileExistsError as error:
            if handle is not None and not handle.closed:
                handle.close()
            raise JournalCorrupt(error) from error
        except (OSError, ValueError) as error:
            if handle is not None and not handle.closed:
                handle.close()
            raise RecoveryRequired(error) from error

    def load(self, import_id: str) -> JournalEntry:
        """Load one bounded regular journal with strict schema validation."""

        try:
            require_plain_directory(self._root)
            with open_plain_directory_handle(self._root) as directory:
                result, _identity = self._load_bound(import_id, directory)
                return result
        except JournalCorrupt:
            raise
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise JournalCorrupt(error) from error

    def update(self, previous: JournalEntry, current: JournalEntry) -> JournalEntry:
        """Atomically replace a journal after transition and identity checks."""

        previous.validate()
        current.validate()
        if previous.import_id != current.import_id:
            raise JournalCorrupt()
        _validate_update(previous, current)
        path = self._path(previous.import_id)
        try:
            require_plain_directory(self._root)
            with open_plain_directory_handle(self._root) as directory:
                handle, on_disk, before_identity = self._open_bound(
                    previous.import_id, directory
                )
                try:
                    if on_disk != previous:
                        raise JournalCorrupt()
                    self._exercise_injected_writer(current, directory)
                    if not directory.verify_path():
                        raise RecoveryRequired()
                    if (
                        self._bound_entry_identity(directory, path.name)
                        != before_identity
                        or handle_object_identity(handle) != before_identity
                    ):
                        raise RecoveryRequired()
                    self._write_bound(
                        directory,
                        path.name,
                        current,
                        expected_destination_identity=before_identity,
                    )
                    if not directory.verify_path():
                        raise RecoveryRequired()
                    on_disk, after_identity = self._load_bound(
                        current.import_id, directory
                    )
                    if (
                        after_identity == before_identity
                        or on_disk != current
                        or handle_object_identity(handle) != before_identity
                    ):
                        raise RecoveryRequired()
                    return current
                finally:
                    handle.close()
        except (JournalCorrupt, RecoveryRequired):
            raise
        except (OSError, ValueError) as error:
            raise RecoveryRequired(error) from error

    def list_entries(self) -> tuple[JournalEntry, ...]:
        """Return deterministic validated journal history; fail on ambiguity."""

        if not self._root.exists():
            return ()
        try:
            require_plain_directory(self._root)
            with open_plain_directory_handle(self._root) as directory:
                names = (
                    os.listdir(directory.descriptor)
                    if directory.descriptor is not None
                    else os.listdir(self._root)
                )
                names = tuple(sorted(names))
                if not directory.verify_path():
                    raise JournalCorrupt()
                expected_identities: dict[str, tuple[int, int]] = {}
                for name in names:
                    if directory.descriptor is not None:
                        info = os.stat(
                            name,
                            dir_fd=directory.descriptor,
                            follow_symlinks=False,
                        )
                        expected_identities[name] = (info.st_dev, info.st_ino)
                    else:
                        expected_identities[name] = path_object_identity(
                            self._root / name
                        )
                entries: list[JournalEntry] = []
                for name in names:
                    path = Path(name)
                    if path.name != name or path.suffix != ".json":
                        raise JournalCorrupt()
                    entry, identity = self._load_bound(path.stem, directory)
                    if identity != expected_identities[name]:
                        raise JournalCorrupt()
                    entries.append(entry)
                if not directory.verify_path():
                    raise JournalCorrupt()
                return tuple(entries)
        except (JournalCorrupt,):
            raise
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise JournalCorrupt(error) from error

    def _load_bound(self, import_id: str, directory) -> tuple[JournalEntry, tuple[int, int]]:
        handle, result, identity = self._open_bound(import_id, directory)
        handle.close()
        return result, identity

    def _open_bound(self, import_id: str, directory):
        path = self._path(import_id)
        if not directory.verify_path():
            raise JournalCorrupt()
        handle = None
        try:
            if directory.descriptor is not None:
                flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(
                    os, "O_NOFOLLOW", 0
                )
                descriptor = os.open(path.name, flags, dir_fd=directory.descriptor)
                handle = os.fdopen(descriptor, "r+b", buffering=0)
            else:
                handle = open_existing_binary_for_delete(path)
            identity = handle_object_identity(handle)
            info = os.fstat(handle.fileno())
            if info.st_size > MAX_JSON_BYTES:
                raise JournalCorrupt()
            raw = handle.read(MAX_JSON_BYTES + 1)
            if len(raw) != info.st_size or not directory.verify_path():
                raise JournalCorrupt()
            if directory.descriptor is None and not handle_matches_path(handle, path):
                raise JournalCorrupt()
            result = JournalEntry.from_dict(
                parse_bounded_json_object(raw, "package import journal")
            )
            if result.import_id != import_id:
                raise JournalCorrupt()
            return handle, result, identity
        except Exception:
            if handle is not None:
                handle.close()
            raise

    def _exercise_injected_writer(self, current: JournalEntry, directory) -> None:
        if self._atomic_writer is write_json_atomically:
            return
        with tempfile.TemporaryDirectory(prefix="coin-analyzer-journal-") as root:
            probe = Path(root) / "journal.json"
            self._atomic_writer(
                str(probe), current.to_dict(), indent=2, ensure_ascii=False
            )
            if not directory.verify_path():
                raise RecoveryRequired()
            parsed = JournalEntry.from_dict(
                parse_bounded_json_object(
                    probe.read_bytes(), "package import journal"
                )
            )
            if parsed != current:
                raise RecoveryRequired()

    def _bound_entry_identity(self, directory, filename: str) -> tuple[int, int]:
        if directory.descriptor is not None:
            info = os.stat(
                filename,
                dir_fd=directory.descriptor,
                follow_symlinks=False,
            )
            return info.st_dev, info.st_ino
        return path_object_identity(self._root / filename)

    def _write_bound(
        self,
        directory,
        filename: str,
        current: JournalEntry,
        *,
        expected_destination_identity: tuple[int, int],
    ) -> None:
        payload = canonical_json_bytes(current.to_dict())
        temporary_name = f".{filename}.{uuid4().hex}.tmp"
        temporary_path = self._root / temporary_name
        handle = None
        cleanup_identities: set[tuple[int, int]] = set()
        try:
            if directory.descriptor is not None:
                flags = (
                    os.O_CREAT
                    | os.O_EXCL
                    | os.O_RDWR
                    | getattr(os, "O_BINARY", 0)
                    | getattr(os, "O_NOFOLLOW", 0)
                )
                descriptor = os.open(
                    temporary_name, flags, 0o600, dir_fd=directory.descriptor
                )
                handle = os.fdopen(descriptor, "w+b", buffering=0)
            else:
                handle = open_exclusive_binary(temporary_path)
            temporary_identity = handle_object_identity(handle)
            cleanup_identities.add(temporary_identity)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            handle.seek(0)
            if handle.read(len(payload) + 1) != payload or not directory.verify_path():
                raise RecoveryRequired()
            if (
                self._bound_entry_identity(directory, filename)
                != expected_destination_identity
            ):
                raise RecoveryRequired()
            if directory.descriptor is not None:
                handle.close()
                handle = None
                exchange_paths_in_directory(directory, temporary_name, filename)
                displaced_identity = self._bound_entry_identity(
                    directory, temporary_name
                )
                if displaced_identity != expected_destination_identity:
                    try:
                        exchange_paths_in_directory(
                            directory, temporary_name, filename
                        )
                    except OSError as error:
                        raise RecoveryRequired(error) from error
                    raise RecoveryRequired()
                cleanup_identities.add(expected_destination_identity)
                os.unlink(temporary_name, dir_fd=directory.descriptor)
                os.fsync(directory.descriptor)
            else:
                replace_open_file_in_directory(handle, directory, filename)
                handle.close()
                handle = None
        finally:
            if handle is not None:
                handle.close()
            try:
                if directory.descriptor is not None:
                    identity = self._bound_entry_identity(
                        directory, temporary_name
                    )
                    if identity in cleanup_identities:
                        os.unlink(temporary_name, dir_fd=directory.descriptor)
                else:
                    identity = path_object_identity(temporary_path)
                    if identity in cleanup_identities:
                        temporary_path.unlink()
            except FileNotFoundError:
                pass

    def _path(self, import_id: str) -> Path:
        # JournalEntry performs the authoritative UUID validation on write/load.
        if (
            not isinstance(import_id, str)
            or len(import_id) != 36
            or any(character in import_id for character in "/\\:")
        ):
            raise JournalCorrupt()
        path = self._root / f"{import_id}.json"
        if path.parent != self._root:
            raise JournalCorrupt()
        return path

    def _directory_identity(self) -> tuple[int, int]:
        require_plain_directory(self._root)
        return path_object_identity(self._root)


def _validate_update(previous: JournalEntry, current: JournalEntry) -> None:
    for field_name in _IMMUTABLE_FIELDS:
        if getattr(previous, field_name) != getattr(current, field_name):
            raise JournalCorrupt()
    if previous.phase is current.phase:
        try:
            validate_same_phase_update(previous, current)
        except ValueError as error:
            raise JournalCorrupt(error) from error
        return
    if current.phase not in _TRANSITIONS[previous.phase]:
        raise JournalCorrupt()
    if previous.terminal_audit is not None:
        raise JournalCorrupt()
