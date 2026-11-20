"""Data safety, backup, restore, and validation helpers.

This module uses local files only. It does not sync to cloud services, call
APIs, scrape listings, or modify collection workbooks.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import stat
import struct
import tempfile
import unicodedata
import uuid
import zipfile
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from pathlib import Path

from capture_import import _filesystem as backup_fs

from collection_dashboard import CollectionDashboard
from collector_operating_system import CollectionHealthReportEngine
from confirmed_observations import CONFIRMED_OBSERVATIONS_FILENAME
from market_awareness import MarketAwarenessEngine
from persistence_manager import AppState, PersistenceManager
from photo_vault import PhotoRecord, PhotoVault, PhotoVaultIntegrityAudit
from series_tracker import SeriesTracker
from smart_shopping_assistant import ShoppingCandidate, SmartShoppingAssistant


APP_VERSION = "2.4.1"
MANIFEST_NAME = "backup_manifest.json"
MANIFEST_MARKDOWN_NAME = "backup_manifest.md"
DEFAULT_COLLECTION_JSON_PATH = os.path.join("data", "collection.json")
DEFAULT_SNAPSHOT_PATH = os.path.join("collection_data", "app_state", "collection_snapshots.json")

# Legacy ZIP security budgets. See docs/security/SEC-001-002-phase1.md.
MAX_BACKUP_ENTRIES = 4096
MAX_BACKUP_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_BACKUP_FILE_BYTES = 512 * 1024 * 1024
MAX_BACKUP_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024
MAX_BACKUP_ARCHIVE_BYTES = 1024 * 1024 * 1024
MAX_BACKUP_CENTRAL_BYTES = 8 * 1024 * 1024
MAX_BACKUP_JSON_DEPTH = 64
MAX_BACKUP_RATIO = 2000
BACKUP_CHUNK_BYTES = 64 * 1024
RESTORE_PATHS = frozenset({
    ("data", "collection.json"),
    ("collection_data", "app_state", "app_state.json"),
    ("collection_data", "app_state", "collection_snapshots.json"),
    ("collection_data", "app_state", CONFIRMED_OBSERVATIONS_FILENAME),
})


def _backup_name(name: str) -> tuple[str, ...]:
    """Require portable components, without normalizing hostile spellings."""
    if not isinstance(name, str) or not name or len(name) > 1024:
        raise ValueError("Invalid backup member name")
    parts = tuple(name.split("/"))
    reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    reserved.update(f"{prefix}{number}" for prefix in ("COM", "LPT")
                    for number in "123456789¹²³")
    for part in parts:
        if (not part or part in {".", ".."} or len(part) > 255
                or part[-1] in " ." or unicodedata.normalize("NFC", part) != part
                or any(ord(c) < 32 or ord(c) == 127 or c in '\\:*?"<>|'
                       or 0xD800 <= ord(c) <= 0xDFFF for c in part)
                or part.split(".")[0].upper() in reserved):
            raise ValueError("Unsafe backup member name")
    return parts


def _unique_backup_names(names):
    keys = set()
    for name in names:
        key = tuple(part.casefold() for part in _backup_name(name))
        if key in keys:
            raise ValueError("Duplicate or aliased backup member")
        keys.add(key)
    if any(key[:length] in keys for key in keys for length in range(1, len(key))):
        raise ValueError("Conflicting backup file and directory")


def _backup_zip_preflight(handle):
    """Bound central-directory allocation before constructing ZipFile.

    The writer emits ordinary single-disk ZIPs. ZIP64 end records would be
    needed only above our byte/count limits, and are rejected explicitly.
    Small force-ZIP64 local file headers remain supported by ZipFile.
    """
    handle.seek(0, os.SEEK_END)
    size = handle.tell()
    if size > MAX_BACKUP_ARCHIVE_BYTES:
        raise ValueError("Backup compressed-byte budget exceeded")
    handle.seek(max(0, size - 65557))
    tail = handle.read(65557)
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or len(tail) - offset < 22:
        raise ValueError("Missing ZIP end record")
    _, disk, central_disk, disk_count, count, central_size, central_offset, comment = struct.unpack(
        "<4s4H2LH", tail[offset:offset + 22])
    end_offset = size - len(tail) + offset
    # ZipFile probes exactly here, even if a classic entry comment covers the
    # locator. Reject it before it can redirect parsing to an unchecked ZIP64
    # directory. Local force-ZIP64 file headers do not use this locator.
    if end_offset >= 20:
        handle.seek(end_offset - 20)
        if handle.read(4) == b"PK\x06\x07":
            raise ValueError("ZIP64 end records are outside the legacy backup budgets")
    if (disk or central_disk or disk_count != count or count == 65535
            or count > MAX_BACKUP_ENTRIES or central_size > MAX_BACKUP_CENTRAL_BYTES
            or central_offset + central_size != end_offset
            or offset + 22 + comment != len(tail)):
        raise ValueError("Unsupported or over-budget ZIP directory")
    # Do not trust the advertised count: walk bounded central metadata first.
    handle.seek(central_offset)
    consumed = actual_count = 0
    while consumed < central_size:
        header = handle.read(46)
        if len(header) != 46 or header[:4] != b"PK\x01\x02":
            raise ValueError("Invalid ZIP central entry")
        name_len, extra_len, comment_len = struct.unpack_from("<3H", header, 28)
        consumed += 46 + name_len + extra_len + comment_len
        actual_count += 1
        if consumed > central_size or actual_count > MAX_BACKUP_ENTRIES:
            raise ValueError("Backup central-entry budget exceeded")
        handle.seek(name_len + extra_len + comment_len, os.SEEK_CUR)
    if actual_count != count:
        raise ValueError("Inconsistent ZIP entry count")
    handle.seek(0)


def _backup_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate manifest field")
        result[key] = value
    return result


def _backup_json_depth(raw):
    depth = 0
    quoted = escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > MAX_BACKUP_JSON_DEPTH:
                raise ValueError("Backup manifest nesting budget exceeded")
        elif byte in (93, 125):
            depth -= 1


def _read_backup_member(archive, info, remaining, sink=None):
    """Hash and optionally stage bytes using enforced actual-byte limits."""
    limit = min(MAX_BACKUP_FILE_BYTES, remaining)
    if info.filename == MANIFEST_NAME:
        limit = min(limit, MAX_BACKUP_MANIFEST_BYTES)
    digest = hashlib.sha256()
    total = 0
    with archive.open(info) as source:
        while True:
            chunk = source.read(min(BACKUP_CHUNK_BYTES, limit - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise ValueError("Backup streamed-byte budget exceeded")
            digest.update(chunk)
            if sink is not None:
                sink.write(chunk)
    if total != info.file_size:
        raise ValueError("Backup member length mismatch")
    return total, digest.hexdigest()


def _verify_backup_archive(handle, stack, stage=False):
    _backup_zip_preflight(handle)
    staged = {}
    with zipfile.ZipFile(handle, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_BACKUP_ENTRIES:
            raise ValueError("Backup entry-count budget exceeded")
        _unique_backup_names(info.orig_filename for info in infos)
        total = 0
        for info in infos:
            mode = info.external_attr >> 16
            if (info.filename != info.orig_filename or info.is_dir()
                    or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
                    or info.flag_bits & 1
                    or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise ValueError("Unsupported backup member type or encoding")
            limit = MAX_BACKUP_MANIFEST_BYTES if info.filename == MANIFEST_NAME else MAX_BACKUP_FILE_BYTES
            total += info.file_size
            if (info.file_size > limit or total > MAX_BACKUP_EXPANDED_BYTES
                    or info.file_size > MAX_BACKUP_RATIO * max(1, info.compress_size)):
                raise ValueError("Backup expanded-byte or ratio budget exceeded")
        info = archive.getinfo(MANIFEST_NAME)
        with tempfile.TemporaryFile() as manifest_bytes:
            used, _ = _read_backup_member(archive, info, MAX_BACKUP_EXPANDED_BYTES, manifest_bytes)
            manifest_bytes.seek(0)
            raw = manifest_bytes.read(MAX_BACKUP_MANIFEST_BYTES + 1)
            _backup_json_depth(raw)
            payload = json.loads(raw.decode("utf-8"),
                                 object_pairs_hook=_backup_json_pairs)
        if not isinstance(payload, dict) or not isinstance(payload.get("included_files", []), list):
            raise ValueError("Invalid backup manifest schema")
        rows = payload.get("included_files", [])
        if len(rows) > MAX_BACKUP_ENTRIES or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Invalid backup manifest records")
        _unique_backup_names(row.get("archive_path") for row in rows)
        indexed = {}
        for row in rows:
            name = row["archive_path"]
            if name in (MANIFEST_NAME, MANIFEST_MARKDOWN_NAME):
                raise ValueError("Manifest cannot list itself")
            member = archive.getinfo(name)
            size = row.get("size_bytes", member.file_size)
            checksum = row.get("sha256", "")
            if (type(size) is not int or size < 0 or size != member.file_size
                    or not isinstance(checksum, str)
                    or (checksum and (len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum)))):
                raise ValueError("Invalid backup length or checksum metadata")
            indexed[name] = row
        for field_name in ("warnings", "restore_notes", "excluded_files", "missing_files"):
            if field_name in payload and (not isinstance(payload[field_name], list)
                    or any(not isinstance(value, str) for value in payload[field_name])):
                raise ValueError("Invalid backup manifest list")
        for info in infos:
            if info.filename == MANIFEST_NAME:
                continue
            sink = None
            if stage and info.filename in indexed and _backup_name(info.filename) in RESTORE_PATHS:
                sink = stack.enter_context(tempfile.TemporaryFile())
                staged[info.filename] = sink
            length, digest = _read_backup_member(archive, info, MAX_BACKUP_EXPANDED_BYTES - used, sink)
            used += length
            row = indexed.get(info.filename)
            if row and row.get("sha256") and row["sha256"] != digest:
                raise ValueError("Backup checksum mismatch")
        return BackupManifest.from_dict(payload), staged


def _snapshot_backup(package_path, stack):
    snapshot = stack.enter_context(tempfile.TemporaryFile())
    with open(package_path, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BACKUP_ARCHIVE_BYTES:
            raise ValueError("Backup is not a bounded regular archive")
        _backup_zip_preflight(source)
        consumed = 0
        while True:
            chunk = source.read(min(BACKUP_CHUNK_BYTES, MAX_BACKUP_ARCHIVE_BYTES - consumed + 1))
            if not chunk:
                break
            consumed += len(chunk)
            if consumed > MAX_BACKUP_ARCHIVE_BYTES:
                raise ValueError("Backup compressed streamed-byte budget exceeded")
            snapshot.write(chunk)
    snapshot.seek(0)
    return snapshot


def _hold_restore_directory(path, stack):
    held = stack.enter_context(backup_fs.open_plain_directory_handle(path))
    if os.name == "nt":
        # Deny directory deletion/rename while allowing the kernel's relative
        # rename target open (FILE_WRITE_DATA). Pin every ancestor.
        raw = backup_fs._windows_open_path(
            path, desired_access=0x80 | 0x20, share_mode=0x3,
            flags=0x02000000 | 0x00200000,
            message="Restore directory cannot be pinned safely")
        pin = stack.enter_context(backup_fs.PlainDirectoryHandle(path, held.identity, windows_handle=raw))
        if not pin.verify_path():
            raise OSError("Restore directory was substituted")
    return held


def _restore_parent(root, parts, held, stack):
    current = Path(root.anchor)
    for part in (*root.parts[1:], *parts):
        parent = current
        current /= part
        if current in held:
            continue
        if not os.path.lexists(current):
            if parent not in held:
                raise OSError("Restore ancestor is not held")
            created = backup_fs.create_plain_child_directory(held[parent], part)
            identity = created.identity
            created.close()
            directory = _hold_restore_directory(current, stack)
            if directory.identity != identity:
                raise OSError("New restore directory was substituted")
        else:
            directory = _hold_restore_directory(current, stack)
        held[current] = directory
    return held[current]


def _restore_bindings(held):
    if any(not directory.verify_path() for directory in held.values()):
        raise OSError("Restore ancestor binding changed")


def _restore_remove(handle, parent, name):
    """Remove only an owned temporary regular file; never recurse."""
    if not parent.verify_path() or not backup_fs.handle_matches_path(handle, parent.path / name):
        raise OSError("Restore artifact changed; preserved for manual recovery")
    if os.name == "nt":
        backup_fs.delete_open_file(handle, parent.path / name)
    else:
        os.unlink(name, dir_fd=parent.descriptor)


def _rename_restore_file(handle, parent, source_name, destination_name):
    """Move an exact held Windows file without replacement, or use renameat.

    Matches the repository's native relative rename protocol, with replacement
    disabled. MoveFileExW reopens pinned parents and cannot be used here.
    """
    if not parent.verify_path() or not backup_fs.handle_matches_path(handle, parent.path / source_name):
        raise OSError("Restore rename binding changed")
    if os.name != "nt":
        backup_fs.rename_entry_no_replace_in_directory(parent, source_name, destination_name)
        return
    import ctypes
    import msvcrt

    class RenameInformation(ctypes.Structure):
        _fields_ = (("flags", ctypes.c_uint32), ("root", ctypes.c_void_p),
                    ("length", ctypes.c_uint32), ("name", ctypes.c_wchar * 1))

    class IoStatus(ctypes.Structure):
        _fields_ = (("status", ctypes.c_void_p), ("information", ctypes.c_void_p))

    encoded = destination_name.encode("utf-16-le")
    offset = RenameInformation.name.offset
    buffer = ctypes.create_string_buffer(offset + len(encoded))
    information = RenameInformation.from_buffer(buffer)
    information.flags = 0x2  # POSIX semantics; FILE_RENAME_REPLACE_IF_EXISTS is OFF.
    information.root = parent.windows_handle
    information.length = len(encoded)
    ctypes.memmove(ctypes.addressof(buffer) + offset, encoded, len(encoded))
    operation = ctypes.WinDLL("ntdll", use_last_error=True).NtSetInformationFile
    operation.argtypes = (ctypes.c_void_p, ctypes.POINTER(IoStatus), ctypes.c_void_p,
                          ctypes.c_uint32, ctypes.c_int)
    operation.restype = ctypes.c_long
    status = operation(msvcrt.get_osfhandle(handle.fileno()), ctypes.byref(IoStatus()),
                       buffer, len(buffer), 65)
    if status < 0:
        raise OSError(status & 0xFFFFFFFF, "Restore no-replace rename failed")


def _restore_staged_files(root, staged, overwrite, stack, before_write):
    """Backup-specific in-process transaction using existing native primitives.

    Never truncate live files. Keep originals until all publications succeed.
    Ambiguous namespace changes preserve artifacts rather than deleting them.
    This is not a durable crash-recovery protocol.
    """
    held = {}
    anchor = Path(root.anchor)
    held[anchor] = _hold_restore_directory(anchor, stack)
    plans = []
    skipped = []
    warnings = []
    try:
        for name, source in staged.items():
            parts = _backup_name(name)
            parent = _restore_parent(root, parts[:-1], held, stack)
            target = parent.path / parts[-1]
            original_identity = None
            if os.path.lexists(target):
                info = backup_fs.require_plain_regular_file(target)
                if info.st_nlink != 1:
                    raise OSError("Restore target has multiple hard links")
                if not overwrite:
                    skipped.append(name)
                    continue
                original_identity = backup_fs.path_object_identity(target)
            token = uuid.uuid4().hex
            temporary_name = f".backup-restore-{token}.new"
            new = stack.enter_context(backup_fs.open_exclusive_child_binary(parent, temporary_name))
            plan = dict(parent=parent, target=target, original=None, original_identity=original_identity, new=new,
                        temporary_name=temporary_name, old_name=f".backup-restore-{token}.old",
                        displaced=False, published=False, ambiguous=False)
            plans.append(plan)
            source.seek(0)
            shutil.copyfileobj(source, new, BACKUP_CHUNK_BYTES)
            new.flush()
        _restore_bindings(held)
        before_write()
        # Windows held source files carry DELETE access for exact-object
        # cleanup. Acquire them after the pre-backup's ordinary reader closes.
        for plan in plans:
            if plan["original_identity"] is not None:
                original = stack.enter_context(backup_fs.open_plain_child_file_readonly(
                    plan["parent"], plan["target"].name))
                if backup_fs.handle_object_identity(original) != plan["original_identity"]:
                    raise OSError("Restore destination changed before backup completed")
                plan["original"] = original
        for plan in plans:
            _restore_bindings(held)
            parent, target = plan["parent"], plan["target"]
            if plan["original"] is not None:
                if not backup_fs.handle_matches_path(plan["original"], target):
                    raise OSError("Restore destination was replaced")
                _rename_restore_file(plan["original"], parent, target.name, plan["old_name"])
                plan["displaced"] = True
                if not backup_fs.handle_matches_path(plan["original"], parent.path / plan["old_name"]):
                    plan["ambiguous"] = True
                    raise OSError("Restore destination changed during displacement")
            _rename_restore_file(plan["new"], parent, plan["temporary_name"], target.name)
            plan["published"] = True
            if not backup_fs.handle_matches_path(plan["new"], target):
                plan["ambiguous"] = True
                raise OSError("Restore publication was substituted")
        _restore_bindings(held)
    except Exception:
        for plan in reversed(plans):
            parent, target = plan["parent"], plan["target"]
            try:
                _restore_bindings(held)
                if plan["published"]:
                    if not backup_fs.handle_matches_path(plan["new"], target):
                        raise OSError("Published restore target changed")
                    _rename_restore_file(plan["new"], parent, target.name, plan["temporary_name"])
                    if not backup_fs.handle_matches_path(plan["new"], parent.path / plan["temporary_name"]):
                        raise OSError("Rollback destination changed")
                    plan["published"] = False
                if plan["displaced"]:
                    # Even a substituted displaced object is put back only into
                    # an absent destination. Never delete or overwrite it.
                    if plan["ambiguous"]:
                        raise OSError("Ambiguous displaced object preserved")
                    _rename_restore_file(plan["original"], parent, plan["old_name"], target.name)
                    plan["displaced"] = False
                if not plan["ambiguous"]:
                    _restore_remove(plan["new"], parent, plan["temporary_name"])
            except OSError:
                warnings.append("Restore rollback is incomplete; preserve restore artifacts for manual recovery")
        if warnings:
            raise OSError("Restore failed; rollback is incomplete; artifacts preserved")
        raise
    for plan in plans:
        if plan["displaced"]:
            try:
                _restore_remove(plan["original"], plan["parent"], plan["old_name"])
            except OSError:
                warnings.append("Original restore artifact retained; manual cleanup required")
    return [str(plan["target"]) for plan in plans], skipped, warnings


def _yes_no(value: Any) -> str:
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in {"YES", "NO"}:
            return normalized
        return "YES" if normalized in {"TRUE", "1"} else "NO"
    return "YES" if bool(value) else "NO"


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class BackupFileRecord:
    source_path: str
    archive_path: str
    size_bytes: int = 0
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "archive_path": self.archive_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass
class BackupManifest:
    backup_created_at: str
    app_version: str = APP_VERSION
    collection_json_backed_up: str = "NO"
    workbook_backed_up: str = "NO"
    app_state_backed_up: str = "NO"
    included_files: List[BackupFileRecord] = field(default_factory=list)
    excluded_files: List[str] = field(default_factory=list)
    missing_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    restore_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backup_created_at": self.backup_created_at,
            "app_version": self.app_version,
            "collection_json_backed_up": _yes_no(self.collection_json_backed_up),
            "workbook_backed_up": _yes_no(self.workbook_backed_up),
            "app_state_backed_up": _yes_no(self.app_state_backed_up),
            "included_files": [record.to_dict() for record in self.included_files],
            "excluded_files": list(self.excluded_files),
            "missing_files": list(self.missing_files),
            "warnings": list(self.warnings),
            "restore_notes": list(self.restore_notes),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "BackupManifest":
        return cls(
            backup_created_at=str(payload.get("backup_created_at") or ""),
            app_version=str(payload.get("app_version") or APP_VERSION),
            collection_json_backed_up=_yes_no(payload.get("collection_json_backed_up", "NO")),
            workbook_backed_up=_yes_no(payload.get("workbook_backed_up", "NO")),
            app_state_backed_up=_yes_no(payload.get("app_state_backed_up", "NO")),
            included_files=[
                BackupFileRecord(
                    source_path=str(row.get("source_path") or ""),
                    archive_path=str(row.get("archive_path") or ""),
                    size_bytes=int(row.get("size_bytes") or 0),
                    sha256=str(row.get("sha256") or ""),
                )
                for row in payload.get("included_files", [])
            ],
            excluded_files=list(payload.get("excluded_files") or []),
            missing_files=list(payload.get("missing_files") or []),
            warnings=list(payload.get("warnings") or []),
            restore_notes=list(payload.get("restore_notes") or []),
        )

    def format_markdown(self) -> str:
        lines = [
            "# Backup Manifest",
            "",
            f"- Created: {self.backup_created_at}",
            f"- App version: {self.app_version}",
            "",
            "## Recovery Coverage",
            "",
            f"- collection_json_backed_up: {_yes_no(self.collection_json_backed_up)}",
            f"- workbook_backed_up: {_yes_no(self.workbook_backed_up)}",
            f"- app_state_backed_up: {_yes_no(self.app_state_backed_up)}",
            "",
            "## Included Files",
            "",
        ]
        if self.included_files:
            for record in self.included_files:
                lines.append(f"- {record.archive_path}: {record.size_bytes} bytes; sha256 {record.sha256}")
        else:
            lines.append("- None")
        lines.extend(["", "## Missing Files", ""])
        lines.extend(f"- {path}" for path in self.missing_files) if self.missing_files else lines.append("- None")
        lines.extend(["", "## Excluded Files", ""])
        lines.extend(f"- {path}" for path in self.excluded_files) if self.excluded_files else lines.append("- None")
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in self.warnings) if self.warnings else lines.append("- None")
        lines.extend(["", "## Restore Notes", ""])
        lines.extend(f"- {note}" for note in self.restore_notes) if self.restore_notes else lines.append("- Validate before restore.")
        return "\n".join(lines) + "\n"


@dataclass
class BackupResult:
    success: bool
    status: str
    package_path: str = ""
    manifest: Optional[BackupManifest] = None
    restored_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    pre_restore_backup_path: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class CollectionRecoveryReport:
    status: str
    package_path: str = ""
    collection_json_backed_up: str = "NO"
    workbook_backed_up: str = "NO"
    app_state_backed_up: str = "NO"
    recoverable: List[str] = field(default_factory=list)
    not_recoverable: List[str] = field(default_factory=list)
    missing_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "package_path": self.package_path,
            "collection_json_backed_up": _yes_no(self.collection_json_backed_up),
            "workbook_backed_up": _yes_no(self.workbook_backed_up),
            "app_state_backed_up": _yes_no(self.app_state_backed_up),
            "recoverable": list(self.recoverable),
            "not_recoverable": list(self.not_recoverable),
            "missing_files": list(self.missing_files),
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Collection Recovery Report",
            "",
            f"- Status: {self.status}",
            f"- Package: {self.package_path or 'No verified backup package'}",
            f"- collection_json_backed_up: {_yes_no(self.collection_json_backed_up)}",
            f"- workbook_backed_up: {_yes_no(self.workbook_backed_up)}",
            f"- app_state_backed_up: {_yes_no(self.app_state_backed_up)}",
            "",
            "## Recoverable",
            "",
        ]
        lines.extend(f"- {item}" for item in self.recoverable) if self.recoverable else lines.append("- None confirmed")
        lines.extend(["", "## Not Recoverable", ""])
        lines.extend(f"- {item}" for item in self.not_recoverable) if self.not_recoverable else lines.append("- None identified")
        lines.extend(["", "## Missing Files", ""])
        lines.extend(f"- {item}" for item in self.missing_files) if self.missing_files else lines.append("- None")
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in self.warnings) if self.warnings else lines.append("- None")
        lines.extend(["", "## Recommendations", ""])
        lines.extend(f"- {item}" for item in self.recommendations) if self.recommendations else lines.append("- Continue regular backup packages and off-machine copies.")
        return "\n".join(lines) + "\n"


@dataclass
class DataSafetyIssue:
    severity: str
    area: str
    message: str
    recommended_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "area": self.area,
            "message": self.message,
            "recommended_action": self.recommended_action,
        }


@dataclass
class DataSafetyReport:
    status: str
    issues: List[DataSafetyIssue] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "issues": [issue.to_dict() for issue in self.issues],
            "recommended_actions": list(self.recommended_actions),
        }

    def format_markdown(self) -> str:
        lines = ["# Data Safety Report", "", f"- Status: {self.status}", "", "## Issues", ""]
        if self.issues:
            for issue in self.issues:
                lines.append(f"- [{issue.severity}] {issue.area}: {issue.message}")
                if issue.recommended_action:
                    lines.append(f"  - Action: {issue.recommended_action}")
        else:
            lines.append("- No issues found.")
        lines.extend(["", "## Recommended Actions", ""])
        lines.extend(f"- {action}" for action in self.recommended_actions) if self.recommended_actions else lines.append("- Continue regular backups.")
        return "\n".join(lines) + "\n"


class DataSafetyValidator:
    """Validate app-state, referenced paths, and backup folder readiness."""

    def __init__(
        self,
        persistence_manager: Optional[PersistenceManager] = None,
        backup_dir: str = os.path.join("backups", "packages"),
        collection_json_path: str = DEFAULT_COLLECTION_JSON_PATH,
    ):
        self.persistence_manager = persistence_manager or PersistenceManager()
        self.backup_dir = backup_dir
        self.collection_json_path = collection_json_path

    def validate(self) -> DataSafetyReport:
        issues: List[DataSafetyIssue] = []
        state_result = self.persistence_manager.load_state()
        loaded_state = state_result.state or AppState()
        if not os.path.exists(self.collection_json_path):
            issues.append(DataSafetyIssue(
                "FAIL",
                "Collection JSON",
                f"Production collection JSON is missing: {self.collection_json_path}",
                "Restore data/collection.json from a verified backup or repository backup.",
            ))
        if not os.path.exists(self.persistence_manager.state_path):
            issues.append(DataSafetyIssue(
                "WARNING",
                "App State",
                f"App state JSON is missing: {self.persistence_manager.state_path}",
                "Use Tools -> Save Session State.",
            ))
        elif not state_result.success:
            issues.append(DataSafetyIssue(
                "FAIL",
                "App State",
                "; ".join(state_result.errors) or state_result.status,
                "Repair, import, or clear the saved state file.",
            ))
        else:
            issues.extend(self._validate_loaded_state(loaded_state))

        if not os.path.isdir(self.backup_dir):
            issues.append(DataSafetyIssue(
                "WARNING",
                "Backups",
                f"Backup directory is missing: {self.backup_dir}",
                "Create a backup package to initialize backup storage.",
            ))
        else:
            issues.extend(self._validate_backup_coverage(loaded_state))

        status = "PASS"
        if any(issue.severity == "FAIL" for issue in issues):
            status = "FAIL"
        elif issues:
            status = "WARNING"
        actions = self._recommended_actions(issues)
        return DataSafetyReport(status=status, issues=issues, recommended_actions=actions)

    def _validate_loaded_state(self, state: AppState) -> List[DataSafetyIssue]:
        issues = []
        for label, path in [
            ("Collection workbook path", state.collection_workbook_path),
            ("WANT_LIST source path", state.want_list_path),
        ]:
            if path and not os.path.exists(path):
                issues.append(DataSafetyIssue(
                    "WARNING",
                    label,
                    f"Referenced file is missing: {path}",
                    "Reload the workbook/source manually or update saved session state.",
                ))
        for record in state.photo_records:
            if record.file_path and not os.path.exists(record.file_path):
                issues.append(DataSafetyIssue(
                    "WARNING",
                    "Photo Vault",
                    f"Referenced photo path is missing: {record.file_path}",
                    "Move the photo back or update the photo record path.",
                ))
        photo_report = PhotoVaultIntegrityAudit(
            state.photo_records,
            photo_candidates=getattr(state, "photo_candidates", []) or [],
        ).run()
        for finding in photo_report.findings:
            if finding.issue_type in {
                "Duplicate Photo Reference",
                "Unlinked Photo Record",
                "Invalid File Extension",
                "Unsupported File Path",
                "Candidate Without Photo",
            }:
                issues.append(DataSafetyIssue(
                    "WARNING" if finding.severity != "INFO" else "WARNING",
                    "Photo Vault",
                    f"{finding.issue_type}: {finding.reference or finding.photo_path}",
                    finding.recommendation,
                ))
        return issues

    @staticmethod
    def _recommended_actions(issues: List[DataSafetyIssue]) -> List[str]:
        if not issues:
            return ["Create regular backup packages after major collection sessions."]
        actions = []
        for issue in issues:
            if issue.recommended_action and issue.recommended_action not in actions:
                actions.append(issue.recommended_action)
        return actions

    def _validate_backup_coverage(self, state: AppState) -> List[DataSafetyIssue]:
        issues: List[DataSafetyIssue] = []
        manifest = self._latest_verified_manifest()
        if not manifest:
            issues.append(DataSafetyIssue(
                "WARNING",
                "Backups",
                "No verified backup package found.",
                "Create a backup package and verify it before ending the session.",
            ))
            return issues
        if _yes_no(manifest.collection_json_backed_up) != "YES":
            issues.append(DataSafetyIssue(
                "WARNING",
                "Collection JSON Backup",
                "Latest verified backup package does not include data/collection.json.",
                "Create a new backup package with v2.4.1 or later.",
            ))
        workbook_path = state.collection_workbook_path
        if workbook_path:
            if not os.path.exists(workbook_path):
                issues.append(DataSafetyIssue(
                    "WARNING",
                    "Collection Workbook",
                    f"Persisted workbook path is missing: {workbook_path}",
                    "Save the workbook in a known location and reload collection context.",
                ))
            elif _yes_no(manifest.workbook_backed_up) != "YES":
                issues.append(DataSafetyIssue(
                    "WARNING",
                    "Collection Workbook Backup",
                    "Latest verified backup package does not include the persisted collection workbook.",
                    "Create a new backup package after saving session state.",
                ))
        if _yes_no(manifest.app_state_backed_up) != "YES":
            issues.append(DataSafetyIssue(
                "WARNING",
                "App State Backup",
                "Latest verified backup package does not include app state.",
                "Use Tools -> Save Session State, then create a backup package.",
            ))
        return issues

    def _latest_verified_manifest(self) -> Optional[BackupManifest]:
        packages = []
        if not os.path.isdir(self.backup_dir):
            return None
        for name in os.listdir(self.backup_dir):
            path = os.path.join(self.backup_dir, name)
            if name.lower().endswith(".zip") and os.path.isfile(path):
                packages.append(path)
        for path in sorted(packages, key=os.path.getmtime, reverse=True):
            result = BackupManager(
                backup_dir=self.backup_dir,
                persistence_manager=self.persistence_manager,
                collection_json_path=self.collection_json_path,
            ).verify_backup_package(path)
            if result.success and result.manifest:
                return result.manifest
        return None


class BackupManager:
    """Create, verify, list, restore, and report local backup packages."""

    def __init__(
        self,
        backup_dir: str = os.path.join("backups", "packages"),
        persistence_manager: Optional[PersistenceManager] = None,
        collection_json_path: str = DEFAULT_COLLECTION_JSON_PATH,
        confirmed_observations_path: Optional[str] = None,
    ):
        self.backup_dir = backup_dir
        self.persistence_manager = persistence_manager or PersistenceManager()
        self.collection_json_path = collection_json_path
        self.confirmed_observations_path = confirmed_observations_path or os.path.join(
            self.persistence_manager.state_dir,
            CONFIRMED_OBSERVATIONS_FILENAME,
        )

    def create_backup_package(
        self,
        package_path: Optional[str] = None,
        include_workbook_path: str = "",
        copy_workbook: bool = True,
    ) -> BackupResult:
        """Create a zip package containing safe local app/report files."""

        os.makedirs(self.backup_dir, exist_ok=True)
        package_path = package_path or os.path.join(self.backup_dir, f"coin-analyzer-backup-{_now_stamp()}.zip")
        manifest = BackupManifest(
            backup_created_at=_now_iso(),
            included_files=[],
            excluded_files=[],
            missing_files=[],
            warnings=[
                "Photograph file contents are not included in this backup. "
                "Collection and Photo Vault records preserve photo references/metadata only. "
                "Back up the photograph files separately.",
            ],
            restore_notes=[
                "Restore does not restore photograph file contents; recover them from a separate photograph backup.",
                "Validate backup before restore.",
                "Restore creates a pre-restore backup before overwriting files.",
                "Collection workbook is not modified by restore.",
            ],
        )
        state_result = self.persistence_manager.load_state()
        loaded_state = state_result.state or AppState()
        snapshot_path = os.path.join(self.persistence_manager.state_dir, "collection_snapshots.json")
        candidates = [
            (self.persistence_manager.state_path, "collection_data/app_state/app_state.json"),
            (self.collection_json_path, "data/collection.json"),
            ("RELEASE_HISTORY.md", "release/RELEASE_HISTORY.md"),
            ("README.md", "release/README.md"),
            ("PROJECT_STATE.md", "release/PROJECT_STATE.md"),
            ("TASK_QUEUE.md", "release/TASK_QUEUE.md"),
            ("AI_HANDOFF.md", "release/AI_HANDOFF.md"),
            ("docs/BACKUP.md", "release/docs/BACKUP.md"),
        ]
        if os.path.exists(snapshot_path):
            candidates.append((snapshot_path, "collection_data/app_state/collection_snapshots.json"))
        if os.path.exists(self.confirmed_observations_path):
            candidates.append((
                self.confirmed_observations_path,
                f"collection_data/app_state/{CONFIRMED_OBSERVATIONS_FILENAME}",
            ))
        release_dir = os.path.join("docs", "releases")
        if os.path.isdir(release_dir):
            for name in sorted(os.listdir(release_dir)):
                if name.endswith(".md"):
                    candidates.append((os.path.join(release_dir, name), f"release/docs/releases/{name}"))

        workbook_path = include_workbook_path or loaded_state.collection_workbook_path
        if workbook_path:
            if copy_workbook:
                candidates.append((workbook_path, f"collection_workbook/{os.path.basename(workbook_path)}"))
            else:
                manifest.excluded_files.append(workbook_path)
                manifest.warnings.append("Collection workbook path recorded but workbook was not copied.")
        else:
            manifest.warnings.append("No persisted collection workbook path found; workbook was not backed up.")
        try:
            with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for source, archive_name in candidates:
                    if os.path.exists(source):
                        record = BackupFileRecord(
                            source_path=source,
                            archive_path=archive_name.replace("\\", "/"),
                            size_bytes=os.path.getsize(source),
                            sha256=_sha256(source),
                        )
                        archive.write(source, record.archive_path)
                        manifest.included_files.append(record)
                    else:
                        manifest.missing_files.append(source)
                        if archive_name == "data/collection.json":
                            manifest.warnings.append("Production collection JSON was not found and was not backed up.")
                        elif archive_name.startswith("collection_workbook/"):
                            manifest.warnings.append(f"Collection workbook was not found and was not backed up: {source}")
                manifest.collection_json_backed_up = _yes_no(any(record.archive_path == "data/collection.json" for record in manifest.included_files))
                manifest.workbook_backed_up = _yes_no(any(record.archive_path.startswith("collection_workbook/") for record in manifest.included_files))
                manifest.app_state_backed_up = _yes_no(any(record.archive_path == "collection_data/app_state/app_state.json" for record in manifest.included_files))
                archive.writestr(MANIFEST_NAME, json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n")
                archive.writestr(MANIFEST_MARKDOWN_NAME, manifest.format_markdown())
            return BackupResult(True, "Backup package created", package_path=package_path, manifest=manifest, warnings=list(manifest.warnings))
        except Exception as exc:
            return BackupResult(False, "Backup package creation failed", package_path=package_path, manifest=manifest, errors=[str(exc)])

    def verify_backup_package(self, package_path: str) -> BackupResult:
        """Validate backup zip, manifest, and file checksums."""

        if not os.path.exists(package_path):
            return BackupResult(False, "Backup package missing", package_path=package_path, errors=["Backup not found"])
        try:
            with ExitStack() as stack:
                snapshot = _snapshot_backup(package_path, stack)
                manifest, _ = _verify_backup_archive(snapshot, stack)
            return BackupResult(True, "Backup verified", package_path=package_path,
                                manifest=manifest, warnings=list(manifest.warnings))
        except Exception as exc:
            return BackupResult(False, "Backup verification failed", package_path=package_path, errors=[str(exc)])

    def collection_recovery_report(self, package_path: str = "") -> CollectionRecoveryReport:
        """Summarize what core collection data can be recovered from a backup."""

        target = package_path or self._latest_backup_path()
        if not target:
            return CollectionRecoveryReport(
                status="FAIL",
                warnings=["No backup package found."],
                recommendations=["Create a backup package before ending the session."],
            )
        verified = self.verify_backup_package(target)
        if not verified.success or not verified.manifest:
            return CollectionRecoveryReport(
                status="FAIL",
                package_path=target,
                warnings=list(verified.errors),
                recommendations=["Create a fresh backup package and verify it."],
            )
        manifest = verified.manifest
        recoverable: List[str] = []
        not_recoverable: List[str] = []
        recommendations: List[str] = []
        warnings = list(manifest.warnings)
        if _yes_no(manifest.collection_json_backed_up) == "YES":
            recoverable.append("data/collection.json ownership records")
        else:
            not_recoverable.append("data/collection.json ownership records")
            recommendations.append("Create a v2.4.1 backup package that includes data/collection.json.")
        if _yes_no(manifest.workbook_backed_up) == "YES":
            recoverable.append("collection workbook copy")
        else:
            not_recoverable.append("collection workbook copy")
            recommendations.append("Save session state with the workbook path, then create a backup package.")
        if _yes_no(manifest.app_state_backed_up) == "YES":
            recoverable.extend([
                "app state",
                "market records stored in app state",
                "photo metadata stored in app state",
                "photo candidate metadata stored in app state",
                "shopping candidates stored in app state",
            ])
            warnings.append("Photo files copied: NO; backup packages preserve photo metadata but do not copy arbitrary photo folders.")
            recommendations.append("Keep photo folders in regular external backups; app backup packages preserve metadata only.")
        else:
            not_recoverable.append("app state, market records, photo metadata, and shopping candidates")
            recommendations.append("Use Tools -> Save Session State before creating the next backup package.")
        not_recoverable.extend(f"Missing file: {path}" for path in manifest.missing_files)
        status = "PASS"
        if _yes_no(manifest.collection_json_backed_up) != "YES":
            status = "FAIL"
        elif not_recoverable:
            status = "WARNING"
        return CollectionRecoveryReport(
            status=status,
            package_path=target,
            collection_json_backed_up=manifest.collection_json_backed_up,
            workbook_backed_up=manifest.workbook_backed_up,
            app_state_backed_up=manifest.app_state_backed_up,
            recoverable=recoverable,
            not_recoverable=not_recoverable,
            missing_files=list(manifest.missing_files),
            warnings=warnings,
            recommendations=recommendations or ["Keep this backup package and maintain off-machine copies."],
        )

    def list_available_backups(self) -> List[Dict[str, Any]]:
        """List backup zip packages in the configured backup directory."""

        if not os.path.isdir(self.backup_dir):
            return []
        rows = []
        for name in sorted(os.listdir(self.backup_dir)):
            path = os.path.join(self.backup_dir, name)
            if not name.lower().endswith(".zip") or not os.path.isfile(path):
                continue
            rows.append({
                "path": path,
                "name": name,
                "size_bytes": os.path.getsize(path),
                "modified_at": datetime.fromtimestamp(os.path.getmtime(path)).replace(microsecond=0).isoformat(sep=" "),
            })
        return rows

    def backup_metadata_report(self, package_path: str) -> BackupResult:
        """Return manifest metadata for display/reporting."""

        return self.verify_backup_package(package_path)

    def restore_from_backup_package(
        self,
        package_path: str,
        restore_root: str = ".",
        overwrite: bool = False,
    ) -> BackupResult:
        """Restore known safe files from a verified backup package."""

        pre_restore = None
        try:
            with ExitStack() as stack:
                snapshot = _snapshot_backup(package_path, stack)
                manifest, staged = _verify_backup_archive(snapshot, stack, stage=True)
                skipped = [record.archive_path for record in manifest.included_files
                           if record.archive_path not in staged]

                def before_write():
                    nonlocal pre_restore
                    # Unique name prevents a same-second pre-backup from
                    # truncating the input package or an earlier backup.
                    pre_restore = self.create_backup_package(os.path.join(
                        self.backup_dir, f"pre-restore-{uuid.uuid4().hex}.zip"))
                    if not pre_restore.success:
                        raise OSError("Pre-restore backup failed; restore aborted")

                restored, existing, warnings = _restore_staged_files(
                    Path(os.path.abspath(restore_root)), staged, overwrite, stack, before_write)
                return BackupResult(
                    True, "Restore completed", package_path=package_path,
                    manifest=manifest, restored_files=restored,
                    skipped_files=skipped + existing,
                    pre_restore_backup_path=pre_restore.package_path if pre_restore else "",
                    warnings=list(manifest.warnings) + warnings + (pre_restore.warnings if pre_restore else []),
                )
        except Exception as exc:
            return BackupResult(False, "Restore failed", package_path=package_path,
                                pre_restore_backup_path=pre_restore.package_path if pre_restore else "",
                                errors=[str(exc)])

    def _latest_backup_path(self) -> str:
        backups = self.list_available_backups()
        if not backups:
            return ""
        return max(backups, key=lambda row: row["modified_at"])["path"]

    def export_collector_bundle(
        self,
        output_dir: str,
        items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        shopping_candidates: Optional[Iterable[ShoppingCandidate]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        photo_records: Optional[Iterable[PhotoRecord]] = None,
    ) -> BackupResult:
        """Generate a reporting/export bundle without modifying collection data."""

        try:
            os.makedirs(output_dir, exist_ok=True)
            items = list(items or [])
            want_list_intents = list(want_list_intents or [])
            shopping_candidates = list(shopping_candidates or [])
            market = market_awareness_engine or MarketAwarenessEngine()
            photos = list(photo_records or [])

            manifest = BackupManifest(backup_created_at=_now_iso())
            paths = []
            health = CollectionHealthReportEngine(items, want_list_intents, shopping_candidates, market, photos)
            paths.append(self._write_text(output_dir, "collection_health_report.md", health.format_markdown()))
            dashboard = CollectionDashboard(items, want_list_intents, photo_records=photos, market_awareness_engine=market, shopping_candidates=shopping_candidates)
            paths.append(self._write_text(output_dir, "collection_dashboard.md", dashboard.format_markdown()))
            shopping = SmartShoppingAssistant(items, want_list_intents, market)
            shopping_report = shopping.generate_report(shopping_candidates, include_want_list_targets=bool(want_list_intents), limit=10)
            paths.append(self._write_text(output_dir, "shopping_recommendations.md", shopping.format_markdown(shopping_report)))
            paths.append(self._write_text(output_dir, "market_awareness_summary.md", market.format_markdown()))
            paths.append(self._write_text(output_dir, "series_summary.md", SeriesTracker(items, want_list_intents).format_markdown()))
            paths.append(self._write_text(output_dir, "photo_coverage_summary.md", PhotoVault(photos, items).format_markdown()))
            csv_path = os.path.join(output_dir, "collector_export_bundle_index.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["file", "size_bytes", "sha256"])
                for path in paths:
                    writer.writerow([os.path.basename(path), os.path.getsize(path), _sha256(path)])
            paths.append(csv_path)
            for path in paths:
                manifest.included_files.append(BackupFileRecord(path, os.path.basename(path), os.path.getsize(path), _sha256(path)))
            manifest_path = os.path.join(output_dir, MANIFEST_NAME)
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump(manifest.to_dict(), handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            return BackupResult(True, "Collector export bundle created", package_path=output_dir, manifest=manifest)
        except Exception as exc:
            return BackupResult(False, "Collector export bundle failed", package_path=output_dir, errors=[str(exc)])

    @staticmethod
    def _write_text(output_dir: str, name: str, text: str) -> str:
        path = os.path.join(output_dir, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path
