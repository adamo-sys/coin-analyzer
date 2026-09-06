"""Local-only discovery policy for the Phone Drop file picker.

This module deliberately chooses among explicit local directories only. It does
not enumerate devices, access cloud APIs, crawl folders, or mutate collection
state.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, MutableMapping, Sequence


PHONE_DROP_LAST_DIRECTORY_PREFERENCE = "phone_drop_last_source_directory"
PHONE_DROP_DISCOVERY_HINT = (
    "Apple Photos albums may not appear as Windows folders. Transfer/export the "
    "images to a local folder such as Pictures or Downloads, then select them here."
)


def load_last_phone_drop_directory(preferences: Mapping[str, object]) -> str:
    """Return the remembered Phone Drop source directory, if one is stored."""

    value = preferences.get(PHONE_DROP_LAST_DIRECTORY_PREFERENCE, "")
    return str(value).strip() if isinstance(value, (str, os.PathLike)) else ""


def save_last_phone_drop_directory(
    preferences: MutableMapping[str, object], directory: str | os.PathLike[str]
) -> str:
    """Store one normalized local source directory in the existing preference bag."""

    normalized = os.path.abspath(os.path.expanduser(os.fspath(directory)))
    preferences[PHONE_DROP_LAST_DIRECTORY_PREFERENCE] = normalized
    return normalized


def choose_phone_drop_initial_directory(
    remembered_directory: str | os.PathLike[str] | None = None,
    *,
    home_directory: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Choose the first existing useful local directory deterministically.

    Priority is remembered directory, Pictures, Downloads, OneDrive/Pictures,
    then a Windows OneDrive environment-root Pictures directory. If none exists,
    an existing home directory is returned; otherwise an empty string lets Tk use
    its safe default.
    """

    env = os.environ if environ is None else environ
    home = Path(home_directory).expanduser() if home_directory is not None else Path.home()

    candidates: list[Path] = []
    if remembered_directory:
        candidates.append(Path(remembered_directory).expanduser())
    candidates.extend((home / "Pictures", home / "Downloads", home / "OneDrive" / "Pictures"))

    one_drive_root = str(env.get("OneDrive", "") or "").strip()
    if one_drive_root:
        candidates.append(Path(one_drive_root).expanduser() / "Pictures")

    seen: set[str] = set()
    for candidate in candidates:
        normalized = os.path.abspath(os.fspath(candidate))
        key = os.path.normcase(normalized)
        if key in seen:
            continue
        seen.add(key)
        if os.path.isdir(normalized):
            return normalized

    normalized_home = os.path.abspath(os.fspath(home))
    return normalized_home if os.path.isdir(normalized_home) else ""


def remember_phone_drop_directory_after_import(
    preferences: MutableMapping[str, object],
    source_paths: Sequence[str | os.PathLike[str]],
    *,
    copied_count: int,
    duplicate_count: int,
) -> bool:
    """Remember discovery only after copied or duplicate-only import success."""

    if not source_paths or (copied_count <= 0 and duplicate_count <= 0):
        return False

    first_source = os.path.abspath(os.path.expanduser(os.fspath(source_paths[0])))
    parent = os.path.dirname(first_source)
    if not os.path.isdir(parent):
        return False

    save_last_phone_drop_directory(preferences, parent)
    return True
