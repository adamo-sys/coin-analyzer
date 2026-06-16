"""Deterministic acquisition workflow built on focused collection intelligence."""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from focused_collection_intelligence import (
    CandidateItem,
    CollectionIntelligenceResult,
    FocusedCollectionIntelligenceEngine,
    MatchStatus,
)


@dataclass
class AcquisitionDecision:
    """Structured answer to whether a candidate should be purchased."""

    collection_intelligence_status: str
    owned_current_match_summary: str
    want_list_status: str
    upgrade_status: str
    asking_price: float
    max_rational_price: float
    recommendation: str
    confidence_score: int
    priority_reasons: List[str] = field(default_factory=list)
    warning_flags: List[str] = field(default_factory=list)
    intelligence_result: Optional[CollectionIntelligenceResult] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "collection_intelligence_status": self.collection_intelligence_status,
            "owned_current_match_summary": self.owned_current_match_summary,
            "want_list_status": self.want_list_status,
            "upgrade_status": self.upgrade_status,
            "asking_price": self.asking_price,
            "max_rational_price": self.max_rational_price,
            "recommendation": self.recommendation,
            "confidence_score": self.confidence_score,
            "priority_reasons": list(self.priority_reasons),
            "warning_flags": list(self.warning_flags),
        }


class AcquisitionWorkflow:
    """Use Collection Intelligence to produce deterministic acquisition guidance."""

    def __init__(self, collection_items: Iterable[Any], want_list_intents: Optional[Iterable[Any]] = None):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.intelligence_engine = FocusedCollectionIntelligenceEngine(
            self.collection_items,
            self.want_list_intents,
        )

    def evaluate(self, candidate: CandidateItem) -> AcquisitionDecision:
        """Evaluate a manual candidate and asking price."""
        intelligence = self.intelligence_engine.analyze_candidate(candidate)
        asking_price = float(candidate.asking_price or 0.0)
        max_price = self._max_rational_price(intelligence, candidate)
        warnings = list(intelligence.warning_flags)
        priority_reasons = list(intelligence.priority_reasons)

        if asking_price <= 0:
            warnings.append("Missing asking price")

        if self._is_raw_expensive_candidate(candidate, intelligence, asking_price, max_price):
            warnings.append("Raw expensive candidate requires manual review")

        recommendation = self._recommend(intelligence, asking_price, max_price, warnings)

        return AcquisitionDecision(
            collection_intelligence_status=intelligence.match_status.value,
            owned_current_match_summary=self._match_summary(intelligence),
            want_list_status=intelligence.want_list_status,
            upgrade_status=self._upgrade_status(intelligence),
            asking_price=asking_price,
            max_rational_price=max_price,
            recommendation=recommendation,
            confidence_score=intelligence.confidence_score,
            priority_reasons=self._dedupe(priority_reasons),
            warning_flags=self._dedupe(warnings),
            intelligence_result=intelligence,
        )

    def _max_rational_price(self, intelligence: CollectionIntelligenceResult, candidate: CandidateItem) -> float:
        status = intelligence.match_status
        if status in {MatchStatus.SAME_GRADE_DUPLICATE, MatchStatus.LOWER_GRADE_DUPLICATE, MatchStatus.NOT_RELEVANT}:
            return 0.0

        score = {
            MatchStatus.WANT_LIST_MATCH: 100,
            MatchStatus.COLLECTION_GAP: 70,
            MatchStatus.BETTER_GRADE_UPGRADE: 90,
            MatchStatus.ALREADY_OWNED: 20,
            MatchStatus.NEEDS_REVIEW: 45,
        }.get(status, 0)

        reasons = set(intelligence.priority_reasons)
        if "Explicit WANT_LIST Target" in reasons:
            score += 40
        if "Collection Gap" in reasons:
            score += 20
        if "Upgrade Candidate" in reasons:
            score += 20
        if "High-Priority Series: Newfoundland" in reasons:
            score += 30
        if "High-Priority Series: Canadian silver" in reasons:
            score += 25
        if "High-Priority Series: 1859 Canadian Large Cent" in reasons:
            score += 35
        if "Certified candidate may replace raw example" in reasons:
            score += 10

        if self._candidate_is_raw(candidate) and status in {MatchStatus.WANT_LIST_MATCH, MatchStatus.COLLECTION_GAP, MatchStatus.BETTER_GRADE_UPGRADE}:
            score -= 15
        if status == MatchStatus.NEEDS_REVIEW:
            score = min(score, 50)

        return round(max(0.0, min(float(score), 250.0)), 2)

    def _recommend(
        self,
        intelligence: CollectionIntelligenceResult,
        asking_price: float,
        max_price: float,
        warnings: List[str],
    ) -> str:
        status = intelligence.match_status

        if status in {MatchStatus.SAME_GRADE_DUPLICATE, MatchStatus.LOWER_GRADE_DUPLICATE, MatchStatus.NOT_RELEVANT}:
            return "PASS"
        if status == MatchStatus.NEEDS_REVIEW or intelligence.confidence_score < 75:
            return "REVIEW"
        if "Raw expensive candidate requires manual review" in warnings:
            return "REVIEW" if asking_price > max_price * 1.5 else "NEGOTIATE"
        if asking_price <= 0:
            return "WATCH"
        if max_price <= 0:
            return "PASS"
        if asking_price <= max_price:
            if status in {MatchStatus.WANT_LIST_MATCH, MatchStatus.COLLECTION_GAP, MatchStatus.BETTER_GRADE_UPGRADE}:
                return "BUY"
            return "WATCH"
        if asking_price <= max_price * 1.25:
            if status in {MatchStatus.WANT_LIST_MATCH, MatchStatus.COLLECTION_GAP, MatchStatus.BETTER_GRADE_UPGRADE}:
                return "NEGOTIATE"
            return "WATCH"
        if asking_price <= max_price * 1.75:
            return "WATCH"
        return "PASS"

    def _match_summary(self, intelligence: CollectionIntelligenceResult) -> str:
        match = intelligence.best_existing_match
        if not match:
            return "No current owned match."
        parts = [match.country, match.denomination, match.year]
        summary = " ".join(part for part in parts if part)
        if match.grade:
            summary += f" ({match.grade})"
        if match.item_id:
            summary += f" [ID: {match.item_id}]"
        return summary or "Current match found."

    @staticmethod
    def _upgrade_status(intelligence: CollectionIntelligenceResult) -> str:
        if intelligence.match_status == MatchStatus.BETTER_GRADE_UPGRADE:
            return "UPGRADE"
        if intelligence.match_status == MatchStatus.SAME_GRADE_DUPLICATE:
            return "SAME_GRADE_DUPLICATE"
        if intelligence.match_status == MatchStatus.LOWER_GRADE_DUPLICATE:
            return "DOWNGRADE"
        if intelligence.match_status == MatchStatus.ALREADY_OWNED:
            return "OWNED_GRADE_UNKNOWN"
        return "NOT_AN_UPGRADE"

    @staticmethod
    def _candidate_is_raw(candidate: CandidateItem) -> bool:
        text = " ".join([
            str(candidate.certifier or ""),
            str(candidate.certification_number or ""),
            str(candidate.notes or ""),
        ]).lower()
        return not any(term in text for term in ["pcgs", "ngc", "icc", "cert", "slab"])

    def _is_raw_expensive_candidate(
        self,
        candidate: CandidateItem,
        intelligence: CollectionIntelligenceResult,
        asking_price: float,
        max_price: float,
    ) -> bool:
        return (
            asking_price > 0
            and max_price > 0
            and self._candidate_is_raw(candidate)
            and asking_price > max_price * 1.25
            and intelligence.match_status in {
                MatchStatus.WANT_LIST_MATCH,
                MatchStatus.COLLECTION_GAP,
                MatchStatus.BETTER_GRADE_UPGRADE,
            }
        )

    @staticmethod
    def _dedupe(values: List[str]) -> List[str]:
        seen = set()
        deduped = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                deduped.append(value)
        return deduped
