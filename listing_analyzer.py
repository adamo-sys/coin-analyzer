"""Offline listing analyzer built on acquisition workflow."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from acquisition_workflow import AcquisitionDecision, AcquisitionWorkflow
from acquisition_impact import AcquisitionImpactEngine, AcquisitionImpactReport
from focused_collection_intelligence import CandidateItem, CollectionIntelligenceResult, MatchStatus


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _as_money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    return round(float(cleaned), 2) if cleaned else 0.0


def is_valid_listing_url(url: str) -> bool:
    """Return True for empty URLs or basic http(s) URLs."""

    cleaned = (url or "").strip()
    if not cleaned:
        return True
    parsed = urlparse(cleaned)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


@dataclass
class ListingCandidate:
    """Manual listing input stored without scraping or network access."""

    title: str
    price: float = 0.0
    shipping: float = 0.0
    url: str = ""
    notes: str = ""
    seller: str = ""
    source: str = ""
    description: str = ""
    created_at: str = ""
    total_cost: float = field(init=False)

    def __post_init__(self) -> None:
        self.title = (self.title or "").strip()
        self.price = _as_money(self.price)
        self.shipping = _as_money(self.shipping)
        self.url = (self.url or "").strip()
        self.notes = (self.notes or "").strip()
        self.seller = (self.seller or "").strip()
        self.source = (self.source or "").strip()
        self.description = (self.description or "").strip()
        self.created_at = self.created_at or _now_iso()
        self.total_cost = round(self.price + self.shipping, 2)

    def validate(self) -> List[str]:
        warnings = []
        if not self.title:
            warnings.append("Missing listing title")
        if not is_valid_listing_url(self.url):
            warnings.append("Invalid URL format")
        if self.price <= 0:
            warnings.append("Missing asking price")
        return warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "price": self.price,
            "shipping": self.shipping,
            "total_cost": self.total_cost,
            "url": self.url,
            "notes": self.notes,
            "seller": self.seller,
            "source": self.source,
            "description": self.description,
            "created_at": self.created_at,
        }


@dataclass
class ListingAnalysisResult:
    """Structured listing analysis output."""

    listing: ListingCandidate
    candidate: CandidateItem
    ownership_status: str
    duplicate_status: str
    upgrade_status: str
    want_list_status: str
    collection_impact: str
    priority_score: int
    max_rational_price: float
    acquisition_impact_score: int
    quality_impact: int
    completion_impact: float
    recommendation_reasoning: List[str]
    recommendation: str
    acquisition_decision: AcquisitionDecision
    acquisition_impact_report: Optional[AcquisitionImpactReport] = None
    intelligence_result: Optional[CollectionIntelligenceResult] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing": self.listing.to_dict(),
            "candidate": self.candidate.__dict__,
            "ownership_status": self.ownership_status,
            "duplicate_status": self.duplicate_status,
            "upgrade_status": self.upgrade_status,
            "want_list_status": self.want_list_status,
            "collection_impact": self.collection_impact,
            "priority_score": self.priority_score,
            "max_rational_price": self.max_rational_price,
            "acquisition_impact_score": self.acquisition_impact_score,
            "quality_impact": self.quality_impact,
            "completion_impact": self.completion_impact,
            "recommendation_reasoning": list(self.recommendation_reasoning),
            "recommendation": self.recommendation,
            "warnings": list(self.warnings),
        }


class ListingAnalyzer:
    """Analyze pasted listing information using existing collection intelligence."""

    COUNTRY_TERMS = [
        "Newfoundland",
        "Canada",
        "Canadian",
        "United States",
        "USA",
        "US",
        "Great Britain",
        "United Kingdom",
        "Argentina",
        "Australia",
        "France",
        "Germany",
    ]

    DENOM_PATTERNS = [
        (r"\b50\s*(?:c|cent|cents)\b", "50 cents"),
        (r"\b20\s*(?:c|cent|cents)\b", "20 cents"),
        (r"\b25\s*(?:c|cent|cents)\b|\bquarter\b", "25 cents"),
        (r"\b10\s*(?:c|cent|cents)\b|\bdime\b", "10 cents"),
        (r"\b5\s*(?:c|cent|cents)\b|\bnickel\b", "5 cents"),
        (r"\b1\s*(?:c|cent)\b|\bpenny\b|\blarge cent\b", "1 cent"),
        (r"\bsilver dollar\b|\bdollar\b|\b1\s*dollar\b", "dollar"),
    ]

    GRADE_PATTERN = re.compile(
        r"\b(PO|FR|AG|G|VG|F|VF|EF|XF|AU|MS|PR|PF)[ -]?(1|2|3|4|6|8|10|12|15|20|25|30|35|40|45|50|53|55|58|60|61|62|63|64|65|66|67|68|69|70)\b",
        re.IGNORECASE,
    )

    def __init__(self, collection_items: Iterable[Any], want_list_intents: Optional[Iterable[Any]] = None):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])

    def analyze(self, listing: ListingCandidate) -> ListingAnalysisResult:
        """Analyze a listing using the acquisition workflow."""

        candidate = self.to_candidate_item(listing)
        acquisition = AcquisitionWorkflow(self.collection_items, self.want_list_intents).evaluate(candidate)
        impact = AcquisitionImpactEngine(self.collection_items, self.want_list_intents).evaluate(candidate)
        intelligence = acquisition.intelligence_result
        warnings = list(listing.validate())
        warnings.extend(acquisition.warning_flags)

        return ListingAnalysisResult(
            listing=listing,
            candidate=candidate,
            ownership_status=self._ownership_status(intelligence),
            duplicate_status=self._duplicate_status(intelligence),
            upgrade_status=acquisition.upgrade_status,
            want_list_status=acquisition.want_list_status,
            collection_impact=intelligence.collection_impact if intelligence else "",
            priority_score=self._priority_score(acquisition),
            max_rational_price=acquisition.max_rational_price,
            acquisition_impact_score=impact.impact_score,
            quality_impact=impact.quality_delta,
            completion_impact=impact.completion_delta,
            recommendation_reasoning=impact.recommendation_reasoning,
            recommendation=self._listing_recommendation(acquisition),
            acquisition_decision=acquisition,
            acquisition_impact_report=impact,
            intelligence_result=intelligence,
            warnings=self._dedupe(warnings),
        )

    def to_candidate_item(self, listing: ListingCandidate) -> CandidateItem:
        """Convert pasted listing text into Acquisition Workflow candidate input."""

        text = " ".join([listing.title, listing.description, listing.notes])
        return CandidateItem(
            country=self._extract_country(text),
            denomination=self._extract_denomination(text),
            year=self._extract_year(text),
            type_series=listing.title,
            variety=self._extract_variety(text),
            grade=self._extract_grade(text),
            certifier=self._extract_certifier(text),
            asking_price=listing.total_cost,
            notes=self._candidate_notes(listing),
        )

    def _extract_country(self, text: str) -> str:
        lowered = text.lower()
        if "newfoundland" in lowered or "nfld" in lowered:
            return "Newfoundland"
        for term in self.COUNTRY_TERMS:
            if term.lower() in lowered:
                return "Canada" if term.lower() == "canadian" else term
        return ""

    def _extract_denomination(self, text: str) -> str:
        lowered = text.lower()
        for pattern, denomination in self.DENOM_PATTERNS:
            if re.search(pattern, lowered):
                return denomination
        return ""

    def _extract_year(self, text: str) -> str:
        match = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", text)
        return match.group(1) if match else ""

    def _extract_grade(self, text: str) -> str:
        match = self.GRADE_PATTERN.search(text)
        if not match:
            return ""
        prefix = match.group(1).upper()
        if prefix == "XF":
            prefix = "EF"
        return f"{prefix}-{match.group(2)}"

    def _extract_certifier(self, text: str) -> str:
        lowered = text.lower()
        for certifier in ["PCGS", "NGC", "ICCS", "ANACS", "CCCS"]:
            if certifier.lower() in lowered:
                return certifier
        return ""

    def _extract_variety(self, text: str) -> str:
        lowered = text.lower()
        varieties = []
        for term in ["narrow 9", "wide 9", "8 over 9", "8/9"]:
            if term in lowered:
                varieties.append(term)
        return ", ".join(varieties)

    def _candidate_notes(self, listing: ListingCandidate) -> str:
        parts = []
        if listing.url:
            parts.append(f"Listing URL: {listing.url}")
        if listing.seller:
            parts.append(f"Seller: {listing.seller}")
        if listing.source:
            parts.append(f"Source: {listing.source}")
        if listing.notes:
            parts.append(listing.notes)
        return "\n".join(parts)

    def _ownership_status(self, intelligence: Optional[CollectionIntelligenceResult]) -> str:
        if not intelligence:
            return "UNKNOWN"
        if intelligence.match_status in {
            MatchStatus.ALREADY_OWNED,
            MatchStatus.BETTER_GRADE_UPGRADE,
            MatchStatus.SAME_GRADE_DUPLICATE,
            MatchStatus.LOWER_GRADE_DUPLICATE,
        }:
            return "OWNED_MATCH"
        return "NOT_OWNED"

    def _duplicate_status(self, intelligence: Optional[CollectionIntelligenceResult]) -> str:
        if not intelligence:
            return "UNKNOWN"
        if intelligence.match_status == MatchStatus.SAME_GRADE_DUPLICATE:
            return "SAME_GRADE_DUPLICATE"
        if intelligence.match_status == MatchStatus.LOWER_GRADE_DUPLICATE:
            return "LOWER_GRADE_DUPLICATE"
        if intelligence.match_status == MatchStatus.ALREADY_OWNED:
            return "ALREADY_OWNED"
        return "NOT_DUPLICATE"

    def _priority_score(self, acquisition: AcquisitionDecision) -> int:
        intelligence = acquisition.intelligence_result
        if not intelligence:
            return 0
        score = {
            MatchStatus.WANT_LIST_MATCH: 100,
            MatchStatus.BETTER_GRADE_UPGRADE: 85,
            MatchStatus.COLLECTION_GAP: 70,
            MatchStatus.NEEDS_REVIEW: 45,
            MatchStatus.ALREADY_OWNED: 20,
            MatchStatus.SAME_GRADE_DUPLICATE: 5,
            MatchStatus.LOWER_GRADE_DUPLICATE: 0,
            MatchStatus.NOT_RELEVANT: 0,
        }.get(intelligence.match_status, 0)
        score += 10 * len(acquisition.priority_reasons)
        return min(score, 150)

    def _listing_recommendation(self, acquisition: AcquisitionDecision) -> str:
        base = acquisition.recommendation
        if base == "BUY":
            if acquisition.want_list_status == "ON_WANT_LIST" and acquisition.asking_price <= acquisition.max_rational_price * 0.8:
                return "MUST BUY"
            if acquisition.asking_price <= acquisition.max_rational_price * 0.95:
                return "STRONG BUY"
            return "BUY"
        return base if base in {"NEGOTIATE", "WATCH", "PASS", "REVIEW"} else "REVIEW"

    @staticmethod
    def _dedupe(values: Iterable[str]) -> List[str]:
        seen = set()
        result = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result
