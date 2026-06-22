"""End-to-end collector workflow integration layer.

This module coordinates the v5 mobile collector workflow without replacing the
underlying engines. It never mutates collection records, performs cloud sync,
purchases, bids, or grades automatically.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from mobile_collection_entry import (
    APPROVE,
    REJECT,
    REVIEW,
    CollectionEntryReport,
    MobileCollectionEntryEngine,
)
from ocr_assisted_identification import OCRIdentificationEngine, OCRIdentificationReport
from photo_capture_workflow import PhotoCaptureReport, PhotoCaptureSession, PhotoCaptureWorkflow
from portfolio_performance import PortfolioPerformanceEngine
from watchlist_engine import Watchlist


STAGE_PHOTO_CAPTURE = "Photo Capture"
STAGE_OCR_REVIEW = "OCR Review"
STAGE_EVIDENCE_REVIEW = "Evidence Review"
STAGE_COLLECTION_CONTEXT = "Collection Context"
STAGE_ENTRY_REVIEW = "Collection Entry Candidate"
STAGE_PORTFOLIO_PREVIEW = "Portfolio Impact Preview"
STAGE_FINAL_REVIEW = "Final Review"

STATUS_PENDING = "PENDING"
STATUS_COMPLETE = "COMPLETE"
STATUS_REJECTED = "REJECTED"
STATUS_REVIEW = "REVIEW"
STATUS_ABANDONED = "ABANDONED"

WORKFLOW_ACTIVE = "ACTIVE"
WORKFLOW_COMPLETE = "COMPLETE"
WORKFLOW_REJECTED = "REJECTED"
WORKFLOW_REVIEW = "REVIEW"

REVIEW_DECISIONS = {APPROVE, REJECT, REVIEW}
ALL_STAGES = [
    STAGE_PHOTO_CAPTURE,
    STAGE_OCR_REVIEW,
    STAGE_EVIDENCE_REVIEW,
    STAGE_COLLECTION_CONTEXT,
    STAGE_ENTRY_REVIEW,
    STAGE_PORTFOLIO_PREVIEW,
    STAGE_FINAL_REVIEW,
]


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


def _clamp(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


@dataclass
class WorkflowStage:
    """Reviewable checkpoint in the collector workflow."""

    name: str
    status: str = STATUS_PENDING
    decision: str = REVIEW
    summary: str = ""
    evidence: List[str] = field(default_factory=list)
    confidence: int = 0
    started_at: str = ""
    completed_at: str = ""
    review_required: bool = True
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = _text(self.name)
        self.status = _text(self.status).upper() or STATUS_PENDING
        self.decision = _text(self.decision).upper() or REVIEW
        if self.decision not in REVIEW_DECISIONS:
            self.decision = REVIEW
        self.summary = _text(self.summary)
        self.evidence = _dedupe(self.evidence)
        self.confidence = _clamp(self.confidence)
        self.started_at = _text(self.started_at) or _now_iso()
        self.completed_at = _text(self.completed_at)
        self.warnings = _dedupe(self.warnings)

    def mark(self, decision: str = REVIEW, summary: str = "", evidence: Optional[Iterable[str]] = None, confidence: Optional[int] = None) -> "WorkflowStage":
        decision = _text(decision).upper() or REVIEW
        if decision not in REVIEW_DECISIONS:
            decision = REVIEW
        self.decision = decision
        self.status = STATUS_COMPLETE if decision == APPROVE else STATUS_REJECTED if decision == REJECT else STATUS_REVIEW
        self.completed_at = _now_iso()
        if summary:
            self.summary = _text(summary)
        if evidence is not None:
            self.evidence = _dedupe(evidence)
        if confidence is not None:
            self.confidence = _clamp(confidence)
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "decision": self.decision,
            "summary": self.summary,
            "evidence": "; ".join(self.evidence),
            "confidence": self.confidence,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "review_required": "YES" if self.review_required else "NO",
            "warnings": "; ".join(self.warnings),
        }


@dataclass
class WorkflowSession:
    """Resumable end-to-end collector workflow state."""

    session_id: str
    subject: str = ""
    status: str = WORKFLOW_ACTIVE
    started_at: str = ""
    updated_at: str = ""
    location: str = ""
    notes: str = ""
    photo_sessions: List[PhotoCaptureSession] = field(default_factory=list)
    ocr_report: Optional[OCRIdentificationReport] = None
    entry_report: Optional[CollectionEntryReport] = None
    stages: List[WorkflowStage] = field(default_factory=list)
    portfolio_previews: List[str] = field(default_factory=list)
    final_review_decision: str = REVIEW
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.session_id = _text(self.session_id) or f"workflow-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.subject = _text(self.subject)
        self.status = _text(self.status).upper() or WORKFLOW_ACTIVE
        self.started_at = _text(self.started_at) or _now_iso()
        self.updated_at = _text(self.updated_at) or self.started_at
        self.location = _text(self.location)
        self.notes = _text(self.notes)
        self.photo_sessions = [session if isinstance(session, PhotoCaptureSession) else PhotoCaptureSession(**session) for session in self.photo_sessions]
        if self.ocr_report is not None and not isinstance(self.ocr_report, OCRIdentificationReport):
            self.ocr_report = OCRIdentificationReport(**self.ocr_report)
        if self.entry_report is not None and not isinstance(self.entry_report, CollectionEntryReport):
            self.entry_report = CollectionEntryReport(**self.entry_report)
        self.stages = [stage if isinstance(stage, WorkflowStage) else WorkflowStage(**stage) for stage in self.stages]
        self.portfolio_previews = _dedupe(self.portfolio_previews)
        self.final_review_decision = _text(self.final_review_decision).upper() or REVIEW
        if self.final_review_decision not in REVIEW_DECISIONS:
            self.final_review_decision = REVIEW
        self.warnings = _dedupe([*self.warnings, "Collector review required before any collection change"])

    @property
    def completed_stage_count(self) -> int:
        return sum(1 for stage in self.stages if stage.status == STATUS_COMPLETE)

    @property
    def review_escalation_count(self) -> int:
        return sum(1 for stage in self.stages if stage.decision == REVIEW)

    @property
    def rejected_stage_count(self) -> int:
        return sum(1 for stage in self.stages if stage.decision == REJECT)

    def stage(self, name: str) -> Optional[WorkflowStage]:
        needle = _text(name).lower()
        return next((stage for stage in self.stages if stage.name.lower() == needle), None)

    def add_stage(self, stage: WorkflowStage) -> WorkflowStage:
        existing = self.stage(stage.name)
        if existing:
            self.stages = [stage if item.name == existing.name else item for item in self.stages]
        else:
            self.stages.append(stage)
        self.updated_at = _now_iso()
        self._refresh_status()
        return stage

    def review_stage(self, stage_name: str, decision: str = REVIEW, reasoning: str = "") -> WorkflowStage:
        stage = self.stage(stage_name)
        if stage is None:
            stage = WorkflowStage(stage_name)
            self.stages.append(stage)
        stage.mark(decision=decision, summary=reasoning or stage.summary)
        if stage.name == STAGE_FINAL_REVIEW:
            self.final_review_decision = stage.decision
        self.updated_at = _now_iso()
        self._refresh_status()
        return stage

    def _refresh_status(self) -> None:
        if any(stage.decision == REJECT for stage in self.stages):
            self.status = WORKFLOW_REJECTED
        elif self.final_review_decision == APPROVE and self.stages and all(stage.decision == APPROVE for stage in self.stages):
            self.status = WORKFLOW_COMPLETE
        elif any(stage.decision == REVIEW for stage in self.stages):
            self.status = WORKFLOW_REVIEW
        else:
            self.status = WORKFLOW_ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "subject": self.subject,
            "status": self.status,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "location": self.location,
            "notes": self.notes,
            "photo_sessions": [session.to_dict() for session in self.photo_sessions],
            "ocr_report": self.ocr_report.to_dict() if self.ocr_report else {},
            "entry_report": self.entry_report.to_dict() if self.entry_report else {},
            "stages": [stage.to_dict() for stage in self.stages],
            "portfolio_previews": "; ".join(self.portfolio_previews),
            "final_review_decision": self.final_review_decision,
            "completed_stage_count": self.completed_stage_count,
            "review_escalation_count": self.review_escalation_count,
            "rejected_stage_count": self.rejected_stage_count,
            "warnings": "; ".join(self.warnings),
        }


@dataclass
class WorkflowCompletionReport:
    """Completion summary for one collector workflow session."""

    session: WorkflowSession
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.session, WorkflowSession):
            self.session = WorkflowSession(**self.session)
        self.generated_at = _text(self.generated_at) or _now_iso()

    @property
    def stage_count(self) -> int:
        return len(self.session.stages)

    @property
    def completed_stage_count(self) -> int:
        return self.session.completed_stage_count

    @property
    def review_escalation_count(self) -> int:
        return self.session.review_escalation_count

    @property
    def rejected_stage_count(self) -> int:
        return self.session.rejected_stage_count

    @property
    def approved(self) -> bool:
        return self.session.status == WORKFLOW_COMPLETE

    def to_dict(self) -> Dict[str, Any]:
        data = self.session.to_dict()
        data.update({
            "generated_at": self.generated_at,
            "stage_count": self.stage_count,
            "approved": "YES" if self.approved else "NO",
        })
        return data

    def format_markdown(self) -> str:
        lines = [
            "# Collector Workflow Integration Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Session: {self.session.session_id}",
            f"- Subject: {self.session.subject or 'None'}",
            f"- Status: {self.session.status}",
            f"- Stages: {self.completed_stage_count}/{self.stage_count} complete",
            f"- Review escalations: {self.review_escalation_count}",
            f"- Rejected stages: {self.rejected_stage_count}",
            "- Collection mutation performed: NO",
            "",
            "## Workflow Stages",
            "",
        ]
        if not self.session.stages:
            lines.append("- No workflow stages recorded.")
        for stage in self.session.stages:
            lines.append(f"- {stage.name}: {stage.decision} ({stage.status}); confidence {stage.confidence}")
            if stage.summary:
                lines.append(f"  - Summary: {stage.summary}")
            if stage.evidence:
                lines.append(f"  - Evidence: {'; '.join(stage.evidence)}")
        lines.extend(["", "## Portfolio Preview", ""])
        lines.extend(f"- {item}" for item in self.session.portfolio_previews) if self.session.portfolio_previews else lines.append("- None.")
        if self.session.entry_report:
            lines.extend(["", "## Entry Candidates", "", f"- Entry candidates: {self.session.entry_report.candidate_count}"])
            for candidate in self.session.entry_report.candidates[:5]:
                lines.append(f"- {candidate.title}: {candidate.collection_status}; {candidate.confidence_summary()}")
        lines.extend(["", "## Boundaries", ""])
        lines.extend(f"- {warning}" for warning in self.session.warnings)
        lines.append("- Approval is a workflow checkpoint only; records must be saved manually outside this report.")
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        fieldnames = [
            "session_id", "subject", "workflow_status", "stage_name", "stage_status", "decision",
            "confidence", "summary", "evidence", "portfolio_previews", "warnings",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            if not self.session.stages:
                writer.writerow({"session_id": self.session.session_id, "subject": self.session.subject, "workflow_status": self.session.status})
            for stage in self.session.stages:
                writer.writerow({
                    "session_id": self.session.session_id,
                    "subject": self.session.subject,
                    "workflow_status": self.session.status,
                    "stage_name": stage.name,
                    "stage_status": stage.status,
                    "decision": stage.decision,
                    "confidence": stage.confidence,
                    "summary": stage.summary,
                    "evidence": "; ".join(stage.evidence),
                    "portfolio_previews": "; ".join(self.session.portfolio_previews),
                    "warnings": "; ".join(self.session.warnings),
                })
        return True


@dataclass
class WorkflowHealthReport:
    """Aggregate workflow quality and completion metrics."""

    sessions: List[WorkflowSession] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.sessions = [session if isinstance(session, WorkflowSession) else WorkflowSession(**session) for session in self.sessions]
        self.generated_at = _text(self.generated_at) or _now_iso()

    @property
    def total_workflows(self) -> int:
        return len(self.sessions)

    @property
    def completed_workflows(self) -> int:
        return sum(1 for session in self.sessions if session.status == WORKFLOW_COMPLETE)

    @property
    def abandoned_workflows(self) -> int:
        return sum(1 for session in self.sessions if session.status == STATUS_ABANDONED)

    @property
    def review_escalations(self) -> int:
        return sum(session.review_escalation_count for session in self.sessions)

    def confidence_distribution(self) -> Dict[str, int]:
        distribution = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for stage in [stage for session in self.sessions for stage in session.stages]:
            if stage.confidence >= 75:
                distribution["HIGH"] += 1
            elif stage.confidence >= 45:
                distribution["MEDIUM"] += 1
            else:
                distribution["LOW"] += 1
        return distribution

    def stage_completion_rates(self) -> Dict[str, str]:
        rates: Dict[str, str] = {}
        total = max(1, self.total_workflows)
        for stage_name in ALL_STAGES:
            completed = sum(1 for session in self.sessions for stage in session.stages if stage.name == stage_name and stage.status == STATUS_COMPLETE)
            rates[stage_name] = f"{round((completed / total) * 100)}%"
        return rates

    def to_dict(self) -> Dict[str, Any]:
        distribution = self.confidence_distribution()
        return {
            "generated_at": self.generated_at,
            "total_workflows": self.total_workflows,
            "completed_workflows": self.completed_workflows,
            "abandoned_workflows": self.abandoned_workflows,
            "review_escalations": self.review_escalations,
            "confidence_high": distribution["HIGH"],
            "confidence_medium": distribution["MEDIUM"],
            "confidence_low": distribution["LOW"],
            "stage_completion_rates": self.stage_completion_rates(),
        }

    def format_markdown(self) -> str:
        data = self.to_dict()
        lines = [
            "# Collector Workflow Health Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Total workflows: {self.total_workflows}",
            f"- Completed workflows: {self.completed_workflows}",
            f"- Abandoned workflows: {self.abandoned_workflows}",
            f"- Review escalations: {self.review_escalations}",
            "",
            "## Confidence Distribution",
            "",
            f"- HIGH: {data['confidence_high']}",
            f"- MEDIUM: {data['confidence_medium']}",
            f"- LOW: {data['confidence_low']}",
            "",
            "## Stage Completion Rates",
            "",
        ]
        lines.extend(f"- {name}: {rate}" for name, rate in self.stage_completion_rates().items())
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        fieldnames = ["metric", "value"]
        data = self.to_dict()
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for key, value in data.items():
                if key == "stage_completion_rates":
                    for stage, rate in value.items():
                        writer.writerow({"metric": f"stage_{stage}", "value": rate})
                else:
                    writer.writerow({"metric": key, "value": value})
        return True


class CollectorWorkflowIntegrationEngine:
    """Coordinate the complete v5 collector workflow without side effects."""

    def __init__(
        self,
        collection_items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        watchlists: Optional[Sequence[Watchlist]] = None,
        photo_capture_workflow: Optional[PhotoCaptureWorkflow] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.watchlists = list(watchlists or [])
        self.photo_capture_workflow = photo_capture_workflow or PhotoCaptureWorkflow()
        self.ocr_engine = OCRIdentificationEngine(self.collection_items, self.want_list_intents, self.watchlists)
        self.entry_engine = MobileCollectionEntryEngine(self.collection_items, self.want_list_intents, self.watchlists)

    def start_session(self, subject: str = "", location: str = "", notes: str = "") -> WorkflowSession:
        return WorkflowSession(
            session_id=f"collector-workflow-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            subject=subject,
            location=location,
            notes=notes,
        )

    def run_workflow(
        self,
        subject: str = "",
        raw_text: str = "",
        front_path: str = "",
        back_path: str = "",
        location: str = "",
        acquisition_source: str = "Collector Workflow Integration",
    ) -> WorkflowCompletionReport:
        session = self.start_session(subject=subject or raw_text, location=location)
        if front_path or back_path:
            photo_session = self.photo_capture_workflow.capture_coin_pair(subject or raw_text, front_path=front_path, back_path=back_path, location=location)
            photo_session.mark_ready_for_ocr()
            session.photo_sessions.append(photo_session)
        photo_report = PhotoCaptureReport(session.photo_sessions)
        session.add_stage(WorkflowStage(
            STAGE_PHOTO_CAPTURE,
            summary=f"{photo_report.total_photos} photo(s), {photo_report.ready_for_ocr_count} ready for OCR",
            evidence=[f"sessions {photo_report.total_sessions}", f"photos {photo_report.total_photos}"],
            confidence=90 if photo_report.total_photos else 55,
        ).mark(APPROVE if raw_text or photo_report.total_photos else REVIEW))

        ocr_report = self._ocr_report(session, raw_text)
        session.ocr_report = ocr_report
        first_ocr = ocr_report.candidates[0] if ocr_report.candidates else None
        session.add_stage(WorkflowStage(
            STAGE_OCR_REVIEW,
            summary=f"{ocr_report.candidate_count} OCR identification candidate(s)",
            evidence=[candidate.format_brief() for candidate in ocr_report.candidates[:3]],
            confidence=getattr(first_ocr, "confidence_score", 0),
        ).mark(APPROVE if first_ocr and first_ocr.confidence_score >= 45 else REVIEW))
        session.add_stage(WorkflowStage(
            STAGE_EVIDENCE_REVIEW,
            summary=self._evidence_summary(ocr_report),
            evidence=self._evidence_rows(ocr_report),
            confidence=getattr(first_ocr, "confidence_score", 0),
        ).mark(APPROVE if first_ocr and first_ocr.confidence_score >= 60 else REVIEW))
        session.add_stage(WorkflowStage(
            STAGE_COLLECTION_CONTEXT,
            summary=self._collection_context_summary(ocr_report),
            evidence=[candidate.collection_relevance for candidate in ocr_report.candidates[:3]],
            confidence=getattr(first_ocr, "confidence_score", 0),
        ).mark(APPROVE if first_ocr else REVIEW))

        entry_report = self.entry_engine.from_ocr_report(ocr_report, acquisition_source=acquisition_source)
        session.entry_report = entry_report
        first_entry = entry_report.candidates[0] if entry_report.candidates else None
        session.add_stage(WorkflowStage(
            STAGE_ENTRY_REVIEW,
            summary=f"{entry_report.candidate_count} collection entry candidate(s); no automatic insertion",
            evidence=[candidate.title for candidate in entry_report.candidates[:3]],
            confidence=getattr(first_entry, "overall_confidence", 0),
        ).mark(APPROVE if first_entry and first_entry.overall_confidence >= 45 else REVIEW))

        session.portfolio_previews = self._portfolio_preview(entry_report)
        session.add_stage(WorkflowStage(
            STAGE_PORTFOLIO_PREVIEW,
            summary="; ".join(session.portfolio_previews[:3]) or "Portfolio preview unavailable",
            evidence=session.portfolio_previews,
            confidence=70 if session.portfolio_previews else 35,
        ).mark(APPROVE if session.portfolio_previews else REVIEW))
        session.add_stage(WorkflowStage(
            STAGE_FINAL_REVIEW,
            summary="Final collector review required before any manual save",
            evidence=["No collection mutation performed"],
            confidence=min([stage.confidence for stage in session.stages] or [0]),
        ).mark(REVIEW))
        return WorkflowCompletionReport(session)

    def resume_session(self, data: Dict[str, Any]) -> WorkflowSession:
        allowed = {field.name for field in fields(WorkflowSession)}
        payload = {key: value for key, value in dict(data or {}).items() if key in allowed}
        payload["ocr_report"] = self._restore_ocr_report(payload.get("ocr_report"))
        payload["entry_report"] = self._restore_entry_report(payload.get("entry_report"))
        return WorkflowSession(**payload)

    def review_stage(self, session: WorkflowSession, stage_name: str, decision: str = REVIEW, reasoning: str = "") -> WorkflowStage:
        return session.review_stage(stage_name, decision, reasoning)

    def completion_report(self, session: WorkflowSession) -> WorkflowCompletionReport:
        return WorkflowCompletionReport(session)

    def health_report(self, sessions: Iterable[WorkflowSession]) -> WorkflowHealthReport:
        return WorkflowHealthReport(list(sessions or []))


    def _restore_ocr_report(self, value: Any) -> Optional[OCRIdentificationReport]:
        if not value:
            return None
        if isinstance(value, OCRIdentificationReport):
            return value
        try:
            from ocr_assisted_identification import IdentificationEvidence, OCRIdentificationCandidate
            candidates = []
            for row in value.get("candidates", []) or []:
                evidence = IdentificationEvidence(
                    ocr_text_used=row.get("evidence_ocr_text_used", ""),
                    validation_score=row.get("evidence_validation_score", 0),
                    trust_level=row.get("evidence_trust_level", "LOW"),
                    supporting_keywords=str(row.get("evidence_supporting_keywords", "")).split("; ") if row.get("evidence_supporting_keywords") else [],
                    conflicts_detected=str(row.get("evidence_conflicts_detected", "")).split("; ") if row.get("evidence_conflicts_detected") else [],
                    missing_evidence=str(row.get("evidence_missing_evidence", "")).split("; ") if row.get("evidence_missing_evidence") else [],
                )
                candidates.append(OCRIdentificationCandidate(
                    source_photo_id=row.get("source_photo_id", ""),
                    image_path=row.get("image_path", ""),
                    year=row.get("year", ""),
                    denomination=row.get("denomination", ""),
                    country=row.get("country", ""),
                    monarch=row.get("monarch", ""),
                    banknote_prefix=row.get("banknote_prefix", ""),
                    certification_number=row.get("certification_number", ""),
                    series_type=row.get("series_type", ""),
                    silver_indicator=row.get("silver_indicator", ""),
                    possible_variety_keywords=str(row.get("possible_variety_keywords", "")).split("; ") if row.get("possible_variety_keywords") else [],
                    confidence_level=row.get("confidence_level", "LOW"),
                    confidence_score=row.get("confidence_score", 0),
                    confidence_reason=row.get("confidence_reason", ""),
                    collection_relevance=row.get("collection_relevance", ""),
                    collection_status=row.get("collection_status", ""),
                    watchlist_matches=str(row.get("watchlist_matches", "")).split("; ") if row.get("watchlist_matches") else [],
                    review_status=row.get("review_status", ""),
                    warnings=str(row.get("warnings", "")).split("; ") if row.get("warnings") else [],
                    evidence=evidence,
                ))
            return OCRIdentificationReport(candidates=candidates, generated_at=value.get("generated_at", ""), warnings=str(value.get("warnings", "")).split("; ") if value.get("warnings") else [])
        except Exception:
            return None

    def _restore_entry_report(self, value: Any) -> Optional[CollectionEntryReport]:
        if not value:
            return None
        if isinstance(value, CollectionEntryReport):
            return value
        try:
            from mobile_collection_entry import CollectionEntryCandidate, CollectionEntryReview
            candidates = []
            for row in value.get("candidates", []) or []:
                confidence = {}
                for part in str(row.get("field_confidence", "")).split("; "):
                    if ":" in part:
                        key, score = part.split(":", 1)
                        confidence[key] = _clamp(score)
                candidates.append(CollectionEntryCandidate(
                    candidate_id=row.get("candidate_id", ""),
                    country=row.get("country", ""),
                    year=row.get("year", ""),
                    denomination=row.get("denomination", ""),
                    series=row.get("series", ""),
                    monarch=row.get("monarch", ""),
                    variety=row.get("variety", ""),
                    grade_estimate=row.get("grade_estimate", ""),
                    certification_number=row.get("certification_number", ""),
                    notes=row.get("notes", ""),
                    acquisition_source=row.get("acquisition_source", ""),
                    field_confidence=confidence,
                    overall_confidence=row.get("overall_confidence", 0),
                    confidence_level=row.get("confidence_level", "LOW"),
                    evidence_summary=row.get("evidence_summary", ""),
                    collection_context=row.get("collection_context", ""),
                    collection_status=row.get("collection_status", ""),
                    portfolio_impact_preview=str(row.get("portfolio_impact_preview", "")).split("; ") if row.get("portfolio_impact_preview") else [],
                    review_status=row.get("review_status", ""),
                    warnings=str(row.get("warnings", "")).split("; ") if row.get("warnings") else [],
                    source_identification_title=row.get("source_identification_title", ""),
                ))
            reviews = [CollectionEntryReview(**row) for row in value.get("reviews", []) or []]
            return CollectionEntryReport(candidates=candidates, reviews=reviews, generated_at=value.get("generated_at", ""), warnings=str(value.get("warnings", "")).split("; ") if value.get("warnings") else [])
        except Exception:
            return None

    def _ocr_report(self, session: WorkflowSession, raw_text: str) -> OCRIdentificationReport:
        if session.photo_sessions:
            latest = session.photo_sessions[-1]
            return self.ocr_engine.identify_from_session(latest, raw_text_by_photo_id={photo.photo_id: raw_text for photo in latest.photos if raw_text})
        return self.ocr_engine.identify(raw_text=raw_text or session.subject or "manual collector workflow")

    def _evidence_summary(self, report: OCRIdentificationReport) -> str:
        if not report.candidates:
            return "No OCR evidence available."
        candidate = report.candidates[0]
        return f"Evidence trust {candidate.evidence.trust_level} ({candidate.evidence.validation_score}/100); {candidate.confidence_reason}"

    def _evidence_rows(self, report: OCRIdentificationReport) -> List[str]:
        rows: List[str] = []
        for candidate in report.candidates[:3]:
            rows.extend(candidate.evidence.supporting_keywords[:5])
            rows.extend(candidate.evidence.conflicts_detected[:3])
            rows.extend(f"missing {item}" for item in candidate.evidence.missing_evidence[:3])
        return _dedupe(rows)

    def _collection_context_summary(self, report: OCRIdentificationReport) -> str:
        if not report.candidates:
            return "Collection context unavailable."
        return "; ".join(_dedupe([candidate.collection_status for candidate in report.candidates]))

    def _portfolio_preview(self, report: CollectionEntryReport) -> List[str]:
        previews = [item for candidate in report.candidates for item in candidate.portfolio_impact_preview]
        if previews:
            return _dedupe(previews)
        try:
            performance = PortfolioPerformanceEngine(self.collection_items, self.want_list_intents).generate_report()
            return [
                "Preview only; no collection mutation performed",
                f"Current portfolio health: {performance.health_score.score}/100",
                "Collection value impact: no automatic valuation assigned",
            ]
        except Exception:
            return ["Preview only; portfolio preview unavailable"]
