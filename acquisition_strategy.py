"""
Acquisition Strategy Engine

Orchestrates existing collection intelligence, insights, analytics, opportunity scoring,
and market intelligence into strategic acquisition plans with phased priorities,
portfolio balance guidance, and risk-adjusted recommendations.

This is NOT AI reasoning, forecasting, machine learning, or external APIs.
All strategies are deterministic, explainable, reproducible, and derived only from local collection data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional


class PriorityCategory(Enum):
    """Categories of acquisition priorities."""
    SERIES_COMPLETION = "series_completion"
    UPGRADE = "upgrade"
    WANT_LIST = "want_list"
    GAP_FILL = "gap_fill"
    DIVERSIFICATION = "diversification"
    KEY_DATE = "key_date"
    BUDGET_OPPORTUNITY = "budget_opportunity"


class PriorityLevel(Enum):
    """Priority levels for acquisition targets."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskLevel(Enum):
    """Risk levels for acquisition priorities."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Timeframe(Enum):
    """Timeframes for acquisition phases."""
    IMMEDIATE = "immediate"  # Next 1-3 purchases
    SHORT_TERM = "short_term"  # Next 3-6 months
    LONG_TERM = "long_term"  # 6-12 months


@dataclass
class AcquisitionPriority:
    """A single prioritized acquisition target."""
    id: str
    target: str
    category: PriorityCategory
    priority_level: PriorityLevel
    strategic_reason: str
    estimated_impact: str
    budget_guidance: str
    risk_level: RiskLevel
    timeframe: Timeframe
    prerequisites: List[str] = field(default_factory=list)
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AcquisitionPhase:
    """A phase in the strategic acquisition plan."""
    phase_number: int
    phase_name: str
    timeframe: Timeframe
    targets: List[AcquisitionPriority] = field(default_factory=list)
    estimated_budget: float = 0.0
    expected_outcomes: List[str] = field(default_factory=list)


@dataclass
class PortfolioBalanceRecommendation:
    """Portfolio balance recommendation for a category."""
    category: str
    current_percentage: float
    recommended_percentage: float
    reasoning: str
    priority: PriorityLevel


@dataclass
class RiskAssessment:
    """Risk assessment for the acquisition strategy."""
    overall_risk: RiskLevel
    risk_factors: List[str] = field(default_factory=list)
    mitigation_strategies: List[str] = field(default_factory=list)
    market_risk_notes: List[str] = field(default_factory=list)


@dataclass
class AcquisitionStrategyReport:
    """Complete acquisition strategy report."""
    strategy_overview: str
    collection_context: str
    strategic_plan: List[AcquisitionPhase]
    immediate_priorities: List[AcquisitionPriority]
    short_term_priorities: List[AcquisitionPriority]
    long_term_priorities: List[AcquisitionPriority]
    portfolio_balance: List[PortfolioBalanceRecommendation]
    risk_assessment: RiskAssessment
    recommended_actions: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StrategyDashboard:
    """Dashboard for acquisition strategy."""
    report: AcquisitionStrategyReport
    summary: str
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    category_breakdown: Dict[str, int]
    total_estimated_budget: float
    timestamp: datetime = field(default_factory=datetime.now)


class AcquisitionStrategyEngine:
    """Engine for generating deterministic acquisition strategies from local data."""

    def __init__(self):
        self.strategy_history: List[AcquisitionStrategyReport] = []

    def generate_strategy(
        self,
        collection_data: Optional[Dict[str, Any]] = None,
        insights_data: Optional[Dict[str, Any]] = None,
        analytics_data: Optional[Dict[str, Any]] = None,
        opportunity_data: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
        series_data: Optional[Dict[str, Any]] = None
    ) -> AcquisitionStrategyReport:
        """Generate complete acquisition strategy report."""
        collection_data = collection_data or {}
        insights_data = insights_data or {}
        analytics_data = analytics_data or {}
        opportunity_data = opportunity_data or {}
        market_data = market_data or {}
        series_data = series_data or {}

        # Generate collection context
        collection_context = self._generate_collection_context(collection_data)

        # Generate immediate priorities
        immediate_priorities = self._generate_immediate_priorities(
            collection_data, insights_data, opportunity_data, series_data
        )

        # Generate short-term priorities
        short_term_priorities = self._generate_short_term_priorities(
            collection_data, insights_data, opportunity_data, series_data
        )

        # Generate long-term priorities
        long_term_priorities = self._generate_long_term_priorities(
            collection_data, insights_data, opportunity_data, series_data
        )

        # Build strategic plan phases
        strategic_plan = self._build_strategic_plan(
            immediate_priorities, short_term_priorities, long_term_priorities
        )

        # Generate portfolio balance recommendations
        portfolio_balance = self._generate_portfolio_balance(
            collection_data, analytics_data, insights_data
        )

        # Generate risk assessment
        risk_assessment = self._generate_risk_assessment(
            collection_data, immediate_priorities, market_data
        )

        # Generate recommended actions
        recommended_actions = self._generate_recommended_actions(
            immediate_priorities, portfolio_balance, risk_assessment
        )

        # Generate strategy overview
        strategy_overview = self._generate_strategy_overview(
            collection_data, immediate_priorities, portfolio_balance
        )

        report = AcquisitionStrategyReport(
            strategy_overview=strategy_overview,
            collection_context=collection_context,
            strategic_plan=strategic_plan,
            immediate_priorities=immediate_priorities,
            short_term_priorities=short_term_priorities,
            long_term_priorities=long_term_priorities,
            portfolio_balance=portfolio_balance,
            risk_assessment=risk_assessment,
            recommended_actions=recommended_actions
        )

        self.strategy_history.append(report)
        return report

    def _generate_collection_context(self, collection_data: Dict[str, Any]) -> str:
        """Generate context about the current collection state."""
        items = collection_data.get("items", [])
        total_items = len(items)

        if not items:
            return "Collection is empty. Focus on building foundational holdings before advanced strategy."

        # Count by category
        countries = {}
        for item in items:
            country = item.get("country", "Unknown")
            countries[country] = countries.get(country, 0) + 1

        # Check for Newfoundland and Canadian silver
        newfoundland_count = sum(1 for item in items if item.get("country", "").lower() == "newfoundland")
        canada_count = sum(1 for item in items if item.get("country", "").lower() == "canada")

        context_parts = [f"Collection contains {total_items} items."]

        if newfoundland_count > 0:
            context_parts.append(f"Newfoundland holdings: {newfoundland_count} items.")
        else:
            context_parts.append("No Newfoundland items. Consider starting with key dates.")

        if canada_count > 0:
            context_parts.append(f"Canadian holdings: {canada_count} items.")
        else:
            context_parts.append("No Canadian items. Consider 1859 Large Cent or silver coinage.")

        return " ".join(context_parts)

    def _generate_immediate_priorities(
        self,
        collection_data: Dict[str, Any],
        insights_data: Dict[str, Any],
        opportunity_data: Dict[str, Any],
        series_data: Dict[str, Any]
    ) -> List[AcquisitionPriority]:
        """Generate immediate acquisition priorities (next 1-3 purchases)."""
        priorities = []
        items = collection_data.get("items", [])

        if not items:
            # Empty collection - start with foundational pieces
            priorities.append(AcquisitionPriority(
                id="imm_start_newfoundland",
                target="Newfoundland 5 Cent or 10 Cent key date",
                category=PriorityCategory.SERIES_COMPLETION,
                priority_level=PriorityLevel.HIGH,
                strategic_reason="Newfoundland coinage is the top collecting priority. Starting with a common date establishes the series foundation.",
                estimated_impact="Establishes Newfoundland collection presence. Enables future date-run completion.",
                budget_guidance="Common dates: $10-50. Focus on readable dates and decent condition.",
                risk_level=RiskLevel.LOW,
                timeframe=Timeframe.IMMEDIATE,
                prerequisites=[],
                confidence=0.9
            ))
            return priorities

        # Check for series completion opportunities
        series_definitions = series_data.get("series_definitions", [])
        for series_def in series_definitions:
            series_name = series_def.get("name", "")
            owned_dates = series_def.get("owned_dates", [])
            missing_dates = series_def.get("missing_dates", [])
            want_list_dates = series_def.get("want_list_dates", [])
            completion_pct = series_def.get("completion_percentage", 0)

            if completion_pct >= 80 and missing_dates:
                # Near completion - high priority to finish
                target = f"{series_name} missing dates: {', '.join(str(d) for d in missing_dates[:3])}"
                priorities.append(AcquisitionPriority(
                    id=f"imm_series_{series_name.lower().replace(' ', '_')}",
                    target=target,
                    category=PriorityCategory.SERIES_COMPLETION,
                    priority_level=PriorityLevel.CRITICAL,
                    strategic_reason=f"{series_name} is {completion_pct:.0f}% complete. Finishing the series provides high collection satisfaction and completion value.",
                    estimated_impact=f"Completes {series_name} series. Final completion percentage: 100%.",
                    budget_guidance="Focus on the most affordable missing dates first. Common dates under $50.",
                    risk_level=RiskLevel.LOW,
                    timeframe=Timeframe.IMMEDIATE,
                    prerequisites=[],
                    confidence=0.85
                ))
            elif 50 <= completion_pct < 80 and missing_dates:
                # Mid-completion - want list dates first
                if want_list_dates:
                    target = f"{series_name} WANT_LIST dates: {', '.join(str(d) for d in want_list_dates[:3])}"
                    priorities.append(AcquisitionPriority(
                        id=f"imm_want_{series_name.lower().replace(' ', '_')}",
                        target=target,
                        category=PriorityCategory.WANT_LIST,
                        priority_level=PriorityLevel.HIGH,
                        strategic_reason=f"{series_name} has explicit WANT_LIST targets. These are collector-identified priorities.",
                        estimated_impact=f"Progresses {series_name} toward completion while satisfying stated collecting goals.",
                        budget_guidance="WANT_LIST targets typically have budget estimates. Stay within stated ranges.",
                        risk_level=RiskLevel.MEDIUM,
                        timeframe=Timeframe.IMMEDIATE,
                        prerequisites=[],
                        confidence=0.8
                    ))

        # Check for upgrade opportunities
        upgrade_opportunities = opportunity_data.get("upgrade_opportunities", [])
        for opp in upgrade_opportunities[:2]:  # Top 2 upgrades
            target = opp.get("target", "")
            current_grade = opp.get("current_grade", "")
            upgrade_grade = opp.get("upgrade_grade", "")
            priorities.append(AcquisitionPriority(
                id=f"imm_upgrade_{target.lower().replace(' ', '_')}",
                target=f"{target} upgrade from {current_grade} to {upgrade_grade}",
                category=PriorityCategory.UPGRADE,
                priority_level=PriorityLevel.MEDIUM,
                strategic_reason="Upgrade-over-duplicate strategy: prefer quality improvements over adding duplicates.",
                estimated_impact="Improves collection quality score. Reduces duplicate count.",
                budget_guidance="Upgrade budget should be 1.5-2x the value of the current holding for meaningful improvement.",
                risk_level=RiskLevel.MEDIUM,
                timeframe=Timeframe.IMMEDIATE,
                prerequisites=[f"Verify current {target} condition before seeking upgrade"],
                confidence=0.75
            ))

        # Check for gap-fill opportunities in Adam's priorities
        # Newfoundland key dates
        has_newfoundland_key_dates = any(
            item.get("country", "").lower() == "newfoundland" and
            item.get("year", "") in ["1880", "1881", "1885", "1888", "1913", "1916"]
            for item in items
        )
        if not has_newfoundland_key_dates and any(item.get("country", "").lower() == "newfoundland" for item in items):
            priorities.append(AcquisitionPriority(
                id="imm_newf_key_date",
                target="Newfoundland key date (1880, 1881, 1885, 1888, 1913, or 1916)",
                category=PriorityCategory.KEY_DATE,
                priority_level=PriorityLevel.HIGH,
                strategic_reason="Newfoundland key dates are foundational to the collection. Adding one significantly improves series completeness and collector satisfaction.",
                estimated_impact="Major series completion boost. High collection impact for Adam-specific priorities.",
                budget_guidance="Key dates range from $50-500 depending on grade. Start with the most affordable grade.",
                risk_level=RiskLevel.MEDIUM,
                timeframe=Timeframe.IMMEDIATE,
                prerequisites=["Verify date-run gaps first"],
                confidence=0.7
            ))

        # 1859 Large Cent variety
        has_1859 = any(
            item.get("country", "").lower() == "canada" and
            item.get("year", "") == "1859" and
            "large cent" in item.get("denomination", "").lower()
            for item in items
        )
        if not has_1859:
            priorities.append(AcquisitionPriority(
                id="imm_1859_large_cent",
                target="1859 Canadian Large Cent (any variety)",
                category=PriorityCategory.KEY_DATE,
                priority_level=PriorityLevel.HIGH,
                strategic_reason="1859 Large Cent is a core Adam-specific priority. Essential for Canadian date-run completion and variety attribution.",
                estimated_impact="Establishes Canadian Large Cent foundation. Enables future variety upgrade analysis.",
                budget_guidance="$20-100 depending on grade and variety. Narrow 9 vs Wide 9 varies significantly.",
                risk_level=RiskLevel.LOW,
                timeframe=Timeframe.IMMEDIATE,
                prerequisites=[],
                confidence=0.85
            ))

        # For collections with some items but no clear immediate priorities,
        # add foundational expansion priorities
        if len(items) > 0 and len(priorities) == 0:
            # Collection exists but no series/upgrade/key date priorities triggered
            # Add small collection expansion priority
            if len(items) < 10:
                priorities.append(AcquisitionPriority(
                    id="imm_expand_collection",
                    target="Expand Newfoundland or Canadian foundational holdings",
                    category=PriorityCategory.SERIES_COMPLETION,
                    priority_level=PriorityLevel.HIGH,
                    strategic_reason="Small collection benefits from rapid foundational expansion. Focus on common dates in target series to build momentum.",
                    estimated_impact="Increases collection size and series coverage. Creates more opportunities for future upgrades and gap analysis.",
                    budget_guidance="Common dates: $10-40 each. Bulk purchases of common dates can accelerate series building.",
                    risk_level=RiskLevel.LOW,
                    timeframe=Timeframe.IMMEDIATE,
                    prerequisites=[],
                    confidence=0.8
                ))

            # Check for missing key dates even if some are present
            newfoundland_years = set(
                item.get("year", "") for item in items
                if item.get("country", "").lower() == "newfoundland"
            )
            key_dates = {"1880", "1881", "1885", "1888", "1913", "1916"}
            missing_key_dates = key_dates - newfoundland_years
            if missing_key_dates and any(item.get("country", "").lower() == "newfoundland" for item in items):
                target = f"Newfoundland missing key dates: {', '.join(sorted(missing_key_dates)[:3])}"
                priorities.append(AcquisitionPriority(
                    id="imm_newf_missing_key_dates",
                    target=target,
                    category=PriorityCategory.KEY_DATE,
                    priority_level=PriorityLevel.HIGH,
                    strategic_reason="Additional Newfoundland key dates strengthen the core collection. Each key date adds significant series value and rarity.",
                    estimated_impact="Improves key date coverage. Enhances collection prestige and completion metrics.",
                    budget_guidance="Key dates range from $50-500 depending on grade and rarity. Start with most affordable missing date.",
                    risk_level=RiskLevel.MEDIUM,
                    timeframe=Timeframe.IMMEDIATE,
                    prerequisites=["Verify current date-run gaps"],
                    confidence=0.75
                ))

            # Series continuation for low-completion series
            for series_def in series_definitions:
                series_name = series_def.get("name", "")
                completion_pct = series_def.get("completion_percentage", 0)
                missing_dates = series_def.get("missing_dates", [])
                if 0 < completion_pct < 50 and missing_dates:
                    target = f"{series_name} continuation: {', '.join(str(d) for d in missing_dates[:3])}"
                    priorities.append(AcquisitionPriority(
                        id=f"imm_continue_{series_name.lower().replace(' ', '_')}",
                        target=target,
                        category=PriorityCategory.SERIES_COMPLETION,
                        priority_level=PriorityLevel.MEDIUM,
                        strategic_reason=f"{series_name} is at {completion_pct:.0f}% completion. Early-stage series benefit from consistent additions to build toward 50% completion.",
                        estimated_impact=f"Progresses {series_name} toward 50% completion milestone. Builds series momentum.",
                        budget_guidance="Common dates: $10-40 each. Focus on affordable dates to build core coverage.",
                        risk_level=RiskLevel.LOW,
                        timeframe=Timeframe.IMMEDIATE,
                        prerequisites=[],
                        confidence=0.7
                    ))

            # Canadian silver expansion if minimal
            has_canadian_silver = any(
                item.get("country", "").lower() == "canada" and
                item.get("type", item.get("denomination", "")).lower() in ["dime", "quarter", "half dollar", "dollar"]
                for item in items
            )
            if not has_canadian_silver and any(item.get("country", "").lower() == "canada" for item in items):
                priorities.append(AcquisitionPriority(
                    id="imm_canadian_silver",
                    target="Canadian silver coinage (dime, quarter, half dollar, or dollar)",
                    category=PriorityCategory.DIVERSIFICATION,
                    priority_level=PriorityLevel.HIGH,
                    strategic_reason="Canadian silver is a core collecting priority. Adding silver coinage improves collection breadth and melt-value exposure.",
                    estimated_impact="Adds Canadian silver category. Improves collection diversity and establishes new acquisition target area.",
                    budget_guidance="Common dates: $15-75. Start with dimes or quarters for lower entry cost.",
                    risk_level=RiskLevel.LOW,
                    timeframe=Timeframe.IMMEDIATE,
                    prerequisites=["Verify melt-value tracking is enabled"],
                    confidence=0.8
                ))

        # Sort by priority level
        priority_order = {PriorityLevel.CRITICAL: 0, PriorityLevel.HIGH: 1, PriorityLevel.MEDIUM: 2, PriorityLevel.LOW: 3}
        priorities.sort(key=lambda p: priority_order.get(p.priority_level, 99))

        return priorities

    def _generate_short_term_priorities(
        self,
        collection_data: Dict[str, Any],
        insights_data: Dict[str, Any],
        opportunity_data: Dict[str, Any],
        series_data: Dict[str, Any]
    ) -> List[AcquisitionPriority]:
        """Generate short-term acquisition priorities (3-6 months)."""
        priorities = []
        items = collection_data.get("items", [])

        if not items:
            return priorities

        # Diversification: check for Canadian silver
        has_canadian_silver = any(
            item.get("country", "").lower() == "canada" and
            item.get("type", item.get("denomination", "")).lower() in ["dime", "quarter", "half dollar", "dollar"]
            for item in items
        )
        if not has_canadian_silver:
            priorities.append(AcquisitionPriority(
                id="st_canadian_silver",
                target="Canadian silver coinage (dime, quarter, half dollar, or dollar)",
                category=PriorityCategory.DIVERSIFICATION,
                priority_level=PriorityLevel.HIGH,
                strategic_reason="Canadian silver is a core collecting priority. Diversifying into silver coinage improves collection breadth and melt-value exposure.",
                estimated_impact="Adds Canadian silver category. Improves collection diversity and melt-value coverage.",
                budget_guidance="Common dates: $15-75. Start with dimes or quarters for lower entry cost.",
                risk_level=RiskLevel.LOW,
                timeframe=Timeframe.SHORT_TERM,
                prerequisites=["Verify melt-value tracking is enabled"],
                confidence=0.8
            ))

        # Series continuation: pick up where immediate left off
        series_definitions = series_data.get("series_definitions", [])
        for series_def in series_definitions:
            series_name = series_def.get("name", "")
            completion_pct = series_def.get("completion_percentage", 0)
            missing_dates = series_def.get("missing_dates", [])

            if 30 <= completion_pct < 50 and missing_dates:
                target = f"{series_name} continuation: {', '.join(str(d) for d in missing_dates[:5])}"
                priorities.append(AcquisitionPriority(
                    id=f"st_series_{series_name.lower().replace(' ', '_')}",
                    target=target,
                    category=PriorityCategory.SERIES_COMPLETION,
                    priority_level=PriorityLevel.MEDIUM,
                    strategic_reason=f"{series_name} is {completion_pct:.0f}% complete. Building toward 50%+ completion is a meaningful milestone.",
                    estimated_impact=f"Progresses {series_name} toward 50% completion. Mid-series momentum building.",
                    budget_guidance="Focus on common dates in the $10-40 range. Avoid expensive key dates until later.",
                    risk_level=RiskLevel.LOW,
                    timeframe=Timeframe.SHORT_TERM,
                    prerequisites=[f"Complete immediate {series_name} priorities first"],
                    confidence=0.75
                ))

        # Gap fills by country/denomination
        country_denom_gaps = collection_data.get("country_denomination_gaps", [])
        for gap in country_denom_gaps[:3]:
            country = gap.get("country", "")
            denomination = gap.get("denomination", "")
            missing_count = gap.get("missing_count", 0)
            priorities.append(AcquisitionPriority(
                id=f"st_gap_{country.lower()}_{denomination.lower().replace(' ', '_')}",
                target=f"{country} {denomination} gap fills ({missing_count} missing dates)",
                category=PriorityCategory.GAP_FILL,
                priority_level=PriorityLevel.MEDIUM,
                strategic_reason=f"Filling gaps in {country} {denomination} improves date-run coverage and collection completeness.",
                estimated_impact=f"Reduces missing dates by up to {missing_count}. Improves completion percentage.",
                budget_guidance="Common gap fillers: $5-30 each. Bulk common-date purchases can be efficient.",
                risk_level=RiskLevel.LOW,
                timeframe=Timeframe.SHORT_TERM,
                prerequisites=["Review existing duplicates before gap filling"],
                confidence=0.7
            ))

        return priorities

    def _generate_long_term_priorities(
        self,
        collection_data: Dict[str, Any],
        insights_data: Dict[str, Any],
        opportunity_data: Dict[str, Any],
        series_data: Dict[str, Any]
    ) -> List[AcquisitionPriority]:
        """Generate long-term acquisition priorities (6-12 months)."""
        priorities = []
        items = collection_data.get("items", [])

        if not items:
            return priorities

        # Major upgrades for high-value items
        high_value_upgrades = opportunity_data.get("high_value_upgrade_opportunities", [])
        for opp in high_value_upgrades[:2]:
            target = opp.get("target", "")
            current_grade = opp.get("current_grade", "")
            upgrade_grade = opp.get("upgrade_grade", "")
            estimated_value = opp.get("estimated_value", 0)
            priorities.append(AcquisitionPriority(
                id=f"lt_upgrade_{target.lower().replace(' ', '_')}",
                target=f"{target} major upgrade from {current_grade} to {upgrade_grade}",
                category=PriorityCategory.UPGRADE,
                priority_level=PriorityLevel.MEDIUM,
                strategic_reason="Major upgrades for high-value items improve collection quality and long-term value. These are strategic quality investments.",
                estimated_impact=f"Significant quality improvement. Estimated value impact: ${estimated_value:.0f}.",
                budget_guidance=f"Major upgrades require ${estimated_value:.0f}+ budget. Plan and save for these acquisitions.",
                risk_level=RiskLevel.HIGH,
                timeframe=Timeframe.LONG_TERM,
                prerequisites=[f"Confirm current {target} condition", "Save dedicated upgrade budget"],
                confidence=0.6
            ))

        # Rare/key date acquisitions
        rare_targets = [
            ("Newfoundland 1916 5 Cent", "Key date rarity", 200, 1000),
            ("Canada 1926 Near 6 Nickel", "Variety key date", 100, 500),
            ("Canada 1973 Large Bust Quarter", "Variety scarcity", 50, 300),
        ]
        for target, reason, min_budget, max_budget in rare_targets[:2]:
            # Check if already owned
            has_item = any(
                target.lower() in (item.get("title", "") + item.get("description", "")).lower()
                for item in items
            )
            if not has_item:
                priorities.append(AcquisitionPriority(
                    id=f"lt_rare_{target.lower().replace(' ', '_').replace('/', '_')}",
                    target=target,
                    category=PriorityCategory.KEY_DATE,
                    priority_level=PriorityLevel.LOW,
                    strategic_reason=f"{reason}. Rare/key dates appreciate in collection value and are difficult to replace.",
                    estimated_impact="High collection prestige and rarity value. Long-term acquisition satisfaction.",
                    budget_guidance=f"${min_budget}-{max_budget} depending on grade. Requires patience and market awareness.",
                    risk_level=RiskLevel.HIGH,
                    timeframe=Timeframe.LONG_TERM,
                    prerequisites=["Build foundational holdings first", "Develop market awareness for fair pricing"],
                    confidence=0.5
                ))

        # Diversification into new categories
        categories = set()
        for item in items:
            cat = item.get("category", item.get("type", item.get("denomination", "unknown")))
            categories.add(cat.lower())

        if "banknote" not in categories and "paper money" not in categories:
            priorities.append(AcquisitionPriority(
                id="lt_banknote_diversification",
                target="Canadian or Newfoundland banknote entry",
                category=PriorityCategory.DIVERSIFICATION,
                priority_level=PriorityLevel.LOW,
                strategic_reason="Banknotes add diversification beyond metal coinage. Paper money has different storage and preservation considerations.",
                estimated_impact="New collecting category. Different preservation and display requirements.",
                budget_guidance="Common banknotes: $20-100. Start with affordable grade for category exploration.",
                risk_level=RiskLevel.MEDIUM,
                timeframe=Timeframe.LONG_TERM,
                prerequisites=["Research banknote storage requirements", "Verify grading standards for paper"],
                confidence=0.6
            ))

        return priorities

    def _build_strategic_plan(
        self,
        immediate: List[AcquisitionPriority],
        short_term: List[AcquisitionPriority],
        long_term: List[AcquisitionPriority]
    ) -> List[AcquisitionPhase]:
        """Build strategic plan from prioritized targets."""
        phases = []

        if immediate:
            estimated_budget = sum(
                self._extract_budget_estimate(p.budget_guidance)
                for p in immediate
            )
            phases.append(AcquisitionPhase(
                phase_number=1,
                phase_name="Immediate Actions",
                timeframe=Timeframe.IMMEDIATE,
                targets=immediate,
                estimated_budget=estimated_budget,
                expected_outcomes=[
                    "Complete or significantly progress top series",
                    "Fill critical gaps in Adam-priority areas",
                    "Establish foundational holdings for new categories"
                ]
            ))

        if short_term:
            estimated_budget = sum(
                self._extract_budget_estimate(p.budget_guidance)
                for p in short_term
            )
            phases.append(AcquisitionPhase(
                phase_number=2,
                phase_name="Short-Term Build",
                timeframe=Timeframe.SHORT_TERM,
                targets=short_term,
                estimated_budget=estimated_budget,
                expected_outcomes=[
                    "Reach 50%+ completion on targeted series",
                    "Diversify into Canadian silver and banknotes",
                    "Complete common-date gap fills"
                ]
            ))

        if long_term:
            estimated_budget = sum(
                self._extract_budget_estimate(p.budget_guidance)
                for p in long_term
            )
            phases.append(AcquisitionPhase(
                phase_number=3,
                phase_name="Long-Term Vision",
                timeframe=Timeframe.LONG_TERM,
                targets=long_term,
                estimated_budget=estimated_budget,
                expected_outcomes=[
                    "Acquire rare/key dates for completion",
                    "Major upgrades for high-value holdings",
                    "Full diversification across collecting categories"
                ]
            ))

        return phases

    def _extract_budget_estimate(self, budget_guidance: str) -> float:
        """Extract approximate budget from guidance text."""
        import re
        # First try to find a range like $X-Y or $X to $Y
        range_match = re.search(r'\$(\d+(?:,\d{3})*)\s*(?:-|to)\s*\$?(\d+(?:,\d{3})*)', budget_guidance)
        if range_match:
            low = float(range_match.group(1).replace(",", ""))
            high = float(range_match.group(2).replace(",", ""))
            return (low + high) / 2
        
        # Single amount
        single_match = re.search(r'\$(\d+(?:,\d{3})*)', budget_guidance)
        if single_match:
            return float(single_match.group(1).replace(",", ""))
        
        return 0.0

    def _generate_portfolio_balance(
        self,
        collection_data: Dict[str, Any],
        analytics_data: Dict[str, Any],
        insights_data: Dict[str, Any]
    ) -> List[PortfolioBalanceRecommendation]:
        """Generate portfolio balance recommendations."""
        recommendations = []
        items = collection_data.get("items", [])

        if not items:
            recommendations.append(PortfolioBalanceRecommendation(
                category="Overall Collection",
                current_percentage=0.0,
                recommended_percentage=100.0,
                reasoning="Collection is empty. 100% of acquisition budget should go to foundational purchases.",
                priority=PriorityLevel.CRITICAL
            ))
            return recommendations

        total_items = len(items)

        # Calculate current category percentages
        country_counts = {}
        for item in items:
            country = item.get("country", "Unknown")
            country_counts[country] = country_counts.get(country, 0) + 1

        # Newfoundland balance
        newfoundland_pct = (country_counts.get("Newfoundland", 0) / total_items) * 100
        if newfoundland_pct < 30:
            recommendations.append(PortfolioBalanceRecommendation(
                category="Newfoundland Coinage",
                current_percentage=newfoundland_pct,
                recommended_percentage=30.0,
                reasoning="Newfoundland is the top Adam-specific priority. Currently underweight. Increase allocation to 30% for proper series development.",
                priority=PriorityLevel.HIGH
            ))
        else:
            recommendations.append(PortfolioBalanceRecommendation(
                category="Newfoundland Coinage",
                current_percentage=newfoundland_pct,
                recommended_percentage=30.0,
                reasoning="Newfoundland allocation is on target. Maintain current focus while exploring other categories.",
                priority=PriorityLevel.LOW
            ))

        # Canadian silver balance
        canada_count = country_counts.get("Canada", 0)
        canadian_silver_count = sum(
            1 for item in items
            if item.get("country", "") == "Canada" and
            item.get("type", item.get("denomination", "")).lower() in ["dime", "quarter", "half dollar", "dollar"]
        )
        canadian_silver_pct = (canadian_silver_count / total_items) * 100 if total_items > 0 else 0

        if canadian_silver_pct < 20:
            recommendations.append(PortfolioBalanceRecommendation(
                category="Canadian Silver",
                current_percentage=canadian_silver_pct,
                recommended_percentage=20.0,
                reasoning="Canadian silver is underweight. Silver coinage provides melt-value exposure and historical significance. Target 20% allocation.",
                priority=PriorityLevel.MEDIUM
            ))
        else:
            recommendations.append(PortfolioBalanceRecommendation(
                category="Canadian Silver",
                current_percentage=canadian_silver_pct,
                recommended_percentage=20.0,
                reasoning="Canadian silver allocation is on target. Maintain while exploring upgrades.",
                priority=PriorityLevel.LOW
            ))

        # 1859 Large Cent balance
        large_cent_count = sum(
            1 for item in items
            if item.get("country", "") == "Canada" and
            item.get("year", "") == "1859" and
            "large cent" in item.get("denomination", "").lower()
        )
        large_cent_pct = (large_cent_count / total_items) * 100 if total_items > 0 else 0

        if large_cent_count == 0:
            recommendations.append(PortfolioBalanceRecommendation(
                category="1859 Large Cent Varieties",
                current_percentage=0.0,
                recommended_percentage=5.0,
                reasoning="No 1859 Large Cent in collection. This is a core variety-priority area. At least one example is essential.",
                priority=PriorityLevel.HIGH
            ))
        else:
            recommendations.append(PortfolioBalanceRecommendation(
                category="1859 Large Cent Varieties",
                current_percentage=large_cent_pct,
                recommended_percentage=5.0,
                reasoning="1859 Large Cent present. Focus on variety upgrades (Narrow 9, Wide 9, 8/9) rather than quantity.",
                priority=PriorityLevel.LOW
            ))

        # Diversification check
        unique_countries = len(country_counts)
        if unique_countries < 3:
            recommendations.append(PortfolioBalanceRecommendation(
                category="Geographic Diversification",
                current_percentage=(unique_countries / 3) * 100,
                recommended_percentage=100.0,
                reasoning=f"Only {unique_countries} countries represented. Consider adding UK, US, or world coins for broader collecting interest.",
                priority=PriorityLevel.MEDIUM
            ))
        else:
            recommendations.append(PortfolioBalanceRecommendation(
                category="Geographic Diversification",
                current_percentage=(unique_countries / 3) * 100,
                recommended_percentage=100.0,
                reasoning="Good geographic diversity. Focus on depth rather than breadth.",
                priority=PriorityLevel.LOW
            ))

        return recommendations

    def _generate_risk_assessment(
        self,
        collection_data: Dict[str, Any],
        immediate_priorities: List[AcquisitionPriority],
        market_data: Dict[str, Any]
    ) -> RiskAssessment:
        """Generate risk assessment for the acquisition strategy."""
        items = collection_data.get("items", [])
        risk_factors = []
        mitigation_strategies = []
        market_risk_notes = []

        # Empty collection risk
        if not items:
            risk_factors.append("Empty collection: No baseline for strategic decisions")
            mitigation_strategies.append("Start with common, affordable dates to establish baseline")
            return RiskAssessment(
                overall_risk=RiskLevel.HIGH,
                risk_factors=risk_factors,
                mitigation_strategies=mitigation_strategies,
                market_risk_notes=market_risk_notes
            )

        # Budget concentration risk
        critical_count = sum(1 for p in immediate_priorities if p.priority_level == PriorityLevel.CRITICAL)
        if critical_count > 2:
            risk_factors.append(f"High critical priority count ({critical_count}): Budget may be stretched across too many targets")
            mitigation_strategies.append("Rank critical priorities by estimated impact and focus on top 2")

        # Key date availability risk
        key_date_targets = [p for p in immediate_priorities if p.category == PriorityCategory.KEY_DATE]
        if key_date_targets:
            risk_factors.append("Key date targets may have limited availability and require patience")
            mitigation_strategies.append("Set watchlist alerts for key dates. Be prepared to wait for the right example.")
            market_risk_notes.append("Key date prices can vary significantly by grade and market conditions")

        # Upgrade risk
        upgrade_targets = [p for p in immediate_priorities if p.category == PriorityCategory.UPGRADE]
        if upgrade_targets:
            risk_factors.append("Upgrade purchases require careful grade verification to avoid marginal improvements")
            mitigation_strategies.append("Verify current holding condition before seeking upgrade. Target meaningful grade jumps (2+ points).")
            market_risk_notes.append("Upgrade premiums vary. Ensure the price differential justifies the quality improvement.")

        # Series completion risk
        series_targets = [p for p in immediate_priorities if p.category == PriorityCategory.SERIES_COMPLETION]
        if series_targets:
            risk_factors.append("Series completion can lead to expensive final-date acquisitions")
            mitigation_strategies.append("Complete common dates first. Budget separately for key dates.")

        # Overall risk assessment
        high_risk_count = sum(1 for p in immediate_priorities if p.risk_level == RiskLevel.HIGH)
        medium_risk_count = sum(1 for p in immediate_priorities if p.risk_level == RiskLevel.MEDIUM)

        if high_risk_count > 0:
            overall_risk = RiskLevel.HIGH
        elif medium_risk_count > 2:
            overall_risk = RiskLevel.MEDIUM
        else:
            overall_risk = RiskLevel.LOW

        return RiskAssessment(
            overall_risk=overall_risk,
            risk_factors=risk_factors,
            mitigation_strategies=mitigation_strategies,
            market_risk_notes=market_risk_notes
        )

    def _generate_recommended_actions(
        self,
        immediate_priorities: List[AcquisitionPriority],
        portfolio_balance: List[PortfolioBalanceRecommendation],
        risk_assessment: RiskAssessment
    ) -> List[str]:
        """Generate recommended actions from the strategy."""
        actions = []

        # Immediate action recommendations
        if immediate_priorities:
            top_priority = immediate_priorities[0]
            actions.append(f"1. Focus immediate budget on: {top_priority.target} ({top_priority.priority_level.value})")

        # Portfolio balance actions
        high_balance = [b for b in portfolio_balance if b.priority == PriorityLevel.HIGH or b.priority == PriorityLevel.CRITICAL]
        for balance in high_balance:
            actions.append(f"Rebalance {balance.category}: currently {balance.current_percentage:.1f}%, target {balance.recommended_percentage:.1f}%")

        # Risk mitigation actions
        for mitigation in risk_assessment.mitigation_strategies:
            actions.append(f"Risk mitigation: {mitigation}")

        # General strategy actions
        actions.append("Review acquisition strategy monthly and adjust priorities based on new opportunities")
        actions.append("Set watchlist alerts for key dates and rare varieties")
        actions.append("Track actual spending against estimated budgets for each acquisition")

        return actions

    def _generate_strategy_overview(
        self,
        collection_data: Dict[str, Any],
        immediate_priorities: List[AcquisitionPriority],
        portfolio_balance: List[PortfolioBalanceRecommendation]
    ) -> str:
        """Generate high-level strategy overview."""
        items = collection_data.get("items", [])
        total_items = len(items)

        if not items:
            return (
                "STRATEGY: Build foundational collection. "
                "Start with Newfoundland common dates and Canadian silver. "
                "Focus on affordable, readable examples before rare varieties."
            )

        # Count priorities by category
        category_counts = {}
        for p in immediate_priorities:
            cat = p.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # Determine dominant strategy theme
        if category_counts.get("series_completion", 0) > 0:
            theme = "series completion"
        elif category_counts.get("upgrade", 0) > 0:
            theme = "quality upgrades"
        elif category_counts.get("want_list", 0) > 0:
            theme = "WANT_LIST fulfillment"
        else:
            theme = "gap filling"

        # Check balance issues
        balance_issues = [b for b in portfolio_balance if b.priority in (PriorityLevel.HIGH, PriorityLevel.CRITICAL)]
        if balance_issues:
            balance_str = f"Address {len(balance_issues)} portfolio balance issues. "
        else:
            balance_str = "Portfolio balance is acceptable. "

        return (
            f"STRATEGY: Collection of {total_items} items. "
            f"Primary focus: {theme}. "
            f"{balance_str}"
            f"{len(immediate_priorities)} immediate priorities identified. "
            "All recommendations are deterministic and based on local collection data only."
        )

    def generate_dashboard(self, report: AcquisitionStrategyReport) -> StrategyDashboard:
        """Generate strategy dashboard from report."""
        # Count priorities by level
        all_priorities = (
            report.immediate_priorities +
            report.short_term_priorities +
            report.long_term_priorities
        )

        critical_count = sum(1 for p in all_priorities if p.priority_level == PriorityLevel.CRITICAL)
        high_count = sum(1 for p in all_priorities if p.priority_level == PriorityLevel.HIGH)
        medium_count = sum(1 for p in all_priorities if p.priority_level == PriorityLevel.MEDIUM)
        low_count = sum(1 for p in all_priorities if p.priority_level == PriorityLevel.LOW)

        # Category breakdown
        category_breakdown = {}
        for p in all_priorities:
            cat = p.category.value
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1

        # Total estimated budget
        total_budget = sum(phase.estimated_budget for phase in report.strategic_plan)

        # Summary
        summary = (
            f"Acquisition Strategy: {len(report.immediate_priorities)} immediate, "
            f"{len(report.short_term_priorities)} short-term, "
            f"{len(report.long_term_priorities)} long-term priorities. "
            f"Risk level: {report.risk_assessment.overall_risk.value}. "
            f"Estimated total budget: ${total_budget:.0f}."
        )

        return StrategyDashboard(
            report=report,
            summary=summary,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            category_breakdown=category_breakdown,
            total_estimated_budget=total_budget
        )

    def export_strategy_markdown(self, report: AcquisitionStrategyReport) -> str:
        """Export strategy report as Markdown."""
        lines = [
            "# Acquisition Strategy Report",
            "",
            f"Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Strategy Overview",
            "",
            report.strategy_overview,
            "",
            "## Collection Context",
            "",
            report.collection_context,
            "",
            "## Strategic Plan",
            ""
        ]

        for phase in report.strategic_plan:
            lines.extend([
                f"### Phase {phase.phase_number}: {phase.phase_name}",
                "",
                f"Timeframe: {phase.timeframe.value}",
                f"Estimated Budget: ${phase.estimated_budget:.0f}",
                "",
                "Expected Outcomes:",
            ])
            for outcome in phase.expected_outcomes:
                lines.append(f"- {outcome}")
            lines.append("")

            lines.append("Targets:")
            for target in phase.targets:
                lines.append(f"- **{target.target}** ({target.priority_level.value}, {target.risk_level.value} risk)")
                lines.append(f"  - Reason: {target.strategic_reason}")
                lines.append(f"  - Budget: {target.budget_guidance}")
            lines.append("")

        lines.extend([
            "## Immediate Priorities",
            ""
        ])
        for p in report.immediate_priorities:
            lines.extend([
                f"### {p.target}",
                "",
                f"- Category: {p.category.value}",
                f"- Priority: {p.priority_level.value}",
                f"- Risk: {p.risk_level.value}",
                f"- Confidence: {p.confidence:.1%}",
                f"- Reason: {p.strategic_reason}",
                f"- Impact: {p.estimated_impact}",
                f"- Budget: {p.budget_guidance}",
                ""
            ])

        lines.extend([
            "## Portfolio Balance",
            ""
        ])
        for balance in report.portfolio_balance:
            lines.extend([
                f"### {balance.category}",
                "",
                f"- Current: {balance.current_percentage:.1f}%",
                f"- Recommended: {balance.recommended_percentage:.1f}%",
                f"- Priority: {balance.priority.value}",
                f"- Reasoning: {balance.reasoning}",
                ""
            ])

        lines.extend([
            "## Risk Assessment",
            "",
            f"**Overall Risk: {report.risk_assessment.overall_risk.value}**",
            ""
        ])
        if report.risk_assessment.risk_factors:
            lines.append("### Risk Factors")
            lines.append("")
            for factor in report.risk_assessment.risk_factors:
                lines.append(f"- {factor}")
            lines.append("")
        if report.risk_assessment.mitigation_strategies:
            lines.append("### Mitigation Strategies")
            lines.append("")
            for strategy in report.risk_assessment.mitigation_strategies:
                lines.append(f"- {strategy}")
            lines.append("")
        if report.risk_assessment.market_risk_notes:
            lines.append("### Market Risk Notes")
            lines.append("")
            for note in report.risk_assessment.market_risk_notes:
                lines.append(f"- {note}")
            lines.append("")

        lines.extend([
            "## Recommended Actions",
            ""
        ])
        for i, action in enumerate(report.recommended_actions, 1):
            lines.append(f"{i}. {action}")
        lines.append("")

        return "\n".join(lines)

    def export_strategy_csv(self, report: AcquisitionStrategyReport) -> str:
        """Export strategy report as CSV."""
        lines = [
            "ID,Target,Category,Priority,Risk,Timeframe,Confidence,Strategic Reason,Estimated Impact,Budget Guidance"
        ]

        all_priorities = (
            report.immediate_priorities +
            report.short_term_priorities +
            report.long_term_priorities
        )

        for p in all_priorities:
            lines.append(
                f'"{p.id}","{p.target}","{p.category.value}","{p.priority_level.value}",'
                f'"{p.risk_level.value}","{p.timeframe.value}",{p.confidence:.2f},'
                f'"{p.strategic_reason}","{p.estimated_impact}","{p.budget_guidance}"'
            )

        return "\n".join(lines)

    def export_priorities_markdown(self, priorities: List[AcquisitionPriority]) -> str:
        """Export priorities as Markdown."""
        lines = ["# Acquisition Priorities", ""]

        for p in priorities:
            lines.extend([
                f"## {p.target}",
                "",
                f"- Category: {p.category.value}",
                f"- Priority: {p.priority_level.value}",
                f"- Risk: {p.risk_level.value}",
                f"- Timeframe: {p.timeframe.value}",
                f"- Confidence: {p.confidence:.1%}",
                f"- Strategic Reason: {p.strategic_reason}",
                f"- Estimated Impact: {p.estimated_impact}",
                f"- Budget Guidance: {p.budget_guidance}",
                ""
            ])
            if p.prerequisites:
                lines.append("Prerequisites:")
                for prereq in p.prerequisites:
                    lines.append(f"- {prereq}")
                lines.append("")

        return "\n".join(lines)

    def export_priorities_csv(self, priorities: List[AcquisitionPriority]) -> str:
        """Export priorities as CSV."""
        lines = [
            "ID,Target,Category,Priority,Risk,Timeframe,Confidence,Strategic Reason,Estimated Impact,Budget Guidance,Prerequisites"
        ]

        for p in priorities:
            prereqs = "; ".join(p.prerequisites) if p.prerequisites else ""
            lines.append(
                f'"{p.id}","{p.target}","{p.category.value}","{p.priority_level.value}",'
                f'"{p.risk_level.value}","{p.timeframe.value}",{p.confidence:.2f},'
                f'"{p.strategic_reason}","{p.estimated_impact}","{p.budget_guidance}",'
                f'"{prereqs}"'
            )

        return "\n".join(lines)
