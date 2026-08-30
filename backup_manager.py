"""Data safety, backup, restore, and validation helpers.

This module uses local files only. It does not sync to cloud services, call
APIs, scrape listings, or modify collection workbooks.
"""

from __future__ import annotations

import csv
import hashlib
import json
import ntpath
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import unicodedata
from uuid import UUID, uuid4
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from collection_dashboard import CollectionDashboard
from collector_operating_system import CollectionHealthReportEngine
from confirmed_observations import CONFIRMED_OBSERVATIONS_FILENAME
from coin_collection import deserialize_collection_payload
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
PORTABLE_BACKUP_VERSION = 1
PORTABLE_COLLECTION_MEMBER = "portable/collection/collection.json"


_PORTABLE_MANIFEST_FIELDS = frozenset({
    "portable_collection_backup_version",
    "authoritative_collection",
    "members",
    "photo_references",
    "capture_import_roots",
})
_PORTABLE_COLLECTION_FIELDS = frozenset({
    "archive_member", "byte_length", "sha256", "item_count", "stable_ids",
})
_PORTABLE_MEMBER_FIELDS = frozenset({
    "archive_member", "byte_length", "sha256", "member_type", "ownership",
})
_PORTABLE_PHOTO_FIELDS = frozenset({
    "item_id", "photo_index", "stored_reference", "ownership",
    "archive_member", "capture_import_id", "owner_archive_member",
})
_PORTABLE_CAPTURE_ROOT_FIELDS = frozenset({
    "import_id", "owner_archive_member", "media_archive_members",
})
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


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


@dataclass(frozen=True)
class PortableBackupManifest:
    """Closed version-1 portable collection backup manifest."""

    authoritative_collection: Dict[str, Any]
    members: tuple[Dict[str, Any], ...]
    photo_references: tuple[Dict[str, Any], ...]
    capture_import_roots: tuple[Dict[str, Any], ...]
    portable_collection_backup_version: int = PORTABLE_BACKUP_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portable_collection_backup_version": self.portable_collection_backup_version,
            "authoritative_collection": dict(self.authoritative_collection),
            "members": [dict(value) for value in self.members],
            "photo_references": [dict(value) for value in self.photo_references],
            "capture_import_roots": [dict(value) for value in self.capture_import_roots],
        }


@dataclass
class BackupResult:
    success: bool
    status: str
    package_path: str = ""
    manifest: Optional[BackupManifest | PortableBackupManifest] = None
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
            if result.success and isinstance(result.manifest, BackupManifest):
                return result.manifest
        return None


class _PortableBackupError(ValueError):
    """Fail-closed portable backup validation error."""


def _portable_sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_stable_regular_file(path: Path, label: str) -> bytes:
    """Read one plain file while checking identity and metadata stability."""

    try:
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode) or _is_link_or_reparse(before):
            raise _PortableBackupError(f"{label} is not a plain regular file: {path}")
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise _PortableBackupError(f"{label} changed before it could be read: {path}")
            payload = handle.read()
            after_handle = os.fstat(handle.fileno())
        after = os.lstat(path)
    except _PortableBackupError:
        raise
    except OSError as error:
        raise _PortableBackupError(f"{label} is missing or unreadable: {path}: {error}") from error
    identity = (before.st_dev, before.st_ino)
    if (
        (after.st_dev, after.st_ino) != identity
        or (after_handle.st_dev, after_handle.st_ino) != identity
        or before.st_size != len(payload)
        or after.st_size != len(payload)
        or after_handle.st_size != len(payload)
        or getattr(before, "st_mtime_ns", None) != getattr(after, "st_mtime_ns", None)
    ):
        raise _PortableBackupError(f"{label} changed while it was being read: {path}")
    return payload


def _is_link_or_reparse(value: os.stat_result) -> bool:
    attributes = getattr(value, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(value.st_mode) or bool(attributes & reparse)


def _require_plain_path_below(root: Path, path: Path, label: str) -> None:
    try:
        root_info = os.lstat(root)
    except OSError as error:
        raise _PortableBackupError(
            f"{label} ownership root is missing or unreadable: {root}: {error}"
        ) from error
    if not stat.S_ISDIR(root_info.st_mode) or _is_link_or_reparse(root_info):
        raise _PortableBackupError(
            f"{label} ownership root is not a plain directory: {root}"
        )
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise _PortableBackupError(f"{label} is outside its managed ownership root: {path}") from error
    current = root
    for part in relative.parts:
        current = current / part
        try:
            info = os.lstat(current)
        except OSError as error:
            raise _PortableBackupError(f"{label} is missing or unreadable: {path}: {error}") from error
        if _is_link_or_reparse(info):
            raise _PortableBackupError(f"{label} traverses a link or reparse point: {path}")


def _canonical_uuid4(value: str, label: str) -> str:
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError) as error:
        raise _PortableBackupError(f"{label} must be a canonical UUIDv4") from error
    if parsed.version != 4 or str(parsed) != value:
        raise _PortableBackupError(f"{label} must be a canonical UUIDv4")
    return value


def _portable_archive_key(name: str) -> str:
    """Validate an archive file path and return its collision key."""

    if not isinstance(name, str) or not name or "\x00" in name or "\\" in name:
        raise _PortableBackupError(f"Unsafe ZIP member path: {name!r}")
    drive, _tail = ntpath.splitdrive(name)
    pure = PurePosixPath(name)
    if drive or pure.is_absolute() or name.startswith("/"):
        raise _PortableBackupError(f"Unsafe absolute or drive-qualified ZIP member: {name!r}")
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise _PortableBackupError(f"Unsafe ZIP member path component: {name!r}")
    normalized_parts = []
    for part in parts:
        if ":" in part or part != part.rstrip(" ."):
            raise _PortableBackupError(f"Unsafe Windows ZIP member component: {name!r}")
        normalized = unicodedata.normalize("NFC", part).rstrip(" .").casefold()
        if not normalized:
            raise _PortableBackupError(f"Unsafe normalized ZIP member path: {name!r}")
        device_stem = normalized.split(".", 1)[0]
        if device_stem in {"con", "prn", "aux", "nul"} or re.fullmatch(
            r"(?:com|lpt)[1-9]", device_stem
        ):
            raise _PortableBackupError(f"Unsafe reserved ZIP member component: {name!r}")
        normalized_parts.append(normalized)
    return "/".join(normalized_parts)


def _portable_reference_parts(reference: str) -> tuple[str, ...]:
    if not isinstance(reference, str) or not reference.strip() or "\x00" in reference:
        raise _PortableBackupError("Collection photo reference must be nonblank")
    normalized = reference.replace("\\", "/")
    parts = tuple(part for part in normalized.split("/") if part not in {"", "."})
    if ".." in parts:
        raise _PortableBackupError(f"Collection photo reference contains parent traversal: {reference}")
    return parts


def _portable_capture_import_id(reference: str, expected: str = "") -> str:
    parts = _portable_reference_parts(reference)
    candidates = [
        parts[index + 1]
        for index, part in enumerate(parts[:-1])
        if part == "imports" and index + 3 < len(parts)
    ]
    if expected:
        if expected not in candidates:
            raise _PortableBackupError(
                f"Capture-import reference does not match provenance import_id {expected}: {reference}"
            )
        return _canonical_uuid4(expected, "capture import_id")
    for candidate in reversed(candidates):
        try:
            return _canonical_uuid4(candidate, "capture import_id")
        except _PortableBackupError:
            continue
    raise _PortableBackupError(f"Reference is not capture-import managed media: {reference}")


def _require_portable_capture_item_reference(
    reference: str,
    import_id: str,
    item_id: str,
) -> None:
    """Require the canonical imports/<import>/<item>/<file> ownership suffix."""

    if not isinstance(item_id, str) or "/" in item_id or "\\" in item_id:
        raise _PortableBackupError(
            "Capture-import collection item id must be one safe path component"
        )
    _portable_archive_key(item_id)
    parts = _portable_reference_parts(reference)
    matches = [
        index
        for index in range(len(parts) - 3)
        if (
            parts[index] == "imports"
            and parts[index + 1] == import_id
            and parts[index + 2] == item_id
            and index + 4 == len(parts)
        )
    ]
    if len(matches) != 1:
        raise _PortableBackupError(
            "Capture-import reference does not have the canonical item-owned "
            f"suffix for item {item_id}: {reference}"
        )


def _portable_owner_payload(payload: bytes, import_id: str) -> Dict[str, str]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _PortableBackupError(f"Capture-import owner artifact is invalid JSON for {import_id}") from error
    expected_fields = {"ownership_schema_version", "import_id", "random_ownership_token"}
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise _PortableBackupError(f"Capture-import owner artifact has unsupported fields for {import_id}")
    if value["ownership_schema_version"] != "1.0" or value["import_id"] != import_id:
        raise _PortableBackupError(f"Capture-import owner artifact does not match import {import_id}")
    _canonical_uuid4(value["random_ownership_token"], "capture ownership token")
    return value


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

    def create_portable_backup_package(
        self,
        package_path: Optional[str] = None,
    ) -> BackupResult:
        """Create and independently verify a complete portable v1 package."""

        target = Path(package_path or os.path.join(
            self.backup_dir, f"coin-analyzer-portable-{_now_stamp()}.zip"
        ))
        temporary_path: Path | None = None
        try:
            if target.exists():
                raise _PortableBackupError(f"Portable backup target already exists: {target}")
            collection_source = Path(self.collection_json_path)
            collection_bytes = _read_stable_regular_file(
                collection_source, "Authoritative collection"
            )
            try:
                payload = json.loads(collection_bytes.decode("utf-8"))
                _collection_format, _records, items = deserialize_collection_payload(payload)
            except Exception as error:
                raise _PortableBackupError(
                    f"Authoritative collection is INVALID_OR_UNSUPPORTED: {error}"
                ) from error

            stable_ids = [item.id for item in items]
            ordinary_root = (
                collection_source.parent / "managed_media" / "ordinary"
            ).absolute()
            members_by_archive: Dict[str, Dict[str, Any]] = {}
            bytes_by_archive: Dict[str, bytes] = {}
            source_to_archive: Dict[tuple[str, str], str] = {}
            source_expectations: Dict[Path, tuple[int, str, str]] = {
                collection_source: (
                    len(collection_bytes),
                    _portable_sha256_bytes(collection_bytes),
                    "Authoritative collection",
                )
            }
            owner_members: Dict[str, str] = {}
            capture_media: Dict[str, set[str]] = {}
            photo_records: List[Dict[str, Any]] = []

            collection_record = {
                "archive_member": PORTABLE_COLLECTION_MEMBER,
                "byte_length": len(collection_bytes),
                "sha256": _portable_sha256_bytes(collection_bytes),
                "member_type": "authoritative_collection",
                "ownership": "collection",
            }
            members_by_archive[PORTABLE_COLLECTION_MEMBER] = collection_record
            bytes_by_archive[PORTABLE_COLLECTION_MEMBER] = collection_bytes

            for item in items:
                for photo_index, photo in enumerate(item.normalized_photos()):
                    reference = photo.path.strip()
                    if not reference:
                        continue
                    source = Path(reference).absolute()
                    provenance = photo.capture_import_media
                    ownership = ""
                    import_id = ""
                    owner_archive_member = ""
                    try:
                        source.relative_to(ordinary_root)
                        is_ordinary_path = True
                    except ValueError:
                        is_ordinary_path = False

                    if is_ordinary_path and provenance is None:
                        ownership = "ordinary_entry"
                        _require_plain_path_below(
                            ordinary_root, source, f"Managed photo for item {item.id}"
                        )
                    else:
                        if provenance is None:
                            raise _PortableBackupError(
                                f"Item {item.id} has external/unmanaged photo reference "
                                f"{reference}: capture-import provenance is absent"
                            )
                        expected_import_id = provenance.import_id
                        try:
                            import_id = _portable_capture_import_id(
                                reference, expected_import_id
                            )
                            _require_portable_capture_item_reference(
                                reference, import_id, item.id
                            )
                        except _PortableBackupError as error:
                            raise _PortableBackupError(
                                f"Item {item.id} has external/unmanaged photo reference "
                                f"{reference!r}: {error}"
                            ) from error
                        ownership = "capture_import"
                        parts = source.parts
                        matching = [
                            index for index, part in enumerate(parts[:-1])
                            if part == "imports" and parts[index + 1] == import_id
                        ]
                        if not matching:
                            raise _PortableBackupError(
                                f"Item {item.id} capture-import reference cannot be resolved: {reference!r}"
                            )
                        import_root = Path(*parts[: matching[-1] + 2])
                        _require_plain_path_below(
                            import_root, source, f"Capture-import photo for item {item.id}"
                        )
                        owner_source = import_root / ".import-owner.json"
                        owner_bytes = _read_stable_regular_file(
                            owner_source, f"Capture-import owner artifact for item {item.id}"
                        )
                        owner_expectation = (
                            len(owner_bytes),
                            _portable_sha256_bytes(owner_bytes),
                            f"Capture-import owner artifact for item {item.id}",
                        )
                        previous_owner = source_expectations.get(owner_source)
                        if previous_owner is not None and previous_owner[:2] != owner_expectation[:2]:
                            raise _PortableBackupError(
                                f"Capture-import owner artifact changed during packaging: {owner_source}"
                            )
                        source_expectations[owner_source] = owner_expectation
                        _portable_owner_payload(owner_bytes, import_id)
                        owner_archive_member = (
                            f"portable/media/capture_import/{import_id}/.import-owner.json"
                        )
                        existing_owner = bytes_by_archive.get(owner_archive_member)
                        if existing_owner is not None and existing_owner != owner_bytes:
                            raise _PortableBackupError(
                                f"Capture-import owner artifact changed or conflicts for {import_id}"
                            )
                        bytes_by_archive[owner_archive_member] = owner_bytes
                        members_by_archive[owner_archive_member] = {
                            "archive_member": owner_archive_member,
                            "byte_length": len(owner_bytes),
                            "sha256": _portable_sha256_bytes(owner_bytes),
                            "member_type": "capture_import_owner",
                            "ownership": "capture_import",
                        }
                        owner_members[import_id] = owner_archive_member
                        capture_media.setdefault(import_id, set())

                    media_bytes = _read_stable_regular_file(
                        source, f"Managed photo for item {item.id} reference {reference!r}"
                    )
                    media_sha256 = _portable_sha256_bytes(media_bytes)
                    media_expectation = (
                        len(media_bytes), media_sha256,
                        f"Managed photo for item {item.id} reference {reference!r}",
                    )
                    previous_media = source_expectations.get(source)
                    if previous_media is not None and previous_media[:2] != media_expectation[:2]:
                        raise _PortableBackupError(
                            f"Managed photo changed during packaging: {source}"
                        )
                    source_expectations[source] = media_expectation
                    if provenance is not None and provenance.artifact_sha256 != media_sha256:
                        raise _PortableBackupError(
                            f"Item {item.id} capture-import provenance hash does not match {reference!r}"
                        )
                    suffix = source.suffix.lower()
                    if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix) is None:
                        suffix = ".bin"
                    source_key = (ownership, str(source))
                    archive_member = source_to_archive.get(source_key, "")
                    if not archive_member:
                        if ownership == "ordinary_entry":
                            archive_member = f"portable/media/ordinary/{media_sha256}{suffix}"
                        else:
                            archive_member = (
                                f"portable/media/capture_import/{import_id}/{media_sha256}{suffix}"
                            )
                        existing = bytes_by_archive.get(archive_member)
                        if existing is not None and existing != media_bytes:
                            raise _PortableBackupError(
                                f"Managed media archive-name collision for {reference!r}"
                            )
                        bytes_by_archive[archive_member] = media_bytes
                        members_by_archive[archive_member] = {
                            "archive_member": archive_member,
                            "byte_length": len(media_bytes),
                            "sha256": media_sha256,
                            "member_type": "managed_photo",
                            "ownership": ownership,
                        }
                        source_to_archive[source_key] = archive_member
                    if import_id:
                        capture_media[import_id].add(archive_member)
                    photo_records.append({
                        "item_id": item.id,
                        "photo_index": photo_index,
                        "stored_reference": reference,
                        "ownership": ownership,
                        "archive_member": archive_member,
                        "capture_import_id": import_id,
                        "owner_archive_member": owner_archive_member,
                    })

            ordered_members = tuple(
                members_by_archive[name] for name in sorted(members_by_archive)
            )
            capture_roots = tuple({
                "import_id": import_id,
                "owner_archive_member": owner_members[import_id],
                "media_archive_members": sorted(capture_media[import_id]),
            } for import_id in sorted(capture_media))
            manifest = PortableBackupManifest(
                authoritative_collection={
                    "archive_member": PORTABLE_COLLECTION_MEMBER,
                    "byte_length": len(collection_bytes),
                    "sha256": collection_record["sha256"],
                    "item_count": len(items),
                    "stable_ids": stable_ids,
                },
                members=ordered_members,
                photo_references=tuple(photo_records),
                capture_import_roots=capture_roots,
            )
            manifest_bytes = (
                json.dumps(
                    manifest.to_dict(), indent=2, ensure_ascii=False, sort_keys=True
                ) + "\n"
            ).encode("utf-8")

            for source, (expected_length, expected_sha256, label) in sorted(
                source_expectations.items(), key=lambda value: str(value[0])
            ):
                observed = _read_stable_regular_file(source, label)
                if (
                    len(observed) != expected_length
                    or _portable_sha256_bytes(observed) != expected_sha256
                ):
                    raise _PortableBackupError(
                        f"{label} changed during portable backup creation: {source}"
                    )

            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.", suffix=f".{uuid4().hex}.partial",
                dir=target.parent,
            )
            os.close(descriptor)
            temporary_path = Path(temporary_name)
            with zipfile.ZipFile(
                temporary_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for name in sorted(bytes_by_archive):
                    archive.writestr(name, bytes_by_archive[name])
                archive.writestr(MANIFEST_NAME, manifest_bytes)

            verified = self.verify_backup_package(str(temporary_path))
            if not verified.success:
                raise _PortableBackupError(
                    "Created portable package failed independent verification: "
                    + "; ".join(verified.errors)
                )
            os.link(temporary_path, target)
            temporary_path.unlink()
            temporary_path = None
            return BackupResult(
                True,
                "Complete portable collection backup created and verified",
                package_path=str(target),
                manifest=verified.manifest,
            )
        except Exception as error:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
            return BackupResult(
                False,
                "Portable backup package creation failed",
                package_path=str(target),
                errors=[str(error) or type(error).__name__],
            )

    def create_backup_package(
        self,
        package_path: Optional[str] = None,
        include_workbook_path: str = "",
        copy_workbook: bool = True,
        *,
        portable: bool = False,
    ) -> BackupResult:
        """Create a zip package containing safe local app/report files."""

        if portable:
            if include_workbook_path or not copy_workbook:
                return BackupResult(
                    False,
                    "Portable backup package creation failed",
                    package_path=package_path or "",
                    errors=[
                        "Legacy workbook options are not part of the closed portable-v1 package."
                    ],
                )
            return self.create_portable_backup_package(package_path)

        os.makedirs(self.backup_dir, exist_ok=True)
        package_path = package_path or os.path.join(self.backup_dir, f"coin-analyzer-backup-{_now_stamp()}.zip")
        manifest = BackupManifest(
            backup_created_at=_now_iso(),
            included_files=[],
            excluded_files=[],
            missing_files=[],
            warnings=[],
            restore_notes=[
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
        """Independently verify a portable-v1 or legacy backup package."""

        if not os.path.exists(package_path):
            return BackupResult(False, "Backup package missing", package_path=package_path, errors=[f"Backup not found: {package_path}"])
        try:
            with zipfile.ZipFile(package_path, "r") as archive:
                if archive.testzip():
                    return BackupResult(False, "Backup zip is corrupt", package_path=package_path, errors=["Zip integrity check failed"])
                manifest_infos = [
                    info for info in archive.infolist() if info.filename == MANIFEST_NAME
                ]
                if len(manifest_infos) != 1:
                    return BackupResult(False, "Backup manifest missing", package_path=package_path, errors=["backup_manifest.json not found"])
                raw_manifest = archive.read(manifest_infos[0])
                payload = json.loads(raw_manifest.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise _PortableBackupError("Backup manifest must be a JSON object")
                if "portable_collection_backup_version" in payload:
                    return self._verify_portable_backup_archive(
                        archive, payload, package_path
                    )
                return self._verify_legacy_backup_archive(
                    archive, payload, package_path
                )
        except Exception as exc:
            return BackupResult(False, "Backup verification failed", package_path=package_path, errors=[str(exc)])

    @staticmethod
    def _verify_legacy_backup_archive(
        archive: zipfile.ZipFile,
        payload: Dict[str, Any],
        package_path: str,
    ) -> BackupResult:
        manifest = BackupManifest.from_dict(payload)
        errors = []
        names = archive.namelist()
        for record in manifest.included_files:
            if record.archive_path not in names:
                errors.append(f"Missing archived file: {record.archive_path}")
                continue
            archived = archive.read(record.archive_path)
            digest = hashlib.sha256(archived).hexdigest()
            if record.sha256 and digest != record.sha256:
                errors.append(f"Checksum mismatch: {record.archive_path}")
        if errors:
            return BackupResult(
                False, "Backup verification failed", package_path=package_path,
                manifest=manifest, errors=errors,
            )
        return BackupResult(
            True, "Backup verified", package_path=package_path,
            manifest=manifest, warnings=list(manifest.warnings),
        )

    @staticmethod
    def _verify_portable_backup_archive(
        archive: zipfile.ZipFile,
        payload: Dict[str, Any],
        package_path: str,
    ) -> BackupResult:
        try:
            version = payload.get("portable_collection_backup_version")
            if type(version) is not int or version != PORTABLE_BACKUP_VERSION:
                raise _PortableBackupError(
                    f"Unsupported portable_collection_backup_version: {version!r}"
                )
            if set(payload) != _PORTABLE_MANIFEST_FIELDS:
                raise _PortableBackupError("Portable manifest has unknown or missing top-level fields")
            collection_record = payload["authoritative_collection"]
            member_rows = payload["members"]
            photo_rows = payload["photo_references"]
            root_rows = payload["capture_import_roots"]
            if (
                not isinstance(collection_record, dict)
                or set(collection_record) != _PORTABLE_COLLECTION_FIELDS
                or not isinstance(member_rows, list)
                or not isinstance(photo_rows, list)
                or not isinstance(root_rows, list)
            ):
                raise _PortableBackupError("Portable manifest structure is invalid")

            archive_infos = archive.infolist()
            seen_keys: Dict[str, str] = {}
            info_by_name: Dict[str, zipfile.ZipInfo] = {}
            for info in archive_infos:
                if info.is_dir():
                    raise _PortableBackupError(
                        f"Undeclared directory member is not allowed: {info.filename!r}"
                    )
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                file_type = stat.S_IFMT(unix_mode)
                if file_type not in {0, stat.S_IFREG}:
                    raise _PortableBackupError(
                        f"ZIP member is not a plain regular file: {info.filename!r}"
                    )
                key = _portable_archive_key(info.filename)
                if key in seen_keys:
                    raise _PortableBackupError(
                        f"Duplicate or normalized ZIP member collision: "
                        f"{seen_keys[key]!r} and {info.filename!r}"
                    )
                seen_keys[key] = info.filename
                info_by_name[info.filename] = info

            for key, name in seen_keys.items():
                parts = key.split("/")
                for end in range(1, len(parts)):
                    ancestor_key = "/".join(parts[:end])
                    if ancestor_key in seen_keys:
                        raise _PortableBackupError(
                            "ZIP member file/directory prefix collision: "
                            f"{seen_keys[ancestor_key]!r} and {name!r}"
                        )

            members: Dict[str, Dict[str, Any]] = {}
            verified_bytes: Dict[str, bytes] = {}
            for index, row in enumerate(member_rows):
                if not isinstance(row, dict) or set(row) != _PORTABLE_MEMBER_FIELDS:
                    raise _PortableBackupError(f"Portable member record {index} is not closed")
                name = row["archive_member"]
                _portable_archive_key(name)
                if name in members:
                    raise _PortableBackupError(f"Duplicate declared member: {name}")
                if row["member_type"] not in {
                    "authoritative_collection", "managed_photo", "capture_import_owner"
                } or row["ownership"] not in {
                    "collection", "ordinary_entry", "capture_import"
                }:
                    raise _PortableBackupError(f"Unsupported member classification: {name}")
                valid_pair = (
                    (row["member_type"], row["ownership"])
                    in {
                        ("authoritative_collection", "collection"),
                        ("managed_photo", "ordinary_entry"),
                        ("managed_photo", "capture_import"),
                        ("capture_import_owner", "capture_import"),
                    }
                )
                if not valid_pair:
                    raise _PortableBackupError(f"Conflicting member classification: {name}")
                if type(row["byte_length"]) is not int or row["byte_length"] < 0:
                    raise _PortableBackupError(f"Invalid byte length for {name}")
                if not isinstance(row["sha256"], str) or _SHA256_PATTERN.fullmatch(row["sha256"]) is None:
                    raise _PortableBackupError(f"Invalid SHA-256 for {name}")
                info = info_by_name.get(name)
                if info is None:
                    raise _PortableBackupError(f"Missing declared member: {name}")
                if info.file_size != row["byte_length"]:
                    raise _PortableBackupError(f"Byte-length mismatch: {name}")
                content = archive.read(info)
                if len(content) != row["byte_length"]:
                    raise _PortableBackupError(f"Byte-length mismatch: {name}")
                if _portable_sha256_bytes(content) != row["sha256"]:
                    raise _PortableBackupError(f"SHA-256 mismatch: {name}")
                members[name] = row
                verified_bytes[name] = content

            expected_names = {MANIFEST_NAME, *members}
            if set(info_by_name) != expected_names:
                undeclared = sorted(set(info_by_name) - expected_names)
                missing = sorted(expected_names - set(info_by_name))
                raise _PortableBackupError(
                    f"Portable package inventory is not closed; undeclared={undeclared!r}, missing={missing!r}"
                )

            collection_member = collection_record["archive_member"]
            if collection_member != PORTABLE_COLLECTION_MEMBER:
                raise _PortableBackupError("Authoritative collection member is not canonical")
            declared_collection = members.get(collection_member)
            if declared_collection is None or declared_collection["member_type"] != "authoritative_collection" or declared_collection["ownership"] != "collection":
                raise _PortableBackupError("Authoritative collection member classification is invalid")
            authoritative_members = {
                name for name, row in members.items()
                if row["member_type"] == "authoritative_collection"
            }
            if authoritative_members != {collection_member}:
                raise _PortableBackupError("Authoritative collection inventory is not exact")
            for field in ("byte_length", "sha256"):
                if collection_record[field] != declared_collection[field]:
                    raise _PortableBackupError(f"Authoritative collection {field} disagrees with member inventory")
            if type(collection_record["item_count"]) is not int or collection_record["item_count"] < 0:
                raise _PortableBackupError("Authoritative item_count is invalid")
            if not isinstance(collection_record["stable_ids"], list) or any(
                not isinstance(value, str) or not value.strip()
                for value in collection_record["stable_ids"]
            ):
                raise _PortableBackupError("Authoritative stable-ID roster is invalid")
            try:
                collection_payload = json.loads(
                    verified_bytes[collection_member].decode("utf-8")
                )
                _format, _records, items = deserialize_collection_payload(collection_payload)
            except Exception as error:
                raise _PortableBackupError(
                    f"Packaged collection is INVALID_OR_UNSUPPORTED: {error}"
                ) from error
            stable_ids = [item.id for item in items]
            if collection_record["item_count"] != len(items):
                raise _PortableBackupError("Manifest item count does not match packaged collection")
            if collection_record["stable_ids"] != stable_ids:
                raise _PortableBackupError("Manifest stable-ID roster does not match packaged collection")

            roots: Dict[str, Dict[str, Any]] = {}
            for index, row in enumerate(root_rows):
                if not isinstance(row, dict) or set(row) != _PORTABLE_CAPTURE_ROOT_FIELDS:
                    raise _PortableBackupError(f"Capture-import root record {index} is not closed")
                import_id = _canonical_uuid4(row["import_id"], "capture import_id")
                if import_id in roots:
                    raise _PortableBackupError(f"Duplicate capture-import root: {import_id}")
                expected_owner = f"portable/media/capture_import/{import_id}/.import-owner.json"
                if row["owner_archive_member"] != expected_owner:
                    raise _PortableBackupError(f"Capture-import owner member is not canonical for {import_id}")
                owner_record = members.get(expected_owner)
                if owner_record is None or owner_record["member_type"] != "capture_import_owner" or owner_record["ownership"] != "capture_import":
                    raise _PortableBackupError(f"Capture-import owner artifact is missing for {import_id}")
                _portable_owner_payload(verified_bytes[expected_owner], import_id)
                media_names = row["media_archive_members"]
                if not isinstance(media_names, list) or media_names != sorted(set(media_names)):
                    raise _PortableBackupError(f"Capture-import media roster is invalid for {import_id}")
                for name in media_names:
                    record = members.get(name)
                    if record is None or record["member_type"] != "managed_photo" or record["ownership"] != "capture_import" or not name.startswith(f"portable/media/capture_import/{import_id}/"):
                        raise _PortableBackupError(f"Capture-import media member is invalid for {import_id}: {name}")
                roots[import_id] = row

            mappings: Dict[tuple[str, int], Dict[str, Any]] = {}
            for index, row in enumerate(photo_rows):
                if not isinstance(row, dict) or set(row) != _PORTABLE_PHOTO_FIELDS:
                    raise _PortableBackupError(f"Photo-reference record {index} is not closed")
                if not isinstance(row["item_id"], str) or type(row["photo_index"]) is not int or row["photo_index"] < 0:
                    raise _PortableBackupError(f"Photo-reference identity is invalid at index {index}")
                key = (row["item_id"], row["photo_index"])
                if key in mappings:
                    raise _PortableBackupError(f"Duplicate photo-reference mapping: {key!r}")
                media = members.get(row["archive_member"])
                if media is None or media["member_type"] != "managed_photo" or media["ownership"] != row["ownership"]:
                    raise _PortableBackupError(f"Photo reference does not map to verified managed media: {key!r}")
                mappings[key] = row

            expected_mapping_keys: set[tuple[str, int]] = set()
            used_capture_media: Dict[str, set[str]] = {value: set() for value in roots}
            used_ordinary_media: set[str] = set()
            for item in items:
                for photo_index, photo in enumerate(item.normalized_photos()):
                    if not photo.path.strip():
                        continue
                    key = (item.id, photo_index)
                    expected_mapping_keys.add(key)
                    row = mappings.get(key)
                    if row is None or row["stored_reference"] != photo.path:
                        raise _PortableBackupError(f"Managed photo reference mapping is missing or changed: {key!r}")
                    parts = _portable_reference_parts(photo.path)
                    if row["ownership"] == "ordinary_entry":
                        if photo.capture_import_media is not None or row["capture_import_id"] != "" or row["owner_archive_member"] != "":
                            raise _PortableBackupError(f"Ordinary media ownership conflicts with provenance: {key!r}")
                        anchors = [
                            index for index in range(len(parts) - 2)
                            if parts[index:index + 2] == ("managed_media", "ordinary")
                        ]
                        if not anchors or anchors[-1] + 3 >= len(parts) or parts[anchors[-1] + 2] != item.id or anchors[-1] + 4 != len(parts):
                            raise _PortableBackupError(f"External/unmanaged photo is not portable: item {item.id}, reference {photo.path!r}")
                        used_ordinary_media.add(row["archive_member"])
                    elif row["ownership"] == "capture_import":
                        provenance_id = photo.capture_import_media.import_id if photo.capture_import_media else ""
                        import_id = _portable_capture_import_id(photo.path, provenance_id)
                        if photo.capture_import_media is None:
                            raise _PortableBackupError(
                                f"Capture-import provenance is absent: {key!r}"
                            )
                        _require_portable_capture_item_reference(
                            photo.path, import_id, item.id
                        )
                        root = roots.get(import_id)
                        if root is None or row["capture_import_id"] != import_id or row["owner_archive_member"] != root["owner_archive_member"] or row["archive_member"] not in root["media_archive_members"]:
                            raise _PortableBackupError(f"Capture-import ownership mapping is incomplete: {key!r}")
                        if photo.capture_import_media is not None and photo.capture_import_media.artifact_sha256 != members[row["archive_member"]]["sha256"]:
                            raise _PortableBackupError(f"Capture-import provenance hash mismatch: {key!r}")
                        used_capture_media[import_id].add(row["archive_member"])
                    else:
                        raise _PortableBackupError(f"External/unmanaged photo classification is not portable: {key!r}")
            if set(mappings) != expected_mapping_keys:
                raise _PortableBackupError("Photo-reference manifest does not exactly match the collection")
            for import_id, root in roots.items():
                if used_capture_media[import_id] != set(root["media_archive_members"]):
                    raise _PortableBackupError(f"Capture-import media roster has unreferenced or missing members for {import_id}")
            declared_ordinary = {
                name for name, row in members.items()
                if row["member_type"] == "managed_photo" and row["ownership"] == "ordinary_entry"
            }
            declared_capture = {
                name for name, row in members.items()
                if row["member_type"] == "managed_photo" and row["ownership"] == "capture_import"
            }
            expected_capture = (
                set().union(*used_capture_media.values())
                if used_capture_media else set()
            )
            if (
                declared_ordinary != used_ordinary_media
                or declared_capture != expected_capture
            ):
                raise _PortableBackupError("Managed media inventory is not exactly referenced by the collection")
            owner_members = {
                name for name, row in members.items()
                if row["member_type"] == "capture_import_owner"
            }
            if owner_members != {row["owner_archive_member"] for row in roots.values()}:
                raise _PortableBackupError("Capture-import owner inventory is not exact")

            manifest = PortableBackupManifest(
                authoritative_collection=dict(collection_record),
                members=tuple(dict(row) for row in member_rows),
                photo_references=tuple(dict(row) for row in photo_rows),
                capture_import_roots=tuple(dict(row) for row in root_rows),
            )
            return BackupResult(
                True, "Complete portable collection backup verified",
                package_path=package_path, manifest=manifest,
            )
        except Exception as error:
            return BackupResult(
                False, "Portable backup verification failed",
                package_path=package_path,
                errors=[str(error) or type(error).__name__],
            )

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
        if isinstance(verified.manifest, PortableBackupManifest):
            return CollectionRecoveryReport(
                status="FAIL",
                package_path=target,
                collection_json_backed_up="YES",
                recoverable=["complete portable collection backup verified"],
                warnings=["Portable backup restore/publication is reserved for Product Unit 5C."],
                recommendations=["Retain the verified package and use the Unit 5C restore boundary when available."],
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

        verified = self.verify_backup_package(package_path)
        if not verified.success:
            return verified
        if isinstance(verified.manifest, PortableBackupManifest):
            return BackupResult(
                False,
                "Portable backup restore is not implemented",
                package_path=package_path,
                manifest=verified.manifest,
                errors=["Portable backup restore/publication is reserved for Product Unit 5C."],
            )
        manifest = verified.manifest or BackupManifest(_now_iso())
        allowed_prefixes = ("collection_data/app_state/", "data/collection.json")
        restore_records = [
            record for record in manifest.included_files
            if record.archive_path.startswith(allowed_prefixes)
        ]
        skipped = [
            record.archive_path for record in manifest.included_files
            if record.archive_path not in {row.archive_path for row in restore_records}
        ]
        pre_restore = self.create_backup_package()
        restored = []
        try:
            with zipfile.ZipFile(package_path, "r") as archive:
                for record in restore_records:
                    target = os.path.abspath(os.path.join(restore_root, record.archive_path))
                    root = os.path.abspath(restore_root)
                    if os.path.commonpath([root, target]) != root:
                        skipped.append(record.archive_path)
                        continue
                    if os.path.exists(target) and not overwrite:
                        skipped.append(record.archive_path)
                        continue
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with archive.open(record.archive_path) as source, open(target, "wb") as destination:
                        shutil.copyfileobj(source, destination)
                    restored.append(target)
            return BackupResult(
                True,
                "Restore completed",
                package_path=package_path,
                manifest=manifest,
                restored_files=restored,
                skipped_files=skipped,
                pre_restore_backup_path=pre_restore.package_path,
                warnings=list(manifest.warnings) + list(pre_restore.warnings),
            )
        except Exception as exc:
            return BackupResult(False, "Restore failed", package_path=package_path, manifest=manifest, restored_files=restored, skipped_files=skipped, pre_restore_backup_path=pre_restore.package_path, errors=[str(exc)])

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
