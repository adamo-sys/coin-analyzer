"""
Unit tests for Collection Insights Engine
"""

import unittest
from datetime import datetime
from collection_insights import (
    InsightCategory,
    InsightPriority,
    InsightEvidence,
    CollectionInsight,
    CollectorHealthReport,
    CollectionInsightReport,
    InsightsDashboard,
    CollectionInsightsEngine
)


class TestInsightEvidence(unittest.TestCase):
    """Test InsightEvidence dataclass."""

    def test_evidence_creation(self):
        """Test creating evidence."""
        evidence = InsightEvidence(
            metric_name="test_metric",
            metric_value=42,
            description="Test description"
        )
        self.assertEqual(evidence.metric_name, "test_metric")
        self.assertEqual(evidence.metric_value, 42)
        self.assertEqual(evidence.description, "Test description")
        self.assertIsInstance(evidence.timestamp, datetime)


class TestCollectionInsight(unittest.TestCase):
    """Test CollectionInsight dataclass."""

    def test_insight_creation(self):
        """Test creating an insight."""
        evidence = InsightEvidence("test", 42, "Test")
        insight = CollectionInsight(
            id="test_insight",
            category=InsightCategory.COLLECTION,
            priority=InsightPriority.HIGH,
            title="Test Insight",
            description="Test description",
            explanation="Test explanation",
            evidence=[evidence],
            affected_modules=["Test Module"],
            confidence=0.9
        )
        self.assertEqual(insight.id, "test_insight")
        self.assertEqual(insight.category, InsightCategory.COLLECTION)
        self.assertEqual(insight.priority, InsightPriority.HIGH)
        self.assertEqual(insight.confidence, 0.9)
        self.assertTrue(insight.actionable)
        self.assertIsInstance(insight.timestamp, datetime)


class TestCollectorHealthReport(unittest.TestCase):
    """Test CollectorHealthReport dataclass."""

    def test_health_report_creation(self):
        """Test creating health report."""
        report = CollectorHealthReport(
            overall_score=0.85,
            metadata_completeness=0.9,
            photo_coverage=0.8,
            ocr_coverage=0.7,
            grading_completeness=0.85,
            collection_documentation=0.81,
            workflow_completion=0.9,
            improvement_suggestions=["Test suggestion"],
            strengths=["Test strength"],
            weaknesses=[]
        )
        self.assertEqual(report.overall_score, 0.85)
        self.assertEqual(len(report.improvement_suggestions), 1)
        self.assertEqual(len(report.strengths), 1)
        self.assertIsInstance(report.timestamp, datetime)


class TestCollectionInsightsEngine(unittest.TestCase):
    """Test CollectionInsightsEngine."""

    def setUp(self):
        """Set up test engine."""
        self.engine = CollectionInsightsEngine()

    def test_engine_initialization(self):
        """Test engine initialization."""
        self.assertIsNotNone(self.engine)
        self.assertEqual(len(self.engine.insights_history), 0)

    def test_generate_insights_empty_collection(self):
        """Test generating insights with empty collection."""
        report = self.engine.generate_insights(
            collection_data={"items": []},
            portfolio_data={},
            workflow_data={},
            watchlist_data={},
            market_data={}
        )
        self.assertIsNotNone(report)
        self.assertIsInstance(report, CollectionInsightReport)
        self.assertGreater(len(report.insights), 0)
        # Should have empty collection insight
        empty_insights = [i for i in report.insights if i.id == "collection_empty"]
        self.assertEqual(len(empty_insights), 1)

    def test_generate_insights_with_collection(self):
        """Test generating insights with collection data."""
        collection_data = {
            "items": [
                {"country": "Canada", "denomination": "Dollar", "year": 1967, "grade": "MS-65"},
                {"country": "USA", "denomination": "Quarter", "year": 1999, "grade": "MS-63"},
                {"country": "Canada", "denomination": "Dollar", "year": 1968, "grade": "MS-64"},
            ]
        }
        report = self.engine.generate_insights(
            collection_data=collection_data,
            portfolio_data={},
            workflow_data={},
            watchlist_data={},
            market_data={}
        )
        self.assertIsNotNone(report)
        self.assertGreater(len(report.insights), 0)
        self.assertGreater(len(report.collection_insights), 0)

    def test_generate_portfolio_insights(self):
        """Test portfolio insights generation."""
        portfolio_data = {
            "total_estimated_value": 1000.0,
            "total_acquisition_cost": 800.0,
            "silver_value": 200.0
        }
        report = self.engine.generate_insights(
            collection_data={"items": [{"country": "Canada", "denomination": "Dollar", "year": 1967}]},
            portfolio_data=portfolio_data,
            workflow_data={},
            watchlist_data={},
            market_data={}
        )
        self.assertGreater(len(report.portfolio_insights), 0)
        # Should have portfolio value insight
        value_insights = [i for i in report.portfolio_insights if i.id == "portfolio_value"]
        self.assertEqual(len(value_insights), 1)

    def test_generate_acquisition_insights(self):
        """Test acquisition insights generation."""
        watchlist_data = {
            "watchlists": [
                {"items": [{"target": "test"}]},
                {"items": [{"target": "test2"}]}
            ]
        }
        report = self.engine.generate_insights(
            collection_data={"items": [{"country": "Canada", "denomination": "Dollar", "year": 1967}]},
            portfolio_data={},
            workflow_data={},
            watchlist_data=watchlist_data,
            market_data={}
        )
        self.assertGreater(len(report.acquisition_insights), 0)

    def test_generate_workflow_insights(self):
        """Test workflow insights generation."""
        workflow_data = {
            "photos_captured": 10,
            "ocr_sessions": 5,
            "completed_workflows": 8,
            "workflow_sessions": 10
        }
        report = self.engine.generate_insights(
            collection_data={"items": [{"country": "Canada", "denomination": "Dollar", "year": 1967}]},
            portfolio_data={},
            workflow_data=workflow_data,
            watchlist_data={},
            market_data={}
        )
        self.assertGreater(len(report.workflow_insights), 0)

    def test_generate_health_report(self):
        """Test health report generation."""
        collection_data = {
            "items": [
                {"country": "Canada", "denomination": "Dollar", "year": 1967, "grade": "MS-65"},
                {"country": "USA", "denomination": "Quarter", "year": 1999, "grade": "MS-63"},
            ]
        }
        workflow_data = {
            "photos_captured": 10,
            "ocr_sessions": 5,
            "completed_workflows": 8,
            "workflow_sessions": 10
        }
        report = self.engine.generate_insights(
            collection_data=collection_data,
            portfolio_data={},
            workflow_data=workflow_data,
            watchlist_data={},
            market_data={}
        )
        self.assertIsNotNone(report.health_report)
        self.assertGreaterEqual(report.health_report.overall_score, 0.0)
        self.assertLessEqual(report.health_report.overall_score, 1.0)

    def test_prioritize_insights(self):
        """Test insight prioritization."""
        collection_data = {
            "items": [
                {"country": "Canada", "denomination": "Dollar", "year": 1967, "grade": "MS-65"},
            ]
        }
        report = self.engine.generate_insights(
            collection_data=collection_data,
            portfolio_data={},
            workflow_data={},
            watchlist_data={},
            market_data={}
        )
        self.assertIsNotNone(report.top_priorities)
        self.assertLessEqual(len(report.top_priorities), 10)

    def test_generate_dashboard(self):
        """Test dashboard generation."""
        collection_data = {
            "items": [
                {"country": "Canada", "denomination": "Dollar", "year": 1967, "grade": "MS-65"},
            ]
        }
        report = self.engine.generate_insights(
            collection_data=collection_data,
            portfolio_data={},
            workflow_data={},
            watchlist_data={},
            market_data={}
        )
        dashboard = self.engine.generate_dashboard(report)
        self.assertIsNotNone(dashboard)
        self.assertIsInstance(dashboard, InsightsDashboard)
        self.assertEqual(dashboard.report, report)
        self.assertGreaterEqual(dashboard.critical_count, 0)
        self.assertGreaterEqual(dashboard.high_count, 0)
        self.assertGreaterEqual(dashboard.medium_count, 0)
        self.assertGreaterEqual(dashboard.low_count, 0)
        self.assertGreaterEqual(dashboard.informational_count, 0)
        self.assertIsNotNone(dashboard.summary)

    def test_export_report_markdown(self):
        """Test exporting report as Markdown."""
        collection_data = {
            "items": [
                {"country": "Canada", "denomination": "Dollar", "year": 1967, "grade": "MS-65"},
            ]
        }
        report = self.engine.generate_insights(
            collection_data=collection_data,
            portfolio_data={},
            workflow_data={},
            watchlist_data={},
            market_data={}
        )
        markdown = self.engine.export_report_markdown(report)
        self.assertIsInstance(markdown, str)
        self.assertIn("# Collection Insights Report", markdown)
        self.assertIn("Collector Health Report", markdown)

    def test_export_report_csv(self):
        """Test exporting report as CSV."""
        collection_data = {
            "items": [
                {"country": "Canada", "denomination": "Dollar", "year": 1967, "grade": "MS-65"},
            ]
        }
        report = self.engine.generate_insights(
            collection_data=collection_data,
            portfolio_data={},
            workflow_data={},
            watchlist_data={},
            market_data={}
        )
        csv = self.engine.export_report_csv(report)
        self.assertIsInstance(csv, str)
        self.assertIn("ID,Title,Category,Priority,Confidence", csv)

    def test_export_health_markdown(self):
        """Test exporting health report as Markdown."""
        collection_data = {
            "items": [
                {"country": "Canada", "denomination": "Dollar", "year": 1967, "grade": "MS-65"},
            ]
        }
        report = self.engine.generate_insights(
            collection_data=collection_data,
            portfolio_data={},
            workflow_data={},
            watchlist_data={},
            market_data={}
        )
        markdown = self.engine.export_health_markdown(report.health_report)
        self.assertIsInstance(markdown, str)
        self.assertIn("# Collector Health Report", markdown)
        self.assertIn("Overall Score", markdown)

    def test_export_health_csv(self):
        """Test exporting health report as CSV."""
        collection_data = {
            "items": [
                {"country": "Canada", "denomination": "Dollar", "year": 1967, "grade": "MS-65"},
            ]
        }
        report = self.engine.generate_insights(
            collection_data=collection_data,
            portfolio_data={},
            workflow_data={},
            watchlist_data={},
            market_data={}
        )
        csv = self.engine.export_health_csv(report.health_report)
        self.assertIsInstance(csv, str)
        self.assertIn("Component,Score", csv)

    def test_insights_history(self):
        """Test that insights are stored in history."""
        collection_data = {
            "items": [
                {"country": "Canada", "denomination": "Dollar", "year": 1967, "grade": "MS-65"},
            ]
        }
        self.engine.generate_insights(
            collection_data=collection_data,
            portfolio_data={},
            workflow_data={},
            watchlist_data={},
            market_data={}
        )
        self.assertEqual(len(self.engine.insights_history), 1)

    def test_duplicate_concentration_insight(self):
        """Test duplicate concentration insight generation."""
        collection_data = {
            "items": [
                {"country": "Canada", "denomination": "Dollar", "year": 1967, "grade": "MS-65"},
                {"country": "Canada", "denomination": "Dollar", "year": 1968, "grade": "MS-64"},
                {"country": "Canada", "denomination": "Dollar", "year": 1969, "grade": "MS-63"},
                {"country": "USA", "denomination": "Quarter", "year": 1999, "grade": "MS-63"},
            ]
        }
        report = self.engine.generate_insights(
            collection_data=collection_data,
            portfolio_data={},
            workflow_data={},
            watchlist_data={},
            market_data={}
        )
        # Should trigger duplicate concentration insight (75% Dollar)
        duplicate_insights = [i for i in report.acquisition_insights if i.id == "duplicate_concentration"]
        self.assertEqual(len(duplicate_insights), 1)

    def test_low_grade_coverage_insight(self):
        """Test low grade coverage insight."""
        collection_data = {
            "items": [
                {"country": "Canada", "denomination": "Dollar", "year": 1967, "grade": "Ungraded"},
                {"country": "USA", "denomination": "Quarter", "year": 1999, "grade": "Ungraded"},
                {"country": "Canada", "denomination": "Dollar", "year": 1968, "grade": "MS-64"},
            ]
        }
        report = self.engine.generate_insights(
            collection_data=collection_data,
            portfolio_data={},
            workflow_data={},
            watchlist_data={},
            market_data={}
        )
        # Should trigger low grade coverage insight (33% graded)
        grade_insights = [i for i in report.collection_insights if i.id == "low_grade_coverage"]
        self.assertEqual(len(grade_insights), 1)


class TestInsightsDashboard(unittest.TestCase):
    """Test InsightsDashboard dataclass."""

    def test_dashboard_creation(self):
        """Test creating dashboard."""
        health_report = CollectorHealthReport(
            overall_score=0.85,
            metadata_completeness=0.9,
            photo_coverage=0.8,
            ocr_coverage=0.7,
            grading_completeness=0.85,
            collection_documentation=0.81,
            workflow_completion=0.9,
            improvement_suggestions=[],
            strengths=[],
            weaknesses=[]
        )
        report = CollectionInsightReport(
            insights=[],
            health_report=health_report,
            collection_insights=[],
            portfolio_insights=[],
            acquisition_insights=[],
            workflow_insights=[],
            top_priorities=[]
        )
        dashboard = InsightsDashboard(
            report=report,
            summary="Test summary",
            critical_count=0,
            high_count=1,
            medium_count=2,
            low_count=3,
            informational_count=4,
            category_breakdown={"collection": 5, "portfolio": 3}
        )
        self.assertEqual(dashboard.summary, "Test summary")
        self.assertEqual(dashboard.critical_count, 0)
        self.assertEqual(dashboard.high_count, 1)
        self.assertEqual(dashboard.medium_count, 2)
        self.assertEqual(dashboard.low_count, 3)
        self.assertEqual(dashboard.informational_count, 4)
        self.assertEqual(dashboard.category_breakdown["collection"], 5)
        self.assertIsInstance(dashboard.timestamp, datetime)


if __name__ == '__main__':
    unittest.main()
