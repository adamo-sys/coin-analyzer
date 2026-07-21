"""Bounded immutable package snapshots owned by the desktop importer."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path, PurePosixPath
import secrets
import socket
import stat
from typing import Any, BinaryIO, Callable, Iterable, Iterator, Mapping

from ._advisory import acquire_advisory_lock, release_advisory_lock
from ._filesystem import (
    delete_open_file,
    ensure_plain_directory,
    handle_object_identity,
    handle_matches_path,
    is_link_or_reparse,
    open_existing_binary_for_delete,
    open_exclusive_binary,
    path_object_identity,
    require_plain_directory,
    require_plain_regular_file,
)
from ._json import canonical_json_bytes, parse_bounded_json_object
from .errors import (
    PackageChanged,
    PackageNotFound,
    PackageTooLarge,
    SnapshotFailed,
    SnapshotRecoveryRequired,
)
from .durable_models import NativeObjectIdentity, OwnershipDescriptor
from .limits import MAX_JSON_BYTES, MAX_PACKAGE_SIZE, SNAPSHOT_SCHEMA_VERSION
from .lock import PackageImportLock, require_verified_import_lock
from .models import (
    _require_fields,
    _require_integer,
    _require_object,
    _require_string,
    _validate_relative_path,
    _validate_sha256,
    _validate_timestamp,
)

Clock = Callable[[], str]
TokenFactory = Callable[[], str]
ProcessLiveness = Callable[[int], bool]
FileIdentity = tuple[int, int]
DEFAULT_COPY_CHUNK_SIZE = 1024 * 1024
OWNER_FILENAME = "snapshot-owner.json"
LEASE_FILENAME = "snapshot.lease"
PACKAGE_FILENAME = "package.ca-package"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _token() -> str:
    return secrets.token_hex(32)


def _process_is_live(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _validate_snapshot_token(value: Any) -> str:
    text = _require_string(value, "snapshot_token", max_chars=64)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError("snapshot_token must be a 256-bit lowercase hexadecimal token.")
    return text


@dataclass(frozen=True, slots=True)
class SnapshotOwner:
    """Strict ownership record stored beside one temporary package snapshot."""

    snapshot_schema_version: str
    hostname: str
    process_id: int
    created_at: str
    snapshot_token: str

    def validate(self) -> None:
        if self.snapshot_schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("The snapshot schema version is not supported.")
        _require_string(self.hostname, "hostname", max_chars=255)
        _require_integer(self.process_id, "process_id", minimum=1)
        _validate_timestamp(self.created_at, "created_at")
        _validate_snapshot_token(self.snapshot_token)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "snapshot_schema_version": self.snapshot_schema_version,
            "hostname": self.hostname,
            "process_id": self.process_id,
            "created_at": self.created_at,
            "snapshot_token": self.snapshot_token,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SnapshotOwner":
        data = _require_object(value, "SnapshotOwner")
        required = frozenset(
            {
                "snapshot_schema_version",
                "hostname",
                "process_id",
                "created_at",
                "snapshot_token",
            }
        )
        _require_fields(data, required, "SnapshotOwner", allow_extra=False)
        result = cls(
            snapshot_schema_version=_require_string(
                data["snapshot_schema_version"], "snapshot_schema_version"
            ),
            hostname=_require_string(data["hostname"], "hostname", max_chars=255),
            process_id=_require_integer(data["process_id"], "process_id", minimum=1),
            created_at=_require_string(data["created_at"], "created_at"),
            snapshot_token=_require_string(
                data["snapshot_token"], "snapshot_token", max_chars=64
            ),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class SnapshotDescriptor:
    """Private relative identity of one accepted immutable package snapshot."""

    snapshot_token: str
    relative_path: str
    sha256: str
    byte_length: int

    def validate(self) -> None:
        token = _validate_snapshot_token(self.snapshot_token)
        path = _validate_relative_path(self.relative_path, "relative_path")
        if path != f"{token}/{PACKAGE_FILENAME}":
            raise ValueError("relative_path does not match the snapshot token.")
        _validate_sha256(self.sha256, "sha256")
        _require_integer(
            self.byte_length,
            "byte_length",
            minimum=1,
            maximum=MAX_PACKAGE_SIZE,
        )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "snapshot_token": self.snapshot_token,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SnapshotDescriptor":
        data = _require_object(value, "SnapshotDescriptor")
        required = frozenset(
            {"snapshot_token", "relative_path", "sha256", "byte_length"}
        )
        _require_fields(data, required, "SnapshotDescriptor", allow_extra=False)
        result = cls(
            snapshot_token=_require_string(
                data["snapshot_token"], "snapshot_token", max_chars=64
            ),
            relative_path=_require_string(data["relative_path"], "relative_path"),
            sha256=_require_string(data["sha256"], "sha256", max_chars=64),
            byte_length=_require_integer(
                data["byte_length"],
                "byte_length",
                minimum=1,
                maximum=MAX_PACKAGE_SIZE,
            ),
        )
        result.validate()
        return result


class SnapshotHandle:
    """Held advisory lease and immutable descriptor for an accepted snapshot."""

    def __init__(
        self,
        service: "CapturePackageSnapshotService",
        descriptor: SnapshotDescriptor,
        owner: SnapshotOwner,
        lease_handle: BinaryIO,
        root_identity: FileIdentity,
        directory_identity: FileIdentity,
        owner_identity: FileIdentity,
    ) -> None:
        self._service = service
        self.descriptor = descriptor
        self.owner = owner
        self._lease_handle = lease_handle
        self._root_identity = root_identity
        self._directory_identity = directory_identity
        self._owner_identity = owner_identity
        self._cleaned = False

    @property
    def is_active(self) -> bool:
        return not self._cleaned and not self._lease_handle.closed

    def validate(self) -> None:
        self._service.validate_snapshot(self)

    @contextmanager
    def open_package(self) -> Iterator[BinaryIO]:
        """Open the protected package through an identity-checked read lease."""

        with self._service.open_snapshot(self) as package:
            yield package

    def cleanup(self) -> None:
        self._service.cleanup_snapshot(self)

    def preserve_for_recovery(self) -> None:
        """Close the live lease while deliberately retaining owned evidence."""

        self._service.preserve_snapshot(self)

    def ownership_descriptors(
        self, import_ownership_token: str
    ) -> tuple[OwnershipDescriptor, ...]:
        """Return the exact snapshot cleanup inventory while the lease is held."""

        return self._service.ownership_descriptors(self, import_ownership_token)

    def __enter__(self) -> "SnapshotHandle":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.cleanup()


class CapturePackageSnapshotService:
    """Create, verify, and remove exact importer-owned snapshot directories."""

    def __init__(
        self,
        snapshot_root: str | os.PathLike[str],
        *,
        maximum_package_size: int = MAX_PACKAGE_SIZE,
        chunk_size: int = DEFAULT_COPY_CHUNK_SIZE,
        clock: Clock = _utc_now,
        token_factory: TokenFactory = _token,
        process_id: int | None = None,
        hostname: str | None = None,
        process_is_live: ProcessLiveness = _process_is_live,
    ) -> None:
        if (
            isinstance(maximum_package_size, bool)
            or not isinstance(maximum_package_size, int)
            or not 1 <= maximum_package_size <= MAX_PACKAGE_SIZE
        ):
            raise ValueError("maximum_package_size is outside its supported range.")
        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer.")
        self._root = Path(snapshot_root).absolute()
        self._maximum_package_size = maximum_package_size
        self._chunk_size = chunk_size
        self._clock = clock
        self._token_factory = token_factory
        self._process_id = os.getpid() if process_id is None else process_id
        self._hostname = socket.gethostname() if hostname is None else hostname
        self._process_is_live = process_is_live

    @property
    def root(self) -> Path:
        return self._root

    def cleanup_orphaned_snapshots(
        self,
        referenced_relative_paths: Iterable[str],
        *,
        import_lock: PackageImportLock,
    ) -> tuple[str, ...]:
        """Remove only proven, inactive, unjournaled snapshot directories."""

        require_verified_import_lock(import_lock)
        references = set()
        try:
            for value in referenced_relative_paths:
                references.add(_validate_relative_path(value, "snapshot reference"))
            if not self._root.exists():
                return ()
            require_plain_directory(self._root)
            root_identity = path_object_identity(self._root)
            removed: list[str] = []
            for directory in sorted(self._root.iterdir(), key=lambda path: path.name):
                if is_link_or_reparse(directory) or not directory.is_dir():
                    raise SnapshotRecoveryRequired()
                token = _validate_snapshot_token(directory.name)
                relative_path = f"{token}/{PACKAGE_FILENAME}"
                if relative_path in references:
                    continue
                require_verified_import_lock(import_lock)
                if self._cleanup_one_orphan(directory, token, root_identity):
                    removed.append(relative_path)
            return tuple(removed)
        except SnapshotRecoveryRequired:
            raise
        except (OSError, ValueError) as error:
            raise SnapshotRecoveryRequired(error) from error

    def _cleanup_one_orphan(
        self, directory: Path, token: str, root_identity: FileIdentity
    ) -> bool:
        self._verify_snapshot_children(directory, require_complete=True)
        owner_path = directory / OWNER_FILENAME
        owner, owner_identity = self._read_owner_with_identity(owner_path)
        if owner.snapshot_token != token or owner.hostname != self._hostname:
            raise SnapshotRecoveryRequired()
        lease_path = directory / LEASE_FILENAME
        lease_handle = open_existing_binary_for_delete(lease_path)
        locked = False
        try:
            try:
                acquire_advisory_lock(lease_handle)
                locked = True
            except BlockingIOError:
                return False
            if self._process_is_live(owner.process_id):
                raise SnapshotRecoveryRequired()
            package_path = directory / PACKAGE_FILENAME
            require_plain_regular_file(package_path)
            digest = hashlib.sha256()
            byte_length = 0
            with package_path.open("rb") as package_handle:
                while True:
                    chunk = package_handle.read(self._chunk_size)
                    if not chunk:
                        break
                    byte_length += len(chunk)
                    if byte_length > self._maximum_package_size:
                        raise SnapshotRecoveryRequired()
                    digest.update(chunk)
            descriptor = SnapshotDescriptor(
                snapshot_token=token,
                relative_path=f"{token}/{PACKAGE_FILENAME}",
                sha256=digest.hexdigest(),
                byte_length=byte_length,
            )
            descriptor.validate()
            handle = SnapshotHandle(
                self,
                descriptor,
                owner,
                lease_handle,
                root_identity,
                path_object_identity(directory),
                owner_identity,
            )
            self.validate_snapshot(handle)
            handle.cleanup()
            return True
        except SnapshotRecoveryRequired:
            raise
        except (OSError, ValueError) as error:
            raise SnapshotRecoveryRequired(error) from error
        finally:
            if not lease_handle.closed:
                if locked:
                    try:
                        release_advisory_lock(lease_handle)
                    except OSError:
                        pass
                lease_handle.close()

    def create_snapshot(
        self,
        source_path: str | os.PathLike[str],
        validation_sha256: str,
    ) -> SnapshotHandle:
        """Copy a source package once through a bounded, digesting stream."""

        _validate_sha256(validation_sha256, "validation_sha256")
        source = Path(source_path)
        try:
            source_before = require_plain_regular_file(source)
        except FileNotFoundError as error:
            raise PackageNotFound(error) from error
        except OSError as error:
            raise SnapshotFailed(error) from error
        if source_before.st_size < 1 or source_before.st_size > self._maximum_package_size:
            raise PackageTooLarge()

        token = _validate_snapshot_token(self._token_factory())
        owner = SnapshotOwner(
            snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
            hostname=self._hostname,
            process_id=self._process_id,
            created_at=self._clock(),
            snapshot_token=token,
        )
        owner.validate()
        directory = self._root / token
        owner_path = directory / OWNER_FILENAME
        lease_path = directory / LEASE_FILENAME
        package_path = directory / PACKAGE_FILENAME
        lease_handle: BinaryIO | None = None
        directory_created = False

        try:
            ensure_plain_directory(self._root)
            os.mkdir(directory, 0o700)
            directory_created = True
            self._write_exclusive(owner_path, canonical_json_bytes(owner.to_dict()))
            lease_handle = self._open_exclusive(lease_path)
            acquire_advisory_lock(lease_handle)
            lease_handle.flush()
            os.fsync(lease_handle.fileno())
            digest, byte_length = self._copy_exclusive(source, package_path)
            source_after = require_plain_regular_file(source)
            stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
            if any(
                getattr(source_before, field) != getattr(source_after, field)
                for field in stable_fields
            ):
                raise PackageChanged()
            if byte_length != source_before.st_size or digest != validation_sha256:
                raise PackageChanged()
            try:
                package_path.chmod(stat.S_IREAD)
            except OSError as error:
                raise SnapshotFailed(error) from error
            descriptor = SnapshotDescriptor(
                snapshot_token=token,
                relative_path=f"{token}/{PACKAGE_FILENAME}",
                sha256=digest,
                byte_length=byte_length,
            )
            descriptor.validate()
            root_identity = path_object_identity(self._root)
            directory_identity = path_object_identity(directory)
            require_plain_regular_file(owner_path)
            owner_identity = path_object_identity(owner_path)
            return SnapshotHandle(
                self,
                descriptor,
                owner,
                lease_handle,
                root_identity,
                directory_identity,
                owner_identity,
            )
        except (PackageChanged, PackageTooLarge):
            if directory_created:
                self._cleanup_failed_create(directory, lease_handle)
            raise
        except Exception as error:
            try:
                if directory_created:
                    self._cleanup_failed_create(directory, lease_handle)
            except SnapshotRecoveryRequired:
                raise
            if isinstance(error, SnapshotFailed):
                raise
            raise SnapshotFailed(error) from error
        finally:
            if not directory_created and lease_handle is not None and not lease_handle.closed:
                lease_handle.close()

    def resume_snapshot(
        self,
        relative_path: str,
        sha256: str,
        byte_length: int,
    ) -> SnapshotHandle:
        """Reacquire the exact durable snapshot lease for proven recovery."""

        parts = PurePosixPath(relative_path).parts
        if len(parts) != 2 or parts[1] != PACKAGE_FILENAME:
            raise SnapshotRecoveryRequired()
        descriptor = SnapshotDescriptor(parts[0], relative_path, sha256, byte_length)
        descriptor.validate()
        directory = self._snapshot_directory(descriptor)
        owner_path = directory / OWNER_FILENAME
        lease_path = directory / LEASE_FILENAME
        lease_handle: BinaryIO | None = None
        try:
            self._verify_snapshot_children(directory, require_complete=True)
            owner, owner_identity = self._read_owner_with_identity(owner_path)
            if owner.snapshot_token != descriptor.snapshot_token:
                raise SnapshotRecoveryRequired()
            lease_handle = open_existing_binary_for_delete(lease_path)
            acquire_advisory_lock(lease_handle)
            handle = SnapshotHandle(
                self,
                descriptor,
                owner,
                lease_handle,
                path_object_identity(self._root),
                path_object_identity(directory),
                owner_identity,
            )
            self.validate_snapshot(handle)
            return handle
        except SnapshotRecoveryRequired:
            if lease_handle is not None and not lease_handle.closed:
                try:
                    release_advisory_lock(lease_handle)
                except OSError:
                    pass
                lease_handle.close()
            raise
        except (BlockingIOError, OSError, ValueError) as error:
            if lease_handle is not None and not lease_handle.closed:
                try:
                    release_advisory_lock(lease_handle)
                except OSError:
                    pass
                lease_handle.close()
            raise SnapshotRecoveryRequired(error) from error

    def validate_snapshot(self, handle: SnapshotHandle) -> None:
        """Rehash the accepted snapshot and reject any integrity change."""

        try:
            self._verify_snapshot_binding(handle)
            package_path = self._path_for(handle.descriptor)
            before = require_plain_regular_file(package_path)
            if (
                before.st_size != handle.descriptor.byte_length
                or before.st_size > self._maximum_package_size
            ):
                raise PackageChanged()
            digest = hashlib.sha256()
            byte_length = 0
            with package_path.open("rb") as package:
                opened = os.fstat(package.fileno())
                if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                    raise PackageChanged()
                while True:
                    chunk = package.read(self._chunk_size)
                    if not chunk:
                        break
                    byte_length += len(chunk)
                    if byte_length > self._maximum_package_size:
                        raise PackageChanged()
                    digest.update(chunk)
                after_handle = os.fstat(package.fileno())
            after = require_plain_regular_file(package_path)
        except (OSError, SnapshotRecoveryRequired) as error:
            raise PackageChanged(error) from error
        stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
        if any(
            getattr(before, field) != getattr(after_handle, field)
            or getattr(before, field) != getattr(after, field)
            for field in stable_fields
        ):
            raise PackageChanged()
        if (
            digest.hexdigest() != handle.descriptor.sha256
            or byte_length != handle.descriptor.byte_length
        ):
            raise PackageChanged()

    @contextmanager
    def open_snapshot(self, handle: SnapshotHandle) -> Iterator[BinaryIO]:
        """Yield the exact accepted snapshot and verify it before and after use."""

        self.validate_snapshot(handle)
        package: BinaryIO | None = None
        try:
            package_path = self._path_for(handle.descriptor)
            before = require_plain_regular_file(package_path)
            package = package_path.open("rb")
            opened = os.fstat(package.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                package.close()
                raise PackageChanged()
            self._verify_snapshot_binding(handle)
            if not handle_matches_path(package, package_path):
                package.close()
                raise PackageChanged()
        except (OSError, SnapshotRecoveryRequired) as error:
            if package is not None and not package.closed:
                package.close()
            raise PackageChanged(error) from error
        integrity_error: PackageChanged | None = None
        try:
            yield package
        finally:
            try:
                after_handle = os.fstat(package.fileno())
                stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
                if any(
                    getattr(opened, field) != getattr(after_handle, field)
                    for field in stable_fields
                ):
                    integrity_error = PackageChanged()
                self._verify_snapshot_binding(handle)
                if not handle_matches_path(package, package_path):
                    integrity_error = PackageChanged()
            except OSError as error:
                integrity_error = PackageChanged(error)
            except SnapshotRecoveryRequired as error:
                integrity_error = PackageChanged(error)
            finally:
                package.close()
            try:
                self.validate_snapshot(handle)
            except PackageChanged as error:
                integrity_error = error
            if integrity_error is not None:
                raise integrity_error

    def cleanup_snapshot(self, handle: SnapshotHandle) -> None:
        """Idempotently remove only the exact snapshot owned by ``handle``."""

        if handle._cleaned:
            return
        self._require_owned_handle(handle)
        descriptor = handle.descriptor
        directory = self._snapshot_directory(descriptor)
        owner_path = directory / OWNER_FILENAME
        lease_path = directory / LEASE_FILENAME
        package_path = directory / PACKAGE_FILENAME
        try:
            directory_identity = directory.lstat()
            self._verify_snapshot_children(directory, require_complete=True)
            if not handle_matches_path(handle._lease_handle, lease_path):
                raise SnapshotRecoveryRequired()
            owner = self._read_owner(owner_path)
            if owner != handle.owner or owner.snapshot_token != descriptor.snapshot_token:
                raise SnapshotRecoveryRequired()
            self._delete_regular_file(package_path)
            delete_open_file(handle._lease_handle, lease_path)
            release_advisory_lock(handle._lease_handle)
            handle._lease_handle.close()
            self._delete_regular_file(owner_path)
            final_identity = directory.lstat()
            if (
                final_identity.st_dev != directory_identity.st_dev
                or final_identity.st_ino != directory_identity.st_ino
                or is_link_or_reparse(directory)
            ):
                raise SnapshotRecoveryRequired()
            directory.rmdir()
            handle._cleaned = True
        except SnapshotRecoveryRequired:
            raise
        except (OSError, ValueError) as error:
            raise SnapshotRecoveryRequired(error) from error

    def ownership_descriptors(
        self, handle: SnapshotHandle, import_ownership_token: str
    ) -> tuple[OwnershipDescriptor, ...]:
        """Build identity-bound cleanup evidence for the active snapshot."""

        handle.validate()
        directory = self._snapshot_directory(handle.descriptor)
        parent_identity = NativeObjectIdentity.from_native(
            path_object_identity(self._root), windows=os.name == "nt"
        )
        directory_identity = NativeObjectIdentity.from_native(
            path_object_identity(directory), windows=os.name == "nt"
        )
        result: list[OwnershipDescriptor] = []
        for name in (PACKAGE_FILENAME, LEASE_FILENAME, OWNER_FILENAME):
            path = directory / name
            if name == LEASE_FILENAME:
                info = os.fstat(handle._lease_handle.fileno())
                position = handle._lease_handle.tell()
                handle._lease_handle.seek(0)
                payload = handle._lease_handle.read(self._maximum_package_size + 1)
                handle._lease_handle.seek(position)
                if not handle_matches_path(handle._lease_handle, path):
                    raise SnapshotRecoveryRequired()
                object_identity = handle_object_identity(handle._lease_handle)
            else:
                info = require_plain_regular_file(path)
                payload = path.read_bytes()
                object_identity = path_object_identity(path)
            digest = hashlib.sha256(payload).hexdigest()
            result.append(
                OwnershipDescriptor(
                    root="SNAPSHOT",
                    relative_path=f"{handle.descriptor.snapshot_token}/{name}",
                    object_kind="FILE",
                    ownership_token=import_ownership_token,
                    expected_byte_length=info.st_size,
                    expected_sha256=digest,
                    parent_identity=directory_identity,
                    object_identity=NativeObjectIdentity.from_native(
                        object_identity, windows=os.name == "nt"
                    ),
                )
            )
        result.append(
            OwnershipDescriptor(
                root="SNAPSHOT",
                relative_path=handle.descriptor.snapshot_token,
                object_kind="DIRECTORY",
                ownership_token=import_ownership_token,
                expected_byte_length=None,
                expected_sha256=None,
                parent_identity=parent_identity,
                object_identity=directory_identity,
            )
        )
        return tuple(result)

    def preserve_snapshot(self, handle: SnapshotHandle) -> None:
        """Verify ownership, then release only the lease without deleting files."""

        self._verify_snapshot_binding(handle)
        try:
            release_advisory_lock(handle._lease_handle)
            handle._lease_handle.close()
        except OSError as error:
            if not handle._lease_handle.closed:
                handle._lease_handle.close()
            raise SnapshotRecoveryRequired(error) from error

    def _require_owned_handle(self, handle: SnapshotHandle) -> None:
        if not isinstance(handle, SnapshotHandle) or handle._service is not self:
            raise ValueError("The snapshot handle belongs to a different service.")
        if not handle.is_active:
            raise SnapshotRecoveryRequired()
        handle.descriptor.validate()
        handle.owner.validate()

    def _verify_snapshot_binding(self, handle: SnapshotHandle) -> None:
        """Rebind a live handle to its root, directory, lease, and owner objects."""

        self._require_owned_handle(handle)
        directory = self._root / handle.descriptor.snapshot_token
        owner_path = directory / OWNER_FILENAME
        lease_path = directory / LEASE_FILENAME
        try:
            require_plain_directory(self._root)
            require_plain_directory(directory)
            if directory.parent != self._root:
                raise SnapshotRecoveryRequired()
            if path_object_identity(self._root) != handle._root_identity:
                raise SnapshotRecoveryRequired()
            if path_object_identity(directory) != handle._directory_identity:
                raise SnapshotRecoveryRequired()
            self._verify_snapshot_children(directory, require_complete=True)
            if not handle_matches_path(handle._lease_handle, lease_path):
                raise SnapshotRecoveryRequired()
            owner, owner_identity = self._read_owner_with_identity(owner_path)
            if owner_identity != handle._owner_identity or owner != handle.owner:
                raise SnapshotRecoveryRequired()
            if owner.snapshot_token != handle.descriptor.snapshot_token:
                raise SnapshotRecoveryRequired()
        except SnapshotRecoveryRequired:
            raise
        except (OSError, ValueError) as error:
            raise SnapshotRecoveryRequired(error) from error

    def _path_for(self, descriptor: SnapshotDescriptor) -> Path:
        return self._snapshot_directory(descriptor) / PACKAGE_FILENAME

    def _snapshot_directory(self, descriptor: SnapshotDescriptor) -> Path:
        descriptor.validate()
        directory = self._root / descriptor.snapshot_token
        try:
            require_plain_directory(self._root)
            require_plain_directory(directory)
            if (
                directory.parent != self._root
            ):
                raise SnapshotRecoveryRequired()
        except FileNotFoundError as error:
            raise SnapshotRecoveryRequired(error) from error
        return directory

    def _read_owner(self, path: Path) -> SnapshotOwner:
        owner, _ = self._read_owner_with_identity(path)
        return owner

    def _read_owner_with_identity(
        self, path: Path
    ) -> tuple[SnapshotOwner, FileIdentity]:
        require_plain_regular_file(path)
        with open_existing_binary_for_delete(path) as owner_handle:
            identity = handle_object_identity(owner_handle)
            if identity != path_object_identity(path):
                raise OSError("Snapshot owner identity changed while opening.")
            raw = owner_handle.read(MAX_JSON_BYTES + 1)
            if identity != handle_object_identity(owner_handle) or not handle_matches_path(
                owner_handle, path
            ):
                raise OSError("Snapshot owner identity changed while reading.")
        return (
            SnapshotOwner.from_dict(
                parse_bounded_json_object(raw, "snapshot owner metadata")
            ),
            identity,
        )

    def _open_exclusive(self, path: Path) -> BinaryIO:
        return open_exclusive_binary(path)

    def _delete_regular_file(self, path: Path) -> None:
        require_plain_regular_file(path)
        path.chmod(stat.S_IWRITE | stat.S_IREAD)
        with open_existing_binary_for_delete(path) as handle:
            delete_open_file(handle, path)

    def _verify_snapshot_children(
        self, directory: Path, *, require_complete: bool
    ) -> None:
        allowed = {OWNER_FILENAME, LEASE_FILENAME, PACKAGE_FILENAME}
        children: list[Path] = []
        for child in directory.iterdir():
            children.append(child)
            if len(children) > len(allowed):
                raise SnapshotRecoveryRequired()
        names = {child.name for child in children}
        if not names.issubset(allowed) or (require_complete and names != allowed):
            raise SnapshotRecoveryRequired()
        for child in children:
            try:
                require_plain_regular_file(child)
            except OSError as error:
                raise SnapshotRecoveryRequired(error) from error

    def _write_exclusive(self, path: Path, payload: bytes) -> None:
        with self._open_exclusive(path) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    def _copy_exclusive(self, source: Path, destination: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        byte_length = 0
        with source.open("rb") as source_handle, self._open_exclusive(destination) as target:
            while True:
                chunk = source_handle.read(self._chunk_size)
                if not chunk:
                    break
                byte_length += len(chunk)
                if byte_length > self._maximum_package_size:
                    raise PackageTooLarge()
                digest.update(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        if byte_length < 1:
            raise PackageTooLarge()
        return digest.hexdigest(), byte_length

    def _cleanup_failed_create(
        self, directory: Path, lease_handle: BinaryIO | None
    ) -> None:
        try:
            if not directory.exists():
                return
            if is_link_or_reparse(directory) or not directory.is_dir():
                raise OSError("Snapshot ownership cannot be proven.")
            self._verify_snapshot_children(directory, require_complete=False)
            for name in (PACKAGE_FILENAME,):
                path = directory / name
                if path.exists():
                    self._delete_regular_file(path)
            if lease_handle is not None and not lease_handle.closed:
                try:
                    delete_open_file(lease_handle, directory / LEASE_FILENAME)
                finally:
                    try:
                        release_advisory_lock(lease_handle)
                    except OSError:
                        pass
                    lease_handle.close()
            owner_path = directory / OWNER_FILENAME
            if owner_path.exists():
                self._delete_regular_file(owner_path)
            directory.rmdir()
        except OSError as error:
            raise SnapshotRecoveryRequired(error) from error
