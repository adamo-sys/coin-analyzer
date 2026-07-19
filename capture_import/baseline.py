"""Exact-byte collection baseline capture and comparison."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ._filesystem import require_plain_regular_file
from .errors import CollectionChanged
from .limits import MISSING_COLLECTION_SENTINEL
from .models import CollectionBaseline

DEFAULT_HASH_CHUNK_SIZE = 1024 * 1024


def capture_collection_baseline(
    collection_path: str | os.PathLike[str],
    *,
    chunk_size: int = DEFAULT_HASH_CHUNK_SIZE,
) -> CollectionBaseline:
    """Hash the exact collection bytes, or return the normative missing sentinel."""

    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
        raise ValueError("chunk_size must be a positive integer.")
    path = Path(collection_path)
    try:
        before = require_plain_regular_file(path)
    except FileNotFoundError:
        return CollectionBaseline(MISSING_COLLECTION_SENTINEL, 0)
    except OSError as error:
        raise CollectionChanged(error) from error

    digest = hashlib.sha256()
    byte_length = 0
    try:
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise CollectionChanged()
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
                byte_length += len(chunk)
            after_handle = os.fstat(handle.fileno())
        after_path = require_plain_regular_file(path)
    except CollectionChanged:
        raise
    except OSError as error:
        raise CollectionChanged(error) from error

    stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if any(
        getattr(before, field) != getattr(after_handle, field)
        or getattr(before, field) != getattr(after_path, field)
        for field in stable_fields
    ) or byte_length != before.st_size:
        raise CollectionChanged()
    return CollectionBaseline(digest.hexdigest(), byte_length)


def collection_matches_baseline(
    collection_path: str | os.PathLike[str], baseline: CollectionBaseline
) -> bool:
    """Return whether the collection's current exact bytes match ``baseline``."""

    if not isinstance(baseline, CollectionBaseline):
        raise ValueError("baseline must be a CollectionBaseline.")
    baseline.validate()
    return capture_collection_baseline(collection_path) == baseline


def require_collection_baseline(
    collection_path: str | os.PathLike[str], baseline: CollectionBaseline
) -> None:
    """Raise a sanitized error unless the exact collection baseline still matches."""

    if not collection_matches_baseline(collection_path, baseline):
        raise CollectionChanged()
