"""Offline Sync & Backup planning for Collector Companion.

This module builds on Collector Cloud Foundation snapshots. It creates local
backup archives, restore plans, backup history, synchronization simulations,
conflict reports, and rollback plans without using a network, cloud provider,
credentials, automatic conflict resolution, automatic restore, or collection
mutation.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from collector_cloud import (
    CloudCollectionSnapshot,
    CloudConflict,
    CloudSyncPlan,
    CollectorCloud,
)


RECOMMEND_MERGE = "MERGE"
RECOMMEND_REVIEW = "REVIEW"
RECOMMEND_REJECT = "REJECT"

SCOPE_COLLECTION = "collection"
SCOPE_PORTFOLIO = "portfolio"
SCOPE_WATCHLISTS = "watchlists"
SCOPE_WORKFLOW = "workflow"
SCOPE_SETTINGS = "settings"
DEFAULT_SCOPES = [SCOPE_COLLECTION, SCOPE_PORTFOLIO, SCOPE_WATCHLISTS, SCOPE_WORKFLOW, SCOPE_SETTINGS]


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


def _checksum(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _module_from_record_id(record_id: str) -> str:
    return _text(record_id).split(":", 1)[0] if ":" in _text(record_id) else "unknown"


@dataclass
class BackupArchive:
    """Local backup archive model generated from a cloud snapshot."""

    archive_id: str
    source_snapshot: CloudCollectionSnapshot
    version: str = "v6.1"
    backup_scope: List[str] = field(default_factory=lambda: list(DEFAULT_SCOPES))
    checksum: str = ""
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.source_snapshot, CloudCollectionSnapshot):
            self.source_snapshot = CloudCollectionSnapshot(**self.source_snapshot)
        self.archive_id = _text(self.archive_id) or f"backup-archive-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.version = _text(self.version) or "v6.1"
        self.backup_scope = _dedupe(self.backup_scope or DEFAULT_SCOPES)
        self.created_at = _text(self.created_at) or _now_iso()
        self.metadata = dict(self.metadata or {})
        self.metadata.setdefault("network_required", "NO")
        self.metadata.setdefault("cloud_provider", "NONE")
        self.metadata.setdefault("automatic_restore", "NO")
        if not self.checksum:
            self.checksum = _checksum({
                "snapshot_hash": self.source_snapshot.content_hash,
                "scope": self.backup_scope,
                "version": self.version,
                "metadata": self.metadata,
            })
        self.warnings = _dedupe([*self.warnings, "Offline backup archive only; no files restored automatically"])

    @property
    def record_count(self) -> int:
        return self.source_snapshot.record_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "archive_id": self.archive_id,
            "version": self.version,
            "created_at": self.created_at,
            "source_snapshot_id": self.source_snapshot.snapshot_id,
            "source_snapshot_hash": self.source_snapshot.content_hash,
            "record_count": self.record_count,
            "checksum": self.checksum,
            "backup_scope": list(self.backup_scope),
            "metadata": dict(self.metadata),
            "warnings": "; ".join(self.warnings),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Sync & Backup Archive",
            "",
            f"- Archive: {self.archive_id}",
            f"- Version: {self.version}",
            f"- Created: {self.created_at}",
            f"- Source snapshot: {self.source_snapshot.snapshot_id}",
            f"- Records: {self.record_count}",
            f"- Checksum: {self.checksum}",
            "- Internet synchronization performed: NO",
            "- Automatic restore performed: NO",
            "",
            "## Backup Scope",
            "",
        ]
        lines.extend(f"- {scope}" for scope in self.backup_scope)
        lines.extend(["", "## Metadata", ""])
        lines.extend(f"- {key}: {value}" for key, value in sorted(self.metadata.items()))
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
            writer.writerow(["section", "value"])
            for key, value in self.to_dict().items():
                if isinstance(value, list):
                    for item in value:
                        writer.writerow([key, item])
                elif isinstance(value, dict):
                    for sub_key, sub_value in sorted(value.items()):
                        writer.writerow([f"{key}.{sub_key}", sub_value])
                else:
                    writer.writerow([key, value])
        return True


@dataclass
class SyncConflictReport:
    """Conflict report for restore and sync simulations."""

    report_id: str
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""
    duplicate_entries: List[str] = field(default_factory=list)
    collection_mismatches: List[str] = field(default_factory=list)
    workflow_mismatches: List[str] = field(default_factory=list)
    settings_mismatches: List[str] = field(default_factory=list)
    snapshot_divergence: List[str] = field(default_factory=list)
    backup_incompatibilities: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.report_id = _text(self.report_id) or f"sync-conflict-report-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.conflicts = [dict(conflict) for conflict in self.conflicts]
        self.duplicate_entries = _dedupe(self.duplicate_entries)
        self.collection_mismatches = _dedupe(self.collection_mismatches)
        self.workflow_mismatches = _dedupe(self.workflow_mismatches)
        self.settings_mismatches = _dedupe(self.settings_mismatches)
        self.snapshot_divergence = _dedupe(self.snapshot_divergence)
        self.backup_incompatibilities = _dedupe(self.backup_incompatibilities)
        self.recommendations = _dedupe(self.recommendations or self._default_recommendations())

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    def _default_recommendations(self) -> List[str]:
        if self.conflicts or self.collection_mismatches or self.workflow_mismatches or self.settings_mismatches:
            return [RECOMMEND_REVIEW]
        if self.duplicate_entries:
            return [RECOMMEND_MERGE]
        if self.backup_incompatibilities:
            return [RECOMMEND_REJECT, RECOMMEND_REVIEW]
        return [RECOMMEND_MERGE]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "conflict_count": self.conflict_count,
            "conflicts": list(self.conflicts),
            "duplicate_entries": list(self.duplicate_entries),
            "collection_mismatches": list(self.collection_mismatches),
            "workflow_mismatches": list(self.workflow_mismatches),
            "settings_mismatches": list(self.settings_mismatches),
            "snapshot_divergence": list(self.snapshot_divergence),
            "backup_incompatibilities": list(self.backup_incompatibilities),
            "recommendations": list(self.recommendations),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Sync Conflict Report",
            "",
            f"- Report: {self.report_id}",
            f"- Generated: {self.generated_at}",
            f"- Conflicts: {self.conflict_count}",
            f"- Recommendations: {'; '.join(self.recommendations)}",
            "- Automatic conflict resolution: NO",
            "",
        ]
        sections = [
            ("Duplicate Entries", self.duplicate_entries),
            ("Collection Mismatches", self.collection_mismatches),
            ("Workflow Mismatches", self.workflow_mismatches),
            ("Settings Mismatches", self.settings_mismatches),
            ("Snapshot Divergence", self.snapshot_divergence),
            ("Backup Incompatibilities", self.backup_incompatibilities),
        ]
        for title, values in sections:
            lines.extend([f"## {title}", ""])
            lines.extend(f"- {value}" for value in values) if values else lines.append("- None")
            lines.append("")
        lines.extend(["## Conflict Details", ""])
        if self.conflicts:
            for conflict in self.conflicts:
                lines.append(f"- {conflict.get('record_id', 'unknown')}: {conflict.get('recommendation', RECOMMEND_REVIEW)}")
        else:
            lines.append("- None")
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "record_id", "value", "recommendation"])
            for conflict in self.conflicts:
                writer.writerow(["conflict", conflict.get("record_id", ""), conflict.get("summary", ""), conflict.get("recommendation", RECOMMEND_REVIEW)])
            for section, values in [
                ("duplicate_entry", self.duplicate_entries),
                ("collection_mismatch", self.collection_mismatches),
                ("workflow_mismatch", self.workflow_mismatches),
                ("settings_mismatch", self.settings_mismatches),
                ("snapshot_divergence", self.snapshot_divergence),
                ("backup_incompatibility", self.backup_incompatibilities),
            ]:
                for value in values:
                    writer.writerow([section, "", value, "; ".join(self.recommendations)])
        return True


@dataclass
class RestorePlan:
    """Preview-only plan for restoring from a backup archive."""

    plan_id: str
    archive: BackupArchive
    current_snapshot: CloudCollectionSnapshot
    affected_modules: List[str] = field(default_factory=list)
    affected_records: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    validation_results: List[str] = field(default_factory=list)
    rollback_options: List[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.archive, BackupArchive):
            self.archive = BackupArchive(**self.archive)
        if not isinstance(self.current_snapshot, CloudCollectionSnapshot):
            self.current_snapshot = CloudCollectionSnapshot(**self.current_snapshot)
        self.plan_id = _text(self.plan_id) or f"restore-plan-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.affected_modules = _dedupe(self.affected_modules)
        self.affected_records = _dedupe(self.affected_records)
        self.warnings = _dedupe([*self.warnings, "Preview only; existing data will not be overwritten automatically"])
        self.conflicts = [dict(conflict) for conflict in self.conflicts]
        self.validation_results = _dedupe(self.validation_results)
        self.rollback_options = _dedupe(self.rollback_options)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "archive_id": self.archive.archive_id,
            "current_snapshot_id": self.current_snapshot.snapshot_id,
            "generated_at": self.generated_at,
            "affected_modules": list(self.affected_modules),
            "affected_records": list(self.affected_records),
            "warnings": list(self.warnings),
            "conflicts": list(self.conflicts),
            "validation_results": list(self.validation_results),
            "rollback_options": list(self.rollback_options),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Restore Plan",
            "",
            f"- Plan: {self.plan_id}",
            f"- Archive: {self.archive.archive_id}",
            f"- Current snapshot: {self.current_snapshot.snapshot_id}",
            f"- Affected modules: {len(self.affected_modules)}",
            f"- Affected records: {len(self.affected_records)}",
            "- Restore executed: NO",
            "",
        ]
        for title, values in [
            ("Affected Modules", self.affected_modules),
            ("Affected Records", self.affected_records),
            ("Validation Results", self.validation_results),
            ("Warnings", self.warnings),
            ("Rollback Options", self.rollback_options),
        ]:
            lines.extend([f"## {title}", ""])
            lines.extend(f"- {value}" for value in values) if values else lines.append("- None")
            lines.append("")
        lines.extend(["## Conflicts", ""])
        if self.conflicts:
            for conflict in self.conflicts:
                lines.append(f"- {conflict.get('record_id', 'unknown')}: {conflict.get('recommendation', RECOMMEND_REVIEW)}")
        else:
            lines.append("- None")
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "value"])
            for section, values in [
                ("affected_module", self.affected_modules),
                ("affected_record", self.affected_records),
                ("validation", self.validation_results),
                ("warning", self.warnings),
                ("rollback_option", self.rollback_options),
            ]:
                for value in values:
                    writer.writerow([section, value])
            for conflict in self.conflicts:
                writer.writerow(["conflict", conflict.get("record_id", "")])
        return True


@dataclass
class BackupHistory:
    """Timeline and comparison view over backup archives and snapshots."""

    history_id: str
    archives: List[BackupArchive] = field(default_factory=list)
    generated_at: str = ""
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    snapshot_comparisons: List[Dict[str, Any]] = field(default_factory=list)
    collection_delta: Dict[str, Any] = field(default_factory=dict)
    portfolio_delta: Dict[str, Any] = field(default_factory=dict)
    workflow_delta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.history_id = _text(self.history_id) or f"backup-history-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.archives = [archive if isinstance(archive, BackupArchive) else BackupArchive(**archive) for archive in self.archives]
        self.timeline = list(self.timeline or self._timeline())
        self.snapshot_comparisons = list(self.snapshot_comparisons or self._comparisons())
        self.collection_delta = dict(self.collection_delta or self._delta("collection_metrics"))
        self.portfolio_delta = dict(self.portfolio_delta or self._delta("portfolio_metrics"))
        self.workflow_delta = dict(self.workflow_delta or self._delta("workflow_metrics"))

    def _timeline(self) -> List[Dict[str, Any]]:
        return [
            {
                "archive_id": archive.archive_id,
                "created_at": archive.created_at,
                "snapshot_id": archive.source_snapshot.snapshot_id,
                "record_count": archive.record_count,
                "checksum": archive.checksum,
            }
            for archive in sorted(self.archives, key=lambda item: item.created_at)
        ]

    def _comparisons(self) -> List[Dict[str, Any]]:
        comparisons: List[Dict[str, Any]] = []
        sorted_archives = sorted(self.archives, key=lambda item: item.created_at)
        for previous, current in zip(sorted_archives, sorted_archives[1:]):
            diff = current.source_snapshot.compare_to(previous.source_snapshot)
            comparisons.append({
                "from_archive": previous.archive_id,
                "to_archive": current.archive_id,
                "added_records": len(diff["added_record_ids"]),
                "removed_records": len(diff["removed_record_ids"]),
                "changed_records": len(diff["changed_record_ids"]),
            })
        return comparisons

    def _delta(self, metric_name: str) -> Dict[str, Any]:
        if len(self.archives) < 2:
            return {}
        sorted_archives = sorted(self.archives, key=lambda item: item.created_at)
        first = getattr(sorted_archives[0].source_snapshot, metric_name)
        last = getattr(sorted_archives[-1].source_snapshot, metric_name)
        delta: Dict[str, Any] = {}
        for key in set(first) | set(last):
            first_value = first.get(key, 0)
            last_value = last.get(key, 0)
            if isinstance(first_value, (int, float)) and isinstance(last_value, (int, float)):
                delta[key] = last_value - first_value
            elif first_value != last_value:
                delta[key] = f"{first_value} -> {last_value}"
        return delta

    def to_dict(self) -> Dict[str, Any]:
        return {
            "history_id": self.history_id,
            "generated_at": self.generated_at,
            "archive_count": len(self.archives),
            "timeline": list(self.timeline),
            "snapshot_comparisons": list(self.snapshot_comparisons),
            "collection_delta": dict(self.collection_delta),
            "portfolio_delta": dict(self.portfolio_delta),
            "workflow_delta": dict(self.workflow_delta),
        }

    def format_markdown(self) -> str:
        lines = ["# Backup History", "", f"- History: {self.history_id}", f"- Archives: {len(self.archives)}", ""]
        lines.extend(["## Timeline", ""])
        if self.timeline:
            for row in self.timeline:
                lines.append(f"- {row['created_at']}: {row['archive_id']} ({row['record_count']} records)")
        else:
            lines.append("- No archives available.")
        lines.extend(["", "## Snapshot Comparisons", ""])
        if self.snapshot_comparisons:
            for row in self.snapshot_comparisons:
                lines.append(f"- {row['from_archive']} -> {row['to_archive']}: +{row['added_records']} / -{row['removed_records']} / changed {row['changed_records']}")
        else:
            lines.append("- No comparisons available.")
        for title, delta in [("Collection Delta", self.collection_delta), ("Portfolio Delta", self.portfolio_delta), ("Workflow Delta", self.workflow_delta)]:
            lines.extend(["", f"## {title}", ""])
            lines.extend(f"- {key}: {value}" for key, value in sorted(delta.items())) if delta else lines.append("- None")
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "key", "value", "detail"])
            for row in self.timeline:
                writer.writerow(["timeline", row["archive_id"], row["record_count"], row["created_at"]])
            for row in self.snapshot_comparisons:
                writer.writerow(["comparison", f"{row['from_archive']}->{row['to_archive']}", row["changed_records"], f"added={row['added_records']}; removed={row['removed_records']}"])
            for section, delta in [("collection_delta", self.collection_delta), ("portfolio_delta", self.portfolio_delta), ("workflow_delta", self.workflow_delta)]:
                for key, value in sorted(delta.items()):
                    writer.writerow([section, key, value, ""])
        return True


@dataclass
class RollbackPlan:
    """Preview-only rollback plan for backup, restore, or sync scenarios."""

    plan_id: str
    rollback_type: str
    rollback_targets: List[str] = field(default_factory=list)
    rollback_scope: List[str] = field(default_factory=list)
    rollback_risks: List[str] = field(default_factory=list)
    rollback_recommendations: List[str] = field(default_factory=list)
    generated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.plan_id = _text(self.plan_id) or f"rollback-plan-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.rollback_type = _text(self.rollback_type) or "backup"
        self.rollback_targets = _dedupe(self.rollback_targets)
        self.rollback_scope = _dedupe(self.rollback_scope)
        self.rollback_risks = _dedupe(self.rollback_risks)
        self.rollback_recommendations = _dedupe(self.rollback_recommendations or ["Review rollback plan manually before any future restore"])
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "rollback_type": self.rollback_type,
            "generated_at": self.generated_at,
            "rollback_targets": list(self.rollback_targets),
            "rollback_scope": list(self.rollback_scope),
            "rollback_risks": list(self.rollback_risks),
            "rollback_recommendations": list(self.rollback_recommendations),
            "metadata": dict(self.metadata),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Rollback Plan",
            "",
            f"- Plan: {self.plan_id}",
            f"- Type: {self.rollback_type}",
            f"- Generated: {self.generated_at}",
            "- Rollback executed: NO",
            "",
        ]
        for title, values in [
            ("Rollback Targets", self.rollback_targets),
            ("Rollback Scope", self.rollback_scope),
            ("Rollback Risks", self.rollback_risks),
            ("Rollback Recommendations", self.rollback_recommendations),
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
            for key, value in self.to_dict().items():
                if isinstance(value, list):
                    for item in value:
                        writer.writerow([key, item])
                elif isinstance(value, dict):
                    for sub_key, sub_value in sorted(value.items()):
                        writer.writerow([f"{key}.{sub_key}", sub_value])
                else:
                    writer.writerow([key, value])
        return True


@dataclass
class SyncSimulation:
    """Preview-only synchronization simulation between two snapshots."""

    simulation_id: str
    device_a_snapshot: CloudCollectionSnapshot
    device_b_snapshot: CloudCollectionSnapshot
    sync_plan: CloudSyncPlan
    conflict_report: SyncConflictReport
    merge_preview: List[str] = field(default_factory=list)
    generated_at: str = ""
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.device_a_snapshot, CloudCollectionSnapshot):
            self.device_a_snapshot = CloudCollectionSnapshot(**self.device_a_snapshot)
        if not isinstance(self.device_b_snapshot, CloudCollectionSnapshot):
            self.device_b_snapshot = CloudCollectionSnapshot(**self.device_b_snapshot)
        if not isinstance(self.sync_plan, CloudSyncPlan):
            self.sync_plan = CloudSyncPlan(**self.sync_plan)
        if not isinstance(self.conflict_report, SyncConflictReport):
            self.conflict_report = SyncConflictReport(**self.conflict_report)
        self.simulation_id = _text(self.simulation_id) or f"sync-simulation-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.merge_preview = _dedupe(self.merge_preview)
        self.warnings = _dedupe([*self.warnings, "Simulation only; no synchronization executed"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "generated_at": self.generated_at,
            "device_a_snapshot_id": self.device_a_snapshot.snapshot_id,
            "device_b_snapshot_id": self.device_b_snapshot.snapshot_id,
            "proposed_change_count": self.sync_plan.proposed_change_count,
            "conflict_count": self.conflict_report.conflict_count,
            "merge_preview": list(self.merge_preview),
            "warnings": list(self.warnings),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Sync Simulation",
            "",
            f"- Simulation: {self.simulation_id}",
            f"- Device A snapshot: {self.device_a_snapshot.snapshot_id}",
            f"- Device B snapshot: {self.device_b_snapshot.snapshot_id}",
            f"- Proposed changes: {self.sync_plan.proposed_change_count}",
            f"- Conflicts: {self.conflict_report.conflict_count}",
            "- Synchronization executed: NO",
            "",
            "## Merge Preview",
            "",
        ]
        lines.extend(f"- {item}" for item in self.merge_preview) if self.merge_preview else lines.append("- No merge preview generated.")
        lines.extend(["", "## Conflict Report Summary", ""])
        lines.append(f"- Recommendations: {'; '.join(self.conflict_report.recommendations)}")
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
            writer.writerow(["section", "value"])
            for key, value in self.to_dict().items():
                if isinstance(value, list):
                    for item in value:
                        writer.writerow([key, item])
                else:
                    writer.writerow([key, value])
        return True


class SyncBackupEngine:
    """Create offline backup and sync-planning artifacts."""

    def __init__(
        self,
        collection_items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        workflow_completion_reports: Optional[Iterable[Any]] = None,
        mobile_entry_reports: Optional[Iterable[Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        collector_cloud: Optional[CollectorCloud] = None,
    ):
        self.collector_cloud = collector_cloud or CollectorCloud(
            collection_items=collection_items,
            want_list_intents=want_list_intents,
            workflow_completion_reports=workflow_completion_reports,
            mobile_entry_reports=mobile_entry_reports,
            settings=settings,
        )
        self.archives: List[BackupArchive] = []

    def create_backup_archive(
        self,
        backup_scope: Optional[Iterable[str]] = None,
        version: str = "v6.1",
        source_snapshot: Optional[CloudCollectionSnapshot] = None,
    ) -> BackupArchive:
        snapshot = source_snapshot or self.collector_cloud.create_snapshot("sync-backup-archive")
        archive = BackupArchive(
            archive_id=f"backup-archive-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            version=version,
            source_snapshot=snapshot,
            backup_scope=list(backup_scope or DEFAULT_SCOPES),
            metadata={
                "source_snapshot": snapshot.snapshot_id,
                "backup_scope_count": len(list(backup_scope or DEFAULT_SCOPES)),
                "collection_records": snapshot.module_counts().get("collection", 0),
                "workflow_records": snapshot.module_counts().get("workflow", 0),
                "settings_records": snapshot.module_counts().get("settings", 0),
            },
        )
        self.archives.append(archive)
        return archive

    def plan_restore(self, archive: BackupArchive, current_snapshot: Optional[CloudCollectionSnapshot] = None) -> RestorePlan:
        current = current_snapshot or self.collector_cloud.create_snapshot("restore-current")
        diff = archive.source_snapshot.compare_to(current)
        affected_records = _dedupe([*diff["added_record_ids"], *diff["removed_record_ids"], *diff["changed_record_ids"]])
        affected_modules = _dedupe(_module_from_record_id(record_id) for record_id in affected_records)
        conflict_report = self.create_conflict_report(archive.source_snapshot, current, archive=archive)
        validation = [
            "Archive checksum present" if archive.checksum else "Archive checksum missing",
            "Archive snapshot hash present" if archive.source_snapshot.content_hash else "Archive snapshot hash missing",
            f"Archive records available: {archive.record_count}",
        ]
        rollback_options = [
            f"Create pre-restore archive from current snapshot {current.snapshot_id}",
            f"Rollback target can return to archive {archive.archive_id}",
            "Manual confirmation required before any future restore",
        ]
        return RestorePlan(
            plan_id=f"restore-plan-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            archive=archive,
            current_snapshot=current,
            affected_modules=affected_modules,
            affected_records=affected_records,
            warnings=["Restore planning only; no existing data overwritten"],
            conflicts=conflict_report.conflicts,
            validation_results=validation,
            rollback_options=rollback_options,
        )

    def backup_history(self, archives: Optional[Sequence[BackupArchive]] = None) -> BackupHistory:
        return BackupHistory(
            history_id=f"backup-history-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            archives=list(archives or self.archives),
        )

    def simulate_sync(self, device_a_snapshot: CloudCollectionSnapshot, device_b_snapshot: CloudCollectionSnapshot) -> SyncSimulation:
        sync_plan = self.collector_cloud.create_sync_plan(device_a_snapshot, device_b_snapshot)
        conflict_report = self._conflict_report_from_plan(sync_plan)
        merge_preview = [
            f"{change.get('action')}: {change.get('record_id')} ({change.get('module')})"
            for change in sync_plan.proposed_changes[:20]
        ]
        merge_preview.extend(
            f"Conflict requires {RECOMMEND_REVIEW}: {conflict.get('record_id')}"
            for conflict in conflict_report.conflicts[:10]
        )
        return SyncSimulation(
            simulation_id=f"sync-simulation-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            device_a_snapshot=device_a_snapshot,
            device_b_snapshot=device_b_snapshot,
            sync_plan=sync_plan,
            conflict_report=conflict_report,
            merge_preview=merge_preview,
        )

    def create_conflict_report(
        self,
        source_snapshot: CloudCollectionSnapshot,
        destination_snapshot: CloudCollectionSnapshot,
        archive: Optional[BackupArchive] = None,
    ) -> SyncConflictReport:
        plan = self.collector_cloud.create_sync_plan(source_snapshot, destination_snapshot)
        report = self._conflict_report_from_plan(plan)
        if archive and archive.source_snapshot.content_hash != source_snapshot.content_hash:
            report.backup_incompatibilities.append("Archive snapshot hash differs from supplied source snapshot")
            report.recommendations = _dedupe([*report.recommendations, RECOMMEND_REVIEW])
        if source_snapshot.content_hash != destination_snapshot.content_hash:
            report.snapshot_divergence.append(f"{source_snapshot.snapshot_id} differs from {destination_snapshot.snapshot_id}")
        return report

    def plan_rollback(
        self,
        rollback_type: str,
        archive: Optional[BackupArchive] = None,
        restore_plan: Optional[RestorePlan] = None,
        sync_simulation: Optional[SyncSimulation] = None,
    ) -> RollbackPlan:
        targets: List[str] = []
        scope: List[str] = []
        risks = ["Rollback is preview-only and must be manually reviewed"]
        recommendations = ["Create a fresh backup before any future rollback"]
        metadata: Dict[str, Any] = {}
        if archive:
            targets.append(archive.archive_id)
            scope.extend(archive.backup_scope)
            metadata["archive_checksum"] = archive.checksum
        if restore_plan:
            targets.append(restore_plan.plan_id)
            scope.extend(restore_plan.affected_modules)
            risks.extend(restore_plan.warnings)
            recommendations.extend(restore_plan.rollback_options)
        if sync_simulation:
            targets.append(sync_simulation.simulation_id)
            scope.extend(_module_from_record_id(change.get("record_id", "")) for change in sync_simulation.sync_plan.proposed_changes)
            risks.extend(sync_simulation.warnings)
            recommendations.append("Review sync simulation conflicts before rollback planning")
        return RollbackPlan(
            plan_id=f"rollback-plan-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            rollback_type=rollback_type,
            rollback_targets=targets,
            rollback_scope=scope or DEFAULT_SCOPES,
            rollback_risks=risks,
            rollback_recommendations=recommendations,
            metadata=metadata,
        )

    def _conflict_report_from_plan(self, plan: CloudSyncPlan) -> SyncConflictReport:
        conflict_rows: List[Dict[str, Any]] = []
        collection_mismatches: List[str] = []
        workflow_mismatches: List[str] = []
        settings_mismatches: List[str] = []
        duplicate_entries: List[str] = []
        snapshot_divergence: List[str] = []
        for conflict in plan.conflicts:
            row = conflict.to_dict() if isinstance(conflict, CloudConflict) else dict(conflict)
            row["recommendation"] = RECOMMEND_REVIEW
            conflict_rows.append(row)
            record_id = row.get("record_id", "")
            module = _module_from_record_id(record_id)
            if module == "collection":
                collection_mismatches.append(record_id)
            elif module == "workflow":
                workflow_mismatches.append(record_id)
            elif module == "settings":
                settings_mismatches.append(record_id)
        for candidate in plan.merge_candidates:
            duplicate_entries.append(candidate.get("summary", "") or candidate.get("record_id", ""))
        if plan.source_snapshot.content_hash != plan.destination_snapshot.content_hash:
            snapshot_divergence.append(f"{plan.source_snapshot.snapshot_id} -> {plan.destination_snapshot.snapshot_id}")
        recommendations = [RECOMMEND_REVIEW if conflict_rows else RECOMMEND_MERGE]
        if duplicate_entries:
            recommendations.append(RECOMMEND_MERGE)
        return SyncConflictReport(
            report_id=f"sync-conflict-report-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            conflicts=conflict_rows,
            duplicate_entries=duplicate_entries,
            collection_mismatches=collection_mismatches,
            workflow_mismatches=workflow_mismatches,
            settings_mismatches=settings_mismatches,
            snapshot_divergence=snapshot_divergence,
            backup_incompatibilities=[],
            recommendations=recommendations,
        )
