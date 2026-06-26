"""
Tests for the Acquisition Strategy Engine.

These tests verify deterministic acquisition strategy generation without AI,
forecasting, machine learning, or external APIs.
"""

import unittest
from datetime import datetime

from acquisition_strategy import (
    AcquisitionStrategyEngine,
    AcquisitionPriority,
    AcquisitionPhase,
    PortfolioBalanceRecommendation,
    RiskAssessment,
    AcquisitionStrategyReport,
    StrategyDashboard,
    PriorityCategory,
    PriorityLevel,
    RiskLevel,
    Timeframe,
)


class TestAcquisitionStrategyEngine(unittest.TestCase):
    """Test suite for AcquisitionStrategyEngine."""

    def setUp(self):
        """Set up test fixtures."""
        self.engine = AcquisitionStrategyEngine()
        self.empty_collection = {"items": []}
        self.sample_collection = {
            "items": [
                {"country": "Newfoundland", "year": "1880", "denomination": "5 Cent", "type": "5 Cent"},
                {"country": "Newfoundland", "year": "1881", "denomination": "10 Cent", "type": "10 Cent"},
                {"country": "Canada", "year": "1859", "denomination": "Large Cent", "type": "Large Cent"},
                {"country": "Canada", "year": "1920", "denomination": "Dime", "type": "Dime"},
            ]
        }
        self.series_data = {
            "series_definitions": [
                {
                    "name": "Newfoundland 5 Cent",
                    "owned_dates": ["1880"],
                    "missing_dates": ["1881", "1882", "1883"],
                    "want_list_dates": ["1881"],
                    "completion_percentage": 25
                },
                {
                    "name": "Newfoundland 10 Cent",
                    "owned_dates": ["1881"],
                    "missing_dates": ["1880", "1882", "1883"],
                    "want_list_dates": [],
                    "completion_percentage": 25
                }
            ]
        }

    def test_engine_initialization(self):
        """Test engine initializes with empty history."""
        self.assertEqual(len(self.engine.strategy_history), 0)

    def test_generate_strategy_empty_collection(self):
        """Test strategy generation for empty collection."""
        report = self.engine.generate_strategy(collection_data=self.empty_collection)

        self.assertIsInstance(report, AcquisitionStrategyReport)
        self.assertIn("empty", report.collection_context.lower())
        self.assertTrue(len(report.immediate_priorities) > 0)
        self.assertIsInstance(report.risk_assessment, RiskAssessment)
        self.assertTrue(len(report.recommended_actions) > 0)
        self.assertEqual(len(self.engine.strategy_history), 1)

    def test_generate_strategy_with_collection(self):
        """Test strategy generation with sample collection."""
        report = self.engine.generate_strategy(
            collection_data=self.sample_collection,
            series_data=self.series_data
        )

        self.assertIsInstance(report, AcquisitionStrategyReport)
        self.assertIn("4 items", report.collection_context)
        self.assertTrue(len(report.immediate_priorities) > 0)
        self.assertTrue(len(report.short_term_priorities) >= 0)
        self.assertTrue(len(report.long_term_priorities) >= 0)
        self.assertTrue(len(report.portfolio_balance) > 0)
        self.assertIsInstance(report.risk_assessment, RiskAssessment)
        self.assertTrue(len(report.recommended_actions) > 0)
        self.assertTrue(len(report.strategic_plan) > 0)

    def test_immediate_priorities_empty_collection(self):
        """Test immediate priorities for empty collection."""
        priorities = self.engine._generate_immediate_priorities(
            self.empty_collection, {}, {}, {}
        )

        self.assertTrue(len(priorities) > 0)
        # Empty collection should suggest starting with Newfoundland
        newfoundland_priority = next(
            (p for p in priorities if "newfoundland" in p.target.lower()),
            None
        )
        self.assertIsNotNone(newfoundland_priority)
        self.assertEqual(newfoundland_priority.timeframe, Timeframe.IMMEDIATE)

    def test_immediate_priorities_with_series_data(self):
        """Test immediate priorities with series completion data."""
        priorities = self.engine._generate_immediate_priorities(
            self.sample_collection, {}, {}, self.series_data
        )

        self.assertTrue(len(priorities) > 0)
        # Should have priorities for series completion
        series_priorities = [p for p in priorities if p.category == PriorityCategory.SERIES_COMPLETION]
        self.assertTrue(len(series_priorities) > 0)

    def test_portfolio_balance_empty_collection(self):
        """Test portfolio balance for empty collection."""
        balance = self.engine._generate_portfolio_balance(
            self.empty_collection, {}, {}
        )

        self.assertEqual(len(balance), 1)
        self.assertEqual(balance[0].category, "Overall Collection")
        self.assertEqual(balance[0].priority, PriorityLevel.CRITICAL)

    def test_portfolio_balance_with_collection(self):
        """Test portfolio balance with sample collection."""
        balance = self.engine._generate_portfolio_balance(
            self.sample_collection, {}, {}
        )

        self.assertTrue(len(balance) > 0)
        # Should have Newfoundland balance recommendation
        newfoundland = next(
            (b for b in balance if "Newfoundland" in b.category),
            None
        )
        self.assertIsNotNone(newfoundland)

    def test_risk_assessment_empty_collection(self):
        """Test risk assessment for empty collection."""
        risk = self.engine._generate_risk_assessment(
            self.empty_collection, [], {}
        )

        self.assertEqual(risk.overall_risk, RiskLevel.HIGH)
        self.assertTrue(len(risk.risk_factors) > 0)
        self.assertTrue(len(risk.mitigation_strategies) > 0)

    def test_risk_assessment_with_priorities(self):
        """Test risk assessment with priorities."""
        priorities = self.engine._generate_immediate_priorities(
            self.sample_collection, {}, {}, self.series_data
        )
        risk = self.engine._generate_risk_assessment(
            self.sample_collection, priorities, {}
        )

        self.assertIn(risk.overall_risk, [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH])

    def test_strategic_plan_building(self):
        """Test strategic plan building."""
        immediate = self.engine._generate_immediate_priorities(
            self.sample_collection, {}, {}, self.series_data
        )
        short_term = self.engine._generate_short_term_priorities(
            self.sample_collection, {}, {}, self.series_data
        )
        long_term = self.engine._generate_long_term_priorities(
            self.sample_collection, {}, {}, self.series_data
        )

        plan = self.engine._build_strategic_plan(immediate, short_term, long_term)

        self.assertTrue(len(plan) > 0)
        for phase in plan:
            self.assertIsInstance(phase, AcquisitionPhase)
            self.assertTrue(phase.phase_number > 0)
            self.assertTrue(len(phase.phase_name) > 0)
            self.assertTrue(len(phase.targets) > 0)

    def test_generate_dashboard(self):
        """Test dashboard generation."""
        report = self.engine.generate_strategy(collection_data=self.sample_collection)
        dashboard = self.engine.generate_dashboard(report)

        self.assertIsInstance(dashboard, StrategyDashboard)
        self.assertTrue(len(dashboard.summary) > 0)
        self.assertGreaterEqual(dashboard.critical_count, 0)
        self.assertGreaterEqual(dashboard.high_count, 0)
        self.assertGreaterEqual(dashboard.medium_count, 0)
        self.assertGreaterEqual(dashboard.low_count, 0)
        self.assertIsInstance(dashboard.category_breakdown, dict)
        self.assertGreaterEqual(dashboard.total_estimated_budget, 0)

    def test_export_strategy_markdown(self):
        """Test strategy markdown export."""
        report = self.engine.generate_strategy(collection_data=self.sample_collection)
        markdown = self.engine.export_strategy_markdown(report)

        self.assertIn("# Acquisition Strategy Report", markdown)
        self.assertIn("## Strategy Overview", markdown)
        self.assertIn("## Collection Context", markdown)
        self.assertIn("## Strategic Plan", markdown)
        self.assertIn("## Immediate Priorities", markdown)
        self.assertIn("## Portfolio Balance", markdown)
        self.assertIn("## Risk Assessment", markdown)
        self.assertIn("## Recommended Actions", markdown)

    def test_export_strategy_csv(self):
        """Test strategy CSV export."""
        report = self.engine.generate_strategy(collection_data=self.sample_collection)
        csv = self.engine.export_strategy_csv(report)

        lines = csv.split("\n")
        self.assertEqual(len(lines) > 1, True)
        self.assertIn("ID,Target,Category,Priority,Risk,Timeframe", lines[0])

    def test_export_priorities_markdown(self):
        """Test priorities markdown export."""
        priorities = self.engine._generate_immediate_priorities(
            self.sample_collection, {}, {}, self.series_data
        )
        markdown = self.engine.export_priorities_markdown(priorities)

        self.assertIn("# Acquisition Priorities", markdown)
        for p in priorities:
            self.assertIn(p.target, markdown)

    def test_export_priorities_csv(self):
        """Test priorities CSV export."""
        priorities = self.engine._generate_immediate_priorities(
            self.sample_collection, {}, {}, self.series_data
        )
        csv = self.engine.export_priorities_csv(priorities)

        lines = csv.split("\n")
        self.assertEqual(len(lines) > 1, True)
        self.assertIn("ID,Target,Category,Priority,Risk,Timeframe", lines[0])

    def test_budget_extraction(self):
        """Test budget extraction from guidance text."""
        self.assertEqual(self.engine._extract_budget_estimate("$10-50"), 30.0)
        self.assertEqual(self.engine._extract_budget_estimate("$100"), 100.0)
        self.assertEqual(self.engine._extract_budget_estimate("$50-500 depending on grade"), 275.0)
        self.assertEqual(self.engine._extract_budget_estimate("No budget mentioned"), 0.0)

    def test_collection_context_generation(self):
        """Test collection context generation."""
        context = self.engine._generate_collection_context(self.sample_collection)
        self.assertIn("4 items", context)
        self.assertIn("Newfoundland", context)
        self.assertIn("Canadian", context)

    def test_strategy_overview(self):
        """Test strategy overview generation."""
        immediate = self.engine._generate_immediate_priorities(
            self.sample_collection, {}, {}, self.series_data
        )
        balance = self.engine._generate_portfolio_balance(
            self.sample_collection, {}, {}
        )
        overview = self.engine._generate_strategy_overview(
            self.sample_collection, immediate, balance
        )

        self.assertIn("STRATEGY", overview)
        self.assertIn("4 items", overview)
        self.assertIn("deterministic", overview.lower())

    def test_recommended_actions(self):
        """Test recommended actions generation."""
        immediate = self.engine._generate_immediate_priorities(
            self.sample_collection, {}, {}, self.series_data
        )
        balance = self.engine._generate_portfolio_balance(
            self.sample_collection, {}, {}
        )
        risk = self.engine._generate_risk_assessment(
            self.sample_collection, immediate, {}
        )
        actions = self.engine._generate_recommended_actions(immediate, balance, risk)

        self.assertTrue(len(actions) > 0)
        self.assertTrue(any("Focus immediate" in a for a in actions))
        self.assertTrue(any("Review acquisition strategy" in a for a in actions))

    def test_short_term_priorities(self):
        """Test short-term priorities generation."""
        priorities = self.engine._generate_short_term_priorities(
            self.sample_collection, {}, {}, self.series_data
        )

        # Should include diversification and series continuation
        self.assertIsInstance(priorities, list)
        for p in priorities:
            self.assertEqual(p.timeframe, Timeframe.SHORT_TERM)

    def test_long_term_priorities(self):
        """Test long-term priorities generation."""
        priorities = self.engine._generate_long_term_priorities(
            self.sample_collection, {}, {}, self.series_data
        )

        self.assertIsInstance(priorities, list)
        for p in priorities:
            self.assertEqual(p.timeframe, Timeframe.LONG_TERM)

    def test_priority_sorting(self):
        """Test that priorities are sorted correctly."""
        priorities = self.engine._generate_immediate_priorities(
            self.sample_collection, {}, {}, self.series_data
        )

        # CRITICAL should come before HIGH, which comes before MEDIUM, etc.
        priority_order = {
            PriorityLevel.CRITICAL: 0,
            PriorityLevel.HIGH: 1,
            PriorityLevel.MEDIUM: 2,
            PriorityLevel.LOW: 3
        }
        for i in range(len(priorities) - 1):
            current_order = priority_order.get(priorities[i].priority_level, 99)
            next_order = priority_order.get(priorities[i + 1].priority_level, 99)
            self.assertLessEqual(current_order, next_order)

    def test_strategy_history_accumulation(self):
        """Test that strategy history accumulates."""
        self.engine.generate_strategy(collection_data=self.sample_collection)
        self.assertEqual(len(self.engine.strategy_history), 1)

        self.engine.generate_strategy(collection_data=self.sample_collection)
        self.assertEqual(len(self.engine.strategy_history), 2)

    def test_empty_series_data(self):
        """Test with empty series data."""
        report = self.engine.generate_strategy(
            collection_data=self.sample_collection,
            series_data={"series_definitions": []}
        )

        self.assertIsInstance(report, AcquisitionStrategyReport)
        self.assertTrue(len(report.immediate_priorities) > 0)

    def test_canadian_silver_detection(self):
        """Test Canadian silver detection in portfolio balance."""
        collection_with_silver = {
            "items": [
                {"country": "Canada", "year": "1920", "denomination": "Dime", "type": "Dime"},
                {"country": "Canada", "year": "1921", "denomination": "Quarter", "type": "Quarter"},
                {"country": "Canada", "year": "1922", "denomination": "Half Dollar", "type": "Half Dollar"},
            ]
        }
        balance = self.engine._generate_portfolio_balance(
            collection_with_silver, {}, {}
        )

        silver_balance = next(
            (b for b in balance if "Canadian Silver" in b.category),
            None
        )
        self.assertIsNotNone(silver_balance)
        self.assertGreater(silver_balance.current_percentage, 0)

    def test_newfoundland_key_date_priority(self):
        """Test Newfoundland key date priority generation."""
        collection = {
            "items": [
                {"country": "Newfoundland", "year": "1890", "denomination": "5 Cent", "type": "5 Cent"},
            ]
        }
        priorities = self.engine._generate_immediate_priorities(
            collection, {}, {}, {}
        )

        key_date = next(
            (p for p in priorities if "key date" in p.target.lower()),
            None
        )
        self.assertIsNotNone(key_date)
        self.assertEqual(key_date.category, PriorityCategory.KEY_DATE)

    def test_1859_large_cent_priority(self):
        """Test 1859 Large Cent priority generation."""
        collection = {
            "items": [
                {"country": "Canada", "year": "1920", "denomination": "Dime", "type": "Dime"},
            ]
        }
        priorities = self.engine._generate_immediate_priorities(
            collection, {}, {}, {}
        )

        large_cent = next(
            (p for p in priorities if "1859" in p.target and "Large Cent" in p.target),
            None
        )
        self.assertIsNotNone(large_cent)
        self.assertEqual(large_cent.category, PriorityCategory.KEY_DATE)


class TestDataClasses(unittest.TestCase):
    """Test data class creation and defaults."""

    def test_acquisition_priority_defaults(self):
        """Test AcquisitionPriority defaults."""
        priority = AcquisitionPriority(
            id="test",
            target="Test Target",
            category=PriorityCategory.GAP_FILL,
            priority_level=PriorityLevel.MEDIUM,
            strategic_reason="Test reason",
            estimated_impact="Test impact",
            budget_guidance="$10-50",
            risk_level=RiskLevel.LOW,
            timeframe=Timeframe.IMMEDIATE
        )
        self.assertEqual(priority.prerequisites, [])
        self.assertEqual(priority.confidence, 0.0)
        self.assertIsInstance(priority.timestamp, datetime)

    def test_acquisition_phase_defaults(self):
        """Test AcquisitionPhase defaults."""
        phase = AcquisitionPhase(
            phase_number=1,
            phase_name="Test",
            timeframe=Timeframe.IMMEDIATE
        )
        self.assertEqual(phase.targets, [])
        self.assertEqual(phase.estimated_budget, 0.0)
        self.assertEqual(phase.expected_outcomes, [])

    def test_risk_assessment_defaults(self):
        """Test RiskAssessment defaults."""
        risk = RiskAssessment(overall_risk=RiskLevel.LOW)
        self.assertEqual(risk.risk_factors, [])
        self.assertEqual(risk.mitigation_strategies, [])
        self.assertEqual(risk.market_risk_notes, [])

    def test_strategy_report(self):
        """Test AcquisitionStrategyReport creation."""
        report = AcquisitionStrategyReport(
            strategy_overview="Test overview",
            collection_context="Test context",
            strategic_plan=[],
            immediate_priorities=[],
            short_term_priorities=[],
            long_term_priorities=[],
            portfolio_balance=[],
            risk_assessment=RiskAssessment(overall_risk=RiskLevel.LOW),
            recommended_actions=[]
        )
        self.assertIsInstance(report.timestamp, datetime)

    def test_strategy_dashboard(self):
        """Test StrategyDashboard creation."""
        report = AcquisitionStrategyReport(
            strategy_overview="",
            collection_context="",
            strategic_plan=[],
            immediate_priorities=[],
            short_term_priorities=[],
            long_term_priorities=[],
            portfolio_balance=[],
            risk_assessment=RiskAssessment(overall_risk=RiskLevel.LOW),
            recommended_actions=[]
        )
        dashboard = StrategyDashboard(
            report=report,
            summary="Test summary",
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            category_breakdown={},
            total_estimated_budget=0.0
        )
        self.assertIsInstance(dashboard.timestamp, datetime)


class TestIntegrationWithExistingEngines(unittest.TestCase):
    """Test integration with existing engine data formats."""

    def setUp(self):
        self.engine = AcquisitionStrategyEngine()

    def test_with_insights_data(self):
        """Test strategy generation with insights data."""
        insights_data = {
            "top_priorities": [
                {"title": "Missing Newfoundland dates", "priority": "high"},
                {"title": "Low photo coverage", "priority": "medium"}
            ]
        }
        report = self.engine.generate_strategy(
            collection_data={"items": [{"country": "Canada", "year": "1920", "denomination": "Dime"}]},
            insights_data=insights_data
        )
        self.assertIsInstance(report, AcquisitionStrategyReport)

    def test_with_analytics_data(self):
        """Test strategy generation with analytics data."""
        analytics_data = {
            "collection_metrics": {"total_items": 5, "countries": 2}
        }
        report = self.engine.generate_strategy(
            collection_data={"items": [{"country": "Canada", "year": "1920", "denomination": "Dime"}]},
            analytics_data=analytics_data
        )
        self.assertIsInstance(report, AcquisitionStrategyReport)

    def test_with_opportunity_data(self):
        """Test strategy generation with opportunity data."""
        opportunity_data = {
            "upgrade_opportunities": [
                {"target": "Canada 1920 Dime", "current_grade": "VF-20", "upgrade_grade": "EF-40"}
            ]
        }
        report = self.engine.generate_strategy(
            collection_data={"items": [{"country": "Canada", "year": "1920", "denomination": "Dime"}]},
            opportunity_data=opportunity_data
        )
        self.assertIsInstance(report, AcquisitionStrategyReport)
        # Should include upgrade priorities
        upgrade_priorities = [p for p in report.immediate_priorities if p.category == PriorityCategory.UPGRADE]
        self.assertTrue(len(upgrade_priorities) > 0)

    def test_with_market_data(self):
        """Test strategy generation with market data."""
        market_data = {
            "observed_prices": [
                {"item": "Canada 1920 Dime", "price": 25.0}
            ]
        }
        report = self.engine.generate_strategy(
            collection_data={"items": [{"country": "Canada", "year": "1920", "denomination": "Dime"}]},
            market_data=market_data
        )
        self.assertIsInstance(report, AcquisitionStrategyReport)


if __name__ == "__main__":
    unittest.main()
