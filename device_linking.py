"""Offline device linking and conflict-resolution planning.

This module completes the v6 architecture arc by modeling linked collector
devices and cross-device conflicts. It never performs internet sync, account
auth, cloud-provider calls, automatic conflict resolution, background sync, or
collection mutation. All recommendations require collector review.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from collector_cloud import CollectorCloud
from multi_device_workspace import (
    CAPABILITY_BACKUP_OPERATIONS,
    CAPABILITY_COLLECTION_ENTRY,
    CAPABILITY_WORKFLOW_INTEGRATION,
    CollectorWorkspace,
    DeviceProfile,
    MultiDeviceWorkspaceEngine,
    WorkspaceHealthReport,
    WorkspaceSnapshot,
)
from sync_backup_engine import SyncBackupEngine


RELATIONSHIP_PRIMARY = "Primary Device"
RELATIONSHIP_SECONDARY = "Secondary Device"
RELATIONSHIP_MOBILE = "Mobile Device"
RELATIONSHIP_TABLET = "Tablet Device"
RELATIONSHIP_BACKUP = "Backup Device"
RELATIONSHIPS = [
    RELATIONSHIP_PRIMARY,
    RELATIONSHIP_SECONDARY,
    RELATIONSHIP_MOBILE,
    RELATIONSHIP_TABLET,
    RELATIONSHIP_BACKUP,
]

LINK_PENDING = "PENDING_REVIEW"
LINK_LINKED = "LINKED"
LINK_NEEDS_REVIEW = "NEEDS_REVIEW"

CONFLICT_COLLECTION = "collection"
CONFLICT_WORKFLOW = "workflow"
CONFLICT_PORTFOLIO = "portfolio"
CONFLICT_WATCHLIST = "watchlist"
CONFLICT_SETTINGS = "settings"
CONFLICT_SNAPSHOT = "snapshot"
CONFLICT_TYPES = [
    CONFLICT_COLLECTION,
    CONFLICT_WORKFLOW,
    CONFLICT_PORTFOLIO,
    CONFLICT_WATCHLIST,
    CONFLICT_SETTINGS,
    CONFLICT_SNAPSHOT,
]

SEVERITY_LOW = "LOW"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_HIGH = "HIGH"

ACTION_MERGE = "MERGE"
ACTION_KEEP_PRIMARY = "KEEP_PRIMARY"
ACTION_KEEP_SECONDARY = "KEEP_SECONDARY"
ACTION_REVIEW_REQUIRED = "REVIEW_REQUIRED"
ACTION_REJECT = "REJECT"


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


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _id(prefix: str, *parts: Any) -> str:
    clean_parts = [_text(part).lower().replace(" ", "-").replace(":", "-") for part in parts if _text(part)]
    suffix = "-".join(clean_parts) or datetime.now().strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}-{suffix}"


def _write_rows(output_path: str, rows: Sequence[Sequence[Any]]) -> bool:
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)
    return True


@dataclass
class LinkedDevice:
    """Linked workspace device record."""

    device_id: str
    device_name: str
    device_type: str
    relationship_role: str
    link_status: str = LINK_PENDING
    capabilities: List[str] = field(default_factory=list)
    supported_modules: List[str] = field(default_factory=list)
    last_activity: str = ""
    sync_readiness: str = "NOT_READY"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.device_id = _text(self.device_id)
        self.device_name = _text(self.device_name) or self.device_id
        self.device_type = _text(self.device_type) or "Device"
        self.relationship_role = _text(self.relationship_role) or RELATIONSHIP_SECONDARY
        if self.relationship_role not in RELATIONSHIPS:
            self.relationship_role = RELATIONSHIP_SECONDARY
        self.link_status = _text(self.link_status).upper() or LINK_PENDING
        self.capabilities = _dedupe(self.capabilities)
        self.supported_modules = _dedupe(self.supported_modules)
        self.last_activity = _text(self.last_activity) or _now_iso()
        self.metadata = dict(self.metadata or {})
        if self.sync_readiness == "NOT_READY":
            self.sync_readiness = self._default_sync_readiness()

    @classmethod
    def from_profile(cls, profile: DeviceProfile, relationship_role: str = RELATIONSHIP_SECONDARY) -> "LinkedDevice":
        return cls(
            device_id=profile.device_id,
            device_name=profile.device_name,
            device_type=profile.device_type,
            relationship_role=relationship_role,
            capabilities=list(profile.capabilities),
            supported_modules=list(profile.supported_modules),
            last_activity=profile.last_activity,
        )

    def _default_sync_readiness(self) -> str:
        required = {CAPABILITY_COLLECTION_ENTRY, CAPABILITY_WORKFLOW_INTEGRATION}
        if required.issubset({capability for capability in self.capabilities}):
            return "READY_FOR_REVIEW"
        return "NEEDS_CAPABILITY_REVIEW"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "relationship_role": self.relationship_role,
            "link_status": self.link_status,
            "capabilities": list(self.capabilities),
            "supported_modules": list(self.supported_modules),
            "last_activity": self.last_activity,
            "sync_readiness": self.sync_readiness,
            "metadata": dict(self.metadata),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Linked Device",
            "",
            f"- Device: {self.device_name}",
            f"- ID: {self.device_id}",
            f"- Type: {self.device_type}",
            f"- Role: {self.relationship_role}",
            f"- Link status: {self.link_status}",
            f"- Sync readiness: {self.sync_readiness}",
            "- Automatic sync enabled: NO",
            "",
            "## Capabilities",
            "",
        ]
        lines.extend(f"- {capability}" for capability in self.capabilities) if self.capabilities else lines.append("- None")
        return "\n".join(lines).rstrip() + "\n"


@dataclass
class DeviceRelationship:
    """Relationship between two linked devices."""

    relationship_id: str
    primary_device_id: str
    secondary_device_id: str
    relationship_type: str
    link_status: str = LINK_PENDING
    capability_overlap: List[str] = field(default_factory=list)
    sync_readiness: str = "NOT_READY"
    last_activity: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.relationship_id = _text(self.relationship_id) or _id("relationship", self.primary_device_id, self.secondary_device_id)
        self.primary_device_id = _text(self.primary_device_id)
        self.secondary_device_id = _text(self.secondary_device_id)
        self.relationship_type = _text(self.relationship_type) or RELATIONSHIP_SECONDARY
        if self.relationship_type not in RELATIONSHIPS:
            self.relationship_type = RELATIONSHIP_SECONDARY
        self.link_status = _text(self.link_status).upper() or LINK_PENDING
        self.capability_overlap = _dedupe(self.capability_overlap)
        self.last_activity = _text(self.last_activity) or _now_iso()
        self.metadata = dict(self.metadata or {})
        if self.sync_readiness == "NOT_READY":
            self.sync_readiness = "READY_FOR_REVIEW" if self.capability_overlap else "NEEDS_CAPABILITY_REVIEW"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relationship_id": self.relationship_id,
            "primary_device_id": self.primary_device_id,
            "secondary_device_id": self.secondary_device_id,
            "relationship_type": self.relationship_type,
            "link_status": self.link_status,
            "capability_overlap": list(self.capability_overlap),
            "sync_readiness": self.sync_readiness,
            "last_activity": self.last_activity,
            "metadata": dict(self.metadata),
        }


@dataclass
class ConflictCase:
    """One cross-device conflict requiring review."""

    conflict_id: str
    conflict_type: str
    severity: str
    primary_summary: str
    secondary_summary: str
    affected_section: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.conflict_type = _text(self.conflict_type).lower() or CONFLICT_SNAPSHOT
        if self.conflict_type not in CONFLICT_TYPES:
            self.conflict_type = CONFLICT_SNAPSHOT
        self.severity = _text(self.severity).upper() or SEVERITY_LOW
        if self.severity not in {SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH}:
            self.severity = SEVERITY_LOW
        self.conflict_id = _text(self.conflict_id) or _id("conflict", self.conflict_type, self.affected_section)
        self.primary_summary = _text(self.primary_summary)
        self.secondary_summary = _text(self.secondary_summary)
        self.affected_section = _text(self.affected_section) or self.conflict_type
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type,
            "severity": self.severity,
            "primary_summary": self.primary_summary,
            "secondary_summary": self.secondary_summary,
            "affected_section": self.affected_section,
            "metadata": dict(self.metadata),
        }


@dataclass
class ConflictAnalysis:
    """Risk analysis for a conflict case."""

    conflict: ConflictCase
    risk_score: int = 0
    evidence: List[str] = field(default_factory=list)
    classification: str = SEVERITY_LOW

    def __post_init__(self) -> None:
        if not isinstance(self.conflict, ConflictCase):
            self.conflict = ConflictCase(**self.conflict)
        self.risk_score = max(0, min(100, _safe_int(self.risk_score) or self._default_risk_score()))
        self.evidence = _dedupe(self.evidence or self._default_evidence())
        self.classification = _text(self.classification).upper() or self._classification_from_score()
        if self.classification not in {SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH}:
            self.classification = self._classification_from_score()

    def _default_risk_score(self) -> int:
        return {SEVERITY_LOW: 25, SEVERITY_MEDIUM: 55, SEVERITY_HIGH: 85}.get(self.conflict.severity, 25)

    def _default_evidence(self) -> List[str]:
        return [
            f"Conflict type: {self.conflict.conflict_type}",
            f"Affected section: {self.conflict.affected_section}",
            "Collector review required before any future write path",
        ]

    def _classification_from_score(self) -> str:
        if self.risk_score >= 75:
            return SEVERITY_HIGH
        if self.risk_score >= 45:
            return SEVERITY_MEDIUM
        return SEVERITY_LOW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict": self.conflict.to_dict(),
            "risk_score": self.risk_score,
            "classification": self.classification,
            "evidence": list(self.evidence),
        }


@dataclass
class ConflictRecommendation:
    """Review-only recommendation for a conflict case."""

    conflict_id: str
    action: str
    reasoning: str
    review_required: bool = True
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.conflict_id = _text(self.conflict_id)
        self.action = _text(self.action).upper() or ACTION_REVIEW_REQUIRED
        if self.action not in {ACTION_MERGE, ACTION_KEEP_PRIMARY, ACTION_KEEP_SECONDARY, ACTION_REVIEW_REQUIRED, ACTION_REJECT}:
            self.action = ACTION_REVIEW_REQUIRED
        self.reasoning = _text(self.reasoning) or "Manual collector review required before any future action."
        self.warnings = _dedupe([*self.warnings, "Recommendation not applied automatically"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "action": self.action,
            "reasoning": self.reasoning,
            "review_required": "YES" if self.review_required else "NO",
            "warnings": list(self.warnings),
        }


@dataclass
class ConflictResolutionReport:
    """Conflict resolution report with cases, analyses, and recommendations."""

    report_id: str
    generated_at: str = ""
    conflicts: List[ConflictCase] = field(default_factory=list)
    analyses: List[ConflictAnalysis] = field(default_factory=list)
    recommendations: List[ConflictRecommendation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.report_id = _text(self.report_id) or _id("conflict-report")
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.conflicts = [case if isinstance(case, ConflictCase) else ConflictCase(**case) for case in self.conflicts]
        self.analyses = [analysis if isinstance(analysis, ConflictAnalysis) else ConflictAnalysis(**analysis) for analysis in self.analyses]
        self.recommendations = [
            recommendation if isinstance(recommendation, ConflictRecommendation) else ConflictRecommendation(**recommendation)
            for recommendation in self.recommendations
        ]
        self.warnings = _dedupe([*self.warnings, "Conflict resolution report only; no changes applied"])

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    def severity_counts(self) -> Dict[str, int]:
        counts = {SEVERITY_LOW: 0, SEVERITY_MEDIUM: 0, SEVERITY_HIGH: 0}
        for case in self.conflicts:
            counts[case.severity] = counts.get(case.severity, 0) + 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "conflict_count": self.conflict_count,
            "severity_counts": self.severity_counts(),
            "conflicts": [case.to_dict() for case in self.conflicts],
            "analyses": [analysis.to_dict() for analysis in self.analyses],
            "recommendations": [recommendation.to_dict() for recommendation in self.recommendations],
            "warnings": list(self.warnings),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Conflict Resolution Report",
            "",
            f"- Report: {self.report_id}",
            f"- Generated: {self.generated_at}",
            f"- Conflicts: {self.conflict_count}",
            "- Automatic resolution applied: NO",
            "",
            "## Severity Counts",
            "",
        ]
        for severity, count in self.severity_counts().items():
            lines.append(f"- {severity}: {count}")
        lines.extend(["", "## Conflicts", ""])
        if self.conflicts:
            for case in self.conflicts:
                lines.append(f"- {case.conflict_type} ({case.severity}): {case.affected_section}")
        else:
            lines.append("- None")
        lines.extend(["", "## Recommendations", ""])
        if self.recommendations:
            for recommendation in self.recommendations:
                lines.append(f"- {recommendation.conflict_id}: {recommendation.action} - {recommendation.reasoning}")
        else:
            lines.append("- None")
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        rows = [["section", "conflict_id", "type", "severity", "value"]]
        for case in self.conflicts:
            rows.append(["conflict", case.conflict_id, case.conflict_type, case.severity, case.affected_section])
        for recommendation in self.recommendations:
            rows.append(["recommendation", recommendation.conflict_id, "", recommendation.action, recommendation.reasoning])
        return _write_rows(output_path, rows)


@dataclass
class DeviceLinkReport:
    """Report of linked devices and relationships."""

    report_id: str
    workspace_id: str
    linked_devices: List[LinkedDevice] = field(default_factory=list)
    relationships: List[DeviceRelationship] = field(default_factory=list)
    generated_at: str = ""
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.report_id = _text(self.report_id) or _id("device-link-report", self.workspace_id)
        self.workspace_id = _text(self.workspace_id)
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.linked_devices = [device if isinstance(device, LinkedDevice) else LinkedDevice(**device) for device in self.linked_devices]
        self.relationships = [
            relationship if isinstance(relationship, DeviceRelationship) else DeviceRelationship(**relationship)
            for relationship in self.relationships
        ]
        self.recommendations = _dedupe(self.recommendations or self._default_recommendations())
        self.warnings = _dedupe([*self.warnings, "Device link report only; no synchronization executed"])

    def _default_recommendations(self) -> List[str]:
        if not self.relationships:
            return ["Create at least one reviewed relationship before future device linking"]
        if any(relationship.sync_readiness != "READY_FOR_REVIEW" for relationship in self.relationships):
            return ["Review relationship capability overlap before future sync planning"]
        return ["Relationships are ready for offline conflict review"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "workspace_id": self.workspace_id,
            "generated_at": self.generated_at,
            "linked_device_count": len(self.linked_devices),
            "relationship_count": len(self.relationships),
            "linked_devices": [device.to_dict() for device in self.linked_devices],
            "relationships": [relationship.to_dict() for relationship in self.relationships],
            "recommendations": list(self.recommendations),
            "warnings": list(self.warnings),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Device Link Report",
            "",
            f"- Workspace: {self.workspace_id}",
            f"- Linked devices: {len(self.linked_devices)}",
            f"- Relationships: {len(self.relationships)}",
            "- Synchronization executed: NO",
            "",
            "## Linked Devices",
            "",
        ]
        lines.extend(f"- {device.device_name}: {device.relationship_role} ({device.link_status})" for device in self.linked_devices) if self.linked_devices else lines.append("- None")
        lines.extend(["", "## Relationships", ""])
        if self.relationships:
            for relationship in self.relationships:
                lines.append(f"- {relationship.primary_device_id} -> {relationship.secondary_device_id}: {relationship.relationship_type} ({relationship.sync_readiness})")
        else:
            lines.append("- None")
        lines.extend(["", "## Recommendations", ""])
        lines.extend(f"- {item}" for item in self.recommendations)
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        rows = [["section", "key", "value", "detail"]]
        for device in self.linked_devices:
            rows.append(["device", device.device_id, device.device_name, device.relationship_role])
        for relationship in self.relationships:
            rows.append(["relationship", relationship.relationship_id, relationship.relationship_type, relationship.sync_readiness])
        for recommendation in self.recommendations:
            rows.append(["recommendation", "", recommendation, ""])
        return _write_rows(output_path, rows)


@dataclass
class WorkspaceLinkMap:
    """Workspace map of linked devices, overlap, exposure, and readiness."""

    map_id: str
    workspace_id: str
    linked_devices: List[LinkedDevice] = field(default_factory=list)
    relationships: List[DeviceRelationship] = field(default_factory=list)
    capability_overlap: Dict[str, List[str]] = field(default_factory=dict)
    conflict_exposure: Dict[str, Any] = field(default_factory=dict)
    sync_readiness: str = "NOT_READY"
    generated_at: str = ""
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.map_id = _text(self.map_id) or _id("workspace-link-map", self.workspace_id)
        self.workspace_id = _text(self.workspace_id)
        self.linked_devices = [device if isinstance(device, LinkedDevice) else LinkedDevice(**device) for device in self.linked_devices]
        self.relationships = [
            relationship if isinstance(relationship, DeviceRelationship) else DeviceRelationship(**relationship)
            for relationship in self.relationships
        ]
        self.capability_overlap = {key: list(value) for key, value in dict(self.capability_overlap or {}).items()}
        self.conflict_exposure = dict(self.conflict_exposure or {})
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.warnings = _dedupe([*self.warnings, "Workspace link map only; no device linking executed"])
        if self.sync_readiness == "NOT_READY":
            self.sync_readiness = "READY_FOR_REVIEW" if self.relationships else "NEEDS_RELATIONSHIPS"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "map_id": self.map_id,
            "workspace_id": self.workspace_id,
            "generated_at": self.generated_at,
            "linked_device_count": len(self.linked_devices),
            "relationship_count": len(self.relationships),
            "capability_overlap": dict(self.capability_overlap),
            "conflict_exposure": dict(self.conflict_exposure),
            "sync_readiness": self.sync_readiness,
            "warnings": list(self.warnings),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Workspace Link Map",
            "",
            f"- Workspace: {self.workspace_id}",
            f"- Linked devices: {len(self.linked_devices)}",
            f"- Relationships: {len(self.relationships)}",
            f"- Sync readiness: {self.sync_readiness}",
            "- Real sync configured: NO",
            "",
            "## Capability Overlap",
            "",
        ]
        if self.capability_overlap:
            for key, values in sorted(self.capability_overlap.items()):
                lines.append(f"- {key}: {', '.join(values) if values else 'None'}")
        else:
            lines.append("- None")
        lines.extend(["", "## Conflict Exposure", ""])
        lines.extend(f"- {key}: {value}" for key, value in sorted(self.conflict_exposure.items())) if self.conflict_exposure else lines.append("- None")
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        rows = [["section", "key", "value"]]
        for key, values in sorted(self.capability_overlap.items()):
            rows.append(["capability_overlap", key, "; ".join(values)])
        for key, value in sorted(self.conflict_exposure.items()):
            rows.append(["conflict_exposure", key, value])
        rows.append(["sync_readiness", "status", self.sync_readiness])
        return _write_rows(output_path, rows)


@dataclass
class DeviceLinkReadinessReport:
    """Readiness report for linked devices and unresolved conflicts."""

    report_id: str
    workspace_id: str
    linked_devices: int = 0
    unresolved_conflicts: int = 0
    merge_exposure: int = 0
    backup_coverage: str = "UNKNOWN"
    workspace_health: int = 0
    generated_at: str = ""
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.report_id = _text(self.report_id) or _id("device-link-readiness", self.workspace_id)
        self.workspace_id = _text(self.workspace_id)
        self.linked_devices = _safe_int(self.linked_devices)
        self.unresolved_conflicts = _safe_int(self.unresolved_conflicts)
        self.merge_exposure = _safe_int(self.merge_exposure)
        self.workspace_health = _safe_int(self.workspace_health)
        self.backup_coverage = _text(self.backup_coverage) or "UNKNOWN"
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.recommendations = _dedupe(self.recommendations or self._default_recommendations())
        self.warnings = _dedupe([*self.warnings, "Readiness report only; no linking or resolution applied"])

    @property
    def readiness_score(self) -> int:
        score = self.workspace_health
        score += min(25, self.linked_devices * 8)
        score += 15 if self.backup_coverage == "READY" else 0
        score -= min(50, self.unresolved_conflicts * 10)
        score -= min(25, self.merge_exposure * 5)
        return max(0, min(100, score))

    def _default_recommendations(self) -> List[str]:
        recommendations = []
        if self.unresolved_conflicts:
            recommendations.append("Review unresolved conflicts before future device linking")
        if self.merge_exposure:
            recommendations.append("Review merge exposure and require collector confirmation")
        if self.backup_coverage != "READY":
            recommendations.append("Create or verify backup coverage before future linking")
        if not recommendations:
            recommendations.append("Device links are ready for offline review-driven planning")
        return recommendations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "workspace_id": self.workspace_id,
            "generated_at": self.generated_at,
            "linked_devices": self.linked_devices,
            "unresolved_conflicts": self.unresolved_conflicts,
            "merge_exposure": self.merge_exposure,
            "backup_coverage": self.backup_coverage,
            "workspace_health": self.workspace_health,
            "readiness_score": self.readiness_score,
            "recommendations": list(self.recommendations),
            "warnings": list(self.warnings),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Device Link Readiness Report",
            "",
            f"- Workspace: {self.workspace_id}",
            f"- Linked devices: {self.linked_devices}",
            f"- Unresolved conflicts: {self.unresolved_conflicts}",
            f"- Merge exposure: {self.merge_exposure}",
            f"- Backup coverage: {self.backup_coverage}",
            f"- Workspace health: {self.workspace_health}/100",
            f"- Readiness score: {self.readiness_score}/100",
            "- Automatic conflict resolution: NO",
            "",
            "## Recommendations",
            "",
        ]
        lines.extend(f"- {item}" for item in self.recommendations)
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        rows = [["section", "key", "value"]]
        for key, value in self.to_dict().items():
            if isinstance(value, list):
                for item in value:
                    rows.append([key, "", item])
            else:
                rows.append(["summary", key, value])
        return _write_rows(output_path, rows)


class ConflictResolutionEngine:
    """Analyze workspace snapshots and recommend review-only resolutions."""

    def analyze_snapshots(self, primary: WorkspaceSnapshot, secondary: WorkspaceSnapshot) -> ConflictResolutionReport:
        conflicts = self.detect_conflicts(primary, secondary)
        analyses = [self.analyze_case(case) for case in conflicts]
        recommendations = [self.recommend(analysis) for analysis in analyses]
        return ConflictResolutionReport(
            report_id=_id("conflict-resolution", primary.snapshot_id, secondary.snapshot_id),
            conflicts=conflicts,
            analyses=analyses,
            recommendations=recommendations,
        )

    def detect_conflicts(self, primary: WorkspaceSnapshot, secondary: WorkspaceSnapshot) -> List[ConflictCase]:
        diff = primary.compare_to(secondary)
        conflicts: List[ConflictCase] = []
        section_map = {
            "collection_state": CONFLICT_COLLECTION,
            "portfolio_state": CONFLICT_PORTFOLIO,
            "workflow_state": CONFLICT_WORKFLOW,
            "watchlist_state": CONFLICT_WATCHLIST,
        }
        for section in diff.get("changed_sections", []):
            conflict_type = section_map.get(section, CONFLICT_SNAPSHOT)
            primary_state = getattr(primary, section, {})
            secondary_state = getattr(secondary, section, {})
            severity = self.classify_conflict(conflict_type, primary_state, secondary_state)
            conflicts.append(ConflictCase(
                conflict_id=_id("conflict", conflict_type, section),
                conflict_type=conflict_type,
                severity=severity,
                affected_section=section,
                primary_summary=self._state_summary(primary_state),
                secondary_summary=self._state_summary(secondary_state),
                metadata={"primary_snapshot": primary.snapshot_id, "secondary_snapshot": secondary.snapshot_id},
            ))
        if primary.metadata.get("settings_hash") and secondary.metadata.get("settings_hash") and primary.metadata.get("settings_hash") != secondary.metadata.get("settings_hash"):
            conflicts.append(ConflictCase(
                conflict_id=_id("conflict", CONFLICT_SETTINGS, primary.snapshot_id, secondary.snapshot_id),
                conflict_type=CONFLICT_SETTINGS,
                severity=SEVERITY_MEDIUM,
                affected_section="settings",
                primary_summary=_text(primary.metadata.get("settings_hash")),
                secondary_summary=_text(secondary.metadata.get("settings_hash")),
                metadata={"primary_snapshot": primary.snapshot_id, "secondary_snapshot": secondary.snapshot_id},
            ))
        if primary.state_hash != secondary.state_hash:
            conflicts.append(ConflictCase(
                conflict_id=_id("conflict", CONFLICT_SNAPSHOT, primary.snapshot_id, secondary.snapshot_id),
                conflict_type=CONFLICT_SNAPSHOT,
                severity=SEVERITY_LOW if conflicts else SEVERITY_MEDIUM,
                affected_section="snapshot",
                primary_summary=primary.state_hash,
                secondary_summary=secondary.state_hash,
                metadata={"added_devices": diff.get("added_devices", []), "removed_devices": diff.get("removed_devices", [])},
            ))
        return conflicts

    def classify_conflict(self, conflict_type: str, primary_state: Dict[str, Any], secondary_state: Dict[str, Any]) -> str:
        if conflict_type == CONFLICT_COLLECTION:
            item_delta = abs(_safe_int(primary_state.get("collection_items")) - _safe_int(secondary_state.get("collection_items")))
            changed_hash = primary_state.get("content_hash") != secondary_state.get("content_hash")
            if item_delta >= 2 or (changed_hash and item_delta):
                return SEVERITY_HIGH
            return SEVERITY_MEDIUM if changed_hash else SEVERITY_LOW
        if conflict_type == CONFLICT_WORKFLOW:
            escalations = max(_safe_int(primary_state.get("review_escalations")), _safe_int(secondary_state.get("review_escalations")))
            return SEVERITY_HIGH if escalations >= 2 else SEVERITY_MEDIUM
        if conflict_type == CONFLICT_PORTFOLIO:
            return SEVERITY_MEDIUM
        if conflict_type == CONFLICT_WATCHLIST:
            return SEVERITY_LOW
        if conflict_type == CONFLICT_SETTINGS:
            return SEVERITY_MEDIUM
        return SEVERITY_LOW

    def analyze_case(self, case: ConflictCase) -> ConflictAnalysis:
        base = {SEVERITY_LOW: 25, SEVERITY_MEDIUM: 55, SEVERITY_HIGH: 85}[case.severity]
        if case.conflict_type == CONFLICT_COLLECTION:
            base += 10
        if case.conflict_type == CONFLICT_WORKFLOW:
            base += 5
        return ConflictAnalysis(
            conflict=case,
            risk_score=min(100, base),
            evidence=[
                f"Primary: {case.primary_summary}",
                f"Secondary: {case.secondary_summary}",
                "Collector review remains mandatory",
            ],
        )

    def recommend(self, analysis: ConflictAnalysis) -> ConflictRecommendation:
        case = analysis.conflict
        if analysis.classification == SEVERITY_HIGH:
            action = ACTION_REVIEW_REQUIRED
            reasoning = "High-risk conflict; compare both device states before choosing any future write path."
        elif case.conflict_type == CONFLICT_WATCHLIST:
            action = ACTION_MERGE
            reasoning = "Watchlist differences are usually merge candidates, but collector confirmation is still required."
        elif case.conflict_type == CONFLICT_SETTINGS:
            action = ACTION_KEEP_PRIMARY
            reasoning = "Settings should default to the primary device unless the collector chooses otherwise."
        elif case.conflict_type == CONFLICT_SNAPSHOT:
            action = ACTION_REVIEW_REQUIRED
            reasoning = "Snapshot divergence indicates device state drift and must be reviewed."
        else:
            action = ACTION_KEEP_PRIMARY if analysis.classification == SEVERITY_MEDIUM else ACTION_MERGE
            reasoning = "Primary device can be the reference point, but no change is applied automatically."
        return ConflictRecommendation(conflict_id=case.conflict_id, action=action, reasoning=reasoning)

    def _state_summary(self, state: Dict[str, Any]) -> str:
        if not state:
            return "empty"
        useful = []
        for key in ["collection_items", "record_count", "health_score", "workflow_reports", "want_list_intents", "content_hash"]:
            if key in state:
                useful.append(f"{key}={state.get(key)}")
        return "; ".join(useful) if useful else "; ".join(f"{key}={value}" for key, value in sorted(state.items())[:4])


class DeviceLinkingEngine:
    """Build offline linked-device and conflict-resolution artifacts."""

    def __init__(
        self,
        collection_items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        workflow_completion_reports: Optional[Iterable[Any]] = None,
        mobile_entry_reports: Optional[Iterable[Any]] = None,
        mobile_companion_reports: Optional[Iterable[Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        workspace_engine: Optional[MultiDeviceWorkspaceEngine] = None,
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
        self.workspace_engine = workspace_engine or MultiDeviceWorkspaceEngine(
            collection_items=self.collection_items,
            want_list_intents=self.want_list_intents,
            workflow_completion_reports=self.workflow_completion_reports,
            mobile_entry_reports=self.mobile_entry_reports,
            mobile_companion_reports=self.mobile_companion_reports,
            settings=self.settings,
            collector_cloud=self.collector_cloud,
            sync_backup_engine=self.sync_backup_engine,
        )
        self.conflict_engine = ConflictResolutionEngine()

    def create_linked_device(self, profile: DeviceProfile, relationship_role: str = RELATIONSHIP_SECONDARY) -> LinkedDevice:
        return LinkedDevice.from_profile(profile, relationship_role)

    def capability_overlap(self, primary: LinkedDevice, secondary: LinkedDevice) -> List[str]:
        return _dedupe(capability for capability in primary.capabilities if capability in set(secondary.capabilities))

    def link_devices(
        self,
        primary: LinkedDevice,
        secondary: LinkedDevice,
        relationship_type: str = RELATIONSHIP_SECONDARY,
        link_status: str = LINK_PENDING,
    ) -> DeviceRelationship:
        overlap = self.capability_overlap(primary, secondary)
        readiness = "READY_FOR_REVIEW" if overlap and primary.link_status in {LINK_PENDING, LINK_LINKED} else "NEEDS_REVIEW"
        return DeviceRelationship(
            relationship_id=_id("relationship", primary.device_id, secondary.device_id, relationship_type),
            primary_device_id=primary.device_id,
            secondary_device_id=secondary.device_id,
            relationship_type=relationship_type,
            link_status=link_status,
            capability_overlap=overlap,
            sync_readiness=readiness,
            metadata={"automatic_sync": "NO", "collector_review_required": "YES"},
        )

    def link_workspace(self, workspace: CollectorWorkspace) -> DeviceLinkReport:
        linked_devices = self._linked_devices_for_workspace(workspace)
        primary = self._primary_device(linked_devices)
        relationships: List[DeviceRelationship] = []
        for device in linked_devices:
            if device.device_id == primary.device_id:
                continue
            relationships.append(self.link_devices(primary, device, device.relationship_role))
        return DeviceLinkReport(
            report_id=_id("device-link-report", workspace.workspace_id),
            workspace_id=workspace.workspace_id,
            linked_devices=linked_devices,
            relationships=relationships,
        )

    def create_link_map(
        self,
        workspace: CollectorWorkspace,
        link_report: Optional[DeviceLinkReport] = None,
        conflict_report: Optional[ConflictResolutionReport] = None,
    ) -> WorkspaceLinkMap:
        link_report = link_report or self.link_workspace(workspace)
        overlap = {
            relationship.relationship_id: list(relationship.capability_overlap)
            for relationship in link_report.relationships
        }
        conflict_report = conflict_report or self.analyze_workspace_conflicts(workspace)
        exposure = {
            "conflict_count": conflict_report.conflict_count,
            "high_severity": conflict_report.severity_counts().get(SEVERITY_HIGH, 0),
            "review_required": sum(1 for rec in conflict_report.recommendations if rec.action == ACTION_REVIEW_REQUIRED),
            "automatic_resolution": "NO",
        }
        readiness = "READY_FOR_REVIEW" if link_report.relationships and exposure["high_severity"] == 0 else "NEEDS_CONFLICT_REVIEW"
        return WorkspaceLinkMap(
            map_id=_id("workspace-link-map", workspace.workspace_id),
            workspace_id=workspace.workspace_id,
            linked_devices=link_report.linked_devices,
            relationships=link_report.relationships,
            capability_overlap=overlap,
            conflict_exposure=exposure,
            sync_readiness=readiness,
        )

    def analyze_workspace_conflicts(self, workspace: CollectorWorkspace) -> ConflictResolutionReport:
        if len(workspace.workspace_snapshots) < 2:
            if not workspace.workspace_snapshots:
                self.workspace_engine.create_snapshot(workspace, "device-link-primary")
            self.workspace_engine.create_snapshot(workspace, "device-link-secondary")
        return self.conflict_engine.analyze_snapshots(workspace.workspace_snapshots[-2], workspace.workspace_snapshots[-1])

    def readiness_report(
        self,
        workspace: CollectorWorkspace,
        link_map: Optional[WorkspaceLinkMap] = None,
        conflict_report: Optional[ConflictResolutionReport] = None,
        workspace_health: Optional[WorkspaceHealthReport] = None,
    ) -> DeviceLinkReadinessReport:
        conflict_report = conflict_report or self.analyze_workspace_conflicts(workspace)
        link_map = link_map or self.create_link_map(workspace, conflict_report=conflict_report)
        workspace_health = workspace_health or self.workspace_engine.health_report(workspace)
        merge_exposure = sum(1 for recommendation in conflict_report.recommendations if recommendation.action == ACTION_MERGE)
        return DeviceLinkReadinessReport(
            report_id=_id("device-link-readiness", workspace.workspace_id),
            workspace_id=workspace.workspace_id,
            linked_devices=len(link_map.linked_devices),
            unresolved_conflicts=conflict_report.conflict_count,
            merge_exposure=merge_exposure,
            backup_coverage=workspace.backup_readiness,
            workspace_health=workspace_health.health_score,
        )

    def _linked_devices_for_workspace(self, workspace: CollectorWorkspace) -> List[LinkedDevice]:
        linked: List[LinkedDevice] = []
        for index, profile in enumerate(workspace.registered_devices):
            role = self._role_for_profile(profile, index)
            status = LINK_LINKED if index == 0 else LINK_PENDING
            device = self.create_linked_device(profile, role)
            device.link_status = status
            linked.append(device)
        return linked

    def _primary_device(self, devices: Sequence[LinkedDevice]) -> LinkedDevice:
        for device in devices:
            if device.relationship_role == RELATIONSHIP_PRIMARY:
                return device
        return devices[0] if devices else LinkedDevice("primary", "Primary Device", "Desktop", RELATIONSHIP_PRIMARY)

    def _role_for_profile(self, profile: DeviceProfile, index: int) -> str:
        if index == 0:
            return RELATIONSHIP_PRIMARY
        if CAPABILITY_BACKUP_OPERATIONS in profile.capabilities:
            return RELATIONSHIP_BACKUP
        if profile.device_type.lower() == "phone":
            return RELATIONSHIP_MOBILE
        if profile.device_type.lower() == "tablet":
            return RELATIONSHIP_TABLET
        return RELATIONSHIP_SECONDARY
