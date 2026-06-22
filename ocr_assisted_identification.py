"""OCR-assisted identification candidates for captured photos.

This module turns advisory OCR output into explainable identification
suggestions. It does not perform computer vision attribution, AI grading,
automatic collection entry, ownership decisions, purchases, or collection
mutation.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from focused_collection_intelligence import CandidateItem, FocusedCollectionIntelligenceEngine, MatchStatus
from ocr_experiment import OCRExperiment, OCRSuggestionReport
from ocr_validation import OCRTrustLevel, OCRValidationEngine, OCRValidationReport
from photo_capture_workflow import CapturedPhoto, PhotoCaptureSession
from watchlist_engine import AlertEngine, Watchlist, WatchlistEngine


CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

VARIETY_KEYWORDS = (
    "Near 6",
    "Wide 9",
    "Narrow 9",
    "8 over 9",
    "Large Bust",
    "Proof-Like",
    "Prooflike",
    "Specimen",
    "Chartered Banknote",
    "Small Date",
    "Large Date",
    "H Mintmark",
)

MONARCH_KEYWORDS = (
    "Victoria",
    "Edward VII",
    "Edward VIII",
    "George VI",
    "George V",
    "Elizabeth II",
    "Charles III",
)

SILVER_TERMS = ("silver", "sterling", "925", ".925", "800", ".800")
SILVER_DENOMINATION_HINTS = ("5 cents", "10 cents", "20 cents", "25 cents", "50 cents", "dime", "quarter", "half dollar", "dollar")


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


def _first(values: Iterable[str]) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


@dataclass
class IdentificationEvidence:
    """Evidence bundle explaining an OCR identification suggestion."""

    ocr_text_used: str = ""
    validation_score: int = 0
    trust_level: str = "LOW"
    supporting_keywords: List[str] = field(default_factory=list)
    conflicts_detected: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.ocr_text_used = str(self.ocr_text_used or "")
        self.validation_score = max(0, min(100, int(self.validation_score or 0)))
        self.trust_level = _text(self.trust_level).upper() or "LOW"
        self.supporting_keywords = _dedupe(self.supporting_keywords)
        self.conflicts_detected = _dedupe(self.conflicts_detected)
        self.missing_evidence = _dedupe(self.missing_evidence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ocr_text_used": self.ocr_text_used,
            "validation_score": self.validation_score,
            "trust_level": self.trust_level,
            "supporting_keywords": "; ".join(self.supporting_keywords),
            "conflicts_detected": "; ".join(self.conflicts_detected),
            "missing_evidence": "; ".join(self.missing_evidence),
        }


@dataclass
class OCRIdentificationCandidate:
    """Review-only identification candidate generated from OCR signals."""

    source_photo_id: str = ""
    image_path: str = ""
    year: str = ""
    denomination: str = ""
    country: str = ""
    monarch: str = ""
    banknote_prefix: str = ""
    certification_number: str = ""
    series_type: str = ""
    silver_indicator: str = ""
    possible_variety_keywords: List[str] = field(default_factory=list)
    confidence_level: str = CONFIDENCE_LOW
    confidence_score: int = 0
    confidence_reason: str = ""
    collection_relevance: str = "needs review"
    collection_status: str = "needs review"
    watchlist_matches: List[str] = field(default_factory=list)
    review_status: str = REVIEW_REQUIRED
    warnings: List[str] = field(default_factory=list)
    evidence: IdentificationEvidence = field(default_factory=IdentificationEvidence)

    def __post_init__(self) -> None:
        self.source_photo_id = _text(self.source_photo_id)
        self.image_path = _text(self.image_path)
        self.year = _text(self.year)
        self.denomination = _text(self.denomination)
        self.country = _text(self.country)
        self.monarch = _text(self.monarch)
        self.banknote_prefix = _text(self.banknote_prefix)
        self.certification_number = _text(self.certification_number)
        self.series_type = _text(self.series_type)
        self.silver_indicator = _text(self.silver_indicator)
        self.possible_variety_keywords = _dedupe(self.possible_variety_keywords)
        self.confidence_level = _text(self.confidence_level).upper() or CONFIDENCE_LOW
        self.confidence_score = max(0, min(100, int(self.confidence_score or 0)))
        self.confidence_reason = _text(self.confidence_reason) or "Manual review required."
        self.collection_relevance = _text(self.collection_relevance) or "needs review"
        self.collection_status = _text(self.collection_status) or "needs review"
        self.watchlist_matches = _dedupe(self.watchlist_matches)
        self.review_status = _text(self.review_status) or REVIEW_REQUIRED
        self.warnings = _dedupe([*self.warnings, "Manual review required"])
        if not isinstance(self.evidence, IdentificationEvidence):
            self.evidence = IdentificationEvidence(**(self.evidence or {}))

    @property
    def title(self) -> str:
        series = self.series_type if self.series_type.lower() != self.denomination.lower() else ""
        parts = [self.country, self.year, self.denomination, series, " ".join(self.possible_variety_keywords)]
        return " ".join(part for part in parts if part).strip() or "OCR identification candidate"

    @property
    def recommendation(self) -> str:
        return "REVIEW"

    def to_candidate_item(self) -> CandidateItem:
        return CandidateItem(
            country=self.country,
            denomination=self.denomination,
            year=self.year,
            type_series=self.series_type,
            variety="; ".join(self.possible_variety_keywords),
            certification_number=self.certification_number,
            notes=self.title,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "source_photo_id": self.source_photo_id,
            "image_path": self.image_path,
            "year": self.year,
            "denomination": self.denomination,
            "country": self.country,
            "monarch": self.monarch,
            "banknote_prefix": self.banknote_prefix,
            "certification_number": self.certification_number,
            "series_type": self.series_type,
            "silver_indicator": self.silver_indicator,
            "possible_variety_keywords": "; ".join(self.possible_variety_keywords),
            "confidence_level": self.confidence_level,
            "confidence_score": self.confidence_score,
            "confidence_reason": self.confidence_reason,
            "collection_relevance": self.collection_relevance,
            "collection_status": self.collection_status,
            "watchlist_matches": "; ".join(self.watchlist_matches),
            "review_status": self.review_status,
            "warnings": "; ".join(self.warnings),
            **{f"evidence_{key}": value for key, value in self.evidence.to_dict().items()},
        }

    def format_brief(self) -> str:
        return (
            f"{self.title} - {self.confidence_level} ({self.confidence_score}). "
            f"{self.collection_status}; review required."
        )


@dataclass
class OCRIdentificationReport:
    """Report of review-only OCR identification candidates."""

    candidates: List[OCRIdentificationCandidate] = field(default_factory=list)
    generated_at: str = ""
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.candidates = [
            candidate if isinstance(candidate, OCRIdentificationCandidate) else OCRIdentificationCandidate(**candidate)
            for candidate in self.candidates
        ]
        self.warnings = _dedupe([*self.warnings, "Manual review required before use"])

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def high_confidence_count(self) -> int:
        return sum(1 for candidate in self.candidates if candidate.confidence_level == CONFIDENCE_HIGH)

    @property
    def review_required_count(self) -> int:
        return sum(1 for candidate in self.candidates if candidate.review_status == REVIEW_REQUIRED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "candidate_count": self.candidate_count,
            "high_confidence_count": self.high_confidence_count,
            "review_required_count": self.review_required_count,
            "warnings": "; ".join(self.warnings),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }

    def format_markdown(self) -> str:
        lines = [
            "# OCR-Assisted Identification Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Identification candidates: {self.candidate_count}",
            f"- High confidence candidates: {self.high_confidence_count}",
            f"- Manual review required: YES",
            "",
            "## Candidates",
            "",
        ]
        if not self.candidates:
            lines.append("- No OCR identification candidates available.")
        for candidate in self.candidates:
            lines.extend([
                f"- {candidate.format_brief()}",
                f"  - Year: {candidate.year or 'None'}",
                f"  - Denomination: {candidate.denomination or 'None'}",
                f"  - Country: {candidate.country or 'None'}",
                f"  - Monarch: {candidate.monarch or 'None'}",
                f"  - Banknote prefix: {candidate.banknote_prefix or 'None'}",
                f"  - Certification number: {candidate.certification_number or 'None'}",
                f"  - Series/type: {candidate.series_type or 'None'}",
                f"  - Silver indicator: {candidate.silver_indicator or 'None'}",
                f"  - Variety keywords: {', '.join(candidate.possible_variety_keywords) if candidate.possible_variety_keywords else 'None'}",
                f"  - Collection relevance: {candidate.collection_relevance}",
                f"  - Watchlist matches: {', '.join(candidate.watchlist_matches) if candidate.watchlist_matches else 'None'}",
                f"  - Evidence trust: {candidate.evidence.trust_level} ({candidate.evidence.validation_score}/100)",
                f"  - Supporting keywords: {', '.join(candidate.evidence.supporting_keywords) if candidate.evidence.supporting_keywords else 'None'}",
                f"  - Conflicts: {', '.join(candidate.evidence.conflicts_detected) if candidate.evidence.conflicts_detected else 'None'}",
                f"  - Missing evidence: {', '.join(candidate.evidence.missing_evidence) if candidate.evidence.missing_evidence else 'None'}",
            ])
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in self.warnings)
        lines.extend([
            "",
            "## Boundaries",
            "",
            "- OCR-assisted identification is advisory only.",
            "- No collection records are created or changed.",
            "- Manual review is mandatory before using any suggestion.",
        ])
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        fieldnames = [
            "title",
            "source_photo_id",
            "image_path",
            "year",
            "denomination",
            "country",
            "monarch",
            "banknote_prefix",
            "certification_number",
            "series_type",
            "silver_indicator",
            "possible_variety_keywords",
            "confidence_level",
            "confidence_score",
            "confidence_reason",
            "collection_relevance",
            "collection_status",
            "watchlist_matches",
            "review_status",
            "warnings",
            "evidence_validation_score",
            "evidence_trust_level",
            "evidence_supporting_keywords",
            "evidence_conflicts_detected",
            "evidence_missing_evidence",
            "evidence_ocr_text_used",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for candidate in self.candidates:
                row = candidate.to_dict()
                writer.writerow({key: row.get(key, "") for key in fieldnames})
        return True


class OCRIdentificationEngine:
    """Build reviewable identification candidates from OCR and collection context."""

    def __init__(
        self,
        collection_items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        watchlists: Optional[Sequence[Watchlist]] = None,
        ocr_experiment: Optional[OCRExperiment] = None,
        validation_engine: Optional[OCRValidationEngine] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.watchlists = list(watchlists or [])
        self.ocr_experiment = ocr_experiment or OCRExperiment()
        self.validation_engine = validation_engine or OCRValidationEngine()

    def identify(
        self,
        image_path: str = "",
        raw_text: Optional[str] = None,
        source_photo_id: str = "",
    ) -> OCRIdentificationReport:
        suggestion = self.ocr_experiment.run(image_path=image_path, raw_text=raw_text)
        validation = self.validation_engine.validate(suggestion_report=suggestion)
        return OCRIdentificationReport([self._candidate_from_reports(suggestion, validation, source_photo_id)])

    def identify_from_captured_photo(self, captured_photo: CapturedPhoto, raw_text: Optional[str] = None) -> OCRIdentificationReport:
        suggestion = self.ocr_experiment.from_captured_photo(captured_photo, raw_text=raw_text)
        validation = self.validation_engine.validate(suggestion_report=suggestion)
        candidate = self._candidate_from_reports(suggestion, validation, getattr(captured_photo, "photo_id", ""))
        if getattr(captured_photo, "photo_role", ""):
            candidate.evidence.supporting_keywords = _dedupe([*candidate.evidence.supporting_keywords, getattr(captured_photo, "photo_role", "")])
        return OCRIdentificationReport([candidate])

    def identify_from_session(
        self,
        session: PhotoCaptureSession,
        raw_text_by_photo_id: Optional[Dict[str, str]] = None,
    ) -> OCRIdentificationReport:
        candidates: List[OCRIdentificationCandidate] = []
        raw_text_by_photo_id = raw_text_by_photo_id or {}
        for photo in getattr(session, "photos", []) or []:
            raw_text = raw_text_by_photo_id.get(getattr(photo, "photo_id", ""))
            candidates.extend(self.identify_from_captured_photo(photo, raw_text=raw_text).candidates)
        return OCRIdentificationReport(candidates)

    def identify_from_validation_report(self, validation_report: OCRValidationReport, source_photo_id: str = "") -> OCRIdentificationReport:
        return OCRIdentificationReport([
            self._candidate_from_reports(validation_report.suggestion_report, validation_report, source_photo_id)
        ])

    def _candidate_from_reports(
        self,
        suggestion: OCRSuggestionReport,
        validation: OCRValidationReport,
        source_photo_id: str = "",
    ) -> OCRIdentificationCandidate:
        raw_text = suggestion.result.raw_text
        year = _first(suggestion.possible_years)
        denomination = self._normalize_denomination(_first(suggestion.possible_denominations), raw_text)
        country = self._normalize_country(_first(suggestion.possible_countries), raw_text)
        monarch = self._extract_monarch(raw_text)
        banknote_prefix = _first(suggestion.possible_note_prefixes)
        certification_number = _first(suggestion.possible_certification_numbers)
        varieties = self._extract_variety_keywords(raw_text)
        series_type = self._series_type(country, denomination, raw_text, banknote_prefix, varieties)
        silver_indicator = self._silver_indicator(country, denomination, year, raw_text)
        evidence = self._evidence(suggestion, validation, [year, denomination, country, monarch, banknote_prefix, certification_number, series_type, silver_indicator, *varieties])
        level, score, reason = self._confidence(validation, evidence)
        candidate = OCRIdentificationCandidate(
            source_photo_id=source_photo_id,
            image_path=suggestion.result.image_path,
            year=year,
            denomination=denomination,
            country=country,
            monarch=monarch,
            banknote_prefix=banknote_prefix,
            certification_number=certification_number,
            series_type=series_type,
            silver_indicator=silver_indicator,
            possible_variety_keywords=varieties,
            confidence_level=level,
            confidence_score=score,
            confidence_reason=reason,
            warnings=_dedupe([*suggestion.warnings, *validation.warnings]),
            evidence=evidence,
        )
        self._apply_collection_context(candidate)
        return candidate

    def _evidence(self, suggestion: OCRSuggestionReport, validation: OCRValidationReport, supporting_values: Iterable[str]) -> IdentificationEvidence:
        missing = []
        if not suggestion.possible_years:
            missing.append("year")
        if not suggestion.possible_denominations:
            missing.append("denomination")
        if not suggestion.possible_countries:
            missing.append("country")
        conflicts = [
            finding.message
            for finding in validation.findings
            if "Conflicting" in finding.message or "Ambiguous" in finding.message
        ]
        return IdentificationEvidence(
            ocr_text_used=suggestion.result.raw_text,
            validation_score=validation.validation_score.score,
            trust_level=validation.trust_level.value if isinstance(validation.trust_level, OCRTrustLevel) else str(validation.trust_level),
            supporting_keywords=[value for value in supporting_values if _text(value)],
            conflicts_detected=conflicts,
            missing_evidence=missing,
        )

    def _confidence(self, validation: OCRValidationReport, evidence: IdentificationEvidence) -> tuple[str, int, str]:
        score = validation.validation_score.score
        score += min(12, len(evidence.supporting_keywords) * 2)
        score -= min(20, len(evidence.missing_evidence) * 8)
        score -= min(15, len(evidence.conflicts_detected) * 7)
        score = max(0, min(100, score))
        if validation.trust_level == OCRTrustLevel.HIGH and score >= 78 and not evidence.conflicts_detected:
            level = CONFIDENCE_HIGH
        elif validation.trust_level != OCRTrustLevel.LOW and score >= 48:
            level = CONFIDENCE_MEDIUM
        else:
            level = CONFIDENCE_LOW
        reason = (
            f"{evidence.trust_level} OCR trust, validation score {evidence.validation_score}/100, "
            f"{len(evidence.supporting_keywords)} supporting signal(s), "
            f"{len(evidence.missing_evidence)} missing evidence item(s)."
        )
        if evidence.conflicts_detected:
            reason += " Conflicts require manual review."
        return level, score, reason

    def _apply_collection_context(self, candidate: OCRIdentificationCandidate) -> None:
        if not (candidate.country or candidate.denomination or candidate.year):
            candidate.collection_status = "needs review"
            candidate.collection_relevance = "Not enough OCR evidence to compare with collection."
            return
        result = FocusedCollectionIntelligenceEngine(
            self.collection_items,
            self.want_list_intents,
        ).analyze_candidate(candidate.to_candidate_item())
        status_map = {
            MatchStatus.ALREADY_OWNED: "already owned",
            MatchStatus.BETTER_GRADE_UPGRADE: "possible upgrade",
            MatchStatus.SAME_GRADE_DUPLICATE: "already owned",
            MatchStatus.LOWER_GRADE_DUPLICATE: "already owned",
            MatchStatus.WANT_LIST_MATCH: "watchlist/want-list match",
            MatchStatus.COLLECTION_GAP: "collection gap",
            MatchStatus.NEEDS_REVIEW: "needs review",
            MatchStatus.NOT_RELEVANT: "needs review",
        }
        candidate.collection_status = status_map.get(result.match_status, "needs review")
        candidate.collection_relevance = result.collection_impact
        if result.want_list_status == "ON_WANT_LIST":
            candidate.collection_status = "want-list match"
        candidate.warnings = _dedupe([*candidate.warnings, *result.warning_flags])
        candidate.evidence.supporting_keywords = _dedupe([*candidate.evidence.supporting_keywords, *result.priority_reasons])

        if self.watchlists:
            alert_report = AlertEngine(WatchlistEngine(self.watchlists)).generate_alerts([candidate])
            candidate.watchlist_matches = _dedupe(
                alert.matched_watch.watch_item.name
                for alert in alert_report.alerts
                if alert.matched_watch
            )
            if candidate.watchlist_matches:
                candidate.collection_status = "watchlist match"

    def _normalize_country(self, country: str, raw_text: str) -> str:
        text = _text(country)
        if text.upper() == "USA":
            return "United States"
        lower = raw_text.lower()
        if "newfoundland" in lower:
            return "Newfoundland"
        if "canada" in lower or "canadian" in lower:
            return "Canada"
        return text

    def _normalize_denomination(self, denomination: str, raw_text: str) -> str:
        text = _text(denomination)
        lower = raw_text.lower()
        aliases = {
            "nickel": "5 cents",
            "dime": "10 cents",
            "quarter": "25 cents",
            "half dollar": "50 cents",
            "penny": "1 cent",
        }
        if text.lower() in aliases:
            return aliases[text.lower()]
        if not text:
            for key, value in aliases.items():
                if key in lower:
                    return value
        return text

    def _extract_monarch(self, raw_text: str) -> str:
        lower = raw_text.lower()
        for monarch in MONARCH_KEYWORDS:
            if monarch.lower() in lower:
                return monarch
        return ""

    def _extract_variety_keywords(self, raw_text: str) -> List[str]:
        lower = raw_text.lower()
        return [keyword for keyword in VARIETY_KEYWORDS if keyword.lower() in lower]

    def _series_type(self, country: str, denomination: str, raw_text: str, banknote_prefix: str, varieties: Sequence[str]) -> str:
        lower = raw_text.lower()
        if banknote_prefix or "banknote" in lower or "chartered" in lower:
            return "Banknote"
        if "newfoundland" in _text(country).lower() or "newfoundland" in lower:
            return "Newfoundland coinage"
        if any(variety.lower() in {"near 6", "large bust"} for variety in varieties):
            return "Canadian variety coinage"
        if "specimen" in lower:
            return "Specimen"
        if "proof-like" in lower or "prooflike" in lower:
            return "Proof-Like"
        return _text(denomination)

    def _silver_indicator(self, country: str, denomination: str, year: str, raw_text: str) -> str:
        lower = " ".join([raw_text, country, denomination]).lower()
        if any(term in lower for term in SILVER_TERMS):
            return "Possible silver"
        if any(term in lower for term in SILVER_DENOMINATION_HINTS):
            try:
                numeric_year = int(year)
            except (TypeError, ValueError):
                numeric_year = 0
            if _text(country).lower() in {"canada", "newfoundland"} and 1850 <= numeric_year <= 1968:
                return "Possible silver"
        return ""
