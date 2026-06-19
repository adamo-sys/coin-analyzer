"""Collector workflow orchestration.

This module coordinates existing collector tools into guided workflows. It does
not replace recommendation engines, mutate collection records, scrape data,
perform grading, or run background jobs.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from collection_dashboard import CollectionDashboard
from collection_integrity import CollectionIntegrityAudit
from collection_quality import CollectionQualityEngine
from collection_snapshot import CollectionSnapshotManager
from market_awareness import MarketAwarenessEngine
from ocr_experiment import OCRExperiment, OCRSuggestionReport
from ocr_validation import OCRValidationEngine, OCRValidationReport
from photo_assisted_entry import PhotoAssistedEntry, PhotoCandidate, PhotoReviewReport
from photo_vault import PhotoCoverageReport, PhotoRecord, PhotoVaultIntegrityAudit
from shopping_explainability import ExplainableRecommendationReport, ShoppingExplanationEngine
from smart_shopping_assistant import ShoppingCandidate, ShoppingRecommendationReport, SmartShoppingAssistant


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            result.append(text)
    return result


@dataclass
class WorkflowStatus:
    """A deterministic workflow status item. No background jobs are created."""

    status: str
    detail: str = ""
    severity: str = "INFO"
    action: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        self.status = str(self.status or "").strip()
        self.detail = str(self.detail or "").strip()
        self.severity = str(self.severity or "INFO").strip().upper()
        self.action = str(self.action or "").strip()
        self.created_at = self.created_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "detail": self.detail,
            "severity": self.severity,
            "action": self.action,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "WorkflowStatus":
        return cls(
            status=str(payload.get("status") or ""),
            detail=str(payload.get("detail") or ""),
            severity=str(payload.get("severity") or "INFO"),
            action=str(payload.get("action") or ""),
            created_at=str(payload.get("created_at") or ""),
        )


@dataclass
class WorkflowSummary:
    """Compact workflow summary suitable for persistence."""

    workflow_name: str
    status: str
    headline: str
    next_actions: List[str] = field(default_factory=list)
    statuses: List[WorkflowStatus] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()
        self.next_actions = _dedupe(self.next_actions)
        self.statuses = [status if isinstance(status, WorkflowStatus) else WorkflowStatus.from_dict(status) for status in self.statuses]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_name": self.workflow_name,
            "status": self.status,
            "headline": self.headline,
            "next_actions": list(self.next_actions),
            "statuses": [status.to_dict() for status in self.statuses],
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "WorkflowSummary":
        return cls(
            workflow_name=str(payload.get("workflow_name") or ""),
            status=str(payload.get("status") or ""),
            headline=str(payload.get("headline") or ""),
            next_actions=list(payload.get("next_actions") or []),
            statuses=[WorkflowStatus.from_dict(row) for row in payload.get("statuses", [])],
            generated_at=str(payload.get("generated_at") or ""),
        )

    def format_markdown(self) -> str:
        lines = [
            f"# {self.workflow_name}",
            "",
            f"- Status: {self.status}",
            f"- Headline: {self.headline}",
            f"- Generated: {self.generated_at}",
            "",
            "## Workflow Status",
            "",
        ]
        lines.extend(f"- [{status.severity}] {status.status}: {status.detail or status.action}" for status in self.statuses) if self.statuses else lines.append("- No status items.")
        lines.extend(["", "## Next Actions", ""])
        lines.extend(f"- {action}" for action in self.next_actions) if self.next_actions else lines.append("- No next actions.")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["workflow_name", "status", "headline", "status_item", "severity", "action"])
            writer.writeheader()
            if self.statuses:
                for status in self.statuses:
                    writer.writerow({
                        "workflow_name": self.workflow_name,
                        "status": self.status,
                        "headline": self.headline,
                        "status_item": status.status,
                        "severity": status.severity,
                        "action": status.action,
                    })
            else:
                writer.writerow({
                    "workflow_name": self.workflow_name,
                    "status": self.status,
                    "headline": self.headline,
                    "status_item": "",
                    "severity": "",
                    "action": "",
                })
        return True


@dataclass
class AcquisitionWorkflowReport:
    """Guided acquisition workflow from photo evidence to recommendation review."""

    summary: WorkflowSummary
    photo_review_report: Optional[PhotoReviewReport] = None
    ocr_report: Optional[OCRSuggestionReport] = None
    validation_report: Optional[OCRValidationReport] = None
    shopping_report: Optional[ShoppingRecommendationReport] = None
    explanation_report: Optional[ExplainableRecommendationReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "photo_review_report": self.photo_review_report.to_dict() if self.photo_review_report else None,
            "ocr_report": self.ocr_report.to_dict() if self.ocr_report else None,
            "validation_report": self.validation_report.to_dict() if self.validation_report else None,
            "shopping_report": self.shopping_report.to_dict() if self.shopping_report else None,
            "explanation_report": self.explanation_report.to_dict() if self.explanation_report else None,
        }

    def format_markdown(self) -> str:
        lines = [self.summary.format_markdown()]
        if self.photo_review_report:
            lines.extend(["", "## Photo-Assisted Entry", "", self.photo_review_report.format_markdown()])
        if self.ocr_report:
            lines.extend(["", "## OCR Experiment", "", self.ocr_report.format_markdown()])
        if self.validation_report:
            lines.extend(["", "## OCR Validation", "", self.validation_report.format_markdown()])
        if self.shopping_report:
            lines.extend(["", "## Shopping Assistant", "", SmartShoppingAssistant([], []).format_markdown(self.shopping_report)])
        if self.explanation_report:
            lines.extend(["", "## Shopping Explainability", "", self.explanation_report.format_markdown()])
        return "\n".join(lines).strip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        self.summary.export_csv(output_path)
        return True


@dataclass
class CollectionReviewReport:
    summary: WorkflowSummary
    dashboard_data: Any = None
    quality_report: Any = None
    integrity_report: Any = None
    snapshot_report: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "dashboard_data": self.dashboard_data.snapshot.to_dict() if self.dashboard_data else None,
            "quality_score": getattr(self.quality_report, "overall_quality_score", 0) if self.quality_report else 0,
            "integrity_score": getattr(getattr(self.integrity_report, "integrity_score", None), "score", 0) if self.integrity_report else 0,
            "snapshot_report": self.snapshot_report.to_dict() if self.snapshot_report else None,
        }

    def format_markdown(self) -> str:
        lines = [self.summary.format_markdown()]
        if self.dashboard_data:
            snapshot = self.dashboard_data.snapshot
            lines.extend([
                "",
                "## Collection Dashboard",
                "",
                f"- Total collection items: {snapshot.total_collection_items}",
                f"- Countries represented: {snapshot.collection_countries_count}",
                f"- Denominations represented: {snapshot.collection_denominations_count}",
                f"- WANT_LIST items: {snapshot.total_want_list_items}",
                f"- Upgrade opportunities: {snapshot.total_upgrade_opportunities}",
            ])
            if self.dashboard_data.top_collection_priorities:
                lines.extend(["", "### Top Priorities", ""])
                lines.extend(f"- {item.title}: {item.detail}" for item in self.dashboard_data.top_collection_priorities[:5])
        if self.quality_report:
            lines.extend([
                "",
                "## Collection Quality",
                "",
                f"- Overall quality score: {self.quality_report.overall_quality_score}",
            ])
            for category in self.quality_report.category_scores:
                lines.append(f"- {category.name}: {category.score}")
            if self.quality_report.recommended_actions:
                lines.extend(["", "### Recommended Actions", ""])
                lines.extend(f"- {action.rank}. {action.action}: {action.expected_impact}" for action in self.quality_report.recommended_actions[:5])
        if self.integrity_report:
            lines.extend(["", "## Collection Integrity", "", self.integrity_report.format_markdown()])
        if self.snapshot_report:
            lines.extend(["", "## Snapshot Review", "", self.snapshot_report.format_markdown()])
        return "\n".join(lines).strip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        self.summary.export_csv(output_path)
        return True


@dataclass
class PhotoWorkflowReport:
    summary: WorkflowSummary
    photo_coverage_report: Optional[PhotoCoverageReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "photo_coverage_report": self.photo_coverage_report.to_dict() if self.photo_coverage_report else None,
        }

    def format_markdown(self) -> str:
        lines = [self.summary.format_markdown()]
        if self.photo_coverage_report:
            lines.extend(["", "## Photo Vault Audit", "", self.photo_coverage_report.format_markdown()])
        return "\n".join(lines).strip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        self.summary.export_csv(output_path)
        return True


@dataclass
class CollectorDailySummary:
    summary: WorkflowSummary
    recommended_tasks: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.recommended_tasks = _dedupe(self.recommended_tasks)

    def to_dict(self) -> Dict[str, Any]:
        payload = self.summary.to_dict()
        payload["recommended_tasks"] = list(self.recommended_tasks)
        return payload

    def format_markdown(self) -> str:
        lines = [self.summary.format_markdown(), "", "## Recommended Today", ""]
        lines.extend(f"- {task}" for task in self.recommended_tasks) if self.recommended_tasks else lines.append("- No immediate workflow tasks.")
        return "\n".join(lines).strip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["task", "workflow_status"])
            writer.writeheader()
            for task in self.recommended_tasks:
                writer.writerow({"task": task, "workflow_status": self.summary.status})
        return True


class AcquisitionWorkflow:
    """Orchestrate Photo -> OCR -> Validation -> Shopping -> Explainability."""

    def __init__(
        self,
        collection_items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        photo_records: Optional[Iterable[PhotoRecord]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.photo_records = list(photo_records or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()

    def run(self, candidate: PhotoCandidate, raw_ocr_text: str = "") -> AcquisitionWorkflowReport:
        statuses = []
        photo_report = PhotoAssistedEntry(
            self.collection_items,
            self.want_list_intents,
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
        ).analyze_candidate(candidate)
        statuses.append(WorkflowStatus("Photo Review Complete", candidate.title, "INFO", "Review attached photo evidence"))
        ocr_report = OCRExperiment().from_photo_candidate(candidate, raw_text=raw_ocr_text if raw_ocr_text else None)
        statuses.append(WorkflowStatus("OCR Complete", f"{len(ocr_report.result.raw_text)} OCR character(s)", "INFO", "Review OCR suggestions"))
        validation_report = OCRValidationEngine().validate(suggestion_report=ocr_report)
        severity = "WARNING" if validation_report.trust_level.value != "HIGH" else "INFO"
        statuses.append(WorkflowStatus("OCR Validation Complete", validation_report.trust_level.value, severity, "Review validation warnings"))
        shopping_candidate = candidate.to_shopping_candidate()
        shopping_report = SmartShoppingAssistant(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).generate_report([shopping_candidate], include_want_list_targets=False, limit=1)
        statuses.append(WorkflowStatus("Shopping Recommendation Complete", self._shopping_headline(shopping_report), "INFO", "Review recommendation and explanation"))
        explanation = None
        if shopping_report.best_next_purchase:
            explanation = ShoppingExplanationEngine().explain_shopping_recommendation(shopping_report.best_next_purchase)
            statuses.append(WorkflowStatus("Shopping Explanation Complete", explanation.explanation.confidence.level, "INFO", "Save candidate after collector review"))
        next_actions = self._acquisition_actions(candidate, validation_report, shopping_report)
        summary = WorkflowSummary(
            "Acquisition Workflow",
            "Review Ready",
            self._shopping_headline(shopping_report),
            next_actions=next_actions,
            statuses=statuses,
        )
        return AcquisitionWorkflowReport(summary, photo_report, ocr_report, validation_report, shopping_report, explanation)

    @staticmethod
    def _shopping_headline(report: ShoppingRecommendationReport) -> str:
        if report.best_next_purchase:
            rec = report.best_next_purchase
            return f"{rec.recommendation_status}: {rec.item_name} (score {rec.opportunity_score})"
        return "No shopping recommendation produced"

    @staticmethod
    def _acquisition_actions(candidate: PhotoCandidate, validation: OCRValidationReport, shopping: ShoppingRecommendationReport) -> List[str]:
        actions = ["Review candidate manually before saving"]
        if validation.trust_level.value != "HIGH":
            actions.append("Verify OCR fields before using them")
        if candidate.missing_photo_references():
            actions.append("Resolve missing photo references")
        if shopping.best_next_purchase:
            actions.append(f"Review {shopping.best_next_purchase.recommendation_status} recommendation")
        actions.append("Save candidate only after collector confirmation")
        return actions


class CollectionReviewWorkflow:
    """Orchestrate Dashboard -> Quality -> Integrity -> Snapshot -> Actions."""

    def __init__(
        self,
        collection_items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        photo_records: Optional[Iterable[PhotoRecord]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        shopping_candidates: Optional[Iterable[ShoppingCandidate]] = None,
        snapshot_manager: Optional[CollectionSnapshotManager] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.photo_records = list(photo_records or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()
        self.shopping_candidates = list(shopping_candidates or [])
        self.snapshot_manager = snapshot_manager or CollectionSnapshotManager()

    def run(self) -> CollectionReviewReport:
        dashboard = CollectionDashboard(
            self.collection_items,
            self.want_list_intents,
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
            shopping_candidates=self.shopping_candidates,
        ).generate_dashboard()
        quality = CollectionQualityEngine(self.collection_items, self.want_list_intents).generate_report()
        integrity = CollectionIntegrityAudit(
            self.collection_items,
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
            shopping_candidates=self.shopping_candidates,
        ).run()
        current_snapshot = self.snapshot_manager.create_snapshot(
            self.collection_items,
            self.want_list_intents,
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
            shopping_candidates=self.shopping_candidates,
        )
        snapshot = self.snapshot_manager.latest_report(current_snapshot)
        statuses = [
            WorkflowStatus("Dashboard Reviewed", f"{dashboard.snapshot.total_collection_items} collection item(s)", "INFO", "Review top priorities"),
            WorkflowStatus("Quality Reviewed", f"Quality score {quality.overall_quality_score}", "INFO", "Review strengths and weaknesses"),
            WorkflowStatus("Integrity Reviewed", f"Integrity score {integrity.integrity_score.score}", "WARNING" if integrity.warnings else "INFO", "Resolve integrity findings"),
            WorkflowStatus("Snapshot Reviewed", f"Collection size {current_snapshot.collection_size}", "INFO", "Create snapshot after major changes"),
        ]
        summary = WorkflowSummary(
            "Collection Review Workflow",
            "Review Ready",
            f"Quality {quality.overall_quality_score}; Integrity {integrity.integrity_score.score}",
            next_actions=self._collection_actions(dashboard, quality, integrity),
            statuses=statuses,
        )
        return CollectionReviewReport(summary, dashboard, quality, integrity, snapshot)

    @staticmethod
    def _collection_actions(dashboard: Any, quality: Any, integrity: Any) -> List[str]:
        actions = []
        actions.extend(action.action for action in getattr(quality, "recommended_actions", [])[:3])
        actions.extend(getattr(integrity, "recommendations", [])[:3])
        if getattr(dashboard, "top_collection_priorities", []):
            actions.append(dashboard.top_collection_priorities[0].action or dashboard.top_collection_priorities[0].title)
        actions.append("Create snapshot after completing collection maintenance")
        return actions


class PhotoReviewWorkflow:
    """Orchestrate Photo Vault -> Audit -> Coverage -> Missing Photo Actions."""

    def __init__(
        self,
        photo_records: Optional[Iterable[PhotoRecord]] = None,
        collection_items: Optional[Iterable[Any]] = None,
        photo_candidates: Optional[Iterable[Any]] = None,
    ):
        self.photo_records = list(photo_records or [])
        self.collection_items = list(collection_items or [])
        self.photo_candidates = list(photo_candidates or [])

    def run(self) -> PhotoWorkflowReport:
        coverage = PhotoVaultIntegrityAudit(
            self.photo_records,
            self.collection_items,
            self.photo_candidates,
        ).run()
        statuses = [
            WorkflowStatus("Photo Vault Reviewed", f"{coverage.total_photo_records} photo record(s)", "INFO", "Review photo metadata"),
            WorkflowStatus("Coverage Reviewed", f"{coverage.collection_photo_coverage_percentage:.1f}% collection coverage", "INFO", "Add missing collection photos"),
        ]
        if coverage.missing_photo_references:
            statuses.append(WorkflowStatus("Photo Missing", f"{coverage.missing_photo_references} missing reference(s)", "WARNING", "Fix missing photo paths"))
        summary = WorkflowSummary(
            "Photo Review Workflow",
            "Review Ready",
            f"Photo coverage {coverage.collection_photo_coverage_percentage:.1f}%",
            next_actions=coverage.recommended_actions or ["Review photo coverage and add missing photos"],
            statuses=statuses,
        )
        return PhotoWorkflowReport(summary, coverage)


class CollectorWorkflowEngine:
    """Facade for guided collector workflows."""

    def __init__(
        self,
        collection_items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        photo_records: Optional[Iterable[PhotoRecord]] = None,
        photo_candidates: Optional[Iterable[Any]] = None,
        shopping_candidates: Optional[Iterable[ShoppingCandidate]] = None,
        ocr_reports: Optional[Iterable[OCRSuggestionReport]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        snapshot_manager: Optional[CollectionSnapshotManager] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.photo_records = list(photo_records or [])
        self.photo_candidates = list(photo_candidates or [])
        self.shopping_candidates = list(shopping_candidates or [])
        self.ocr_reports = list(ocr_reports or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()
        self.snapshot_manager = snapshot_manager or CollectionSnapshotManager()

    def acquisition_workflow(self, candidate: PhotoCandidate, raw_ocr_text: str = "") -> AcquisitionWorkflowReport:
        return AcquisitionWorkflow(
            self.collection_items,
            self.want_list_intents,
            self.photo_records,
            self.market_awareness_engine,
        ).run(candidate, raw_ocr_text=raw_ocr_text)

    def collection_review_workflow(self) -> CollectionReviewReport:
        return CollectionReviewWorkflow(
            self.collection_items,
            self.want_list_intents,
            self.photo_records,
            self.market_awareness_engine,
            self.shopping_candidates,
            self.snapshot_manager,
        ).run()

    def photo_review_workflow(self) -> PhotoWorkflowReport:
        return PhotoReviewWorkflow(
            self.photo_records,
            self.collection_items,
            self.photo_candidates,
        ).run()

    def daily_summary(self) -> CollectorDailySummary:
        collection = self.collection_review_workflow()
        photo = self.photo_review_workflow()
        statuses = []
        statuses.extend(collection.summary.statuses)
        statuses.extend(photo.summary.statuses)
        tasks = []
        if self.ocr_reports:
            low_trust = [
                report for report in self.ocr_reports
                if OCRValidationEngine().validate(suggestion_report=report).trust_level.value != "HIGH"
            ]
            if low_trust:
                statuses.append(WorkflowStatus("OCR Pending", f"{len(low_trust)} OCR report(s) need review", "WARNING", "Review OCR validation reports"))
                tasks.append("Review OCR items")
        if any(status.status == "Photo Missing" for status in statuses):
            tasks.append("Add missing photos")
        if any(status.status == "Integrity Reviewed" and status.severity == "WARNING" for status in statuses):
            tasks.append("Fix integrity issues")
        if self.shopping_candidates:
            tasks.append("Consider top acquisition opportunity")
        tasks.append("Create snapshot")
        summary = WorkflowSummary(
            "Daily Collector Summary",
            "Ready",
            "Daily collector priorities generated",
            next_actions=tasks,
            statuses=statuses,
        )
        return CollectorDailySummary(summary, tasks)
