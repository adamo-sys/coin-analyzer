"""Collector workflow orchestration.

This module coordinates existing collector tools into guided workflows. It does
not replace recommendation engines, mutate collection records, scrape data,
perform grading, or run background jobs.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from collection_dashboard import CollectionDashboard
from collection_intelligence import CollectionIntelligenceEngine
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
from upgrade_advisor import UpgradeAdvisor


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


class WorkflowType(Enum):
    """Supported unified review workflow routes."""

    ACQUISITION_REVIEW = "ACQUISITION_REVIEW"
    COLLECTION_REVIEW = "COLLECTION_REVIEW"
    UPGRADE_REVIEW = "UPGRADE_REVIEW"
    DUPLICATE_REVIEW = "DUPLICATE_REVIEW"
    DAILY_INBOX = "DAILY_INBOX"


class WorkflowState(Enum):
    """High-level state for a unified workflow report."""

    READY = "READY"
    NEEDS_INPUT = "NEEDS_INPUT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"
    COMPLETE = "COMPLETE"


class WorkflowSeverity(Enum):
    """Normalized severity for workflow evidence."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class RecommendedTool(Enum):
    """Metadata-only tool vocabulary for workflow navigation hints."""

    NONE = "NONE"
    WANT_LIST = "WANT_LIST"
    AI_GRADING = "AI_GRADING"
    UPGRADE_ADVISOR = "UPGRADE_ADVISOR"
    DUPLICATE_REVIEW = "DUPLICATE_REVIEW"
    SMART_SHOPPING = "SMART_SHOPPING"
    WORKFLOW = "WORKFLOW"
    COLLECTION_DASHBOARD = "COLLECTION_DASHBOARD"
    COLLECTION_INTEGRITY = "COLLECTION_INTEGRITY"
    PHOTO_VAULT = "PHOTO_VAULT"
    OCR_EXPERIMENT = "OCR_EXPERIMENT"


RECOMMENDED_TOOL_LABELS = {
    RecommendedTool.NONE: "",
    RecommendedTool.WANT_LIST: "Want List",
    RecommendedTool.AI_GRADING: "AI Grading",
    RecommendedTool.UPGRADE_ADVISOR: "Upgrade Advisor",
    RecommendedTool.DUPLICATE_REVIEW: "Duplicate Review",
    RecommendedTool.SMART_SHOPPING: "Smart Shopping Assistant",
    RecommendedTool.WORKFLOW: "Workflow Review",
    RecommendedTool.COLLECTION_DASHBOARD: "Collection Dashboard",
    RecommendedTool.COLLECTION_INTEGRITY: "Collection Integrity Report",
    RecommendedTool.PHOTO_VAULT: "Photo Vault",
    RecommendedTool.OCR_EXPERIMENT: "OCR Experiment",
}

WORKFLOW_TOOL_MAP = {
    WorkflowType.ACQUISITION_REVIEW: RecommendedTool.SMART_SHOPPING,
    WorkflowType.COLLECTION_REVIEW: RecommendedTool.COLLECTION_DASHBOARD,
    WorkflowType.UPGRADE_REVIEW: RecommendedTool.UPGRADE_ADVISOR,
    WorkflowType.DUPLICATE_REVIEW: RecommendedTool.DUPLICATE_REVIEW,
    WorkflowType.DAILY_INBOX: RecommendedTool.WORKFLOW,
}


def _coerce_workflow_type(value: Any) -> WorkflowType:
    if isinstance(value, WorkflowType):
        return value
    try:
        return WorkflowType(str(value or "").strip())
    except ValueError as exc:
        raise ValueError(f"Unsupported workflow type: {value}") from exc


def _coerce_state(value: Any) -> WorkflowState:
    if isinstance(value, WorkflowState):
        return value
    try:
        return WorkflowState(str(value or WorkflowState.REVIEW_REQUIRED.value).strip().upper())
    except ValueError:
        return WorkflowState.REVIEW_REQUIRED


def _coerce_severity(value: Any) -> WorkflowSeverity:
    if isinstance(value, WorkflowSeverity):
        return value
    try:
        return WorkflowSeverity(str(value or WorkflowSeverity.INFO.value).strip().upper())
    except ValueError:
        return WorkflowSeverity.INFO


def _coerce_recommended_tool(value: Any) -> RecommendedTool:
    if isinstance(value, RecommendedTool):
        return value
    if value in (None, ""):
        return RecommendedTool.NONE
    text = str(value).strip()
    try:
        return RecommendedTool[text.upper()]
    except KeyError:
        try:
            return RecommendedTool(text.upper())
        except ValueError:
            return RecommendedTool.NONE


def _default_state_reason(
    workflow_type: WorkflowType,
    state: WorkflowState,
    title: str,
    summary: str,
    evidence: Iterable["WorkflowEvidence"],
) -> str:
    warning = next((item.detail for item in evidence if item.severity == WorkflowSeverity.WARNING), "")
    error = next((item.detail for item in evidence if item.severity == WorkflowSeverity.ERROR), "")
    name = title or workflow_type.value.replace("_", " ").title()
    if state == WorkflowState.NEEDS_INPUT:
        return warning or summary or f"{name} requires additional input before workflow evidence can be generated."
    if state == WorkflowState.BLOCKED:
        detail = error or summary
        if detail:
            return f"{name} failed because {detail}."
        return f"{name} could not complete because a source workflow component failed."
    if state == WorkflowState.REVIEW_REQUIRED:
        return warning or f"{name} produced evidence that requires collector review before any action."
    if state == WorkflowState.COMPLETE:
        return summary or f"{name} found no immediate workflow action in the available data."
    return f"{name} generated reviewable workflow output from the available data."


@dataclass
class WorkflowEvidence:
    """Source-labeled evidence used by unified workflow reports and actions."""

    source: str
    detail: str
    severity: WorkflowSeverity = WorkflowSeverity.INFO
    action: str = ""

    def __post_init__(self) -> None:
        self.source = str(self.source or "collector_workflows").strip()
        self.detail = str(self.detail or "").strip()
        self.severity = _coerce_severity(self.severity)
        self.action = str(self.action or "").strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "detail": self.detail,
            "severity": self.severity.value,
            "action": self.action,
        }


@dataclass
class WorkflowAction:
    """Review-only next action with source evidence."""

    label: str
    reason: str = ""
    source: str = ""
    state: WorkflowState = WorkflowState.REVIEW_REQUIRED
    evidence: List[WorkflowEvidence] = field(default_factory=list)
    recommended_tool: RecommendedTool = RecommendedTool.NONE
    recommended_tool_label: str = ""

    def __post_init__(self) -> None:
        self.label = str(self.label or "").strip()
        self.reason = str(self.reason or "").strip()
        self.source = str(self.source or "collector_workflows").strip()
        self.state = _coerce_state(self.state)
        self.recommended_tool = _coerce_recommended_tool(self.recommended_tool)
        self.recommended_tool_label = str(
            self.recommended_tool_label or RECOMMENDED_TOOL_LABELS.get(self.recommended_tool, "")
        ).strip()
        self.evidence = [
            evidence if isinstance(evidence, WorkflowEvidence) else WorkflowEvidence(**evidence)
            for evidence in self.evidence
        ]
        if not self.evidence:
            detail = self.reason or self.label or "Workflow action requires collector review."
            self.evidence = [WorkflowEvidence(self.source, detail, WorkflowSeverity.INFO)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "reason": self.reason,
            "source": self.source,
            "state": self.state.value,
            "evidence": [evidence.to_dict() for evidence in self.evidence],
            "recommended_tool": self.recommended_tool.value,
            "recommended_tool_label": self.recommended_tool_label,
        }


@dataclass
class WorkflowRequest:
    """Request for one unified workflow route."""

    workflow_type: WorkflowType
    candidate: Optional[Any] = None
    owned_item: Optional[Any] = None
    raw_ocr_text: str = ""
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.workflow_type = _coerce_workflow_type(self.workflow_type)
        self.raw_ocr_text = str(self.raw_ocr_text or "")
        self.context = dict(self.context or {})


@dataclass
class UnifiedWorkflowReport:
    """Normalized report returned by the unified workflow engine."""

    workflow_type: WorkflowType
    state: WorkflowState
    title: str
    summary: str
    evidence: List[WorkflowEvidence] = field(default_factory=list)
    next_actions: List[WorkflowAction] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_reports: Dict[str, Any] = field(default_factory=dict)
    state_reason: str = ""
    recommended_tool: RecommendedTool = RecommendedTool.NONE
    recommended_tool_label: str = ""

    def __post_init__(self) -> None:
        self.workflow_type = _coerce_workflow_type(self.workflow_type)
        self.state = _coerce_state(self.state)
        self.title = str(self.title or "").strip()
        self.summary = str(self.summary or "").strip()
        self.state_reason = str(self.state_reason or "").strip()
        self.recommended_tool = _coerce_recommended_tool(self.recommended_tool)
        if self.recommended_tool == RecommendedTool.NONE:
            self.recommended_tool = WORKFLOW_TOOL_MAP.get(self.workflow_type, RecommendedTool.WORKFLOW)
        self.recommended_tool_label = str(
            self.recommended_tool_label or RECOMMENDED_TOOL_LABELS.get(self.recommended_tool, "")
        ).strip()
        self.evidence = [
            evidence if isinstance(evidence, WorkflowEvidence) else WorkflowEvidence(**evidence)
            for evidence in self.evidence
        ]
        self.next_actions = [
            action if isinstance(action, WorkflowAction) else WorkflowAction(**action)
            for action in self.next_actions
        ]
        if not self.state_reason:
            self.state_reason = _default_state_reason(
                self.workflow_type,
                self.state,
                self.title,
                self.summary,
                self.evidence,
            )
        self.warnings = _dedupe(self.warnings)
        self.source_reports = dict(self.source_reports or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_type": self.workflow_type.value,
            "state": self.state.value,
            "title": self.title,
            "summary": self.summary,
            "state_reason": self.state_reason,
            "recommended_tool": self.recommended_tool.value,
            "recommended_tool_label": self.recommended_tool_label,
            "evidence": [evidence.to_dict() for evidence in self.evidence],
            "next_actions": [action.to_dict() for action in self.next_actions],
            "warnings": list(self.warnings),
            "source_reports": {
                key: value.to_dict() if hasattr(value, "to_dict") else str(value)
                for key, value in self.source_reports.items()
            },
        }


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

    def run_workflow(self, request: WorkflowRequest) -> UnifiedWorkflowReport:
        """Run one deterministic workflow route and normalize the result."""
        if not isinstance(request, WorkflowRequest):
            raise ValueError("run_workflow requires a WorkflowRequest.")
        routes = {
            WorkflowType.ACQUISITION_REVIEW: self._run_acquisition_review,
            WorkflowType.COLLECTION_REVIEW: self._run_collection_review,
            WorkflowType.UPGRADE_REVIEW: self._run_upgrade_review,
            WorkflowType.DUPLICATE_REVIEW: self._run_duplicate_review,
            WorkflowType.DAILY_INBOX: self._run_daily_inbox,
        }
        route = routes.get(request.workflow_type)
        if route is None:
            raise ValueError(f"Unsupported workflow type: {request.workflow_type}")
        try:
            return route(request)
        except Exception as exc:
            return self._blocked_report(request.workflow_type, self._workflow_title(request.workflow_type), exc)

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

    def _run_acquisition_review(self, request: WorkflowRequest) -> UnifiedWorkflowReport:
        if request.candidate is None:
            return self._needs_input_report(
                WorkflowType.ACQUISITION_REVIEW,
                "Acquisition Review",
                "Acquisition Review requires a candidate.",
            )
        report = self.acquisition_workflow(request.candidate, raw_ocr_text=request.raw_ocr_text)
        return self._normalize_summary_report(
            WorkflowType.ACQUISITION_REVIEW,
            "Acquisition Review",
            report.summary,
            {"acquisition": report},
        )

    def _run_collection_review(self, request: WorkflowRequest) -> UnifiedWorkflowReport:
        report = self.collection_review_workflow()
        return self._normalize_summary_report(
            WorkflowType.COLLECTION_REVIEW,
            "Collection Review",
            report.summary,
            {"collection_review": report},
        )

    def _run_upgrade_review(self, request: WorkflowRequest) -> UnifiedWorkflowReport:
        if request.candidate is None:
            return self._needs_input_report(
                WorkflowType.UPGRADE_REVIEW,
                "Upgrade Review",
                "Upgrade Review requires a candidate.",
            )
        candidate = self._candidate_fields(request.candidate)
        recommendation = UpgradeAdvisor(self.collection_items).analyze_upgrade(
            candidate["country"],
            candidate["denomination"],
            candidate["year"],
            candidate["grade"],
            candidate["estimate"],
        )
        evidence = [
            WorkflowEvidence("UpgradeAdvisor", recommendation.reason or recommendation.verdict, self._severity_for_text(recommendation.verdict), "Review upgrade verdict"),
            WorkflowEvidence("UpgradeAdvisor", f"Upgrade score {recommendation.upgrade_score}", WorkflowSeverity.INFO, "Compare candidate against owned example"),
        ]
        if recommendation.existing_item_id:
            evidence.append(WorkflowEvidence("UpgradeAdvisor", f"Existing item {recommendation.existing_item_id}: {recommendation.existing_grade}", WorkflowSeverity.INFO))
        warnings = []
        if recommendation.spot_price_warning:
            warnings.append(recommendation.spot_price_warning)
            evidence.append(WorkflowEvidence("MeltValueEngine", recommendation.spot_price_warning, WorkflowSeverity.WARNING))
        actions = [
            WorkflowAction(
                "Review upgrade recommendation",
                recommendation.reason or recommendation.verdict,
                "UpgradeAdvisor",
                WorkflowState.REVIEW_REQUIRED,
                [evidence[0]],
                recommended_tool=RecommendedTool.UPGRADE_ADVISOR,
            )
        ]
        state = self._state_from_evidence(evidence)
        return UnifiedWorkflowReport(
            WorkflowType.UPGRADE_REVIEW,
            state,
            "Upgrade Review",
            f"{recommendation.verdict}: {candidate['country']} {candidate['denomination']} {candidate['year']}".strip(),
            evidence=self._sort_evidence(evidence),
            next_actions=actions,
            warnings=warnings,
            source_reports={"upgrade_recommendation": recommendation},
            state_reason=self._state_reason_for_workflow(WorkflowType.UPGRADE_REVIEW, state, evidence),
            recommended_tool=RecommendedTool.UPGRADE_ADVISOR,
        )

    def _run_duplicate_review(self, request: WorkflowRequest) -> UnifiedWorkflowReport:
        intelligence = CollectionIntelligenceEngine(self.collection_items)
        duplicates = intelligence.detect_duplicates()
        upgrade_candidates = intelligence.detect_upgrade_candidates()
        evidence = [
            WorkflowEvidence("CollectionIntelligenceEngine", f"{len(duplicates)} duplicate group(s) detected", WorkflowSeverity.WARNING if duplicates else WorkflowSeverity.INFO, "Review duplicate holdings"),
            WorkflowEvidence("CollectionIntelligenceEngine", f"{len(upgrade_candidates)} lower-grade duplicate upgrade candidate(s)", WorkflowSeverity.WARNING if upgrade_candidates else WorkflowSeverity.INFO, "Review lower-grade duplicates"),
        ]
        for duplicate in duplicates[:5]:
            detail = f"{duplicate['country']} {duplicate['denomination']} {duplicate['year']}: {duplicate['count']} held".strip()
            evidence.append(WorkflowEvidence("CollectionIntelligenceEngine", detail, WorkflowSeverity.WARNING, "Decide keep/trade/sell after manual review"))
        actions = []
        if duplicates:
            actions.append(WorkflowAction(
                "Review duplicate holdings",
                "Duplicate groups need collector review before any action.",
                "CollectionIntelligenceEngine",
                WorkflowState.REVIEW_REQUIRED,
                [evidence[0]],
                recommended_tool=RecommendedTool.DUPLICATE_REVIEW,
            ))
        if upgrade_candidates:
            actions.append(WorkflowAction(
                "Review lower-grade duplicate upgrades",
                "Keep strongest examples and review lower-grade duplicates.",
                "CollectionIntelligenceEngine",
                WorkflowState.REVIEW_REQUIRED,
                [evidence[1]],
                recommended_tool=RecommendedTool.UPGRADE_ADVISOR,
            ))
        if not actions:
            actions.append(WorkflowAction(
                "No duplicate action required",
                "No duplicate holdings were detected.",
                "CollectionIntelligenceEngine",
                WorkflowState.COMPLETE,
                [evidence[0]],
                recommended_tool=RecommendedTool.DUPLICATE_REVIEW,
            ))
        state = WorkflowState.REVIEW_REQUIRED if duplicates or upgrade_candidates else WorkflowState.COMPLETE
        return UnifiedWorkflowReport(
            WorkflowType.DUPLICATE_REVIEW,
            state,
            "Duplicate Review",
            f"{len(duplicates)} duplicate group(s); {len(upgrade_candidates)} upgrade candidate(s)",
            evidence=self._sort_evidence(evidence),
            next_actions=actions,
            source_reports={"duplicates": duplicates, "upgrade_candidates": upgrade_candidates},
            state_reason=self._state_reason_for_workflow(WorkflowType.DUPLICATE_REVIEW, state, evidence),
            recommended_tool=RecommendedTool.DUPLICATE_REVIEW,
        )

    def _run_daily_inbox(self, request: WorkflowRequest) -> UnifiedWorkflowReport:
        report = self.daily_summary()
        return self._normalize_summary_report(
            WorkflowType.DAILY_INBOX,
            "Daily Inbox",
            report.summary,
            {"daily_summary": report},
        )

    def _normalize_summary_report(
        self,
        workflow_type: WorkflowType,
        title: str,
        summary: WorkflowSummary,
        source_reports: Dict[str, Any],
    ) -> UnifiedWorkflowReport:
        evidence = self._evidence_from_statuses(summary.statuses)
        if not evidence:
            evidence = [WorkflowEvidence(title, summary.headline or "Workflow produced no status items.")]
        actions = self._actions_from_summary(summary)
        warnings = [evidence_item.detail for evidence_item in evidence if evidence_item.severity in {WorkflowSeverity.WARNING, WorkflowSeverity.ERROR}]
        state = self._state_from_summary(summary, evidence, actions)
        return UnifiedWorkflowReport(
            workflow_type,
            state,
            title,
            summary.headline,
            evidence=self._sort_evidence(evidence),
            next_actions=actions,
            warnings=warnings,
            source_reports=source_reports,
            state_reason=self._state_reason_for_workflow(workflow_type, state, evidence),
            recommended_tool=WORKFLOW_TOOL_MAP.get(workflow_type, RecommendedTool.WORKFLOW),
        )

    @staticmethod
    def _evidence_from_statuses(statuses: Iterable[WorkflowStatus]) -> List[WorkflowEvidence]:
        evidence = []
        for status in statuses:
            detail = f"{status.status}: {status.detail or status.action}".strip()
            evidence.append(WorkflowEvidence("WorkflowStatus", detail, _coerce_severity(status.severity), status.action))
        return evidence

    @staticmethod
    def _actions_from_summary(summary: WorkflowSummary) -> List[WorkflowAction]:
        status_evidence = CollectorWorkflowEngine._evidence_from_statuses(summary.statuses)
        fallback = status_evidence[:1] or [WorkflowEvidence(summary.workflow_name, summary.headline or "Review workflow output.")]
        actions = []
        for action in summary.next_actions:
            tool = CollectorWorkflowEngine._recommended_tool_for_action(action, fallback)
            actions.append(WorkflowAction(
                action,
                summary.headline,
                summary.workflow_name,
                WorkflowState.REVIEW_REQUIRED,
                fallback,
                recommended_tool=tool,
            ))
        if not actions:
            tool = CollectorWorkflowEngine._recommended_tool_for_action(summary.headline, fallback)
            actions.append(WorkflowAction(
                "Review workflow report",
                summary.headline,
                summary.workflow_name,
                WorkflowState.REVIEW_REQUIRED,
                fallback,
                recommended_tool=tool,
            ))
        return actions

    @staticmethod
    def _recommended_tool_for_action(label: str, evidence: Iterable[WorkflowEvidence]) -> RecommendedTool:
        text = " ".join(
            [str(label or "")]
            + [item.source for item in evidence]
            + [item.detail for item in evidence]
            + [item.action for item in evidence]
        ).lower()
        if "ocr" in text:
            return RecommendedTool.OCR_EXPERIMENT
        if "photo" in text:
            return RecommendedTool.PHOTO_VAULT
        if "integrity" in text:
            return RecommendedTool.COLLECTION_INTEGRITY
        if "shopping" in text or "acquisition" in text or "opportunity" in text:
            return RecommendedTool.SMART_SHOPPING
        if "duplicate" in text:
            return RecommendedTool.DUPLICATE_REVIEW
        if "upgrade" in text:
            return RecommendedTool.UPGRADE_ADVISOR
        return RecommendedTool.WORKFLOW

    @staticmethod
    def _state_reason_for_workflow(
        workflow_type: WorkflowType,
        state: WorkflowState,
        evidence: Iterable[WorkflowEvidence],
    ) -> str:
        evidence_list = list(evidence or [])
        if workflow_type == WorkflowType.ACQUISITION_REVIEW and state == WorkflowState.NEEDS_INPUT:
            return "Acquisition Review requires a candidate before workflow evidence can be generated."
        if workflow_type == WorkflowType.UPGRADE_REVIEW and state == WorkflowState.NEEDS_INPUT:
            return "Upgrade Review requires a candidate before workflow evidence can be generated."
        if workflow_type == WorkflowType.DUPLICATE_REVIEW:
            if state == WorkflowState.COMPLETE:
                return "No duplicate groups were detected from the current collection data."
            if state == WorkflowState.REVIEW_REQUIRED:
                return "Duplicate or lower-grade duplicate evidence was found and requires collector review."
        if workflow_type == WorkflowType.DAILY_INBOX:
            if state == WorkflowState.REVIEW_REQUIRED:
                return "Daily Inbox found workflow items that require collector review."
            if state == WorkflowState.READY:
                return "Daily Inbox generated reviewable workflow tasks from current workspace data."
        if workflow_type == WorkflowType.COLLECTION_REVIEW:
            if state == WorkflowState.REVIEW_REQUIRED:
                return "Collection Review found warnings that require collector review."
            if state == WorkflowState.READY:
                return "Collection Review generated reviewable collection health output."
        if workflow_type == WorkflowType.UPGRADE_REVIEW and state == WorkflowState.REVIEW_REQUIRED:
            return "Upgrade Advisor evidence requires collector review before any upgrade decision."
        if workflow_type == WorkflowType.ACQUISITION_REVIEW:
            if state == WorkflowState.REVIEW_REQUIRED:
                return "Acquisition Review found warnings or decision evidence that require collector review."
            if state == WorkflowState.READY:
                return "Acquisition Review generated reviewable acquisition evidence for the candidate."
        return _default_state_reason(
            workflow_type,
            state,
            CollectorWorkflowEngine._workflow_title(workflow_type),
            "",
            evidence_list,
        )

    @staticmethod
    def _sort_evidence(evidence: Iterable[WorkflowEvidence]) -> List[WorkflowEvidence]:
        return sorted(evidence, key=lambda item: (item.source.lower(), item.detail.lower(), item.action.lower()))

    @staticmethod
    def _state_from_summary(summary: WorkflowSummary, evidence: List[WorkflowEvidence], actions: List[WorkflowAction]) -> WorkflowState:
        if any(item.severity == WorkflowSeverity.ERROR for item in evidence):
            return WorkflowState.BLOCKED
        if any(item.severity == WorkflowSeverity.WARNING for item in evidence):
            return WorkflowState.REVIEW_REQUIRED
        if not actions:
            return WorkflowState.COMPLETE
        status = str(summary.status or "").strip().lower()
        if status in {"ready", "review ready"}:
            return WorkflowState.READY
        return WorkflowState.REVIEW_REQUIRED

    @staticmethod
    def _state_from_evidence(evidence: List[WorkflowEvidence]) -> WorkflowState:
        if any(item.severity == WorkflowSeverity.ERROR for item in evidence):
            return WorkflowState.BLOCKED
        if any(item.severity == WorkflowSeverity.WARNING for item in evidence):
            return WorkflowState.REVIEW_REQUIRED
        return WorkflowState.READY

    @staticmethod
    def _severity_for_text(value: str) -> WorkflowSeverity:
        text = str(value or "").lower()
        if any(term in text for term in ("pass", "hold", "duplicate", "warning", "review")):
            return WorkflowSeverity.WARNING
        return WorkflowSeverity.INFO

    @staticmethod
    def _candidate_fields(candidate: Any) -> Dict[str, Any]:
        estimate = getattr(candidate, "estimate_cad", getattr(candidate, "asking_price", 0.0))
        try:
            estimate = float(estimate or 0.0)
        except (TypeError, ValueError):
            estimate = 0.0
        return {
            "country": str(getattr(candidate, "country", "") or "").strip(),
            "denomination": str(getattr(candidate, "denomination", "") or "").strip(),
            "year": str(getattr(candidate, "year", "") or "").strip(),
            "grade": str(getattr(candidate, "grade", "") or "").strip(),
            "estimate": estimate,
        }

    @staticmethod
    def _workflow_title(workflow_type: WorkflowType) -> str:
        return {
            WorkflowType.ACQUISITION_REVIEW: "Acquisition Review",
            WorkflowType.COLLECTION_REVIEW: "Collection Review",
            WorkflowType.UPGRADE_REVIEW: "Upgrade Review",
            WorkflowType.DUPLICATE_REVIEW: "Duplicate Review",
            WorkflowType.DAILY_INBOX: "Daily Inbox",
        }[workflow_type]

    @staticmethod
    def _needs_input_report(workflow_type: WorkflowType, title: str, detail: str) -> UnifiedWorkflowReport:
        evidence = [WorkflowEvidence("CollectorWorkflowEngine", detail, WorkflowSeverity.WARNING, "Provide required workflow input")]
        tool = WORKFLOW_TOOL_MAP.get(workflow_type, RecommendedTool.WORKFLOW)
        return UnifiedWorkflowReport(
            workflow_type,
            WorkflowState.NEEDS_INPUT,
            title,
            detail,
            evidence=evidence,
            next_actions=[
                WorkflowAction(
                    "Provide required workflow input",
                    detail,
                    "CollectorWorkflowEngine",
                    WorkflowState.NEEDS_INPUT,
                    evidence,
                    recommended_tool=tool,
                )
            ],
            warnings=[detail],
            state_reason=CollectorWorkflowEngine._state_reason_for_workflow(
                workflow_type,
                WorkflowState.NEEDS_INPUT,
                evidence,
            ),
            recommended_tool=tool,
        )

    @staticmethod
    def _blocked_report(workflow_type: WorkflowType, title: str, error: Exception) -> UnifiedWorkflowReport:
        detail = str(error) or error.__class__.__name__
        evidence = [WorkflowEvidence("CollectorWorkflowEngine", detail, WorkflowSeverity.ERROR, "Review source engine failure")]
        tool = WORKFLOW_TOOL_MAP.get(workflow_type, RecommendedTool.WORKFLOW)
        return UnifiedWorkflowReport(
            workflow_type,
            WorkflowState.BLOCKED,
            title,
            "Workflow could not complete because a source engine failed.",
            evidence=evidence,
            next_actions=[
                WorkflowAction(
                    "Review workflow failure",
                    detail,
                    "CollectorWorkflowEngine",
                    WorkflowState.BLOCKED,
                    evidence,
                    recommended_tool=tool,
                )
            ],
            warnings=[detail],
            state_reason=CollectorWorkflowEngine._state_reason_for_workflow(
                workflow_type,
                WorkflowState.BLOCKED,
                evidence,
            ),
            recommended_tool=tool,
        )
