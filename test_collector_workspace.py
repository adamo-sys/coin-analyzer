"""Tests for CollectorWorkspace — v8.3 Phase 1 core aggregation engine.

Strategy: Unit tests with mocks for engine isolation, plus integration tests
with real engines using test collection fixtures.
"""

import unittest
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from collector_workspace import (
    CollectorWorkspace,
    DashboardReport,
    InboxReport,
    CollectionSummaryReport,
    WorkspaceReport,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_items(count: int = 3) -> List[MagicMock]:
    """Create mock collection items with realistic fields."""
    items = []
    for i in range(count):
        item = MagicMock()
        item.country = f"Country{i % 2 + 1}"
        item.denomination = f"Denom{i % 3 + 1}"
        item.year = 1900 + i
        item.quantity = 1
        item.grade = "XF"
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

class TestCollectorWorkspaceUnit(unittest.TestCase):
    """Unit tests with mocked engines."""

    def test_init_does_not_create_engines(self) -> None:
        """__init__ should not instantiate any engines."""
        ws = CollectorWorkspace([])
        self.assertEqual(ws._engines, {})
        self.assertEqual(ws._cache, {})

    def test_refresh_clears_cache(self) -> None:
        """refresh() should clear all cached reports."""
        ws = CollectorWorkspace(_make_mock_items(1))
        # Warm the cache by mocking get_dashboard
        with patch.object(ws, "get_dashboard", return_value=DashboardReport()):
            ws.get_dashboard()
        # Manually inject a cache entry to test refresh directly
        ws._cache["dashboard"] = DashboardReport()
        ws._cache["inbox"] = InboxReport()
        ws.refresh()
        self.assertEqual(ws._cache, {})

    def test_refresh_keeps_engines(self) -> None:
        """refresh() should clear cache but keep engines."""
        ws = CollectorWorkspace([])
        ws._engines["dummy"] = MagicMock()
        ws.refresh()
        self.assertIn("dummy", ws._engines)
        self.assertEqual(ws._cache, {})

    def test_get_dashboard_aggregates_home_dashboard(self) -> None:
        """get_dashboard should call collector_home_dashboard and populate report."""
        ws = CollectorWorkspace(_make_mock_items(1))

        mock_home_report = MagicMock()
        mock_home_report.health_score = 85
        mock_home_report.top_priority = "Review silver coins"
        mock_home_report.recent_activity = ["Added 3 items"]
        mock_home_report.daily_actions = []

        mock_home_data = MagicMock()
        mock_home_data.best_next_purchase = "1847 Large Cent"

        mock_health_report = MagicMock()
        mock_finding = MagicMock()
        mock_finding.area = "Collection JSON"
        mock_finding.survives_restart = True
        mock_health_report.persistence_findings = [mock_finding]

        mock_daily = MagicMock()
        mock_daily.recommended_tasks = ["Review photos", "Check market"]

        mock_quality = MagicMock()
        mock_quality.overall_quality_score = 78

        mock_integrity = MagicMock()
        mock_score = MagicMock()
        mock_score.score = 92
        mock_integrity.integrity_score = mock_score

        with patch.object(
            ws, "_create_engine"
        ) as mock_create:
            mock_home_engine = MagicMock()
            mock_home_engine.generate_report.return_value = mock_home_report

            mock_os = {
                "home": MagicMock(),
                "health": MagicMock(),
            }
            mock_os["home"].generate_home.return_value = mock_home_data
            mock_os["health"].generate_report.return_value = mock_health_report

            mock_workflow = MagicMock()
            mock_workflow.daily_summary.return_value = mock_daily

            mock_quality_engine = MagicMock()
            mock_quality_engine.generate_report.return_value = mock_quality

            mock_integrity_engine = MagicMock()
            mock_integrity_engine.run.return_value = mock_integrity

            def side_effect(name: str) -> Any:
                mapping: Dict[str, Any] = {
                    "collector_home_dashboard": mock_home_engine,
                    "collector_operating_system": mock_os,
                    "collector_workflows": mock_workflow,
                    "collection_quality": mock_quality_engine,
                    "collection_integrity": mock_integrity_engine,
                }
                return mapping[name]

            mock_create.side_effect = side_effect

            # Pre-populate engines to bypass _create_engine for the ones we want
            ws._engines["collector_home_dashboard"] = mock_home_engine
            ws._engines["collector_operating_system"] = mock_os
            ws._engines["collector_workflows"] = mock_workflow
            ws._engines["collection_quality"] = mock_quality_engine
            ws._engines["collection_integrity"] = mock_integrity_engine

            report = ws.get_dashboard()

        self.assertIsInstance(report, DashboardReport)
        self.assertEqual(report.health_score, 85)
        self.assertEqual(report.top_priority, "Review silver coins")
        self.assertEqual(report.recent_activity, ["Added 3 items"])
        self.assertEqual(report.best_next_purchase, "1847 Large Cent")
        self.assertEqual(report.data_safety_status, "Persisted")
        self.assertTrue(report.backup_ready)
        self.assertEqual(report.todays_tasks, ["Review photos", "Check market"])
        self.assertEqual(report.quality_score, 78)
        self.assertEqual(report.integrity_score, 92)
        self.assertEqual(report.engine_errors, [])
        self.assertIn("dashboard", ws._cache)

    def test_get_dashboard_survives_engine_failure(self) -> None:
        """One engine failure should not crash the dashboard; others should still populate."""
        ws = CollectorWorkspace(_make_mock_items(1))

        mock_home_engine = MagicMock()
        mock_home_engine.generate_report.side_effect = RuntimeError("Home engine failed")

        mock_os = {
            "home": MagicMock(),
            "health": MagicMock(),
        }
        mock_home_data = MagicMock()
        mock_home_data.best_next_purchase = "1847 Large Cent"
        mock_os["home"].generate_home.return_value = mock_home_data
        mock_health_report = MagicMock()
        mock_health_report.persistence_findings = []
        mock_os["health"].generate_report.return_value = mock_health_report

        mock_workflow = MagicMock()
        mock_workflow.daily_summary.return_value = MagicMock(recommended_tasks=[])

        mock_quality = MagicMock()
        mock_quality.overall_quality_score = 80
        mock_quality_engine = MagicMock()
        mock_quality_engine.generate_report.return_value = mock_quality

        mock_integrity = MagicMock()
        mock_score = MagicMock()
        mock_score.score = 90
        mock_integrity.integrity_score = mock_score
        mock_integrity_engine = MagicMock()
        mock_integrity_engine.run.return_value = mock_integrity

        ws._engines["collector_home_dashboard"] = mock_home_engine
        ws._engines["collector_operating_system"] = mock_os
        ws._engines["collector_workflows"] = mock_workflow
        ws._engines["collection_quality"] = mock_quality_engine
        ws._engines["collection_integrity"] = mock_integrity_engine

        report = ws.get_dashboard()

        self.assertIsInstance(report, DashboardReport)
        self.assertIsNone(report.health_score)  # Home engine failed
        self.assertEqual(report.quality_score, 80)
        self.assertEqual(report.integrity_score, 90)
        self.assertEqual(report.best_next_purchase, "1847 Large Cent")
        self.assertEqual(len(report.engine_errors), 1)
        self.assertIn("Home dashboard", report.engine_errors[0])

    def test_get_inbox_aggregates_review_queues(self) -> None:
        """get_inbox should aggregate collection assistant pending items."""
        ws = CollectorWorkspace(_make_mock_items(1))

        mock_candidate = MagicMock()
        mock_candidate.is_pending = True
        mock_candidate.display_label = "1847 Large Cent"
        mock_candidate.confidence = 0.85
        mock_candidate.id = "cand-001"

        mock_candidate2 = MagicMock()
        mock_candidate2.is_pending = False
        mock_candidate2.display_label = "1900 Small Cent"
        mock_candidate2.confidence = 0.60
        mock_candidate2.id = "cand-002"

        mock_queue = MagicMock()
        mock_queue.pending_count = 1
        mock_queue.candidates = [mock_candidate, mock_candidate2]

        mock_session = MagicMock()
        mock_session.queue = mock_queue

        mock_assistant = MagicMock()
        mock_assistant.start_session.return_value = mock_session

        ws._engines["collection_assistant"] = mock_assistant
        ws._engines["batch_processing"] = MagicMock()
        ws._engines["ai_grading"] = MagicMock()

        report = ws.get_inbox()

        self.assertIsInstance(report, InboxReport)
        self.assertEqual(report.collection_assistant_pending, 1)
        self.assertEqual(report.batch_processing_pending, 0)
        self.assertEqual(report.ai_grading_review, 0)
        self.assertEqual(report.total_pending, 1)
        self.assertEqual(len(report.items), 1)
        self.assertEqual(report.items[0]["label"], "1847 Large Cent")
        self.assertEqual(report.items[0]["confidence"], 0.85)
        self.assertEqual(report.items[0]["source"], "Collection Assistant")
        self.assertEqual(report.engine_errors, [])

    def test_get_inbox_empty_queue(self) -> None:
        """get_inbox should return zero counts when no pending items."""
        ws = CollectorWorkspace([])

        mock_queue = MagicMock()
        mock_queue.pending_count = 0
        mock_queue.candidates = []

        mock_session = MagicMock()
        mock_session.queue = mock_queue

        mock_assistant = MagicMock()
        mock_assistant.start_session.return_value = mock_session

        ws._engines["collection_assistant"] = mock_assistant
        ws._engines["batch_processing"] = MagicMock()
        ws._engines["ai_grading"] = MagicMock()

        report = ws.get_inbox()

        self.assertEqual(report.total_pending, 0)
        self.assertEqual(report.items, [])

    def test_get_collection_summary_aggregates_intelligence(self) -> None:
        """get_collection_summary should aggregate collection intelligence data."""
        ws = CollectorWorkspace(_make_mock_items(3))

        mock_country_data = {
            "Country1": {"count": 2, "denominations": ["Denom1", "Denom2"], "years": [1900, 1901]},
            "Country2": {"count": 1, "denominations": ["Denom3"], "years": [1902]},
        }

        mock_intel = MagicMock()
        mock_intel.analyze_by_country.return_value = mock_country_data

        mock_dashboard = MagicMock()
        mock_series = MagicMock()
        mock_series.to_dict.return_value = {
            "series": "Large Cents",
            "years_owned": "1900-1901",
            "missing_years": "1902",
            "completion_percentage": 66.7,
        }
        mock_dashboard.series_completion = [mock_series]
        mock_dashboard.grade_coverage = None

        mock_snapshot_mgr = MagicMock()
        mock_current = MagicMock()
        mock_current.collection_size = 3
        mock_snapshot_mgr.create_snapshot.return_value = mock_current
        mock_latest = MagicMock()
        mock_growth = MagicMock()
        mock_growth.growth_since_last_snapshot = 2
        mock_latest.growth_summary = mock_growth
        mock_snapshot_mgr.latest_report.return_value = mock_latest

        mock_quality = MagicMock()
        mock_quality.overall_quality_score = 82
        mock_quality_engine = MagicMock()
        mock_quality_engine.generate_report.return_value = mock_quality

        mock_integrity = MagicMock()
        mock_score = MagicMock()
        mock_score.score = 95
        mock_integrity.integrity_score = mock_score
        mock_integrity_engine = MagicMock()
        mock_integrity_engine.run.return_value = mock_integrity

        ws._engines["collection_intelligence"] = mock_intel
        ws._engines["collection_dashboard"] = MagicMock()
        ws._engines["collection_dashboard"].generate_dashboard.return_value = mock_dashboard
        ws._engines["collection_snapshot"] = mock_snapshot_mgr
        ws._engines["collection_quality"] = mock_quality_engine
        ws._engines["collection_integrity"] = mock_integrity_engine

        report = ws.get_collection_summary()

        self.assertIsInstance(report, CollectionSummaryReport)
        self.assertEqual(report.total_items, 3)
        self.assertEqual(report.total_countries, 2)
        self.assertEqual(report.total_denominations, 3)
        self.assertEqual(report.total_years, 3)
        self.assertEqual(report.recent_additions, 2)
        self.assertEqual(report.quality_score, 82)
        self.assertEqual(report.integrity_score, 95)
        self.assertEqual(len(report.series_completion), 1)
        self.assertEqual(report.series_completion[0]["series"], "Large Cents")
        self.assertEqual(report.engine_errors, [])

    def test_get_collection_summary_survives_failure(self) -> None:
        """One engine failure in collection summary should not crash the report."""
        ws = CollectorWorkspace([])

        mock_intel = MagicMock()
        mock_intel.analyze_by_country.side_effect = RuntimeError("Intel failed")

        mock_dashboard = MagicMock()
        mock_dashboard.series_completion = []
        mock_dashboard.grade_coverage = None

        mock_snapshot_mgr = MagicMock()
        mock_snapshot_mgr.create_snapshot.return_value = MagicMock()
        mock_snapshot_mgr.latest_report.return_value = MagicMock(growth_summary=MagicMock(growth_since_last_snapshot=0))

        mock_quality = MagicMock()
        mock_quality.overall_quality_score = 75
        mock_quality_engine = MagicMock()
        mock_quality_engine.generate_report.return_value = mock_quality

        mock_integrity = MagicMock()
        mock_score = MagicMock()
        mock_score.score = 88
        mock_integrity.integrity_score = mock_score
        mock_integrity_engine = MagicMock()
        mock_integrity_engine.run.return_value = mock_integrity

        ws._engines["collection_intelligence"] = mock_intel
        ws._engines["collection_dashboard"] = MagicMock()
        ws._engines["collection_dashboard"].generate_dashboard.return_value = mock_dashboard
        ws._engines["collection_snapshot"] = mock_snapshot_mgr
        ws._engines["collection_quality"] = mock_quality_engine
        ws._engines["collection_integrity"] = mock_integrity_engine

        report = ws.get_collection_summary()

        self.assertIsInstance(report, CollectionSummaryReport)
        self.assertEqual(report.total_items, 0)  # Intel failed, no fallback
        self.assertEqual(report.quality_score, 75)
        self.assertEqual(report.integrity_score, 88)
        self.assertEqual(len(report.engine_errors), 1)
        self.assertIn("Collection Intelligence", report.engine_errors[0])

    def test_caching_avoids_requery(self) -> None:
        """Second call to same getter should return cached report."""
        ws = CollectorWorkspace([])

        mock_home = MagicMock()
        mock_home.generate_report.return_value = MagicMock(
            health_score=80, top_priority=None, recent_activity=[], daily_actions=[]
        )
        mock_os = {
            "home": MagicMock(),
            "health": MagicMock(),
        }
        mock_os["home"].generate_home.return_value = MagicMock(best_next_purchase=None)
        mock_os["health"].generate_report.return_value = MagicMock(persistence_findings=[])
        mock_workflow = MagicMock()
        mock_workflow.daily_summary.return_value = MagicMock(recommended_tasks=[])
        mock_quality = MagicMock()
        mock_quality.generate_report.return_value = MagicMock(overall_quality_score=70)
        mock_integrity = MagicMock()
        mock_integrity.run.return_value = MagicMock(integrity_score=MagicMock(score=90))

        ws._engines["collector_home_dashboard"] = mock_home
        ws._engines["collector_operating_system"] = mock_os
        ws._engines["collector_workflows"] = mock_workflow
        ws._engines["collection_quality"] = mock_quality
        ws._engines["collection_integrity"] = mock_integrity

        report1 = ws.get_dashboard()
        report2 = ws.get_dashboard()

        self.assertIs(report1, report2)  # Same cached object
        mock_home.generate_report.assert_called_once()  # Only queried once

    def test_unknown_engine_raises(self) -> None:
        """Requesting an unknown engine name should raise ValueError."""
        ws = CollectorWorkspace([])
        with self.assertRaises(ValueError) as ctx:
            ws._get_engine("nonexistent_engine")
        self.assertIn("Unknown engine", str(ctx.exception))

    def test_zero_business_logic_methods(self) -> None:
        """Workspace should not contain methods that compute business logic."""
        ws = CollectorWorkspace([])
        # These should NOT exist on the workspace
        forbidden_methods = [
            "detect_duplicates",
            "find_upgrades",
            "grade_analysis",
            "score_quality",
            "run_integrity_audit",
            "analyze_want_list",
            "compute_health",
        ]
        for method in forbidden_methods:
            self.assertFalse(
                hasattr(ws, method),
                f"Workspace should not have business logic method: {method}",
            )

    def test_report_has_errors(self) -> None:
        """WorkspaceReport.has_errors() should reflect engine_errors."""
        report = WorkspaceReport()
        self.assertFalse(report.has_errors())
        report.engine_errors = ["Something failed"]
        self.assertTrue(report.has_errors())

    def test_get_dashboard_top_priority_from_daily_actions(self) -> None:
        """If home report lacks top_priority, derive from daily_actions."""
        ws = CollectorWorkspace([])

        mock_action = MagicMock()
        mock_action.title = "Check silver coins"
        mock_action.action = None

        mock_home_report = MagicMock()
        mock_home_report.health_score = None
        mock_home_report.top_priority = None
        mock_home_report.recent_activity = []
        mock_home_report.daily_actions = [mock_action]

        mock_home = MagicMock()
        mock_home.generate_report.return_value = mock_home_report

        mock_os = {
            "home": MagicMock(),
            "health": MagicMock(),
        }
        mock_os["home"].generate_home.return_value = MagicMock(best_next_purchase=None)
        mock_os["health"].generate_report.return_value = MagicMock(persistence_findings=[])
        mock_workflow = MagicMock()
        mock_workflow.daily_summary.return_value = MagicMock(recommended_tasks=[])
        mock_quality = MagicMock()
        mock_quality.generate_report.return_value = MagicMock(overall_quality_score=70)
        mock_integrity = MagicMock()
        mock_integrity.run.return_value = MagicMock(integrity_score=MagicMock(score=90))

        ws._engines["collector_home_dashboard"] = mock_home
        ws._engines["collector_operating_system"] = mock_os
        ws._engines["collector_workflows"] = mock_workflow
        ws._engines["collection_quality"] = mock_quality
        ws._engines["collection_integrity"] = mock_integrity

        report = ws.get_dashboard()
        self.assertEqual(report.top_priority, "Check silver coins")


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestCollectorWorkspaceIntegration(unittest.TestCase):
    """Integration tests with real engines and mock collection items."""

    def _make_real_items(self) -> List[Any]:
        """Create CoinItem instances that real engines can process."""
        from coin_collection import CoinItem
        from datetime import datetime

        now = datetime.now().isoformat()
        return [
            CoinItem(
                id="usa_1900", image_path="", country="USA", denomination="Cent",
                year="1900", grade="VF", notes="", date_added=now, quantity=1,
            ),
            CoinItem(
                id="usa_1901", image_path="", country="USA", denomination="Cent",
                year="1901", grade="XF", notes="", date_added=now, quantity=1,
            ),
            CoinItem(
                id="uk_1900", image_path="", country="UK", denomination="Penny",
                year="1900", grade="G", notes="", date_added=now, quantity=1,
            ),
            CoinItem(
                id="uk_1901", image_path="", country="UK", denomination="Penny",
                year="1901", grade="VF", notes="", date_added=now, quantity=1,
            ),
            CoinItem(
                id="can_1900", image_path="", country="Canada", denomination="Cent",
                year="1900", grade="AU", notes="", date_added=now, quantity=1,
            ),
        ]

    def test_dashboard_with_real_engines(self) -> None:
        """Use real engines to verify get_dashboard produces a valid report."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items)
        report = ws.get_dashboard()

        self.assertIsInstance(report, DashboardReport)
        # Quality and integrity should be populated by real engines
        self.assertIsNotNone(report.quality_score)
        self.assertIsNotNone(report.integrity_score)
        # Should not have errors for the engines that succeed
        error_names = [e.split(":")[0] for e in report.engine_errors]
        self.assertNotIn("Quality", error_names)
        self.assertNotIn("Integrity", error_names)

    def test_collection_summary_with_real_collection(self) -> None:
        """Use real collection items to verify summary counts."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items)
        report = ws.get_collection_summary()

        self.assertIsInstance(report, CollectionSummaryReport)
        self.assertEqual(report.total_items, 5)
        self.assertEqual(report.total_countries, 3)  # USA, UK, Canada
        self.assertEqual(report.total_denominations, 2)  # Cent, Penny (deduplicated across countries)
        self.assertEqual(report.total_years, 2)  # 1900, 1901
        self.assertIsNotNone(report.quality_score)
        self.assertIsNotNone(report.integrity_score)

    def test_inbox_with_real_assistant_engine(self) -> None:
        """Use real CollectionAssistantEngine to verify inbox report."""
        ws = CollectorWorkspace([])
        report = ws.get_inbox()

        self.assertIsInstance(report, InboxReport)
        # Real engine starts with empty queue
        self.assertEqual(report.collection_assistant_pending, 0)
        self.assertEqual(report.total_pending, 0)
        self.assertEqual(report.items, [])
        self.assertEqual(report.engine_errors, [])

    def test_refresh_requeries_engines(self) -> None:
        """After refresh(), get_dashboard should re-query engines."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items)
        report1 = ws.get_dashboard()
        ws.refresh()
        report2 = ws.get_dashboard()

        self.assertIsNot(report1, report2)
        self.assertEqual(report1.quality_score, report2.quality_score)
        self.assertEqual(report1.integrity_score, report2.integrity_score)

    def test_all_three_panels_with_real_engines(self) -> None:
        """All three panels should work together without error."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items)

        dashboard = ws.get_dashboard()
        inbox = ws.get_inbox()
        summary = ws.get_collection_summary()

        self.assertIsInstance(dashboard, DashboardReport)
        self.assertIsInstance(inbox, InboxReport)
        self.assertIsInstance(summary, CollectionSummaryReport)

        # Inbox should be independent of collection items
        self.assertEqual(inbox.total_pending, 0)

        # Summary should have real counts
        self.assertEqual(summary.total_items, 5)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
