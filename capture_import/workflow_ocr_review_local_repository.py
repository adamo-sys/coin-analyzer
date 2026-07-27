"""Concrete local storage for versioned OCR review-session envelopes.

The repository owns only deterministic JSON storage beneath an explicitly
injected root.  It does not choose that root, create a global instance, migrate
data, or integrate persistence with desktop workflows.

Simultaneous writers, cross-process locking, optimistic concurrency,
stale-write detection, directory-entry fsync durability, and backup/rollback
policy are deferred.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import tempfile
from typing import BinaryIO

from ._json import canonical_json_bytes, parse_bounded_json_object
from .limits import MAX_JSON_BYTES
from .workflow_ocr_review_persistence_models import (
    OCRReviewSessionEnvelope,
    UnsupportedOCRReviewSessionSchemaVersion,
)


_MAX_SESSION_ID_CHARS = 256
_SESSION_FILE_SUFFIX = ".json"
_TEMPORARY_FILE_SUFFIX = ".tmp"


class OCRReviewSessionRepositoryError(Exception):
    """A local review-session repository operation could not be completed."""


class OCRReviewSessionCorruptError(OCRReviewSessionRepositoryError):
    """Stored review-session content is malformed or internally inconsistent."""


class OCRReviewSessionWriteError(OCRReviewSessionRepositoryError):
    """A review-session envelope could not be written atomically."""


class LocalOCRReviewSessionRepository:
    """Store one canonical JSON document per opaque review-session identity."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        try:
            raw_root = os.fspath(root)
        except TypeError as error:
            raise TypeError("root must be a path-like value.") from error
        if not isinstance(raw_root, str):
            raise TypeError("root must resolve to a text path.")
        if not raw_root.strip():
            raise ValueError("root must not be blank.")
        self._root = Path(raw_root).absolute()

    @property
    def root(self) -> Path:
        """Return the explicitly configured repository root."""

        return self._root

    def save(self, envelope: OCRReviewSessionEnvelope) -> None:
        """Create or atomically replace one validated session document."""

        if not isinstance(envelope, OCRReviewSessionEnvelope):
            raise TypeError(
                "envelope must be an OCRReviewSessionEnvelope."
            )
        envelope.validate()
        target = self._path(envelope.session_id)
        payload = canonical_json_bytes(envelope.to_dict())

        descriptor: int | None = None
        temporary: Path | None = None
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            if not self._root.is_dir():
                raise OSError("Repository root is not a directory.")
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.stem}.",
                suffix=_TEMPORARY_FILE_SUFFIX,
                dir=self._root,
            )
            temporary = Path(temporary_name)
            _write_and_sync(descriptor, payload)
            descriptor = None
            os.replace(temporary, target)
            temporary = None
        except OSError as error:
            if descriptor is not None:
                _close_descriptor(descriptor)
            if temporary is not None:
                _remove_temporary(temporary)
            raise OCRReviewSessionWriteError(
                "OCR review session could not be written atomically."
            ) from error

    def get(self, session_id: str) -> OCRReviewSessionEnvelope | None:
        """Load and strictly validate one session, returning None if absent."""

        target = self._path(session_id)
        try:
            status = target.lstat()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise OCRReviewSessionRepositoryError(
                "OCR review session could not be accessed."
            ) from error
        if not stat.S_ISREG(status.st_mode):
            raise OCRReviewSessionCorruptError(
                "OCR review session path is not a regular file."
            )

        try:
            with target.open("rb") as handle:
                raw = handle.read(MAX_JSON_BYTES + 1)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise OCRReviewSessionRepositoryError(
                "OCR review session could not be read."
            ) from error

        try:
            payload = parse_bounded_json_object(
                raw,
                "OCR review session",
            )
            envelope = OCRReviewSessionEnvelope.from_dict(payload)
            if envelope.session_id != session_id:
                raise ValueError(
                    "Stored OCR review session identity does not match "
                    "the requested identity."
                )
            return envelope
        except UnsupportedOCRReviewSessionSchemaVersion:
            raise
        except (TypeError, ValueError) as error:
            raise OCRReviewSessionCorruptError(
                "Stored OCR review session is corrupt."
            ) from error

    def exists(self, session_id: str) -> bool:
        """Return whether a regular session document exists."""

        target = self._path(session_id)
        try:
            status = target.lstat()
        except FileNotFoundError:
            return False
        except OSError as error:
            raise OCRReviewSessionRepositoryError(
                "OCR review session could not be accessed."
            ) from error
        if not stat.S_ISREG(status.st_mode):
            raise OCRReviewSessionRepositoryError(
                "OCR review session path is not a regular file."
            )
        return True

    def _path(self, session_id: str) -> Path:
        validated = _validate_session_id(session_id)
        digest = hashlib.sha256(validated.encode("utf-8")).hexdigest()
        return self._root / f"{digest}{_SESSION_FILE_SUFFIX}"


def _validate_session_id(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("session_id must be a string.")
    if not value.strip():
        raise ValueError("session_id must not be blank.")
    if len(value) > _MAX_SESSION_ID_CHARS:
        raise ValueError("session_id exceeds its character limit.")
    if value in {".", ".."}:
        raise ValueError("session_id must not be a traversal form.")
    if "/" in value or "\\" in value:
        raise ValueError("session_id must not contain path separators.")
    if (
        len(value) >= 2
        and value[0].isalpha()
        and value[1] == ":"
    ):
        raise ValueError("session_id must not contain a drive prefix.")
    return value


def _write_and_sync(
    descriptor: int,
    payload: bytes,
) -> None:
    with os.fdopen(descriptor, "wb") as handle:
        _write_all(handle, payload)
        _flush_and_sync(handle)


def _write_all(handle: BinaryIO, payload: bytes) -> None:
    written = handle.write(payload)
    if written != len(payload):
        raise OSError("Incomplete OCR review-session temporary write.")


def _flush_and_sync(handle: BinaryIO) -> None:
    handle.flush()
    os.fsync(handle.fileno())


def _close_descriptor(descriptor: int) -> None:
    try:
        os.close(descriptor)
    except OSError:
        pass


def _remove_temporary(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
