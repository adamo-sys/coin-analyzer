"""Budget-aware opportunity planning built from existing collection engines."""

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from collection_intelligence import AcquisitionTarget, CollectionIntelligenceEngine
from deal_hunter import DealHunterResult
from market_awareness import MarketAwarenessEngine
from smart_shopping_assistant import ShoppingCandidate, ShoppingRecommendation, SmartShoppingAssistant


OPPORTUNITY_UPGRADE = "Upgrade Opportunity"
OPPORTUNITY_COLLECTION_GAP = "Collection Gap Opportunity"
OPPORTUNITY_SERIES_COMPLETION = "Series Completion Opportunity"
OPPORTUNITY_WANT_LIST = "Want List Opportunity"
OPPORTUNITY_NEWFOUNDLAND = "Newfoundland Opportunity"
OPPORTUNITY_CANADIAN_SILVER = "Canadian Silver Opportunity"
OPPORTUNITY_CANADIAN_BANKNOTE = "Canadian Banknote Opportunity"
OPPORTUNITY_HIGH_ROI = "High-ROI Opportunity"

DEFAULT_BUDGETS = (50, 100, 250, 500)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _dedupe(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


@dataclass
class OpportunityScore:
    """Explainable 0-100 score components for an opportunity."""

    score: int
    collection_fit: int = 0
    upgrade_impact: int = 0
    completion_impact: int = 0
    liquidity: int = 0
    risk: int = 0
    collection_priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "collection_fit": self.collection_fit,
            "upgrade_impact": self.upgrade_impact,
            "completion_impact": self.completion_impact,
            "liquidity": self.liquidity,
            "risk": self.risk,
            "collection_priority": self.collection_priority,
        }


@dataclass
class OpportunityReport:
    """One ranked collection opportunity."""

    rank: int
    opportunity_type: str
    item_name: str
    score: int
    reasoning: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    counterargument: str = ""
    estimated_collection_impact: str = ""
    budget_fit: str = ""
    total_cost: float = 0.0
    source: str = ""
    recommendation: str = ""
    score_detail: Optional[OpportunityScore] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "opportunity_type": self.opportunity_type,
            "item_name": self.item_name,
            "score": self.score,
            "reasoning": "; ".join(self.reasoning),
            "risks": "; ".join(self.risks),
            "counterargument": self.counterargument,
            "estimated_collection_impact": self.estimated_collection_impact,
            "budget_fit": self.budget_fit,
            "total_cost": self.total_cost,
            "source": self.source,
            "recommendation": self.recommendation,
            "collection_fit": self.score_detail.collection_fit if self.score_detail else 0,
            "upgrade_impact": self.score_detail.upgrade_impact if self.score_detail else 0,
            "completion_impact": self.score_detail.completion_impact if self.score_detail else 0,
            "liquidity": self.score_detail.liquidity if self.score_detail else 0,
            "risk": self.score_detail.risk if self.score_detail else 0,
            "collection_priority": self.score_detail.collection_priority if self.score_detail else 0,
        }


@dataclass
class TopOpportunitiesReport:
    """Top opportunities and budget-specific recommendations."""

    opportunities: List[OpportunityReport] = field(default_factory=list)
    budget_recommendations: Dict[int, Optional[OpportunityReport]] = field(default_factory=dict)
    top_overall: List[OpportunityReport] = field(default_factory=list)
    top_under_100: List[OpportunityReport] = field(default_factory=list)
    top_newfoundland: List[OpportunityReport] = field(default_factory=list)
    top_banknote: List[OpportunityReport] = field(default_factory=list)
    top_upgrade: List[OpportunityReport] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "opportunities": [row.to_dict() for row in self.opportunities],
            "budget_recommendations": {
                str(budget): row.to_dict() if row else None
                for budget, row in self.budget_recommendations.items()
            },
            "top_overall": [row.to_dict() for row in self.top_overall],
            "top_under_100": [row.to_dict() for row in self.top_under_100],
            "top_newfoundland": [row.to_dict() for row in self.top_newfoundland],
            "top_banknote": [row.to_dict() for row in self.top_banknote],
            "top_upgrade": [row.to_dict() for row in self.top_upgrade],
        }

    def format_markdown(self) -> str:
        lines = [
            "# Opportunity Engine Report",
            "",
            f"- Generated: {self.generated_at}",
            "- Guidance note: deterministic local opportunity guidance only; no live pricing, scraping, or market prediction.",
            "",
            "## Top Opportunities",
            "",
        ]
        if not self.top_overall:
            lines.append("- No opportunities generated from available collection context.")
        for row in self.top_overall:
            lines.extend(self._format_opportunity(row))
        lines.extend(["", "## Budget Recommendations", ""])
        for budget, row in self.budget_recommendations.items():
            if row:
                lines.append(f"- ${budget}: {row.item_name} ({row.opportunity_type}, score {row.score})")
                lines.append(f"  - Counterargument: {row.counterargument}")
            else:
                lines.append(f"- ${budget}: No priced opportunity available within this budget.")
        lines.extend(self._format_section("Top Under $100", self.top_under_100))
        lines.extend(self._format_section("Top Newfoundland Opportunities", self.top_newfoundland))
        lines.extend(self._format_section("Top Banknote Opportunities", self.top_banknote))
        lines.extend(self._format_section("Top Upgrade Opportunities", self.top_upgrade))
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            fieldnames = [
                "rank",
                "opportunity_type",
                "item_name",
                "score",
                "reasoning",
                "risks",
                "counterargument",
                "estimated_collection_impact",
                "budget_fit",
                "total_cost",
                "source",
                "recommendation",
                "collection_fit",
                "upgrade_impact",
                "completion_impact",
                "liquidity",
                "risk",
                "collection_priority",
            ]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for opportunity in self.opportunities:
                writer.writerow(opportunity.to_dict())
        return True

    @staticmethod
    def _format_opportunity(row: OpportunityReport) -> List[str]:
        lines = [
            f"### {row.rank}. {row.item_name}",
            "",
            f"- Type: {row.opportunity_type}",
            f"- Score: {row.score}",
            f"- Recommendation: {row.recommendation or 'REVIEW'}",
            f"- Budget fit: {row.budget_fit}",
            f"- Estimated impact: {row.estimated_collection_impact}",
            f"- Counterargument: {row.counterargument}",
            "- Reasoning:",
        ]
        lines.extend(f"  - {reason}" for reason in row.reasoning) if row.reasoning else lines.append("  - No positive reason generated.")
        lines.append("- Risks:")
        lines.extend(f"  - {risk}" for risk in row.risks) if row.risks else lines.append("  - Normal manual review.")
        lines.append("")
        return lines

    def _format_section(self, title: str, rows: Sequence[OpportunityReport]) -> List[str]:
        lines = ["", f"## {title}", ""]
        if not rows:
            lines.append("- No matching opportunities.")
            return lines
        for row in rows:
            lines.append(f"- {row.item_name}: {row.opportunity_type}, score {row.score}, {row.budget_fit}")
        return lines


class OpportunityEngine:
    """Identify the best next collection opportunities from existing systems."""

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
        shopping_candidates: Optional[Iterable[ShoppingCandidate]] = None,
        deal_hunter_results: Optional[Iterable[DealHunterResult]] = None,
        budgets: Iterable[int] = DEFAULT_BUDGETS,
        limit: int = 5,
    ) -> TopOpportunitiesReport:
        opportunities: List[OpportunityReport] = []
        opportunities.extend(self._shopping_opportunities(shopping_candidates or []))
        opportunities.extend(self._collection_target_opportunities())
        opportunities.extend(self._deal_hunter_opportunities(deal_hunter_results or []))
        opportunities = self._dedupe_opportunities(opportunities)
        opportunities.sort(key=lambda row: (-row.score, self._budget_sort(row.total_cost), row.item_name))
        for index, opportunity in enumerate(opportunities, 1):
            opportunity.rank = index

        budget_map = {int(budget): self._best_for_budget(opportunities, int(budget)) for budget in budgets}
        return TopOpportunitiesReport(
            opportunities=opportunities,
            budget_recommendations=budget_map,
            top_overall=opportunities[:limit],
            top_under_100=[row for row in opportunities if 0 < row.total_cost <= 100][:limit],
            top_newfoundland=[row for row in opportunities if "newfoundland" in row.item_name.lower() or row.opportunity_type == OPPORTUNITY_NEWFOUNDLAND][:limit],
            top_banknote=[row for row in opportunities if "banknote" in row.item_name.lower() or row.opportunity_type == OPPORTUNITY_CANADIAN_BANKNOTE][:limit],
            top_upgrade=[row for row in opportunities if row.opportunity_type == OPPORTUNITY_UPGRADE][:limit],
        )

    def export_markdown(self, output_path: str, report: Optional[TopOpportunitiesReport] = None) -> bool:
        (report or self.generate_report()).export_markdown(output_path)
        return True

    def export_csv(self, output_path: str, report: Optional[TopOpportunitiesReport] = None) -> bool:
        (report or self.generate_report()).export_csv(output_path)
        return True

    def _shopping_opportunities(self, candidates: Iterable[ShoppingCandidate]) -> List[OpportunityReport]:
        assistant = SmartShoppingAssistant(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        )
        shopping_report = assistant.generate_report(candidates, include_want_list_targets=True, limit=50)
        return [self._from_shopping(row) for row in shopping_report.recommendations]

    def _collection_target_opportunities(self) -> List[OpportunityReport]:
        targets = CollectionIntelligenceEngine(self.collection_items).generate_want_list(
            limit=25,
            staged_want_list_intents=self.want_list_intents,
        )
        return [self._from_target(target) for target in targets]

    def _deal_hunter_opportunities(self, deal_hunter_results: Iterable[DealHunterResult]) -> List[OpportunityReport]:
        return [self._from_deal_hunter(result) for result in deal_hunter_results]

    def _from_shopping(self, row: ShoppingRecommendation) -> OpportunityReport:
        opportunity_type = self._type_from_text(row.item_name, row.reasons, row.want_list_status, row.source)
        risk = self._risk_from_warnings(row.warnings, row.recommendation_status)
        score_detail = OpportunityScore(
            score=row.opportunity_score,
            collection_fit=min(100, row.impact_score),
            upgrade_impact=25 if any("upgrade" in reason.lower() for reason in row.reasons) else 0,
            completion_impact=max(0, min(25, int(round(row.series_delta)))),
            liquidity=15 if row.market_context and "range" in row.market_context.lower() else 0,
            risk=risk,
            collection_priority=self._priority_from_text(row.item_name, row.reasons),
        )
        score_detail.score = self._score(score_detail, row.opportunity_score)
        return OpportunityReport(
            rank=0,
            opportunity_type=opportunity_type,
            item_name=row.item_name,
            score=score_detail.score,
            reasoning=_dedupe(row.reasons),
            risks=_dedupe(row.warnings),
            counterargument=self._counterargument(row.item_name, row.total_cost, row.warnings, opportunity_type),
            estimated_collection_impact=self._impact_summary(row),
            budget_fit=self._budget_fit(row.total_cost),
            total_cost=row.total_cost,
            source=row.source,
            recommendation=row.recommendation_status,
            score_detail=score_detail,
        )

    def _from_target(self, target: AcquisitionTarget) -> OpportunityReport:
        opportunity_type = self._type_from_text(target.coin_label, [target.reason], "", target.target_type)
        if target.target_type == "Upgrade Candidate":
            opportunity_type = OPPORTUNITY_UPGRADE
        elif target.target_type == "Missing Date" and "complete" in (target.estimated_impact or "").lower():
            opportunity_type = OPPORTUNITY_SERIES_COMPLETION
        score_detail = OpportunityScore(
            score=0,
            collection_fit=min(100, target.priority_score),
            upgrade_impact=20 if target.target_type == "Upgrade Candidate" else 0,
            completion_impact=25 if target.target_type == "Missing Date" else 0,
            liquidity=0,
            risk=5,
            collection_priority=self._priority_from_text(target.coin_label, [target.reason]),
        )
        score_detail.score = self._score(score_detail, target.priority_score)
        return OpportunityReport(
            rank=0,
            opportunity_type=opportunity_type,
            item_name=target.coin_label,
            score=score_detail.score,
            reasoning=_dedupe([target.reason]),
            risks=["No asking price supplied; budget fit requires manual review."],
            counterargument=self._counterargument(target.coin_label, 0.0, ["No asking price supplied"], opportunity_type),
            estimated_collection_impact=target.estimated_impact,
            budget_fit="No price supplied",
            total_cost=0.0,
            source=target.target_type,
            recommendation="REVIEW",
            score_detail=score_detail,
        )

    def _from_deal_hunter(self, result: DealHunterResult) -> OpportunityReport:
        opportunity_type = self._type_from_text(
            result.listing.title,
            result.reasons,
            "ON_WANT_LIST" if "Explicit WANT_LIST match" in result.reasons else "",
            "Deal Hunter",
        )
        risk = max(0, min(100, result.risk_score))
        score_detail = OpportunityScore(
            score=0,
            collection_fit=result.collection_fit_score,
            upgrade_impact=20 if "upgrade" in result.collection_status.lower() else 0,
            completion_impact=18 if "gap" in result.collection_status.lower() else 0,
            liquidity=result.liquidity_score,
            risk=risk,
            collection_priority=result.priority_score,
        )
        score_detail.score = self._score(score_detail, result.priority_score)
        return OpportunityReport(
            rank=0,
            opportunity_type=opportunity_type,
            item_name=result.listing.title,
            score=score_detail.score,
            reasoning=_dedupe(result.reasons),
            risks=_dedupe(list(result.warnings) + list(result.risk_flags)),
            counterargument=result.counterargument or self._counterargument(result.listing.title, result.listing.total_cost, result.warnings, opportunity_type),
            estimated_collection_impact=f"{result.collection_status}; max rational price CAD {result.max_rational_price:.2f}",
            budget_fit=self._budget_fit(result.listing.total_cost),
            total_cost=result.listing.total_cost,
            source="Deal Hunter",
            recommendation=result.recommendation,
            score_detail=score_detail,
        )

    def _score(self, detail: OpportunityScore, base: int) -> int:
        score = int(round(base * 0.45))
        score += int(round(detail.collection_fit * 0.22))
        score += detail.upgrade_impact
        score += detail.completion_impact
        score += int(round(detail.liquidity * 0.10))
        score += int(round(detail.collection_priority * 0.20))
        score -= int(round(detail.risk * 0.18))
        return max(0, min(100, score))

    def _type_from_text(self, item_name: str, reasons: Iterable[str], want_status: str, source: str = "") -> str:
        text = " ".join([item_name, source, " ".join(reasons or []), want_status]).lower()
        if "banknote" in text:
            return OPPORTUNITY_CANADIAN_BANKNOTE
        if "want_list" in text or "want list" in text:
            return OPPORTUNITY_WANT_LIST
        if "newfoundland" in text:
            return OPPORTUNITY_NEWFOUNDLAND
        if "upgrade" in text:
            return OPPORTUNITY_UPGRADE
        if "silver" in text or any(term in text for term in ["10 cents", "25 cents", "50 cents", "dollar", "dime", "quarter"]):
            return OPPORTUNITY_CANADIAN_SILVER
        if "missing" in text or "gap" in text:
            return OPPORTUNITY_COLLECTION_GAP
        if "within recent observed range" in text or "below recent observed range" in text:
            return OPPORTUNITY_HIGH_ROI
        return OPPORTUNITY_COLLECTION_GAP

    def _priority_from_text(self, item_name: str, reasons: Iterable[str]) -> int:
        text = " ".join([item_name, " ".join(reasons or [])]).lower()
        score = 0
        if "newfoundland" in text:
            score += 35
        if "1859" in text and "cent" in text:
            score += 28
        if "banknote" in text:
            score += 24
        if "silver" in text or any(term in text for term in ["10 cents", "25 cents", "50 cents", "dollar"]):
            score += 20
        if "want" in text:
            score += 18
        return min(100, score)

    @staticmethod
    def _risk_from_warnings(warnings: Iterable[str], status: str) -> int:
        text = " ".join(warnings or []).lower()
        risk = 0
        if "manual review" in text or status == "REVIEW":
            risk += 25
        if "duplicate" in text or status == "PASS":
            risk += 20
        if "high shipping" in text:
            risk += 18
        if "grade" in text:
            risk += 12
        return min(100, risk)

    @staticmethod
    def _counterargument(item_name: str, total_cost: float, warnings: Iterable[str], opportunity_type: str) -> str:
        points = []
        if total_cost <= 0:
            points.append("no asking price is available")
        if warnings:
            points.append("warnings require manual review")
        if opportunity_type == OPPORTUNITY_UPGRADE:
            points.append("confirm the candidate is truly better than the current holding")
        elif opportunity_type == OPPORTUNITY_COLLECTION_GAP:
            points.append("confirm the date and denomination are correctly attributed")
        elif opportunity_type == OPPORTUNITY_WANT_LIST:
            points.append("confirm it still matches the active WANT_LIST priority")
        else:
            points.append("compare against other available opportunities before buying")
        if total_cost > 0:
            points.append("budget could be saved for a stronger target")
        return "; ".join(points)

    @staticmethod
    def _impact_summary(row: ShoppingRecommendation) -> str:
        parts = [
            f"impact score {row.impact_score}",
            f"quality {row.quality_delta:+d}",
            f"series {row.series_delta:+g}%",
        ]
        if row.want_list_status:
            parts.append(row.want_list_status)
        return "; ".join(parts)

    @staticmethod
    def _budget_fit(total_cost: float) -> str:
        if total_cost <= 0:
            return "No price supplied"
        for budget in DEFAULT_BUDGETS:
            if total_cost <= budget:
                return f"Within ${budget}"
        return "Above $500"

    @staticmethod
    def _budget_sort(total_cost: float) -> float:
        return total_cost if total_cost > 0 else 999999.0

    @staticmethod
    def _best_for_budget(rows: List[OpportunityReport], budget: int) -> Optional[OpportunityReport]:
        priced = [row for row in rows if 0 < row.total_cost <= budget]
        return priced[0] if priced else None

    @staticmethod
    def _dedupe_opportunities(rows: List[OpportunityReport]) -> List[OpportunityReport]:
        selected: Dict[str, OpportunityReport] = {}
        for row in rows:
            key = " ".join(row.item_name.lower().split())
            existing = selected.get(key)
            if not existing or row.score > existing.score:
                selected[key] = row
        return list(selected.values())
