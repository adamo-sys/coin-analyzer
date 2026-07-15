"""Small, dependency-free helpers for durable JSON replacement."""

import json
import os
import tempfile
from typing import Any


def write_json_atomically(path: str, payload: Any, *, indent: int = 2, ensure_ascii: bool = False) -> None:
    """Write JSON via a same-directory temporary file and atomic replacement."""
    destination = os.path.abspath(path)
    directory = os.path.dirname(destination)
    os.makedirs(directory, exist_ok=True)

    fd, temporary_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(destination)}.",
        suffix=".tmp",
        dir=directory,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=indent, ensure_ascii=ensure_ascii)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    except Exception as error:
        try:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
        except OSError as cleanup_error:
            raise OSError(
                f"Atomic JSON write failed for {destination}; temporary file cleanup also failed: {cleanup_error}"
            ) from error
        raise
