"""Acquisition impact simulation for collection improvement decisions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from acquisition_workflow import AcquisitionDecision, AcquisitionWorkflow
from collection_intelligence import CollectionIntelligenceEngine
from collection_quality import CollectionQualityEngine, CollectionQualityReport
from coin_collection import CoinItem
from focused_collection_intelligence import CandidateItem, MatchStatus
from series_tracker import SeriesTracker


@dataclass
class AcquisitionImpactReport:
    """Structured impact output for a candidate acquisition."""

    impact_score: int
    collection_impact: str
    quality_delta: int
    quality_before: int
    quality_after: int
    completion_delta: float
    completion_before: float
    completion_after: float
    upgrade_impact: str
    upgrade_opportunities_before: int
    upgrade_opportunities_after: int
    want_list_impact: str
    want_list_completed_delta: int
    want_list_completed_before: int
    want_list_completed_after: int
    series_name: str = ""
    series_priority_before: int = 0
    series_priority_after: int = 0
    series_priority_delta: int = 0
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
            "recommendation_reasoning": list(self.recommendation_reasoning),
        }


class AcquisitionImpactEngine:
    """Measure how a candidate would improve collection quality and focus."""

    def __init__(self, collection_items: Iterable[Any], want_list_intents: Optional[Iterable[Any]] = None):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])

    def evaluate(self, candidate: CandidateItem) -> AcquisitionImpactReport:
        acquisition = AcquisitionWorkflow(self.collection_items, self.want_list_intents).evaluate(candidate)
        before_quality = CollectionQualityEngine(
            self.collection_items,
            self.want_list_intents,
        ).generate_report()
        simulated_items = self._simulate_collection(candidate, acquisition)
        after_quality = CollectionQualityEngine(
            simulated_items,
            self.want_list_intents,
        ).generate_report()

        completion_before = self._series_completion(self.collection_items, candidate)
        completion_after = self._series_completion(simulated_items, candidate)
        upgrade_before = self._upgrade_count(self.collection_items)
        upgrade_after = self._upgrade_count(simulated_items)
        want_before = self._want_completed_count(self.collection_items)
        want_after = self._want_completed_count(simulated_items)
        before_series = SeriesTracker(
            self.collection_items,
            self.want_list_intents,
        ).find_report_for_candidate(candidate)
        after_series = SeriesTracker(
            simulated_items,
            self.want_list_intents,
        ).find_report_for_candidate(candidate)
        quality_delta = after_quality.overall_quality_score - before_quality.overall_quality_score
        completion_delta = round(completion_after - completion_before, 1)
        want_delta = want_after - want_before
        series_priority_before = before_series.priority_score if before_series else 0
        series_priority_after = after_series.priority_score if after_series else 0

        score = self._impact_score(
            acquisition,
            quality_delta,
            completion_delta,
            upgrade_before,
            upgrade_after,
            want_delta,
        )

        return AcquisitionImpactReport(
            impact_score=score,
            collection_impact=self._impact_band(score),
            quality_delta=quality_delta,
            quality_before=before_quality.overall_quality_score,
            quality_after=after_quality.overall_quality_score,
            completion_delta=completion_delta,
            completion_before=completion_before,
            completion_after=completion_after,
            upgrade_impact=self._upgrade_impact(acquisition, upgrade_before, upgrade_after),
            upgrade_opportunities_before=upgrade_before,
            upgrade_opportunities_after=upgrade_after,
            want_list_impact=self._want_list_impact(want_delta, acquisition),
            want_list_completed_delta=want_delta,
            want_list_completed_before=want_before,
            want_list_completed_after=want_after,
            series_name=(after_series or before_series).series_name if (after_series or before_series) else "",
            series_priority_before=series_priority_before,
            series_priority_after=series_priority_after,
            series_priority_delta=series_priority_after - series_priority_before,
            recommendation_reasoning=self._reasoning(
                acquisition,
                quality_delta,
                completion_delta,
                upgrade_before,
                upgrade_after,
                want_delta,
            ),
            acquisition_decision=acquisition,
            quality_before_report=before_quality,
            quality_after_report=after_quality,
        )

    def _simulate_collection(self, candidate: CandidateItem, acquisition: AcquisitionDecision) -> List[Any]:
        simulated = list(self.collection_items)
        intelligence = acquisition.intelligence_result
        if not intelligence:
            simulated.append(self._candidate_to_coin_item(candidate))
            return simulated

        if intelligence.match_status == MatchStatus.BETTER_GRADE_UPGRADE and intelligence.best_existing_match:
            match_id = intelligence.best_existing_match.item_id
            simulated = [
                item for item in simulated
                if str(getattr(item, "id", "")) != str(match_id)
            ]

        if intelligence.match_status in {
            MatchStatus.LOWER_GRADE_DUPLICATE,
            MatchStatus.SAME_GRADE_DUPLICATE,
            MatchStatus.NOT_RELEVANT,
        }:
            return simulated

        simulated.append(self._candidate_to_coin_item(candidate))
        return simulated

    def _candidate_to_coin_item(self, candidate: CandidateItem) -> CoinItem:
        notes = " ".join([
            candidate.notes or "",
            candidate.certifier or "",
            candidate.certification_number or "",
        ]).strip()
        return CoinItem(
            id="simulated_candidate",
            image_path="",
            country=candidate.country,
            denomination=candidate.denomination,
            year=candidate.year,
            grade=candidate.grade,
            notes=notes,
            date_added=datetime.now().strftime("%Y-%m-%d"),
            reference=candidate.variety,
            title=candidate.type_series,
        )

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
