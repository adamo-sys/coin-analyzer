"""Mobile-oriented collection entry candidate workflow.

This module prepares reviewed collection-entry records from OCR-assisted
identification candidates. It never mutates collection data, creates ownership
records automatically, grades automatically, syncs to cloud services, purchases,
or makes automatic ownership decisions.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from focused_collection_intelligence import CandidateItem, FocusedCollectionIntelligenceEngine, MatchStatus
from ocr_assisted_identification import OCRIdentificationCandidate, OCRIdentificationEngine, OCRIdentificationReport
from portfolio_performance import PortfolioPerformanceEngine
from watchlist_engine import AlertEngine, Watchlist, WatchlistEngine


APPROVE = "APPROVE"
REJECT = "REJECT"
REVIEW = "REVIEW"
PENDING_REVIEW = "PENDING_REVIEW"

WORKFLOW_COIN_SHOW = "Coin Show"
WORKFLOW_DEALER_VISIT = "Dealer Visit"
WORKFLOW_COIN_SHOP = "Coin Shop"
WORKFLOW_AUCTION_PREVIEW = "Auction Preview"
WORKFLOW_ANTIQUE_MARKET = "Antique Market"


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
class CollectionEntryCandidate:
    """Review-only proposed collection entry fields."""

    candidate_id: str
    country: str = ""
    year: str = ""
    denomination: str = ""
    series: str = ""
    monarch: str = ""
    variety: str = ""
    grade_estimate: str = ""
    certification_number: str = ""
    notes: str = ""
    acquisition_source: str = ""
    field_confidence: Dict[str, int] = field(default_factory=dict)
    overall_confidence: int = 0
    confidence_level: str = "LOW"
    evidence_summary: str = ""
    collection_context: str = "review required"
    collection_status: str = "review required"
    portfolio_impact_preview: List[str] = field(default_factory=list)
    review_status: str = PENDING_REVIEW
    warnings: List[str] = field(default_factory=list)
    source_identification_title: str = ""

    def __post_init__(self) -> None:
        self.candidate_id = _text(self.candidate_id) or f"entry-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.country = _text(self.country)
        self.year = _text(self.year)
        self.denomination = _text(self.denomination)
        self.series = _text(self.series)
        self.monarch = _text(self.monarch)
        self.variety = _text(self.variety)
        self.grade_estimate = _text(self.grade_estimate)
        self.certification_number = _text(self.certification_number)
        self.notes = _text(self.notes)
        self.acquisition_source = _text(self.acquisition_source)
        self.field_confidence = {str(k): _clamp(v) for k, v in dict(self.field_confidence or {}).items()}
        self.overall_confidence = _clamp(self.overall_confidence)
        self.confidence_level = _text(self.confidence_level).upper() or "LOW"
        self.evidence_summary = _text(self.evidence_summary)
        self.collection_context = _text(self.collection_context) or "review required"
        self.collection_status = _text(self.collection_status) or "review required"
        self.portfolio_impact_preview = _dedupe(self.portfolio_impact_preview)
        self.review_status = _text(self.review_status).upper() or PENDING_REVIEW
        self.warnings = _dedupe([*self.warnings, "Manual review required before collection entry"])
        self.source_identification_title = _text(self.source_identification_title)

    @property
    def title(self) -> str:
        parts = [self.country, self.year, self.denomination, self.series, self.variety]
        return " ".join(part for part in parts if part).strip() or "Mobile collection entry candidate"

    def to_candidate_item(self) -> CandidateItem:
        return CandidateItem(
            country=self.country,
            denomination=self.denomination,
            year=self.year,
            type_series=self.series,
            variety=self.variety,
            grade=self.grade_estimate,
            certification_number=self.certification_number,
            notes=self.notes,
        )

    def approved_entry_record(self) -> Dict[str, Any]:
        return {
            "country": self.country,
            "year": self.year,
            "denomination": self.denomination,
            "series": self.series,
            "monarch": self.monarch,
            "variety": self.variety,
            "grade": self.grade_estimate,
            "certification_number": self.certification_number,
            "notes": self.notes,
            "acquisition_source": self.acquisition_source,
            "review_status": APPROVE,
            "created_from": "Mobile Collection Entry preview",
            "mutation_allowed": "NO",
        }

    def confidence_summary(self) -> str:
        if not self.field_confidence:
            return f"{self.confidence_level} ({self.overall_confidence})"
        fields = "; ".join(f"{field} {score}" for field, score in sorted(self.field_confidence.items()))
        return f"{self.confidence_level} ({self.overall_confidence}); {fields}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "title": self.title,
            "country": self.country,
            "year": self.year,
            "denomination": self.denomination,
            "series": self.series,
            "monarch": self.monarch,
            "variety": self.variety,
            "grade_estimate": self.grade_estimate,
            "certification_number": self.certification_number,
            "notes": self.notes,
            "acquisition_source": self.acquisition_source,
            "field_confidence": "; ".join(f"{k}:{v}" for k, v in sorted(self.field_confidence.items())),
            "overall_confidence": self.overall_confidence,
            "confidence_level": self.confidence_level,
            "evidence_summary": self.evidence_summary,
            "collection_context": self.collection_context,
            "collection_status": self.collection_status,
            "portfolio_impact_preview": "; ".join(self.portfolio_impact_preview),
            "review_status": self.review_status,
            "warnings": "; ".join(self.warnings),
            "source_identification_title": self.source_identification_title,
        }


@dataclass
class CollectionEntryReview:
    """Manual review decision for an entry candidate."""

    candidate_id: str
    decision: str = REVIEW
    reasoning: str = ""
    evidence_summary: str = ""
    confidence_summary: str = ""
    collection_relevance: str = ""
    reviewed_at: str = ""
    approved_entry_record: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        self.candidate_id = _text(self.candidate_id)
        self.decision = _text(self.decision).upper() or REVIEW
        if self.decision not in {APPROVE, REJECT, REVIEW}:
            self.decision = REVIEW
        self.reasoning = _text(self.reasoning) or "Manual review required."
        self.evidence_summary = _text(self.evidence_summary)
        self.confidence_summary = _text(self.confidence_summary)
        self.collection_relevance = _text(self.collection_relevance)
        self.reviewed_at = _text(self.reviewed_at) or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision": self.decision,
            "reasoning": self.reasoning,
            "evidence_summary": self.evidence_summary,
            "confidence_summary": self.confidence_summary,
            "collection_relevance": self.collection_relevance,
            "reviewed_at": self.reviewed_at,
            "approved_entry_record": self.approved_entry_record or {},
        }


@dataclass
class CollectionEntryReport:
    """Report of mobile entry candidates and manual review decisions."""

    candidates: List[CollectionEntryCandidate] = field(default_factory=list)
    reviews: List[CollectionEntryReview] = field(default_factory=list)
    generated_at: str = ""
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.candidates = [candidate if isinstance(candidate, CollectionEntryCandidate) else CollectionEntryCandidate(**candidate) for candidate in self.candidates]
        self.reviews = [review if isinstance(review, CollectionEntryReview) else CollectionEntryReview(**review) for review in self.reviews]
        self.warnings = _dedupe([*self.warnings, "Preview only; no collection mutation performed"])

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def approved_count(self) -> int:
        return sum(1 for review in self.reviews if review.decision == APPROVE)

    @property
    def review_count(self) -> int:
        return sum(1 for review in self.reviews if review.decision == REVIEW)

    @property
    def rejected_count(self) -> int:
        return sum(1 for review in self.reviews if review.decision == REJECT)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "candidate_count": self.candidate_count,
            "approved_count": self.approved_count,
            "review_count": self.review_count,
            "rejected_count": self.rejected_count,
            "warnings": "; ".join(self.warnings),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "reviews": [review.to_dict() for review in self.reviews],
        }

    def format_markdown(self) -> str:
        lines = [
            "# Mobile Collection Entry Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Entry candidates: {self.candidate_count}",
            f"- Approved previews: {self.approved_count}",
            f"- Review decisions: {self.review_count}",
            f"- Rejected candidates: {self.rejected_count}",
            "- Collection mutation performed: NO",
            "",
            "## Entry Candidates",
            "",
        ]
        if not self.candidates:
            lines.append("- No entry candidates available.")
        for candidate in self.candidates:
            lines.extend([
                f"- {candidate.title}",
                f"  - Status: {candidate.review_status}",
                f"  - Confidence: {candidate.confidence_summary()}",
                f"  - Evidence: {candidate.evidence_summary or 'None'}",
                f"  - Collection context: {candidate.collection_status}; {candidate.collection_context}",
                f"  - Portfolio preview: {'; '.join(candidate.portfolio_impact_preview) if candidate.portfolio_impact_preview else 'None'}",
            ])
        lines.extend(["", "## Reviews", ""])
        if not self.reviews:
            lines.append("- No manual reviews recorded.")
        for review in self.reviews:
            lines.append(f"- {review.candidate_id}: {review.decision}; {review.reasoning}")
            if review.approved_entry_record:
                lines.append("  - Approved entry record prepared as preview only.")
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        fieldnames = [
            "row_type", "candidate_id", "title", "country", "year", "denomination", "series", "monarch", "variety",
            "grade_estimate", "certification_number", "acquisition_source", "overall_confidence", "confidence_level",
            "field_confidence", "collection_status", "collection_context", "portfolio_impact_preview", "review_status",
            "decision", "reasoning", "evidence_summary", "warnings",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for candidate in self.candidates:
                row = candidate.to_dict()
                row.update({"row_type": "candidate", "decision": "", "reasoning": ""})
                writer.writerow({key: row.get(key, "") for key in fieldnames})
            by_id = {candidate.candidate_id: candidate for candidate in self.candidates}
            for review in self.reviews:
                candidate = by_id.get(review.candidate_id)
                base = candidate.to_dict() if candidate else {"candidate_id": review.candidate_id, "title": ""}
                base.update({"row_type": "review", "decision": review.decision, "reasoning": review.reasoning})
                writer.writerow({key: base.get(key, "") for key in fieldnames})
        return True


class MobileCollectionEntryEngine:
    """Prepare mobile collection-entry candidates without saving them."""

    def __init__(
        self,
        collection_items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        watchlists: Optional[Iterable[Watchlist]] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.watchlists = list(watchlists or [])

    def from_ocr_candidate(
        self,
        ocr_candidate: OCRIdentificationCandidate,
        acquisition_source: str = "Mobile Field Workflow",
        notes: str = "",
    ) -> CollectionEntryCandidate:
        field_confidence = self._field_confidence(ocr_candidate)
        overall = self._overall_confidence(field_confidence, ocr_candidate.confidence_score)
        candidate = CollectionEntryCandidate(
            candidate_id=f"entry-{ocr_candidate.source_photo_id or datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            country=ocr_candidate.country,
            year=ocr_candidate.year,
            denomination=ocr_candidate.denomination,
            series=ocr_candidate.series_type,
            monarch=ocr_candidate.monarch,
            variety="; ".join(ocr_candidate.possible_variety_keywords),
            grade_estimate="",
            certification_number=ocr_candidate.certification_number,
            notes=_text(notes) or f"Created from OCR candidate: {ocr_candidate.title}",
            acquisition_source=acquisition_source,
            field_confidence=field_confidence,
            overall_confidence=overall,
            confidence_level=self._confidence_level(overall),
            evidence_summary=self._evidence_summary(ocr_candidate),
            warnings=ocr_candidate.warnings,
            source_identification_title=ocr_candidate.title,
        )
        self._apply_collection_context(candidate)
        self._apply_portfolio_preview(candidate)
        return candidate

    def from_ocr_report(
        self,
        report: OCRIdentificationReport,
        acquisition_source: str = "Mobile Field Workflow",
    ) -> CollectionEntryReport:
        candidates = [self.from_ocr_candidate(candidate, acquisition_source=acquisition_source) for candidate in report.candidates]
        reviews = [self.review_candidate(candidate, REVIEW, "Prepared for manual collection-entry review") for candidate in candidates]
        return CollectionEntryReport(candidates, reviews)

    def identify_and_prepare(
        self,
        raw_text: str = "",
        image_path: str = "",
        acquisition_source: str = "Mobile Field Workflow",
    ) -> CollectionEntryReport:
        ocr_report = OCRIdentificationEngine(
            collection_items=self.collection_items,
            want_list_intents=self.want_list_intents,
            watchlists=self.watchlists,
        ).identify(image_path=image_path, raw_text=raw_text or None)
        return self.from_ocr_report(ocr_report, acquisition_source=acquisition_source)

    def review_candidate(self, candidate: CollectionEntryCandidate, decision: str = REVIEW, reasoning: str = "") -> CollectionEntryReview:
        decision = _text(decision).upper() or REVIEW
        approved = candidate.approved_entry_record() if decision == APPROVE else None
        candidate.review_status = decision if decision in {APPROVE, REJECT, REVIEW} else REVIEW
        return CollectionEntryReview(
            candidate_id=candidate.candidate_id,
            decision=candidate.review_status,
            reasoning=reasoning or self._default_reason(candidate),
            evidence_summary=candidate.evidence_summary,
            confidence_summary=candidate.confidence_summary(),
            collection_relevance=f"{candidate.collection_status}: {candidate.collection_context}",
            approved_entry_record=approved,
        )

    def report(self, candidates: Iterable[CollectionEntryCandidate], reviews: Optional[Iterable[CollectionEntryReview]] = None) -> CollectionEntryReport:
        return CollectionEntryReport(list(candidates or []), list(reviews or []))

    def _field_confidence(self, ocr_candidate: OCRIdentificationCandidate) -> Dict[str, int]:
        base = _clamp(ocr_candidate.confidence_score)
        fields = {
            "country": base if ocr_candidate.country else 0,
            "year": base if ocr_candidate.year else 0,
            "denomination": base if ocr_candidate.denomination else 0,
            "series": max(35, base - 10) if ocr_candidate.series_type else 0,
            "monarch": max(30, base - 15) if ocr_candidate.monarch else 0,
            "variety": max(30, base - 20) if ocr_candidate.possible_variety_keywords else 0,
            "grade_estimate": 0,
            "certification_number": base if ocr_candidate.certification_number else 0,
        }
        return fields

    def _overall_confidence(self, field_confidence: Dict[str, int], ocr_score: int) -> int:
        key_scores = [field_confidence.get("country", 0), field_confidence.get("year", 0), field_confidence.get("denomination", 0)]
        active = [score for score in field_confidence.values() if score > 0]
        if not active:
            return min(_clamp(ocr_score), 30)
        return _clamp((sum(active) / len(active)) * 0.75 + (sum(key_scores) / 3) * 0.25)

    def _confidence_level(self, score: int) -> str:
        if score >= 75:
            return "HIGH"
        if score >= 45:
            return "MEDIUM"
        return "LOW"

    def _evidence_summary(self, ocr_candidate: OCRIdentificationCandidate) -> str:
        evidence = ocr_candidate.evidence
        parts = [
            f"OCR confidence {ocr_candidate.confidence_level} ({ocr_candidate.confidence_score})",
            f"validation {evidence.trust_level} ({evidence.validation_score}/100)",
        ]
        if evidence.supporting_keywords:
            parts.append("signals: " + ", ".join(evidence.supporting_keywords[:8]))
        if evidence.conflicts_detected:
            parts.append("conflicts: " + ", ".join(evidence.conflicts_detected[:3]))
        if evidence.missing_evidence:
            parts.append("missing: " + ", ".join(evidence.missing_evidence))
        return "; ".join(parts)

    def _apply_collection_context(self, candidate: CollectionEntryCandidate) -> None:
        result = FocusedCollectionIntelligenceEngine(self.collection_items, self.want_list_intents).analyze_candidate(candidate.to_candidate_item())
        mapping = {
            MatchStatus.ALREADY_OWNED: "already owned",
            MatchStatus.SAME_GRADE_DUPLICATE: "duplicate",
            MatchStatus.LOWER_GRADE_DUPLICATE: "duplicate",
            MatchStatus.BETTER_GRADE_UPGRADE: "possible upgrade",
            MatchStatus.WANT_LIST_MATCH: "want-list match",
            MatchStatus.COLLECTION_GAP: "collection gap",
            MatchStatus.NEEDS_REVIEW: "review required",
            MatchStatus.NOT_RELEVANT: "review required",
        }
        candidate.collection_status = mapping.get(result.match_status, "review required")
        candidate.collection_context = result.collection_impact
        candidate.warnings = _dedupe([*candidate.warnings, *result.warning_flags])
        if result.want_list_status == "ON_WANT_LIST":
            candidate.collection_status = "want-list match"
        if self.watchlists:
            alerts = AlertEngine(WatchlistEngine(self.watchlists)).generate_alerts([candidate])
            matches = [alert.matched_watch.watch_item.name for alert in alerts.alerts if alert.matched_watch]
            if matches:
                candidate.collection_status = "watchlist match"
                candidate.collection_context = f"Watchlist match: {', '.join(_dedupe(matches))}"

    def _apply_portfolio_preview(self, candidate: CollectionEntryCandidate) -> None:
        preview = ["Preview only; collection size would increase by 1 if approved and manually saved"]
        try:
            performance = PortfolioPerformanceEngine(self.collection_items, self.want_list_intents).generate_report()
            preview.append(f"Current portfolio health: {performance.health_score.score}/100")
        except Exception:
            preview.append("Portfolio health unavailable in entry preview")
        if candidate.collection_status in {"collection gap", "want-list match", "watchlist match"}:
            preview.append(f"Priority impact: {candidate.collection_status}")
        if candidate.collection_status == "possible upgrade":
            preview.append("Collection gap impact: possible upgrade/replacement review")
        elif candidate.collection_status == "collection gap":
            preview.append("Collection gap impact: may fill a missing collection slot")
        else:
            preview.append("Collection gap impact: manual review required")
        preview.append("Collection value impact: no automatic valuation assigned")
        candidate.portfolio_impact_preview = _dedupe(preview)

    def _default_reason(self, candidate: CollectionEntryCandidate) -> str:
        if candidate.collection_status in {"duplicate", "already owned"}:
            return "Review duplicate or already-owned status before entry."
        if candidate.confidence_level == "LOW":
            return "Low confidence fields require manual verification."
        return "Prepared for collector review; no automatic collection mutation."
