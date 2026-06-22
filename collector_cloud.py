"""Offline Collector Cloud Foundation models.

This module prepares local collection data for future cloud, sync, backup, and
multi-device work. It does not connect to a network, authenticate users, create
cloud accounts, run background jobs, execute synchronization, or mutate
collection records.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from collection_intelligence import CollectionIntelligenceEngine
from portfolio_performance import PortfolioPerformanceEngine


CONFLICT_RECORD = "record"
CONFLICT_COLLECTION = "collection"
CONFLICT_WORKFLOW = "workflow"
CONFLICT_SETTINGS = "settings"

MODULE_COLLECTION = "collection"
MODULE_WANT_LIST = "want_list"
MODULE_PORTFOLIO = "portfolio"
MODULE_MOBILE_ENTRY = "mobile_entry"
MODULE_MOBILE_COMPANION = "mobile_companion"
MODULE_WORKFLOW = "workflow"
MODULE_SETTINGS = "settings"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_list(values: Optional[Iterable[Any]]) -> List[Any]:
    return list(values or [])


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


def _money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    try:
        return round(float(_text(value).replace("$", "").replace(",", "")), 2)
    except ValueError:
        return 0.0


def _item_label(item: Any) -> str:
    parts = [
        _text(getattr(item, "country", "")),
        _text(getattr(item, "year", "")),
        _text(getattr(item, "denomination", "")),
        _text(getattr(item, "grade", "")),
    ]
    return " ".join(part for part in parts if part) or _text(getattr(item, "title", "")) or "Collection record"


def _record_id(module: str, prefix: str, raw_id: Any, payload: Any) -> str:
    clean = _text(raw_id)
    if clean:
        return f"{module}:{clean}"
    return f"{module}:{prefix}-{_hash(payload)[:12]}"


@dataclass
class CloudRecord:
    """Local representation of one future cloud-syncable record."""

    record_id: str
    module: str
    record_type: str
    summary: str = ""
    content_hash: str = ""
    updated_at: str = ""
    sync_status: str = "SYNCABLE"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.record_id = _text(self.record_id)
        self.module = _text(self.module) or MODULE_COLLECTION
        self.record_type = _text(self.record_type) or "record"
        self.summary = _text(self.summary) or self.record_id
        self.updated_at = _text(self.updated_at) or _now_iso()
        self.sync_status = _text(self.sync_status).upper() or "SYNCABLE"
        self.metadata = dict(self.metadata or {})
        if not self.content_hash:
            self.content_hash = _hash({"summary": self.summary, "metadata": self.metadata})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "module": self.module,
            "record_type": self.record_type,
            "summary": self.summary,
            "content_hash": self.content_hash,
            "updated_at": self.updated_at,
            "sync_status": self.sync_status,
            "metadata": dict(self.metadata),
        }


@dataclass
class CloudConflict:
    """Manual-review conflict produced by sync planning."""

    conflict_id: str
    conflict_type: str
    record_id: str
    source_summary: str = ""
    destination_summary: str = ""
    recommendation: str = "Manual review required before any future sync."
    severity: str = "REVIEW"
    review_required: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.conflict_id = _text(self.conflict_id) or f"conflict-{_hash(self.record_id)[:12]}"
        self.conflict_type = _text(self.conflict_type).lower() or CONFLICT_RECORD
        if self.conflict_type not in {CONFLICT_RECORD, CONFLICT_COLLECTION, CONFLICT_WORKFLOW, CONFLICT_SETTINGS}:
            self.conflict_type = CONFLICT_RECORD
        self.record_id = _text(self.record_id)
        self.source_summary = _text(self.source_summary)
        self.destination_summary = _text(self.destination_summary)
        self.recommendation = _text(self.recommendation) or "Manual review required before any future sync."
        self.severity = _text(self.severity).upper() or "REVIEW"
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type,
            "record_id": self.record_id,
            "source_summary": self.source_summary,
            "destination_summary": self.destination_summary,
            "recommendation": self.recommendation,
            "severity": self.severity,
            "review_required": "YES" if self.review_required else "NO",
            "metadata": dict(self.metadata),
        }


@dataclass
class CloudCollectionSnapshot:
    """Point-in-time local cloud-readiness snapshot."""

    snapshot_id: str
    source_label: str = "local"
    created_at: str = ""
    records: List[CloudRecord] = field(default_factory=list)
    collection_metrics: Dict[str, Any] = field(default_factory=dict)
    portfolio_metrics: Dict[str, Any] = field(default_factory=dict)
    workflow_metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.source_label = _text(self.source_label) or "local"
        self.created_at = _text(self.created_at) or _now_iso()
        self.records = [record if isinstance(record, CloudRecord) else CloudRecord(**record) for record in self.records]
        if not self.snapshot_id:
            self.snapshot_id = f"cloud-snapshot-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.collection_metrics = dict(self.collection_metrics or {})
        self.portfolio_metrics = dict(self.portfolio_metrics or {})
        self.workflow_metrics = dict(self.workflow_metrics or {})
        self.metadata = dict(self.metadata or {})
        self.warnings = _dedupe([*self.warnings, "Offline snapshot only; no cloud upload performed"])

    @property
    def record_count(self) -> int:
        return len(self.records)

    @property
    def content_hash(self) -> str:
        return _hash([record.to_dict() for record in sorted(self.records, key=lambda item: item.record_id)])

    def module_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for record in self.records:
            counts[record.module] = counts.get(record.module, 0) + 1
        return counts

    def records_by_id(self) -> Dict[str, CloudRecord]:
        return {record.record_id: record for record in self.records}

    def compare_to(self, other: "CloudCollectionSnapshot") -> Dict[str, Any]:
        other = other if isinstance(other, CloudCollectionSnapshot) else CloudCollectionSnapshot(**other)
        source = self.records_by_id()
        destination = other.records_by_id()
        added = sorted(record_id for record_id in source if record_id not in destination)
        removed = sorted(record_id for record_id in destination if record_id not in source)
        changed = sorted(
            record_id for record_id in source.keys() & destination.keys()
            if source[record_id].content_hash != destination[record_id].content_hash
        )
        return {
            "source_snapshot_id": self.snapshot_id,
            "destination_snapshot_id": other.snapshot_id,
            "added_record_ids": added,
            "removed_record_ids": removed,
            "changed_record_ids": changed,
            "source_record_count": self.record_count,
            "destination_record_count": other.record_count,
            "source_hash": self.content_hash,
            "destination_hash": other.content_hash,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "source_label": self.source_label,
            "created_at": self.created_at,
            "record_count": self.record_count,
            "content_hash": self.content_hash,
            "module_counts": self.module_counts(),
            "collection_metrics": dict(self.collection_metrics),
            "portfolio_metrics": dict(self.portfolio_metrics),
            "workflow_metrics": dict(self.workflow_metrics),
            "metadata": dict(self.metadata),
            "warnings": "; ".join(self.warnings),
            "records": [record.to_dict() for record in self.records],
        }

    def format_markdown(self) -> str:
        lines = [
            "# Collector Cloud Snapshot",
            "",
            f"- Snapshot: {self.snapshot_id}",
            f"- Source: {self.source_label}",
            f"- Created: {self.created_at}",
            f"- Records: {self.record_count}",
            f"- Snapshot hash: {self.content_hash}",
            "- Cloud upload performed: NO",
            "",
            "## Module Counts",
            "",
        ]
        for module, count in sorted(self.module_counts().items()):
            lines.append(f"- {module}: {count}")
        lines.extend(["", "## Collection Metrics", ""])
        metric_lines = [f"- {key}: {value}" for key, value in sorted(self.collection_metrics.items())]
        lines.extend(metric_lines or ["- None"])
        lines.extend(["", "## Portfolio Metrics", ""])
        portfolio_lines = [f"- {key}: {value}" for key, value in sorted(self.portfolio_metrics.items())]
        lines.extend(portfolio_lines or ["- None"])
        lines.extend(["", "## Workflow Metrics", ""])
        workflow_lines = [f"- {key}: {value}" for key, value in sorted(self.workflow_metrics.items())]
        lines.extend(workflow_lines or ["- None"])
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["snapshot_id", "record_id", "module", "record_type", "summary", "content_hash", "sync_status"])
            for record in self.records:
                writer.writerow([self.snapshot_id, record.record_id, record.module, record.record_type, record.summary, record.content_hash, record.sync_status])
        return True


@dataclass
class CloudSyncPlan:
    """Review-only plan for a possible future sync operation."""

    plan_id: str
    source_snapshot: CloudCollectionSnapshot
    destination_snapshot: CloudCollectionSnapshot
    proposed_changes: List[Dict[str, Any]] = field(default_factory=list)
    merge_candidates: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[CloudConflict] = field(default_factory=list)
    generated_at: str = ""
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.generated_at = _text(self.generated_at) or _now_iso()
        if not isinstance(self.source_snapshot, CloudCollectionSnapshot):
            self.source_snapshot = CloudCollectionSnapshot(**self.source_snapshot)
        if not isinstance(self.destination_snapshot, CloudCollectionSnapshot):
            self.destination_snapshot = CloudCollectionSnapshot(**self.destination_snapshot)
        self.conflicts = [conflict if isinstance(conflict, CloudConflict) else CloudConflict(**conflict) for conflict in self.conflicts]
        self.warnings = _dedupe([*self.warnings, "Plan only; synchronization not executed"])

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def proposed_change_count(self) -> int:
        return len(self.proposed_changes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "generated_at": self.generated_at,
            "source_snapshot_id": self.source_snapshot.snapshot_id,
            "destination_snapshot_id": self.destination_snapshot.snapshot_id,
            "proposed_change_count": self.proposed_change_count,
            "merge_candidate_count": len(self.merge_candidates),
            "conflict_count": self.conflict_count,
            "proposed_changes": list(self.proposed_changes),
            "merge_candidates": list(self.merge_candidates),
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "warnings": "; ".join(self.warnings),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Collector Cloud Sync Plan",
            "",
            f"- Plan: {self.plan_id}",
            f"- Generated: {self.generated_at}",
            f"- Source snapshot: {self.source_snapshot.snapshot_id}",
            f"- Destination snapshot: {self.destination_snapshot.snapshot_id}",
            f"- Proposed changes: {self.proposed_change_count}",
            f"- Merge candidates: {len(self.merge_candidates)}",
            f"- Conflicts: {self.conflict_count}",
            "- Synchronization executed: NO",
            "",
            "## Proposed Changes",
            "",
        ]
        if self.proposed_changes:
            for change in self.proposed_changes:
                lines.append(f"- {change.get('action')}: {change.get('record_id')} - {change.get('summary')}")
        else:
            lines.append("- No changes proposed.")
        lines.extend(["", "## Merge Candidates", ""])
        if self.merge_candidates:
            for candidate in self.merge_candidates:
                lines.append(f"- {candidate.get('record_id')}: {candidate.get('reason')}")
        else:
            lines.append("- No merge candidates identified.")
        lines.extend(["", "## Conflicts", ""])
        if self.conflicts:
            for conflict in self.conflicts:
                lines.append(f"- {conflict.conflict_type}: {conflict.record_id} - {conflict.recommendation}")
        else:
            lines.append("- No conflicts detected.")
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "action", "record_id", "summary", "recommendation"])
            for change in self.proposed_changes:
                writer.writerow(["proposed_change", change.get("action", ""), change.get("record_id", ""), change.get("summary", ""), ""])
            for candidate in self.merge_candidates:
                writer.writerow(["merge_candidate", "REVIEW", candidate.get("record_id", ""), candidate.get("reason", ""), "Manual merge review"])
            for conflict in self.conflicts:
                writer.writerow(["conflict", conflict.conflict_type, conflict.record_id, conflict.source_summary, conflict.recommendation])
        return True


@dataclass
class CloudBackupPackage:
    """Local backup package model for future recovery flows."""

    package_id: str
    snapshot: CloudCollectionSnapshot
    generated_at: str = ""
    package_metadata: Dict[str, Any] = field(default_factory=dict)
    validation_findings: List[str] = field(default_factory=list)
    restore_preview: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, CloudCollectionSnapshot):
            self.snapshot = CloudCollectionSnapshot(**self.snapshot)
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.package_metadata = dict(self.package_metadata or {})
        self.validation_findings = _dedupe(self.validation_findings or self._default_validation())
        self.restore_preview = _dedupe(self.restore_preview or self._default_restore_preview())
        self.warnings = _dedupe([*self.warnings, "Backup package model only; no cloud storage or restore executed"])

    def _default_validation(self) -> List[str]:
        findings = ["Snapshot metadata present", f"Records included: {self.snapshot.record_count}"]
        findings.append("Snapshot hash present" if self.snapshot.content_hash else "Snapshot hash missing")
        if self.snapshot.record_count == 0:
            findings.append("No records in package; review before relying on backup")
        return findings

    def _default_restore_preview(self) -> List[str]:
        return [
            f"Would review {self.snapshot.record_count} record(s) from snapshot {self.snapshot.snapshot_id}",
            "Would require manual confirmation before replacing local records",
            "Would not contact cloud services",
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "generated_at": self.generated_at,
            "snapshot_id": self.snapshot.snapshot_id,
            "record_count": self.snapshot.record_count,
            "package_metadata": dict(self.package_metadata),
            "validation_findings": list(self.validation_findings),
            "restore_preview": list(self.restore_preview),
            "warnings": "; ".join(self.warnings),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Collector Cloud Backup Package",
            "",
            f"- Package: {self.package_id}",
            f"- Generated: {self.generated_at}",
            f"- Snapshot: {self.snapshot.snapshot_id}",
            f"- Records: {self.snapshot.record_count}",
            "- Cloud storage used: NO",
            "- Restore executed: NO",
            "",
            "## Validation Report",
            "",
        ]
        lines.extend(f"- {finding}" for finding in self.validation_findings)
        lines.extend(["", "## Restore Preview", ""])
        lines.extend(f"- {item}" for item in self.restore_preview)
        lines.extend(["", "## Metadata", ""])
        metadata_lines = [f"- {key}: {value}" for key, value in sorted(self.package_metadata.items())]
        lines.extend(metadata_lines or ["- None"])
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "value"])
            writer.writerow(["package_id", self.package_id])
            writer.writerow(["snapshot_id", self.snapshot.snapshot_id])
            writer.writerow(["record_count", self.snapshot.record_count])
            for finding in self.validation_findings:
                writer.writerow(["validation", finding])
            for item in self.restore_preview:
                writer.writerow(["restore_preview", item])
            for key, value in sorted(self.package_metadata.items()):
                writer.writerow([f"metadata_{key}", value])
        return True


@dataclass
class CloudReadinessReport:
    """Report measuring readiness for future cloud adoption."""

    generated_at: str = ""
    syncable_modules: List[str] = field(default_factory=list)
    non_syncable_modules: List[str] = field(default_factory=list)
    migration_requirements: List[str] = field(default_factory=list)
    risk_areas: List[str] = field(default_factory=list)
    conflict_exposure: List[str] = field(default_factory=list)
    readiness_score: int = 0
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.syncable_modules = _dedupe(self.syncable_modules)
        self.non_syncable_modules = _dedupe(self.non_syncable_modules)
        self.migration_requirements = _dedupe(self.migration_requirements)
        self.risk_areas = _dedupe(self.risk_areas)
        self.conflict_exposure = _dedupe(self.conflict_exposure)
        if not self.readiness_score:
            total = len(self.syncable_modules) + len(self.non_syncable_modules) + len(self.risk_areas)
            self.readiness_score = 0 if total == 0 else max(0, min(100, round((len(self.syncable_modules) / total) * 100)))
        self.warnings = _dedupe([*self.warnings, "Readiness report only; no cloud services configured"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "readiness_score": self.readiness_score,
            "syncable_modules": list(self.syncable_modules),
            "non_syncable_modules": list(self.non_syncable_modules),
            "migration_requirements": list(self.migration_requirements),
            "risk_areas": list(self.risk_areas),
            "conflict_exposure": list(self.conflict_exposure),
            "warnings": "; ".join(self.warnings),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Collector Cloud Readiness Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Readiness score: {self.readiness_score}/100",
            "- Cloud services configured: NO",
            "",
        ]
        for title, values in [
            ("Syncable Modules", self.syncable_modules),
            ("Non-Syncable Modules", self.non_syncable_modules),
            ("Migration Requirements", self.migration_requirements),
            ("Risk Areas", self.risk_areas),
            ("Conflict Exposure", self.conflict_exposure),
            ("Warnings", self.warnings),
        ]:
            lines.extend([f"## {title}", ""])
            lines.extend(f"- {value}" for value in values) if values else lines.append("- None")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "value"])
            writer.writerow(["readiness_score", self.readiness_score])
            for section, values in [
                ("syncable_module", self.syncable_modules),
                ("non_syncable_module", self.non_syncable_modules),
                ("migration_requirement", self.migration_requirements),
                ("risk_area", self.risk_areas),
                ("conflict_exposure", self.conflict_exposure),
                ("warning", self.warnings),
            ]:
                for value in values:
                    writer.writerow([section, value])
        return True


class CollectorCloud:
    """Build local cloud-foundation reports without network side effects."""

    def __init__(
        self,
        collection_items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        workflow_completion_reports: Optional[Iterable[Any]] = None,
        mobile_entry_reports: Optional[Iterable[Any]] = None,
        mobile_companion_reports: Optional[Iterable[Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ):
        self.collection_items = _as_list(collection_items)
        self.want_list_intents = _as_list(want_list_intents)
        self.workflow_completion_reports = _as_list(workflow_completion_reports)
        self.mobile_entry_reports = _as_list(mobile_entry_reports)
        self.mobile_companion_reports = _as_list(mobile_companion_reports)
        self.settings = dict(settings or {})
        self.snapshots: List[CloudCollectionSnapshot] = []

    def create_snapshot(self, source_label: str = "local") -> CloudCollectionSnapshot:
        records = self._collection_records()
        records.extend(self._want_list_records())
        records.extend(self._mobile_entry_records())
        records.extend(self._workflow_records())
        records.extend(self._mobile_companion_records())
        records.extend(self._settings_records())
        snapshot = CloudCollectionSnapshot(
            snapshot_id=f"cloud-snapshot-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            source_label=source_label,
            records=records,
            collection_metrics=self._collection_metrics(),
            portfolio_metrics=self._portfolio_metrics(),
            workflow_metrics=self._workflow_metrics(),
            metadata={
                "engine": "CollectorCloud",
                "network_required": "NO",
                "cloud_provider": "NONE",
                "sync_execution": "NO",
            },
        )
        self.snapshots.append(snapshot)
        return snapshot

    def snapshot_history(self) -> List[CloudCollectionSnapshot]:
        return list(self.snapshots)

    def compare_snapshots(self, source: CloudCollectionSnapshot, destination: CloudCollectionSnapshot) -> Dict[str, Any]:
        return source.compare_to(destination)

    def create_sync_plan(self, source: CloudCollectionSnapshot, destination: CloudCollectionSnapshot) -> CloudSyncPlan:
        source_records = source.records_by_id()
        dest_records = destination.records_by_id()
        changes: List[Dict[str, Any]] = []
        conflicts: List[CloudConflict] = []
        for record_id in sorted(source_records):
            record = source_records[record_id]
            if record_id not in dest_records:
                changes.append({"action": "ADD_TO_DESTINATION", "record_id": record_id, "summary": record.summary, "module": record.module})
            elif record.content_hash != dest_records[record_id].content_hash:
                changes.append({"action": "REVIEW_UPDATE", "record_id": record_id, "summary": record.summary, "module": record.module})
                conflicts.append(self._conflict(record, dest_records[record_id]))
        for record_id in sorted(dest_records):
            if record_id not in source_records:
                record = dest_records[record_id]
                changes.append({"action": "DESTINATION_ONLY_REVIEW", "record_id": record_id, "summary": record.summary, "module": record.module})
        merge_candidates = self._merge_candidates(source.records, destination.records)
        return CloudSyncPlan(
            plan_id=f"cloud-sync-plan-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            source_snapshot=source,
            destination_snapshot=destination,
            proposed_changes=changes,
            merge_candidates=merge_candidates,
            conflicts=conflicts,
        )

    def create_backup_package(self, snapshot: Optional[CloudCollectionSnapshot] = None, package_label: str = "local-backup") -> CloudBackupPackage:
        snapshot = snapshot or (self.snapshots[-1] if self.snapshots else self.create_snapshot(package_label))
        return CloudBackupPackage(
            package_id=f"cloud-backup-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            snapshot=snapshot,
            package_metadata={
                "package_label": package_label,
                "snapshot_hash": snapshot.content_hash,
                "record_count": snapshot.record_count,
                "cloud_storage": "NO",
                "restore_execution": "NO",
            },
        )

    def validate_backup_package(self, package: CloudBackupPackage) -> List[str]:
        findings = list(package.validation_findings)
        if package.snapshot.content_hash != package.package_metadata.get("snapshot_hash"):
            findings.append("Snapshot hash differs from package metadata; review before restore")
        else:
            findings.append("Snapshot hash matches package metadata")
        return _dedupe(findings)

    def restore_package_preview(self, package: CloudBackupPackage) -> List[str]:
        return list(package.restore_preview)

    def cloud_readiness_report(self, snapshots: Optional[Sequence[CloudCollectionSnapshot]] = None) -> CloudReadinessReport:
        snapshots = list(snapshots or self.snapshots)
        latest = snapshots[-1] if snapshots else self.create_snapshot("readiness")
        module_counts = latest.module_counts()
        syncable = [
            f"Collection records ({module_counts.get(MODULE_COLLECTION, 0)})",
            f"WANT_LIST intents ({module_counts.get(MODULE_WANT_LIST, 0)})",
            f"Portfolio metrics ({len(latest.portfolio_metrics)})",
            f"Mobile collection entry reports ({module_counts.get(MODULE_MOBILE_ENTRY, 0)})",
            f"Workflow integration sessions ({module_counts.get(MODULE_WORKFLOW, 0)})",
        ]
        non_syncable = [
            "Raw photo files and arbitrary local image folders",
            "Live source fetching state and public RSS connectivity",
            "Tkinter runtime/window state",
            "External workbook files not copied into a package",
        ]
        requirements = [
            "Define stable record identifiers for all persisted modules",
            "Persist snapshot manifests before real sync",
            "Add device identity and user-confirmed trust boundary in a future release",
            "Keep conflict review mandatory before any write-back path",
        ]
        risks = [
            "Duplicate local records may produce collection conflicts",
            "OCR and mobile-entry previews require manual review before becoming ownership records",
            "Photo paths may be machine-specific and need migration mapping",
            "Settings are currently lightweight local preferences only",
        ]
        exposure = [
            f"Snapshot records exposed to conflict planning: {latest.record_count}",
            f"Collection duplicate groups: {latest.collection_metrics.get('duplicate_groups', 0)}",
            f"Workflow review escalations: {latest.workflow_metrics.get('review_escalations', 0)}",
            f"Changed snapshot history entries available: {len(snapshots)}",
        ]
        score = max(0, min(100, 55 + min(25, latest.record_count) - min(20, len(risks) * 2)))
        return CloudReadinessReport(
            syncable_modules=syncable,
            non_syncable_modules=non_syncable,
            migration_requirements=requirements,
            risk_areas=risks,
            conflict_exposure=exposure,
            readiness_score=score,
        )

    def _collection_records(self) -> List[CloudRecord]:
        records: List[CloudRecord] = []
        for index, item in enumerate(self.collection_items, 1):
            payload = {
                "id": _text(getattr(item, "id", "") or getattr(item, "coin_id", "")),
                "country": _text(getattr(item, "country", "")),
                "denomination": _text(getattr(item, "denomination", "")),
                "year": _text(getattr(item, "year", "")),
                "grade": _text(getattr(item, "grade", "")),
                "notes": _text(getattr(item, "notes", "") or getattr(item, "comments", "")),
                "estimated_value": _money(getattr(item, "estimated_value", 0)),
            }
            records.append(CloudRecord(
                record_id=_record_id(MODULE_COLLECTION, f"item-{index}", payload["id"], payload),
                module=MODULE_COLLECTION,
                record_type="collection_item",
                summary=_item_label(item),
                content_hash=_hash(payload),
                metadata=payload,
            ))
        return records

    def _want_list_records(self) -> List[CloudRecord]:
        records: List[CloudRecord] = []
        for index, intent in enumerate(self.want_list_intents, 1):
            payload = intent.to_dict() if hasattr(intent, "to_dict") else dict(getattr(intent, "__dict__", {}))
            records.append(CloudRecord(
                record_id=_record_id(MODULE_WANT_LIST, f"want-{index}", payload.get("legacy_id") or payload.get("target_coin"), payload),
                module=MODULE_WANT_LIST,
                record_type="want_list_intent",
                summary=_text(payload.get("target_coin") or payload.get("coin_label") or f"WANT_LIST intent {index}"),
                content_hash=_hash(payload),
                metadata=payload,
            ))
        return records

    def _mobile_entry_records(self) -> List[CloudRecord]:
        records: List[CloudRecord] = []
        for report_index, report in enumerate(self.mobile_entry_reports, 1):
            for index, candidate in enumerate(getattr(report, "candidates", []) or [], 1):
                payload = candidate.to_dict() if hasattr(candidate, "to_dict") else dict(getattr(candidate, "__dict__", {}))
                records.append(CloudRecord(
                    record_id=_record_id(MODULE_MOBILE_ENTRY, f"entry-{report_index}-{index}", payload.get("candidate_id"), payload),
                    module=MODULE_MOBILE_ENTRY,
                    record_type="entry_candidate",
                    summary=_text(payload.get("title") or f"Mobile entry candidate {index}"),
                    content_hash=_hash(payload),
                    sync_status="REVIEW_ONLY",
                    metadata=payload,
                ))
        return records

    def _workflow_records(self) -> List[CloudRecord]:
        records: List[CloudRecord] = []
        for index, report in enumerate(self.workflow_completion_reports, 1):
            session = getattr(report, "session", None)
            payload = session.to_dict() if hasattr(session, "to_dict") else report.to_dict() if hasattr(report, "to_dict") else dict(getattr(report, "__dict__", {}))
            records.append(CloudRecord(
                record_id=_record_id(MODULE_WORKFLOW, f"workflow-{index}", payload.get("session_id"), payload),
                module=MODULE_WORKFLOW,
                record_type="workflow_session",
                summary=_text(payload.get("subject") or payload.get("session_id") or f"Workflow session {index}"),
                content_hash=_hash(payload),
                sync_status="REVIEW_ONLY",
                metadata=payload,
            ))
        return records

    def _mobile_companion_records(self) -> List[CloudRecord]:
        records: List[CloudRecord] = []
        for index, report in enumerate(self.mobile_companion_reports, 1):
            payload = report.to_dict() if hasattr(report, "to_dict") else dict(getattr(report, "__dict__", {}))
            session = payload.get("session", {}) if isinstance(payload.get("session"), dict) else {}
            records.append(CloudRecord(
                record_id=_record_id(MODULE_MOBILE_COMPANION, f"mobile-{index}", session.get("session_id"), payload),
                module=MODULE_MOBILE_COMPANION,
                record_type="mobile_companion_report",
                summary=_text(session.get("workflow_type") or f"Mobile companion report {index}"),
                content_hash=_hash(payload),
                sync_status="REVIEW_ONLY",
                metadata=payload,
            ))
        return records

    def _settings_records(self) -> List[CloudRecord]:
        if not self.settings:
            return []
        payload = dict(self.settings)
        return [CloudRecord(
            record_id="settings:local-preferences",
            module=MODULE_SETTINGS,
            record_type="settings",
            summary="Local app preferences",
            content_hash=_hash(payload),
            sync_status="REVIEW_ONLY",
            metadata=payload,
        )]

    def _collection_metrics(self) -> Dict[str, Any]:
        intelligence = CollectionIntelligenceEngine(self.collection_items)
        countries = {_text(getattr(item, "country", "")) for item in self.collection_items if _text(getattr(item, "country", ""))}
        denominations = {_text(getattr(item, "denomination", "")) for item in self.collection_items if _text(getattr(item, "denomination", ""))}
        years = {_text(getattr(item, "year", "")) for item in self.collection_items if _text(getattr(item, "year", ""))}
        return {
            "collection_items": len(self.collection_items),
            "countries": len(countries),
            "denominations": len(denominations),
            "years": len(years),
            "duplicate_groups": len(intelligence.detect_duplicates()),
            "upgrade_candidates": len(intelligence.detect_upgrade_candidates()),
            "want_list_intents": len(self.want_list_intents),
        }

    def _portfolio_metrics(self) -> Dict[str, Any]:
        try:
            report = PortfolioPerformanceEngine(self.collection_items, self.want_list_intents).generate_report()
            return {
                "health_score": report.health_score.score,
                "estimated_collection_value": report.growth_report.estimated_collection_value,
                "silver_holdings": report.growth_report.silver_holdings,
                "newfoundland_count": report.growth_report.newfoundland_count,
                "recommended_focus_count": len(report.recommended_focus_areas),
            }
        except Exception as exc:
            return {"portfolio_status": "unavailable", "portfolio_warning": _text(exc)}

    def _workflow_metrics(self) -> Dict[str, Any]:
        sessions = [getattr(report, "session", None) for report in self.workflow_completion_reports]
        sessions = [session for session in sessions if session is not None]
        return {
            "workflow_reports": len(self.workflow_completion_reports),
            "workflow_sessions": len(sessions),
            "completed_workflows": sum(1 for session in sessions if _text(getattr(session, "status", "")) == "COMPLETE"),
            "review_escalations": sum(int(getattr(session, "review_escalation_count", 0) or 0) for session in sessions),
            "mobile_entry_reports": len(self.mobile_entry_reports),
            "mobile_companion_reports": len(self.mobile_companion_reports),
        }

    def _conflict(self, source: CloudRecord, destination: CloudRecord) -> CloudConflict:
        if source.module == MODULE_COLLECTION:
            conflict_type = CONFLICT_COLLECTION
        elif source.module == MODULE_WORKFLOW:
            conflict_type = CONFLICT_WORKFLOW
        elif source.module == MODULE_SETTINGS:
            conflict_type = CONFLICT_SETTINGS
        else:
            conflict_type = CONFLICT_RECORD
        return CloudConflict(
            conflict_id=f"conflict-{_hash(source.record_id + destination.content_hash)[:12]}",
            conflict_type=conflict_type,
            record_id=source.record_id,
            source_summary=source.summary,
            destination_summary=destination.summary,
            recommendation="Compare both local versions and choose manually before any future sync.",
            severity="REVIEW",
            metadata={"source_hash": source.content_hash, "destination_hash": destination.content_hash},
        )

    def _merge_candidates(self, source: Sequence[CloudRecord], destination: Sequence[CloudRecord]) -> List[Dict[str, Any]]:
        source_by_summary = {record.summary.lower(): record for record in source if record.summary}
        candidates: List[Dict[str, Any]] = []
        for record in destination:
            key = record.summary.lower()
            source_record = source_by_summary.get(key)
            if source_record and source_record.record_id != record.record_id:
                candidates.append({
                    "record_id": source_record.record_id,
                    "destination_record_id": record.record_id,
                    "summary": record.summary,
                    "reason": "Matching summary with different record identifiers; manual merge review required",
                })
        return candidates
