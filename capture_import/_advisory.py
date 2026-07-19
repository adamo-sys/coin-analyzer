"""Small cross-platform advisory-lock helpers for importer-owned files."""

from __future__ import annotations

import os
from typing import BinaryIO


def acquire_advisory_lock(handle: BinaryIO) -> None:
    """Acquire a non-blocking exclusive advisory lock on one open file."""

    if os.name == "nt":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise BlockingIOError("The advisory lock is already held.") from error
        return

    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        raise BlockingIOError("The advisory lock is already held.") from error


def release_advisory_lock(handle: BinaryIO) -> None:
    """Release an advisory lock previously acquired on ``handle``."""

    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
