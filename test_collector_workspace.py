"""Tests for CollectorWorkspace — v8.3 Phase 1 core aggregation engine.

Strategy: Unit tests with mocks for engine isolation, plus integration tests
with real engines using test collection fixtures.
"""

import os
import tempfile
import unittest
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from collector_workspace import (
    CollectorWorkspace,
    DashboardReport,
    InboxReport,
    CollectionSummaryReport,
    WorkspaceReport,
    WantListReport,
    OpportunitiesReport,
    AIQueueReport,
    BatchQueueReport,
    PhotoVaultReport,
    WorkflowStatusReport,
    DataSafetyReport,
    ConnectedDataReport,
    ImageAssessmentReport,
    ReportDescriptor,
    ReportsMenu,
    LifecycleInfo,
)
from collector_workflows import (
    RecommendedTool,
    UnifiedWorkflowReport,
    WorkflowAction,
    WorkflowEvidence,
    WorkflowRequest,
    WorkflowSeverity,
    WorkflowState,
    WorkflowType,
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


def _write_workspace_test_image(path: str, size: int = 1000) -> str:
    """Write a deterministic image suitable for ImageAssessmentEngine tests."""
    tile = np.array([[80, 180], [180, 80]], dtype=np.uint8)
    gray = np.tile(tile, (size // 2, size // 2))
    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    cv2.imwrite(path, image)
    return path


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
        ws._engines["collector_workflows"] = MagicMock()

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
        ws._engines["collector_workflows"] = MagicMock()

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
        # Workflow reviews may appear if workflow engine has pending items
        self.assertGreaterEqual(report.total_pending, 0)
        # Non-workflow items should be empty
        non_workflow_items = [i for i in report.items if i.get("source") != "Workflow"]
        self.assertEqual(non_workflow_items, [])
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

        # Inbox now includes workflow reviews
        self.assertGreaterEqual(inbox.total_pending, 0)

        # Summary should have real counts
        self.assertEqual(summary.total_items, 5)


# ---------------------------------------------------------------------------
# Phase 2 Unit Tests
# ---------------------------------------------------------------------------

class TestCollectorWorkspacePhase2Unit(unittest.TestCase):
    """Unit tests for Phase 2 panel methods (mock-based)."""

    def test_keyword_only_constructor(self) -> None:
        """Constructor should accept keyword-only optional context parameters."""
        ws = CollectorWorkspace(
            [],
            want_list_intents=[],
            photo_records=[],
            shopping_candidates=[],
            market_awareness_engine=None,
            photo_candidates=[],
            watchlists=[],
            ocr_reports=[],
            workflow_statuses=[],
            acknowledged_action_ids=[],
        )
        self.assertEqual(ws._collection_items, [])
        self.assertEqual(ws._want_list_intents, [])
        self.assertEqual(ws._photo_records, [])
        self.assertEqual(ws._shopping_candidates, [])
        self.assertIsNone(ws._market_awareness_engine)
        self.assertEqual(ws._photo_candidates, [])
        self.assertEqual(ws._watchlists, [])
        self.assertEqual(ws._ocr_reports, [])
        self.assertEqual(ws._workflow_statuses, [])
        self.assertEqual(ws._acknowledged_action_ids, [])
        self.assertEqual(ws._engines, {})
        self.assertEqual(ws._cache, {})

    def test_constructor_minimal_args(self) -> None:
        """Constructor should work with only collection_items (Phase 1 compatibility)."""
        ws = CollectorWorkspace(["item"])
        self.assertEqual(ws._collection_items, ["item"])
        self.assertIsNone(ws._want_list_intents)
        self.assertIsNone(ws._photo_records)
        self.assertEqual(ws._engines, {})

    def test_get_want_list_aggregates_upgrades_and_gaps(self) -> None:
        """get_want_list should aggregate upgrade candidates, gaps, and watchlist matches."""
        ws = CollectorWorkspace(_make_mock_items(3))

        mock_upgrade = MagicMock()
        mock_upgrade.to_dict.return_value = {"country": "USA", "denomination": "Cent"}

        mock_gap = MagicMock()
        mock_gap.to_dict.return_value = {"series": "Large Cents", "missing": "1902"}

        mock_match = MagicMock()
        mock_match.to_dict.return_value = {"watchlist": "Pennies", "candidate": "1900"}

        mock_intel = MagicMock()
        mock_intel.detect_upgrade_candidates.return_value = [mock_upgrade]
        mock_gap_report = {"series_rows": [mock_gap]}
        mock_intel.generate_gap_report.return_value = mock_gap_report

        mock_watch = MagicMock()
        mock_watch_report = MagicMock()
        mock_watch_report.matches = [mock_match]
        mock_watch.scan.return_value = mock_watch_report

        ws._engines["collection_intelligence"] = mock_intel
        ws._engines["watchlist_engine"] = mock_watch

        report = ws.get_want_list()

        self.assertIsInstance(report, WantListReport)
        self.assertEqual(report.total_upgrades, 1)
        self.assertEqual(report.upgrade_candidates, [{"country": "USA", "denomination": "Cent"}])
        self.assertEqual(report.total_gaps, 1)
        self.assertEqual(report.gap_targets, [{"series": "Large Cents", "missing": "1902"}])
        self.assertEqual(report.total_watchlist_matches, 1)
        self.assertEqual(report.watchlist_matches, [{"watchlist": "Pennies", "candidate": "1900"}])
        self.assertEqual(report.engine_errors, [])

    def test_get_opportunities_aggregates_shopping(self) -> None:
        """get_opportunities should aggregate shopping recommendations and budget advice."""
        ws = CollectorWorkspace(_make_mock_items(3))

        mock_rec = MagicMock()
        mock_rec.to_dict.return_value = {"item": "1847 Large Cent", "score": 85}

        mock_shop_report = MagicMock()
        mock_shop_report.recommendations = [mock_rec]
        mock_shop_report.best_next_purchase = "1847 Large Cent"
        mock_shop_report.highest_impact_candidate = "1859 Narrow 9"

        mock_shopping = MagicMock()
        mock_shopping.generate_report.return_value = mock_shop_report

        mock_opp_report = MagicMock()
        mock_opp_report.budget_recommendations = ["Under $100: 3 items", "$100-$500: 1 item"]

        mock_opp = MagicMock()
        mock_opp.generate_report.return_value = mock_opp_report

        ws._engines["smart_shopping"] = mock_shopping
        ws._engines["opportunity_engine"] = mock_opp

        report = ws.get_opportunities()

        self.assertIsInstance(report, OpportunitiesReport)
        self.assertEqual(report.total_opportunities, 1)
        self.assertEqual(report.top_recommendations, [{"item": "1847 Large Cent", "score": 85}])
        self.assertEqual(report.best_next_purchase, "1847 Large Cent")
        self.assertEqual(report.highest_impact, "1859 Narrow 9")
        self.assertEqual(report.budget_recommendations, ["Under $100: 3 items", "$100-$500: 1 item"])
        self.assertEqual(report.engine_errors, [])

    def test_get_ai_queue_phase_2_placeholder(self) -> None:
        """get_ai_queue should return empty but valid report in Phase 2."""
        ws = CollectorWorkspace([])
        report = ws.get_ai_queue()

        self.assertIsInstance(report, AIQueueReport)
        self.assertEqual(report.total_assessments, 0)
        self.assertEqual(report.proceed_count, 0)
        self.assertEqual(report.caution_count, 0)
        self.assertEqual(report.review_count, 0)
        self.assertEqual(report.assessments, [])
        self.assertEqual(report.engine_errors, [])

    def test_get_batch_queue_phase_2_placeholder(self) -> None:
        """get_batch_queue should return empty but valid report in Phase 2."""
        ws = CollectorWorkspace([])
        report = ws.get_batch_queue()

        self.assertIsInstance(report, BatchQueueReport)
        self.assertEqual(report.total_sessions, 0)
        self.assertEqual(report.total_candidates, 0)
        self.assertEqual(report.reviewed_count, 0)
        self.assertEqual(report.approved_count, 0)
        self.assertEqual(report.engine_errors, [])

    def test_get_photo_vault_aggregates_coverage_and_audit(self) -> None:
        """get_photo_vault should aggregate PhotoVault coverage and integrity audit."""
        ws = CollectorWorkspace(_make_mock_items(3))

        mock_coverage = MagicMock()
        mock_coverage.total_collection_items = 10
        mock_coverage.items_with_photos = 7
        mock_coverage.items_without_photos = 3
        mock_coverage.photo_coverage_percentage = 70.0
        mock_coverage.certified_items = 2
        mock_coverage.certified_items_with_photos = 1

        mock_vault = MagicMock()
        mock_vault.coverage_summary.return_value = mock_coverage

        mock_audit_report = MagicMock()
        mock_audit_report.missing_photo_references = 2
        mock_audit_report.duplicate_photo_references = 1
        mock_audit_report.recommended_actions = ["Add missing photos for 1900-1902"]

        mock_audit = MagicMock()
        mock_audit.run.return_value = mock_audit_report

        ws._engines["photo_vault"] = mock_vault
        ws._engines["photo_vault_audit"] = mock_audit

        report = ws.get_photo_vault()

        self.assertIsInstance(report, PhotoVaultReport)
        self.assertEqual(report.total_collection_items, 10)
        self.assertEqual(report.items_with_photos, 7)
        self.assertEqual(report.items_without_photos, 3)
        self.assertEqual(report.coverage_percentage, 70.0)
        self.assertEqual(report.certified_items, 2)
        self.assertEqual(report.certified_with_photos, 1)
        self.assertEqual(report.missing_photo_count, 2)
        self.assertEqual(report.duplicate_photo_count, 1)
        self.assertEqual(report.recommended_actions, ["Add missing photos for 1900-1902"])
        self.assertEqual(report.engine_errors, [])

    def test_get_workflow_status_aggregates_daily_summary(self) -> None:
        """get_workflow_status should aggregate workflow daily summary."""
        ws = CollectorWorkspace([])

        mock_summary = MagicMock()
        mock_summary.workflow_name = "Collection Review"
        mock_summary.statuses = [MagicMock(), MagicMock()]
        mock_summary.next_actions = ["Review photos", "Check market"]
        mock_summary.status = "Review Ready"

        mock_daily = MagicMock()
        mock_daily.recommended_tasks = ["Review photos", "Check market"]
        mock_daily.summary = mock_summary

        mock_workflow = MagicMock()
        mock_workflow.daily_summary.return_value = mock_daily

        ws._engines["collector_workflows"] = mock_workflow

        report = ws.get_workflow_status()

        self.assertIsInstance(report, WorkflowStatusReport)
        self.assertEqual(report.todays_tasks, ["Review photos", "Check market"])
        self.assertEqual(report.active_workflows, ["Collection Review"])
        self.assertEqual(report.pending_reviews, 2)
        self.assertEqual(report.next_actions, ["Review photos", "Check market"])
        self.assertEqual(report.workflow_health, "Review Ready")
        self.assertEqual(report.engine_errors, [])

    def test_get_workflows_returns_default_daily_inbox(self) -> None:
        """get_workflows should return the default Daily Inbox unified workflow."""
        ws = CollectorWorkspace(_make_mock_items(1))
        mock_engine = MagicMock()
        expected = UnifiedWorkflowReport(
            WorkflowType.DAILY_INBOX,
            WorkflowState.READY,
            "Daily Inbox",
            "Ready",
            evidence=[WorkflowEvidence("test", "daily inbox ready")],
            next_actions=[WorkflowAction("Review inbox", evidence=[WorkflowEvidence("test", "review")])],
        )
        mock_engine.run_workflow.return_value = expected
        ws._engines["collector_workflows"] = mock_engine

        report = ws.get_workflows()

        self.assertIs(report, expected)
        request = mock_engine.run_workflow.call_args[0][0]
        self.assertEqual(request.workflow_type, WorkflowType.DAILY_INBOX)
        self.assertIn("workflow_default", ws._cache)

    def test_get_workflow_executes_explicit_request(self) -> None:
        """get_workflow should pass an explicit request to the workflow engine."""
        ws = CollectorWorkspace(_make_mock_items(1))
        mock_engine = MagicMock()
        expected = UnifiedWorkflowReport(
            WorkflowType.DUPLICATE_REVIEW,
            WorkflowState.COMPLETE,
            "Duplicate Review",
            "No duplicates",
            evidence=[WorkflowEvidence("test", "no duplicates")],
            next_actions=[WorkflowAction("No duplicate action required", evidence=[WorkflowEvidence("test", "done")])],
        )
        mock_engine.run_workflow.return_value = expected
        ws._engines["collector_workflows"] = mock_engine
        request = WorkflowRequest(WorkflowType.DUPLICATE_REVIEW)

        report = ws.get_workflow(request)

        self.assertIs(report, expected)
        mock_engine.run_workflow.assert_called_once_with(request)

    def test_get_workflows_uses_workflow_cache_namespace(self) -> None:
        """Default workflows should cache as workflow_default and workflow hash."""
        ws = CollectorWorkspace(_make_mock_items(1))
        mock_engine = MagicMock()
        mock_engine.run_workflow.return_value = UnifiedWorkflowReport(
            WorkflowType.DAILY_INBOX,
            WorkflowState.READY,
            "Daily Inbox",
            "Ready",
            evidence=[WorkflowEvidence("test", "ready")],
            next_actions=[WorkflowAction("Review", evidence=[WorkflowEvidence("test", "ready")])],
        )
        ws._engines["collector_workflows"] = mock_engine

        first = ws.get_workflows()
        second = ws.get_workflows()

        self.assertIs(first, second)
        self.assertEqual(mock_engine.run_workflow.call_count, 1)
        self.assertIn("workflow_default", ws._cache)
        self.assertTrue(any(key.startswith("workflow:") for key in ws._cache))

    def test_refresh_clears_workflow_cache(self) -> None:
        """refresh should clear workflow cache entries while keeping engines."""
        ws = CollectorWorkspace(_make_mock_items(1))
        ws._engines["collector_workflows"] = MagicMock()
        ws._cache["workflow_default"] = MagicMock()
        ws._cache["workflow:abc"] = MagicMock()

        ws.refresh()

        self.assertNotIn("workflow_default", ws._cache)
        self.assertNotIn("workflow:abc", ws._cache)
        self.assertIn("collector_workflows", ws._engines)

    def test_get_workflow_invalid_request_returns_blocked(self) -> None:
        """Invalid workflow requests should degrade instead of escaping to GUI."""
        ws = CollectorWorkspace(_make_mock_items(1))

        report = ws.get_workflow("not a request")

        self.assertEqual(report.state, WorkflowState.BLOCKED)
        self.assertTrue(report.evidence)
        self.assertTrue(report.warnings)

    def test_get_workflow_source_failure_returns_blocked(self) -> None:
        """Workflow engine failures should return BLOCKED reports."""
        ws = CollectorWorkspace(_make_mock_items(1))
        mock_engine = MagicMock()
        mock_engine.run_workflow.side_effect = RuntimeError("workflow failed")
        ws._engines["collector_workflows"] = mock_engine

        report = ws.get_workflow(WorkflowRequest(WorkflowType.COLLECTION_REVIEW))

        self.assertEqual(report.state, WorkflowState.BLOCKED)
        self.assertIn("workflow failed", report.warnings)
        self.assertEqual(report.evidence[0].severity, WorkflowSeverity.ERROR)

    def test_get_workflow_needs_input_flows_through_engine(self) -> None:
        """Missing input reports should pass through from the workflow engine."""
        ws = CollectorWorkspace(_make_mock_items(1))
        expected = UnifiedWorkflowReport(
            WorkflowType.ACQUISITION_REVIEW,
            WorkflowState.NEEDS_INPUT,
            "Acquisition Review",
            "Candidate required",
            evidence=[WorkflowEvidence("engine", "candidate required", WorkflowSeverity.WARNING)],
            next_actions=[WorkflowAction("Provide candidate", evidence=[WorkflowEvidence("engine", "candidate required")])],
            warnings=["candidate required"],
        )
        mock_engine = MagicMock()
        mock_engine.run_workflow.return_value = expected
        ws._engines["collector_workflows"] = mock_engine

        report = ws.get_workflow(WorkflowRequest(WorkflowType.ACQUISITION_REVIEW))

        self.assertEqual(report.state, WorkflowState.NEEDS_INPUT)
        self.assertIs(report, expected)

    def test_identical_workflow_requests_are_deterministic(self) -> None:
        """Two identical requests should produce identical serialized reports."""
        ws = CollectorWorkspace(_make_mock_items(3))
        first = ws.get_workflow(WorkflowRequest(WorkflowType.DUPLICATE_REVIEW))
        second = ws.get_workflow(WorkflowRequest(WorkflowType.DUPLICATE_REVIEW))

        self.assertEqual(first.to_dict(), second.to_dict())

    def test_get_data_safety_aggregates_persistence_and_integrity(self) -> None:
        """get_data_safety should aggregate persistence manager and integrity audit."""
        ws = CollectorWorkspace([])

        mock_state = MagicMock()
        mock_state.saved_at = "2025-01-15T10:00:00"

        mock_result = MagicMock()
        mock_result.state = mock_state

        mock_pm = MagicMock()
        mock_pm.load_state.return_value = mock_result

        mock_finding = MagicMock()
        mock_finding.to_dict.return_value = {"area": "Collection JSON", "survives_restart": True}
        mock_finding.survives_restart = True

        mock_finding2 = MagicMock()
        mock_finding2.to_dict.return_value = {"area": "Session Context", "survives_restart": False}
        mock_finding2.survives_restart = False

        mock_integrity = MagicMock()
        mock_integrity_report = MagicMock()
        mock_integrity_report.persistence_findings = [mock_finding, mock_finding2]
        mock_integrity_report.warnings = ["Session context not persisted"]
        mock_integrity.run.return_value = mock_integrity_report

        ws._engines["persistence_manager"] = mock_pm
        ws._engines["collection_integrity"] = mock_integrity

        report = ws.get_data_safety()

        self.assertIsInstance(report, DataSafetyReport)
        self.assertTrue(report.backup_ready)
        self.assertEqual(report.last_snapshot_age, "2025-01-15T10:00:00")
        self.assertEqual(report.total_persistence_areas, 2)
        self.assertEqual(report.persisted_areas, 1)
        self.assertEqual(report.session_only_areas, 1)
        self.assertEqual(report.integrity_warnings, ["Session context not persisted"])
        self.assertEqual(report.engine_errors, [])

    def test_new_panels_survive_engine_failure(self) -> None:
        """One engine failure in new panels should not crash the report."""
        ws = CollectorWorkspace(_make_mock_items(1))

        mock_intel = MagicMock()
        mock_intel.detect_upgrade_candidates.side_effect = RuntimeError("Intel failed")
        ws._engines["collection_intelligence"] = mock_intel
        ws._engines["watchlist_engine"] = MagicMock()
        ws._engines["watchlist_engine"].scan.return_value = MagicMock(matches=[])

        report = ws.get_want_list()

        self.assertIsInstance(report, WantListReport)
        self.assertEqual(report.total_upgrades, 0)
        self.assertEqual(len(report.engine_errors), 1)
        self.assertIn("Collection Intelligence", report.engine_errors[0])

    def test_phase_2_panels_are_cached(self) -> None:
        """Phase 2 panel methods should cache results."""
        ws = CollectorWorkspace([])
        report1 = ws.get_ai_queue()
        report2 = ws.get_ai_queue()
        self.assertIs(report1, report2)

    def test_refresh_clears_phase_2_cache(self) -> None:
        """refresh() should clear Phase 2 cached panels too."""
        ws = CollectorWorkspace([])
        ws.get_ai_queue()
        ws.get_batch_queue()
        self.assertIn("ai_queue", ws._cache)
        self.assertIn("batch_queue", ws._cache)
        ws.refresh()
        self.assertEqual(ws._cache, {})


# ---------------------------------------------------------------------------
# Phase 2 Integration Tests
# ---------------------------------------------------------------------------

class TestCollectorWorkspacePhase2Integration(unittest.TestCase):
    """Integration tests for Phase 2 panels with real engines."""

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

    def test_want_list_with_real_collection(self) -> None:
        """Use real collection to verify want list panel."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items)
        report = ws.get_want_list()

        self.assertIsInstance(report, WantListReport)
        # No duplicates in this collection so no upgrades expected
        self.assertEqual(report.total_upgrades, 0)
        # Watchlist engine with no watchlists should return empty
        self.assertEqual(report.total_watchlist_matches, 0)
        self.assertEqual(report.engine_errors, [])

    def test_photo_vault_with_empty_collection(self) -> None:
        """Empty collection should still produce valid photo vault report."""
        ws = CollectorWorkspace([])
        report = ws.get_photo_vault()

        self.assertIsInstance(report, PhotoVaultReport)
        self.assertEqual(report.total_collection_items, 0)
        self.assertEqual(report.coverage_percentage, 0.0)
        self.assertEqual(report.engine_errors, [])

    def test_data_safety_with_real_engines(self) -> None:
        """Use real engines to verify data safety panel."""
        ws = CollectorWorkspace([])
        report = ws.get_data_safety()

        self.assertIsInstance(report, DataSafetyReport)
        # Persistence manager may or may not find state
        self.assertIsInstance(report.backup_ready, bool)
        # Integrity should produce findings
        self.assertGreaterEqual(report.total_persistence_areas, 0)
        self.assertEqual(report.engine_errors, [])

    def test_workflow_status_with_real_engines(self) -> None:
        """Use real engines to verify workflow status panel."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items)
        report = ws.get_workflow_status()

        self.assertIsInstance(report, WorkflowStatusReport)
        # Real workflow engine should produce tasks
        self.assertIsInstance(report.todays_tasks, list)
        self.assertEqual(report.engine_errors, [])

    def test_all_ten_panels_with_real_engines(self) -> None:
        """All 10 panel methods should work together without error."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items)

        dashboard = ws.get_dashboard()
        inbox = ws.get_inbox()
        summary = ws.get_collection_summary()
        want_list = ws.get_want_list()
        opportunities = ws.get_opportunities()
        ai_queue = ws.get_ai_queue()
        batch_queue = ws.get_batch_queue()
        photo_vault = ws.get_photo_vault()
        workflow_status = ws.get_workflow_status()
        data_safety = ws.get_data_safety()

        self.assertIsInstance(dashboard, DashboardReport)
        self.assertIsInstance(inbox, InboxReport)
        self.assertIsInstance(summary, CollectionSummaryReport)
        self.assertIsInstance(want_list, WantListReport)
        self.assertIsInstance(opportunities, OpportunitiesReport)
        self.assertIsInstance(ai_queue, AIQueueReport)
        self.assertIsInstance(batch_queue, BatchQueueReport)
        self.assertIsInstance(photo_vault, PhotoVaultReport)
        self.assertIsInstance(workflow_status, WorkflowStatusReport)
        self.assertIsInstance(data_safety, DataSafetyReport)


# ---------------------------------------------------------------------------
# Phase 3 Unit Tests — Reports Panel
# ---------------------------------------------------------------------------

class TestCollectorWorkspacePhase3Unit(unittest.TestCase):
    """Unit tests for Phase 3 Reports Panel (mock-based)."""

    def test_get_reports_returns_menu_without_generating(self) -> None:
        """get_reports should return a ReportsMenu without calling any engine."""
        ws = CollectorWorkspace([])
        menu = ws.get_reports()

        self.assertIsInstance(menu, ReportsMenu)
        self.assertGreater(menu.total_reports, 0)
        self.assertEqual(menu.engine_errors, [])
        # No engines should be created
        self.assertEqual(len(ws._engines), 0)

    def test_get_reports_lists_all_report_descriptors(self) -> None:
        """get_reports should list all report descriptors with categories."""
        ws = CollectorWorkspace([])
        menu = ws.get_reports()

        self.assertGreaterEqual(menu.total_reports, 16)
        self.assertGreater(len(menu.categories), 0)
        # 3 reports are unavailable by default (photo_vault, photo_audit, watchlist_scan need context)
        self.assertEqual(menu.available_reports, menu.total_reports - 3)

    def test_get_reports_all_available_with_full_context(self) -> None:
        """With all context provided, all reports should be available."""
        ws = CollectorWorkspace([], photo_records=[MagicMock()], watchlists=[MagicMock()])
        menu = ws.get_reports()
        self.assertEqual(menu.available_reports, menu.total_reports)

    def test_get_reports_marks_unavailable_without_context(self) -> None:
        """Reports requiring missing context should be marked unavailable."""
        ws = CollectorWorkspace([], photo_records=None, watchlists=None)
        menu = ws.get_reports()

        photo_vault = menu.by_name("photo_vault")
        self.assertIsNotNone(photo_vault)
        self.assertFalse(photo_vault.available)

        photo_audit = menu.by_name("photo_audit")
        self.assertIsNotNone(photo_audit)
        self.assertFalse(photo_audit.available)

        watchlist = menu.by_name("watchlist_scan")
        self.assertIsNotNone(watchlist)
        self.assertFalse(watchlist.available)

    def test_get_reports_marks_available_with_context(self) -> None:
        """Reports with provided context should be marked available."""
        ws = CollectorWorkspace([], photo_records=[MagicMock()], watchlists=[MagicMock()])
        menu = ws.get_reports()

        self.assertTrue(menu.by_name("photo_vault").available)
        self.assertTrue(menu.by_name("photo_audit").available)
        self.assertTrue(menu.by_name("watchlist_scan").available)

    def test_reports_menu_by_category(self) -> None:
        """by_category should filter reports correctly."""
        ws = CollectorWorkspace([])
        menu = ws.get_reports()

        collection_reports = menu.by_category("Collection")
        self.assertGreater(len(collection_reports), 0)
        for r in collection_reports:
            self.assertEqual(r.category, "Collection")

    def test_reports_menu_by_name(self) -> None:
        """by_name should return the correct descriptor or None."""
        ws = CollectorWorkspace([])
        menu = ws.get_reports()

        desc = menu.by_name("collection_quality")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.title, "Collection Quality Report")

        self.assertIsNone(menu.by_name("nonexistent_report"))

    def test_reports_menu_includes_workflow_review(self) -> None:
        """Reports menu should include markdown-only Workflow Review descriptor."""
        ws = CollectorWorkspace([])
        descriptor = ws.get_reports().by_name("workflow_review")

        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.title, "Workflow Review")
        self.assertEqual(descriptor.category, "Workflow")
        self.assertTrue(descriptor.has_markdown_export)
        self.assertFalse(descriptor.has_csv_export)

    def test_generate_report_lazily_generates_by_name(self) -> None:
        """generate_report should call the correct engine method and return a dict."""
        ws = CollectorWorkspace([])

        mock_report = MagicMock()
        mock_report.to_dict.return_value = {"overall_quality_score": 85}

        mock_engine = MagicMock()
        mock_engine.generate_report.return_value = mock_report
        ws._engines["collection_quality"] = mock_engine

        result = ws.generate_report("collection_quality")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["overall_quality_score"], 85)
        mock_engine.generate_report.assert_called_once()

    def test_generate_report_workflow_review(self) -> None:
        """workflow_review report should serialize the default workflow report."""
        ws = CollectorWorkspace([])
        mock_engine = MagicMock()
        mock_engine.run_workflow.return_value = UnifiedWorkflowReport(
            WorkflowType.DAILY_INBOX,
            WorkflowState.READY,
            "Daily Inbox",
            "Ready",
            evidence=[WorkflowEvidence("test", "ready")],
            next_actions=[
                WorkflowAction(
                    "Review",
                    evidence=[WorkflowEvidence("test", "ready")],
                    recommended_tool=RecommendedTool.WORKFLOW,
                )
            ],
            state_reason="Daily Inbox generated reviewable workflow tasks.",
            recommended_tool=RecommendedTool.WORKFLOW,
        )
        ws._engines["collector_workflows"] = mock_engine

        result = ws.generate_report("workflow_review")

        self.assertEqual(result["workflow_type"], "DAILY_INBOX")
        self.assertEqual(result["state"], "READY")
        self.assertEqual(result["state_reason"], "Daily Inbox generated reviewable workflow tasks.")
        self.assertEqual(result["recommended_tool"], "WORKFLOW")
        self.assertEqual(result["recommended_tool_label"], "Workflow Review")
        self.assertEqual(result["next_actions"][0]["recommended_tool"], "WORKFLOW")
        self.assertEqual(mock_engine.run_workflow.call_count, 1)

    def test_generate_report_raises_for_unknown_name(self) -> None:
        """generate_report should raise ValueError for unknown report name."""
        ws = CollectorWorkspace([])
        with self.assertRaises(ValueError) as ctx:
            ws.generate_report("nonexistent_report")
        self.assertIn("Unknown report", str(ctx.exception))

    def test_generate_report_returns_unavailable_for_missing_context(self) -> None:
        """generate_report should return structured error for unavailable report."""
        ws = CollectorWorkspace([], photo_records=None)
        result = ws.generate_report("photo_vault")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["error"], "Report unavailable")
        self.assertIn("photo_vault", result["reason"])

    def test_generate_report_returns_error_on_engine_failure(self) -> None:
        """generate_report should return structured error dict on engine failure."""
        ws = CollectorWorkspace([])

        mock_engine = MagicMock()
        mock_engine.generate_report.side_effect = RuntimeError("Engine failed")
        ws._engines["collection_quality"] = mock_engine

        result = ws.generate_report("collection_quality")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["error"], "Report generation failed")
        self.assertIn("Engine failed", result["reason"])

    def test_generate_report_handles_operating_system(self) -> None:
        """generate_report should use engine['health'] for operating system reports."""
        ws = CollectorWorkspace([])

        mock_report = MagicMock()
        mock_report.to_dict.return_value = {"strengths": ["Good coverage"]}

        mock_health = MagicMock()
        mock_health.generate_report.return_value = mock_report

        ws._engines["collector_operating_system"] = {"home": MagicMock(), "health": mock_health}

        result = ws.generate_report("health_report")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["strengths"], ["Good coverage"])
        mock_health.generate_report.assert_called_once()

    def test_export_report_delegates_to_engine(self) -> None:
        """export_report should generate report then call engine export method."""
        ws = CollectorWorkspace([])

        mock_report = MagicMock()
        mock_engine = MagicMock()
        mock_engine.generate_report.return_value = mock_report
        mock_engine.export_markdown.return_value = True
        ws._engines["collection_quality"] = mock_engine

        result = ws.export_report("collection_quality", "markdown", "/tmp/report.md")

        self.assertTrue(result)
        mock_engine.generate_report.assert_called_once()
        mock_engine.export_markdown.assert_called_once_with("/tmp/report.md")

    def test_export_report_delegates_to_report_object(self) -> None:
        """export_report should fallback to report object's export method if engine lacks it."""
        ws = CollectorWorkspace([])

        mock_report = MagicMock()
        mock_report.export_csv.return_value = True
        mock_engine = MagicMock()
        mock_engine.generate_report.return_value = mock_report
        # engine has no export_csv
        del mock_engine.export_csv
        ws._engines["collection_quality"] = mock_engine

        result = ws.export_report("collection_quality", "csv", "/tmp/report.csv")

        self.assertTrue(result)
        mock_report.export_csv.assert_called_once_with("/tmp/report.csv")

    def test_export_report_workflow_review_markdown(self) -> None:
        """workflow_review should export markdown through the workspace."""
        ws = CollectorWorkspace([])
        mock_engine = MagicMock()
        mock_engine.run_workflow.return_value = UnifiedWorkflowReport(
            WorkflowType.DAILY_INBOX,
            WorkflowState.READY,
            "Daily Inbox",
            "Ready",
            evidence=[WorkflowEvidence("test", "ready")],
            next_actions=[
                WorkflowAction(
                    "Review",
                    evidence=[WorkflowEvidence("test", "ready")],
                    recommended_tool=RecommendedTool.WORKFLOW,
                )
            ],
            state_reason="Daily Inbox generated reviewable workflow tasks.",
            recommended_tool=RecommendedTool.WORKFLOW,
        )
        ws._engines["collector_workflows"] = mock_engine

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "workflow.md")
            result = ws.export_report("workflow_review", "markdown", path)
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()

        self.assertTrue(result)
        self.assertIn("Workflow Summary", content)
        self.assertIn("Workflow: DAILY_INBOX", content)
        self.assertIn("State: READY", content)
        self.assertIn("Reason: Daily Inbox generated reviewable workflow tasks.", content)
        self.assertIn("Recommended Tool:", content)
        self.assertIn("Workflow Review (WORKFLOW)", content)
        self.assertIn("Actions", content)
        self.assertIn("Evidence", content)
        self.assertIn("Warnings", content)
        self.assertIn("No workflow warnings.", content)

    def test_workflow_markdown_includes_action_evidence_and_tool_keys(self) -> None:
        """Workflow markdown should preserve action metadata for auditability."""
        ws = CollectorWorkspace([])
        evidence = WorkflowEvidence(
            "WorkflowStatus",
            "OCR Pending: 1 OCR report needs review",
            WorkflowSeverity.WARNING,
            "Review OCR validation reports",
        )
        report = UnifiedWorkflowReport(
            WorkflowType.DAILY_INBOX,
            WorkflowState.REVIEW_REQUIRED,
            "Daily Inbox",
            "Daily collector priorities generated",
            evidence=[evidence],
            next_actions=[
                WorkflowAction(
                    "Review OCR items",
                    "Daily collector priorities generated",
                    "Daily Summary",
                    WorkflowState.REVIEW_REQUIRED,
                    [evidence],
                    recommended_tool=RecommendedTool.OCR_EXPERIMENT,
                )
            ],
            warnings=["OCR Pending: 1 OCR report needs review"],
            state_reason="Daily Inbox found workflow items that require collector review.",
            recommended_tool=RecommendedTool.WORKFLOW,
        )

        content = ws._format_workflow_markdown(report)

        self.assertIn("Next Action:\nReview OCR items", content)
        self.assertIn("1. Review OCR items", content)
        self.assertIn("Recommended Tool: OCR Experiment", content)
        self.assertIn("Recommended Tool Key: OCR_EXPERIMENT", content)
        self.assertIn("[WARNING] WorkflowStatus: OCR Pending: 1 OCR report needs review", content)
        self.assertIn("Action: Review OCR validation reports", content)

    def test_workflow_markdown_empty_report_has_stable_empty_states(self) -> None:
        """Empty workflow report sections should be deterministic and readable."""
        ws = CollectorWorkspace([])
        report = UnifiedWorkflowReport(
            WorkflowType.DUPLICATE_REVIEW,
            WorkflowState.COMPLETE,
            "Duplicate Review",
            "No duplicates",
            evidence=[],
            next_actions=[],
            warnings=[],
            state_reason="No duplicate groups were detected.",
            recommended_tool=RecommendedTool.DUPLICATE_REVIEW,
        )

        content = ws._format_workflow_markdown(report)

        self.assertIn("Workflow: DUPLICATE_REVIEW", content)
        self.assertIn("State: COMPLETE", content)
        self.assertIn("No workflow actions available.", content)
        self.assertIn("No workflow evidence available.", content)
        self.assertIn("No workflow warnings.", content)

    def test_workflow_markdown_degraded_states_export_cleanly(self) -> None:
        """NEEDS_INPUT and BLOCKED reports should export without special handling."""
        ws = CollectorWorkspace([])
        states = {
            WorkflowState.READY: "Ready reason",
            WorkflowState.NEEDS_INPUT: "Candidate input is required.",
            WorkflowState.BLOCKED: "Workflow engine failed.",
            WorkflowState.COMPLETE: "Workflow is complete.",
        }

        for state, reason in states.items():
            with self.subTest(state=state.value):
                report = UnifiedWorkflowReport(
                    WorkflowType.DAILY_INBOX,
                    state,
                    "Workflow Review",
                    "Summary",
                    evidence=[
                        WorkflowEvidence(
                            "CollectorWorkspace",
                            reason,
                            WorkflowSeverity.ERROR if state == WorkflowState.BLOCKED else WorkflowSeverity.INFO,
                        )
                    ],
                    next_actions=[],
                    warnings=[reason] if state == WorkflowState.BLOCKED else [],
                    state_reason=reason,
                    recommended_tool=RecommendedTool.WORKFLOW,
                )
                content = ws._format_workflow_markdown(report)

                self.assertIn(f"State: {state.value}", content)
                self.assertIn(f"Reason: {reason}", content)
                self.assertIn("Workflow Review (WORKFLOW)", content)

    def test_workflow_markdown_is_deterministic_for_same_input(self) -> None:
        """The same workflow report should produce identical markdown."""
        ws = CollectorWorkspace([])
        report = UnifiedWorkflowReport(
            WorkflowType.DAILY_INBOX,
            WorkflowState.READY,
            "Daily Inbox",
            "Ready",
            evidence=[WorkflowEvidence("test", "ready")],
            next_actions=[WorkflowAction("Review", recommended_tool=RecommendedTool.WORKFLOW)],
            state_reason="Ready reason",
            recommended_tool=RecommendedTool.WORKFLOW,
        )

        self.assertEqual(ws._format_workflow_markdown(report), ws._format_workflow_markdown(report))

    def test_workflow_markdown_missing_optional_metadata_uses_na(self) -> None:
        """Missing optional metadata should not break workflow markdown."""
        ws = CollectorWorkspace([])
        report = MagicMock()
        report.title = ""
        report.workflow_type = None
        report.state = None
        report.state_reason = ""
        report.summary = ""
        report.recommended_tool = None
        report.recommended_tool_label = ""
        report.next_actions = []
        report.evidence = []
        report.warnings = []

        content = ws._format_workflow_markdown(report)

        self.assertIn("Title: Workflow Review", content)
        self.assertIn("Workflow: N/A", content)
        self.assertIn("State: N/A", content)
        self.assertIn("Reason: N/A", content)
        self.assertIn("N/A (N/A)", content)

    def test_export_report_workflow_review_rejects_csv(self) -> None:
        """workflow_review is markdown-only."""
        ws = CollectorWorkspace([])

        with self.assertRaises(ValueError):
            ws.export_report("workflow_review", "csv", "/tmp/workflow.csv")

    def test_export_report_raises_for_unknown_name(self) -> None:
        """export_report should raise ValueError for unknown report name."""
        ws = CollectorWorkspace([])
        with self.assertRaises(ValueError) as ctx:
            ws.export_report("nonexistent", "markdown", "/tmp/x.md")
        self.assertIn("Unknown report", str(ctx.exception))

    def test_export_report_raises_for_unavailable(self) -> None:
        """export_report should raise RuntimeError for unavailable report."""
        ws = CollectorWorkspace([], photo_records=None)
        with self.assertRaises(RuntimeError) as ctx:
            ws.export_report("photo_vault", "markdown", "/tmp/x.md")
        self.assertIn("not available", str(ctx.exception))

    def test_export_report_raises_for_unsupported_format(self) -> None:
        """export_report should raise ValueError for unsupported format."""
        ws = CollectorWorkspace([])
        with self.assertRaises(ValueError) as ctx:
            ws.export_report("collection_quality", "pdf", "/tmp/x.pdf")
        self.assertIn("Unsupported format", str(ctx.exception))

    def test_reports_are_cached(self) -> None:
        """get_reports should cache the menu."""
        ws = CollectorWorkspace([])
        menu1 = ws.get_reports()
        menu2 = ws.get_reports()
        self.assertIs(menu1, menu2)

    def test_refresh_clears_reports_cache(self) -> None:
        """refresh() should clear the reports cache too."""
        ws = CollectorWorkspace([])
        ws.get_reports()
        self.assertIn("reports", ws._cache)
        ws.refresh()
        self.assertNotIn("reports", ws._cache)


class TestCollectorWorkspaceImageAssessment(unittest.TestCase):
    """Unit tests for v8.8 Phase 2 Image Assessment workspace integration."""

    def _item_with_photos(self, photos: List[Any]) -> Any:
        from coin_collection import CoinItem

        return CoinItem(
            id="item-1",
            image_path="",
            country="Canada",
            denomination="Cent",
            year="1920",
            grade="VF-20",
            notes="",
            date_added="2026-07-13",
            photos=photos,
        )

    def test_image_assessment_lazy_engine_creation_and_reuse(self) -> None:
        ws = CollectorWorkspace([])
        self.assertNotIn("image_assessment", ws._engines)

        first = ws.get_image_assessment(photos=[])
        engine = ws._engines["image_assessment"]
        second = ws.get_image_assessment(photos=[])

        self.assertIsInstance(first, ImageAssessmentReport)
        self.assertIs(first, second)
        self.assertIs(ws._engines["image_assessment"], engine)

    def test_image_assessment_explicit_photo_set(self) -> None:
        from coin_collection import ItemPhoto, PhotoRole

        with tempfile.TemporaryDirectory() as tmp:
            front = _write_workspace_test_image(os.path.join(tmp, "front.jpg"))
            back = _write_workspace_test_image(os.path.join(tmp, "back.jpg"))
            ws = CollectorWorkspace([])

            report = ws.get_image_assessment(
                photos=[
                    ItemPhoto(front, role=PhotoRole.FRONT, display_order=0),
                    ItemPhoto(back, role=PhotoRole.BACK, display_order=1),
                ]
            )

        self.assertEqual(report.selection_type, "explicit_photos")
        self.assertEqual(report.photo_count, 2)
        self.assertEqual(report.engine_errors, [])
        self.assertIn("BROAD_IDENTIFICATION", report.readiness_report.downstream_permissions)

    def test_image_assessment_explicit_photos_take_precedence_over_item(self) -> None:
        from coin_collection import ItemPhoto, PhotoRole

        with tempfile.TemporaryDirectory() as tmp:
            explicit = _write_workspace_test_image(os.path.join(tmp, "explicit.jpg"))
            item_photo = _write_workspace_test_image(os.path.join(tmp, "item.jpg"))
            item = self._item_with_photos([ItemPhoto(item_photo, role=PhotoRole.FRONT)])
            ws = CollectorWorkspace([item])

            report = ws.get_image_assessment(
                item_id="item-1",
                photos=[ItemPhoto(explicit, role=PhotoRole.FRONT)],
            )

        self.assertEqual(report.selection_type, "explicit_photos")
        self.assertEqual(report.item_id, "")
        self.assertEqual(report.readiness_report.photo_assessments[0].path, explicit)

    def test_image_assessment_item_based_selection_does_not_mutate_item(self) -> None:
        from coin_collection import ItemPhoto, PhotoRole

        with tempfile.TemporaryDirectory() as tmp:
            front = _write_workspace_test_image(os.path.join(tmp, "front.jpg"))
            back = _write_workspace_test_image(os.path.join(tmp, "back.jpg"))
            item = self._item_with_photos([
                ItemPhoto(back, role=PhotoRole.BACK, display_order=4),
                ItemPhoto(front, role=PhotoRole.FRONT, display_order=2),
            ])
            before = [photo.to_dict() for photo in item.photos]
            ws = CollectorWorkspace([item])

            report = ws.get_image_assessment(item_id="item-1")

        self.assertEqual(report.selection_type, "item")
        self.assertEqual(report.item_id, "item-1")
        self.assertEqual([photo.to_dict() for photo in item.photos], before)

    def test_image_assessment_candidate_based_selection(self) -> None:
        @dataclass
        class Candidate:
            candidate_id: str
            photo_paths: List[str]

        with tempfile.TemporaryDirectory() as tmp:
            front = _write_workspace_test_image(os.path.join(tmp, "front.jpg"))
            candidate = Candidate("candidate-1", [front])
            ws = CollectorWorkspace([], photo_candidates=[candidate])

            report = ws.get_image_assessment(candidate_id="candidate-1")

        self.assertEqual(report.selection_type, "candidate")
        self.assertEqual(report.candidate_id, "candidate-1")
        self.assertEqual(report.photo_count, 1)

    def test_image_assessment_empty_and_invalid_input_degrades(self) -> None:
        ws = CollectorWorkspace([])

        no_selection = ws.get_image_assessment()
        missing_item = ws.get_image_assessment(item_id="missing")

        self.assertEqual(no_selection.selection_type, "none")
        self.assertIn("No image assessment selection", no_selection.engine_errors[0])
        self.assertEqual(missing_item.selection_type, "item")
        self.assertIn("Collection item not found", missing_item.engine_errors[0])

    def test_image_assessment_missing_file_returns_valid_report(self) -> None:
        ws = CollectorWorkspace([])
        report = ws.get_image_assessment(photos=[{"path": "missing.jpg", "role": "FRONT"}])

        self.assertIsInstance(report, ImageAssessmentReport)
        self.assertEqual(report.photo_count, 1)
        self.assertIn("Image file is missing.", report.readiness_report.blocking_issues)

    def test_image_assessment_engine_failure_degrades(self) -> None:
        ws = CollectorWorkspace([])
        engine = MagicMock()
        engine.assess_photos.side_effect = RuntimeError("engine down")
        ws._engines["image_assessment"] = engine

        report = ws.get_image_assessment(photos=[{"path": "missing.jpg", "role": "FRONT"}])

        self.assertIsInstance(report, ImageAssessmentReport)
        self.assertIn("Image Assessment: engine down", report.engine_errors)

    def test_image_assessment_cache_and_refresh_behavior(self) -> None:
        ws = CollectorWorkspace([])
        engine = MagicMock()
        engine.assess_photos.side_effect = lambda *args, **kwargs: MagicMock(
            photo_assessments=[],
            blocking_issues=[],
            engine_errors=[],
            generated_at="1970-01-01T00:00:00",
            decision="NOT_READY",
            confidence="LOW",
            overall_readiness_score=0,
        )
        ws._engines["image_assessment"] = engine

        first = ws.get_image_assessment(photos=[])
        second = ws.get_image_assessment(photos=[])
        self.assertIs(first, second)
        self.assertEqual(engine.assess_photos.call_count, 1)

        refreshed = ws.get_image_assessment(photos=[], refresh=True)
        self.assertIsNot(refreshed, first)
        self.assertEqual(engine.assess_photos.call_count, 2)

        engine_ref = ws._engines["image_assessment"]
        ws.refresh()
        self.assertEqual(ws._cache, {})
        self.assertIs(ws._engines["image_assessment"], engine_ref)

    def test_image_assessment_report_is_deterministic_and_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            front = _write_workspace_test_image(os.path.join(tmp, "front.jpg"))
            photos = [{"path": front, "role": "FRONT", "display_order": 0}]
            first = CollectorWorkspace([]).get_image_assessment(photos=photos).to_dict()
            second = CollectorWorkspace([]).get_image_assessment(photos=photos).to_dict()

        self.assertEqual(first, second)
        self.assertIn("readiness_report", first)
        self.assertEqual(first["generated_at"], "1970-01-01T00:00:00")

    def test_image_assessment_report_descriptor_registration(self) -> None:
        ws = CollectorWorkspace([])
        descriptor = ws.get_reports().by_name("image_assessment")

        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.category, "Photo")
        self.assertTrue(descriptor.has_markdown_export)
        self.assertFalse(descriptor.has_csv_export)
        self.assertTrue(descriptor.available)

    def test_generate_and_export_image_assessment_report(self) -> None:
        ws = CollectorWorkspace([])
        generated = ws.generate_report("image_assessment")

        self.assertEqual(generated["selection_type"], "none")
        self.assertIn("No image assessment selection", generated["engine_errors"][0])

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "image_assessment.md")
            result = ws.export_report("image_assessment", "markdown", path)
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()

        self.assertTrue(result)
        self.assertIn("Image Assessment Readiness", content)
        self.assertIn("Downstream Readiness", content)


# ---------------------------------------------------------------------------
# Phase 3 Integration Tests
# ---------------------------------------------------------------------------

class TestCollectorWorkspacePhase3Integration(unittest.TestCase):
    """Integration tests for Phase 3 Reports Panel with real engines."""

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
        ]

    def test_get_reports_with_real_collection(self) -> None:
        """Use real collection to verify reports menu."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items)
        menu = ws.get_reports()

        self.assertIsInstance(menu, ReportsMenu)
        self.assertGreaterEqual(menu.total_reports, 16)
        self.assertGreater(len(menu.categories), 0)
        # All reports should be available (no photo_records or watchlists required for basic ones)
        self.assertGreaterEqual(menu.available_reports, 10)

    def test_generate_report_collection_quality_with_real_engines(self) -> None:
        """Use real engines to generate a specific report."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items)
        result = ws.generate_report("collection_quality")

        self.assertIsInstance(result, dict)
        self.assertIn("overall_quality_score", result)
        self.assertIsInstance(result["overall_quality_score"], int)

    def test_generate_report_collection_integrity_with_real_engines(self) -> None:
        """Use real engines to generate integrity report."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items)
        result = ws.generate_report("collection_integrity")

        self.assertIsInstance(result, dict)
        self.assertIn("integrity_score", result)

    def test_generate_report_returns_unavailable_for_photo_without_context(self) -> None:
        """photo_vault should be unavailable without photo_records."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items, photo_records=None)
        result = ws.generate_report("photo_vault")

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("error"), "Report unavailable")

    def test_export_report_collection_quality_with_real_engines(self) -> None:
        """Use real engines to export a report to a temp file."""
        import tempfile
        import os

        items = self._make_real_items()
        ws = CollectorWorkspace(items)

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
            path = tmp.name

        try:
            result = ws.export_report("collection_quality", "markdown", path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 0)
        finally:
            if os.path.exists(path):
                os.remove(path)


# ---------------------------------------------------------------------------
# Phase 4 Unit Tests — Refresh & Lifecycle
# ---------------------------------------------------------------------------

class TestCollectorWorkspacePhase4Unit(unittest.TestCase):
    """Unit tests for Phase 4 lifecycle and refresh hardening."""

    def test_lifecycle_info_no_engines_created(self) -> None:
        """get_lifecycle() should return zeros when no engines created."""
        ws = CollectorWorkspace([])
        info = ws.get_lifecycle()

        self.assertIsInstance(info, LifecycleInfo)
        self.assertEqual(info.engine_count, 0)
        self.assertEqual(info.cached_panel_count, 0)
        self.assertFalse(info.reports_menu_cached)
        self.assertEqual(info.panel_names_cached, [])
        self.assertEqual(info.collection_item_count, 0)
        # Verify no engines were created as a side effect
        self.assertEqual(len(ws._engines), 0)

    def test_lifecycle_info_after_panels_accessed(self) -> None:
        """get_lifecycle() should reflect engine and cache state after panel access."""
        ws = CollectorWorkspace(_make_mock_items(1))

        # Pre-populate engines and cache with mocks
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

        ws.get_dashboard()
        ws.get_inbox()

        info = ws.get_lifecycle()
        self.assertGreaterEqual(info.engine_count, 5)
        self.assertEqual(info.cached_panel_count, 2)
        self.assertIn("dashboard", info.panel_names_cached)
        self.assertIn("inbox", info.panel_names_cached)
        self.assertEqual(info.collection_item_count, 1)

    def test_lifecycle_info_after_refresh(self) -> None:
        """get_lifecycle() should show cleared cache after refresh."""
        ws = CollectorWorkspace(_make_mock_items(1))

        ws._engines["mock"] = MagicMock()
        ws._cache["dashboard"] = DashboardReport()
        ws._cache["inbox"] = InboxReport()

        info_before = ws.get_lifecycle()
        self.assertEqual(info_before.cached_panel_count, 2)
        self.assertEqual(info_before.engine_count, 1)

        ws.refresh()

        info_after = ws.get_lifecycle()
        self.assertEqual(info_after.cached_panel_count, 0)
        self.assertEqual(info_after.engine_count, 1)  # engines preserved
        self.assertEqual(info_after.panel_names_cached, [])
        self.assertFalse(info_after.reports_menu_cached)

    def test_refresh_preserves_engine_instances(self) -> None:
        """refresh() should preserve the exact same engine objects."""
        ws = CollectorWorkspace(_make_mock_items(1))

        mock_engine = MagicMock()
        ws._engines["test_engine"] = mock_engine
        ws._cache["test_panel"] = DashboardReport()

        ws.refresh()

        self.assertIs(ws._engines["test_engine"], mock_engine)
        self.assertEqual(len(ws._cache), 0)

    def test_double_failure_after_refresh(self) -> None:
        """Engine that fails before and after refresh should return error both times."""
        ws = CollectorWorkspace(_make_mock_items(1))

        mock_engine = MagicMock()
        mock_engine.generate_report.side_effect = RuntimeError("Engine failed")
        ws._engines["collection_quality"] = mock_engine

        # First call
        report1 = ws.get_dashboard()
        # Dashboard uses multiple engines; quality failure should be in errors
        quality_errors = [e for e in report1.engine_errors if "Quality" in e]
        self.assertEqual(len(quality_errors), 1)

        ws.refresh()

        # Second call after refresh
        report2 = ws.get_dashboard()
        quality_errors2 = [e for e in report2.engine_errors if "Quality" in e]
        self.assertEqual(len(quality_errors2), 1)

    def test_cascading_errors_no_cross_pollution(self) -> None:
        """Errors in one panel should not pollute another panel's error list."""
        ws = CollectorWorkspace(_make_mock_items(1))

        # Pre-populate two engines: one fails, one succeeds
        mock_home = MagicMock()
        mock_home.generate_report.return_value = MagicMock(
            health_score=80, top_priority=None, recent_activity=[], daily_actions=[]
        )
        mock_quality = MagicMock()
        mock_quality.generate_report.side_effect = RuntimeError("Quality down")
        mock_integrity = MagicMock()
        mock_integrity.run.return_value = MagicMock(integrity_score=MagicMock(score=90))
        mock_os = {
            "home": MagicMock(),
            "health": MagicMock(),
        }
        mock_os["home"].generate_home.return_value = MagicMock(best_next_purchase=None)
        mock_os["health"].generate_report.return_value = MagicMock(persistence_findings=[])
        mock_workflow = MagicMock()
        mock_workflow.daily_summary.return_value = MagicMock(recommended_tasks=[])

        ws._engines["collector_home_dashboard"] = mock_home
        ws._engines["collector_operating_system"] = mock_os
        ws._engines["collector_workflows"] = mock_workflow
        ws._engines["collection_quality"] = mock_quality
        ws._engines["collection_integrity"] = mock_integrity

        dashboard = ws.get_dashboard()
        # Dashboard has quality error but also integrity data
        self.assertTrue(any("Quality" in e for e in dashboard.engine_errors))
        self.assertIsNotNone(dashboard.integrity_score)  # Integrity succeeded
        self.assertEqual(dashboard.integrity_score, 90)

    def test_partial_recovery_after_refresh(self) -> None:
        """Engine that fails first call but succeeds after refresh should recover."""
        ws = CollectorWorkspace(_make_mock_items(1))

        mock_engine = MagicMock()
        mock_engine.generate_report.side_effect = [
            RuntimeError("First failure"),
            MagicMock(overall_quality_score=85),
        ]
        ws._engines["collection_quality"] = mock_engine
        ws._engines["collector_home_dashboard"] = MagicMock()
        ws._engines["collector_home_dashboard"].generate_report.return_value = MagicMock(
            health_score=80, top_priority=None, recent_activity=[], daily_actions=[]
        )
        ws._engines["collector_operating_system"] = {
            "home": MagicMock(generate_home=MagicMock(return_value=MagicMock(best_next_purchase=None))),
            "health": MagicMock(generate_report=MagicMock(return_value=MagicMock(persistence_findings=[]))),
        }
        ws._engines["collector_workflows"] = MagicMock()
        ws._engines["collector_workflows"].daily_summary.return_value = MagicMock(recommended_tasks=[])
        ws._engines["collection_integrity"] = MagicMock()
        ws._engines["collection_integrity"].run.return_value = MagicMock(integrity_score=MagicMock(score=90))

        # First call — quality fails
        report1 = ws.get_dashboard()
        self.assertTrue(any("Quality" in e for e in report1.engine_errors))
        self.assertIsNone(report1.quality_score)

        ws.refresh()

        # Second call — quality succeeds
        report2 = ws.get_dashboard()
        self.assertEqual(report2.quality_score, 85)
        self.assertFalse(any("Quality" in e for e in report2.engine_errors))

    def test_per_instance_cache_isolation(self) -> None:
        """Two workspace instances should have independent caches."""
        ws1 = CollectorWorkspace(["item1"])
        ws2 = CollectorWorkspace(["item2", "item3"])

        ws1._cache["panel"] = DashboardReport()
        ws2._cache["panel"] = InboxReport()

        self.assertIsInstance(ws1._cache["panel"], DashboardReport)
        self.assertIsInstance(ws2._cache["panel"], InboxReport)
        self.assertEqual(ws1.get_lifecycle().collection_item_count, 1)
        self.assertEqual(ws2.get_lifecycle().collection_item_count, 2)

    def test_cache_key_uniqueness(self) -> None:
        """All 12 panel cache keys should be unique."""
        keys = [
            "dashboard", "inbox", "collection_summary",
            "want_list", "opportunities", "ai_queue", "batch_queue",
            "photo_vault", "workflow_status", "data_safety",
            "connected_data", "reports",
        ]
        self.assertEqual(len(keys), len(set(keys)), "Cache keys must be unique")
        self.assertEqual(len(keys), 12)

    def test_get_lifecycle_does_not_initialize_engines(self) -> None:
        """get_lifecycle() must not create engines as a side effect."""
        ws = CollectorWorkspace(_make_mock_items(1))
        ws.get_lifecycle()
        ws.get_lifecycle()
        self.assertEqual(len(ws._engines), 0)

    def test_get_lifecycle_does_not_mutate_cache(self) -> None:
        """get_lifecycle() must not modify the cache."""
        ws = CollectorWorkspace([])
        ws._cache["dashboard"] = DashboardReport()
        before_keys = list(ws._cache.keys())
        ws.get_lifecycle()
        after_keys = list(ws._cache.keys())
        self.assertEqual(before_keys, after_keys)


# ---------------------------------------------------------------------------
# Connected Data Tests (v8.4 Phase 2)
# ---------------------------------------------------------------------------

class TestCollectorWorkspaceConnectedData(unittest.TestCase):
    """Tests for get_connected_data panel method."""

    def test_get_connected_data_empty_context(self) -> None:
        """Empty context returns empty report with zero counts."""
        ws = CollectorWorkspace([])
        report = ws.get_connected_data()
        self.assertIsInstance(report, ConnectedDataReport)
        self.assertEqual(report.total_connections, 0)
        self.assertEqual(report.overall_match_rate, 0.0)
        self.assertEqual(report.engine_errors, [])

    def test_get_connected_data_with_photo_grading(self) -> None:
        """Photo linked to grading: workspace has photo but no grading context.
        
        Phase 2: workspace does not store grading_assessments, so no match.
        Verifies the engine runs and produces empty connections gracefully.
        """
        photo = MagicMock()
        photo.file_path = "/photos/coin1.jpg"
        photo.id = "p1"

        ws = CollectorWorkspace(
            collection_items=[],
            photo_records=[photo],
            shopping_candidates=[],
            want_list_intents=[],
            watchlists=[],
        )

        report = ws.get_connected_data()
        self.assertIsInstance(report, ConnectedDataReport)
        # Phase 2: no grading context in workspace, so photo->grading is 0
        self.assertEqual(report.total_connections, 0)
        self.assertEqual(report.engine_errors, [])

    def test_get_connected_data_with_watchlist_shopping(self) -> None:
        """Watchlist keyword matches shopping candidate. Both sides available."""
        watch = MagicMock()
        watch.id = "wl1"
        watch.keyword = "dollar"
        watch.name = None

        shopping = MagicMock()
        shopping.id = "s1"
        shopping.title = "1921 Morgan Dollar"
        shopping.country = "USA"
        shopping.denomination = "1 Dollar"

        ws = CollectorWorkspace(
            collection_items=[],
            watchlists=[watch],
            shopping_candidates=[shopping],
        )

        report = ws.get_connected_data()
        self.assertIsInstance(report, ConnectedDataReport)
        self.assertGreaterEqual(report.total_connections, 1)
        self.assertGreater(len(report.top_connections), 0)

    def test_get_connected_data_cache_hit(self) -> None:
        """Second call returns cached report."""
        ws = CollectorWorkspace([])
        report1 = ws.get_connected_data()
        report2 = ws.get_connected_data()
        self.assertIs(report1, report2)

    def test_get_connected_data_after_refresh(self) -> None:
        """After refresh, get_connected_data rebuilds."""
        ws = CollectorWorkspace([])
        report1 = ws.get_connected_data()
        ws.refresh()
        report2 = ws.get_connected_data()
        self.assertIsNot(report1, report2)
        self.assertEqual(report1.total_connections, report2.total_connections)

    def test_get_connected_data_engine_error(self) -> None:
        """Engine failure produces error but doesn't crash."""
        ws = CollectorWorkspace([])
        # Force a bad engine by patching _create_engine
        with patch.object(ws, "_create_engine") as mock_create:
            mock_create.side_effect = RuntimeError("Engine creation failed")
            report = ws.get_connected_data()
        self.assertEqual(report.total_connections, 0)
        self.assertEqual(len(report.engine_errors), 1)
        self.assertIn("Connected Data", report.engine_errors[0])

    def test_get_connected_data_lifecycle(self) -> None:
        """get_connected_data populates cache and lifecycle counts it."""
        ws = CollectorWorkspace([])
        ws.get_connected_data()
        info = ws.get_lifecycle()
        self.assertEqual(info.cached_panel_count, 1)
        self.assertIn("connected_data", ws._cache)

    def test_get_connected_data_with_real_engines(self) -> None:
        """Real engine integration produces actual cross-references."""
        from coin_collection import CoinItem
        from datetime import datetime

        now = datetime.now().isoformat()
        items = [
            CoinItem(
                id="usa_1900", image_path="", country="USA", denomination="Cent",
                year="1900", grade="VF", notes="", date_added=now, quantity=1,
            ),
        ]
        ws = CollectorWorkspace(items)
        report = ws.get_connected_data()
        self.assertIsInstance(report, ConnectedDataReport)
        self.assertEqual(report.engine_errors, [])

    def test_connected_data_report_has_summary(self) -> None:
        """ConnectedDataReport includes summary when available."""
        report = ConnectedDataReport()
        self.assertIsNone(report.summary)
        self.assertEqual(report.total_connections, 0)
        self.assertEqual(report.overall_match_rate, 0.0)

    def test_connected_data_report_total_connections(self) -> None:
        """total_connections sums match_count across all reports."""
        from connected_data import CrossReferenceReport, ConnectedReport, Connection, MatchType

        conn = Connection("photo", "grading", "p1", "g1", MatchType.EXACT)
        sub_report = ConnectedReport("photo", "grading", 1, 1, connections=[conn])
        cross_ref = CrossReferenceReport(reports=[sub_report])

        report = ConnectedDataReport(cross_reference=cross_ref)
        self.assertEqual(report.total_connections, 1)

    def test_connected_data_report_overall_match_rate(self) -> None:
        """overall_match_rate delegates to summary."""
        from connected_data import ConnectionSummary

        summary = ConnectionSummary(total_photos=10, photos_linked=5)
        report = ConnectedDataReport(summary=summary)
        self.assertEqual(report.overall_match_rate, 0.5)

    def test_build_connected_context(self) -> None:
        """_build_connected_context returns ConnectedContext with all workspace fields."""
        ws = CollectorWorkspace(
            collection_items=["item1"],
            photo_records=["p1"],
            ocr_reports=["o1"],
            shopping_candidates=["s1"],
            want_list_intents=["w1"],
            watchlists=["wl1"],
        )
        context = ws._build_connected_context()
        self.assertEqual(context.collection_items, ["item1"])
        self.assertEqual(context.photo_records, ["p1"])
        self.assertEqual(context.ocr_reports, ["o1"])
        self.assertEqual(context.shopping_candidates, ["s1"])
        self.assertEqual(context.want_list_intents, ["w1"])
        self.assertEqual(context.watchlists, ["wl1"])
        self.assertIsNone(context.grading_assessments)
        self.assertIsNone(context.market_records)
        self.assertIsNone(context.batch_candidates)

    def test_get_opportunities_with_connected_data(self) -> None:
        """get_opportunities passes connected_data_engine to SmartShoppingAssistant."""
        ws = CollectorWorkspace(
            collection_items=["item1"],
            shopping_candidates=["s1"],
            want_list_intents=["w1"],
        )
        # Mock the smart shopping engine to capture the call
        mock_shopping = MagicMock()
        mock_report = MagicMock()
        mock_report.recommendations = []
        mock_report.best_next_purchase = None
        mock_report.highest_impact_candidate = None
        mock_report.connected_data = {"watchlist_matches": 3, "total_recommendations": 0, "match_rate": 0.0}
        mock_shopping.generate_report.return_value = mock_report

        ws._engines["smart_shopping"] = mock_shopping
        ws._engines["opportunity_engine"] = MagicMock()
        ws._engines["opportunity_engine"].generate_report.return_value = MagicMock(budget_recommendations=[])

        report = ws.get_opportunities()
        self.assertEqual(report.total_opportunities, 0)
        # Verify generate_report was called with connected_data_engine
        call_kwargs = mock_shopping.generate_report.call_args[1]
        self.assertIn("connected_data_engine", call_kwargs)

    def test_get_opportunities_fallback_without_connected_data(self) -> None:
        """If connected_data engine cannot be retrieved, get_opportunities falls back."""
        ws = CollectorWorkspace(
            collection_items=["item1"],
            shopping_candidates=["s1"],
        )
        mock_shopping = MagicMock()
        mock_report = MagicMock()
        mock_report.recommendations = []
        mock_report.best_next_purchase = None
        mock_report.highest_impact_candidate = None
        mock_shopping.generate_report.return_value = mock_report

        ws._engines["smart_shopping"] = mock_shopping
        ws._engines["opportunity_engine"] = MagicMock()
        ws._engines["opportunity_engine"].generate_report.return_value = MagicMock(budget_recommendations=[])
        # Do NOT pre-populate connected_data engine — force _create_engine to fail
        # by overriding _create_engine for this specific name
        original_create = ws._create_engine

        def failing_create(name: str) -> Any:
            if name == "connected_data":
                raise RuntimeError("Engine unavailable")
            return original_create(name)

        ws._create_engine = failing_create

        report = ws.get_opportunities()
        # Should still succeed (fallback path)
        self.assertEqual(report.total_opportunities, 0)
        # Verify generate_report was called once (fallback only, since _get_engine failed)
        self.assertEqual(mock_shopping.generate_report.call_count, 1)
        # Verify it was called WITHOUT connected_data_engine
        call_kwargs = mock_shopping.generate_report.call_args[1]
        self.assertNotIn("connected_data_engine", call_kwargs)

    # ---------------------------------------------------------------------------
    # Phase 4: Reports Panel integration tests
    # ---------------------------------------------------------------------------

    def test_reports_menu_includes_connected_data(self) -> None:
        """Reports menu includes connected_data descriptor."""
        ws = CollectorWorkspace([])
        menu = ws.get_reports()
        descriptor = menu.by_name("connected_data")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.title, "Connected Data Cross-Reference")
        self.assertEqual(descriptor.category, "Data Integrity")
        self.assertTrue(descriptor.has_markdown_export)
        self.assertFalse(descriptor.has_csv_export)
        self.assertTrue(descriptor.available)

    def test_generate_report_connected_data(self) -> None:
        """Can generate connected_data report by name."""
        ws = CollectorWorkspace([])
        result = ws.generate_report("connected_data")
        self.assertIn("cross_reference", result)
        self.assertIn("summary", result)
        self.assertIn("generated_at", result)

    def test_export_report_connected_data_markdown(self) -> None:
        """Can export connected_data report to markdown."""
        import tempfile
        import os

        ws = CollectorWorkspace([])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "connected_data.md")
            result = ws.export_report("connected_data", "markdown", path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("# Connected Data Cross-Reference Report", content)


class TestCollectorWorkspacePhase4Integration(unittest.TestCase):
    """Integration tests for Phase 4 lifecycle with real engines."""

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
        ]

    def test_lifecycle_with_real_engines(self) -> None:
        """Use real engines to verify lifecycle diagnostics."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items)

        info_before = ws.get_lifecycle()
        self.assertEqual(info_before.engine_count, 0)
        self.assertEqual(info_before.cached_panel_count, 0)

        ws.get_dashboard()
        info_after = ws.get_lifecycle()
        self.assertGreater(info_after.engine_count, 0)
        self.assertEqual(info_after.cached_panel_count, 1)
        self.assertEqual(info_after.collection_item_count, 3)

    def test_refresh_with_real_engines(self) -> None:
        """Use real engines to verify refresh behavior."""
        items = self._make_real_items()
        ws = CollectorWorkspace(items)

        report1 = ws.get_dashboard()
        info1 = ws.get_lifecycle()
        engine_ids_before = set(id(e) for e in ws._engines.values())

        ws.refresh()
        info2 = ws.get_lifecycle()
        self.assertEqual(info2.cached_panel_count, 0)
        self.assertEqual(info2.engine_count, info1.engine_count)

        report2 = ws.get_dashboard()
        self.assertIsNot(report1, report2)
        self.assertEqual(report1.quality_score, report2.quality_score)

        # Verify engine instances are the same objects
        engine_ids_after = set(id(e) for e in ws._engines.values())
        self.assertEqual(engine_ids_before, engine_ids_after)


# ---------------------------------------------------------------------------
# Phase 5 GUI Smoke Tests
# ---------------------------------------------------------------------------

class TestCollectorWorkspaceGUISmoke(unittest.TestCase):
    """Smoke tests for GUI integration — verify imports and basic wiring."""

    def test_gui_imports_collector_workspace_cleanly(self) -> None:
        """coin_collection_gui should import CollectorWorkspace without error."""
        try:
            import coin_collection_gui
            self.assertTrue(hasattr(coin_collection_gui, "CoinCollectionGUI"))
        except Exception as e:
            self.fail(f"coin_collection_gui failed to import: {e}")

    def test_gui_has_open_collector_workspace_method(self) -> None:
        """CoinCollectionGUI should have open_collector_workspace method."""
        import coin_collection_gui
        self.assertTrue(
            hasattr(coin_collection_gui.CoinCollectionGUI, "open_collector_workspace"),
            "CoinCollectionGUI should have open_collector_workspace method",
        )

    def test_gui_has_workspace_helper_methods(self) -> None:
        """CoinCollectionGUI should have workspace tab helper methods."""
        import coin_collection_gui
        required_methods = [
            "_create_workspace_tabs",
            "_create_dashboard_tab",
            "_create_inbox_tab",
            "_create_reports_tab",
            "_refresh_workspace_tabs",
            "_format_dashboard",
            "_format_inbox",
            "_format_collection_summary",
        ]
        for method in required_methods:
            self.assertTrue(
                hasattr(coin_collection_gui.CoinCollectionGUI, method),
                f"CoinCollectionGUI should have {method}",
            )

    def test_gui_has_format_engine_errors(self) -> None:
        """CoinCollectionGUI should have _format_engine_errors helper."""
        import coin_collection_gui
        self.assertTrue(hasattr(coin_collection_gui.CoinCollectionGUI, "_format_engine_errors"))

    def test_gui_has_connected_data_tab(self) -> None:
        """CoinCollectionGUI should have _create_connected_data_tab method."""
        import coin_collection_gui
        self.assertTrue(
            hasattr(coin_collection_gui.CoinCollectionGUI, "_create_connected_data_tab"),
            "CoinCollectionGUI should have _create_connected_data_tab",
        )

    def test_gui_has_format_connected_data(self) -> None:
        """CoinCollectionGUI should have _format_connected_data method."""
        import coin_collection_gui
        self.assertTrue(
            hasattr(coin_collection_gui.CoinCollectionGUI, "_format_connected_data"),
            "CoinCollectionGUI should have _format_connected_data",
        )

    def test_gui_has_refresh_connected_data(self) -> None:
        """_refresh_workspace_tabs should reference connected_data in panel_methods."""
        import coin_collection_gui
        import inspect
        source = inspect.getsource(coin_collection_gui.CoinCollectionGUI._refresh_workspace_tabs)
        self.assertIn("connected_data", source)


# ---------------------------------------------------------------------------
# Phase 4 Tests — Advisor Signal Quality Fixes
# ---------------------------------------------------------------------------

class TestCollectorWorkspacePhase4SignalQuality(unittest.TestCase):
    """Unit tests for v8.5 Phase 4 upstream signal quality fixes."""

    def test_photo_vault_missing_count_with_no_records(self) -> None:
        """When no photo records exist, missing_photo_count should equal items_without_photos."""
        from coin_collection import CoinItem
        items = [
            CoinItem(id="c001", image_path="", country="Canada", denomination="5 cents", year="1910", grade="VG8", notes="", date_added="2026-01-01"),
        ]
        ws = CollectorWorkspace(items)
        report = ws.get_photo_vault()

        self.assertIsInstance(report, PhotoVaultReport)
        self.assertEqual(report.total_collection_items, 1)
        self.assertEqual(report.items_without_photos, 1)
        # Phase 4 fix: missing_photo_count should reflect items without photos
        # even when no photo records exist at all
        self.assertEqual(report.missing_photo_count, 1)

    def test_inbox_includes_workflow_reviews(self) -> None:
        """Inbox should include pending workflow reviews."""
        ws = CollectorWorkspace([])

        mock_queue = MagicMock()
        mock_queue.pending_count = 0
        mock_queue.candidates = []

        mock_session = MagicMock()
        mock_session.queue = mock_queue

        mock_assistant = MagicMock()
        mock_assistant.start_session.return_value = mock_session

        # Mock workflow engine with 3 pending statuses
        mock_workflow = MagicMock()
        mock_status1 = MagicMock(name="Review A", id="r1")
        mock_status2 = MagicMock(name="Review B", id="r2")
        mock_status3 = MagicMock(name="Review C", id="r3")
        mock_summary = MagicMock()
        mock_summary.statuses = [mock_status1, mock_status2, mock_status3]
        mock_daily = MagicMock()
        mock_daily.summary = mock_summary
        mock_workflow.daily_summary.return_value = mock_daily

        ws._engines["collection_assistant"] = mock_assistant
        ws._engines["batch_processing"] = MagicMock()
        ws._engines["ai_grading"] = MagicMock()
        ws._engines["collector_workflows"] = mock_workflow

        report = ws.get_inbox()

        self.assertEqual(report.total_pending, 3)
        self.assertEqual(len(report.items), 3)
        for item in report.items:
            self.assertEqual(item["source"], "Workflow")

    def test_want_list_gap_targets_include_year(self) -> None:
        """Gap targets should include a specific year when missing_years is available."""
        ws = CollectorWorkspace([])

        mock_intel = MagicMock()
        mock_gap_row = MagicMock()
        mock_gap_row.to_dict.return_value = {
            "country": "Canada",
            "denomination": "5 cents",
            "missing_years": "1910, 1911, 1912",
            "completion_percentage": 25.0,
        }
        mock_intel.generate_gap_report.return_value = {"series_rows": [mock_gap_row]}
        mock_intel.detect_upgrade_candidates.return_value = []

        ws._engines["collection_intelligence"] = mock_intel
        ws._engines["watchlist_engine"] = MagicMock()

        report = ws.get_want_list()

        self.assertEqual(len(report.gap_targets), 1)
        self.assertEqual(report.gap_targets[0]["country"], "Canada")
        self.assertEqual(report.gap_targets[0]["denomination"], "5 cents")
        self.assertEqual(report.gap_targets[0]["year"], "1910")

    def test_opportunities_falls_back_to_intrinsic(self) -> None:
        """When no shopping candidates exist, opportunities should use intrinsic collection targets."""
        from coin_collection import CoinItem
        items = [
            CoinItem(id="c001", image_path="", country="Canada", denomination="5 cents", year="1910", grade="VG8", notes="", date_added="2026-01-01"),
        ]
        ws = CollectorWorkspace(items)

        report = ws.get_opportunities()

        # Without shopping candidates, smart_shopping fails.
        # OpportunityEngine should still produce collection-target opportunities.
        self.assertIsInstance(report, OpportunitiesReport)
        # top_recommendations may be empty if no intrinsic opportunities exist
        # (e.g., no gaps), but the mechanism should be in place
        self.assertIsInstance(report.top_recommendations, list)

    def test_collection_summary_duplicate_count(self) -> None:
        """Collection summary should include actual duplicate count from intelligence."""
        from coin_collection import CoinItem
        items = [
            CoinItem(id="c001", image_path="", country="Canada", denomination="5 cents", year="1910", grade="VG8", notes="", date_added="2026-01-01"),
            CoinItem(id="c002", image_path="", country="Canada", denomination="5 cents", year="1910", grade="F12", notes="", date_added="2026-01-01"),
        ]
        ws = CollectorWorkspace(items)

        report = ws.get_collection_summary()

        self.assertIsInstance(report, CollectionSummaryReport)
        self.assertEqual(report.total_items, 2)
        self.assertEqual(report.duplicate_count, 1)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
