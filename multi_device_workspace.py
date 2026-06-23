"""Offline multi-device workspace models for Collector Companion.

This module models how a collector may use desktop, laptop, phone, and tablet
workflows around the same collection. It creates local planning reports only:
no accounts, authentication, network services, background sync, automatic
restore, automatic conflict resolution, or collection mutation.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from collector_cloud import CloudCollectionSnapshot, CollectorCloud
from sync_backup_engine import BackupArchive, SyncBackupEngine


DEVICE_DESKTOP = "Desktop"
DEVICE_LAPTOP = "Laptop"
DEVICE_PHONE = "Phone"
DEVICE_TABLET = "Tablet"
DEVICE_TYPES = [DEVICE_DESKTOP, DEVICE_LAPTOP, DEVICE_PHONE, DEVICE_TABLET]

CAPABILITY_PHOTO_CAPTURE = "Photo Capture"
CAPABILITY_OCR_IDENTIFICATION = "OCR Identification"
CAPABILITY_COLLECTION_ENTRY = "Collection Entry"
CAPABILITY_WORKFLOW_INTEGRATION = "Workflow Integration"
CAPABILITY_DEAL_HUNTER = "Deal Hunter"
CAPABILITY_PORTFOLIO_ANALYSIS = "Portfolio Analysis"
CAPABILITY_BACKUP_OPERATIONS = "Backup Operations"

CAPABILITIES = [
    CAPABILITY_PHOTO_CAPTURE,
    CAPABILITY_OCR_IDENTIFICATION,
    CAPABILITY_COLLECTION_ENTRY,
    CAPABILITY_WORKFLOW_INTEGRATION,
    CAPABILITY_DEAL_HUNTER,
    CAPABILITY_PORTFOLIO_ANALYSIS,
    CAPABILITY_BACKUP_OPERATIONS,
]

DEFAULT_DEVICE_CAPABILITIES = {
    DEVICE_DESKTOP: [
        CAPABILITY_COLLECTION_ENTRY,
        CAPABILITY_WORKFLOW_INTEGRATION,
        CAPABILITY_DEAL_HUNTER,
        CAPABILITY_PORTFOLIO_ANALYSIS,
        CAPABILITY_BACKUP_OPERATIONS,
    ],
    DEVICE_LAPTOP: [
        CAPABILITY_COLLECTION_ENTRY,
        CAPABILITY_WORKFLOW_INTEGRATION,
        CAPABILITY_DEAL_HUNTER,
        CAPABILITY_PORTFOLIO_ANALYSIS,
        CAPABILITY_BACKUP_OPERATIONS,
    ],
    DEVICE_PHONE: [
        CAPABILITY_PHOTO_CAPTURE,
        CAPABILITY_OCR_IDENTIFICATION,
        CAPABILITY_COLLECTION_ENTRY,
        CAPABILITY_WORKFLOW_INTEGRATION,
    ],
    DEVICE_TABLET: [
        CAPABILITY_PHOTO_CAPTURE,
        CAPABILITY_OCR_IDENTIFICATION,
        CAPABILITY_COLLECTION_ENTRY,
        CAPABILITY_WORKFLOW_INTEGRATION,
        CAPABILITY_PORTFOLIO_ANALYSIS,
    ],
}

DEFAULT_DEVICE_MODULES = {
    DEVICE_DESKTOP: ["Collection Manager", "Collector Cloud Foundation", "Sync & Backup", "Portfolio Performance", "Deal Hunter"],
    DEVICE_LAPTOP: ["Collection Manager", "Collector Cloud Foundation", "Sync & Backup", "Portfolio Performance", "Deal Hunter"],
    DEVICE_PHONE: ["Phone Photo Capture", "OCR-Assisted Identification", "Mobile Collection Entry", "Mobile Collector Companion"],
    DEVICE_TABLET: ["Phone Photo Capture", "OCR-Assisted Identification", "Collector Workflow Integration", "Portfolio Performance"],
}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        text = _text(value)
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _id(prefix: str, value: str = "") -> str:
    clean = _text(value).lower().replace(" ", "-")
    suffix = clean or datetime.now().strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}-{suffix}"


def _write_rows(output_path: str, rows: Sequence[Sequence[Any]]) -> bool:
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)
    return True


@dataclass
class DeviceProfile:
    """Collector device profile for offline workspace planning."""

    device_id: str
    device_name: str
    device_type: str
    capabilities: List[str] = field(default_factory=list)
    supported_modules: List[str] = field(default_factory=list)
    last_activity: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.device_type = _text(self.device_type).title()
        if self.device_type not in DEVICE_TYPES:
            self.device_type = DEVICE_DESKTOP
        self.device_id = _text(self.device_id) or _id("device", self.device_name or self.device_type)
        self.device_name = _text(self.device_name) or self.device_type
        self.capabilities = _dedupe(self.capabilities or DEFAULT_DEVICE_CAPABILITIES[self.device_type])
        self.supported_modules = _dedupe(self.supported_modules or DEFAULT_DEVICE_MODULES[self.device_type])
        self.last_activity = _text(self.last_activity) or _now_iso()
        self.metadata = dict(self.metadata or {})

    @classmethod
    def default_for_type(cls, device_type: str, device_name: str = "") -> "DeviceProfile":
        normalized = _text(device_type).title()
        if normalized not in DEVICE_TYPES:
            normalized = DEVICE_DESKTOP
        name = _text(device_name) or f"Collector {normalized}"
        return cls(
            device_id=_id("device", name),
            device_name=name,
            device_type=normalized,
            capabilities=DEFAULT_DEVICE_CAPABILITIES[normalized],
            supported_modules=DEFAULT_DEVICE_MODULES[normalized],
        )

    def supports(self, capability: str) -> bool:
        return _text(capability).lower() in {item.lower() for item in self.capabilities}

    def capability_summary(self) -> Dict[str, Any]:
        missing = [capability for capability in CAPABILITIES if not self.supports(capability)]
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "supported_capabilities": list(self.capabilities),
            "missing_capabilities": missing,
            "capability_count": len(self.capabilities),
            "supported_modules": list(self.supported_modules),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "capabilities": list(self.capabilities),
            "supported_modules": list(self.supported_modules),
            "last_activity": self.last_activity,
            "metadata": dict(self.metadata),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Device Profile",
            "",
            f"- Device: {self.device_name}",
            f"- ID: {self.device_id}",
            f"- Type: {self.device_type}",
            f"- Last activity: {self.last_activity}",
            "",
            "## Capabilities",
            "",
        ]
        lines.extend(f"- {capability}" for capability in self.capabilities)
        lines.extend(["", "## Supported Modules", ""])
        lines.extend(f"- {module}" for module in self.supported_modules)
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        return _write_rows(output_path, [
            ["section", "value"],
            ["device_id", self.device_id],
            ["device_name", self.device_name],
            ["device_type", self.device_type],
            *[["capability", capability] for capability in self.capabilities],
            *[["module", module] for module in self.supported_modules],
        ])


@dataclass
class WorkspaceActivity:
    """Activity event for a workspace/device workflow."""

    activity_id: str
    device_id: str
    activity_type: str
    summary: str
    timestamp: str = ""
    module: str = ""
    related_record_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.activity_id = _text(self.activity_id) or _id("activity", self.device_id)
        self.device_id = _text(self.device_id)
        self.activity_type = _text(self.activity_type) or "workspace"
        self.summary = _text(self.summary) or self.activity_type
        self.timestamp = _text(self.timestamp) or _now_iso()
        self.module = _text(self.module) or "Multi-Device Workspace"
        self.related_record_id = _text(self.related_record_id)
        self.metadata = dict(self.metadata or {})

    @staticmethod
    def summarize(activities: Iterable["WorkspaceActivity"]) -> Dict[str, Any]:
        rows = [activity if isinstance(activity, WorkspaceActivity) else WorkspaceActivity(**activity) for activity in activities]
        by_device: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        for activity in rows:
            by_device[activity.device_id] = by_device.get(activity.device_id, 0) + 1
            by_type[activity.activity_type] = by_type.get(activity.activity_type, 0) + 1
        return {
            "activity_count": len(rows),
            "devices_active": len(by_device),
            "activity_by_device": by_device,
            "activity_by_type": by_type,
            "latest_activity": max((activity.timestamp for activity in rows), default=""),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "device_id": self.device_id,
            "activity_type": self.activity_type,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "module": self.module,
            "related_record_id": self.related_record_id,
            "metadata": dict(self.metadata),
        }

    def format_markdown(self) -> str:
        return "\n".join([
            "# Workspace Activity",
            "",
            f"- Activity: {self.activity_id}",
            f"- Device: {self.device_id}",
            f"- Type: {self.activity_type}",
            f"- Module: {self.module}",
            f"- Timestamp: {self.timestamp}",
            f"- Summary: {self.summary}",
        ]).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        return _write_rows(output_path, [["field", "value"], *[[key, value] for key, value in self.to_dict().items() if key != "metadata"]])


@dataclass
class WorkspaceSnapshot:
    """Point-in-time multi-device workspace snapshot."""

    snapshot_id: str
    workspace_id: str
    created_at: str = ""
    devices: List[DeviceProfile] = field(default_factory=list)
    collection_state: Dict[str, Any] = field(default_factory=dict)
    portfolio_state: Dict[str, Any] = field(default_factory=dict)
    workflow_state: Dict[str, Any] = field(default_factory=dict)
    watchlist_state: Dict[str, Any] = field(default_factory=dict)
    cloud_snapshot_id: str = ""
    backup_archive_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.snapshot_id = _text(self.snapshot_id) or _id("workspace-snapshot")
        self.workspace_id = _text(self.workspace_id)
        self.created_at = _text(self.created_at) or _now_iso()
        self.devices = [device if isinstance(device, DeviceProfile) else DeviceProfile(**device) for device in self.devices]
        self.collection_state = dict(self.collection_state or {})
        self.portfolio_state = dict(self.portfolio_state or {})
        self.workflow_state = dict(self.workflow_state or {})
        self.watchlist_state = dict(self.watchlist_state or {})
        self.cloud_snapshot_id = _text(self.cloud_snapshot_id)
        self.backup_archive_id = _text(self.backup_archive_id)
        self.metadata = dict(self.metadata or {})
        self.warnings = _dedupe([*self.warnings, "Workspace snapshot only; synchronization not executed"])

    @property
    def state_hash(self) -> str:
        return _hash({
            "devices": [device.to_dict() for device in self.devices],
            "collection_state": self.collection_state,
            "portfolio_state": self.portfolio_state,
            "workflow_state": self.workflow_state,
            "watchlist_state": self.watchlist_state,
            "cloud_snapshot_id": self.cloud_snapshot_id,
            "backup_archive_id": self.backup_archive_id,
        })

    def compare_to(self, other: "WorkspaceSnapshot") -> Dict[str, Any]:
        other = other if isinstance(other, WorkspaceSnapshot) else WorkspaceSnapshot(**other)
        source_devices = {device.device_id for device in self.devices}
        other_devices = {device.device_id for device in other.devices}
        changed_sections = []
        for name in ["collection_state", "portfolio_state", "workflow_state", "watchlist_state"]:
            if getattr(self, name) != getattr(other, name):
                changed_sections.append(name)
        return {
            "source_snapshot_id": self.snapshot_id,
            "destination_snapshot_id": other.snapshot_id,
            "added_devices": sorted(source_devices - other_devices),
            "removed_devices": sorted(other_devices - source_devices),
            "changed_sections": changed_sections,
            "source_hash": self.state_hash,
            "destination_hash": other.state_hash,
            "drift_detected": self.state_hash != other.state_hash,
        }

    def drift_analysis(self, other: "WorkspaceSnapshot") -> Dict[str, Any]:
        diff = self.compare_to(other)
        risk = 0
        risk += len(diff["added_devices"]) + len(diff["removed_devices"])
        risk += len(diff["changed_sections"]) * 2
        if self.cloud_snapshot_id != other.cloud_snapshot_id:
            risk += 1
        if self.backup_archive_id != other.backup_archive_id:
            risk += 1
        return {
            "drift_detected": diff["drift_detected"],
            "drift_score": min(100, risk * 10),
            "changed_sections": diff["changed_sections"],
            "recommendations": ["Review changed workspace sections before future sync"] if diff["drift_detected"] else ["No drift detected"],
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "workspace_id": self.workspace_id,
            "created_at": self.created_at,
            "device_count": len(self.devices),
            "devices": [device.to_dict() for device in self.devices],
            "collection_state": dict(self.collection_state),
            "portfolio_state": dict(self.portfolio_state),
            "workflow_state": dict(self.workflow_state),
            "watchlist_state": dict(self.watchlist_state),
            "cloud_snapshot_id": self.cloud_snapshot_id,
            "backup_archive_id": self.backup_archive_id,
            "state_hash": self.state_hash,
            "metadata": dict(self.metadata),
            "warnings": "; ".join(self.warnings),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Workspace Snapshot",
            "",
            f"- Snapshot: {self.snapshot_id}",
            f"- Workspace: {self.workspace_id}",
            f"- Created: {self.created_at}",
            f"- Devices: {len(self.devices)}",
            f"- Cloud snapshot: {self.cloud_snapshot_id or 'None'}",
            f"- Backup archive: {self.backup_archive_id or 'None'}",
            "- Synchronization executed: NO",
            "",
            "## Devices",
            "",
        ]
        lines.extend(f"- {device.device_name} ({device.device_type})" for device in self.devices)
        for title, state in [
            ("Collection State", self.collection_state),
            ("Portfolio State", self.portfolio_state),
            ("Workflow State", self.workflow_state),
            ("Watchlist State", self.watchlist_state),
        ]:
            lines.extend(["", f"## {title}", ""])
            lines.extend(f"- {key}: {value}" for key, value in sorted(state.items())) if state else lines.append("- None")
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        rows = [["section", "key", "value"]]
        rows.extend([["summary", "snapshot_id", self.snapshot_id], ["summary", "workspace_id", self.workspace_id], ["summary", "device_count", len(self.devices)]])
        for device in self.devices:
            rows.append(["device", device.device_id, f"{device.device_name} ({device.device_type})"])
        for section, state in [
            ("collection", self.collection_state),
            ("portfolio", self.portfolio_state),
            ("workflow", self.workflow_state),
            ("watchlist", self.watchlist_state),
        ]:
            for key, value in sorted(state.items()):
                rows.append([section, key, value])
        return _write_rows(output_path, rows)


@dataclass
class CollectorWorkspace:
    """Collector ecosystem containing registered devices and snapshots."""

    workspace_id: str
    workspace_name: str
    registered_devices: List[DeviceProfile] = field(default_factory=list)
    workspace_snapshots: List[WorkspaceSnapshot] = field(default_factory=list)
    sync_readiness: str = "NOT_READY"
    backup_readiness: str = "NOT_READY"
    activities: List[WorkspaceActivity] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.workspace_id = _text(self.workspace_id) or _id("workspace", self.workspace_name)
        self.workspace_name = _text(self.workspace_name) or "Collector Workspace"
        self.registered_devices = [device if isinstance(device, DeviceProfile) else DeviceProfile(**device) for device in self.registered_devices]
        self.workspace_snapshots = [snapshot if isinstance(snapshot, WorkspaceSnapshot) else WorkspaceSnapshot(**snapshot) for snapshot in self.workspace_snapshots]
        self.activities = [activity if isinstance(activity, WorkspaceActivity) else WorkspaceActivity(**activity) for activity in self.activities]
        self.metadata = dict(self.metadata or {})
        self.refresh_readiness()

    def register_device(self, device: DeviceProfile) -> DeviceProfile:
        existing = {item.device_id for item in self.registered_devices}
        if device.device_id not in existing:
            self.registered_devices.append(device)
        self.refresh_readiness()
        return device

    def add_snapshot(self, snapshot: WorkspaceSnapshot) -> WorkspaceSnapshot:
        self.workspace_snapshots.append(snapshot)
        self.refresh_readiness()
        return snapshot

    def add_activity(self, activity: WorkspaceActivity) -> WorkspaceActivity:
        self.activities.append(activity)
        for device in self.registered_devices:
            if device.device_id == activity.device_id:
                device.last_activity = activity.timestamp
        self.refresh_readiness()
        return activity

    def refresh_readiness(self) -> None:
        has_backup_device = any(device.supports(CAPABILITY_BACKUP_OPERATIONS) for device in self.registered_devices)
        has_mobile_device = any(device.device_type in {DEVICE_PHONE, DEVICE_TABLET} for device in self.registered_devices)
        has_desktop_device = any(device.device_type in {DEVICE_DESKTOP, DEVICE_LAPTOP} for device in self.registered_devices)
        self.sync_readiness = "READY_FOR_SIMULATION" if has_mobile_device and has_desktop_device and len(self.registered_devices) >= 2 else "NEEDS_DEVICE_COVERAGE"
        self.backup_readiness = "READY" if has_backup_device else "NEEDS_BACKUP_DEVICE"

    def to_dict(self) -> Dict[str, Any]:
        self.refresh_readiness()
        return {
            "workspace_id": self.workspace_id,
            "workspace_name": self.workspace_name,
            "device_count": len(self.registered_devices),
            "snapshot_count": len(self.workspace_snapshots),
            "activity_count": len(self.activities),
            "sync_readiness": self.sync_readiness,
            "backup_readiness": self.backup_readiness,
            "registered_devices": [device.to_dict() for device in self.registered_devices],
            "workspace_snapshots": [snapshot.to_dict() for snapshot in self.workspace_snapshots],
            "activities": [activity.to_dict() for activity in self.activities],
            "metadata": dict(self.metadata),
        }

    def format_markdown(self) -> str:
        self.refresh_readiness()
        lines = [
            "# Collector Workspace",
            "",
            f"- Workspace: {self.workspace_name}",
            f"- ID: {self.workspace_id}",
            f"- Devices: {len(self.registered_devices)}",
            f"- Snapshots: {len(self.workspace_snapshots)}",
            f"- Activities: {len(self.activities)}",
            f"- Sync readiness: {self.sync_readiness}",
            f"- Backup readiness: {self.backup_readiness}",
            "- Synchronization executed: NO",
            "",
            "## Devices",
            "",
        ]
        lines.extend(f"- {device.device_name} ({device.device_type})" for device in self.registered_devices)
        lines.extend(["", "## Recent Activities", ""])
        lines.extend(f"- {activity.timestamp}: {activity.summary}" for activity in self.activities[-10:]) if self.activities else lines.append("- None")
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        rows = [["section", "key", "value"]]
        for key, value in self.to_dict().items():
            if not isinstance(value, (list, dict)):
                rows.append(["workspace", key, value])
        for device in self.registered_devices:
            rows.append(["device", device.device_id, f"{device.device_name} ({device.device_type})"])
        for snapshot in self.workspace_snapshots:
            rows.append(["snapshot", snapshot.snapshot_id, snapshot.state_hash])
        for activity in self.activities:
            rows.append(["activity", activity.activity_id, activity.summary])
        return _write_rows(output_path, rows)


@dataclass
class WorkspaceHealthReport:
    """Health/readiness report for a multi-device workspace."""

    report_id: str
    workspace_id: str
    generated_at: str = ""
    device_coverage: Dict[str, Any] = field(default_factory=dict)
    backup_coverage: Dict[str, Any] = field(default_factory=dict)
    sync_readiness: Dict[str, Any] = field(default_factory=dict)
    snapshot_freshness: Dict[str, Any] = field(default_factory=dict)
    conflict_exposure: Dict[str, Any] = field(default_factory=dict)
    workflow_coverage: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.report_id = _text(self.report_id) or _id("workspace-health", self.workspace_id)
        self.workspace_id = _text(self.workspace_id)
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.device_coverage = dict(self.device_coverage or {})
        self.backup_coverage = dict(self.backup_coverage or {})
        self.sync_readiness = dict(self.sync_readiness or {})
        self.snapshot_freshness = dict(self.snapshot_freshness or {})
        self.conflict_exposure = dict(self.conflict_exposure or {})
        self.workflow_coverage = dict(self.workflow_coverage or {})
        self.recommendations = _dedupe(self.recommendations)
        self.warnings = _dedupe([*self.warnings, "Health report only; no synchronization executed"])

    @property
    def health_score(self) -> int:
        score = 0
        score += int(self.device_coverage.get("coverage_score", 0))
        score += int(self.backup_coverage.get("coverage_score", 0))
        score += int(self.sync_readiness.get("readiness_score", 0))
        score += int(self.snapshot_freshness.get("freshness_score", 0))
        score += int(self.workflow_coverage.get("coverage_score", 0))
        score -= int(self.conflict_exposure.get("exposure_score", 0))
        return max(0, min(100, round(score / 5)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "workspace_id": self.workspace_id,
            "generated_at": self.generated_at,
            "health_score": self.health_score,
            "device_coverage": dict(self.device_coverage),
            "backup_coverage": dict(self.backup_coverage),
            "sync_readiness": dict(self.sync_readiness),
            "snapshot_freshness": dict(self.snapshot_freshness),
            "conflict_exposure": dict(self.conflict_exposure),
            "workflow_coverage": dict(self.workflow_coverage),
            "recommendations": list(self.recommendations),
            "warnings": list(self.warnings),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Workspace Health Report",
            "",
            f"- Report: {self.report_id}",
            f"- Workspace: {self.workspace_id}",
            f"- Generated: {self.generated_at}",
            f"- Health score: {self.health_score}/100",
            "- Real synchronization configured: NO",
            "",
        ]
        for title, values in [
            ("Device Coverage", self.device_coverage),
            ("Backup Coverage", self.backup_coverage),
            ("Sync Readiness", self.sync_readiness),
            ("Snapshot Freshness", self.snapshot_freshness),
            ("Conflict Exposure", self.conflict_exposure),
            ("Workflow Coverage", self.workflow_coverage),
        ]:
            lines.extend([f"## {title}", ""])
            lines.extend(f"- {key}: {value}" for key, value in sorted(values.items())) if values else lines.append("- None")
            lines.append("")
        lines.extend(["## Recommendations", ""])
        lines.extend(f"- {item}" for item in self.recommendations) if self.recommendations else lines.append("- None")
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        rows = [["section", "key", "value"]]
        rows.extend([["summary", "report_id", self.report_id], ["summary", "workspace_id", self.workspace_id], ["summary", "health_score", self.health_score]])
        for section, values in [
            ("device_coverage", self.device_coverage),
            ("backup_coverage", self.backup_coverage),
            ("sync_readiness", self.sync_readiness),
            ("snapshot_freshness", self.snapshot_freshness),
            ("conflict_exposure", self.conflict_exposure),
            ("workflow_coverage", self.workflow_coverage),
        ]:
            for key, value in sorted(values.items()):
                rows.append([section, key, value])
        for recommendation in self.recommendations:
            rows.append(["recommendation", "", recommendation])
        for warning in self.warnings:
            rows.append(["warning", "", warning])
        return _write_rows(output_path, rows)


class MultiDeviceWorkspaceEngine:
    """Create offline multi-device workspace planning artifacts."""

    def __init__(
        self,
        collection_items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        workflow_completion_reports: Optional[Iterable[Any]] = None,
        mobile_entry_reports: Optional[Iterable[Any]] = None,
        mobile_companion_reports: Optional[Iterable[Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        collector_cloud: Optional[CollectorCloud] = None,
        sync_backup_engine: Optional[SyncBackupEngine] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.workflow_completion_reports = list(workflow_completion_reports or [])
        self.mobile_entry_reports = list(mobile_entry_reports or [])
        self.mobile_companion_reports = list(mobile_companion_reports or [])
        self.settings = dict(settings or {})
        self.collector_cloud = collector_cloud or CollectorCloud(
            collection_items=self.collection_items,
            want_list_intents=self.want_list_intents,
            workflow_completion_reports=self.workflow_completion_reports,
            mobile_entry_reports=self.mobile_entry_reports,
            mobile_companion_reports=self.mobile_companion_reports,
            settings=self.settings,
        )
        self.sync_backup_engine = sync_backup_engine or SyncBackupEngine(collector_cloud=self.collector_cloud)
        self.workspaces: List[CollectorWorkspace] = []

    def create_device_profile(self, device_type: str, device_name: str = "", capabilities: Optional[Iterable[str]] = None) -> DeviceProfile:
        device = DeviceProfile.default_for_type(device_type, device_name)
        if capabilities is not None:
            device.capabilities = _dedupe(capabilities)
        return device

    def create_workspace(self, workspace_name: str = "Collector Workspace", devices: Optional[Iterable[DeviceProfile]] = None) -> CollectorWorkspace:
        workspace = CollectorWorkspace(
            workspace_id=_id("workspace", workspace_name),
            workspace_name=workspace_name,
            registered_devices=list(devices or []),
            metadata={"network_required": "NO", "sync_execution": "NO"},
        )
        self.workspaces.append(workspace)
        return workspace

    def default_workspace(self, workspace_name: str = "Collector Workspace") -> CollectorWorkspace:
        devices = [
            self.create_device_profile(DEVICE_DESKTOP, "Collector Desktop"),
            self.create_device_profile(DEVICE_PHONE, "Collector Phone"),
            self.create_device_profile(DEVICE_LAPTOP, "Collector Laptop"),
        ]
        return self.create_workspace(workspace_name, devices)

    def create_snapshot(self, workspace: CollectorWorkspace, source_label: str = "multi-device-workspace") -> WorkspaceSnapshot:
        cloud_snapshot = self.collector_cloud.create_snapshot(source_label)
        archive = self.sync_backup_engine.create_backup_archive(source_snapshot=cloud_snapshot, version="v6.2")
        snapshot = WorkspaceSnapshot(
            snapshot_id=_id("workspace-snapshot", workspace.workspace_name),
            workspace_id=workspace.workspace_id,
            devices=list(workspace.registered_devices),
            collection_state={
                **cloud_snapshot.collection_metrics,
                "record_count": cloud_snapshot.record_count,
                "content_hash": cloud_snapshot.content_hash,
            },
            portfolio_state=dict(cloud_snapshot.portfolio_metrics),
            workflow_state=dict(cloud_snapshot.workflow_metrics),
            watchlist_state={
                "want_list_intents": len(self.want_list_intents),
                "watchlist_count": len(self.settings.get("watchlists", [])) if isinstance(self.settings.get("watchlists", []), list) else 0,
            },
            cloud_snapshot_id=cloud_snapshot.snapshot_id,
            backup_archive_id=archive.archive_id,
            metadata={
                "source_label": source_label,
                "backup_checksum": archive.checksum,
                "sync_execution": "NO",
                "cloud_provider": "NONE",
            },
        )
        workspace.add_snapshot(snapshot)
        workspace.refresh_readiness()
        return snapshot

    def compare_snapshots(self, source: WorkspaceSnapshot, destination: WorkspaceSnapshot) -> Dict[str, Any]:
        return source.compare_to(destination)

    def drift_analysis(self, source: WorkspaceSnapshot, destination: WorkspaceSnapshot) -> Dict[str, Any]:
        return source.drift_analysis(destination)

    def capability_report(self, devices: Iterable[DeviceProfile]) -> Dict[str, Any]:
        device_list = list(devices)
        coverage = {
            capability: sum(1 for device in device_list if device.supports(capability))
            for capability in CAPABILITIES
        }
        missing = [capability for capability, count in coverage.items() if count == 0]
        return {
            "device_count": len(device_list),
            "capability_coverage": coverage,
            "missing_capabilities": missing,
            "device_summaries": [device.capability_summary() for device in device_list],
            "readiness": "READY" if not missing else "NEEDS_CAPABILITY_COVERAGE",
        }

    def record_activity(
        self,
        workspace: CollectorWorkspace,
        device: DeviceProfile,
        activity_type: str,
        summary: str,
        module: str = "Multi-Device Workspace",
        related_record_id: str = "",
    ) -> WorkspaceActivity:
        if device.device_id not in {item.device_id for item in workspace.registered_devices}:
            workspace.register_device(device)
        activity = WorkspaceActivity(
            activity_id=_id("activity", f"{device.device_id}-{activity_type}"),
            device_id=device.device_id,
            activity_type=activity_type,
            summary=summary,
            module=module,
            related_record_id=related_record_id,
        )
        workspace.add_activity(activity)
        return activity

    def activity_summary(self, workspace: CollectorWorkspace) -> Dict[str, Any]:
        return WorkspaceActivity.summarize(workspace.activities)

    def health_report(self, workspace: CollectorWorkspace) -> WorkspaceHealthReport:
        workspace.refresh_readiness()
        device_types = {device.device_type for device in workspace.registered_devices}
        capability_report = self.capability_report(workspace.registered_devices)
        backup_devices = [device.device_name for device in workspace.registered_devices if device.supports(CAPABILITY_BACKUP_OPERATIONS)]
        workflow_devices = [device.device_name for device in workspace.registered_devices if device.supports(CAPABILITY_WORKFLOW_INTEGRATION)]
        latest_snapshot = workspace.workspace_snapshots[-1] if workspace.workspace_snapshots else None
        conflict_exposure_score = 0
        if latest_snapshot:
            conflict_exposure_score += int(latest_snapshot.collection_state.get("duplicate_groups", 0) or 0) * 5
            conflict_exposure_score += int(latest_snapshot.workflow_state.get("review_escalations", 0) or 0) * 5
            conflict_exposure_score += max(0, len(workspace.registered_devices) - 2) * 3
        recommendations = []
        if len(device_types) < len(DEVICE_TYPES):
            recommendations.append("Register all desktop, laptop, phone, and tablet roles for full workspace coverage")
        if not backup_devices:
            recommendations.append("Add at least one desktop or laptop device with Backup Operations")
        if not workspace.workspace_snapshots:
            recommendations.append("Create a workspace snapshot before future sync planning")
        if capability_report["missing_capabilities"]:
            recommendations.append("Review missing capability coverage before device linking")
        if not recommendations:
            recommendations.append("Workspace is ready for offline device-linking planning")
        return WorkspaceHealthReport(
            report_id=_id("workspace-health", workspace.workspace_id),
            workspace_id=workspace.workspace_id,
            device_coverage={
                "device_count": len(workspace.registered_devices),
                "device_types": ", ".join(sorted(device_types)),
                "coverage_score": round((len(device_types) / len(DEVICE_TYPES)) * 100),
                "missing_device_types": ", ".join(device for device in DEVICE_TYPES if device not in device_types),
            },
            backup_coverage={
                "backup_device_count": len(backup_devices),
                "backup_devices": ", ".join(backup_devices),
                "coverage_score": 100 if backup_devices else 0,
                "backup_readiness": workspace.backup_readiness,
            },
            sync_readiness={
                "status": workspace.sync_readiness,
                "readiness_score": 90 if workspace.sync_readiness == "READY_FOR_SIMULATION" else 35,
                "real_sync_enabled": "NO",
            },
            snapshot_freshness={
                "snapshot_count": len(workspace.workspace_snapshots),
                "latest_snapshot": latest_snapshot.snapshot_id if latest_snapshot else "",
                "freshness_score": 100 if latest_snapshot else 0,
            },
            conflict_exposure={
                "exposure_score": min(100, conflict_exposure_score),
                "registered_devices": len(workspace.registered_devices),
                "duplicate_groups": latest_snapshot.collection_state.get("duplicate_groups", 0) if latest_snapshot else 0,
                "workflow_review_escalations": latest_snapshot.workflow_state.get("review_escalations", 0) if latest_snapshot else 0,
            },
            workflow_coverage={
                "workflow_device_count": len(workflow_devices),
                "workflow_devices": ", ".join(workflow_devices),
                "coverage_score": min(100, len(workflow_devices) * 30),
            },
            recommendations=recommendations,
        )

    def simulate_desktop_phone_laptop(self, workspace: Optional[CollectorWorkspace] = None) -> Dict[str, Any]:
        workspace = workspace or self.default_workspace("Desktop Phone Laptop Workspace")
        path = [
            self._ensure_device(workspace, DEVICE_DESKTOP, "Collector Desktop"),
            self._ensure_device(workspace, DEVICE_PHONE, "Collector Phone"),
            self._ensure_device(workspace, DEVICE_LAPTOP, "Collector Laptop"),
        ]
        return self._simulate_path(workspace, path, "desktop-phone-laptop")

    def simulate_phone_tablet_desktop(self, workspace: Optional[CollectorWorkspace] = None) -> Dict[str, Any]:
        workspace = workspace or self.create_workspace("Phone Tablet Desktop Workspace")
        path = [
            self._ensure_device(workspace, DEVICE_PHONE, "Collector Phone"),
            self._ensure_device(workspace, DEVICE_TABLET, "Collector Tablet"),
            self._ensure_device(workspace, DEVICE_DESKTOP, "Collector Desktop"),
        ]
        return self._simulate_path(workspace, path, "phone-tablet-desktop")

    def _ensure_device(self, workspace: CollectorWorkspace, device_type: str, device_name: str) -> DeviceProfile:
        for device in workspace.registered_devices:
            if device.device_type == device_type:
                return device
        return workspace.register_device(self.create_device_profile(device_type, device_name))

    def _simulate_path(self, workspace: CollectorWorkspace, path: Sequence[DeviceProfile], scenario_id: str) -> Dict[str, Any]:
        for order, device in enumerate(path, 1):
            self.record_activity(
                workspace,
                device,
                "scenario_step",
                f"{scenario_id} step {order}: {device.device_type} review",
                module="Multi-Device Workspace",
            )
        snapshot = self.create_snapshot(workspace, scenario_id)
        health = self.health_report(workspace)
        conflict_exposure = {
            "scenario": scenario_id,
            "device_path": " -> ".join(device.device_type for device in path),
            "exposure_score": health.conflict_exposure.get("exposure_score", 0),
            "automatic_resolution": "NO",
            "recommendation": "Review workspace drift before any future device linking",
        }
        return {
            "scenario_id": scenario_id,
            "device_path": [device.device_type for device in path],
            "workspace": workspace,
            "workspace_report": workspace.format_markdown(),
            "snapshot": snapshot,
            "readiness_analysis": health.to_dict(),
            "conflict_exposure": conflict_exposure,
            "health_report": health,
        }
