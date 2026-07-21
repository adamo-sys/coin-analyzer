"""Identity-bound, one-target durable cleanup for schema-2 recovery.

Durable Persistence "Cleanup intent and receipt protocol"; RM-19, RM-20,
RM-22, RM-31, RM-34, and RM-35.
"""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path, PurePosixPath

from ._advisory import acquire_advisory_lock, release_advisory_lock
from ._filesystem import (
    delete_open_file,
    handle_matches_path,
    handle_object_identity,
    open_existing_binary_for_delete,
    open_plain_directory_handle,
    path_object_identity,
    sync_directory,
)
from .durable_models import NativeObjectIdentity, OwnershipDescriptor
from .errors import RecoveryRequired
from .lock import PackageImportLock, require_verified_import_lock


class DurableCleanupExecutor:
    """Delete one previously committed exact object and durably prove absence."""

    def __init__(self, roots: dict[str, Path]) -> None:
        self._roots = {name: Path(path).absolute() for name, path in roots.items()}

    def remove(
        self,
        target: OwnershipDescriptor,
        *,
        import_id: str,
        ownership_token: str,
        import_lock: PackageImportLock,
    ) -> NativeObjectIdentity:
        require_verified_import_lock(import_lock, import_id=import_id)
        target.validate()
        if target.ownership_token != ownership_token:
            raise RecoveryRequired()
        root = self._roots.get(target.root)
        if root is None:
            raise RecoveryRequired()
        parts = PurePosixPath(target.relative_path).parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise RecoveryRequired()
        path = root.joinpath(*parts)
        try:
            path.relative_to(root)
        except ValueError as error:
            raise RecoveryRequired(error) from error
        parent = path.parent
        expected_parent = NativeObjectIdentity.from_native(
            path_object_identity(parent),
            windows=os.name == "nt",
        )
        if expected_parent != target.parent_identity:
            raise RecoveryRequired()
        with open_plain_directory_handle(parent) as directory:
            require_verified_import_lock(import_lock, import_id=import_id)
            if not path.exists():
                sync_directory(directory)
                if not directory.verify_path():
                    raise RecoveryRequired()
                return target.object_identity
            if target.object_kind == "FILE":
                self._remove_file(
                    path,
                    target,
                    directory,
                    import_id=import_id,
                    import_lock=import_lock,
                )
            else:
                if any(path.iterdir()):
                    raise RecoveryRequired()
                actual = NativeObjectIdentity.from_native(
                    path_object_identity(path),
                    windows=os.name == "nt",
                )
                if actual != target.object_identity:
                    raise RecoveryRequired()
                require_verified_import_lock(import_lock, import_id=import_id)
                os.rmdir(path)
                sync_directory(directory)
            if path.exists() or not directory.verify_path():
                raise RecoveryRequired()
        return target.object_identity

    @staticmethod
    def _remove_file(
        path,
        target,
        directory,
        *,
        import_id,
        import_lock,
    ) -> None:
        handle = open_existing_binary_for_delete(path)
        advisory = False
        try:
            actual = NativeObjectIdentity.from_native(
                handle_object_identity(handle),
                windows=os.name == "nt",
            )
            if actual != target.object_identity or not handle_matches_path(handle, path):
                raise RecoveryRequired()
            if path.name == "snapshot.lease":
                try:
                    acquire_advisory_lock(handle)
                    advisory = True
                except BlockingIOError as error:
                    raise RecoveryRequired(error) from error
            digest = sha256()
            length = 0
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                length += len(chunk)
                digest.update(chunk)
            if (
                length != target.expected_byte_length
                or digest.hexdigest() != target.expected_sha256
            ):
                raise RecoveryRequired()
            require_verified_import_lock(import_lock, import_id=import_id)
            delete_open_file(handle, path)
            sync_directory(directory)
        finally:
            if advisory:
                try:
                    release_advisory_lock(handle)
                except OSError:
                    pass
            handle.close()
