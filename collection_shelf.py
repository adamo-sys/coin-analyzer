"""Detached metadata shelf projections and shared non-shelf photo helpers."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from io import BytesIO
import os
import ntpath
import stat
import re
from pathlib import Path

from PIL import Image, ImageOps

from collection_item_reference import CollectionItemReference
from collection_resume import collection_resume_rows


def _local_path_syntax(path):
    """Pure lexical gate, before even binding a relative path to the cwd."""
    if not isinstance(path, str) or not path or any(ord(char) < 32 for char in path):
        return False
    windows = path.replace("/", "\\")
    if windows.startswith("\\\\") or windows.startswith("\\??\\"):
        return False
    drive, tail = ntpath.splitdrive(windows)
    if drive and (len(drive) != 2 or not drive[0].isascii() or
                  not drive[0].isalpha() or drive[1] != ":" or not tail.startswith("\\")):
        return False
    if any(char in tail for char in ':<>"|?*'):
        return False
    for part in tail.split("\\"):
        # Never collapse a parent traversal across an uninspected component.
        # In particular, Windows can skip a missing directory before '..'.
        if part == "..":
            return False
        if part in ("", "."):
            continue
        device = part.split(".", 1)[0].rstrip(" ").upper()
        if (part.endswith((" ", ".")) or device in ("CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$") or
                (device[:3] in ("COM", "LPT") and device[3:] in "123456789¹²³" and len(device) == 4)):
            return False
    # Root-relative Windows paths depend on a drive's current directory.
    return not (os.name == "nt" and not drive and tail.startswith("\\"))


def _local_windows_drive(root):
    import ctypes
    try:
        query = ctypes.windll.kernel32.QueryDosDeviceW
        query.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        query.restype = ctypes.c_uint
        target = ctypes.create_unicode_buffer(32768)
        if not query(root.rstrip("\\"), target, len(target)):
            return False
        # Query only the local object namespace, never open a volume. Reject
        # redirectors, SUBST aliases and unknown devices rather than resolve them.
        return re.fullmatch(r"\\Device\\(?:HarddiskVolume|CdRom|Floppy|Ramdisk)[0-9]+",
                            target.value, re.IGNORECASE) is not None
    except (OSError, AttributeError):
        return False


def _windows_path_attributes(path):
    """Inspect the entry itself, including non-name-surrogate reparse points.

    Windows lstat may resolve some reparse types; GetFileAttributesW returns
    attributes of the link/mounted directory itself. Parents must be checked
    before this query. Preserve Win32 failures as OSError subclasses.
    """
    import ctypes
    query = ctypes.WinDLL("kernel32", use_last_error=True).GetFileAttributesW
    query.argtypes = [ctypes.c_wchar_p]
    query.restype = ctypes.c_uint32
    attributes = query(path)
    if attributes == 0xFFFFFFFF:
        raise ctypes.WinError(ctypes.get_last_error())
    return attributes


def local_photo_path(path):
    """Return a bound local path, or fail closed without following redirects.

    Reject UNC/device/parent-traversal syntax before filesystem access. Bind a
    relative path only to a permitted cwd, then normalize '.' and separators
    lexically. On Windows, accept only a locally classified drive and inspect
    the root and each existing prefix without following reparse points. A missing
    prefix is safe to stop at only because no parent traversal remains: no later
    component can return to an existing ancestor. Callers use only this returned
    path, and report missing/unavailable photos without substituting another.

    This is not atomic with later opens: concurrent drive/reparse replacement
    remains a separate race risk.
    """
    if not _local_path_syntax(path):
        return None
    if not os.path.isabs(path):
        cwd = os.getcwd()
        if not _local_path_syntax(cwd):
            return None
        path = os.path.join(cwd, path)
    if not _local_path_syntax(path):
        return None
    # No '..' is accepted, so normalization cannot hide a traversed link.
    path = os.path.normpath(path)
    if os.name == "nt":
        root = ntpath.splitdrive(path)[0] + "\\"
        if not _local_windows_drive(root):
            return None
        current = root
        for part in [""] + path[len(root):].split("\\"):
            if part:
                current = ntpath.join(current, part)
            try:
                attributes = _windows_path_attributes(current)
            except FileNotFoundError:
                break  # The caller reports the truthful missing-photo state.
            if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                return None
    return path


@dataclass(frozen=True)
class ShelfPhoto:
    path: str
    status: str
    signature: tuple | None = None
    saved_sha256: str | None = None


@dataclass(frozen=True)
class ShelfCard:
    reference: CollectionItemReference
    label: str
    status: str
    recorded_date: str
    photo: ShelfPhoto


@dataclass(frozen=True)
class ShelfPage:
    cards: tuple[ShelfCard, ...]
    total: int
    index: int
    pages: int


def _signature(path):
    stat = os.stat(path)
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _saved_photo(item):
    # CoinItem.normalized_photos changes ItemPhoto flags/order in place.
    # Only the detached copy may cross that boundary.
    try:
        primary = deepcopy(item).primary_photo()
    except (TypeError, ValueError, AttributeError):
        return ShelfPhoto("", "Saved photo metadata unavailable")
    if primary is None:
        return ShelfPhoto("", "No photo reference recorded")
    return ShelfPhoto(primary.path, "Photo reference recorded; image not loaded")


def shelf_page(collection, query="", page=0):
    """Reuse recorded orientation/search without inspecting photo references."""
    rows = collection_resume_rows(collection)
    query = query.strip()
    if query:
        matching = {id(item) for item in collection.search_items(query)}
        rows = tuple(row for row in rows if id(row.reference.item) in matching)
    total = len(rows)
    pages = max(1, (total + 23) // 24)
    index = min(max(0, page), pages - 1)
    cards = tuple(ShelfCard(row.reference, row.label, row.status, row.recorded_date,
                            _saved_photo(row.reference.item))
                  for row in rows[index * 24:(index + 1) * 24])
    return ShelfPage(cards, total, index, pages)


def load_thumbnail(photo: ShelfPhoto):
    """Decode just the selected saved photo; no fallback or disk cache."""
    if photo.status:
        return None, photo.status
    try:
        path = local_photo_path(photo.path)
        if path is None:
            return None, "Only local saved photos can be shown"
        if _signature(path) != photo.signature:
            return None, "Saved photo changed; refresh the shelf"
        data = Path(path).read_bytes()
        if photo.saved_sha256 and hashlib.sha256(data).hexdigest() != photo.saved_sha256:
            return None, "Saved photo changed since import"
        with Image.open(BytesIO(data)) as source:
            # Apply EXIF orientation to a detached image and discard the file handle.
            image = ImageOps.exif_transpose(source).convert("RGB")
        if _signature(path) != photo.signature:
            image.close()
            return None, "Saved photo changed; refresh the shelf"
        image.thumbnail((160, 120))
        return image, ""
    except FileNotFoundError:
        return None, "Saved photo missing"
    except (OSError, ValueError, Image.DecompressionBombError):
        return None, "Saved photo unreadable"
