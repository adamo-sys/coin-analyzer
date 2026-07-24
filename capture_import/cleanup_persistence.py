"""Identity-bound, one-target durable cleanup for schema-2 recovery.

Durable Persistence "Cleanup intent and receipt protocol"; RM-19, RM-20,
RM-22, RM-31, RM-34, and RM-35.
"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
from typing import Callable
from uuid import uuid4

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
from ._json import canonical_json_bytes
from .durable_models import (
    CleanupOperationV3,
    CleanupReceipt,
    NativeObjectIdentity,
    OperationalJournalGenerationV3,
    OwnershipDescriptor,
    OwnershipDescriptorV3,
)
from .durable_repository import Schema3PackageImportJournalRepository
from .enums import CleanupStatus, CollectionPublicationState
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
        """Preserve the frozen Schema 2 removal behavior."""

        return self._remove(
            target,
            import_id=import_id,
            ownership_token=ownership_token,
            import_lock=import_lock,
            schema3=False,
        )

    def remove_v3(
        self,
        target: OwnershipDescriptorV3,
        *,
        import_id: str,
        ownership_token: str,
        import_lock: PackageImportLock,
    ) -> NativeObjectIdentity:
        """Apply Schema 3 namespace and processed-lease requirements."""

        return self._remove(
            target,
            import_id=import_id,
            ownership_token=ownership_token,
            import_lock=import_lock,
            schema3=True,
        )

    def _remove(
        self,
        target: OwnershipDescriptor,
        *,
        import_id: str,
        ownership_token: str,
        import_lock: PackageImportLock,
        schema3: bool,
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
                if schema3:
                    members = set(
                        os.listdir(directory.descriptor)
                        if directory.descriptor is not None
                        else os.listdir(directory.path)
                    )
                    if path.name in members:
                        raise RecoveryRequired()
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
                    schema3=schema3,
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

    def verify_operation(
        self,
        operation: CleanupOperationV3,
        *,
        import_id: str,
        ownership_token: str,
        import_lock: PackageImportLock,
        allow_next_absent: bool,
    ) -> None:
        """Verify the strict receipt prefix and complete remaining suffix."""

        require_verified_import_lock(import_lock, import_id=import_id)
        operation.validate()
        for receipt, target in zip(
            operation.receipts,
            operation.targets,
            strict=False,
        ):
            if receipt.removed_object_identity != target.object_identity:
                raise RecoveryRequired()
        if any(
            target.ownership_token != ownership_token
            for target in operation.targets
        ):
            raise RecoveryRequired()
        next_index = len(operation.receipts)
        authorized_absent_index = None
        targets_by_root_path = {
            (target.root, target.relative_path): target
            for target in operation.targets
        }

        def prove_absent(index: int, target: OwnershipDescriptorV3) -> None:
            """Bind absence to the committed namespace, not a pathname probe."""

            root = self._roots[target.root]
            path = root.joinpath(*PurePosixPath(target.relative_path).parts)
            if path.exists():
                raise RecoveryRequired()
            parent_relative = str(PurePosixPath(target.relative_path).parent)
            parent_target = targets_by_root_path.get(
                (target.root, parent_relative)
            )
            if parent_target is not None:
                parent_index = operation.targets.index(parent_target)
                if parent_index < len(operation.receipts) or (
                    allow_next_absent
                    and parent_index == next_index
                    and not root.joinpath(
                        *PurePosixPath(
                            parent_target.relative_path
                        ).parts
                    ).exists()
                ):
                    prove_absent(parent_index, parent_target)
                    return
            if not path.parent.is_dir():
                raise RecoveryRequired()
            with open_plain_directory_handle(path.parent) as parent:
                if (
                    NativeObjectIdentity.from_native(
                        parent.identity, windows=os.name == "nt"
                    )
                    != target.parent_identity
                    or not parent.verify_path()
                ):
                    raise RecoveryRequired()
                members = set(
                    os.listdir(parent.descriptor)
                    if parent.descriptor is not None
                    else os.listdir(parent.path)
                )
                if path.name in members or not parent.verify_path():
                    raise RecoveryRequired()

        for index, target in enumerate(operation.targets):
            root = self._roots.get(target.root)
            if root is None:
                raise RecoveryRequired()
            path = root.joinpath(*PurePosixPath(target.relative_path).parts)
            try:
                path.relative_to(root)
            except ValueError as error:
                raise RecoveryRequired(error) from error
            present = path.exists()
            if index < next_index:
                prove_absent(index, target)
                continue
            if not present:
                if not (allow_next_absent and index == next_index):
                    raise RecoveryRequired()
                prove_absent(index, target)
                authorized_absent_index = index
                continue
            parent_identity = NativeObjectIdentity.from_native(
                path_object_identity(path.parent), windows=os.name == "nt"
            )
            object_identity = NativeObjectIdentity.from_native(
                path_object_identity(path), windows=os.name == "nt"
            )
            if (
                parent_identity != target.parent_identity
                or object_identity != target.object_identity
            ):
                raise RecoveryRequired()
            if target.object_kind == "FILE":
                digest = sha256()
                length = 0
                with path.open("rb") as handle:
                    if not handle_matches_path(handle, path):
                        raise RecoveryRequired()
                    while chunk := handle.read(1024 * 1024):
                        length += len(chunk)
                        digest.update(chunk)
                if (
                    length != target.expected_byte_length
                    or digest.hexdigest() != target.expected_sha256
                ):
                    raise RecoveryRequired()
        # Every owned directory has exactly its still-unreceipted planned
        # direct children. This rejects extra members before any mutation.
        for directory in (
            target
            for target in operation.targets
            if target.object_kind == "DIRECTORY"
        ):
            root = self._roots[directory.root]
            directory_path = root.joinpath(
                *PurePosixPath(directory.relative_path).parts
            )
            directory_index = operation.targets.index(directory)
            if directory_index < next_index or not directory_path.exists():
                continue
            expected = {
                PurePosixPath(target.relative_path).name
                for index, target in enumerate(operation.targets)
                if index >= next_index
                and index != authorized_absent_index
                and target.root == directory.root
                and PurePosixPath(target.relative_path).parent
                == PurePosixPath(directory.relative_path)
            }
            actual = {child.name for child in directory_path.iterdir()}
            if actual != expected:
                raise RecoveryRequired()

    @staticmethod
    def _remove_file(
        path,
        target,
        directory,
        *,
        import_id,
        import_lock,
        schema3,
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
            if path.name == "snapshot.lease" or (
                schema3 and path.name == "lease.lock"
            ):
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


class Schema3CleanupProtocol:
    """Append intent, one receipt per deletion, completion, and release."""

    def __init__(
        self,
        journals: Schema3PackageImportJournalRepository,
        executor: DurableCleanupExecutor,
        *,
        clock: Callable[[], str],
        token_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self._journals = journals
        self._executor = executor
        self._clock = clock
        self._token_factory = token_factory

    def _append(
        self,
        previous: OperationalJournalGenerationV3,
        import_lock: PackageImportLock,
        **changes,
    ) -> OperationalJournalGenerationV3:
        require_verified_import_lock(import_lock, import_id=previous.import_id)
        successor = replace(
            previous,
            generation=previous.generation + 1,
            previous_generation_sha256=sha256(
                canonical_json_bytes(previous.to_dict())
            ).hexdigest(),
            transition_id=previous.next_generation_token,
            next_generation_token=self._token_factory(),
            updated_at=self._clock(),
            **changes,
        )
        successor.validate()
        return self._journals.append(
            previous, successor, import_lock=import_lock
        )

    def begin(
        self,
        head: OperationalJournalGenerationV3,
        *,
        kind: str,
        targets: tuple[OwnershipDescriptorV3, ...],
        import_lock: PackageImportLock,
    ) -> OperationalJournalGenerationV3:
        """Durably publish exact cleanup authority before any deletion."""

        require_verified_import_lock(import_lock, import_id=head.import_id)
        head.validate()
        if not targets:
            raise RecoveryRequired()
        operation = CleanupOperationV3(
            kind=kind,
            intent_id=self._token_factory(),
            intent_generation=head.generation + 1,
            targets=targets,
            receipts=(),
            status=CleanupStatus.INTENT,
            completed_generation=None,
        )
        operation.validate()
        return self._append(
            head,
            import_lock,
            cleanup_operations=(*head.cleanup_operations, operation),
        )

    def advance(
        self,
        head: OperationalJournalGenerationV3,
        *,
        import_lock: PackageImportLock,
    ) -> OperationalJournalGenerationV3:
        """Perform exactly one next durable action from the strict prefix."""

        require_verified_import_lock(import_lock, import_id=head.import_id)
        head.validate()
        if not head.cleanup_operations:
            raise RecoveryRequired()
        operation = head.cleanup_operations[-1]
        operation.validate()
        if operation.status is CleanupStatus.COMPLETE:
            raise RecoveryRequired()
        if len(operation.receipts) == len(operation.targets):
            complete = replace(
                operation,
                status=CleanupStatus.COMPLETE,
                completed_generation=head.generation + 1,
            )
            return self._append(
                head,
                import_lock,
                cleanup_operations=(*head.cleanup_operations[:-1], complete),
            )
        target = operation.targets[len(operation.receipts)]
        self._executor.verify_operation(
            operation,
            import_id=head.import_id,
            ownership_token=head.random_ownership_token,
            import_lock=import_lock,
            allow_next_absent=True,
        )
        removed = self._executor.remove_v3(
            target,
            import_id=head.import_id,
            ownership_token=head.random_ownership_token,
            import_lock=import_lock,
        )
        self._executor.verify_operation(
            operation,
            import_id=head.import_id,
            ownership_token=head.random_ownership_token,
            import_lock=import_lock,
            allow_next_absent=True,
        )
        receipt = CleanupReceipt(
            target_relative_path=target.relative_path,
            removed_object_identity=removed,
            removal_generation=head.generation + 1,
        )
        advanced = replace(
            operation,
            receipts=(*operation.receipts, receipt),
        )
        changes = {
            "cleanup_operations": (*head.cleanup_operations[:-1], advanced)
        }
        if operation.kind == "BASELINE_BACKUP":
            retained = head.collection_backup_artifact
            if (
                len(operation.targets) != 1
                or retained is None
                or retained.state
                is not CollectionPublicationState.RETAINED
                or retained.current_relative_name
                != target.relative_path
                or retained.object_identity != target.object_identity
            ):
                raise RecoveryRequired()
            changes["collection_backup_artifact"] = replace(
                retained,
                state=CollectionPublicationState.CLEANED,
                cleanup_operation_id=operation.intent_id,
            )
        if target.root == "SNAPSHOT":
            changes["package_snapshot_relative_path"] = None
        return self._append(head, import_lock, **changes)

    def complete(
        self,
        head: OperationalJournalGenerationV3,
        *,
        import_lock: PackageImportLock,
    ) -> OperationalJournalGenerationV3:
        """Idempotently drive only the current operation through COMPLETE."""

        current = head
        while (
            current.cleanup_operations
            and current.cleanup_operations[-1].status is CleanupStatus.INTENT
        ):
            current = self.advance(current, import_lock=import_lock)
        return current

    def release_processed_reference(
        self,
        head: OperationalJournalGenerationV3,
        *,
        import_lock: PackageImportLock,
    ) -> OperationalJournalGenerationV3:
        """Publish the distinct successor that nulls only the processed path."""

        require_verified_import_lock(import_lock, import_id=head.import_id)
        head.validate()
        if head.processed_snapshot_reference is None:
            return head
        if not any(
            (
                operation.status is CleanupStatus.COMPLETE
                and operation.kind == "SUCCESS_PROCESSED_SNAPSHOT"
            )
            or (
                operation.kind == "ROLLBACK_ALL"
                and any(
                    target.root == "PROCESSED_SNAPSHOT"
                    for target in operation.targets
                )
                and all(
                    index < len(operation.receipts)
                    for index, target in enumerate(operation.targets)
                    if target.root == "PROCESSED_SNAPSHOT"
                )
            )
            for operation in head.cleanup_operations
        ):
            raise RecoveryRequired()
        return self._append(
            head,
            import_lock,
            processed_snapshot_reference=None,
        )

    @staticmethod
    def validate_rollback_order(
        targets: tuple[OwnershipDescriptorV3, ...],
    ) -> None:
        """Enforce collection, managed, processed, then raw ownership classes."""

        ranks = {
            "COLLECTION": 0,
            "MANAGED_IMAGE": 1,
            "PROCESSED_SNAPSHOT": 2,
            "SNAPSHOT": 3,
        }
        try:
            values = tuple(ranks[target.root] for target in targets)
        except KeyError as error:
            raise RecoveryRequired() from error
        if values != tuple(sorted(values)):
            raise RecoveryRequired()

    def begin_rollback(
        self,
        head: OperationalJournalGenerationV3,
        *,
        targets: tuple[OwnershipDescriptorV3, ...],
        import_lock: PackageImportLock,
    ) -> OperationalJournalGenerationV3:
        self.validate_rollback_order(targets)
        return self.begin(
            head,
            kind="ROLLBACK_ALL",
            targets=targets,
            import_lock=import_lock,
        )

    def begin_success_next(
        self,
        head: OperationalJournalGenerationV3,
        *,
        baseline_targets: tuple[OwnershipDescriptorV3, ...] = (),
        processed_targets: tuple[OwnershipDescriptorV3, ...],
        raw_targets: tuple[OwnershipDescriptorV3, ...],
        import_lock: PackageImportLock,
    ) -> OperationalJournalGenerationV3:
        """Begin only the next frozen success cleanup class."""

        head.validate()
        existing = tuple(item.kind for item in head.cleanup_operations)
        required = (
            (
                "SUCCESS_PROCESSED_SNAPSHOT",
                "SUCCESS_SNAPSHOT",
            )
            if head.collection_baseline_sha256_or_sentinel
            == "MISSING_COLLECTION_V1"
            else (
                "BASELINE_BACKUP",
                "SUCCESS_PROCESSED_SNAPSHOT",
                "SUCCESS_SNAPSHOT",
            )
        )
        if existing == required:
            return head
        if any(
            operation.status is not CleanupStatus.COMPLETE
            for operation in head.cleanup_operations
        ):
            raise RecoveryRequired()
        kind = required[len(existing)]
        if kind == "BASELINE_BACKUP":
            targets = baseline_targets
        elif kind == "SUCCESS_PROCESSED_SNAPSHOT":
            targets = processed_targets
        else:
            if head.processed_snapshot_reference is not None:
                raise RecoveryRequired()
            targets = raw_targets
        return self.begin(
            head,
            kind=kind,
            targets=targets,
            import_lock=import_lock,
        )
