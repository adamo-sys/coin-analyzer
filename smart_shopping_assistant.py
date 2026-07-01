"""Ranked shopping recommendations built from existing analysis engines."""

import csv
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from acquisition_impact import AcquisitionImpactEngine, AcquisitionImpactReport
from acquisition_workflow import AcquisitionDecision, AcquisitionWorkflow
from focused_collection_intelligence import CandidateItem, MatchStatus
from listing_analyzer import ListingAnalyzer, ListingCandidate
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord


def _money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    return round(float(cleaned), 2) if cleaned else 0.0


@dataclass
class ShoppingCandidate:
    """Opportunity input from manual entry, listing, WANT_LIST, or market records."""

    item_name: str
    source: str = ""
    asking_price: float = 0.0
    shipping: float = 0.0
    recommendation_source: str = "Manual"
    notes: str = ""
    url: str = ""
    seller: str = ""
    candidate: Optional[CandidateItem] = None
    listing: Optional[ListingCandidate] = None
    want_list_priority: int = 0
    photo_reference_ids: List[str] = field(default_factory=list)
    total_cost: float = field(init=False)

    def __post_init__(self) -> None:
        self.item_name = (self.item_name or "").strip()
        self.source = (self.source or "").strip()
        self.asking_price = _money(self.asking_price)
        self.shipping = _money(self.shipping)
        self.recommendation_source = (self.recommendation_source or "Manual").strip()
        self.notes = (self.notes or "").strip()
        self.url = (self.url or "").strip()
        self.seller = (self.seller or "").strip()
        self.want_list_priority = int(self.want_list_priority or 0)
        self.total_cost = round(self.asking_price + self.shipping, 2)

    @classmethod
    def from_listing(cls, listing: ListingCandidate) -> "ShoppingCandidate":
        return cls(
            item_name=listing.title,
            source=listing.source,
            asking_price=listing.price,
            shipping=listing.shipping,
            recommendation_source="Listing Analyzer",
            notes=listing.notes or listing.description,
            url=listing.url,
            seller=listing.seller,
            listing=listing,
        )

    @classmethod
    def from_want_list_intent(cls, intent: Any) -> "ShoppingCandidate":
        return cls(
            item_name=getattr(intent, "target_coin", "") or "",
            source="WANT_LIST",
            asking_price=getattr(intent, "budget", 0.0) or 0.0,
            recommendation_source="WANT_LIST",
            notes=getattr(intent, "why_wanted", "") or "",
            want_list_priority=getattr(intent, "priority_score", 0) or 0,
        )

    @classmethod
    def from_observation(cls, record: ObservedPriceRecord) -> "ShoppingCandidate":
        return cls(
            item_name=record.item_name,
            source=record.source,
            asking_price=record.observed_price,
            shipping=record.shipping,
            recommendation_source="Market Observation",
            notes=record.notes,
            candidate=CandidateItem(
                country=record.country,
                denomination=record.denomination,
                year=record.year,
                grade=record.grade,
                asking_price=record.total_observed_cost,
                notes=record.notes,
            ),
            photo_reference_ids=list(record.linked_photo_ids),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_name": self.item_name,
            "source": self.source,
            "asking_price": self.asking_price,
            "shipping": self.shipping,
            "total_cost": self.total_cost,
            "recommendation_source": self.recommendation_source,
            "notes": self.notes,
            "url": self.url,
            "seller": self.seller,
            "want_list_priority": self.want_list_priority,
            "photo_reference_ids": ";".join(self.photo_reference_ids),
        }


@dataclass
class ShoppingRecommendation:
    """Ranked purchasing recommendation for one opportunity."""

    rank: int
    item_name: str
    recommendation_status: str
    opportunity_score: int
    impact_score: int
    quality_delta: int
    series_delta: float
    want_list_status: str
    market_context: str
    max_rational_price: float
    total_cost: float
    source: str
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    photo_reference_ids: List[str] = field(default_factory=list)
    acquisition_decision: Optional[AcquisitionDecision] = None
    impact_report: Optional[AcquisitionImpactReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "item_name": self.item_name,
            "recommendation_status": self.recommendation_status,
            "opportunity_score": self.opportunity_score,
            "impact_score": self.impact_score,
            "quality_delta": self.quality_delta,
            "series_delta": self.series_delta,
            "want_list_status": self.want_list_status,
            "market_context": self.market_context,
            "max_rational_price": self.max_rational_price,
            "total_cost": self.total_cost,
            "source": self.source,
            "reasons": "; ".join(self.reasons),
            "warnings": "; ".join(self.warnings),
            "photo_reference_ids": ";".join(self.photo_reference_ids),
        }


@dataclass
class ShoppingRecommendationReport:
    """Structured output for ranked shopping decisions."""

    recommendations: List[ShoppingRecommendation] = field(default_factory=list)
    best_next_purchase: Optional[ShoppingRecommendation] = None
    highest_impact_candidate: Optional[ShoppingRecommendation] = None
    highest_priority_want_list_target: Optional[ShoppingRecommendation] = None
    connected_data: Optional[Dict[str, Any]] = None  # NEW: Phase 3 metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendations": [row.to_dict() for row in self.recommendations],
            "best_next_purchase": self.best_next_purchase.to_dict() if self.best_next_purchase else None,
            "highest_impact_candidate": self.highest_impact_candidate.to_dict() if self.highest_impact_candidate else None,
            "highest_priority_want_list_target": self.highest_priority_want_list_target.to_dict() if self.highest_priority_want_list_target else None,
            "connected_data": self.connected_data,
        }


class SmartShoppingAssistant:
    """Combine existing engines into deterministic ranked purchase guidance."""

    def __init__(
        self,
        collection_items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()

    def generate_report(
        self,
        candidates: Optional[Iterable[ShoppingCandidate]] = None,
        include_want_list_targets: bool = True,
        include_market_observations: bool = False,
        limit: int = 10,
        connected_data_engine: Any = None,  # NEW: Phase 3
    ) -> ShoppingRecommendationReport:
        """Rank candidate opportunities without modifying collection data."""

        candidate_rows = list(candidates or [])
        if include_want_list_targets:
            candidate_rows.extend(ShoppingCandidate.from_want_list_intent(intent) for intent in self.want_list_intents)
        if include_market_observations:
            candidate_rows.extend(
                ShoppingCandidate.from_observation(record)
                for record in self.market_awareness_engine.observations
            )

        recommendations = [
            self._evaluate_candidate(candidate)
            for candidate in candidate_rows
            if candidate.item_name or candidate.candidate or candidate.listing
        ]
        recommendations = sorted(
            recommendations,
            key=lambda row: (
                -row.opportunity_score,
                self._status_sort(row.recommendation_status),
                row.total_cost,
                row.item_name,
            ),
        )
        for index, recommendation in enumerate(recommendations, start=1):
            recommendation.rank = index

        top_rows = recommendations[:limit]
        report = ShoppingRecommendationReport(
            recommendations=top_rows,
            best_next_purchase=top_rows[0] if top_rows else None,
            highest_impact_candidate=max(top_rows, key=lambda row: row.impact_score, default=None),
            highest_priority_want_list_target=self._highest_priority_want_list(top_rows),
        )

        # Phase 3: metadata-only enrichment (no reordering, no scoring, no filtering)
        if connected_data_engine:
            try:
                from connected_data import ConnectionType

                match_report = connected_data_engine.connect(
                    ConnectionType.WATCHLIST, ConnectionType.SHOPPING
                )
                matched_ids = {c.target_id for c in match_report.connections}
                total_recs = len(report.recommendations)
                report.connected_data = {
                    "watchlist_matches": len(matched_ids),
                    "total_recommendations": total_recs,
                    "match_rate": len(matched_ids) / total_recs if total_recs else 0.0,
                }
            except Exception:
                # Metadata enrichment failed; report is still valid without it
                report.connected_data = None

        return report

    def format_markdown(self, report: Optional[ShoppingRecommendationReport] = None) -> str:
        report = report or self.generate_report()
        lines = ["# Smart Shopping Assistant", ""]
        if report.best_next_purchase:
            top = report.best_next_purchase
            lines.extend([
                "## Best Next Purchase",
                "",
                f"- Item: {top.item_name}",
                f"- Recommendation: {top.recommendation_status}",
                f"- Opportunity score: {top.opportunity_score}",
                f"- Impact score: {top.impact_score}",
                f"- Quality delta: {top.quality_delta:+d}",
                f"- Series completion delta: {top.series_delta:+g}%",
                f"- Market context: {top.market_context}",
                "",
            ])
        lines.extend(["## Ranked Opportunities", ""])
        if not report.recommendations:
            lines.append("- No shopping opportunities available.")
        for row in report.recommendations:
            lines.append(
                f"{row.rank}. {row.item_name} - {row.recommendation_status} "
                f"(score {row.opportunity_score}, impact {row.impact_score})"
            )
            for reason in row.reasons:
                lines.append(f"   - {reason}")
            try:
                from shopping_explainability import ShoppingExplanationEngine

                explanation = ShoppingExplanationEngine().explain_shopping_recommendation(row).explanation
                lines.append("   Why:")
                for reason in explanation.primary_reasons[:3]:
                    lines.append(f"   - {reason}")
                lines.append(f"   - Confidence: {explanation.confidence.level}")
            except Exception:
                pass
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str, report: Optional[ShoppingRecommendationReport] = None) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown(report))
            return True
        except Exception as exc:
            print(f"Error exporting smart shopping markdown: {exc}")
            return False

    def export_csv(self, output_path: str, report: Optional[ShoppingRecommendationReport] = None) -> bool:
        try:
            report = report or self.generate_report()
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "rank",
                    "item_name",
                    "recommendation_status",
                    "opportunity_score",
                    "impact_score",
                    "quality_delta",
                    "series_delta",
                    "want_list_status",
                    "market_context",
                    "max_rational_price",
                    "total_cost",
                    "source",
                    "reasons",
                    "warnings",
                    "photo_reference_ids",
                ])
                writer.writeheader()
                for recommendation in report.recommendations:
                    writer.writerow(recommendation.to_dict())
            return True
        except Exception as exc:
            print(f"Error exporting smart shopping CSV: {exc}")
            return False

    def _evaluate_candidate(self, shopping_candidate: ShoppingCandidate) -> ShoppingRecommendation:
        candidate = self._to_candidate_item(shopping_candidate)
        acquisition = AcquisitionWorkflow(
            self.collection_items,
            self.want_list_intents,
        ).evaluate(candidate)
        impact = AcquisitionImpactEngine(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).evaluate(candidate)
        status = self._shopping_status(acquisition, impact)
        reasons = self._reasons(shopping_candidate, acquisition, impact, status)
        score = self._opportunity_score(shopping_candidate, acquisition, impact, status)

        return ShoppingRecommendation(
            rank=0,
            item_name=shopping_candidate.item_name or self._candidate_label(candidate),
            recommendation_status=status,
            opportunity_score=score,
            impact_score=impact.impact_score,
            quality_delta=impact.quality_delta,
            series_delta=impact.completion_delta,
            want_list_status=acquisition.want_list_status,
            market_context=impact.market_context_summary,
            max_rational_price=acquisition.max_rational_price,
            total_cost=shopping_candidate.total_cost,
            source=shopping_candidate.recommendation_source,
            reasons=reasons,
            warnings=list(acquisition.warning_flags),
            photo_reference_ids=list(shopping_candidate.photo_reference_ids),
            acquisition_decision=acquisition,
            impact_report=impact,
        )

    def _to_candidate_item(self, shopping_candidate: ShoppingCandidate) -> CandidateItem:
        if shopping_candidate.candidate:
            candidate = shopping_candidate.candidate
            candidate.asking_price = shopping_candidate.total_cost
            return candidate
        listing = shopping_candidate.listing or ListingCandidate(
            title=shopping_candidate.item_name,
            price=shopping_candidate.asking_price,
            shipping=shopping_candidate.shipping,
            url=shopping_candidate.url,
            notes=shopping_candidate.notes,
            seller=shopping_candidate.seller,
            source=shopping_candidate.source,
        )
        return ListingAnalyzer(self.collection_items, self.want_list_intents).to_candidate_item(listing)

    def _shopping_status(self, acquisition: AcquisitionDecision, impact: AcquisitionImpactReport) -> str:
        if acquisition.recommendation == "PASS":
            return "PASS"
        if acquisition.recommendation == "REVIEW":
            return "REVIEW"
        if acquisition.recommendation == "NEGOTIATE":
            return "NEGOTIATE"
        if acquisition.recommendation == "WATCH":
            return "WATCH"
        if acquisition.recommendation == "BUY":
            if impact.market_context_summary == "Above recent observed range":
                return "NEGOTIATE"
            if impact.impact_score >= 75 and acquisition.want_list_status == "ON_WANT_LIST":
                return "STRONG BUY"
            if impact.impact_score >= 65 and impact.quality_delta > 0:
                return "STRONG BUY"
            return "BUY"
        return "REVIEW"

    def _opportunity_score(
        self,
        shopping_candidate: ShoppingCandidate,
        acquisition: AcquisitionDecision,
        impact: AcquisitionImpactReport,
        status: str,
    ) -> int:
        score = impact.impact_score
        score += max(0, min(20, impact.quality_delta * 3))
        score += max(0, min(15, int(round(impact.completion_delta))))
        score += max(0, min(20, shopping_candidate.want_list_priority // 5))
        if impact.want_list_impact in {"COMPLETES_WANT_LIST_TARGET", "MATCHES_WANT_LIST_TARGET"}:
            score += 15
        if impact.upgrade_impact in {"RESOLVES_UPGRADE_OPPORTUNITY", "UPGRADE_CANDIDATE"}:
            score += 12
        if impact.market_context_summary == "Within recent observed range":
            score += 8
        elif impact.market_context_summary == "Below recent observed range":
            score += 12
        elif impact.market_context_summary == "Above recent observed range":
            score -= 10

        score += {
            "STRONG BUY": 18,
            "BUY": 10,
            "NEGOTIATE": 4,
            "WATCH": 0,
            "REVIEW": -8,
            "PASS": -30,
        }.get(status, 0)

        if acquisition.collection_intelligence_status in {
            MatchStatus.SAME_GRADE_DUPLICATE.value,
            MatchStatus.LOWER_GRADE_DUPLICATE.value,
            MatchStatus.NOT_RELEVANT.value,
        }:
            score = min(score, 15)
        return max(0, min(100, int(round(score))))

    def _reasons(
        self,
        shopping_candidate: ShoppingCandidate,
        acquisition: AcquisitionDecision,
        impact: AcquisitionImpactReport,
        status: str,
    ) -> List[str]:
        reasons = []
        if status == "STRONG BUY":
            reasons.append("High impact shopping opportunity")
        if impact.impact_score:
            reasons.append(f"Acquisition impact score {impact.impact_score}")
        if impact.quality_delta:
            reasons.append(f"Quality {self._signed(impact.quality_delta)}")
        if impact.completion_delta:
            reasons.append(f"Series completion {self._signed(impact.completion_delta)}%")
        if impact.want_list_impact in {"COMPLETES_WANT_LIST_TARGET", "MATCHES_WANT_LIST_TARGET"}:
            reasons.append("WANT_LIST priority")
        if impact.upgrade_impact in {"RESOLVES_UPGRADE_OPPORTUNITY", "UPGRADE_CANDIDATE"}:
            reasons.append("Upgrade opportunity")
        if impact.market_context_summary and impact.market_context_summary != "No local observation context available.":
            reasons.append(impact.market_context_summary)
        if status == "NEGOTIATE" and impact.market_context_summary == "Above recent observed range":
            reasons.append("High impact but above observed range")
        if acquisition.recommendation == "PASS":
            reasons.append("Duplicate, downgrade, irrelevant, or overpriced weak candidate")
        if acquisition.recommendation == "REVIEW":
            reasons.append("Manual review required")
        if shopping_candidate.photo_reference_ids:
            reasons.append("Linked photo references available")
        for reason in impact.recommendation_reasoning:
            if reason not in reasons:
                reasons.append(reason)
        return self._dedupe(reasons)

    @staticmethod
    def _highest_priority_want_list(rows: List[ShoppingRecommendation]) -> Optional[ShoppingRecommendation]:
        matches = [row for row in rows if row.want_list_status == "ON_WANT_LIST" or "WANT_LIST" in " ".join(row.reasons)]
        return max(matches, key=lambda row: row.opportunity_score, default=None)

    @staticmethod
    def _status_sort(status: str) -> int:
        return {
            "STRONG BUY": 0,
            "BUY": 1,
            "NEGOTIATE": 2,
            "WATCH": 3,
            "REVIEW": 4,
            "PASS": 5,
        }.get(status, 9)

    @staticmethod
    def _candidate_label(candidate: CandidateItem) -> str:
        return " ".join(
            part for part in [
                candidate.country,
                candidate.year,
                candidate.denomination,
                candidate.grade,
            ]
            if part
        ).strip()

    @staticmethod
    def _signed(value: float) -> str:
        return f"+{value:g}" if value > 0 else f"{value:g}"

    @staticmethod
    def _dedupe(values: Iterable[str]) -> List[str]:
        seen = set()
        result = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result
