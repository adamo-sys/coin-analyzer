"""Unified Collector Home Dashboard.

This module surfaces existing collector workflow, safety, review, progress, and
shopping signals in one deterministic report. It does not create recommendation
logic, mutate collection data, run OCR, scrape prices, or perform background
work.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from backup_manager import BackupManager, DataSafetyValidator
from collection_dashboard import CollectionDashboard
from collection_integrity import CollectionIntegrityAudit
from collection_snapshot import CollectionSnapshotManager
from collector_workflows import CollectorDailySummary, CollectorWorkflowEngine
from market_awareness import MarketAwarenessEngine
from ocr_validation import OCRValidationEngine
from photo_vault import PhotoRecord, PhotoVaultIntegrityAudit
from series_tracker import SeriesTracker
from smart_shopping_assistant import ShoppingCandidate, SmartShoppingAssistant


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _clean_list(values: Iterable[Any], limit: int = 0) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            cleaned.append(text)
            if limit and len(cleaned) >= limit:
                break
    return cleaned


def _severity_value(severity: Any) -> str:
    if isinstance(severity, HomeStatusSeverity):
        return severity.value
    text = str(severity or "INFO").strip().upper()
    return text if text in HomeStatusSeverity.__members__ else "INFO"


class HomeStatusSeverity(Enum):
    """Collector-facing severity for home dashboard sections."""

    OK = "OK"
    INFO = "INFO"
    WARNING = "WARNING"
    ACTION_REQUIRED = "ACTION_REQUIRED"


SEVERITY_RANK = {
    HomeStatusSeverity.ACTION_REQUIRED.value: 4,
    HomeStatusSeverity.WARNING.value: 3,
    HomeStatusSeverity.INFO.value: 2,
    HomeStatusSeverity.OK.value: 1,
}


@dataclass
class DailyCollectorAction:
    """One ranked action surfaced by the Collector Home Dashboard."""

    title: str
    detail: str = ""
    urgency: int = 0
    severity: Any = HomeStatusSeverity.INFO
    source: str = ""
    action_id: str = ""
    acknowledged: bool = False

    def __post_init__(self) -> None:
        self.title = str(self.title or "").strip()
        self.detail = str(self.detail or "").strip()
        self.urgency = int(self.urgency or 0)
        self.severity = _severity_value(self.severity)
        self.source = str(self.source or "").strip()
        self.action_id = self.action_id or self._default_action_id()
        self.acknowledged = bool(self.acknowledged)

    def _default_action_id(self) -> str:
        seed = f"{self.source}:{self.title}".strip(":").lower()
        return "".join(char if char.isalnum() else "_" for char in seed).strip("_")

    @property
    def rank_key(self) -> tuple:
        return (-SEVERITY_RANK.get(self.severity, 0), -self.urgency, self.title.lower())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "detail": self.detail,
            "urgency": self.urgency,
            "severity": self.severity,
            "source": self.source,
            "action_id": self.action_id,
            "acknowledged": self.acknowledged,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "DailyCollectorAction":
        return cls(
            title=str(payload.get("title") or ""),
            detail=str(payload.get("detail") or ""),
            urgency=int(payload.get("urgency") or 0),
            severity=str(payload.get("severity") or "INFO"),
            source=str(payload.get("source") or ""),
            action_id=str(payload.get("action_id") or ""),
            acknowledged=bool(payload.get("acknowledged", False)),
        )


@dataclass
class HomeStatusCard:
    """Simple dashboard section for a collector status area."""

    title: str
    severity: Any
    headline: str
    details: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    actions: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = str(self.title or "").strip()
        self.severity = _severity_value(self.severity)
        self.headline = str(self.headline or "").strip()
        self.details = _clean_list(self.details)
        self.metrics = dict(self.metrics or {})
        self.actions = _clean_list(self.actions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "severity": self.severity,
            "headline": self.headline,
            "details": list(self.details),
            "metrics": dict(self.metrics),
            "actions": list(self.actions),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "HomeStatusCard":
        return cls(
            title=str(payload.get("title") or ""),
            severity=str(payload.get("severity") or "INFO"),
            headline=str(payload.get("headline") or ""),
            details=list(payload.get("details") or []),
            metrics=dict(payload.get("metrics") or {}),
            actions=list(payload.get("actions") or []),
        )


@dataclass
class CollectorHomeReport:
    """Collector-facing daily home report."""

    summary_headline: str
    status_cards: List[HomeStatusCard] = field(default_factory=list)
    daily_actions: List[DailyCollectorAction] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    top_opportunities: List[str] = field(default_factory=list)
    recent_progress: List[str] = field(default_factory=list)
    workflow_statuses: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()
        self.status_cards = [
            card if isinstance(card, HomeStatusCard) else HomeStatusCard.from_dict(card)
            for card in self.status_cards
        ]
        self.daily_actions = sorted(
            [
                action if isinstance(action, DailyCollectorAction) else DailyCollectorAction.from_dict(action)
                for action in self.daily_actions
            ],
            key=lambda action: action.rank_key,
        )
        self.warnings = _clean_list(self.warnings)
        self.top_opportunities = _clean_list(self.top_opportunities)
        self.recent_progress = _clean_list(self.recent_progress)
        self.workflow_statuses = [dict(status) for status in self.workflow_statuses or []]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_headline": self.summary_headline,
            "status_cards": [card.to_dict() for card in self.status_cards],
            "daily_actions": [action.to_dict() for action in self.daily_actions],
            "warnings": list(self.warnings),
            "top_opportunities": list(self.top_opportunities),
            "recent_progress": list(self.recent_progress),
            "workflow_statuses": [dict(status) for status in self.workflow_statuses],
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CollectorHomeReport":
        return cls(
            summary_headline=str(payload.get("summary_headline") or ""),
            status_cards=[HomeStatusCard.from_dict(row) for row in payload.get("status_cards", [])],
            daily_actions=[DailyCollectorAction.from_dict(row) for row in payload.get("daily_actions", [])],
            warnings=list(payload.get("warnings") or []),
            top_opportunities=list(payload.get("top_opportunities") or []),
            recent_progress=list(payload.get("recent_progress") or []),
            workflow_statuses=[dict(row) for row in payload.get("workflow_statuses", [])],
            generated_at=str(payload.get("generated_at") or ""),
        )

    def format_markdown(self) -> str:
        lines = [
            "# Collector Home Dashboard",
            "",
            f"- Headline: {self.summary_headline}",
            f"- Generated: {self.generated_at}",
            "",
            "## Status Cards",
            "",
        ]
        if self.status_cards:
            for card in self.status_cards:
                lines.append(f"### {card.title}")
                lines.append("")
                lines.append(f"- Severity: {card.severity}")
                lines.append(f"- Headline: {card.headline}")
                for key, value in card.metrics.items():
                    lines.append(f"- {key}: {value}")
                if card.details:
                    lines.append("- Details: " + "; ".join(card.details))
                if card.actions:
                    lines.append("- Actions: " + "; ".join(card.actions))
                lines.append("")
        else:
            lines.append("- No status cards generated.")
            lines.append("")
        lines.extend(["## Daily Actions", ""])
        if self.daily_actions:
            for index, action in enumerate(self.daily_actions, 1):
                detail = f": {action.detail}" if action.detail else ""
                suffix = " (acknowledged)" if action.acknowledged else ""
                lines.append(f"{index}. [{action.severity}] {action.title}{detail}{suffix}")
        else:
            lines.append("- No daily actions.")
        lines.extend(["", "## Top Opportunities", ""])
        lines.extend(f"- {item}" for item in self.top_opportunities) if self.top_opportunities else lines.append("- No opportunities surfaced.")
        lines.extend(["", "## Recent Progress", ""])
        lines.extend(f"- {item}" for item in self.recent_progress) if self.recent_progress else lines.append("- No recent progress available.")
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in self.warnings) if self.warnings else lines.append("- No warnings.")
        return "\n".join(lines).strip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["section", "name", "severity", "detail", "value"])
            writer.writeheader()
            writer.writerow({"section": "Summary", "name": "Headline", "severity": "", "detail": self.summary_headline, "value": self.generated_at})
            for card in self.status_cards:
                writer.writerow({"section": "Status Card", "name": card.title, "severity": card.severity, "detail": card.headline, "value": ""})
                for key, value in card.metrics.items():
                    writer.writerow({"section": card.title, "name": key, "severity": card.severity, "detail": "", "value": value})
            for action in self.daily_actions:
                writer.writerow({"section": "Daily Action", "name": action.title, "severity": action.severity, "detail": action.detail, "value": action.urgency})
            for item in self.top_opportunities:
                writer.writerow({"section": "Top Opportunity", "name": item, "severity": "", "detail": "", "value": ""})
            for item in self.recent_progress:
                writer.writerow({"section": "Recent Progress", "name": item, "severity": "", "detail": "", "value": ""})
            for item in self.warnings:
                writer.writerow({"section": "Warning", "name": item, "severity": "WARNING", "detail": "", "value": ""})
        return True


class CollectorHomeDashboard:
    """Aggregate key collector status from existing systems."""

    def __init__(
        self,
        collection_items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        photo_records: Optional[Iterable[PhotoRecord]] = None,
        photo_candidates: Optional[Iterable[Any]] = None,
        shopping_candidates: Optional[Iterable[ShoppingCandidate]] = None,
        ocr_reports: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        snapshot_manager: Optional[CollectionSnapshotManager] = None,
        backup_manager: Optional[BackupManager] = None,
        workflow_statuses: Optional[Iterable[Dict[str, Any]]] = None,
        acknowledged_action_ids: Optional[Iterable[str]] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.photo_records = list(photo_records or [])
        self.photo_candidates = list(photo_candidates or [])
        self.shopping_candidates = list(shopping_candidates or [])
        self.ocr_reports = list(ocr_reports or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()
        self.snapshot_manager = snapshot_manager or CollectionSnapshotManager()
        self.backup_manager = backup_manager or BackupManager()
        self.workflow_statuses = [dict(status) for status in workflow_statuses or []]
        self.acknowledged_action_ids = set(str(action_id) for action_id in acknowledged_action_ids or [])

    def generate_report(self) -> CollectorHomeReport:
        dashboard_data = CollectionDashboard(
            self.collection_items,
            self.want_list_intents,
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
            shopping_candidates=self.shopping_candidates,
        ).generate_dashboard()
        daily_summary = self._daily_summary()
        integrity_report = CollectionIntegrityAudit(
            self.collection_items,
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
            shopping_candidates=self.shopping_candidates,
        ).run()
        data_safety_report = DataSafetyValidator(
            self.backup_manager.persistence_manager,
            self.backup_manager.backup_dir,
        ).validate()
        photo_report = PhotoVaultIntegrityAudit(
            self.photo_records,
            self.collection_items,
            self.photo_candidates,
        ).run()
        snapshot_report = self._snapshot_report()
        shopping_report = SmartShoppingAssistant(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).generate_report(
            self.shopping_candidates,
            include_want_list_targets=bool(self.want_list_intents),
            limit=5,
        )
        series_reports = SeriesTracker(self.collection_items, self.want_list_intents).generate_reports()
        ocr_low_trust = self._low_trust_ocr_count()
        status_cards = [
            self._collection_health_card(dashboard_data, integrity_report),
            self._acquisition_focus_card(shopping_report, dashboard_data),
            self._review_queue_card(ocr_low_trust, photo_report),
            self._data_safety_card(data_safety_report),
            self._progress_card(snapshot_report, series_reports, photo_report),
        ]
        actions = self._daily_actions(
            daily_summary,
            integrity_report,
            data_safety_report,
            photo_report,
            snapshot_report,
            shopping_report,
            ocr_low_trust,
        )
        warnings = self._warnings(status_cards, integrity_report, data_safety_report)
        return CollectorHomeReport(
            summary_headline=self._headline(status_cards, actions),
            status_cards=status_cards,
            daily_actions=actions,
            warnings=warnings,
            top_opportunities=self._top_opportunities(shopping_report, dashboard_data),
            recent_progress=self._recent_progress(snapshot_report, series_reports, photo_report),
            workflow_statuses=list(self.workflow_statuses) + [status.to_dict() for status in daily_summary.summary.statuses],
        )

    def _daily_summary(self) -> CollectorDailySummary:
        return CollectorWorkflowEngine(
            collection_items=self.collection_items,
            want_list_intents=self.want_list_intents,
            photo_records=self.photo_records,
            photo_candidates=self.photo_candidates,
            shopping_candidates=self.shopping_candidates,
            ocr_reports=self.ocr_reports,
            market_awareness_engine=self.market_awareness_engine,
            snapshot_manager=self.snapshot_manager,
        ).daily_summary()

    def _snapshot_report(self) -> Any:
        current = self.snapshot_manager.create_snapshot(
            self.collection_items,
            self.want_list_intents,
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
            shopping_candidates=self.shopping_candidates,
        )
        return self.snapshot_manager.latest_report(current)

    def _low_trust_ocr_count(self) -> int:
        validator = OCRValidationEngine()
        count = 0
        for report in self.ocr_reports:
            try:
                if validator.validate(suggestion_report=report).trust_level.value != "HIGH":
                    count += 1
            except Exception:
                count += 1
        return count

    @staticmethod
    def _collection_health_card(dashboard_data: Any, integrity_report: Any) -> HomeStatusCard:
        quality = getattr(dashboard_data.quality_report, "overall_quality_score", 0) if dashboard_data.quality_report else 0
        integrity = getattr(getattr(integrity_report, "integrity_score", None), "score", 0)
        severity = HomeStatusSeverity.OK
        if integrity < 75 or getattr(integrity_report, "warnings", []):
            severity = HomeStatusSeverity.WARNING
        if integrity < 60:
            severity = HomeStatusSeverity.ACTION_REQUIRED
        return HomeStatusCard(
            "Collection Health",
            severity,
            f"Quality {quality}; integrity {integrity}",
            details=_clean_list(getattr(integrity_report, "recommendations", [])[:3]),
            metrics={
                "Collection items": dashboard_data.snapshot.total_collection_items,
                "Quality score": quality,
                "Integrity score": integrity,
                "Duplicate items": dashboard_data.snapshot.total_duplicate_items,
            },
            actions=getattr(integrity_report, "recommendations", [])[:3],
        )

    @staticmethod
    def _acquisition_focus_card(shopping_report: Any, dashboard_data: Any) -> HomeStatusCard:
        top = getattr(shopping_report, "best_next_purchase", None)
        if top:
            severity = HomeStatusSeverity.INFO
            if str(top.recommendation_status).upper() in {"MUST BUY", "STRONG BUY", "BUY"}:
                severity = HomeStatusSeverity.ACTION_REQUIRED
            return HomeStatusCard(
                "Acquisition Focus",
                severity,
                f"{top.recommendation_status}: {top.item_name}",
                details=list(top.reasons[:3]),
                metrics={
                    "Opportunity score": top.opportunity_score,
                    "Impact score": top.impact_score,
                    "Total cost": top.total_cost,
                },
                actions=["Review top shopping opportunity"],
            )
        priorities = getattr(dashboard_data, "top_collection_priorities", [])[:3]
        return HomeStatusCard(
            "Acquisition Focus",
            HomeStatusSeverity.INFO if priorities else HomeStatusSeverity.OK,
            "Collection priorities available" if priorities else "No active shopping opportunity",
            details=[f"{item.title}: {item.detail}" for item in priorities],
            metrics={"Open shopping candidates": 0},
            actions=["Add candidate to Smart Shopping Assistant"] if priorities else [],
        )

    @staticmethod
    def _review_queue_card(ocr_low_trust: int, photo_report: Any) -> HomeStatusCard:
        photo_issues = len(getattr(photo_report, "findings", []) or [])
        missing_photos = int(getattr(photo_report, "missing_photo_references", 0) or 0)
        severity = HomeStatusSeverity.OK
        if ocr_low_trust or photo_issues:
            severity = HomeStatusSeverity.WARNING
        actions = []
        if ocr_low_trust:
            actions.append("Review OCR validation items")
        if photo_issues:
            actions.extend(getattr(photo_report, "recommended_actions", [])[:3])
        return HomeStatusCard(
            "Review Queue",
            severity,
            f"{ocr_low_trust} OCR item(s); {photo_issues} photo issue(s)",
            details=[
                f"{issue.issue_type}: {issue.reference or issue.photo_path or 'photo metadata'}"
                for issue in getattr(photo_report, "findings", [])[:3]
            ],
            metrics={
                "OCR items awaiting review": ocr_low_trust,
                "Photo issues": photo_issues,
                "Missing photo references": missing_photos,
            },
            actions=actions,
        )

    @staticmethod
    def _data_safety_card(data_safety_report: Any) -> HomeStatusCard:
        status = str(getattr(data_safety_report, "status", "WARNING") or "WARNING").upper()
        severity = {
            "PASS": HomeStatusSeverity.OK,
            "WARNING": HomeStatusSeverity.WARNING,
            "FAIL": HomeStatusSeverity.ACTION_REQUIRED,
        }.get(status, HomeStatusSeverity.WARNING)
        issues = getattr(data_safety_report, "issues", []) or []
        return HomeStatusCard(
            "Data Safety",
            severity,
            f"Backup/data safety status: {status}",
            details=[f"{issue.area}: {issue.message}" for issue in issues[:3]],
            metrics={"Issue count": len(issues), "Status": status},
            actions=getattr(data_safety_report, "recommended_actions", [])[:3],
        )

    @staticmethod
    def _progress_card(snapshot_report: Any, series_reports: List[Any], photo_report: Any) -> HomeStatusCard:
        growth = getattr(snapshot_report, "growth_summary", None)
        best_series = series_reports[0] if series_reports else None
        photo_coverage = float(getattr(photo_report, "collection_photo_coverage_percentage", 0.0) or 0.0)
        headline = "Snapshot trend ready"
        if growth:
            headline = f"Collection size delta {growth.growth_since_last_snapshot:+d}"
        details = []
        if best_series:
            details.append(f"Top series focus: {best_series.series_name} ({best_series.completion_percentage:.1f}% complete)")
        if getattr(snapshot_report, "series_progress", []):
            details.append(f"{len(snapshot_report.series_progress)} supported series changed since comparison snapshot")
        return HomeStatusCard(
            "Progress",
            HomeStatusSeverity.INFO,
            headline,
            details=details,
            metrics={
                "Growth since last snapshot": getattr(growth, "growth_since_last_snapshot", 0) if growth else 0,
                "Quality delta": getattr(snapshot_report, "quality_delta", 0),
                "Integrity delta": getattr(snapshot_report, "integrity_delta", 0),
                "Photo coverage": f"{photo_coverage:.1f}%",
            },
            actions=["Create a new snapshot after meaningful collection changes"],
        )

    def _daily_actions(
        self,
        daily_summary: CollectorDailySummary,
        integrity_report: Any,
        data_safety_report: Any,
        photo_report: Any,
        snapshot_report: Any,
        shopping_report: Any,
        ocr_low_trust: int,
    ) -> List[DailyCollectorAction]:
        actions: List[DailyCollectorAction] = []
        if str(getattr(data_safety_report, "status", "")).upper() != "PASS":
            actions.append(DailyCollectorAction(
                "Back up collection data",
                "Data Safety reports warnings or failures.",
                100,
                HomeStatusSeverity.ACTION_REQUIRED,
                "Data Safety",
            ))
        if getattr(integrity_report, "warnings", []):
            actions.append(DailyCollectorAction(
                "Fix integrity issues",
                f"{len(integrity_report.warnings)} integrity warning(s) found.",
                90,
                HomeStatusSeverity.WARNING,
                "Collection Integrity",
            ))
        if ocr_low_trust:
            actions.append(DailyCollectorAction(
                "Review OCR items",
                f"{ocr_low_trust} OCR item(s) need manual review.",
                80,
                HomeStatusSeverity.WARNING,
                "OCR Validation",
            ))
        if getattr(photo_report, "findings", []):
            actions.append(DailyCollectorAction(
                "Add or fix missing photos",
                f"{len(photo_report.findings)} photo metadata issue(s) found.",
                70,
                HomeStatusSeverity.WARNING,
                "Photo Vault",
            ))
        top = getattr(shopping_report, "best_next_purchase", None)
        if top:
            actions.append(DailyCollectorAction(
                "Review top shopping opportunity",
                f"{top.item_name}: {top.recommendation_status} (score {top.opportunity_score}).",
                60,
                HomeStatusSeverity.INFO,
                "Smart Shopping",
            ))
        growth = getattr(snapshot_report, "growth_summary", None)
        if not growth or getattr(growth, "previous_size", 0) == 0:
            actions.append(DailyCollectorAction(
                "Create a new snapshot",
                "Snapshot history is empty or needs a baseline.",
                40,
                HomeStatusSeverity.INFO,
                "Snapshot System",
            ))
        for task in getattr(daily_summary, "recommended_tasks", [])[:5]:
            actions.append(DailyCollectorAction(
                task,
                "From Daily Collector Summary.",
                30,
                HomeStatusSeverity.INFO,
                "Daily Collector Summary",
            ))
        deduped: Dict[str, DailyCollectorAction] = {}
        for action in actions:
            if action.action_id in self.acknowledged_action_ids:
                action.acknowledged = True
            existing = deduped.get(action.action_id)
            if not existing or action.rank_key < existing.rank_key:
                deduped[action.action_id] = action
        return sorted(deduped.values(), key=lambda action: action.rank_key)

    @staticmethod
    def _headline(cards: List[HomeStatusCard], actions: List[DailyCollectorAction]) -> str:
        if any(card.severity == HomeStatusSeverity.ACTION_REQUIRED.value for card in cards):
            return "Action required before the collection is fully safe."
        if any(card.severity == HomeStatusSeverity.WARNING.value for card in cards):
            return "Review recommended items before the next acquisition."
        if actions:
            return "Collection is stable; review today's focus items."
        return "Collection is stable with no immediate actions."

    @staticmethod
    def _warnings(cards: List[HomeStatusCard], integrity_report: Any, data_safety_report: Any) -> List[str]:
        warnings = []
        warnings.extend(card.headline for card in cards if card.severity in {HomeStatusSeverity.WARNING.value, HomeStatusSeverity.ACTION_REQUIRED.value})
        warnings.extend(getattr(integrity_report, "warnings", [])[:5])
        warnings.extend(f"{issue.area}: {issue.message}" for issue in getattr(data_safety_report, "issues", [])[:5])
        return _clean_list(warnings, limit=10)

    @staticmethod
    def _top_opportunities(shopping_report: Any, dashboard_data: Any) -> List[str]:
        rows = []
        for rec in getattr(shopping_report, "recommendations", [])[:5]:
            rows.append(f"{rec.rank}. {rec.item_name}: {rec.recommendation_status} (score {rec.opportunity_score}, impact {rec.impact_score})")
        if not rows:
            for item in getattr(dashboard_data, "top_collection_priorities", [])[:5]:
                rows.append(f"{item.title}: {item.detail}")
        return rows

    @staticmethod
    def _recent_progress(snapshot_report: Any, series_reports: List[Any], photo_report: Any) -> List[str]:
        rows = []
        growth = getattr(snapshot_report, "growth_summary", None)
        if growth:
            rows.append(f"Collection size changed {growth.growth_since_last_snapshot:+d} since comparison snapshot.")
        rows.append(f"Quality score delta {getattr(snapshot_report, 'quality_delta', 0):+d}.")
        rows.append(f"Integrity score delta {getattr(snapshot_report, 'integrity_delta', 0):+d}.")
        rows.append(f"Photo coverage {float(getattr(photo_report, 'collection_photo_coverage_percentage', 0.0) or 0.0):.1f}%.")
        for series in series_reports[:3]:
            rows.append(f"{series.series_name}: {series.completion_percentage:.1f}% complete; priority {series.priority_score}.")
        return rows
