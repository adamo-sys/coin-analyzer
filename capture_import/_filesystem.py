"""Fail-closed filesystem primitives shared by Sprint 2 services."""

from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

ObjectIdentity = tuple[int, int]


@dataclass
class PlainDirectoryHandle:
    """Held plain-directory identity used to bind pathname operations."""

    path: Path
    identity: ObjectIdentity
    descriptor: int | None = None
    windows_handle: int | None = None

    def close(self) -> None:
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.descriptor = None
        if self.windows_handle is not None:
            import ctypes

            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(
                self.windows_handle
            )
            self.windows_handle = None

    def __enter__(self) -> PlainDirectoryHandle:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def verify_path(self) -> bool:
        try:
            return path_object_identity(self.path) == self.identity
        except OSError:
            return False


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
        require_plain_regular_file(path)
        return handle_object_identity(handle) == path_object_identity(path)
    except OSError:
        return False


def handle_object_identity(handle: BinaryIO) -> ObjectIdentity:
    """Return the platform-native stable identity for one open object."""

    if os.name == "nt":
        import msvcrt

        return _windows_handle_identity(msvcrt.get_osfhandle(handle.fileno()))
    info = os.fstat(handle.fileno())
    return info.st_dev, info.st_ino


def path_object_identity(path: Path) -> ObjectIdentity:
    """Open and return the native identity of one plain file or directory."""

    if os.name != "nt":
        info = path.lstat()
        return info.st_dev, info.st_ino
    return _windows_path_identity(path)


def open_plain_directory_handle(path: Path) -> PlainDirectoryHandle:
    """Open and retain one plain directory without following substitutions."""

    require_plain_directory(path)
    if os.name != "nt":
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(
            os, "O_NOFOLLOW", 0
        )
        descriptor = os.open(path, flags)
        info = os.fstat(descriptor)
        identity = (info.st_dev, info.st_ino)
        result = PlainDirectoryHandle(path, identity, descriptor=descriptor)
    else:
        raw_handle = _windows_open_path(
            path,
            desired_access=0x00000080 | 0x00000001,
            share_mode=0x00000001 | 0x00000002 | 0x00000004,
            flags=0x02000000 | 0x00200000,
            message="The directory identity could not be opened safely.",
        )
        try:
            information = _windows_handle_information(raw_handle)
            _require_windows_plain_type(information, directory=True)
            result = PlainDirectoryHandle(
                path,
                _windows_file_id_information(raw_handle),
                windows_handle=raw_handle,
            )
        except Exception:
            import ctypes

            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(raw_handle)
            raise
    if not result.verify_path():
        result.close()
        raise OSError("The directory identity changed while it was opened.")
    return result


def open_plain_child_directory(
    parent: PlainDirectoryHandle, name: str
) -> PlainDirectoryHandle:
    """Open one plain child directory relative to a verified held parent."""

    _validate_child_name(name)
    if not parent.verify_path():
        raise OSError("The parent directory identity changed.")
    path = parent.path / name
    if os.name != "nt":
        if parent.descriptor is None:
            raise OSError("A held POSIX parent directory is required.")
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(
            os, "O_NOFOLLOW", 0
        )
        descriptor = os.open(name, flags, dir_fd=parent.descriptor)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISDIR(info.st_mode):
                raise OSError("The child object is not a directory.")
            result = PlainDirectoryHandle(
                path, (info.st_dev, info.st_ino), descriptor=descriptor
            )
        except Exception:
            os.close(descriptor)
            raise
    else:
        if parent.windows_handle is None:
            raise OSError("A held Windows parent directory is required.")
        raw_handle = _windows_open_relative_path(
            parent.windows_handle,
            name,
            desired_access=0x00000080 | 0x00100000,
            create_options=0x00000001 | 0x00000020 | 0x00200000,
            message="The child directory could not be opened safely.",
        )
        try:
            information = _windows_handle_information(raw_handle)
            _require_windows_plain_type(information, directory=True)
            result = PlainDirectoryHandle(
                path,
                _windows_file_id_information(raw_handle),
                windows_handle=raw_handle,
            )
        except Exception:
            import ctypes

            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(raw_handle)
            raise
    if (
        result.identity[0] != parent.identity[0]
        or not parent.verify_path()
        or not result.verify_path()
    ):
        result.close()
        raise OSError("The child directory binding changed or crossed a volume.")
    return result


def create_plain_child_directory(
    parent: PlainDirectoryHandle, name: str
) -> PlainDirectoryHandle:
    """Exclusively create and hold one plain child relative to ``parent``."""

    _validate_child_name(name)
    if not parent.verify_path():
        raise OSError("The parent directory identity changed.")
    path = parent.path / name
    if os.name != "nt":
        if parent.descriptor is None:
            raise OSError("A held POSIX parent directory is required.")
        os.mkdir(name, 0o700, dir_fd=parent.descriptor)
        try:
            result = open_plain_child_directory(parent, name)
        except Exception:
            try:
                os.rmdir(name, dir_fd=parent.descriptor)
            except OSError:
                pass
            raise
        return result

    if parent.windows_handle is None:
        raise OSError("A held Windows parent directory is required.")
    raw_handle = _windows_open_relative_path(
        parent.windows_handle,
        name,
        desired_access=0x00000001 | 0x00000080 | 0x00010000 | 0x00100000,
        create_options=0x00000001 | 0x00000020 | 0x00200000,
        disposition=2,
        file_attributes=0x00000010,
        message="The child directory could not be created safely.",
    )
    try:
        information = _windows_handle_information(raw_handle)
        _require_windows_plain_type(information, directory=True)
        result = PlainDirectoryHandle(
            path,
            _windows_file_id_information(raw_handle),
            windows_handle=raw_handle,
        )
    except Exception:
        import ctypes

        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(raw_handle)
        raise
    if (
        result.identity[0] != parent.identity[0]
        or not parent.verify_path()
        or not result.verify_path()
    ):
        result.close()
        raise OSError("The child directory binding changed or crossed a volume.")
    return result


def open_plain_child_file_readonly(
    parent: PlainDirectoryHandle, name: str
) -> BinaryIO:
    """Open one regular file relative to a verified held directory."""

    _validate_child_name(name)
    if not parent.verify_path():
        raise OSError("The parent directory identity changed.")
    path = parent.path / name
    if os.name != "nt":
        if parent.descriptor is None:
            raise OSError("A held POSIX parent directory is required.")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(
            os, "O_NOFOLLOW", 0
        )
        descriptor = os.open(name, flags, dir_fd=parent.descriptor)
        handle = os.fdopen(descriptor, "rb", buffering=0)
    else:
        if parent.windows_handle is None:
            raise OSError("A held Windows parent directory is required.")
        raw_handle = _windows_open_relative_path(
            parent.windows_handle,
            name,
            desired_access=0x80000000 | 0x00100000 | 0x00010000,
            create_options=0x00000040 | 0x00000020 | 0x00200000,
            message="The child file could not be opened safely.",
        )
        import msvcrt

        try:
            _require_windows_plain_type(
                _windows_handle_information(raw_handle), directory=False
            )
            descriptor = msvcrt.open_osfhandle(
                raw_handle, os.O_RDONLY | getattr(os, "O_BINARY", 0)
            )
        except Exception:
            import ctypes

            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(raw_handle)
            raise
        handle = os.fdopen(descriptor, "rb", buffering=0)
    try:
        if (
            handle_object_identity(handle)[0] != parent.identity[0]
            or not parent.verify_path()
            or not handle_matches_path(handle, path)
        ):
            raise OSError("The child file binding changed or crossed a volume.")
        require_dense_regular_handle(handle)
        return handle
    except Exception:
        handle.close()
        raise


def open_exclusive_child_binary(
    parent: PlainDirectoryHandle, name: str
) -> BinaryIO:
    """Exclusively create one regular file relative to a verified held parent."""

    _validate_child_name(name)
    if not parent.verify_path():
        raise OSError("The parent directory identity changed.")
    path = parent.path / name
    if os.name != "nt":
        if parent.descriptor is None:
            raise OSError("A held POSIX parent directory is required.")
        descriptor = os.open(
            name,
            os.O_CREAT
            | os.O_EXCL
            | os.O_RDWR
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent.descriptor,
        )
        handle = os.fdopen(descriptor, "w+b", buffering=0)
    else:
        if parent.windows_handle is None:
            raise OSError("A held Windows parent directory is required.")
        raw_handle = _windows_open_relative_path(
            parent.windows_handle,
            name,
            desired_access=(
                0x80000000 | 0x40000000 | 0x00010000 | 0x00100000
            ),
            create_options=0x00000040 | 0x00000020 | 0x00200000,
            disposition=2,
            file_attributes=0x00000080,
            message="The child file could not be created safely.",
        )
        import msvcrt

        try:
            _require_windows_plain_type(
                _windows_handle_information(raw_handle), directory=False
            )
            descriptor = msvcrt.open_osfhandle(
                raw_handle, os.O_RDWR | getattr(os, "O_BINARY", 0)
            )
        except Exception:
            import ctypes

            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(raw_handle)
            raise
        handle = os.fdopen(descriptor, "w+b", buffering=0)
    try:
        if (
            handle_object_identity(handle)[0] != parent.identity[0]
            or not parent.verify_path()
            or not handle_matches_path(handle, path)
        ):
            raise OSError("The child file binding changed or crossed a volume.")
        return handle
    except Exception:
        handle.close()
        raise


def _validate_child_name(name: str) -> None:
    if (
        not isinstance(name, str)
        or not name
        or name != Path(name).name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
    ):
        raise OSError("An importer child name is invalid.")


def require_dense_regular_handle(handle: BinaryIO) -> None:
    info = os.fstat(handle.fileno())
    if not stat.S_ISREG(info.st_mode):
        raise OSError("The importer object is not a regular file.")
    if os.name == "nt":
        import msvcrt

        attributes = _windows_handle_information(
            msvcrt.get_osfhandle(handle.fileno())
        ).file_attributes
        if attributes & (0x00000200 | 0x00001000 | 0x00040000 | 0x00400000):
            raise OSError("Sparse or placeholder files are not supported.")
    elif info.st_size > 0 and hasattr(info, "st_blocks"):
        if info.st_blocks * 512 < info.st_size:
            raise OSError("Sparse files are not supported.")


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

    class FileDispositionInfoEx(ctypes.Structure):
        _fields_ = [("flags", ctypes.c_uint32)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    operation = kernel32.SetFileInformationByHandle
    operation.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    operation.restype = ctypes.c_int
    disposition = FileDispositionInfoEx(
        0x00000001 | 0x00000002 | 0x00000010
    )
    windows_handle = msvcrt.get_osfhandle(handle.fileno())
    if not operation(
        windows_handle,
        21,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        error_code = ctypes.get_last_error()
        raise OSError(error_code, "The verified file could not be marked for deletion.")


def replace_open_file_in_directory(
    handle: BinaryIO, directory: PlainDirectoryHandle, filename: str
) -> None:
    """Atomically rename an open file relative to one held Windows directory."""

    if os.name != "nt" or directory.windows_handle is None:
        raise OSError("Native relative replacement is unavailable.")
    if not filename or filename != Path(filename).name:
        raise OSError("The replacement filename is invalid.")

    import ctypes
    import msvcrt

    class FileRenameInformation(ctypes.Structure):
        _fields_ = (
            ("flags", ctypes.c_uint32),
            ("root_directory", ctypes.c_void_p),
            ("file_name_length", ctypes.c_uint32),
            ("file_name", ctypes.c_wchar * 1),
        )

    class IoStatusBlock(ctypes.Structure):
        _fields_ = (("status", ctypes.c_void_p), ("information", ctypes.c_void_p))

    encoded_name = filename.encode("utf-16-le")
    name_offset = FileRenameInformation.file_name.offset
    buffer = ctypes.create_string_buffer(name_offset + len(encoded_name))
    information = FileRenameInformation.from_buffer(buffer)
    information.flags = 0x00000001 | 0x00000002
    information.root_directory = directory.windows_handle
    information.file_name_length = len(encoded_name)
    ctypes.memmove(ctypes.addressof(buffer) + name_offset, encoded_name, len(encoded_name))

    operation = ctypes.WinDLL("ntdll", use_last_error=True).NtSetInformationFile
    operation.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(IoStatusBlock),
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
    )
    operation.restype = ctypes.c_long
    io_status = IoStatusBlock()
    status = operation(
        msvcrt.get_osfhandle(handle.fileno()),
        ctypes.byref(io_status),
        buffer,
        len(buffer),
        65,
    )
    if status < 0:
        raise OSError(status & 0xFFFFFFFF, "The journal could not be replaced safely.")


def publish_open_file_no_replace_in_directory(
    handle: BinaryIO,
    directory: PlainDirectoryHandle,
    temporary_name: str,
    destination_name: str,
) -> None:
    """Publish one verified same-directory file without replacing a destination.

    Durable Persistence §§516–532, 1288–1427; RM-03 and RM-41.
    """

    if any(not name or name != Path(name).name for name in (temporary_name, destination_name)):
        raise OSError("A publication filename is invalid.")
    if not directory.verify_path():
        raise OSError("The publication parent identity changed.")
    if os.name == "nt":
        if directory.windows_handle is None:
            raise OSError("A held Windows publication parent is required.")
        import ctypes
        operation = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        operation.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
        operation.restype = ctypes.c_int
        if not operation(
            str(directory.path / temporary_name),
            str(directory.path / destination_name),
            0x00000008,
        ):
            code = ctypes.get_last_error()
            if code in {80, 183}:
                raise FileExistsError(code, "The publication destination exists.")
            raise OSError(code, "The file could not be published exclusively.")
        return
    if directory.descriptor is None:
        raise OSError("A held POSIX publication parent is required.")
    import ctypes

    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        operation = getattr(library, "renameatx_np", None)
        flags = 0x4  # RENAME_EXCL
    else:
        operation = getattr(library, "renameat2", None)
        flags = 0x1  # RENAME_NOREPLACE
    if operation is None:
        raise OSError("Exclusive same-directory publication is unavailable.")
    operation.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    operation.restype = ctypes.c_int
    if operation(directory.descriptor, os.fsencode(temporary_name), directory.descriptor, os.fsencode(destination_name), flags) != 0:
        error_code = ctypes.get_errno()
        if error_code in {17, 80, 183}:
            raise FileExistsError(error_code, "The publication destination exists.")
        raise OSError(error_code, "The file could not be published exclusively.")


def sync_directory(directory: PlainDirectoryHandle) -> None:
    """Make a supported POSIX directory namespace update durable."""

    if not directory.verify_path():
        raise OSError("The directory identity changed before durability sync.")
    if os.name == "nt":
        # The approved Windows contract explicitly does not claim directory fsync.
        return
    if directory.descriptor is None:
        raise OSError("A held POSIX directory descriptor is required.")
    os.fsync(directory.descriptor)


def rename_entry_no_replace_in_directory(
    directory: PlainDirectoryHandle, source_name: str, destination_name: str
) -> None:
    """Rename one verified same-parent entry without replacement."""

    if any(not name or name != Path(name).name for name in (source_name, destination_name)):
        raise OSError("A rename basename is invalid.")
    if not directory.verify_path():
        raise OSError("The rename parent identity changed.")
    if os.name == "nt":
        import ctypes
        operation = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        operation.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
        operation.restype = ctypes.c_int
        if not operation(str(directory.path / source_name), str(directory.path / destination_name), 0x8):
            code = ctypes.get_last_error()
            if code in {80, 183}:
                raise FileExistsError(code, "The rename destination exists.")
            raise OSError(code, "The directory entry could not be renamed exclusively.")
        return
    if directory.descriptor is None:
        raise OSError("A held POSIX rename parent is required.")
    import ctypes
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        operation = getattr(library, "renameatx_np", None)
        flags = 0x4
    else:
        operation = getattr(library, "renameat2", None)
        flags = 0x1
    if operation is None:
        raise OSError("Exclusive same-directory rename is unavailable.")
    operation.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    operation.restype = ctypes.c_int
    if operation(directory.descriptor, os.fsencode(source_name), directory.descriptor, os.fsencode(destination_name), flags) != 0:
        code = ctypes.get_errno()
        if code == 17:
            raise FileExistsError(code, "The rename destination exists.")
        raise OSError(code, "The directory entry could not be renamed exclusively.")


def exchange_paths_in_directory(
    directory: PlainDirectoryHandle, first: str, second: str
) -> None:
    """Atomically exchange two POSIX directory entries without path traversal."""

    if os.name == "nt" or directory.descriptor is None:
        raise OSError("Native directory-entry exchange is unavailable.")
    if any(not name or name != Path(name).name for name in (first, second)):
        raise OSError("An exchange filename is invalid.")

    import ctypes

    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        operation = getattr(library, "renameatx_np", None)
    else:
        operation = getattr(library, "renameat2", None)
    if operation is None:
        raise OSError("Atomic directory-entry exchange is unavailable.")
    operation.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    operation.restype = ctypes.c_int
    if operation(
        directory.descriptor,
        os.fsencode(first),
        directory.descriptor,
        os.fsencode(second),
        0x2,
    ) != 0:
        error_code = ctypes.get_errno()
        raise OSError(error_code, "The journal entries could not be exchanged.")


def _open_windows_binary(
    path: Path, *, create_new: bool, share_delete: bool = True
) -> BinaryIO:
    import ctypes
    import msvcrt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (ctypes.c_void_p,)
    close_handle.restype = ctypes.c_int
    desired_access = 0x80000000 | 0x00010000
    if create_new:
        desired_access |= 0x40000000
    try:
        raw_handle = _windows_open_path(
            path,
            desired_access=desired_access,
            share_mode=(
                0x00000001 | 0x00000002 | (0x00000004 if share_delete else 0)
            ),
            disposition=1 if create_new else 3,
            flags=0x00000080 | 0x00200000,
            message="The file could not be opened safely.",
        )
    except OSError as error:
        error_code = getattr(error, "winerror", None) or error.errno
        if create_new and error_code in {80, 183}:
            raise FileExistsError(
                error_code, "The destination already exists.", str(path)
            ) from error
        raise
    try:
        _require_windows_plain_type(
            _windows_handle_information(raw_handle), directory=False
        )
        descriptor = msvcrt.open_osfhandle(
            raw_handle,
            (os.O_RDWR if create_new else os.O_RDONLY)
            | getattr(os, "O_BINARY", 0),
        )
    except Exception:
        close_handle(raw_handle)
        raise
    return os.fdopen(descriptor, "w+b" if create_new else "rb", buffering=0)


def _windows_path_identity(path: Path) -> ObjectIdentity:
    import ctypes

    raw_handle = _windows_open_path(
        path,
        desired_access=0x00000080,
        share_mode=0x00000001 | 0x00000002 | 0x00000004,
        flags=0x02000000 | 0x00200000,
        message="The object identity could not be opened.",
    )
    try:
        _require_windows_plain_type(
            _windows_handle_information(raw_handle), directory=None
        )
        return _windows_file_id_information(raw_handle)
    finally:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(raw_handle)


def _windows_handle_identity(raw_handle: int) -> ObjectIdentity:
    information = _windows_handle_information(raw_handle)
    _require_windows_plain_type(information, directory=None)
    return _windows_file_id_information(raw_handle)


def _windows_handle_information(raw_handle: int):
    import ctypes

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = (
            ("file_attributes", ctypes.c_uint32),
            ("creation_time_low", ctypes.c_uint32),
            ("creation_time_high", ctypes.c_uint32),
            ("last_access_time_low", ctypes.c_uint32),
            ("last_access_time_high", ctypes.c_uint32),
            ("last_write_time_low", ctypes.c_uint32),
            ("last_write_time_high", ctypes.c_uint32),
            ("volume_serial_number", ctypes.c_uint32),
            ("file_size_high", ctypes.c_uint32),
            ("file_size_low", ctypes.c_uint32),
            ("number_of_links", ctypes.c_uint32),
            ("file_index_high", ctypes.c_uint32),
            ("file_index_low", ctypes.c_uint32),
        )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    operation = kernel32.GetFileInformationByHandle
    operation.argtypes = (ctypes.c_void_p, ctypes.POINTER(ByHandleFileInformation))
    operation.restype = ctypes.c_int
    information = ByHandleFileInformation()
    if not operation(raw_handle, ctypes.byref(information)):
        error_code = ctypes.get_last_error()
        raise OSError(error_code, "The object identity could not be read.")
    return information


def _windows_file_id_information(raw_handle: int) -> ObjectIdentity:
    """Return the native 64-bit volume serial and 128-bit FILE_ID_128."""

    import ctypes

    class FileId128(ctypes.Structure):
        _fields_ = (("identifier", ctypes.c_ubyte * 16),)

    class FileIdInfo(ctypes.Structure):
        _fields_ = (
            ("volume_serial_number", ctypes.c_uint64),
            ("file_id", FileId128),
        )

    operation = ctypes.WinDLL(
        "kernel32", use_last_error=True
    ).GetFileInformationByHandleEx
    operation.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    operation.restype = ctypes.c_int
    information = FileIdInfo()
    if not operation(
        raw_handle,
        18,
        ctypes.byref(information),
        ctypes.sizeof(information),
    ):
        code = ctypes.get_last_error()
        raise OSError(code, "The native file identity could not be read.")
    file_id = int.from_bytes(bytes(information.file_id.identifier), "little")
    return information.volume_serial_number, file_id


def _require_windows_plain_type(information, *, directory: bool | None) -> None:
    attributes = information.file_attributes
    if attributes & 0x00000400:
        raise OSError("A reparse point cannot be used by the importer.")
    is_directory = bool(attributes & 0x00000010)
    if directory is not None and is_directory is not directory:
        raise OSError("The opened importer object has the wrong type.")


def _windows_open_path(
    path: Path,
    *,
    desired_access: int,
    share_mode: int,
    flags: int,
    message: str,
    disposition: int = 3,
) -> int:
    import ctypes

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
    raw_handle = create_file(
        str(path),
        desired_access,
        share_mode,
        None,
        disposition,
        flags,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if raw_handle == invalid_handle:
        error_code = ctypes.get_last_error()
        raise OSError(error_code, message, str(path))
    return raw_handle


def _windows_open_relative_path(
    parent_handle: int,
    name: str,
    *,
    desired_access: int,
    create_options: int,
    message: str,
    disposition: int = 1,
    file_attributes: int = 0,
) -> int:
    """Open one NT child relative to a held directory without reparsing it."""

    import ctypes

    class UnicodeString(ctypes.Structure):
        _fields_ = (
            ("length", ctypes.c_ushort),
            ("maximum_length", ctypes.c_ushort),
            ("buffer", ctypes.c_wchar_p),
        )

    class ObjectAttributes(ctypes.Structure):
        _fields_ = (
            ("length", ctypes.c_ulong),
            ("root_directory", ctypes.c_void_p),
            ("object_name", ctypes.POINTER(UnicodeString)),
            ("attributes", ctypes.c_ulong),
            ("security_descriptor", ctypes.c_void_p),
            ("security_quality_of_service", ctypes.c_void_p),
        )

    class IoStatusBlock(ctypes.Structure):
        _fields_ = (("status", ctypes.c_void_p), ("information", ctypes.c_void_p))

    name_buffer = ctypes.create_unicode_buffer(name)
    encoded_length = len(name.encode("utf-16-le"))
    unicode_name = UnicodeString(
        encoded_length, encoded_length + 2, ctypes.cast(name_buffer, ctypes.c_wchar_p)
    )
    attributes = ObjectAttributes(
        ctypes.sizeof(ObjectAttributes),
        parent_handle,
        ctypes.pointer(unicode_name),
        0x00000040,
        None,
        None,
    )
    result = ctypes.c_void_p()
    io_status = IoStatusBlock()
    operation = ctypes.WinDLL("ntdll", use_last_error=True).NtCreateFile
    operation.argtypes = (
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint32,
        ctypes.POINTER(ObjectAttributes),
        ctypes.POINTER(IoStatusBlock),
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    operation.restype = ctypes.c_long
    status = operation(
        ctypes.byref(result),
        desired_access,
        ctypes.byref(attributes),
        ctypes.byref(io_status),
        None,
        file_attributes,
        0x00000001 | 0x00000002 | 0x00000004,
        disposition,
        create_options,
        None,
        0,
    )
    if status < 0 or not result.value:
        raise OSError(status & 0xFFFFFFFF, message, name)
    return int(result.value)
