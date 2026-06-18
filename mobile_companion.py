"""Mobile companion prototype workflow.

This module is a local desktop prototype. It does not create a mobile app,
web app, API server, OCR, image recognition, scraping, live pricing, cloud
sync, or a new storage backend.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from acquisition_impact import AcquisitionImpactEngine
from listing_analyzer import ListingAnalyzer, ListingCandidate, is_valid_listing_url
from market_awareness import MarketAwarenessEngine
from photo_vault import PhotoRecord, PhotoVault
from smart_shopping_assistant import ShoppingCandidate, SmartShoppingAssistant


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    return round(float(cleaned), 2) if cleaned else 0.0


def _first(values: Iterable[str]) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


@dataclass
class MobileCandidateEntry:
    """Minimal dealer-table input for quick candidate analysis."""

    item_title: str
    asking_price: float = 0.0
    shipping: float = 0.0
    notes: str = ""
    url: str = ""
    photo_reference_id: str = ""
    source: str = "Mobile Companion"
    created_at: str = ""
    total_cost: float = field(init=False)

    def __post_init__(self) -> None:
        self.item_title = (self.item_title or "").strip()
        self.asking_price = _money(self.asking_price)
        self.shipping = _money(self.shipping)
        self.notes = (self.notes or "").strip()
        self.url = (self.url or "").strip()
        self.photo_reference_id = (self.photo_reference_id or "").strip()
        self.source = (self.source or "Mobile Companion").strip()
        self.created_at = self.created_at or _now_iso()
        self.total_cost = round(self.asking_price + self.shipping, 2)

    def validate(self) -> List[str]:
        warnings = []
        if not self.item_title:
            warnings.append("Missing item title")
        if self.asking_price <= 0:
            warnings.append("Missing asking price")
        if not is_valid_listing_url(self.url):
            warnings.append("Invalid URL format")
        return warnings

    def to_listing_candidate(self) -> ListingCandidate:
        return ListingCandidate(
            title=self.item_title,
            price=self.asking_price,
            shipping=self.shipping,
            url=self.url,
            notes=self.notes,
            source=self.source,
            description=self.notes,
            created_at=self.created_at,
        )

    def to_shopping_candidate(self) -> ShoppingCandidate:
        listing = self.to_listing_candidate()
        candidate = ShoppingCandidate.from_listing(listing)
        if self.photo_reference_id:
            candidate.photo_reference_ids = [self.photo_reference_id]
        candidate.recommendation_source = "Mobile Companion"
        return candidate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_title": self.item_title,
            "asking_price": self.asking_price,
            "shipping": self.shipping,
            "total_cost": self.total_cost,
            "notes": self.notes,
            "url": self.url,
            "photo_reference_id": self.photo_reference_id,
            "source": self.source,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "MobileCandidateEntry":
        return cls(
            item_title=str(payload.get("item_title") or ""),
            asking_price=float(payload.get("asking_price") or 0.0),
            shipping=float(payload.get("shipping") or 0.0),
            notes=str(payload.get("notes") or ""),
            url=str(payload.get("url") or ""),
            photo_reference_id=str(payload.get("photo_reference_id") or ""),
            source=str(payload.get("source") or "Mobile Companion"),
            created_at=str(payload.get("created_at") or ""),
        )


@dataclass
class MobileAnalysisReport:
    """Concise mobile-style recommendation output."""

    candidate: MobileCandidateEntry
    recommendation: str
    impact_score: int
    quality_delta: int
    series_delta: float
    want_list_status: str
    top_reason: str
    recommendation_summary: str
    warning_flags: List[str] = field(default_factory=list)
    max_rational_price: float = 0.0
    total_cost: float = 0.0
    photo_reference_status: str = ""
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()
        self.recommendation = self._normalize_recommendation(self.recommendation)
        self.impact_score = int(self.impact_score or 0)
        self.quality_delta = int(self.quality_delta or 0)
        self.series_delta = round(float(self.series_delta or 0.0), 1)
        self.max_rational_price = round(float(self.max_rational_price or 0.0), 2)
        self.total_cost = round(float(self.total_cost or self.candidate.total_cost or 0.0), 2)
        self.warning_flags = [str(flag) for flag in self.warning_flags if str(flag).strip()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "recommendation": self.recommendation,
            "impact_score": self.impact_score,
            "quality_delta": self.quality_delta,
            "series_delta": self.series_delta,
            "want_list_status": self.want_list_status,
            "top_reason": self.top_reason,
            "recommendation_summary": self.recommendation_summary,
            "warning_flags": list(self.warning_flags),
            "max_rational_price": self.max_rational_price,
            "total_cost": self.total_cost,
            "photo_reference_status": self.photo_reference_status,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "MobileAnalysisReport":
        return cls(
            candidate=MobileCandidateEntry.from_dict(payload.get("candidate") or {}),
            recommendation=str(payload.get("recommendation") or "REVIEW"),
            impact_score=int(payload.get("impact_score") or 0),
            quality_delta=int(payload.get("quality_delta") or 0),
            series_delta=float(payload.get("series_delta") or 0.0),
            want_list_status=str(payload.get("want_list_status") or "WANT_LIST_UNAVAILABLE"),
            top_reason=str(payload.get("top_reason") or ""),
            recommendation_summary=str(payload.get("recommendation_summary") or ""),
            warning_flags=list(payload.get("warning_flags") or []),
            max_rational_price=float(payload.get("max_rational_price") or 0.0),
            total_cost=float(payload.get("total_cost") or 0.0),
            photo_reference_status=str(payload.get("photo_reference_status") or ""),
            generated_at=str(payload.get("generated_at") or ""),
        )

    def format_markdown(self) -> str:
        lines = [
            "# Mobile Analysis Report",
            "",
            f"- Candidate: {self.candidate.item_title}",
            f"- Recommendation: {self.recommendation}",
            f"- Total cost: ${self.total_cost:.2f}",
            f"- Max rational price: ${self.max_rational_price:.2f}",
            f"- Impact score: {self.impact_score}",
            f"- Quality delta: {self.quality_delta:+d}",
            f"- Series delta: {self.series_delta:+g}%",
            f"- WANT_LIST status: {self.want_list_status}",
            f"- Top reason: {self.top_reason or 'No reason available'}",
            f"- Summary: {self.recommendation_summary}",
            f"- Photo reference: {self.photo_reference_status or 'No photo reference'}",
            "",
            "## Warnings",
            "",
        ]
        lines.extend(f"- {warning}" for warning in self.warning_flags) if self.warning_flags else lines.append("- None")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _normalize_recommendation(value: str) -> str:
        text = (value or "").strip().upper()
        if text in {"MUST BUY", "STRONG BUY"}:
            return "BUY"
        if text in {"BUY", "PASS", "NEGOTIATE", "WATCH", "REVIEW"}:
            return text
        return "REVIEW"


class StorageProvider:
    """Desktop storage adapter around the existing Persistence Layer."""

    def __init__(self, persistence_manager: Optional[Any] = None):
        self.persistence_manager = persistence_manager

    def load_state(self) -> Any:
        manager = self._manager()
        return manager.load_state()

    def save_mobile_activity(
        self,
        candidates: Iterable[MobileCandidateEntry],
        reports: Iterable[MobileAnalysisReport],
    ) -> Any:
        manager = self._manager()
        loaded = manager.load_state()
        state = loaded.state if loaded.success and loaded.state else manager.create_state()
        state.recent_mobile_candidates.extend(list(candidates or []))
        state.recent_mobile_recommendations.extend(list(reports or []))
        return manager.save_state(state)

    def _manager(self) -> Any:
        if self.persistence_manager:
            return self.persistence_manager
        from persistence_manager import PersistenceManager

        self.persistence_manager = PersistenceManager()
        return self.persistence_manager


class PhotoProvider:
    """Resolve photo reference IDs from existing Photo Vault metadata only."""

    def __init__(self, photo_records: Optional[Iterable[PhotoRecord]] = None):
        self.photo_vault = PhotoVault(photo_records or [])

    def resolve_photo_reference(self, photo_reference_id: str) -> Optional[PhotoRecord]:
        needle = (photo_reference_id or "").strip()
        if not needle:
            return None
        for record in self.photo_vault.records:
            if needle in {
                record.linked_candidate_id,
                record.linked_collection_item_id,
                record.file_path,
                record.iccs_number,
                record.pcgs_number,
                record.ngc_number,
            }:
                return record
        matches = self.photo_vault.search(needle)
        return matches[0] if matches else None

    def describe_photo_reference(self, photo_reference_id: str) -> str:
        if not photo_reference_id:
            return "No photo reference"
        record = self.resolve_photo_reference(photo_reference_id)
        if not record:
            return f"Photo reference not found: {photo_reference_id}"
        label = record.linked_coin_name or record.file_path
        return f"Photo reference found: {label}"


class ExportProvider:
    """Local CSV/Markdown export adapter for mobile companion reports."""

    def export_analysis_markdown(self, output_path: str, report: MobileAnalysisReport) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(report.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting mobile analysis markdown: {exc}")
            return False

    def export_analysis_csv(self, output_path: str, report: MobileAnalysisReport) -> bool:
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "item_title",
                    "recommendation",
                    "impact_score",
                    "quality_delta",
                    "series_delta",
                    "want_list_status",
                    "top_reason",
                    "total_cost",
                    "max_rational_price",
                    "photo_reference_status",
                    "warnings",
                ])
                writer.writeheader()
                writer.writerow({
                    "item_title": report.candidate.item_title,
                    "recommendation": report.recommendation,
                    "impact_score": report.impact_score,
                    "quality_delta": report.quality_delta,
                    "series_delta": report.series_delta,
                    "want_list_status": report.want_list_status,
                    "top_reason": report.top_reason,
                    "total_cost": report.total_cost,
                    "max_rational_price": report.max_rational_price,
                    "photo_reference_status": report.photo_reference_status,
                    "warnings": "; ".join(report.warning_flags),
                })
            return True
        except Exception as exc:
            print(f"Error exporting mobile analysis CSV: {exc}")
            return False

    def export_phone_workflow_markdown(self, output_path: str, report: "PhoneWorkflowReport") -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(report.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting phone workflow markdown: {exc}")
            return False

    def export_phone_workflow_csv(self, output_path: str, report: "PhoneWorkflowReport") -> bool:
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "recommendation",
                    "rationale",
                    "impact",
                    "required_steps",
                    "workflow_complexity",
                    "friction_notes",
                ])
                writer.writeheader()
                writer.writerow({
                    "recommendation": report.recommendation,
                    "rationale": report.rationale,
                    "impact": report.impact,
                    "required_steps": report.required_steps,
                    "workflow_complexity": report.workflow_complexity,
                    "friction_notes": "; ".join(report.friction_notes),
                })
            return True
        except Exception as exc:
            print(f"Error exporting phone workflow CSV: {exc}")
            return False


class MobileCompanionWorkflow:
    """Single candidate -> analysis -> recommendation workflow."""

    def __init__(
        self,
        collection_items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        photo_records: Optional[Iterable[PhotoRecord]] = None,
        storage_provider: Optional[StorageProvider] = None,
        photo_provider: Optional[PhotoProvider] = None,
        export_provider: Optional[ExportProvider] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()
        self.storage_provider = storage_provider or StorageProvider()
        self.photo_provider = photo_provider or PhotoProvider(photo_records or [])
        self.export_provider = export_provider or ExportProvider()

    def analyze(self, entry: MobileCandidateEntry, persist: bool = False) -> MobileAnalysisReport:
        listing = entry.to_listing_candidate()
        listing_result = ListingAnalyzer(self.collection_items, self.want_list_intents).analyze(listing)
        impact = listing_result.acquisition_impact_report or AcquisitionImpactEngine(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).evaluate(listing_result.candidate)
        shopping_report = SmartShoppingAssistant(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).generate_report([entry.to_shopping_candidate()], include_want_list_targets=False, limit=1)
        shopping_top = shopping_report.best_next_purchase
        acquisition = listing_result.acquisition_decision
        top_reason = self._top_reason(
            shopping_top.reasons if shopping_top else [],
            impact.recommendation_reasoning,
            acquisition.priority_reasons,
            listing_result.warnings,
        )
        warnings = self._dedupe(entry.validate() + listing_result.warnings + acquisition.warning_flags)
        photo_status = self.photo_provider.describe_photo_reference(entry.photo_reference_id)
        if photo_status.startswith("Photo reference not found"):
            warnings.append(photo_status)
        report = MobileAnalysisReport(
            candidate=entry,
            recommendation=acquisition.recommendation,
            impact_score=impact.impact_score,
            quality_delta=impact.quality_delta,
            series_delta=impact.completion_delta,
            want_list_status=acquisition.want_list_status,
            top_reason=top_reason,
            recommendation_summary=self._summary(entry, acquisition.recommendation, top_reason, impact.impact_score),
            warning_flags=self._dedupe(warnings),
            max_rational_price=acquisition.max_rational_price,
            total_cost=entry.total_cost,
            photo_reference_status=photo_status,
        )
        if persist:
            self.storage_provider.save_mobile_activity([entry], [report])
        return report

    def export_analysis_csv(self, output_path: str, report: MobileAnalysisReport) -> bool:
        return self.export_provider.export_analysis_csv(output_path, report)

    def export_analysis_markdown(self, output_path: str, report: MobileAnalysisReport) -> bool:
        return self.export_provider.export_analysis_markdown(output_path, report)

    @staticmethod
    def _top_reason(*groups: Iterable[str]) -> str:
        return _first(item for group in groups for item in group) or "Analysis completed with existing collector logic"

    @staticmethod
    def _summary(entry: MobileCandidateEntry, recommendation: str, top_reason: str, impact_score: int) -> str:
        return f"{recommendation}: {entry.item_title} has impact score {impact_score}. {top_reason}"

    @staticmethod
    def _dedupe(values: Iterable[str]) -> List[str]:
        seen = set()
        result = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result


@dataclass
class PhoneWorkflowReport:
    recommendation: str
    rationale: str
    impact: str
    required_steps: int
    workflow_complexity: str
    friction_notes: List[str] = field(default_factory=list)
    analysis_report: Optional[MobileAnalysisReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation": self.recommendation,
            "rationale": self.rationale,
            "impact": self.impact,
            "required_steps": self.required_steps,
            "workflow_complexity": self.workflow_complexity,
            "friction_notes": list(self.friction_notes),
            "analysis_report": self.analysis_report.to_dict() if self.analysis_report else None,
        }

    def format_markdown(self) -> str:
        lines = [
            "# Phone Workflow Report",
            "",
            f"- Recommendation: {self.recommendation}",
            f"- Rationale: {self.rationale}",
            f"- Impact: {self.impact}",
            f"- Required steps: {self.required_steps}",
            f"- Workflow complexity: {self.workflow_complexity}",
            "",
            "## Friction Notes",
            "",
        ]
        lines.extend(f"- {note}" for note in self.friction_notes) if self.friction_notes else lines.append("- None")
        if self.analysis_report:
            lines.extend(["", "## Mobile Analysis Summary", ""])
            lines.append(f"- Candidate: {self.analysis_report.candidate.item_title}")
            lines.append(f"- Top reason: {self.analysis_report.top_reason}")
        return "\n".join(lines) + "\n"


class PhoneWorkflowSimulation:
    """Deterministic dealer-table workflow simulation."""

    def __init__(self, workflow: MobileCompanionWorkflow):
        self.workflow = workflow

    def simulate(
        self,
        title: str,
        price: float = 0.0,
        notes: str = "",
        url: str = "",
        source: str = "Coin shop",
        photo_reference_id: str = "",
    ) -> PhoneWorkflowReport:
        entry = MobileCandidateEntry(
            item_title=title,
            asking_price=price,
            notes=notes,
            url=url,
            source=source,
            photo_reference_id=photo_reference_id,
        )
        analysis = self.workflow.analyze(entry)
        required_fields = [entry.item_title, entry.asking_price, entry.notes]
        required_steps = 3
        if entry.url:
            required_steps += 1
        if entry.photo_reference_id:
            required_steps += 1
        friction = []
        if not entry.item_title:
            friction.append("Title is required for fast candidate parsing")
        if entry.asking_price <= 0:
            friction.append("Asking price missing; recommendation is less decisive")
        if analysis.recommendation == "REVIEW":
            friction.append("Manual review required before a confident dealer-table decision")
        if not friction:
            friction.append("Single workflow avoids switching between collector tools")
        complexity = "LOW" if required_steps <= 3 and analysis.recommendation != "REVIEW" else "MEDIUM"
        if required_steps >= 5 or analysis.recommendation == "REVIEW":
            complexity = "HIGH" if len([field for field in required_fields if not field]) >= 2 else complexity
        return PhoneWorkflowReport(
            recommendation=analysis.recommendation,
            rationale=analysis.top_reason,
            impact=f"Impact score {analysis.impact_score}; quality {analysis.quality_delta:+d}; series {analysis.series_delta:+g}%",
            required_steps=required_steps,
            workflow_complexity=complexity,
            friction_notes=friction,
            analysis_report=analysis,
        )

    def export_csv(self, output_path: str, report: PhoneWorkflowReport) -> bool:
        return self.workflow.export_provider.export_phone_workflow_csv(output_path, report)

    def export_markdown(self, output_path: str, report: PhoneWorkflowReport) -> bool:
        return self.workflow.export_provider.export_phone_workflow_markdown(output_path, report)
