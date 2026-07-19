"""Fail-closed filesystem primitives shared by Sprint 2 services."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import BinaryIO


def is_link_or_reparse(path: Path) -> bool:
    """Return whether ``path`` is a symlink or Windows reparse point."""

    info = path.lstat()
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & reparse_flag)


def ensure_plain_directory(path: Path) -> None:
    """Validate ancestors first, then create and verify one component at a time."""

    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        candidate = current / part
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            try:
                os.mkdir(candidate, 0o700)
            except FileExistsError:
                pass
            info = candidate.lstat()
        attributes = getattr(info, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if (
            stat.S_ISLNK(info.st_mode)
            or bool(attributes & reparse_flag)
            or not stat.S_ISDIR(info.st_mode)
        ):
            raise OSError("A required importer directory is not a plain directory.")
        current = candidate


def require_plain_directory(path: Path) -> None:
    """Require every existing component through ``path`` to be a plain directory."""

    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        info = current.lstat()
        attributes = getattr(info, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if (
            stat.S_ISLNK(info.st_mode)
            or bool(attributes & reparse_flag)
            or not stat.S_ISDIR(info.st_mode)
        ):
            raise OSError("An importer directory is not a plain directory.")


def require_plain_regular_file(path: Path) -> os.stat_result:
    """Return lstat data only for a non-link regular file."""

    info = path.lstat()
    if is_link_or_reparse(path) or not stat.S_ISREG(info.st_mode):
        raise OSError("The importer path is not a plain regular file.")
    return info


def handle_matches_path(handle: BinaryIO, path: Path) -> bool:
    """Return whether an open handle still names the same plain regular file."""

    try:
        path_info = require_plain_regular_file(path)
        handle_info = os.fstat(handle.fileno())
    except OSError:
        return False
    return (
        handle_info.st_dev == path_info.st_dev
        and handle_info.st_ino == path_info.st_ino
        and stat.S_ISREG(handle_info.st_mode)
    )


def open_exclusive_binary(path: Path) -> BinaryIO:
    """Exclusively create a binary file with delete rights on Windows."""

    if os.name != "nt":
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_BINARY", 0),
            0o600,
        )
        return os.fdopen(descriptor, "w+b", buffering=0)
    return _open_windows_binary(path, create_new=True)


def open_existing_binary_for_delete(path: Path) -> BinaryIO:
    """Open one existing plain file without following links, ready for deletion."""

    require_plain_regular_file(path)
    if os.name != "nt":
        flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        handle = os.fdopen(descriptor, "r+b", buffering=0)
    else:
        handle = _open_windows_binary(path, create_new=False)
    if not handle_matches_path(handle, path):
        handle.close()
        raise OSError("The opened file identity changed.")
    return handle


def delete_open_file(handle: BinaryIO, path: Path) -> None:
    """Delete the exact file represented by a still-open verified handle."""

    if not handle_matches_path(handle, path):
        raise OSError("The file identity changed before deletion.")
    if os.name != "nt":
        os.unlink(path)
        if os.fstat(handle.fileno()).st_nlink != 0:
            raise OSError("The verified file name was not removed.")
        return

    import ctypes
    import msvcrt

    class FileDispositionInfo(ctypes.Structure):
        _fields_ = [("delete_file", ctypes.c_int)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    operation = kernel32.SetFileInformationByHandle
    operation.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    operation.restype = ctypes.c_int
    disposition = FileDispositionInfo(1)
    windows_handle = msvcrt.get_osfhandle(handle.fileno())
    if not operation(
        windows_handle,
        4,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        error_code = ctypes.get_last_error()
        raise OSError(error_code, "The verified file could not be marked for deletion.")


def _open_windows_binary(path: Path, *, create_new: bool) -> BinaryIO:
    import ctypes
    import msvcrt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    )
    create_file.restype = ctypes.c_void_p
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (ctypes.c_void_p,)
    close_handle.restype = ctypes.c_int
    desired_access = 0x80000000 | 0x40000000 | 0x00010000
    disposition = 1 if create_new else 3
    raw_handle = create_file(
        str(path),
        desired_access,
        0,
        None,
        disposition,
        0x00000080,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if raw_handle == invalid_handle:
        error_code = ctypes.get_last_error()
        if create_new and error_code in {80, 183}:
            raise FileExistsError(error_code, "The destination already exists.", str(path))
        raise OSError(error_code, "The file could not be opened safely.", str(path))
    try:
        descriptor = msvcrt.open_osfhandle(
            raw_handle, os.O_RDWR | getattr(os, "O_BINARY", 0)
        )
    except Exception:
        close_handle(raw_handle)
        raise
    return os.fdopen(descriptor, "w+b" if create_new else "r+b", buffering=0)
