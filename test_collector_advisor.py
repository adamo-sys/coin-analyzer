"""Tests for collector_advisor.py

v8.5 Phase 1: Unit tests for CollectorAdvisor core engine.

Coverage targets:
- Every public method on CollectorAdvisor
- DTO validation (RecommendationReason, CollectorRecommendation, AdvisorReport)
- Deterministic ordering invariant
- Evidence non-empty invariant on every recommendation
- Graceful degradation (workspace panels that fail)
- Zero modifications to existing engines
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

from collector_advisor import (
    CollectorAdvisor,
    CollectorRecommendation,
    RecommendationCategory,
    RecommendationReason,
    AdvisorReport,
    _priority_sort_key,
)


# ---------------------------------------------------------------------------
# DTO tests
# ---------------------------------------------------------------------------

class TestRecommendationReason(unittest.TestCase):
    """Unit tests for RecommendationReason dataclass."""

    def test_creation(self):
        reason = RecommendationReason(
            category="priority",
            description="test reason",
            source_engine="test_engine",
            confidence="HIGH",
        )
        self.assertEqual(reason.category, "priority")
        self.assertEqual(reason.description, "test reason")
        self.assertEqual(reason.source_engine, "test_engine")
        self.assertEqual(reason.confidence, "HIGH")

    def test_default_confidence(self):
        reason = RecommendationReason(
            category="priority",
            description="test reason",
            source_engine="test_engine",
        )
        self.assertEqual(reason.confidence, "HIGH")


class TestCollectorRecommendation(unittest.TestCase):
    """Unit tests for CollectorRecommendation dataclass."""

    def test_creation_with_evidence(self):
        evidence = [
            RecommendationReason("priority", "reason 1", "engine1"),
            RecommendationReason("upgrade", "reason 2", "engine2"),
        ]
        rec = CollectorRecommendation(
            recommendation_id="rec_1",
            recommendation_type=RecommendationCategory.PRIORITY_ACQUISITION,
            title="Test Recommendation",
            description="A test recommendation",
            evidence=evidence,
            priority="HIGH",
            urgency="SHORT_TERM",
        )
        self.assertEqual(rec.recommendation_id, "rec_1")
        self.assertEqual(len(rec.evidence), 2)
        self.assertEqual(rec.priority, "HIGH")
        self.assertEqual(rec.urgency, "SHORT_TERM")
        self.assertEqual(rec.status, "ACTIVE")

    def test_empty_evidence_raises(self):
        """Every recommendation must include evidence."""
        with self.assertRaises(ValueError) as ctx:
            CollectorRecommendation(
                recommendation_id="rec_empty",
                recommendation_type=RecommendationCategory.UPGRADE,
                title="Empty Evidence",
                description="Should fail",
                evidence=[],
            )
        self.assertIn("evidence", str(ctx.exception).lower())

    def test_evidence_summary(self):
        evidence = [
            RecommendationReason("priority", "reason 1", "engine1", "HIGH"),
        ]
        rec = CollectorRecommendation(
            recommendation_id="rec_1",
            recommendation_type=RecommendationCategory.PRIORITY_ACQUISITION,
            title="Test",
            description="Test desc",
            evidence=evidence,
        )
        summary = rec.evidence_summary
        self.assertIn("engine1", summary)
        self.assertIn("reason 1", summary)
        self.assertIn("HIGH", summary)


class TestAdvisorReport(unittest.TestCase):
    """Unit tests for AdvisorReport dataclass."""

    def test_empty_report(self):
        report = AdvisorReport()
        self.assertEqual(report.recommendations, [])
        self.assertEqual(report.summary, "")
        self.assertIsNone(report.next_best_action)
        self.assertEqual(report.risks, [])
        self.assertEqual(report.opportunities, [])

    def test_report_with_recommendations(self):
        evidence = [RecommendationReason("priority", "reason", "engine")]
        rec = CollectorRecommendation(
            recommendation_id="rec_1",
            recommendation_type=RecommendationCategory.PRIORITY_ACQUISITION,
            title="Test",
            description="Test",
            evidence=evidence,
        )
        report = AdvisorReport(recommendations=[rec], summary="Test summary")
        self.assertEqual(len(report.recommendations), 1)
        self.assertEqual(report.summary, "Test summary")


# ---------------------------------------------------------------------------
# CollectorAdvisor tests
# ---------------------------------------------------------------------------

class TestCollectorAdvisor(unittest.TestCase):
    """Unit tests for CollectorAdvisor."""

    def _mock_workspace(self, **panel_overrides):
        """Create a mock workspace with configurable panel returns.

        Default: all panels return empty/None values. Override specific
        panels by passing kwargs with the panel name as key.
        """
        workspace = MagicMock()

        # Default panel returns
        defaults = {
            "get_dashboard": MagicMock(
                health_score=None,
                quality_score=None,
                integrity_score=None,
                top_priority=None,
                best_next_purchase=None,
                todays_tasks=[],
                recent_activity=[],
                data_safety_status=None,
                backup_ready=False,
                engine_errors=[],
            ),
            "get_inbox": MagicMock(
                total_pending=0,
                collection_assistant_pending=0,
                batch_processing_pending=0,
                ai_grading_review=0,
                workflow_items=[],
                items=[],
                engine_errors=[],
            ),
            "get_collection_summary": MagicMock(
                total_items=0,
                total_countries=0,
                total_denominations=0,
                total_years=0,
                grade_coverage=None,
                series_completion=[],
                recent_additions=0,
                quality_score=None,
                integrity_score=None,
                engine_errors=[],
            ),
            "get_want_list": MagicMock(
                upgrade_candidates=[],
                gap_targets=[],
                watchlist_matches=[],
                total_upgrades=0,
                total_gaps=0,
                total_watchlist_matches=0,
                engine_errors=[],
            ),
            "get_opportunities": MagicMock(
                top_recommendations=[],
                best_next_purchase=None,
                highest_impact=None,
                total_opportunities=0,
                budget_recommendations=[],
                engine_errors=[],
            ),
            "get_ai_queue": MagicMock(
                total_pending=0,
                collection_assistant_pending=0,
                batch_processing_pending=0,
                ai_grading_review=0,
                workflow_items=[],
                items=[],
                engine_errors=[],
            ),
            "get_batch_queue": MagicMock(
                total_pending=0,
                collection_assistant_pending=0,
                batch_processing_pending=0,
                ai_grading_review=0,
                workflow_items=[],
                items=[],
                engine_errors=[],
            ),
            "get_photo_vault": MagicMock(
                total_collection_items=0,
                items_with_photos=0,
                items_without_photos=0,
                coverage_percentage=0.0,
                certified_items=0,
                certified_with_photos=0,
                missing_photo_count=0,
                duplicate_photo_count=0,
                recommended_actions=[],
                engine_errors=[],
            ),
            "get_workflow_status": MagicMock(
                active_workflows=[],
                todays_tasks=[],
                pending_reviews=0,
                next_actions=[],
                workflow_health=None,
                engine_errors=[],
            ),
            "get_data_safety": MagicMock(
                backup_ready=True,
                last_snapshot_age=None,
                integrity_warnings=[],
                persistence_areas=[],
                total_persistence_areas=0,
                persisted_areas=0,
                session_only_areas=0,
                engine_errors=[],
            ),
            "get_connected_data": MagicMock(
                summary=None,
                cross_reference=None,
                top_connections=[],
                engine_errors=[],
            ),
        }

        # Apply overrides
        for panel_name, panel_value in panel_overrides.items():
            defaults[panel_name] = panel_value

        # Attach to workspace
        for panel_name, panel_value in defaults.items():
            setattr(workspace, panel_name, lambda pv=panel_value: pv)

        return workspace

    def test_advisor_creation(self):
        """CollectorAdvisor can be created with a mock workspace."""
        workspace = self._mock_workspace()
        advisor = CollectorAdvisor(workspace)
        self.assertIsNotNone(advisor)
        self.assertIs(advisor.workspace, workspace)

    def test_generate_advisory_report_empty_workspace(self):
        """Empty workspace produces empty report with no errors."""
        workspace = self._mock_workspace()
        advisor = CollectorAdvisor(workspace)
        report = advisor.generate_advisory_report()

        self.assertIsInstance(report, AdvisorReport)
        self.assertEqual(report.recommendations, [])
        self.assertIsNone(report.next_best_action)
        self.assertIn("Total recommendations: 0", report.summary)

    def test_generate_advisory_report_with_gaps(self):
        """Workspace with want-list gaps produces priority acquisition recommendations."""
        want_list = MagicMock(
            upgrade_candidates=[],
            gap_targets=[
                {"id": "gap_1", "country": "Canada", "denomination": "5 cents", "year": "1910"},
                {"id": "gap_2", "country": "Newfoundland", "denomination": "10 cents", "year": "1908"},
            ],
            watchlist_matches=[],
            total_upgrades=0,
            total_gaps=2,
            total_watchlist_matches=0,
            engine_errors=[],
        )
        workspace = self._mock_workspace(get_want_list=want_list)
        advisor = CollectorAdvisor(workspace)
        report = advisor.generate_advisory_report()

        self.assertGreater(len(report.recommendations), 0)
        # Should have gap recommendations
        gap_recs = [r for r in report.recommendations if r.recommendation_type == RecommendationCategory.PRIORITY_ACQUISITION]
        self.assertGreaterEqual(len(gap_recs), 2)

        # Every recommendation has evidence
        for rec in report.recommendations:
            self.assertGreater(len(rec.evidence), 0, f"Recommendation {rec.recommendation_id} has no evidence")

    def test_recommend_priority_acquisitions_with_opportunities(self):
        """Opportunities feed into priority acquisitions."""
        opportunities = MagicMock(
            top_recommendations=[
                {"id": "opp_1", "title": "Buy 1912 5¢", "description": "Good deal"},
                {"id": "opp_2", "title": "Buy 1905 10¢", "description": "Another deal"},
            ],
            best_next_purchase="Buy 1912 5¢",
            highest_impact=None,
            total_opportunities=2,
            budget_recommendations=[],
            engine_errors=[],
        )
        workspace = self._mock_workspace(get_opportunities=opportunities)
        advisor = CollectorAdvisor(workspace)
        recs = advisor.recommend_priority_acquisitions()

        self.assertGreater(len(recs), 0)
        opp_recs = [r for r in recs if r.recommendation_type == RecommendationCategory.PRIORITY_ACQUISITION]
        self.assertGreaterEqual(len(opp_recs), 2)
        for rec in recs:
            self.assertGreater(len(rec.evidence), 0)

    def test_recommend_grade_submissions_with_photo_vault(self):
        """Photo vault coverage gaps produce grading recommendations."""
        photo_vault = MagicMock(
            total_collection_items=10,
            items_with_photos=7,
            items_without_photos=3,
            coverage_percentage=70.0,
            certified_items=0,
            certified_with_photos=0,
            missing_photo_count=3,
            duplicate_photo_count=0,
            recommended_actions=[],
            engine_errors=[],
        )
        workspace = self._mock_workspace(get_photo_vault=photo_vault)
        advisor = CollectorAdvisor(workspace)
        recs = advisor.recommend_grade_submissions()

        self.assertGreater(len(recs), 0)
        photo_rec = [r for r in recs if "photo" in r.recommendation_id.lower()]
        self.assertGreaterEqual(len(photo_rec), 1)
        for rec in recs:
            self.assertGreater(len(rec.evidence), 0)

    def test_recommend_grade_submissions_with_ai_queue(self):
        """AI grading review queue produces grading recommendations."""
        ai_queue = MagicMock(
            total_pending=0,
            collection_assistant_pending=0,
            batch_processing_pending=0,
            ai_grading_review=3,
            workflow_items=[],
            items=[],
            engine_errors=[],
        )
        workspace = self._mock_workspace(get_ai_queue=ai_queue)
        advisor = CollectorAdvisor(workspace)
        recs = advisor.recommend_grade_submissions()

        review_recs = [r for r in recs if "review" in r.recommendation_id.lower()]
        self.assertGreaterEqual(len(review_recs), 1)
        for rec in recs:
            self.assertGreater(len(rec.evidence), 0)

    def test_recommend_upgrades_with_want_list(self):
        """Want-list upgrade candidates produce upgrade recommendations."""
        want_list = MagicMock(
            upgrade_candidates=[
                {"id": "upg_1", "country": "Canada", "denomination": "Large Cent", "year": "1859", "current_grade": "VG8", "target_grade": "AU50"},
            ],
            gap_targets=[],
            watchlist_matches=[],
            total_upgrades=1,
            total_gaps=0,
            total_watchlist_matches=0,
            engine_errors=[],
        )
        workspace = self._mock_workspace(get_want_list=want_list)
        advisor = CollectorAdvisor(workspace)
        recs = advisor.recommend_upgrades()

        self.assertGreater(len(recs), 0)
        for rec in recs:
            self.assertEqual(rec.recommendation_type, RecommendationCategory.UPGRADE)
            self.assertGreater(len(rec.evidence), 0)

    def test_recommend_duplicate_disposal_with_large_collection(self):
        """Large collections produce duplicate review recommendations."""
        summary = MagicMock(
            total_items=75,
            total_countries=5,
            total_denominations=10,
            total_years=50,
            grade_coverage=None,
            series_completion=[],
            recent_additions=0,
            quality_score=None,
            integrity_score=None,
            engine_errors=[],
        )
        workspace = self._mock_workspace(get_collection_summary=summary)
        advisor = CollectorAdvisor(workspace)
        recs = advisor.recommend_duplicate_disposal()

        self.assertGreater(len(recs), 0)
        self.assertEqual(recs[0].recommendation_type, RecommendationCategory.DISPOSE_DUPLICATE)
        self.assertGreater(len(recs[0].evidence), 0)

    def test_recommend_duplicate_disposal_small_collection(self):
        """Small collections produce no duplicate disposal recommendations."""
        summary = MagicMock(
            total_items=10,
            total_countries=2,
            total_denominations=3,
            total_years=8,
            grade_coverage=None,
            series_completion=[],
            recent_additions=0,
            quality_score=None,
            integrity_score=None,
            engine_errors=[],
        )
        workspace = self._mock_workspace(get_collection_summary=summary)
        advisor = CollectorAdvisor(workspace)
        recs = advisor.recommend_duplicate_disposal()

        self.assertEqual(len(recs), 0)

    def test_recommend_budget_allocation_with_budget_recommendations(self):
        """Budget recommendations from opportunities produce budget allocation advice."""
        opportunities = MagicMock(
            top_recommendations=[],
            best_next_purchase=None,
            highest_impact=None,
            total_opportunities=0,
            budget_recommendations=["Focus on Newfoundland", "Consider Canadian silver"],
            engine_errors=[],
        )
        workspace = self._mock_workspace(get_opportunities=opportunities)
        advisor = CollectorAdvisor(workspace)
        recs = advisor.recommend_budget_allocation()

        self.assertGreater(len(recs), 0)
        for rec in recs:
            self.assertEqual(rec.recommendation_type, RecommendationCategory.BUDGET_ALLOCATE)
            self.assertGreater(len(rec.evidence), 0)

    def test_recommend_budget_allocation_with_low_quality(self):
        """Low quality score produces budget allocation recommendation."""
        dashboard = MagicMock(
            health_score=80,
            quality_score=40,
            integrity_score=90,
            top_priority=None,
            best_next_purchase=None,
            todays_tasks=[],
            recent_activity=[],
            data_safety_status=None,
            backup_ready=False,
            engine_errors=[],
        )
        workspace = self._mock_workspace(get_dashboard=dashboard)
        advisor = CollectorAdvisor(workspace)
        recs = advisor.recommend_budget_allocation()

        quality_recs = [r for r in recs if r.recommendation_id == "budget_quality"]
        self.assertGreaterEqual(len(quality_recs), 1)
        for rec in recs:
            self.assertGreater(len(rec.evidence), 0)

    def test_recommend_next_action_from_list(self):
        """next_action returns highest-priority recommendation from provided list."""
        evidence = [RecommendationReason("priority", "reason", "engine")]
        recs = [
            CollectorRecommendation("rec_1", RecommendationCategory.PRIORITY_ACQUISITION, "Low", "desc", evidence, priority="LOW"),
            CollectorRecommendation("rec_2", RecommendationCategory.UPGRADE, "High", "desc", evidence, priority="HIGH"),
            CollectorRecommendation("rec_3", RecommendationCategory.PRIORITY_ACQUISITION, "Medium", "desc", evidence, priority="MEDIUM"),
        ]
        workspace = self._mock_workspace()
        advisor = CollectorAdvisor(workspace)
        next_best = advisor.recommend_next_action(recs)

        self.assertIsNotNone(next_best)
        self.assertEqual(next_best.recommendation_id, "rec_2")
        self.assertEqual(next_best.priority, "HIGH")

    def test_recommend_next_action_none(self):
        """Empty list returns None."""
        workspace = self._mock_workspace()
        advisor = CollectorAdvisor(workspace)
        next_best = advisor.recommend_next_action([])
        self.assertIsNone(next_best)

    def test_recommend_next_action_generates_report(self):
        """next_action without list generates a fresh report."""
        want_list = MagicMock(
            upgrade_candidates=[],
            gap_targets=[
                {"id": "gap_1", "country": "Canada", "denomination": "5 cents", "year": "1910"},
            ],
            watchlist_matches=[],
            total_upgrades=0,
            total_gaps=1,
            total_watchlist_matches=0,
            engine_errors=[],
        )
        workspace = self._mock_workspace(get_want_list=want_list)
        advisor = CollectorAdvisor(workspace)
        next_best = advisor.recommend_next_action()

        self.assertIsNotNone(next_best)
        self.assertGreater(len(next_best.evidence), 0)

    # ------------------------------------------------------------------
    # Determinism tests
    # ------------------------------------------------------------------

    def test_deterministic_ordering(self):
        """Same workspace state → same recommendation ordering."""
        want_list = MagicMock(
            upgrade_candidates=[
                {"id": "upg_1", "country": "Canada", "denomination": "Large Cent", "year": "1859", "current_grade": "VG8", "target_grade": "AU50"},
            ],
            gap_targets=[
                {"id": "gap_1", "country": "Newfoundland", "denomination": "5 cents", "year": "1910"},
                {"id": "gap_2", "country": "Newfoundland", "denomination": "10 cents", "year": "1908"},
            ],
            watchlist_matches=[],
            total_upgrades=1,
            total_gaps=2,
            total_watchlist_matches=0,
            engine_errors=[],
        )

        opportunities = MagicMock(
            top_recommendations=[
                {"id": "opp_1", "title": "Buy 1912 5¢", "description": "Good deal"},
            ],
            best_next_purchase="Buy 1912 5¢",
            highest_impact=None,
            total_opportunities=1,
            budget_recommendations=[],
            engine_errors=[],
        )

        workspace = self._mock_workspace(get_want_list=want_list, get_opportunities=opportunities)

        advisor1 = CollectorAdvisor(workspace)
        report1 = advisor1.generate_advisory_report()
        ids1 = [r.recommendation_id for r in report1.recommendations]

        advisor2 = CollectorAdvisor(workspace)
        report2 = advisor2.generate_advisory_report()
        ids2 = [r.recommendation_id for r in report2.recommendations]

        self.assertEqual(ids1, ids2)
        self.assertEqual(report1.summary, report2.summary)
        if report1.next_best_action and report2.next_best_action:
            self.assertEqual(report1.next_best_action.recommendation_id, report2.next_best_action.recommendation_id)

    def test_priority_sorting_order(self):
        """HIGH priority recommendations sort before MEDIUM, before LOW."""
        evidence = [RecommendationReason("priority", "reason", "engine")]
        recs = [
            CollectorRecommendation("rec_low", RecommendationCategory.PRIORITY_ACQUISITION, "Low", "desc", evidence, priority="LOW"),
            CollectorRecommendation("rec_high", RecommendationCategory.UPGRADE, "High", "desc", evidence, priority="HIGH"),
            CollectorRecommendation("rec_medium", RecommendationCategory.PRIORITY_ACQUISITION, "Medium", "desc", evidence, priority="MEDIUM"),
        ]
        sorted_recs = sorted(recs, key=_priority_sort_key)
        ids = [r.recommendation_id for r in sorted_recs]
        self.assertEqual(ids, ["rec_high", "rec_medium", "rec_low"])

    def test_urgency_sorting_order(self):
        """IMMEDIATE urgency sorts before SHORT_TERM, before LONG_TERM, before ONGOING."""
        evidence = [RecommendationReason("priority", "reason", "engine")]
        recs = [
            CollectorRecommendation("rec_ongoing", RecommendationCategory.PRIORITY_ACQUISITION, "Ongoing", "desc", evidence, priority="HIGH", urgency="ONGOING"),
            CollectorRecommendation("rec_immediate", RecommendationCategory.PRIORITY_ACQUISITION, "Immediate", "desc", evidence, priority="HIGH", urgency="IMMEDIATE"),
            CollectorRecommendation("rec_long", RecommendationCategory.PRIORITY_ACQUISITION, "Long", "desc", evidence, priority="HIGH", urgency="LONG_TERM"),
            CollectorRecommendation("rec_short", RecommendationCategory.PRIORITY_ACQUISITION, "Short", "desc", evidence, priority="HIGH", urgency="SHORT_TERM"),
        ]
        sorted_recs = sorted(recs, key=_priority_sort_key)
        ids = [r.recommendation_id for r in sorted_recs]
        self.assertEqual(ids, ["rec_immediate", "rec_short", "rec_long", "rec_ongoing"])

    def test_stable_id_tiebreaking(self):
        """Same priority and urgency: stable ID breaks ties."""
        evidence = [RecommendationReason("priority", "reason", "engine")]
        recs = [
            CollectorRecommendation("rec_z", RecommendationCategory.PRIORITY_ACQUISITION, "Z", "desc", evidence, priority="HIGH", urgency="SHORT_TERM"),
            CollectorRecommendation("rec_a", RecommendationCategory.PRIORITY_ACQUISITION, "A", "desc", evidence, priority="HIGH", urgency="SHORT_TERM"),
            CollectorRecommendation("rec_m", RecommendationCategory.PRIORITY_ACQUISITION, "M", "desc", evidence, priority="HIGH", urgency="SHORT_TERM"),
        ]
        sorted_recs = sorted(recs, key=_priority_sort_key)
        ids = [r.recommendation_id for r in sorted_recs]
        self.assertEqual(ids, ["rec_a", "rec_m", "rec_z"])

    # ------------------------------------------------------------------
    # Phase 3 enrichment tests
    # ------------------------------------------------------------------

    def test_recommendations_have_at_least_two_evidence_items(self):
        """When cross-panel data is available, every recommendation has >=2 evidence items."""
        want_list = MagicMock(
            upgrade_candidates=[
                {"id": "upg_1", "country": "Canada", "denomination": "Large Cent", "year": "1859", "current_grade": "VG8", "target_grade": "AU50"},
            ],
            gap_targets=[
                {"id": "gap_1", "country": "Canada", "denomination": "5 cents", "year": "1910"},
            ],
            watchlist_matches=[],
            total_upgrades=1,
            total_gaps=1,
            total_watchlist_matches=0,
            engine_errors=[],
        )
        collection_summary = MagicMock(
            total_items=75,
            total_countries=5,
            total_denominations=10,
            total_years=50,
            grade_coverage=None,
            series_completion=[],
            recent_additions=0,
            quality_score=65,
            integrity_score=None,
            engine_errors=[],
        )
        dashboard = MagicMock(
            health_score=80,
            quality_score=45,
            integrity_score=90,
            top_priority="Fill Canada gaps",
            best_next_purchase="Acquire Canada 5 cents 1910",
            todays_tasks=[],
            recent_activity=[],
            data_safety_status=None,
            backup_ready=False,
            engine_errors=[],
        )
        opportunities = MagicMock(
            top_recommendations=[
                {"id": "opp_1", "title": "Buy 1912 5¢", "description": "Good deal"},
            ],
            best_next_purchase="Buy 1912 5¢",
            highest_impact=None,
            total_opportunities=1,
            budget_recommendations=["Focus on Canada"],
            engine_errors=[],
        )
        workspace = self._mock_workspace(
            get_want_list=want_list,
            get_collection_summary=collection_summary,
            get_dashboard=dashboard,
            get_opportunities=opportunities,
        )
        advisor = CollectorAdvisor(workspace)
        report = advisor.generate_advisory_report()

        for rec in report.recommendations:
            self.assertGreaterEqual(len(rec.evidence), 2,
                f"Recommendation {rec.recommendation_id} should have >=2 evidence items")

    def test_cross_panel_evidence_sources_labeled(self):
        """Evidence items should reference the correct source panels."""
        want_list = MagicMock(
            upgrade_candidates=[],
            gap_targets=[
                {"id": "gap_1", "country": "Canada", "denomination": "5 cents", "year": "1910"},
            ],
            watchlist_matches=[],
            total_upgrades=0,
            total_gaps=1,
            total_watchlist_matches=0,
            engine_errors=[],
        )
        collection_summary = MagicMock(
            total_items=10,
            total_countries=2,
            total_denominations=3,
            total_years=8,
            grade_coverage=None,
            series_completion=[],
            recent_additions=0,
            quality_score=55,
            integrity_score=None,
            engine_errors=[],
        )
        workspace = self._mock_workspace(
            get_want_list=want_list,
            get_collection_summary=collection_summary,
        )
        advisor = CollectorAdvisor(workspace)
        recs = advisor.recommend_priority_acquisitions()

        self.assertGreater(len(recs), 0)
        gap_rec = recs[0]
        sources = {e.source_engine for e in gap_rec.evidence}
        self.assertIn("want_list_generator", sources)
        self.assertIn("collection_intelligence", sources)
        self.assertIn("collection_summary", sources)

    def test_photo_vault_enriches_duplicate_disposal(self):
        """PhotoVaultReport duplicate count enriches duplicate disposal evidence."""
        summary = MagicMock(
            total_items=75,
            total_countries=5,
            total_denominations=10,
            total_years=50,
            grade_coverage=None,
            series_completion=[],
            recent_additions=0,
            quality_score=None,
            integrity_score=None,
            engine_errors=[],
        )
        photo_vault = MagicMock(
            total_collection_items=75,
            items_with_photos=70,
            items_without_photos=5,
            coverage_percentage=93.3,
            certified_items=0,
            certified_with_photos=0,
            missing_photo_count=5,
            duplicate_photo_count=3,
            recommended_actions=[],
            engine_errors=[],
        )
        workspace = self._mock_workspace(
            get_collection_summary=summary,
            get_photo_vault=photo_vault,
        )
        advisor = CollectorAdvisor(workspace)
        recs = advisor.recommend_duplicate_disposal()

        self.assertGreater(len(recs), 0)
        dup_rec = recs[0]
        photo_evidence = [e for e in dup_rec.evidence if e.source_engine == "photo_vault"]
        self.assertGreaterEqual(len(photo_evidence), 1)
        self.assertIn("3", photo_evidence[0].description)

    def test_dashboard_quality_enriches_budget_allocation(self):
        """Dashboard quality score and collection summary both enrich budget recommendations."""
        dashboard = MagicMock(
            health_score=80,
            quality_score=40,
            integrity_score=90,
            top_priority=None,
            best_next_purchase=None,
            todays_tasks=[],
            recent_activity=[],
            data_safety_status=None,
            backup_ready=False,
            engine_errors=[],
        )
        collection_summary = MagicMock(
            total_items=100,
            total_countries=10,
            total_denominations=20,
            total_years=60,
            grade_coverage=None,
            series_completion=[],
            recent_additions=0,
            quality_score=42,
            integrity_score=None,
            engine_errors=[],
        )
        workspace = self._mock_workspace(
            get_dashboard=dashboard,
            get_collection_summary=collection_summary,
        )
        advisor = CollectorAdvisor(workspace)
        recs = advisor.recommend_budget_allocation()

        quality_recs = [r for r in recs if r.recommendation_id == "budget_quality"]
        self.assertGreaterEqual(len(quality_recs), 1)
        rec = quality_recs[0]
        sources = {e.source_engine for e in rec.evidence}
        self.assertIn("collection_summary", sources)
        self.assertIn("collection_quality", sources)
        self.assertIn("collector_advisor", sources)

    def test_graceful_degradation_missing_cross_panel(self):
        """When cross-panel data is missing, recommendations still have >=2 evidence."""
        want_list = MagicMock(
            upgrade_candidates=[],
            gap_targets=[
                {"id": "gap_1", "country": "Canada", "denomination": "5 cents", "year": "1910"},
            ],
            watchlist_matches=[],
            total_upgrades=0,
            total_gaps=1,
            total_watchlist_matches=0,
            engine_errors=[],
        )
        workspace = MagicMock()
        workspace.get_want_list = MagicMock(return_value=want_list)
        workspace.get_opportunities = MagicMock(side_effect=Exception("opportunities failed"))
        workspace.get_collection_summary = MagicMock(side_effect=Exception("summary failed"))
        workspace.get_dashboard = MagicMock(side_effect=Exception("dashboard failed"))
        workspace.get_ai_queue = MagicMock(return_value=MagicMock(
            total_pending=0, collection_assistant_pending=0, batch_processing_pending=0,
            ai_grading_review=0, workflow_items=[], items=[], engine_errors=[],
        ))
        workspace.get_photo_vault = MagicMock(return_value=MagicMock(
            total_collection_items=0, items_with_photos=0, items_without_photos=0,
            coverage_percentage=100.0, certified_items=0, certified_with_photos=0,
            missing_photo_count=0, duplicate_photo_count=0, recommended_actions=[],
            engine_errors=[],
        ))
        workspace.get_batch_queue = MagicMock(return_value=MagicMock(
            total_pending=0, collection_assistant_pending=0, batch_processing_pending=0,
            ai_grading_review=0, workflow_items=[], items=[], engine_errors=[],
        ))
        workspace.get_workflow_status = MagicMock(return_value=MagicMock(
            active_workflows=[], todays_tasks=[], pending_reviews=0,
            next_actions=[], workflow_health=None, engine_errors=[],
        ))
        workspace.get_data_safety = MagicMock(return_value=MagicMock(
            backup_ready=True, last_snapshot_age=None, integrity_warnings=[],
            persistence_areas=[], total_persistence_areas=0, persisted_areas=0,
            session_only_areas=0, engine_errors=[],
        ))
        workspace.get_connected_data = MagicMock(return_value=MagicMock(
            summary=None, cross_reference=None, top_connections=[], engine_errors=[],
        ))
        workspace.get_inbox = MagicMock(return_value=MagicMock(
            total_pending=0, collection_assistant_pending=0, batch_processing_pending=0,
            ai_grading_review=0, workflow_items=[], items=[], engine_errors=[],
        ))

        advisor = CollectorAdvisor(workspace)
        recs = advisor.recommend_priority_acquisitions()

        self.assertGreater(len(recs), 0)
        for rec in recs:
            self.assertGreaterEqual(len(rec.evidence), 2,
                f"Recommendation {rec.recommendation_id} should have >=2 evidence even without cross-panel data")

    # ------------------------------------------------------------------
    # Graceful degradation tests
    # ------------------------------------------------------------------

    def test_workspace_panel_failure_graceful(self):
        """If a workspace panel fails, the advisor continues with other panels."""
        workspace = MagicMock()
        workspace.get_want_list = MagicMock(side_effect=Exception("want_list engine failed"))
        workspace.get_opportunities = MagicMock(side_effect=Exception("opportunities engine failed"))
        workspace.get_collection_summary = MagicMock(return_value=MagicMock(
            total_items=100, total_countries=5, total_denominations=10, total_years=50,
            grade_coverage=None, series_completion=[], recent_additions=0,
            quality_score=None, integrity_score=None, engine_errors=[],
        ))
        workspace.get_dashboard = MagicMock(return_value=MagicMock(
            health_score=None, quality_score=None, integrity_score=None,
            top_priority=None, best_next_purchase=None, todays_tasks=[],
            recent_activity=[], data_safety_status=None, backup_ready=False,
            engine_errors=[],
        ))
        workspace.get_ai_queue = MagicMock(return_value=MagicMock(
            total_pending=0, collection_assistant_pending=0, batch_processing_pending=0,
            ai_grading_review=0, workflow_items=[], items=[], engine_errors=[],
        ))
        workspace.get_batch_queue = MagicMock(return_value=MagicMock(
            total_pending=0, collection_assistant_pending=0, batch_processing_pending=0,
            ai_grading_review=0, workflow_items=[], items=[], engine_errors=[],
        ))
        workspace.get_photo_vault = MagicMock(return_value=MagicMock(
            total_collection_items=0, items_with_photos=0, items_without_photos=0,
            coverage_percentage=0.0, certified_items=0, certified_with_photos=0,
            missing_photo_count=0, duplicate_photo_count=0, recommended_actions=[],
            engine_errors=[],
        ))
        workspace.get_workflow_status = MagicMock(return_value=MagicMock(
            active_workflows=[], todays_tasks=[], pending_reviews=0,
            next_actions=[], workflow_health=None, engine_errors=[],
        ))
        workspace.get_data_safety = MagicMock(return_value=MagicMock(
            backup_ready=True, last_snapshot_age=None, integrity_warnings=[],
            persistence_areas=[], total_persistence_areas=0, persisted_areas=0,
            session_only_areas=0, engine_errors=[],
        ))
        workspace.get_connected_data = MagicMock(return_value=MagicMock(
            summary=None, cross_reference=None, top_connections=[], engine_errors=[],
        ))
        workspace.get_inbox = MagicMock(return_value=MagicMock(
            total_pending=0, collection_assistant_pending=0, batch_processing_pending=0,
            ai_grading_review=0, workflow_items=[], items=[], engine_errors=[],
        ))

        advisor = CollectorAdvisor(workspace)
        report = advisor.generate_advisory_report()

        # Should still produce a report without crashing
        self.assertIsInstance(report, AdvisorReport)
        self.assertIsNotNone(report.summary)

        # Should have recommendations from the working panel (collection_summary → duplicate disposal)
        dup_recs = [r for r in report.recommendations if r.recommendation_type == RecommendationCategory.DISPOSE_DUPLICATE]
        self.assertGreaterEqual(len(dup_recs), 1, "Should have duplicate disposal recommendation from working panel")

        # Every recommendation must have evidence
        for rec in report.recommendations:
            self.assertGreater(len(rec.evidence), 0, f"Missing evidence: {rec.recommendation_id}")

        # Should not crash even though want_list and opportunities failed
        self.assertIn("Total recommendations", report.summary)

    # ------------------------------------------------------------------
    # Summary and opportunities extraction tests
    # ------------------------------------------------------------------

    def test_build_summary(self):
        """Summary includes recommendation counts and next best action."""
        evidence = [RecommendationReason("priority", "reason", "engine")]
        recs = [
            CollectorRecommendation("rec_1", RecommendationCategory.PRIORITY_ACQUISITION, "Buy A", "desc", evidence, priority="HIGH"),
            CollectorRecommendation("rec_2", RecommendationCategory.UPGRADE, "Upgrade B", "desc", evidence, priority="MEDIUM"),
        ]
        workspace = self._mock_workspace()
        advisor = CollectorAdvisor(workspace)
        summary = advisor._build_summary(recs, recs[0])

        self.assertIn("Total recommendations: 2", summary)
        self.assertIn("Next Best Action: Buy A", summary)
        self.assertIn("PRIORITY_ACQUISITION: 1 recommendation(s)", summary)
        self.assertIn("UPGRADE: 1 recommendation(s)", summary)

    def test_extract_opportunities(self):
        """Opportunities extraction filters acquisition and upgrade recommendations."""
        evidence = [RecommendationReason("priority", "reason", "engine")]
        recs = [
            CollectorRecommendation("rec_1", RecommendationCategory.PRIORITY_ACQUISITION, "Buy A", "desc", evidence, priority="HIGH"),
            CollectorRecommendation("rec_2", RecommendationCategory.UPGRADE, "Upgrade B", "desc", evidence, priority="MEDIUM"),
            CollectorRecommendation("rec_3", RecommendationCategory.BUDGET_ALLOCATE, "Budget C", "desc", evidence, priority="LOW"),
        ]
        workspace = self._mock_workspace()
        advisor = CollectorAdvisor(workspace)
        ops = advisor._extract_opportunities(recs)

        self.assertEqual(len(ops), 2)
        self.assertIn("Buy A", ops[0])
        self.assertIn("Upgrade B", ops[1])


# ---------------------------------------------------------------------------
# Integration-style tests (minimal — use real workspace if possible)
# ---------------------------------------------------------------------------

class TestCollectorAdvisorIntegration(unittest.TestCase):
    """Light integration tests with a real CollectorWorkspace."""

    def test_with_real_workspace_empty(self):
        """Advisor works with a real empty CollectorWorkspace."""
        try:
            from collector_workspace import CollectorWorkspace
        except ImportError:
            self.skipTest("collector_workspace not available")

        workspace = CollectorWorkspace([])
        advisor = CollectorAdvisor(workspace)
        report = advisor.generate_advisory_report()

        self.assertIsInstance(report, AdvisorReport)
        # Empty workspace should still produce a valid report
        self.assertIsNotNone(report.summary)

    def test_with_real_workspace_small_collection(self):
        """Advisor works with a real workspace with minimal collection items."""
        try:
            from collector_workspace import CollectorWorkspace
        except ImportError:
            self.skipTest("collector_workspace not available")

        # Minimal collection items
        items = [
            {"country": "Canada", "denomination": "5 cents", "year": "1910", "grade": "VG8"},
            {"country": "Newfoundland", "denomination": "10 cents", "year": "1908", "grade": "F12"},
        ]
        workspace = CollectorWorkspace(items)
        advisor = CollectorAdvisor(workspace)
        report = advisor.generate_advisory_report()

        self.assertIsInstance(report, AdvisorReport)
        # Every recommendation has evidence
        for rec in report.recommendations:
            self.assertGreater(len(rec.evidence), 0, f"Missing evidence: {rec.recommendation_id}")

    def test_determinism_with_real_workspace(self):
        """Same workspace state produces identical outputs."""
        try:
            from collector_workspace import CollectorWorkspace
        except ImportError:
            self.skipTest("collector_workspace not available")

        items = [
            {"country": "Canada", "denomination": "Large Cent", "year": "1859", "grade": "VG8"},
        ]
        workspace = CollectorWorkspace(items)

        advisor1 = CollectorAdvisor(workspace)
        report1 = advisor1.generate_advisory_report()

        advisor2 = CollectorAdvisor(workspace)
        report2 = advisor2.generate_advisory_report()

        ids1 = [r.recommendation_id for r in report1.recommendations]
        ids2 = [r.recommendation_id for r in report2.recommendations]
        self.assertEqual(ids1, ids2)

class TestCollectorWorkspaceAdvisorIntegration(unittest.TestCase):
    """Integration tests for CollectorWorkspace.get_advisor()."""

    def test_workspace_get_advisor_empty_collection(self):
        """Workspace with empty collection returns valid AdvisorReport."""
        try:
            from collector_workspace import CollectorWorkspace
        except ImportError:
            self.skipTest("collector_workspace not available")

        workspace = CollectorWorkspace([])
        report = workspace.get_advisor()

        from collector_advisor import AdvisorReport
        self.assertIsInstance(report, AdvisorReport)
        self.assertIsNotNone(report.summary)
        # Empty workspace may still produce recommendations from panel heuristics
        # Every recommendation must have evidence
        for rec in report.recommendations:
            self.assertGreater(len(rec.evidence), 0, f"Missing evidence: {rec.recommendation_id}")

    def test_workspace_get_advisor_cached(self):
        """Second call returns cached result (same object)."""
        try:
            from collector_workspace import CollectorWorkspace
        except ImportError:
            self.skipTest("collector_workspace not available")

        workspace = CollectorWorkspace([])
        report1 = workspace.get_advisor()
        report2 = workspace.get_advisor()

        self.assertIs(report1, report2)

    def test_workspace_get_advisor_with_collection(self):
        """Workspace with items produces recommendations with evidence."""
        try:
            from collector_workspace import CollectorWorkspace
        except ImportError:
            self.skipTest("collector_workspace not available")

        items = [
            {"country": "Canada", "denomination": "Large Cent", "year": "1859", "grade": "VG8"},
            {"country": "Newfoundland", "denomination": "5 cents", "year": "1910", "grade": "F12"},
            {"country": "Canada", "denomination": "5 cents", "year": "1910", "grade": "VG8"},
        ]
        workspace = CollectorWorkspace(items)
        report = workspace.get_advisor()

        from collector_advisor import AdvisorReport
        self.assertIsInstance(report, AdvisorReport)

        # Every recommendation has evidence
        for rec in report.recommendations:
            self.assertGreater(len(rec.evidence), 0, f"Missing evidence: {rec.recommendation_id}")

    def test_workspace_refresh_clears_advisor_cache(self):
        """refresh() clears advisor cache so next call regenerates."""
        try:
            from collector_workspace import CollectorWorkspace
        except ImportError:
            self.skipTest("collector_workspace not available")

        workspace = CollectorWorkspace([])
        report1 = workspace.get_advisor()
        workspace.refresh()
        report2 = workspace.get_advisor()

        self.assertIsNot(report1, report2)

    def test_workspace_advisor_consumes_only_dtos(self):
        """Advisor does not import any engine modules directly."""
        import collector_advisor as ca_module
        import inspect

        source = inspect.getsource(ca_module.CollectorAdvisor)
        # Should not contain direct imports of engine modules
        forbidden = ["collection_intelligence", "smart_shopping", "ai_grading",
                     "opportunity_engine", "upgrade_advisor"]
        for name in forbidden:
            self.assertNotIn(f"import {name}", source,
                             f"Advisor should not import {name} directly")
            self.assertNotIn(f"from {name}", source,
                             f"Advisor should not import {name} directly")


if __name__ == "__main__":
    unittest.main()
