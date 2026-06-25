"""
Unit tests for Platform Analytics Engine
"""

import unittest
from datetime import datetime
from platform_analytics import (
    PlatformAnalyticsEngine,
    AnalyticsMetric,
    AnalyticsTrend,
    ModuleMetrics,
    AnalyticsSnapshot,
    AnalyticsSummary,
    PlatformHealthScore,
    AnalyticsDashboard,
    MetricType
)


class TestAnalyticsMetric(unittest.TestCase):
    """Test AnalyticsMetric dataclass."""

    def test_metric_creation(self):
        """Test creating a metric."""
        metric = AnalyticsMetric(
            name="test_metric",
            value=42,
            metric_type=MetricType.COUNTER,
            description="A test metric"
        )
        self.assertEqual(metric.name, "test_metric")
        self.assertEqual(metric.value, 42)
        self.assertEqual(metric.metric_type, MetricType.COUNTER)
        self.assertEqual(metric.description, "A test metric")
        self.assertIsInstance(metric.timestamp, datetime)


class TestModuleMetrics(unittest.TestCase):
    """Test ModuleMetrics dataclass."""

    def test_module_metrics_creation(self):
        """Test creating module metrics."""
        metrics = ModuleMetrics(module_name="Test Module")
        self.assertEqual(metrics.module_name, "Test Module")
        self.assertEqual(len(metrics.metrics), 0)
        self.assertEqual(metrics.health_score, 0.0)
        self.assertEqual(metrics.activity_level, "unknown")

    def test_module_metrics_with_data(self):
        """Test module metrics with data."""
        metrics = ModuleMetrics(module_name="Test Module")
        metrics.metrics.append(AnalyticsMetric(
            name="test",
            value=100,
            metric_type=MetricType.COUNTER,
            description="Test"
        ))
        metrics.health_score = 85.0
        metrics.activity_level = "active"
        
        self.assertEqual(len(metrics.metrics), 1)
        self.assertEqual(metrics.health_score, 85.0)
        self.assertEqual(metrics.activity_level, "active")


class TestPlatformAnalyticsEngine(unittest.TestCase):
    """Test PlatformAnalyticsEngine."""

    def setUp(self):
        """Set up test engine."""
        self.engine = PlatformAnalyticsEngine()

    def test_engine_initialization(self):
        """Test engine initialization."""
        self.assertIsNotNone(self.engine)
        self.assertEqual(len(self.engine.snapshots), 0)
        self.assertIsNone(self.engine.current_snapshot)

    def test_generate_snapshot_empty(self):
        """Test generating snapshot with no data."""
        snapshot = self.engine.generate_snapshot()
        
        self.assertIsNotNone(snapshot)
        self.assertIsInstance(snapshot, AnalyticsSnapshot)
        self.assertEqual(snapshot.overall_health_score, 0.0)
        self.assertIsNotNone(snapshot.collection_metrics)
        self.assertIsNotNone(snapshot.portfolio_metrics)

    def test_generate_snapshot_with_collection_data(self):
        """Test generating snapshot with collection data."""
        collection_data = {
            "items": [
                {"country": "Canada", "denomination": "Cent", "year": "1900", "grade": "VF"},
                {"country": "Canada", "denomination": "Cent", "year": "1901", "grade": "XF"},
                {"country": "Canada", "denomination": "Nickel", "year": "1920", "grade": "Ungraded"}
            ]
        }
        
        snapshot = self.engine.generate_snapshot(collection_data=collection_data)
        
        self.assertIsNotNone(snapshot.collection_metrics)
        self.assertEqual(snapshot.collection_metrics.activity_level, "active")
        
        # Check for total_items metric
        total_items = next((m.value for m in snapshot.collection_metrics.metrics if m.name == "total_items"), None)
        self.assertEqual(total_items, 3)

    def test_generate_snapshot_with_portfolio_data(self):
        """Test generating snapshot with portfolio data."""
        portfolio_data = {
            "total_estimated_value": 1000.0,
            "total_acquisition_cost": 800.0,
            "silver_value": 500.0
        }
        
        snapshot = self.engine.generate_snapshot(portfolio_data=portfolio_data)
        
        self.assertIsNotNone(snapshot.portfolio_metrics)
        self.assertEqual(snapshot.portfolio_metrics.activity_level, "active")
        self.assertEqual(snapshot.portfolio_metrics.health_score, 100.0)

    def test_generate_snapshot_with_workflow_data(self):
        """Test generating snapshot with workflow data."""
        workflow_data = {
            "photos_captured": 10,
            "ocr_sessions": 5,
            "total_ocr_attempts": 5,
            "successful_identifications": 4,
            "entry_attempts": 3,
            "completed_entries": 2,
            "workflow_sessions": 2,
            "completed_workflows": 1
        }
        
        snapshot = self.engine.generate_snapshot(workflow_data=workflow_data)
        
        self.assertIsNotNone(snapshot.workflow_metrics)
        self.assertEqual(snapshot.workflow_metrics.activity_level, "active")

    def test_generate_summary(self):
        """Test generating analytics summary."""
        collection_data = {"items": [{"country": "Canada", "year": "1900"}]}
        snapshot = self.engine.generate_snapshot(collection_data=collection_data)
        
        summary = self.engine.generate_summary(snapshot)
        
        self.assertIsNotNone(summary)
        self.assertIsInstance(summary, AnalyticsSummary)
        self.assertGreater(summary.total_modules, 0)
        self.assertGreaterEqual(summary.overall_health_score, 0)

    def test_calculate_health_score(self):
        """Test calculating health score."""
        collection_data = {"items": [{"country": "Canada", "year": "1900", "grade": "VF"}]}
        sync_data = {"backup_archives_created": 1, "last_backup_hours_ago": 24, "sync_simulations_run": 0, "backup_ready": True}
        
        snapshot = self.engine.generate_snapshot(collection_data=collection_data, sync_data=sync_data)
        health_score = self.engine.calculate_health_score(snapshot)
        
        self.assertIsNotNone(health_score)
        self.assertIsInstance(health_score, PlatformHealthScore)
        self.assertGreaterEqual(health_score.score, 0)
        self.assertLessEqual(health_score.score, 100)
        self.assertIn(health_score.category, ["excellent", "good", "fair", "poor"])

    def test_generate_dashboard(self):
        """Test generating complete dashboard."""
        collection_data = {"items": [{"country": "Canada", "year": "1900"}]}
        snapshot = self.engine.generate_snapshot(collection_data=collection_data)
        
        dashboard = self.engine.generate_dashboard(snapshot)
        
        self.assertIsNotNone(dashboard)
        self.assertIsInstance(dashboard, AnalyticsDashboard)
        self.assertEqual(dashboard.snapshot, snapshot)
        self.assertIsNotNone(dashboard.summary)
        self.assertIsNotNone(dashboard.health_score)
        self.assertIsInstance(dashboard.trends, list)

    def test_export_snapshot_markdown(self):
        """Test exporting snapshot as Markdown."""
        collection_data = {"items": [{"country": "Canada", "year": "1900"}]}
        snapshot = self.engine.generate_snapshot(collection_data=collection_data)
        
        markdown = self.engine.export_snapshot_markdown(snapshot)
        
        self.assertIsInstance(markdown, str)
        self.assertIn("# Platform Analytics Snapshot", markdown)
        self.assertIn("Collection Intelligence", markdown)

    def test_export_snapshot_csv(self):
        """Test exporting snapshot as CSV."""
        collection_data = {"items": [{"country": "Canada", "year": "1900"}]}
        snapshot = self.engine.generate_snapshot(collection_data=collection_data)
        
        csv = self.engine.export_snapshot_csv(snapshot)
        
        self.assertIsInstance(csv, str)
        self.assertIn("Module,Metric,Value,Type,Description,Timestamp", csv)

    def test_export_health_score_markdown(self):
        """Test exporting health score as Markdown."""
        collection_data = {"items": [{"country": "Canada", "year": "1900"}]}
        snapshot = self.engine.generate_snapshot(collection_data=collection_data)
        health_score = self.engine.calculate_health_score(snapshot)
        
        markdown = self.engine.export_health_score_markdown(health_score)
        
        self.assertIsInstance(markdown, str)
        self.assertIn("# Platform Health Score", markdown)
        self.assertIn("Overall Score", markdown)

    def test_export_health_score_csv(self):
        """Test exporting health score as CSV."""
        collection_data = {"items": [{"country": "Canada", "year": "1900"}]}
        snapshot = self.engine.generate_snapshot(collection_data=collection_data)
        health_score = self.engine.calculate_health_score(snapshot)
        
        csv = self.engine.export_health_score_csv(health_score)
        
        self.assertIsInstance(csv, str)
        self.assertIn("Component,Score", csv)

    def test_trend_generation(self):
        """Test trend generation with multiple snapshots."""
        collection_data = {"items": [{"country": "Canada", "year": "1900"}]}
        
        # Generate first snapshot
        snapshot1 = self.engine.generate_snapshot(collection_data=collection_data)
        
        # Add more items and generate second snapshot
        collection_data["items"].append({"country": "Canada", "year": "1901"})
        snapshot2 = self.engine.generate_snapshot(collection_data=collection_data)
        
        dashboard = self.engine.generate_dashboard(snapshot2)
        
        # Should have trends now
        self.assertGreater(len(dashboard.trends), 0)

    def test_all_module_metrics(self):
        """Test metrics for all modules."""
        collection_data = {"items": [{"country": "Canada", "year": "1900", "grade": "VF"}]}
        portfolio_data = {"total_estimated_value": 1000.0, "total_acquisition_cost": 800.0, "silver_value": 500.0}
        workflow_data = {"photos_captured": 100, "ocr_sessions": 50, "total_ocr_attempts": 50, 
                       "successful_identifications": 45, "entry_attempts": 30, 
                       "completed_entries": 25, "workflow_sessions": 20, "completed_workflows": 15}
        deal_hunter_data = {"total_listings_processed": 500, "buy_recommendations": 50, 
                          "pass_recommendations": 400, "risk_flags": 25}
        opportunity_data = {"total_opportunities": 100, "high_priority_opportunities": 20}
        market_data = {"total_market_records": 200, "comparable_sales": 50}
        watchlist_data = {"total_watchlists": 5, "total_watchlist_items": 50, "alerts_generated": 25}
        cloud_data = {"snapshots_created": 10, "sync_plans_generated": 5}
        sync_data = {"backup_archives_created": 5, "last_backup_hours_ago": 12, 
                   "sync_simulations_run": 3, "backup_ready": True}
        workspace_data = {"registered_devices": 3, "workspace_snapshots": 10}
        device_data = {"linked_devices": 2, "unresolved_conflicts": 0}
        
        snapshot = self.engine.generate_snapshot(
            collection_data=collection_data,
            portfolio_data=portfolio_data,
            workflow_data=workflow_data,
            deal_hunter_data=deal_hunter_data,
            opportunity_data=opportunity_data,
            market_data=market_data,
            watchlist_data=watchlist_data,
            cloud_data=cloud_data,
            sync_data=sync_data,
            workspace_data=workspace_data,
            device_data=device_data
        )
        
        # All modules should be active
        self.assertEqual(snapshot.collection_metrics.activity_level, "active")
        self.assertEqual(snapshot.portfolio_metrics.activity_level, "active")
        self.assertEqual(snapshot.workflow_metrics.activity_level, "active")
        self.assertEqual(snapshot.deal_hunter_metrics.activity_level, "active")
        self.assertEqual(snapshot.opportunity_metrics.activity_level, "active")
        self.assertEqual(snapshot.market_metrics.activity_level, "active")
        self.assertEqual(snapshot.watchlist_metrics.activity_level, "active")
        self.assertEqual(snapshot.cloud_metrics.activity_level, "active")
        self.assertEqual(snapshot.sync_metrics.activity_level, "active")
        self.assertEqual(snapshot.workspace_metrics.activity_level, "active")
        self.assertEqual(snapshot.device_metrics.activity_level, "active")

    def test_overall_health_calculation(self):
        """Test overall health score calculation."""
        # Create a snapshot with all healthy modules
        collection_data = {"items": [{"country": "Canada", "year": "1900", "grade": "VF"}]}
        sync_data = {"backup_archives_created": 1, "last_backup_hours_ago": 1, "sync_simulations_run": 0, "backup_ready": True}
        
        snapshot = self.engine.generate_snapshot(collection_data=collection_data, sync_data=sync_data)
        
        # Overall health should be reasonable
        self.assertGreater(snapshot.overall_health_score, 0)
        self.assertLessEqual(snapshot.overall_health_score, 100)


if __name__ == '__main__':
    unittest.main()
