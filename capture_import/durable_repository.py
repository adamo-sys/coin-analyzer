"""Append-only schema-2 journal storage and deterministic generation replay.

Durable Persistence §§516–643, RM-01–RM-04 and RM-26.
"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
import re
from typing import Callable
from uuid import UUID, uuid4

from ._filesystem import (
    delete_open_file,
    ensure_plain_directory,
    handle_matches_path,
    handle_object_identity,
    open_exclusive_binary,
    open_existing_binary_for_delete,
    open_plain_directory_handle,
    publish_open_file_no_replace_in_directory,
    require_plain_directory,
    require_plain_regular_file,
    sync_directory,
)
from ._json import canonical_json_bytes, parse_bounded_json_object
from .durable_models import (
    JournalOwnerRecord,
    JournalOwnerRecordV2,
    OperationalJournalGeneration,
    OperationalJournalGenerationV3,
)
from .enums import ImportPhase, TerminalCompactionStatus
from .errors import JournalCorrupt, RecoveryRequired
from .limits import MAX_IMPORT_STATE_MEMBERS, MAX_JSON_BYTES
from .lock import PackageImportLock, require_verified_import_lock

TokenFactory = Callable[[], str]
_GENERATION = re.compile(r"^(?P<number>[0-9]{8})-(?P<transition>[0-9a-f-]{36})\.json$")


class Schema2PackageImportJournalRepository:
    """Persist immutable operational generations under one owner-bound directory."""

    def __init__(self, root: str | os.PathLike[str], *, token_factory: TokenFactory = lambda: str(uuid4())) -> None:
        self._root = Path(root).absolute()
        self._token_factory = token_factory

    @property
    def root(self) -> Path:
        return self._root

    @staticmethod
    def generation_name(generation: int, transition_id: str) -> str:
        return f"{generation:08d}-{transition_id}.json"

    @staticmethod
    def temporary_name(generation: int, token: str) -> str:
        return f".next-{generation:08d}-{token}.tmp"

    def create(
        self,
        entry: OperationalJournalGeneration,
        *,
        import_lock: PackageImportLock,
    ) -> OperationalJournalGeneration:
        """Create owner intent and publish generation zero without overwrite."""

        require_verified_import_lock(import_lock, import_id=entry.import_id)
        entry.validate()
        if entry.generation != 0 or entry.phase is not ImportPhase.PREPARED:
            raise ValueError("A schema-2 journal must begin with PREPARED generation zero.")
        payload = canonical_json_bytes(entry.to_dict())
        generation_name = self.generation_name(0, entry.transition_id)
        genesis_token = self._new_token({entry.transition_id, entry.next_generation_token})
        temporary_name = self.temporary_name(0, genesis_token)
        owner = JournalOwnerRecord(
            owner_schema_version="1.0", journal_schema_version="2.0",
            import_id=entry.import_id, random_ownership_token=entry.random_ownership_token,
            created_at=entry.created_at, genesis_filename=generation_name,
            genesis_sha256=sha256(payload).hexdigest(),
            genesis_temporary_token=genesis_token, genesis_temporary_name=temporary_name,
        )
        owner_payload = canonical_json_bytes(owner.to_dict())
        ensure_plain_directory(self._root)
        import_root = self._import_root(entry.import_id)
        try:
            require_verified_import_lock(import_lock, import_id=entry.import_id)
            os.mkdir(import_root, 0o700)
        except FileExistsError as error:
            raise JournalCorrupt(error) from error
        try:
            require_plain_directory(import_root)
            with open_plain_directory_handle(import_root) as directory:
                require_verified_import_lock(import_lock, import_id=entry.import_id)
                self._write_direct_exclusive(directory, "owner.json", owner_payload)
                require_verified_import_lock(import_lock, import_id=entry.import_id)
                sync_directory(directory)
                require_verified_import_lock(import_lock, import_id=entry.import_id)
                self._write_and_publish(directory, temporary_name, generation_name, payload)
                loaded, raw, _identity = self._read_generation(directory, generation_name)
                if loaded != entry or raw != payload:
                    raise RecoveryRequired()
                return loaded
        except Exception as error:
            if isinstance(error, (JournalCorrupt, RecoveryRequired)):
                raise
            raise RecoveryRequired(error) from error

    def append(
        self,
        previous: OperationalJournalGeneration,
        current: OperationalJournalGeneration,
        *,
        import_lock: PackageImportLock,
    ) -> OperationalJournalGeneration:
        """Append exactly one predecessor-authorized immutable generation."""

        require_verified_import_lock(import_lock, import_id=previous.import_id)
        previous.validate()
        current.validate()
        if previous.next_generation_token is None:
            raise JournalCorrupt()
        if current.generation != previous.generation + 1:
            raise JournalCorrupt()
        previous_payload = canonical_json_bytes(previous.to_dict())
        if current.previous_generation_sha256 != sha256(previous_payload).hexdigest():
            raise JournalCorrupt()
        self._validate_immutable(previous, current)
        self._validate_transition(previous, current)
        import_root = self._import_root(previous.import_id)
        with open_plain_directory_handle(import_root) as directory:
            require_verified_import_lock(import_lock, import_id=previous.import_id)
            head = self._load_chain_bound(
                directory,
                previous.import_id,
                import_lock=import_lock,
            )[-1]
            if head != previous:
                raise JournalCorrupt()
            final_name = self.generation_name(current.generation, current.transition_id)
            temporary_name = self.temporary_name(current.generation, previous.next_generation_token)
            require_verified_import_lock(import_lock, import_id=previous.import_id)
            self._write_and_publish(directory, temporary_name, final_name, canonical_json_bytes(current.to_dict()))
            loaded, _raw, _identity = self._read_generation(directory, final_name)
            if loaded != current:
                raise RecoveryRequired()
            return loaded

    def load(
        self,
        import_id: str,
        *,
        import_lock: PackageImportLock,
    ) -> OperationalJournalGeneration:
        """Return the unique valid head after strict complete-chain validation."""

        require_verified_import_lock(import_lock, import_id=import_id)
        with open_plain_directory_handle(self._import_root(import_id)) as directory:
            return self._load_chain_bound(
                directory,
                import_id,
                import_lock=import_lock,
            )[-1]

    def load_chain(
        self,
        import_id: str,
        *,
        import_lock: PackageImportLock,
    ) -> tuple[OperationalJournalGeneration, ...]:
        require_verified_import_lock(import_lock, import_id=import_id)
        with open_plain_directory_handle(self._import_root(import_id)) as directory:
            return self._load_chain_bound(
                directory,
                import_id,
                import_lock=import_lock,
            )

    def list_heads(
        self,
        *,
        import_lock: PackageImportLock,
        validated_legacy_names: frozenset[str] = frozenset(),
    ) -> tuple[OperationalJournalGeneration, ...]:
        """Enumerate only canonical active UUID directories under a bounded root."""

        require_verified_import_lock(import_lock)
        if not self._root.exists():
            return ()
        require_plain_directory(self._root)
        names = sorted(os.listdir(self._root))
        if len(names) > MAX_IMPORT_STATE_MEMBERS:
            raise JournalCorrupt()
        heads: list[OperationalJournalGeneration] = []
        for name in names:
            if name in validated_legacy_names:
                continue
            if name.startswith(".retire-"):
                raise RecoveryRequired()
            try:
                if str(UUID(name)) != name:
                    raise ValueError
            except (ValueError, AttributeError) as error:
                raise JournalCorrupt(error) from error
            heads.append(self.load(name, import_lock=import_lock))
        return tuple(heads)

    def _load_chain_bound(
        self,
        directory,
        import_id: str,
        *,
        import_lock: PackageImportLock,
    ) -> tuple[OperationalJournalGeneration, ...]:
        require_verified_import_lock(import_lock, import_id=import_id)
        owner, owner_raw = self._read_owner(directory)
        if owner.import_id != import_id:
            raise JournalCorrupt()
        names = sorted(os.listdir(directory.descriptor) if directory.descriptor is not None else os.listdir(self._import_root(import_id)))
        if len(names) > MAX_IMPORT_STATE_MEMBERS:
            raise JournalCorrupt()
        generation_names = [name for name in names if _GENERATION.fullmatch(name)]
        temporary_names = [name for name in names if name.startswith(".next-")]
        manifest_names = [
            name for name in names
            if name == "retirement-manifest.json" or name.startswith(".retirement-manifest-")
        ]
        allowed = {"owner.json", *generation_names, *temporary_names, *manifest_names}
        if set(names) != allowed:
            raise JournalCorrupt()
        chain: list[OperationalJournalGeneration] = []
        raw_chain: list[bytes] = []
        for expected, name in enumerate(generation_names):
            match = _GENERATION.fullmatch(name)
            assert match is not None
            if int(match.group("number")) != expected:
                raise JournalCorrupt()
            entry, raw, _identity = self._read_generation(directory, name)
            if entry.generation != expected or entry.transition_id != match.group("transition"):
                raise JournalCorrupt()
            if entry.import_id != owner.import_id or entry.random_ownership_token != owner.random_ownership_token:
                raise JournalCorrupt()
            if expected == 0:
                if name != owner.genesis_filename or sha256(raw).hexdigest() != owner.genesis_sha256:
                    raise JournalCorrupt()
            elif entry.previous_generation_sha256 != sha256(raw_chain[-1]).hexdigest():
                raise JournalCorrupt()
            if chain:
                self._validate_immutable(chain[0], entry)
                self._validate_transition(chain[-1], entry)
            chain.append(entry)
            raw_chain.append(raw)
        if not chain:
            require_verified_import_lock(import_lock, import_id=import_id)
            self._reconcile_genesis(directory, owner, owner_raw, temporary_names)
            return self._load_chain_bound(
                directory,
                import_id,
                import_lock=import_lock,
            )
        if manifest_names:
            compaction = chain[-1].compaction
            if compaction is None:
                raise JournalCorrupt()
            exact = {compaction.retirement_manifest_name, compaction.retirement_manifest_temporary_name}
            if not set(manifest_names).issubset(exact) or len(manifest_names) > 1:
                raise JournalCorrupt()
        expected_candidate = None if chain[-1].next_generation_token is None else self.temporary_name(chain[-1].generation + 1, chain[-1].next_generation_token)
        if temporary_names:
            if len(temporary_names) != 1 or temporary_names[0] != expected_candidate:
                raise JournalCorrupt()
            require_verified_import_lock(import_lock, import_id=import_id)
            self._reconcile_successor_candidate(directory, chain[-1], temporary_names[0])
            return self._load_chain_bound(
                directory,
                import_id,
                import_lock=import_lock,
            )
        return tuple(chain)

    def _reconcile_genesis(self, directory, owner: JournalOwnerRecord, owner_raw: bytes, temporary_names: list[str]) -> None:
        if not temporary_names:
            raise RecoveryRequired()
        if temporary_names != [owner.genesis_temporary_name]:
            raise JournalCorrupt()
        entry, raw, _identity = self._read_generation(directory, owner.genesis_temporary_name, temporary=True)
        if entry.generation != 0 or sha256(raw).hexdigest() != owner.genesis_sha256:
            raise JournalCorrupt()
        self._publish_existing(directory, owner.genesis_temporary_name, owner.genesis_filename)

    def _reconcile_successor_candidate(self, directory, previous: OperationalJournalGeneration, temporary_name: str) -> None:
        try:
            entry, raw, _identity = self._read_generation(
                directory, temporary_name, temporary=True
            )
        except JournalCorrupt:
            self._delete_incomplete_candidate(directory, temporary_name)
            return
        if entry.generation != previous.generation + 1 or entry.previous_generation_sha256 != sha256(canonical_json_bytes(previous.to_dict())).hexdigest():
            raise JournalCorrupt()
        self._validate_immutable(previous, entry)
        self._validate_transition(previous, entry)
        self._publish_existing(directory, temporary_name, self.generation_name(entry.generation, entry.transition_id))

    def _delete_incomplete_candidate(self, directory, temporary_name: str) -> None:
        """Remove only the predecessor-authorized exact partial candidate."""

        path = directory.path / temporary_name
        handle = open_existing_binary_for_delete(path)
        deleted = False
        try:
            size = os.fstat(handle.fileno()).st_size
            if size > MAX_JSON_BYTES or not handle_matches_path(handle, path):
                raise JournalCorrupt()
            delete_open_file(handle, path)
            deleted = True
        finally:
            handle.close()
        if not deleted or path.exists() or not directory.verify_path():
            raise JournalCorrupt()
        sync_directory(directory)

    def _read_owner(self, directory) -> tuple[JournalOwnerRecord, bytes]:
        raw, _identity = self._read_bound_bytes(directory, "owner.json")
        try:
            owner = JournalOwnerRecord.from_dict(parse_bounded_json_object(raw, "journal owner"))
        except Exception as error:
            raise JournalCorrupt(error) from error
        return owner, raw

    def _read_generation(self, directory, name: str, *, temporary: bool = False):
        raw, identity = self._read_bound_bytes(directory, name)
        try:
            entry = OperationalJournalGeneration.from_dict(parse_bounded_json_object(raw, "journal generation"))
        except Exception as error:
            raise JournalCorrupt(error) from error
        if not temporary and name != self.generation_name(entry.generation, entry.transition_id):
            raise JournalCorrupt()
        return entry, raw, identity

    def _read_bound_bytes(self, directory, name: str):
        path = self._root / "unused" / name
        if directory.descriptor is not None:
            descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory.descriptor)
            handle = os.fdopen(descriptor, "rb", buffering=0)
        else:
            path = directory.path / name
            require_plain_regular_file(path)
            handle = path.open("rb", buffering=0)
        try:
            identity = handle_object_identity(handle)
            size = os.fstat(handle.fileno()).st_size
            if size < 1 or size > MAX_JSON_BYTES:
                raise JournalCorrupt()
            raw = handle.read(MAX_JSON_BYTES + 1)
            if len(raw) != size or not directory.verify_path():
                raise JournalCorrupt()
            if directory.descriptor is None and not handle_matches_path(handle, path):
                raise JournalCorrupt()
            return raw, identity
        finally:
            handle.close()

    def _write_direct_exclusive(self, directory, name: str, payload: bytes) -> None:
        path = directory.path / name
        handle = open_exclusive_binary(path)
        try:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            handle.seek(0)
            if handle.read(len(payload) + 1) != payload or not handle_matches_path(handle, path) or not directory.verify_path():
                raise RecoveryRequired()
        finally:
            handle.close()

    def _write_and_publish(self, directory, temporary_name: str, final_name: str, payload: bytes) -> None:
        handle = open_exclusive_binary(directory.path / temporary_name)
        try:
            identity = handle_object_identity(handle)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            handle.seek(0)
            if handle.read(len(payload) + 1) != payload or handle_object_identity(handle) != identity or not handle_matches_path(handle, directory.path / temporary_name):
                raise RecoveryRequired()
            publish_open_file_no_replace_in_directory(handle, directory, temporary_name, final_name)
            sync_directory(directory)
        finally:
            handle.close()

    def _publish_existing(self, directory, temporary_name: str, final_name: str) -> None:
        path = directory.path / temporary_name
        with path.open("r+b", buffering=0) as handle:
            publish_open_file_no_replace_in_directory(handle, directory, temporary_name, final_name)
        sync_directory(directory)

    def _import_root(self, import_id: str) -> Path:
        try:
            if str(UUID(import_id)) != import_id:
                raise ValueError
        except (ValueError, AttributeError) as error:
            raise JournalCorrupt(error) from error
        return self._root / import_id

    def _new_token(self, exclusions: set[str | None]) -> str:
        token = self._token_factory()
        try:
            if str(UUID(token)) != token or UUID(token).version != 4 or token in exclusions:
                raise ValueError
        except (ValueError, AttributeError) as error:
            raise JournalCorrupt(error) from error
        return token

    @staticmethod
    def _validate_immutable(first: OperationalJournalGeneration, current: OperationalJournalGeneration) -> None:
        for field in (
            "journal_schema_version", "import_id", "random_ownership_token", "created_at",
            "package_sha256", "package_version", "package_basename", "snapshot_byte_length",
            "collection_baseline_sha256_or_sentinel", "collection_baseline_byte_length",
            "selected_source_coin_ids", "desktop_item_ids", "import_root_relative_path",
            "expected_image_inventory", "proposed_count", "skipped_count",
        ):
            if getattr(first, field) != getattr(current, field):
                raise JournalCorrupt()

    @staticmethod
    def _validate_transition(
        previous: OperationalJournalGeneration,
        current: OperationalJournalGeneration,
    ) -> None:
        """Reject every schema-2 transition not authorized by the frozen state machine.

        Durable Persistence "Transaction state machine" and RM-03/RM-20.
        """

        legal_phase_changes = {
            ImportPhase.PREPARED: {
                ImportPhase.COPYING_IMAGES,
                ImportPhase.ROLLING_BACK,
                ImportPhase.RECOVERY_REQUIRED,
            },
            ImportPhase.COPYING_IMAGES: {
                ImportPhase.FILES_READY,
                ImportPhase.ROLLING_BACK,
                ImportPhase.RECOVERY_REQUIRED,
            },
            ImportPhase.FILES_READY: {
                ImportPhase.COMMITTING_COLLECTION,
                ImportPhase.ROLLING_BACK,
                ImportPhase.RECOVERY_REQUIRED,
            },
            ImportPhase.COMMITTING_COLLECTION: {
                ImportPhase.COLLECTION_COMMITTED,
                ImportPhase.ROLLING_BACK,
                ImportPhase.RECOVERY_REQUIRED,
            },
            ImportPhase.COLLECTION_COMMITTED: {
                ImportPhase.COMPACTING,
                ImportPhase.RECOVERY_REQUIRED,
            },
            ImportPhase.ROLLING_BACK: {
                ImportPhase.COMPACTING,
                ImportPhase.RECOVERY_REQUIRED,
                ImportPhase.ROLLBACK_FAILED,
            },
            ImportPhase.RECOVERY_REQUIRED: {
                ImportPhase.ROLLING_BACK,
                ImportPhase.COLLECTION_COMMITTED,
                ImportPhase.ROLLBACK_FAILED,
            },
            ImportPhase.ROLLBACK_FAILED: {ImportPhase.ROLLING_BACK},
            ImportPhase.COMPACTING: set(),
        }
        envelope = {
            "generation",
            "previous_generation_sha256",
            "transition_id",
            "next_generation_token",
            "updated_at",
        }
        changed = {
            name
            for name in previous.__dataclass_fields__
            if name not in envelope and getattr(previous, name) != getattr(current, name)
        }
        if previous.phase is not current.phase:
            if current.phase not in legal_phase_changes.get(previous.phase, set()):
                raise JournalCorrupt()
            if current.phase is ImportPhase.COMPACTING:
                if previous.phase not in {
                    ImportPhase.COLLECTION_COMMITTED,
                    ImportPhase.ROLLING_BACK,
                }:
                    raise JournalCorrupt()
                if not previous.cleanup_operations or any(
                    operation.status.value != "COMPLETE"
                    for operation in previous.cleanup_operations
                ):
                    raise JournalCorrupt()
            allowed_changes = {
                (ImportPhase.PREPARED, ImportPhase.COPYING_IMAGES): {"phase"},
                (ImportPhase.COPYING_IMAGES, ImportPhase.FILES_READY): {"phase"},
                (ImportPhase.FILES_READY, ImportPhase.COMMITTING_COLLECTION): {
                    "phase",
                    "prospective_collection_byte_length",
                    "prospective_collection_sha256",
                    "collection_publication",
                    "collection_temporary_artifact",
                    "collection_backup_artifact",
                },
                (ImportPhase.COMMITTING_COLLECTION, ImportPhase.COLLECTION_COMMITTED): {
                    "phase",
                    "collection_publication",
                    "collection_temporary_artifact",
                    "collection_backup_artifact",
                    "committed_collection_item_ids",
                    "imported_count",
                    "pending_terminal_audit",
                },
                (ImportPhase.COLLECTION_COMMITTED, ImportPhase.COMPACTING): {
                    "phase",
                    "collection_temporary_artifact",
                    "collection_backup_artifact",
                    "compaction",
                },
                (ImportPhase.ROLLING_BACK, ImportPhase.COMPACTING): {
                    "phase",
                    "collection_temporary_artifact",
                    "collection_backup_artifact",
                    "compaction",
                },
            }.get((previous.phase, current.phase))
            if current.phase is ImportPhase.RECOVERY_REQUIRED:
                allowed_changes = {
                    "phase", "resume_phase", "error_category",
                    "recovery_attempt_count",
                }
            elif current.phase is ImportPhase.ROLLBACK_FAILED:
                allowed_changes = {
                    "phase", "resume_phase", "error_category",
                    "recovery_attempt_count",
                }
            elif previous.phase in {
                ImportPhase.PREPARED,
                ImportPhase.COPYING_IMAGES,
                ImportPhase.FILES_READY,
                ImportPhase.COMMITTING_COLLECTION,
            } and current.phase is ImportPhase.ROLLING_BACK:
                allowed_changes = {"phase", "pending_terminal_audit"}
            elif previous.phase in {
                ImportPhase.RECOVERY_REQUIRED,
                ImportPhase.ROLLBACK_FAILED,
            }:
                if current.phase is ImportPhase.COLLECTION_COMMITTED:
                    allowed_changes = {
                        "phase", "resume_phase", "error_category",
                        "collection_publication", "collection_temporary_artifact",
                        "collection_backup_artifact", "committed_collection_item_ids",
                        "imported_count", "pending_terminal_audit",
                    }
                elif current.phase is ImportPhase.ROLLING_BACK:
                    allowed_changes = {
                        "phase", "resume_phase", "error_category",
                        "pending_terminal_audit",
                    }
                else:
                    allowed_changes = {"phase", "resume_phase", "error_category"}
            if allowed_changes is None or not changed.issubset(allowed_changes):
                raise JournalCorrupt()
            return

        phase = current.phase
        if phase is ImportPhase.COPYING_IMAGES:
            if changed != {"verified_image_inventory"}:
                raise JournalCorrupt()
            if (
                len(current.verified_image_inventory)
                != len(previous.verified_image_inventory) + 1
                or current.verified_image_inventory[:-1]
                != previous.verified_image_inventory
            ):
                raise JournalCorrupt()
            return
        if phase is ImportPhase.COMMITTING_COLLECTION:
            if not changed or not changed.issubset(
                {
                    "collection_publication",
                    "collection_temporary_artifact",
                    "collection_backup_artifact",
                }
            ):
                raise JournalCorrupt()
            return
        if phase in {ImportPhase.COLLECTION_COMMITTED, ImportPhase.ROLLING_BACK}:
            if not changed.issubset(
                {
                    "cleanup_operations",
                    "snapshot_relative_path",
                    "collection_backup_artifact",
                }
            ) or "cleanup_operations" not in changed:
                raise JournalCorrupt()
            Schema2PackageImportJournalRepository._validate_cleanup_transition(
                previous, current
            )
            return
        if phase in {ImportPhase.RECOVERY_REQUIRED, ImportPhase.ROLLBACK_FAILED}:
            if changed != {"recovery_attempt_count"}:
                raise JournalCorrupt()
            if current.recovery_attempt_count != previous.recovery_attempt_count + 1:
                raise JournalCorrupt()
            return
        if phase is ImportPhase.COMPACTING:
            if changed != {"compaction"}:
                raise JournalCorrupt()
            before = previous.compaction
            after = current.compaction
            if (
                before is None
                or after is None
                or before.status is not TerminalCompactionStatus.PLANNING_MANIFEST
                or after.status is not TerminalCompactionStatus.READY_FOR_TERMINAL
            ):
                raise JournalCorrupt()
            return
        raise JournalCorrupt()

    @staticmethod
    def _validate_cleanup_transition(
        previous: OperationalJournalGeneration,
        current: OperationalJournalGeneration,
    ) -> None:
        before = previous.cleanup_operations
        after = current.cleanup_operations
        if len(after) == len(before) + 1:
            if after[:-1] != before or any(
                operation.status.value != "COMPLETE" for operation in before
            ):
                raise JournalCorrupt()
            appended = after[-1]
            if (
                appended.status.value != "INTENT"
                or appended.receipts
                or appended.completed_generation is not None
                or appended.intent_generation != current.generation
            ):
                raise JournalCorrupt()
            return
        if len(after) != len(before) or not before or after[:-1] != before[:-1]:
            raise JournalCorrupt()
        old = before[-1]
        new = after[-1]
        if (
            new.kind != old.kind
            or new.intent_id != old.intent_id
            or new.intent_generation != old.intent_generation
            or new.targets != old.targets
        ):
            raise JournalCorrupt()
        if (
            old.status.value == "INTENT"
            and new.status.value == "INTENT"
            and new.completed_generation is None
            and len(new.receipts) == len(old.receipts) + 1
            and new.receipts[:-1] == old.receipts
            and new.receipts[-1].removal_generation == current.generation
        ):
            return
        if (
            old.status.value == "INTENT"
            and len(old.receipts) == len(old.targets)
            and old.completed_generation is None
            and new.status.value == "COMPLETE"
            and new.receipts == old.receipts
            and new.completed_generation == current.generation
        ):
            return
        raise JournalCorrupt()


class Schema3PackageImportJournalRepository(
    Schema2PackageImportJournalRepository
):
    """Separate owner-2.0/journal-3.0 repository with closed dispatch."""

    def create(
        self,
        entry: OperationalJournalGenerationV3,
        *,
        import_lock: PackageImportLock,
    ) -> OperationalJournalGenerationV3:
        """Create owner 2.0 and publish Schema 3 generation zero."""

        require_verified_import_lock(import_lock, import_id=entry.import_id)
        entry.validate()
        if entry.generation != 0 or entry.phase is not ImportPhase.PREPARED:
            raise ValueError("A Schema 3 journal must begin with PREPARED generation zero.")
        payload = canonical_json_bytes(entry.to_dict())
        generation_name = self.generation_name(0, entry.transition_id)
        genesis_token = self._new_token(
            {entry.transition_id, entry.next_generation_token}
        )
        temporary_name = self.temporary_name(0, genesis_token)
        owner = JournalOwnerRecordV2(
            owner_schema_version="2.0",
            journal_schema_version="3.0",
            import_id=entry.import_id,
            random_ownership_token=entry.random_ownership_token,
            created_at=entry.created_at,
            genesis_filename=generation_name,
            genesis_sha256=sha256(payload).hexdigest(),
            genesis_temporary_token=genesis_token,
            genesis_temporary_name=temporary_name,
        )
        owner_payload = canonical_json_bytes(owner.to_dict())
        ensure_plain_directory(self._root)
        import_root = self._import_root(entry.import_id)
        try:
            require_verified_import_lock(import_lock, import_id=entry.import_id)
            os.mkdir(import_root, 0o700)
        except FileExistsError as error:
            raise JournalCorrupt(error) from error
        try:
            require_plain_directory(import_root)
            with open_plain_directory_handle(import_root) as directory:
                require_verified_import_lock(import_lock, import_id=entry.import_id)
                self._write_direct_exclusive(directory, "owner.json", owner_payload)
                require_verified_import_lock(import_lock, import_id=entry.import_id)
                sync_directory(directory)
                require_verified_import_lock(import_lock, import_id=entry.import_id)
                self._write_and_publish(
                    directory,
                    temporary_name,
                    generation_name,
                    payload,
                )
                loaded, raw, _identity = self._read_generation(
                    directory, generation_name
                )
                if loaded != entry or raw != payload:
                    raise RecoveryRequired()
                return loaded
        except Exception as error:
            if isinstance(error, (JournalCorrupt, RecoveryRequired)):
                raise
            raise RecoveryRequired(error) from error

    def _read_owner(self, directory) -> tuple[JournalOwnerRecordV2, bytes]:
        raw, _identity = self._read_bound_bytes(directory, "owner.json")
        try:
            owner = JournalOwnerRecordV2.from_dict(
                parse_bounded_json_object(raw, "Schema 3 journal owner")
            )
        except Exception as error:
            raise JournalCorrupt(error) from error
        return owner, raw

    def _read_generation(self, directory, name: str, *, temporary: bool = False):
        raw, identity = self._read_bound_bytes(directory, name)
        try:
            entry = OperationalJournalGenerationV3.from_dict(
                parse_bounded_json_object(raw, "Schema 3 journal generation")
            )
        except Exception as error:
            raise JournalCorrupt(error) from error
        if not temporary and name != self.generation_name(
            entry.generation, entry.transition_id
        ):
            raise JournalCorrupt()
        return entry, raw, identity

    def _publish_existing(
        self, directory, temporary_name: str, final_name: str
    ) -> None:
        """Publish a verified candidate while retaining Windows delete sharing."""

        path = directory.path / temporary_name
        with open_existing_binary_for_delete(path) as handle:
            publish_open_file_no_replace_in_directory(
                handle,
                directory,
                temporary_name,
                final_name,
            )
        sync_directory(directory)

    def _reconcile_successor_candidate(
        self,
        directory,
        previous: OperationalJournalGenerationV3,
        temporary_name: str,
    ) -> None:
        """Delete only syntactically incomplete candidates; preserve conflicts."""

        raw, _identity = self._read_bound_bytes(directory, temporary_name)
        try:
            value = parse_bounded_json_object(
                raw, "Schema 3 successor candidate"
            )
        except Exception:
            self._delete_incomplete_candidate(directory, temporary_name)
            return
        try:
            entry = OperationalJournalGenerationV3.from_dict(value)
        except Exception as error:
            raise JournalCorrupt(error) from error
        if (
            entry.generation != previous.generation + 1
            or entry.previous_generation_sha256
            != sha256(canonical_json_bytes(previous.to_dict())).hexdigest()
        ):
            raise JournalCorrupt()
        self._validate_immutable(previous, entry)
        self._validate_transition(previous, entry)
        self._publish_existing(
            directory,
            temporary_name,
            self.generation_name(entry.generation, entry.transition_id),
        )

    @staticmethod
    def _validate_immutable(
        first: OperationalJournalGenerationV3,
        current: OperationalJournalGenerationV3,
    ) -> None:
        for field in (
            "journal_schema_version",
            "import_id",
            "random_ownership_token",
            "created_at",
            "package_sha256",
            "package_version",
            "package_basename",
            "snapshot_byte_length",
            "processed_media_commitment",
            "collection_baseline_sha256_or_sentinel",
            "collection_baseline_byte_length",
            "selected_source_coin_ids",
            "desktop_item_ids",
            "import_root_relative_path",
            "expected_image_inventory",
            "proposed_count",
            "skipped_count",
        ):
            if getattr(first, field) != getattr(current, field):
                raise JournalCorrupt()

    @staticmethod
    def _validate_transition(
        previous: OperationalJournalGenerationV3,
        current: OperationalJournalGenerationV3,
    ) -> None:
        """Reject transitions outside the frozen Schema 2+3 allowlists."""

        if previous.processed_media_commitment != current.processed_media_commitment:
            raise JournalCorrupt()
        if previous.processed_snapshot_reference != current.processed_snapshot_reference:
            envelope = {
                "generation",
                "previous_generation_sha256",
                "transition_id",
                "next_generation_token",
                "updated_at",
            }
            changed = {
                name
                for name in previous.__dataclass_fields__
                if name not in envelope
                and getattr(previous, name) != getattr(current, name)
            }
            if (
                changed != {"processed_snapshot_reference"}
                or previous.processed_snapshot_reference is None
                or current.processed_snapshot_reference is not None
                or previous.phase is not current.phase
                or current.phase
                not in {
                    ImportPhase.COLLECTION_COMMITTED,
                    ImportPhase.ROLLING_BACK,
                }
                or not any(
                    (
                        operation.status.value == "COMPLETE"
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
                    for operation in current.cleanup_operations
                )
            ):
                raise JournalCorrupt()
            return
        if any(
            len(operation.targets) > 301
            for operation in (
                *previous.cleanup_operations,
                *current.cleanup_operations,
            )
        ):
            Schema3PackageImportJournalRepository._validate_wide_cleanup_transition(
                previous, current
            )
            return
        Schema2PackageImportJournalRepository._validate_transition(
            previous.schema2_projection(),
            current.schema2_projection(),
        )

    @staticmethod
    def _validate_wide_cleanup_transition(previous, current) -> None:
        envelope = {
            "generation",
            "previous_generation_sha256",
            "transition_id",
            "next_generation_token",
            "updated_at",
        }
        changed = {
            name
            for name in previous.__dataclass_fields__
            if name not in envelope
            and getattr(previous, name) != getattr(current, name)
        }
        if not changed <= {
            "cleanup_operations",
            "package_snapshot_relative_path",
        } or "cleanup_operations" not in changed:
            raise JournalCorrupt()
        if len(current.cleanup_operations) == len(previous.cleanup_operations) + 1:
            if current.cleanup_operations[:-1] != previous.cleanup_operations:
                raise JournalCorrupt()
            operation = current.cleanup_operations[-1]
            if operation.status.value != "INTENT" or operation.receipts:
                raise JournalCorrupt()
            return
        if len(current.cleanup_operations) != len(previous.cleanup_operations):
            raise JournalCorrupt()
        if current.cleanup_operations[:-1] != previous.cleanup_operations[:-1]:
            raise JournalCorrupt()
        before = previous.cleanup_operations[-1]
        after = current.cleanup_operations[-1]
        if before.targets != after.targets or before.intent_id != after.intent_id:
            raise JournalCorrupt()
        if (
            before.status.value == "INTENT"
            and after.status.value == "INTENT"
            and len(after.receipts) == len(before.receipts) + 1
            and after.receipts[:-1] == before.receipts
        ):
            return
        if (
            before.status.value == "INTENT"
            and after.status.value == "COMPLETE"
            and before.receipts == after.receipts
            and len(after.receipts) == len(after.targets)
        ):
            return
        raise JournalCorrupt()


class VersionedPackageImportJournalRepository:
    """Dispatch closed Schema 2 and Schema 3 state without reinterpretation."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        token_factory: TokenFactory = lambda: str(uuid4()),
    ) -> None:
        self._root = Path(root).absolute()
        self._schema2 = Schema2PackageImportJournalRepository(
            self._root, token_factory=token_factory
        )
        self._schema3 = Schema3PackageImportJournalRepository(
            self._root, token_factory=token_factory
        )

    @property
    def root(self) -> Path:
        return self._root

    def create(
        self,
        entry: OperationalJournalGeneration | OperationalJournalGenerationV3,
        *,
        import_lock: PackageImportLock,
    ) -> OperationalJournalGeneration | OperationalJournalGenerationV3:
        if isinstance(entry, OperationalJournalGenerationV3):
            return self._schema3.create(entry, import_lock=import_lock)
        if isinstance(entry, OperationalJournalGeneration):
            return self._schema2.create(entry, import_lock=import_lock)
        raise TypeError("Unsupported operational journal generation type.")

    def append(
        self,
        previous: OperationalJournalGeneration | OperationalJournalGenerationV3,
        current: OperationalJournalGeneration | OperationalJournalGenerationV3,
        *,
        import_lock: PackageImportLock,
    ) -> OperationalJournalGeneration | OperationalJournalGenerationV3:
        if isinstance(previous, OperationalJournalGenerationV3) and isinstance(
            current, OperationalJournalGenerationV3
        ):
            return self._schema3.append(
                previous, current, import_lock=import_lock
            )
        if isinstance(previous, OperationalJournalGeneration) and isinstance(
            current, OperationalJournalGeneration
        ):
            return self._schema2.append(
                previous, current, import_lock=import_lock
            )
        raise JournalCorrupt()

    def _version_for(self, import_id: str) -> str:
        import_root = self._schema2._import_root(import_id)
        with open_plain_directory_handle(import_root) as directory:
            raw, _identity = self._schema2._read_bound_bytes(
                directory, "owner.json"
            )
        try:
            value = parse_bounded_json_object(raw, "versioned journal owner")
            owner_version = value["owner_schema_version"]
            journal_version = value["journal_schema_version"]
        except Exception as error:
            raise JournalCorrupt(error) from error
        pair = (owner_version, journal_version)
        if pair == ("1.0", "2.0"):
            JournalOwnerRecord.from_dict(value)
            return "2.0"
        if pair == ("2.0", "3.0"):
            JournalOwnerRecordV2.from_dict(value)
            return "3.0"
        raise JournalCorrupt()

    def load(
        self,
        import_id: str,
        *,
        import_lock: PackageImportLock,
    ) -> OperationalJournalGeneration | OperationalJournalGenerationV3:
        require_verified_import_lock(import_lock, import_id=import_id)
        version = self._version_for(import_id)
        if version == "2.0":
            return self._schema2.load(import_id, import_lock=import_lock)
        return self._schema3.load(import_id, import_lock=import_lock)

    def load_chain(
        self,
        import_id: str,
        *,
        import_lock: PackageImportLock,
    ) -> tuple[OperationalJournalGeneration | OperationalJournalGenerationV3, ...]:
        require_verified_import_lock(import_lock, import_id=import_id)
        version = self._version_for(import_id)
        if version == "2.0":
            return self._schema2.load_chain(import_id, import_lock=import_lock)
        return self._schema3.load_chain(import_id, import_lock=import_lock)

    def list_heads(
        self,
        *,
        import_lock: PackageImportLock,
        validated_legacy_names: frozenset[str] = frozenset(),
    ) -> tuple[OperationalJournalGeneration | OperationalJournalGenerationV3, ...]:
        require_verified_import_lock(import_lock)
        if not self._root.exists():
            return ()
        require_plain_directory(self._root)
        names = sorted(os.listdir(self._root))
        if len(names) > MAX_IMPORT_STATE_MEMBERS:
            raise JournalCorrupt()
        heads: list[
            OperationalJournalGeneration | OperationalJournalGenerationV3
        ] = []
        seen: set[str] = set()
        for name in names:
            if name in validated_legacy_names:
                continue
            if name.startswith(".retire-"):
                raise RecoveryRequired()
            try:
                if str(UUID(name)) != name or name in seen:
                    raise ValueError
            except (ValueError, AttributeError) as error:
                raise JournalCorrupt(error) from error
            seen.add(name)
            heads.append(self.load(name, import_lock=import_lock))
        return tuple(heads)
