"""Acquisition impact simulation for collection improvement decisions."""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from acquisition_workflow import AcquisitionDecision, AcquisitionWorkflow
from collection_intelligence import CollectionIntelligenceEngine
from collection_quality import CollectionQualityEngine, CollectionQualityReport
from focused_collection_intelligence import CandidateItem, MatchStatus
from market_awareness import MarketAwarenessEngine
from series_tracker import SeriesTracker


@dataclass
class AcquisitionImpactReport:
    """Structured impact output for a candidate acquisition."""

    impact_score: Optional[int]
    collection_impact: Optional[str]
    quality_delta: Optional[int]
    quality_before: Optional[int]
    quality_after: Optional[int]
    completion_delta: Optional[float]
    completion_before: Optional[float]
    completion_after: Optional[float]
    upgrade_impact: Optional[str]
    upgrade_opportunities_before: Optional[int]
    upgrade_opportunities_after: Optional[int]
    want_list_impact: Optional[str]
    want_list_completed_delta: Optional[int]
    want_list_completed_before: Optional[int]
    want_list_completed_after: Optional[int]
    series_name: Optional[str] = None
    series_priority_before: Optional[int] = None
    series_priority_after: Optional[int] = None
    series_priority_delta: Optional[int] = None
    market_context_summary: str = ""
    historical_observed_costs: List[float] = field(default_factory=list)
    recommendation_reasoning: List[str] = field(default_factory=list)
    acquisition_decision: Optional[AcquisitionDecision] = None
    quality_before_report: Optional[CollectionQualityReport] = None
    quality_after_report: Optional[CollectionQualityReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "impact_score": self.impact_score,
            "collection_impact": self.collection_impact,
            "quality_delta": self.quality_delta,
            "quality_before": self.quality_before,
            "quality_after": self.quality_after,
            "completion_delta": self.completion_delta,
            "completion_before": self.completion_before,
            "completion_after": self.completion_after,
            "upgrade_impact": self.upgrade_impact,
            "upgrade_opportunities_before": self.upgrade_opportunities_before,
            "upgrade_opportunities_after": self.upgrade_opportunities_after,
            "want_list_impact": self.want_list_impact,
            "want_list_completed_delta": self.want_list_completed_delta,
            "want_list_completed_before": self.want_list_completed_before,
            "want_list_completed_after": self.want_list_completed_after,
            "series_name": self.series_name,
            "series_priority_before": self.series_priority_before,
            "series_priority_after": self.series_priority_after,
            "series_priority_delta": self.series_priority_delta,
            "market_context_summary": self.market_context_summary,
            "historical_observed_costs": list(self.historical_observed_costs),
            "recommendation_reasoning": list(self.recommendation_reasoning),
        }


class AcquisitionImpactEngine:
    """Measure how a candidate would improve collection quality and focus."""

    def __init__(
        self,
        collection_items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()

    def evaluate(self, candidate: CandidateItem) -> AcquisitionImpactReport:
        acquisition = AcquisitionWorkflow(self.collection_items, self.want_list_intents).evaluate(candidate)
        # CandidateItem has no supported canonical issue identity. Neither a
        # mapped recommendation nor retained legacy intelligence can authorize
        # addition/replacement or supply an identity-derived impact component.
        # Stop before constructing a hypothetical collection or running quality,
        # series, upgrade, or want-list completion analysis.
        market_context = self.market_awareness_engine.historical_context_for_candidate(
            candidate, candidate.asking_price or 0.0,
        )
        return AcquisitionImpactReport(
            impact_score=None,
            collection_impact=None,
            quality_delta=None,
            quality_before=None,
            quality_after=None,
            completion_delta=None,
            completion_before=None,
            completion_after=None,
            upgrade_impact=None,
            upgrade_opportunities_before=None,
            upgrade_opportunities_after=None,
            want_list_impact=None,
            want_list_completed_delta=None,
            want_list_completed_before=None,
            want_list_completed_after=None,
            market_context_summary=market_context.context_summary,
            historical_observed_costs=market_context.observed_costs,
            recommendation_reasoning=[
                "Collection impact unavailable: candidate issue equivalence unresolved",
                *acquisition.priority_reasons,
            ],
            acquisition_decision=acquisition,
        )

    def _simulate_collection(
        self, candidate: CandidateItem, acquisition: AcquisitionDecision,
    ) -> Optional[List[Any]]:
        """No current candidate can authorize identity-dependent simulation.

        An ID, grade, legacy match, or free text cannot supply the missing
        canonical candidate-to-holding relationship. None means unavailable;
        returning unchanged items would falsely imply a completed simulation.
        """
        return None

    def _series_completion(self, items: List[Any], candidate: CandidateItem) -> float:
        country = (candidate.country or "").strip()
        denomination = (candidate.denomination or "").strip()
        if not country or not denomination:
            return 0.0
        series = CollectionIntelligenceEngine(items).analyze_by_series()
        data = series.get((country, denomination))
        if not data:
            return 0.0
        return round(float(data["completion_percentage"]), 1)

    @staticmethod
    def _upgrade_count(items: List[Any]) -> int:
        return len(CollectionIntelligenceEngine(items).detect_upgrade_candidates())

    def _want_completed_count(self, items: List[Any]) -> int:
        report = CollectionQualityEngine(items, self.want_list_intents).generate_report()
        category = next(
            (score for score in report.category_scores if score.name == "WANT_LIST Progress"),
            None,
        )
        if not category:
            return 0
        return int(category.metrics.get("completed_targets", 0) or 0)

    def _impact_score(
        self,
        acquisition: AcquisitionDecision,
        quality_delta: int,
        completion_delta: float,
        upgrade_before: int,
        upgrade_after: int,
        want_delta: int,
    ) -> int:
        intelligence = acquisition.intelligence_result
        status = intelligence.match_status if intelligence else MatchStatus.NEEDS_REVIEW
        score = {
            MatchStatus.WANT_LIST_MATCH: 45,
            MatchStatus.COLLECTION_GAP: 32,
            MatchStatus.BETTER_GRADE_UPGRADE: 38,
            MatchStatus.ALREADY_OWNED: 8,
            MatchStatus.NEEDS_REVIEW: 18,
            MatchStatus.SAME_GRADE_DUPLICATE: 5,
            MatchStatus.LOWER_GRADE_DUPLICATE: 3,
            MatchStatus.NOT_RELEVANT: 0,
        }.get(status, 0)

        score += max(0, min(25, quality_delta * 5))
        score += max(0, min(20, int(round(completion_delta))))
        score += max(0, min(18, want_delta * 18))
        score += max(0, min(15, (upgrade_before - upgrade_after) * 15))

        reasons = set(acquisition.priority_reasons)
        if "High-Priority Series: Newfoundland" in reasons:
            score += 18
        if "High-Priority Series: Canadian silver" in reasons:
            score += 12
        if "High-Priority Series: 1859 Canadian Large Cent" in reasons:
            score += 14
        if "Explicit WANT_LIST Target" in reasons:
            score += 12

        return max(0, min(100, int(round(score))))

    @staticmethod
    def _impact_band(score: int) -> str:
        if score >= 80:
            return "MAJOR"
        if score >= 55:
            return "HIGH"
        if score >= 25:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _upgrade_impact(acquisition: AcquisitionDecision, before: int, after: int) -> str:
        intelligence = acquisition.intelligence_result
        if before > after:
            return "RESOLVES_UPGRADE_OPPORTUNITY"
        if intelligence and intelligence.match_status == MatchStatus.BETTER_GRADE_UPGRADE:
            return "UPGRADE_CANDIDATE"
        return "NO_UPGRADE_IMPACT"

    @staticmethod
    def _want_list_impact(want_delta: int, acquisition: AcquisitionDecision) -> str:
        if want_delta > 0:
            return "COMPLETES_WANT_LIST_TARGET"
        if acquisition.want_list_status == "ON_WANT_LIST":
            return "MATCHES_WANT_LIST_TARGET"
        return "NO_WANT_LIST_IMPACT"

    def _reasoning(
        self,
        acquisition: AcquisitionDecision,
        quality_delta: int,
        completion_delta: float,
        upgrade_before: int,
        upgrade_after: int,
        want_delta: int,
    ) -> List[str]:
        reasons = []
        if quality_delta:
            reasons.append(f"Quality {self._signed(quality_delta)}")
        if completion_delta:
            reasons.append(f"Completion {self._signed(completion_delta)}%")
        if want_delta > 0:
            reasons.append("Resolves WANT_LIST target")
        elif acquisition.want_list_status == "ON_WANT_LIST":
            reasons.append("Matches WANT_LIST target")
        if upgrade_before > upgrade_after:
            reasons.append("Eliminates upgrade gap")
        elif acquisition.upgrade_status == "UPGRADE":
            reasons.append("Upgrade candidate")
        if acquisition.collection_intelligence_status == MatchStatus.NOT_RELEVANT.value:
            reasons.append("No measurable collection improvement detected")
        for reason in acquisition.priority_reasons:
            if reason not in reasons:
                reasons.append(reason)
        if not reasons:
            reasons.append("No measurable collection improvement detected")
        return reasons

    @staticmethod
    def _signed(value: float) -> str:
        if value > 0:
            return f"+{value:g}"
        return f"{value:g}"
