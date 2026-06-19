"""Photo-assisted candidate entry using metadata references only.

This module does not perform OCR, image recognition, grading, scraping, or
image file management. Photos are treated as collector-supplied evidence that
can be linked to existing acquisition workflows.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from market_awareness import MarketAwarenessEngine
from mobile_companion import MobileAnalysisReport, MobileCandidateEntry, MobileCompanionWorkflow
from photo_vault import PhotoRecord, PhotoVault
from smart_shopping_assistant import ShoppingCandidate


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _candidate_id(title: str, timestamp: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in (title or "photo-candidate"))
    slug = "-".join(part for part in slug.split("-") if part)[:48] or "photo-candidate"
    stamp = "".join(ch for ch in (timestamp or _now_iso()) if ch.isdigit())[:14]
    return f"photo-{stamp}-{slug}"


def _money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    return round(float(cleaned), 2) if cleaned else 0.0


def _split_refs(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


@dataclass
class PhotoCandidate:
    """Manual candidate entry with linked photo references."""

    title: str
    front_photo: str = ""
    reverse_photo: str = ""
    reference_photos: List[str] = field(default_factory=list)
    notes: str = ""
    asking_price: float = 0.0
    source: str = "Photo-Assisted Entry"
    timestamp: str = ""
    candidate_id: str = ""
    workflow_state: str = "Manual Review"

    def __post_init__(self) -> None:
        self.title = (self.title or "").strip()
        self.front_photo = (self.front_photo or "").strip()
        self.reverse_photo = (self.reverse_photo or "").strip()
        self.reference_photos = _split_refs(self.reference_photos)
        self.notes = (self.notes or "").strip()
        self.asking_price = _money(self.asking_price)
        self.source = (self.source or "Photo-Assisted Entry").strip()
        self.timestamp = self.timestamp or _now_iso()
        self.candidate_id = (self.candidate_id or _candidate_id(self.title, self.timestamp)).strip()
        self.workflow_state = (self.workflow_state or "Manual Review").strip()

    @property
    def photo_references(self) -> List[str]:
        return [path for path in [self.front_photo, self.reverse_photo, *self.reference_photos] if path]

    def missing_photo_references(self) -> List[str]:
        return [path for path in self.photo_references if not os.path.exists(path)]

    def to_mobile_entry(self) -> MobileCandidateEntry:
        return MobileCandidateEntry(
            item_title=self.title,
            asking_price=self.asking_price,
            notes=self.notes,
            photo_reference_id=self.front_photo or self.reverse_photo or (self.reference_photos[0] if self.reference_photos else ""),
            source=self.source,
            created_at=self.timestamp,
        )

    def to_shopping_candidate(self) -> ShoppingCandidate:
        return ShoppingCandidate(
            item_name=self.title,
            source=self.source,
            asking_price=self.asking_price,
            recommendation_source="Photo-Assisted Entry",
            notes=self.notes,
            photo_reference_ids=list(self.photo_references),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "front_photo": self.front_photo,
            "reverse_photo": self.reverse_photo,
            "reference_photos": list(self.reference_photos),
            "notes": self.notes,
            "asking_price": self.asking_price,
            "source": self.source,
            "timestamp": self.timestamp,
            "candidate_id": self.candidate_id,
            "workflow_state": self.workflow_state,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PhotoCandidate":
        return cls(
            title=str(payload.get("title") or ""),
            front_photo=str(payload.get("front_photo") or ""),
            reverse_photo=str(payload.get("reverse_photo") or ""),
            reference_photos=_split_refs(payload.get("reference_photos")),
            notes=str(payload.get("notes") or ""),
            asking_price=float(payload.get("asking_price") or 0.0),
            source=str(payload.get("source") or "Photo-Assisted Entry"),
            timestamp=str(payload.get("timestamp") or ""),
            candidate_id=str(payload.get("candidate_id") or ""),
            workflow_state=str(payload.get("workflow_state") or "Manual Review"),
        )


@dataclass
class PhotoReviewReport:
    """Collector review report for a photo-assisted candidate."""

    candidate: PhotoCandidate
    attached_photos: List[PhotoRecord] = field(default_factory=list)
    recommendation_context: str = ""
    mobile_analysis_report: Optional[MobileAnalysisReport] = None
    warnings: List[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()
        self.warnings = [str(warning) for warning in self.warnings if str(warning).strip()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "attached_photos": [record.to_dict() for record in self.attached_photos],
            "recommendation_context": self.recommendation_context,
            "mobile_analysis_report": self.mobile_analysis_report.to_dict() if self.mobile_analysis_report else None,
            "warnings": list(self.warnings),
            "generated_at": self.generated_at,
        }

    def format_markdown(self) -> str:
        analysis = self.mobile_analysis_report
        lines = [
            "# Photo Review Report",
            "",
            f"- Candidate: {self.candidate.title or 'Untitled candidate'}",
            f"- Asking price: ${self.candidate.asking_price:.2f}",
            f"- Source: {self.candidate.source or 'Not provided'}",
            f"- Workflow state: {self.candidate.workflow_state}",
            f"- Created: {self.candidate.timestamp}",
            "",
            "## Attached Photos",
            "",
        ]
        if self.attached_photos:
            for record in self.attached_photos:
                lines.append(f"- {record.photo_type}: {record.file_path}; notes: {record.notes or 'none'}")
        else:
            lines.append("- No photo records linked.")
        lines.extend(["", "## Recommendation Context", ""])
        if analysis:
            lines.extend([
                f"- Recommendation: {analysis.recommendation}",
                f"- Impact score: {analysis.impact_score}",
                f"- WANT_LIST status: {analysis.want_list_status}",
                f"- Max rational price: ${analysis.max_rational_price:.2f}",
                f"- Top reason: {analysis.top_reason or 'No reason available'}",
                f"- Summary: {analysis.recommendation_summary}",
            ])
        else:
            lines.append(f"- {self.recommendation_context or 'No recommendation context available.'}")
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in self.warnings) if self.warnings else lines.append("- None")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting photo review markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "candidate_id",
                    "title",
                    "asking_price",
                    "source",
                    "photo_count",
                    "photo_references",
                    "recommendation",
                    "impact_score",
                    "want_list_status",
                    "top_reason",
                    "warnings",
                ])
                writer.writeheader()
                analysis = self.mobile_analysis_report
                writer.writerow({
                    "candidate_id": self.candidate.candidate_id,
                    "title": self.candidate.title,
                    "asking_price": self.candidate.asking_price,
                    "source": self.candidate.source,
                    "photo_count": len(self.attached_photos),
                    "photo_references": ";".join(record.file_path for record in self.attached_photos),
                    "recommendation": analysis.recommendation if analysis else "",
                    "impact_score": analysis.impact_score if analysis else "",
                    "want_list_status": analysis.want_list_status if analysis else "",
                    "top_reason": analysis.top_reason if analysis else self.recommendation_context,
                    "warnings": "; ".join(self.warnings),
                })
            return True
        except Exception as exc:
            print(f"Error exporting photo review CSV: {exc}")
            return False


class PhotoAssistedEntry:
    """Create and review photo-assisted acquisition candidates."""

    def __init__(
        self,
        collection_items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        photo_records: Optional[Iterable[PhotoRecord]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.photo_vault = PhotoVault(photo_records or [], self.collection_items)
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()

    def create_candidate(
        self,
        title: str,
        front_photo: str = "",
        reverse_photo: str = "",
        reference_photos: Optional[Iterable[str]] = None,
        notes: str = "",
        asking_price: float = 0.0,
        source: str = "Photo-Assisted Entry",
    ) -> PhotoCandidate:
        return PhotoCandidate(
            title=title,
            front_photo=front_photo,
            reverse_photo=reverse_photo,
            reference_photos=list(reference_photos or []),
            notes=notes,
            asking_price=asking_price,
            source=source,
        )

    def link_candidate_photos(self, candidate: PhotoCandidate) -> List[PhotoRecord]:
        linked = []
        for label, path in [
            ("Front photo", candidate.front_photo),
            ("Reverse photo", candidate.reverse_photo),
        ]:
            if path:
                linked.append(self.photo_vault.link_candidate_photo(
                    path,
                    candidate.candidate_id,
                    candidate.title,
                    notes=f"{label}; {candidate.notes}".strip("; "),
                ))
        for index, path in enumerate(candidate.reference_photos, start=1):
            linked.append(self.photo_vault.link_candidate_photo(
                path,
                candidate.candidate_id,
                candidate.title,
                notes=f"Reference photo {index}; {candidate.notes}".strip("; "),
                photo_type="Reference Photo",
            ))
        return linked

    def analyze_candidate(self, candidate: PhotoCandidate, persist_mobile_activity: bool = False) -> PhotoReviewReport:
        linked_photos = self.link_candidate_photos(candidate)
        mobile_entry = candidate.to_mobile_entry()
        workflow = MobileCompanionWorkflow(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
            photo_records=self.photo_vault.records,
        )
        analysis = workflow.analyze(mobile_entry, persist=persist_mobile_activity)
        warnings = list(candidate.missing_photo_references())
        warnings = [f"Photo reference missing: {path}" for path in warnings]
        warnings.extend(analysis.warning_flags)
        return PhotoReviewReport(
            candidate=candidate,
            attached_photos=linked_photos,
            recommendation_context=analysis.recommendation_summary,
            mobile_analysis_report=analysis,
            warnings=self._dedupe(warnings),
        )

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
