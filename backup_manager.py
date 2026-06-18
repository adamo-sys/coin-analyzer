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
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from collection_dashboard import CollectionDashboard
from collector_operating_system import CollectionHealthReportEngine
from market_awareness import MarketAwarenessEngine
from persistence_manager import AppState, PersistenceManager
from photo_vault import PhotoRecord, PhotoVault
from series_tracker import SeriesTracker
from smart_shopping_assistant import ShoppingCandidate, SmartShoppingAssistant


APP_VERSION = "2.4.1"
MANIFEST_NAME = "backup_manifest.json"
MANIFEST_MARKDOWN_NAME = "backup_manifest.md"
DEFAULT_COLLECTION_JSON_PATH = os.path.join("data", "collection.json")
DEFAULT_SNAPSHOT_PATH = os.path.join("collection_data", "app_state", "collection_snapshots.json")


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
    ):
        self.backup_dir = backup_dir
        self.persistence_manager = persistence_manager or PersistenceManager()
        self.collection_json_path = collection_json_path

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
            return BackupResult(False, "Backup package missing", package_path=package_path, errors=[f"Backup not found: {package_path}"])
        try:
            with zipfile.ZipFile(package_path, "r") as archive:
                if archive.testzip():
                    return BackupResult(False, "Backup zip is corrupt", package_path=package_path, errors=["Zip integrity check failed"])
                if MANIFEST_NAME not in archive.namelist():
                    return BackupResult(False, "Backup manifest missing", package_path=package_path, errors=["backup_manifest.json not found"])
                manifest = BackupManifest.from_dict(json.loads(archive.read(MANIFEST_NAME).decode("utf-8")))
                errors = []
                for record in manifest.included_files:
                    if record.archive_path not in archive.namelist():
                        errors.append(f"Missing archived file: {record.archive_path}")
                        continue
                    digest = hashlib.sha256(archive.read(record.archive_path)).hexdigest()
                    if record.sha256 and digest != record.sha256:
                        errors.append(f"Checksum mismatch: {record.archive_path}")
                if errors:
                    return BackupResult(False, "Backup verification failed", package_path=package_path, manifest=manifest, errors=errors)
                return BackupResult(True, "Backup verified", package_path=package_path, manifest=manifest, warnings=list(manifest.warnings))
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
                "shopping candidates stored in app state",
            ])
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
            warnings=list(manifest.warnings),
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
