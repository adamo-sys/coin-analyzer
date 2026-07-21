"""Exact-byte, identity-bound collection publication for schema-2 imports.

Durable Persistence §§987–1118 and platform §§1288–1427; RM-16–RM-18.
"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Callable, Iterable

from coin_collection import CoinItem

from ._filesystem import (
    exchange_paths_in_directory,
    delete_open_file,
    handle_matches_path,
    handle_object_identity,
    open_exclusive_binary,
    open_existing_binary_for_delete,
    open_plain_directory_handle,
    path_object_identity,
    publish_open_file_no_replace_in_directory,
    require_plain_regular_file,
    sync_directory,
)
from .baseline import capture_collection_baseline, require_collection_baseline
from .durable_models import CollectionPublicationArtifact, NativeObjectIdentity
from .enums import CollectionPublicationState
from .errors import CollectionChanged, CollectionCommitFailed, RecoveryRequired
from .lock import PackageImportLock, require_verified_import_lock
from .models import CollectionBaseline

ExchangeCallback = Callable[[CollectionPublicationArtifact, CollectionPublicationArtifact], None]
ArtifactCallback = Callable[[CollectionPublicationArtifact], None]


def serialize_collection_items(items: Iterable[CoinItem]) -> bytes:
    """Return the exact deterministic bytes used for collection publication."""

    values = list(items)
    if any(not isinstance(item, CoinItem) for item in values):
        raise ValueError("Collection publication requires CoinItem values.")
    identifiers = [item.id for item in values]
    if any(not value for value in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("Prospective collection IDs must be unique.")
    return json.dumps([item.to_dict() for item in values], indent=2, ensure_ascii=False).encode("utf-8")


class DurableCollectionPublisher:
    """Create, verify, and atomically publish one prospective collection."""

    def __init__(self, collection_path: str | os.PathLike[str]) -> None:
        self._path = Path(collection_path).absolute()

    def plan(
        self,
        payload: bytes,
        *,
        baseline: CollectionBaseline,
        import_id: str,
        temporary_token: str,
        backup_token: str,
    ) -> tuple[CollectionPublicationArtifact, CollectionPublicationArtifact | None]:
        parent = self._path.parent
        parent_identity = NativeObjectIdentity.from_native(path_object_identity(parent), windows=os.name == "nt")
        temporary_name = f".collection-{import_id}-{temporary_token}.tmp"
        temporary = CollectionPublicationArtifact(
            kind="TEMPORARY", relative_name=temporary_name, token=temporary_token,
            relationship="PROSPECTIVE_BYTES", expected_byte_length=len(payload),
            expected_sha256=sha256(payload).hexdigest(), expected_parent_identity=parent_identity,
            state=CollectionPublicationState.PLANNED,
        )
        if baseline.sha256_or_sentinel == "MISSING_COLLECTION_V1":
            return temporary, None
        backup_name = temporary_name if os.name != "nt" else f".collection-{import_id}-{backup_token}.bak"
        backup = CollectionPublicationArtifact(
            kind="BACKUP", relative_name=backup_name, token=backup_token,
            relationship="BASELINE_BYTES", expected_byte_length=baseline.byte_length,
            expected_sha256=baseline.sha256_or_sentinel, expected_parent_identity=parent_identity,
            state=CollectionPublicationState.PLANNED,
        )
        return temporary, backup

    def create_temporary(
        self,
        artifact: CollectionPublicationArtifact,
        payload: bytes,
        *,
        generation: int,
        import_lock: PackageImportLock,
        on_created: ArtifactCallback | None = None,
    ) -> CollectionPublicationArtifact:
        require_verified_import_lock(import_lock)
        if artifact.state is not CollectionPublicationState.PLANNED:
            raise ValueError("Temporary creation requires PLANNED state.")
        path = self._path.parent / artifact.relative_name
        handle = open_exclusive_binary(path)
        try:
            require_verified_import_lock(import_lock)
            identity = NativeObjectIdentity.from_native(handle_object_identity(handle), windows=os.name == "nt")
            created = replace(artifact, state=CollectionPublicationState.CREATED, object_identity=identity, current_relative_name=artifact.relative_name)
            created.validate()
            if on_created is not None:
                on_created(created)
            require_verified_import_lock(import_lock)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            handle.seek(0)
            persisted = handle.read(len(payload) + 1)
            if persisted != payload or not handle_matches_path(handle, path):
                raise RecoveryRequired()
            verified = replace(
                created, state=CollectionPublicationState.VERIFIED,
                verified_byte_length=len(payload), verified_sha256=sha256(payload).hexdigest(),
                verified_generation=generation,
            )
            verified.validate()
            return verified
        finally:
            handle.close()

    def create_windows_backup(
        self,
        artifact: CollectionPublicationArtifact,
        *,
        generation: int,
        import_lock: PackageImportLock,
        on_created: ArtifactCallback | None = None,
    ) -> CollectionPublicationArtifact:
        require_verified_import_lock(import_lock)
        if os.name != "nt" or artifact.state is not CollectionPublicationState.PLANNED:
            raise ValueError("Independent backup creation is Windows-only.")
        source_identity = path_object_identity(self._path)
        backup_path = self._path.parent / artifact.relative_name
        import ctypes

        create_link = ctypes.WinDLL(
            "kernel32", use_last_error=True
        ).CreateHardLinkW
        create_link.argtypes = (
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_void_p,
        )
        create_link.restype = ctypes.c_int
        require_verified_import_lock(import_lock)
        if not create_link(str(backup_path), str(self._path), None):
            code = ctypes.get_last_error()
            if code in {80, 183}:
                raise FileExistsError(code, "The collection backup already exists.")
            raise OSError(code, "The collection backup could not be created.")
        if path_object_identity(backup_path) != source_identity:
            raise RecoveryRequired()
        created = replace(
            artifact, state=CollectionPublicationState.CREATED,
            object_identity=NativeObjectIdentity.from_native(source_identity, windows=True),
            current_relative_name=artifact.relative_name,
        )
        if on_created is not None:
            on_created(created)
        self._verify_exact(backup_path, artifact.expected_byte_length, artifact.expected_sha256)
        verified = replace(
            created, state=CollectionPublicationState.VERIFIED,
            verified_byte_length=artifact.expected_byte_length,
            verified_sha256=artifact.expected_sha256,
            verified_generation=generation,
        )
        verified.validate()
        return verified

    def publish(
        self,
        temporary: CollectionPublicationArtifact,
        backup: CollectionPublicationArtifact | None,
        *,
        baseline: CollectionBaseline,
        exchange_generation: int,
        publication_generation: int,
        import_lock: PackageImportLock,
        on_exchanged: ExchangeCallback | None = None,
    ) -> tuple[CollectionPublicationArtifact, CollectionPublicationArtifact | None]:
        """Publish and verify one exact platform-supported namespace outcome."""

        require_verified_import_lock(import_lock)
        require_collection_baseline(self._path, baseline)
        parent = self._path.parent
        temp_path = parent / temporary.relative_name
        with open_plain_directory_handle(parent) as directory:
            temp_handle = open_existing_binary_for_delete(temp_path)
            try:
                require_verified_import_lock(import_lock)
                if NativeObjectIdentity.from_native(handle_object_identity(temp_handle), windows=os.name == "nt") != temporary.object_identity:
                    raise RecoveryRequired()
                if backup is None:
                    require_verified_import_lock(import_lock)
                    publish_open_file_no_replace_in_directory(temp_handle, directory, temporary.relative_name, self._path.name)
                elif os.name == "nt":
                    if not handle_matches_path(temp_handle, temp_path):
                        raise RecoveryRequired()
                    temp_handle.close()
                    require_verified_import_lock(import_lock)
                    self._replace_windows(temporary.relative_name)
                else:
                    require_verified_import_lock(import_lock)
                    exchange_paths_in_directory(directory, temporary.relative_name, self._path.name)
                    prospective_identity = NativeObjectIdentity.from_native(path_object_identity(self._path))
                    baseline_identity = NativeObjectIdentity.from_native(path_object_identity(temp_path))
                    if prospective_identity != temporary.object_identity:
                        raise RecoveryRequired()
                    self._verify_exact(temp_path, backup.expected_byte_length, backup.expected_sha256)
                    exchanged_temp = replace(
                        temporary, state=CollectionPublicationState.EXCHANGED,
                        current_relative_name=self._path.name, exchange_generation=exchange_generation,
                    )
                    exchanged_backup = replace(
                        backup, state=CollectionPublicationState.EXCHANGED,
                        object_identity=baseline_identity,
                        verified_byte_length=backup.expected_byte_length,
                        verified_sha256=backup.expected_sha256,
                        verified_generation=exchange_generation,
                        current_relative_name=temporary.relative_name,
                        exchange_generation=exchange_generation,
                    )
                    exchanged_temp.validate()
                    exchanged_backup.validate()
                    temporary, backup = exchanged_temp, exchanged_backup
                sync_directory(directory)
                if (
                    temporary.state is CollectionPublicationState.EXCHANGED
                    and backup is not None
                    and backup.state is CollectionPublicationState.EXCHANGED
                ):
                    if on_exchanged is None:
                        raise RecoveryRequired()
                    require_verified_import_lock(import_lock)
                    on_exchanged(temporary, backup)
            finally:
                temp_handle.close()
        self._verify_exact(self._path, temporary.expected_byte_length, temporary.expected_sha256)
        if NativeObjectIdentity.from_native(
            path_object_identity(self._path), windows=os.name == "nt"
        ) != temporary.object_identity:
            raise RecoveryRequired()
        published = replace(
            temporary, state=CollectionPublicationState.PUBLISHED,
            current_relative_name=self._path.name, published_relative_name=self._path.name,
            publication_generation=publication_generation,
        )
        retained = None if backup is None else replace(
            backup, state=CollectionPublicationState.RETAINED,
            publication_generation=publication_generation,
        )
        published.validate()
        if retained is not None:
            retained.validate()
            retained_path = parent / retained.current_relative_name
            self._verify_exact(
                retained_path,
                retained.expected_byte_length,
                retained.expected_sha256,
            )
            if NativeObjectIdentity.from_native(
                path_object_identity(retained_path), windows=os.name == "nt"
            ) != retained.object_identity:
                raise RecoveryRequired()
        return published, retained

    def verify_committed(self, expected_length: int, expected_sha256: str) -> None:
        self._verify_exact(self._path, expected_length, expected_sha256)

    def cleanup_backup(
        self,
        artifact: CollectionPublicationArtifact,
        *,
        import_lock: PackageImportLock,
    ) -> None:
        """Delete only the exact retained baseline object and sync its parent."""

        require_verified_import_lock(import_lock)
        if artifact.state is not CollectionPublicationState.RETAINED or artifact.current_relative_name is None or artifact.object_identity is None:
            raise ValueError("Backup cleanup requires a retained exact artifact.")
        path = self._path.parent / artifact.current_relative_name
        with open_plain_directory_handle(self._path.parent) as directory:
            handle = open_existing_binary_for_delete(path)
            deleted = False
            try:
                actual = NativeObjectIdentity.from_native(handle_object_identity(handle), windows=os.name == "nt")
                if actual != artifact.object_identity:
                    raise RecoveryRequired()
                digest = sha256()
                length = 0
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    length += len(chunk)
                    digest.update(chunk)
                if (
                    length != artifact.expected_byte_length
                    or digest.hexdigest() != artifact.expected_sha256
                    or not handle_matches_path(handle, path)
                ):
                    raise RecoveryRequired()
                require_verified_import_lock(import_lock)
                delete_open_file(handle, path)
                deleted = True
            finally:
                handle.close()
            if not deleted or path.exists() or not directory.verify_path():
                raise RecoveryRequired()
            sync_directory(directory)

    def _replace_windows(self, temporary_name: str) -> None:
        """Publish with the frozen NTFS ReplaceFileW protocol."""

        import ctypes

        operation = ctypes.WinDLL(
            "kernel32", use_last_error=True
        ).ReplaceFileW
        operation.argtypes = (
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )
        operation.restype = ctypes.c_int
        if not operation(
            str(self._path),
            str(self._path.parent / temporary_name),
            None,
            0,
            None,
            None,
        ):
            code = ctypes.get_last_error()
            raise OSError(code, "The collection could not be replaced atomically.")

    @staticmethod
    def _verify_exact(path: Path, expected_length: int, expected_sha256: str) -> None:
        info = require_plain_regular_file(path)
        if info.st_size != expected_length:
            raise CollectionCommitFailed()
        digest = sha256()
        length = 0
        with open_existing_binary_for_delete(path) as handle:
            identity = handle_object_identity(handle)
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                length += len(chunk)
                digest.update(chunk)
            if not handle_matches_path(handle, path) or handle_object_identity(handle) != identity:
                raise RecoveryRequired()
        if length != expected_length or digest.hexdigest() != expected_sha256:
            raise CollectionCommitFailed()
