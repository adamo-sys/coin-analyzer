"""Exclusive filesystem lease for package-import and collection-write work."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import secrets
import socket
import time
from typing import Any, BinaryIO, Callable, Mapping

from ._advisory import acquire_advisory_lock, release_advisory_lock
from ._filesystem import (
    delete_open_file,
    ensure_plain_directory,
    handle_matches_path,
    open_exclusive_binary,
)
from ._json import canonical_json_bytes, parse_bounded_json_object
from .errors import ImportLocked, RecoveryRequired
from .limits import (
    IMPORT_LOCK_SCHEMA_VERSION,
    MAX_JSON_BYTES,
    MAX_LOCK_POLL_SECONDS,
    MAX_LOCK_WAIT_SECONDS,
)
from .models import (
    _require_fields,
    _require_integer,
    _require_object,
    _require_optional_string,
    _require_string,
    _validate_timestamp,
    _validate_uuid,
)

Clock = Callable[[], str]
TokenFactory = Callable[[], str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _token() -> str:
    return secrets.token_hex(32)


def _validate_token(value: Any, field_name: str) -> str:
    text = _require_string(value, field_name, max_chars=64)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{field_name} must be a 256-bit lowercase hexadecimal token.")
    return text


@dataclass(frozen=True, slots=True)
class LockMetadata:
    """Strict bounded metadata written into the exclusive import lock."""

    schema_version: str
    process_id: int
    hostname: str
    created_at: str
    random_lock_token: str
    import_id: str | None

    def validate(self) -> None:
        if self.schema_version != IMPORT_LOCK_SCHEMA_VERSION:
            raise ValueError("The import-lock schema version is not supported.")
        _require_integer(self.process_id, "process_id", minimum=1)
        _require_string(self.hostname, "hostname", max_chars=255)
        _validate_timestamp(self.created_at, "created_at")
        _validate_token(self.random_lock_token, "random_lock_token")
        if self.import_id is not None:
            _validate_uuid(self.import_id, "import_id")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "process_id": self.process_id,
            "hostname": self.hostname,
            "created_at": self.created_at,
            "random_lock_token": self.random_lock_token,
            "import_id": self.import_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LockMetadata":
        data = _require_object(value, "LockMetadata")
        required = frozenset(
            {
                "schema_version",
                "process_id",
                "hostname",
                "created_at",
                "random_lock_token",
                "import_id",
            }
        )
        _require_fields(data, required, "LockMetadata", allow_extra=False)
        result = cls(
            schema_version=_require_string(data["schema_version"], "schema_version"),
            process_id=_require_integer(data["process_id"], "process_id", minimum=1),
            hostname=_require_string(data["hostname"], "hostname", max_chars=255),
            created_at=_require_string(data["created_at"], "created_at"),
            random_lock_token=_require_string(
                data["random_lock_token"], "random_lock_token", max_chars=64
            ),
            import_id=_require_optional_string(data["import_id"], "import_id"),
        )
        result.validate()
        return result


class PackageImportLock:
    """One non-reentrant exclusive import-lock lease."""

    def __init__(self, path: Path, metadata: LockMetadata, handle: BinaryIO) -> None:
        self._path = path
        self.metadata = metadata
        self._handle = handle
        self._released = False

    @classmethod
    def acquire(
        cls,
        lock_path: str | os.PathLike[str],
        *,
        import_id: str | None = None,
        wait_seconds: float = 0.0,
        poll_seconds: float = 0.05,
        clock: Clock = _utc_now,
        token_factory: TokenFactory = _token,
        process_id: int | None = None,
        hostname: str | None = None,
    ) -> "PackageImportLock":
        """Exclusively create, lock, flush, and return one held lease."""

        if isinstance(wait_seconds, bool) or not isinstance(wait_seconds, (int, float)):
            raise ValueError("wait_seconds must be numeric.")
        if isinstance(poll_seconds, bool) or not isinstance(poll_seconds, (int, float)):
            raise ValueError("poll_seconds must be numeric.")
        try:
            wait_value = float(wait_seconds)
            poll_value = float(poll_seconds)
        except OverflowError as error:
            raise ValueError(
                "Lock timing values are outside their supported range."
            ) from error
        if (
            not math.isfinite(wait_value)
            or not math.isfinite(poll_value)
            or not 0 <= wait_value <= MAX_LOCK_WAIT_SECONDS
            or not 0 < poll_value <= MAX_LOCK_POLL_SECONDS
        ):
            raise ValueError("Lock timing values are outside their supported range.")
        path = Path(lock_path).absolute()
        try:
            ensure_plain_directory(path.parent)
        except OSError as error:
            raise RecoveryRequired(error) from error
        metadata = LockMetadata(
            schema_version=IMPORT_LOCK_SCHEMA_VERSION,
            process_id=os.getpid() if process_id is None else process_id,
            hostname=socket.gethostname() if hostname is None else hostname,
            created_at=clock(),
            random_lock_token=token_factory(),
            import_id=import_id,
        )
        metadata.validate()
        payload = canonical_json_bytes(metadata.to_dict())
        deadline = time.monotonic() + wait_value

        while True:
            try:
                handle = open_exclusive_binary(path)
                break
            except FileExistsError as error:
                if time.monotonic() >= deadline:
                    raise ImportLocked() from error
                time.sleep(min(poll_value, max(0.0, deadline - time.monotonic())))
            except OSError as error:
                raise RecoveryRequired(error) from error

        locked = False
        try:
            acquire_advisory_lock(handle)
            locked = True
            handle.seek(0)
            handle.truncate()
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            return cls(path, metadata, handle)
        except Exception as error:
            cleanup_error: OSError | None = None
            try:
                delete_open_file(handle, path)
            except OSError as delete_error:
                cleanup_error = delete_error
            if locked:
                try:
                    release_advisory_lock(handle)
                except OSError:
                    pass
            handle.close()
            if cleanup_error is not None:
                raise RecoveryRequired(cleanup_error) from error
            if isinstance(error, BlockingIOError):
                raise ImportLocked() from error
            raise RecoveryRequired(error) from error

    @property
    def is_held(self) -> bool:
        return not self._released and not self._handle.closed

    def verify_ownership(self) -> LockMetadata:
        """Reread bounded metadata through the held handle and prove ownership."""

        if not self.is_held or not handle_matches_path(self._handle, self._path):
            raise RecoveryRequired()
        try:
            self._handle.seek(0)
            raw = self._handle.read(MAX_JSON_BYTES + 1)
            on_disk = LockMetadata.from_dict(
                parse_bounded_json_object(raw, "import lock metadata")
            )
        except (OSError, ValueError) as error:
            raise RecoveryRequired(error) from error
        if on_disk != self.metadata:
            raise RecoveryRequired()
        return on_disk

    def release(self) -> None:
        """Verify in-memory ownership, unlock, and delete only this exact lock."""

        if self._released:
            return
        try:
            self.verify_ownership()
            delete_open_file(self._handle, self._path)
            release_advisory_lock(self._handle)
            self._handle.close()
            self._released = True
        except RecoveryRequired:
            if not self._handle.closed:
                try:
                    release_advisory_lock(self._handle)
                finally:
                    self._handle.close()
            raise
        except (OSError, ValueError) as error:
            if not self._handle.closed:
                try:
                    release_advisory_lock(self._handle)
                except OSError:
                    pass
                self._handle.close()
            raise RecoveryRequired(error) from error

    def __enter__(self) -> "PackageImportLock":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()


def require_verified_import_lock(
    lease: PackageImportLock, *, import_id: str | None = None
) -> LockMetadata:
    """Prove the caller still owns the global importer lease.

    Schema-2 mutating services call this at every durable mutation boundary.
    A startup-recovery lease has a null import ID; an execution lease may be
    bound to the exact import ID.
    """

    if not isinstance(lease, PackageImportLock):
        raise RecoveryRequired()
    metadata = lease.verify_ownership()
    if (
        import_id is not None
        and metadata.import_id is not None
        and metadata.import_id != import_id
    ):
        raise RecoveryRequired()
    return metadata
