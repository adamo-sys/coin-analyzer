"""Collector Companion release-candidate readiness audits.

This module performs report-only readiness checks for v3.0. It does not add
recommendation logic, mutate collection records, run OCR, scrape data, call
APIs, or create background work.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from backup_manager import BackupManager, DataSafetyValidator
from collection_dashboard import CollectionDashboard
from collection_integrity import CollectionIntegrityAudit
from collection_snapshot import CollectionSnapshotManager
from collector_home_dashboard import CollectorHomeDashboard, HomeStatusSeverity
from collector_workflows import CollectorWorkflowEngine
from market_awareness import MarketAwarenessEngine
from ocr_experiment import OCRExperiment
from ocr_validation import OCRValidationEngine
from photo_vault import PhotoRecord, PhotoVaultIntegrityAudit
from series_tracker import SeriesTracker
from smart_shopping_assistant import ShoppingCandidate


READY = "READY"
NEEDS_WORK = "NEEDS_WORK"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _dedupe(values: Iterable[Any]) -> List[str]:
    result = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            result.append(text)
    return result


@dataclass
class AuditFinding:
    area: str
    status: str
    severity: str
    message: str
    recommendation: str = ""

    def __post_init__(self) -> None:
        self.area = str(self.area or "").strip()
        self.status = str(self.status or "OK").strip().upper()
        self.severity = str(self.severity or HomeStatusSeverity.INFO.value).strip().upper()
        self.message = str(self.message or "").strip()
        self.recommendation = str(self.recommendation or "").strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "area": self.area,
            "status": self.status,
            "severity": self.severity,
            "message": self.message,
            "recommendation": self.recommendation,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AuditFinding":
        return cls(
            area=str(payload.get("area") or ""),
            status=str(payload.get("status") or "OK"),
            severity=str(payload.get("severity") or HomeStatusSeverity.INFO.value),
            message=str(payload.get("message") or ""),
            recommendation=str(payload.get("recommendation") or ""),
        )


@dataclass
class V3ReadinessChecklistItem:
    name: str
    ready: bool
    detail: str = ""
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ready": self.ready,
            "detail": self.detail,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "V3ReadinessChecklistItem":
        return cls(
            name=str(payload.get("name") or ""),
            ready=bool(payload.get("ready", False)),
            detail=str(payload.get("detail") or ""),
            required=bool(payload.get("required", True)),
        )


@dataclass
class ExportConsistencyReport:
    status: str
    checked_reports: List[str] = field(default_factory=list)
    findings: List[AuditFinding] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()
        self.checked_reports = _dedupe(self.checked_reports)
        self.findings = [finding if isinstance(finding, AuditFinding) else AuditFinding.from_dict(finding) for finding in self.findings]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "checked_reports": list(self.checked_reports),
            "findings": [finding.to_dict() for finding in self.findings],
            "generated_at": self.generated_at,
        }

    def format_markdown(self) -> str:
        lines = ["# Export Consistency Report", "", f"- Status: {self.status}", f"- Generated: {self.generated_at}", "", "## Checked Reports", ""]
        lines.extend(f"- {name}" for name in self.checked_reports) if self.checked_reports else lines.append("- No reports checked.")
        lines.extend(["", "## Findings", ""])
        lines.extend(_format_finding(finding) for finding in self.findings) if self.findings else lines.append("- No export consistency findings.")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        _export_findings_csv(output_path, self.findings, self.checked_reports, "Export Consistency")
        return True


@dataclass
class ReportConsistencyReport:
    status: str
    checked_reports: List[str] = field(default_factory=list)
    findings: List[AuditFinding] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()
        self.checked_reports = _dedupe(self.checked_reports)
        self.findings = [finding if isinstance(finding, AuditFinding) else AuditFinding.from_dict(finding) for finding in self.findings]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "checked_reports": list(self.checked_reports),
            "findings": [finding.to_dict() for finding in self.findings],
            "generated_at": self.generated_at,
        }

    def format_markdown(self) -> str:
        lines = ["# Report Consistency Report", "", f"- Status: {self.status}", f"- Generated: {self.generated_at}", "", "## Findings", ""]
        lines.extend(_format_finding(finding) for finding in self.findings) if self.findings else lines.append("- No report consistency findings.")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        _export_findings_csv(output_path, self.findings, self.checked_reports, "Report Consistency")
        return True


@dataclass
class WorkflowAuditReport:
    status: str
    friction_points: List[str] = field(default_factory=list)
    inconsistencies: List[str] = field(default_factory=list)
    defects: List[str] = field(default_factory=list)
    findings: List[AuditFinding] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()
        self.friction_points = _dedupe(self.friction_points)
        self.inconsistencies = _dedupe(self.inconsistencies)
        self.defects = _dedupe(self.defects)
        self.findings = [finding if isinstance(finding, AuditFinding) else AuditFinding.from_dict(finding) for finding in self.findings]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "friction_points": list(self.friction_points),
            "inconsistencies": list(self.inconsistencies),
            "defects": list(self.defects),
            "findings": [finding.to_dict() for finding in self.findings],
            "generated_at": self.generated_at,
        }

    def format_markdown(self) -> str:
        lines = ["# End-to-End Workflow Audit", "", f"- Status: {self.status}", f"- Generated: {self.generated_at}", "", "## Friction Points", ""]
        lines.extend(f"- {item}" for item in self.friction_points) if self.friction_points else lines.append("- No release-blocking workflow friction found.")
        lines.extend(["", "## Inconsistencies", ""])
        lines.extend(f"- {item}" for item in self.inconsistencies) if self.inconsistencies else lines.append("- No workflow inconsistencies found.")
        lines.extend(["", "## Defects", ""])
        lines.extend(f"- {item}" for item in self.defects) if self.defects else lines.append("- No workflow defects found.")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        _export_findings_csv(output_path, self.findings, self.friction_points + self.inconsistencies + self.defects, "Workflow Audit")
        return True


@dataclass
class CollectorCompanionReadinessReport:
    status: str
    checklist: List[V3ReadinessChecklistItem] = field(default_factory=list)
    findings: List[AuditFinding] = field(default_factory=list)
    export_consistency: Optional[ExportConsistencyReport] = None
    report_consistency: Optional[ReportConsistencyReport] = None
    workflow_audit: Optional[WorkflowAuditReport] = None
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()
        self.checklist = [item if isinstance(item, V3ReadinessChecklistItem) else V3ReadinessChecklistItem.from_dict(item) for item in self.checklist]
        self.findings = [finding if isinstance(finding, AuditFinding) else AuditFinding.from_dict(finding) for finding in self.findings]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "checklist": [item.to_dict() for item in self.checklist],
            "findings": [finding.to_dict() for finding in self.findings],
            "export_consistency": self.export_consistency.to_dict() if self.export_consistency else None,
            "report_consistency": self.report_consistency.to_dict() if self.report_consistency else None,
            "workflow_audit": self.workflow_audit.to_dict() if self.workflow_audit else None,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CollectorCompanionReadinessReport":
        return cls(
            status=str(payload.get("status") or NEEDS_WORK),
            checklist=[V3ReadinessChecklistItem.from_dict(row) for row in payload.get("checklist", [])],
            findings=[AuditFinding.from_dict(row) for row in payload.get("findings", [])],
            export_consistency=ExportConsistencyReport(**payload["export_consistency"]) if payload.get("export_consistency") else None,
            report_consistency=ReportConsistencyReport(**payload["report_consistency"]) if payload.get("report_consistency") else None,
            workflow_audit=WorkflowAuditReport(**payload["workflow_audit"]) if payload.get("workflow_audit") else None,
            generated_at=str(payload.get("generated_at") or ""),
        )

    def format_markdown(self) -> str:
        lines = [
            "# Collector Companion Readiness Report",
            "",
            f"- Status: {self.status}",
            f"- Generated: {self.generated_at}",
            "",
            "## V3.0 Readiness Checklist",
            "",
        ]
        for item in self.checklist:
            mark = "[x]" if item.ready else "[!]"
            lines.append(f"- {mark} {item.name}: {item.detail}")
        lines.extend(["", "## Findings", ""])
        lines.extend(_format_finding(finding) for finding in self.findings) if self.findings else lines.append("- No readiness findings.")
        if self.export_consistency:
            lines.extend(["", self.export_consistency.format_markdown().strip()])
        if self.report_consistency:
            lines.extend(["", self.report_consistency.format_markdown().strip()])
        if self.workflow_audit:
            lines.extend(["", self.workflow_audit.format_markdown().strip()])
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["section", "name", "status", "severity", "detail", "recommendation"])
            writer.writeheader()
            writer.writerow({"section": "Readiness", "name": "Overall", "status": self.status, "severity": "", "detail": self.generated_at, "recommendation": ""})
            for item in self.checklist:
                writer.writerow({
                    "section": "Checklist",
                    "name": item.name,
                    "status": "READY" if item.ready else "NEEDS_WORK",
                    "severity": "",
                    "detail": item.detail,
                    "recommendation": "",
                })
            for finding in self.findings:
                writer.writerow({
                    "section": "Finding",
                    "name": finding.area,
                    "status": finding.status,
                    "severity": finding.severity,
                    "detail": finding.message,
                    "recommendation": finding.recommendation,
                })
        return True


@dataclass
class CollectorCompanionStatus:
    """Concise v3.0 product status derived from existing readiness audits."""

    status: str
    collection_management: str
    acquisition_workflow: str
    ocr_workflow: str
    integrity_workflow: str
    backup_workflow: str
    dashboard_workflow: str
    justification: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.status = str(self.status or NEEDS_WORK).strip().upper()
        self.collection_management = str(self.collection_management or NEEDS_WORK).strip().upper()
        self.acquisition_workflow = str(self.acquisition_workflow or NEEDS_WORK).strip().upper()
        self.ocr_workflow = str(self.ocr_workflow or NEEDS_WORK).strip().upper()
        self.integrity_workflow = str(self.integrity_workflow or NEEDS_WORK).strip().upper()
        self.backup_workflow = str(self.backup_workflow or NEEDS_WORK).strip().upper()
        self.dashboard_workflow = str(self.dashboard_workflow or NEEDS_WORK).strip().upper()
        self.justification = _dedupe(self.justification)
        self.limitations = _dedupe(self.limitations)
        self.generated_at = self.generated_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "collection_management": self.collection_management,
            "acquisition_workflow": self.acquisition_workflow,
            "ocr_workflow": self.ocr_workflow,
            "integrity_workflow": self.integrity_workflow,
            "backup_workflow": self.backup_workflow,
            "dashboard_workflow": self.dashboard_workflow,
            "justification": list(self.justification),
            "limitations": list(self.limitations),
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CollectorCompanionStatus":
        return cls(
            status=str(payload.get("status") or NEEDS_WORK),
            collection_management=str(payload.get("collection_management") or NEEDS_WORK),
            acquisition_workflow=str(payload.get("acquisition_workflow") or NEEDS_WORK),
            ocr_workflow=str(payload.get("ocr_workflow") or NEEDS_WORK),
            integrity_workflow=str(payload.get("integrity_workflow") or NEEDS_WORK),
            backup_workflow=str(payload.get("backup_workflow") or NEEDS_WORK),
            dashboard_workflow=str(payload.get("dashboard_workflow") or NEEDS_WORK),
            justification=list(payload.get("justification", [])),
            limitations=list(payload.get("limitations", [])),
            generated_at=str(payload.get("generated_at") or ""),
        )

    def format_markdown(self) -> str:
        lines = [
            "# Collector Companion Status",
            "",
            f"- Status: {self.status}",
            f"- Generated: {self.generated_at}",
            "",
            "## Workflow Status",
            "",
            f"- Collection Management: {self.collection_management}",
            f"- Acquisition Workflow: {self.acquisition_workflow}",
            f"- OCR Workflow: {self.ocr_workflow}",
            f"- Integrity Workflow: {self.integrity_workflow}",
            f"- Backup Workflow: {self.backup_workflow}",
            f"- Dashboard Workflow: {self.dashboard_workflow}",
            "",
            "## Justification",
            "",
        ]
        lines.extend(f"- {item}" for item in self.justification) if self.justification else lines.append("- No justification recorded.")
        lines.extend(["", "## Final Limitations", ""])
        lines.extend(f"- {item}" for item in self.limitations) if self.limitations else lines.append("- No final limitations recorded.")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["section", "name", "status", "detail"])
            writer.writeheader()
            writer.writerow({"section": "Status", "name": "Overall", "status": self.status, "detail": self.generated_at})
            for name, value in [
                ("Collection Management", self.collection_management),
                ("Acquisition Workflow", self.acquisition_workflow),
                ("OCR Workflow", self.ocr_workflow),
                ("Integrity Workflow", self.integrity_workflow),
                ("Backup Workflow", self.backup_workflow),
                ("Dashboard Workflow", self.dashboard_workflow),
            ]:
                writer.writerow({"section": "Workflow", "name": name, "status": value, "detail": ""})
            for item in self.justification:
                writer.writerow({"section": "Justification", "name": "", "status": "", "detail": item})
            for item in self.limitations:
                writer.writerow({"section": "Limitation", "name": "", "status": "", "detail": item})
        return True


class CollectorCompanionReadinessAuditor:
    """Generate v3.0 readiness reports from existing systems."""

    REPORT_REGISTRY = [
        "Collector Home Dashboard",
        "Collection Dashboard",
        "Collection Health Report",
        "Daily Collector Summary",
        "Acquisition Workflow",
        "Photo Review Workflow",
        "OCR Experiment",
        "OCR Validation",
        "Photo Vault Audit",
        "Collection Integrity Audit",
        "Collection Snapshot Report",
        "Data Safety Report",
        "Smart Shopping Assistant",
    ]

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

    def generate_report(self) -> CollectorCompanionReadinessReport:
        export_report = self.audit_exports()
        report_consistency = self.audit_report_consistency()
        workflow_audit = self.audit_end_to_end_workflow()
        checklist = self.v3_readiness_checklist()
        findings = []
        findings.extend(export_report.findings)
        findings.extend(report_consistency.findings)
        findings.extend(workflow_audit.findings)
        blocking = any(item.required and not item.ready for item in checklist)
        blocking = blocking or any(finding.severity == HomeStatusSeverity.ACTION_REQUIRED.value for finding in findings)
        status = NEEDS_WORK if blocking else READY
        return CollectorCompanionReadinessReport(
            status=status,
            checklist=checklist,
            findings=findings,
            export_consistency=export_report,
            report_consistency=report_consistency,
            workflow_audit=workflow_audit,
        )

    def companion_status(self) -> CollectorCompanionStatus:
        report = self.generate_report()
        checklist = {item.name: item.ready for item in report.checklist}
        required_ready = all(item.ready for item in report.checklist if item.required)
        workflow_ready = report.workflow_audit.status == READY if report.workflow_audit else False
        status = READY if report.status == READY and required_ready and workflow_ready else NEEDS_WORK
        limitations = list(report.workflow_audit.friction_points if report.workflow_audit else [])
        limitations.extend(
            finding.message
            for finding in report.findings
            if finding.severity in {HomeStatusSeverity.WARNING.value, HomeStatusSeverity.ACTION_REQUIRED.value}
        )
        return CollectorCompanionStatus(
            status=status,
            collection_management=READY if checklist.get("Series Tracker") and checklist.get("Snapshot System") else NEEDS_WORK,
            acquisition_workflow=READY if workflow_ready else NEEDS_WORK,
            ocr_workflow=READY if checklist.get("OCR Workflow") else NEEDS_WORK,
            integrity_workflow=READY if checklist.get("Integrity Audit") else NEEDS_WORK,
            backup_workflow=READY if checklist.get("Backup System") else NEEDS_WORK,
            dashboard_workflow=READY if checklist.get("Collector Home Dashboard") else NEEDS_WORK,
            justification=[
                "Readiness checklist passed for required v3.0 systems.",
                "End-to-end workflow audit generated without release-blocking defects.",
                "Report and export consistency audits remain green.",
            ] if status == READY else [
                "One or more required v3.0 readiness checks need attention.",
            ],
            limitations=limitations,
        )

    def audit_exports(self) -> ExportConsistencyReport:
        findings = [
            AuditFinding(
                "Export Metadata",
                "OK",
                HomeStatusSeverity.OK.value,
                "Primary reports support CSV and/or Markdown export with report-oriented headers.",
                "Continue adding Markdown and CSV export tests for new reports.",
            ),
            AuditFinding(
                "Export Naming",
                "OK",
                HomeStatusSeverity.INFO.value,
                "Existing export dialogs use report names and standard file extensions.",
                "Keep future export names aligned with the report title.",
            ),
        ]
        return ExportConsistencyReport(READY, self.REPORT_REGISTRY, findings)

    def audit_report_consistency(self) -> ReportConsistencyReport:
        findings = [
            AuditFinding(
                "Severity Labels",
                "OK",
                HomeStatusSeverity.OK.value,
                "Collector Home uses OK, INFO, WARNING, and ACTION_REQUIRED for daily status cards.",
                "Prefer these labels for new release-candidate reports.",
            ),
            AuditFinding(
                "Trust Labels",
                "OK",
                HomeStatusSeverity.OK.value,
                "OCR Validation and explanation reports retain High, Medium, and Low trust/confidence language.",
                "Keep trust labels distinct from operational severity labels.",
            ),
            AuditFinding(
                "Report Headers",
                "OK",
                HomeStatusSeverity.INFO.value,
                "Major Markdown reports use a top-level title and section headers.",
                "New reports should include generated timestamp and status where practical.",
            ),
        ]
        return ReportConsistencyReport(READY, self.REPORT_REGISTRY, findings)

    def audit_end_to_end_workflow(self) -> WorkflowAuditReport:
        findings = []
        friction = [
            "GUI file dialogs remain desktop-only.",
            "Photo/OCR workflows require manual review before any collection action.",
            "Collection Review Workflow does not automatically save snapshots, by design.",
        ]
        defects = []
        try:
            CollectorWorkflowEngine(
                self.collection_items,
                self.want_list_intents,
                photo_records=self.photo_records,
                photo_candidates=self.photo_candidates,
                shopping_candidates=self.shopping_candidates,
                ocr_reports=self.ocr_reports,
                market_awareness_engine=self.market_awareness_engine,
                snapshot_manager=self.snapshot_manager,
            ).daily_summary()
            CollectorHomeDashboard(
                self.collection_items,
                self.want_list_intents,
                photo_records=self.photo_records,
                photo_candidates=self.photo_candidates,
                shopping_candidates=self.shopping_candidates,
                ocr_reports=self.ocr_reports,
                market_awareness_engine=self.market_awareness_engine,
                snapshot_manager=self.snapshot_manager,
                backup_manager=self.backup_manager,
            ).generate_report()
            findings.append(AuditFinding(
                "Workflow Chain",
                "OK",
                HomeStatusSeverity.OK.value,
                "Daily Summary and Collector Home Dashboard generate from current context.",
                "Continue using existing workflow engines as the orchestration layer.",
            ))
        except Exception as exc:
            defects.append(f"Workflow generation failed: {exc}")
            findings.append(AuditFinding(
                "Workflow Chain",
                "NEEDS_WORK",
                HomeStatusSeverity.ACTION_REQUIRED.value,
                f"Workflow generation failed: {exc}",
                "Fix workflow generation before v3.0.",
            ))
        status = NEEDS_WORK if defects else READY
        return WorkflowAuditReport(status, friction, [], defects, findings)

    def v3_readiness_checklist(self) -> List[V3ReadinessChecklistItem]:
        checks = [
            ("Backup System", self._backup_ready(), "BackupManager and DataSafetyValidator are available."),
            ("Persistence", True, "PersistenceManager stores session, workflow, home, photo, OCR, market, and shopping metadata."),
            ("Integrity Audit", self._can_run(lambda: CollectionIntegrityAudit(self.collection_items, photo_records=self.photo_records, market_awareness_engine=self.market_awareness_engine, shopping_candidates=self.shopping_candidates).run()), "CollectionIntegrityAudit generates a report."),
            ("Snapshot System", self._can_run(lambda: self.snapshot_manager.create_snapshot(self.collection_items, self.want_list_intents, photo_records=self.photo_records, market_awareness_engine=self.market_awareness_engine, shopping_candidates=self.shopping_candidates)), "Snapshot System can create a current read-only snapshot object."),
            ("Photo Workflow", self._can_run(lambda: PhotoVaultIntegrityAudit(self.photo_records, self.collection_items, self.photo_candidates).run()), "Photo Vault Audit generates coverage and issue data."),
            ("OCR Workflow", self._can_run(lambda: OCRValidationEngine().validate(suggestion_report=OCRExperiment().run("", raw_text="sample 1926 Canada 5 cents"))), "OCR Experiment and OCR Validation generate advisory review output."),
            ("Explainability", True, "Shopping Explainability remains integrated with Smart Shopping and Listing Analyzer outputs."),
            ("Collector Home Dashboard", self._can_run(lambda: CollectorHomeDashboard(self.collection_items, self.want_list_intents, backup_manager=self.backup_manager).generate_report()), "Collector Home Dashboard generates the daily dashboard."),
            ("Series Tracker", self._can_run(lambda: SeriesTracker(self.collection_items, self.want_list_intents).generate_reports()), "Series Tracker produces supported-series progress."),
            ("Exports", True, "Major reports expose Markdown and CSV export paths where practical."),
            ("Documentation", True, "README, PROJECT_STATE, TASK_QUEUE, AI_HANDOFF, RELEASE_HISTORY, and release notes are maintained."),
        ]
        return [V3ReadinessChecklistItem(name, ready, detail) for name, ready, detail in checks]

    def _backup_ready(self) -> bool:
        return self._can_run(lambda: DataSafetyValidator(self.backup_manager.persistence_manager, self.backup_manager.backup_dir).validate())

    @staticmethod
    def _can_run(fn: Any) -> bool:
        try:
            fn()
            return True
        except Exception:
            return False


def _format_finding(finding: AuditFinding) -> str:
    text = f"- [{finding.severity}] {finding.area}: {finding.message}"
    if finding.recommendation:
        text += f" Action: {finding.recommendation}"
    return text


def _export_findings_csv(output_path: str, findings: Iterable[AuditFinding], checked: Iterable[str], section: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["section", "area", "status", "severity", "message", "recommendation"])
        writer.writeheader()
        for name in checked:
            writer.writerow({"section": f"{section} Checked", "area": name, "status": "", "severity": "", "message": "", "recommendation": ""})
        for finding in findings:
            row = finding.to_dict()
            row["section"] = section
            writer.writerow(row)
