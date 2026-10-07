"""Tests for acquisition impact simulation."""

import unittest
from dataclasses import replace
from unittest.mock import patch

from acquisition_impact import AcquisitionImpactEngine, AcquisitionImpactReport
from acquisition_workflow import AcquisitionWorkflow
from coin_collection import CoinItem
from collection_dashboard import CollectionDashboard
from focused_collection_intelligence import CandidateItem, CollectionIntelligenceResult, ExistingMatch, MatchStatus
from legacy_portfolio_importer import LegacyWantListIntent
from listing_analyzer import ListingAnalyzer, ListingCandidate


def make_item(item_id, country, denomination, year, grade, **overrides):
    data = {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": grade,
        "notes": "",
        "date_added": "2026-06-16",
    }
    data.update(overrides)
    return CoinItem(**data)


def make_intent(target_coin, priority_score=75):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id=f"want_{target_coin}",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Impact test target",
        status="Active",
        priority_score=priority_score,
    )


class TestAcquisitionImpactEngine(unittest.TestCase):
    def test_triplet_duplicate_impact_unavailable(self):
        items = [make_item("1", "Canada", "1 cent", "1967", "VF-30")]
        candidate = CandidateItem("Canada", "1 cent", "1967", grade="VF-30", asking_price=5)

        report = AcquisitionImpactEngine(items).evaluate(candidate)

        self.assertIsInstance(report, AcquisitionImpactReport)
        self.assertIsNone(report.impact_score)
        self.assertIsNone(report.collection_impact)
        self.assertIsNone(report.quality_delta)

    def test_grade_difference_does_not_resolve_upgrade_impact(self):
        items = [make_item("1", "Canada", "10 cents", "1911", "VF-20")]
        candidate = CandidateItem("Canada", "10 cents", "1911", grade="EF-40", certifier="PCGS", asking_price=80)

        report = AcquisitionImpactEngine(items).evaluate(candidate)

        self.assertIsNone(report.impact_score)
        self.assertIsNone(report.upgrade_impact)
        self.assertNotIn("Upgrade candidate", report.recommendation_reasoning)

    def test_want_list_target_impact(self):
        items = [make_item("1", "Canada", "dollar", "1934", "VF-20")]
        intents = [make_intent("Canada 1935 silver dollar")]
        candidate = CandidateItem("Canada", "dollar", "1935", grade="EF-40", certifier="PCGS", asking_price=120)

        report = AcquisitionImpactEngine(items, intents).evaluate(candidate)

        self.assertIsNone(report.want_list_completed_delta)
        self.assertIsNone(report.want_list_impact)
        self.assertTrue(any("WANT_LIST" in reason for reason in report.recommendation_reasoning))

    def test_unresolved_gap_completion_unavailable(self):
        items = [
            make_item("1", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("2", "Newfoundland", "50 cents", "1902", "VF-20"),
        ]
        candidate = CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", certifier="PCGS", asking_price=80)

        report = AcquisitionImpactEngine(items).evaluate(candidate)

        self.assertIsNone(report.completion_delta)
        self.assertIsNone(report.completion_after)
        self.assertIsNone(report.collection_impact)

    def test_priority_target_does_not_supply_impact_proof(self):
        items = [
            make_item("1", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("2", "Newfoundland", "50 cents", "1902", "VF-20"),
        ]
        intents = [make_intent("Newfoundland 50 cents 1901", priority_score=90)]
        candidate = CandidateItem("Newfoundland", "50 cents", "1901", grade="EF-40", certifier="PCGS", asking_price=150)

        report = AcquisitionImpactEngine(items, intents).evaluate(candidate)

        self.assertIsNone(report.impact_score)
        self.assertIsNone(report.collection_impact)

    def test_low_interest_coin_impact_unavailable(self):
        candidate = CandidateItem("Argentina", "1 cent", "1975", grade="VF-20", asking_price=1)

        report = AcquisitionImpactEngine([], []).evaluate(candidate)

        self.assertIsNone(report.impact_score)
        self.assertIsNone(report.collection_impact)
        self.assertNotIn("No measurable collection improvement detected", report.recommendation_reasoning)

    def test_quality_score_delta(self):
        items = [
            make_item("1", "Newfoundland", "20 cents", "1900", "VF-20"),
            make_item("2", "Newfoundland", "20 cents", "1902", "VF-20"),
        ]
        candidate = CandidateItem("Newfoundland", "20 cents", "1901", grade="EF-40", certifier="PCGS", asking_price=90)

        report = AcquisitionImpactEngine(items).evaluate(candidate)

        self.assertIsNone(report.quality_after)
        self.assertIsNone(report.quality_delta)

    def test_dashboard_integration(self):
        items = [
            make_item("1", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("2", "Newfoundland", "50 cents", "1902", "VF-20"),
        ]
        data = CollectionDashboard(items, [make_intent("Newfoundland 50 cents 1901")]).generate_dashboard()

        self.assertTrue(data.top_potential_collection_improvements)
        self.assertTrue(any("Acquire" in item.title or "Complete" in item.title for item in data.top_potential_collection_improvements))

    def test_listing_analyzer_integration(self):
        items = [
            make_item("1", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("2", "Newfoundland", "50 cents", "1902", "VF-20"),
        ]
        analyzer = ListingAnalyzer(items, [make_intent("Newfoundland 50 cents 1901")])

        result = analyzer.analyze(ListingCandidate("1901 Newfoundland 50 cents EF40 PCGS", price=100))

        self.assertIsNone(result.acquisition_impact_score)
        self.assertIsNone(result.completion_impact)
        self.assertTrue(result.recommendation_reasoning)
        self.assertIsNotNone(result.acquisition_impact_report)


class TestUnresolvedAcquisitionImpact(unittest.TestCase):
    def setUp(self):
        self.items = [make_item("holding-1", "Canada", "10 cents", "1911", "VF-20")]
        self.candidate = CandidateItem("Canada", "10 cents", "1911", grade="EF-40", asking_price=80)
        self.engine = AcquisitionImpactEngine(self.items)
        self.decision = AcquisitionWorkflow(self.items).evaluate(self.candidate)

    def legacy_upgrade(self, holding_id="holding-1"):
        return CollectionIntelligenceResult(
            match_status=MatchStatus.BETTER_GRADE_UPGRADE,
            best_existing_match=ExistingMatch(holding_id, "Canada", "10 cents", "1911", "VF-20",
                                              notes="Possible upgrade", match_score=95),
            grade_comparison="BETTER", collection_impact="UPGRADE", recommendation="BUY",
            confidence_score=95,
        )

    def test_review_does_not_simulate_replacement(self):
        decision = replace(self.decision, intelligence_result=self.legacy_upgrade())
        self.assertIsNone(self.engine._simulate_collection(self.candidate, decision))
        self.assertEqual([item.id for item in self.items], ["holding-1"])

    def test_review_does_not_simulate_addition(self):
        self.assertIsNone(self.engine._simulate_collection(self.candidate, self.decision))

    def test_review_has_no_quality_or_completion_delta(self):
        report = self.engine.evaluate(self.candidate)
        for name in ("quality_delta", "quality_after", "completion_delta", "completion_after",
                     "quality_after_report", "series_priority_delta", "want_list_completed_delta"):
            with self.subTest(field=name):
                self.assertIsNone(getattr(report, name))

    def test_review_has_no_impact_score_or_positive_band(self):
        report = self.engine.evaluate(self.candidate)
        self.assertIsNone(report.impact_score)
        self.assertIsNone(report.collection_impact)
        self.assertIsNone(report.upgrade_impact)
        self.assertIsNone(report.want_list_impact)

    def test_missing_intelligence_does_not_simulate(self):
        decision = replace(self.decision, intelligence_result=None)
        self.assertIsNone(self.engine._simulate_collection(self.candidate, decision))
        with patch("acquisition_impact.AcquisitionWorkflow.evaluate", return_value=decision):
            report = self.engine.evaluate(self.candidate)
        self.assertIsNone(report.impact_score)
        self.assertIsNone(report.quality_after_report)

    def test_retained_legacy_upgrade_cannot_bypass_contained_advice(self):
        decision = replace(self.decision, intelligence_result=self.legacy_upgrade())
        with patch("acquisition_impact.AcquisitionWorkflow.evaluate", return_value=decision):
            report = self.engine.evaluate(self.candidate)
        self.assertEqual(report.acquisition_decision.recommendation, "REVIEW")
        self.assertIsNone(report.impact_score)
        self.assertIsNone(report.upgrade_impact)
        self.assertIsNone(report.quality_after_report)

    def test_historical_notes_and_weak_similarity_do_not_replace(self):
        candidate = replace(self.candidate, notes="upgrade holding-1 Canada dime", grade="")
        self.assertIsNone(self.engine._simulate_collection(candidate, self.decision))

    def test_absent_holding_id_does_not_authorize_removal(self):
        decision = replace(self.decision, intelligence_result=self.legacy_upgrade(""))
        self.assertIsNone(self.engine._simulate_collection(self.candidate, decision))

    def test_wrong_holding_id_does_not_authorize_removal(self):
        decision = replace(self.decision, intelligence_result=self.legacy_upgrade("lost-id"))
        self.assertIsNone(self.engine._simulate_collection(self.candidate, decision))

    def test_repeated_holding_id_does_not_authorize_removal(self):
        engine = AcquisitionImpactEngine(self.items + [replace(self.items[0], grade="F-12")])
        decision = replace(self.decision, intelligence_result=self.legacy_upgrade())
        self.assertIsNone(engine._simulate_collection(self.candidate, decision))

    def test_unresolved_relationship_with_holding_id_does_not_authorize_removal(self):
        self.assertEqual(self.decision.recommendation, "REVIEW")
        intelligence = replace(self.legacy_upgrade(), match_status=MatchStatus.NEEDS_REVIEW,
                               grade_comparison="UNRESOLVED", recommendation="REVIEW")
        decision = replace(self.decision, intelligence_result=intelligence)
        self.assertIsNone(self.engine._simulate_collection(self.candidate, decision))

    def test_type_series_and_variety_do_not_create_simulated_identity(self):
        candidate = replace(self.candidate, type_series="Canonical-looking title", variety="KM-42")
        self.assertIsNone(self.engine._simulate_collection(candidate, self.decision))

    def test_explicit_interest_and_price_survive_without_impact_proof(self):
        intents = [make_intent("Canada 1911 10 cents")]
        report = AcquisitionImpactEngine(self.items, intents).evaluate(self.candidate)
        self.assertEqual(report.acquisition_decision.asking_price, 80)
        self.assertEqual(report.acquisition_decision.want_list_status, "ON_WANT_LIST")
        self.assertIn("Explicit WANT_LIST Target", report.acquisition_decision.priority_reasons)
        self.assertIsNone(report.want_list_completed_delta)
        self.assertIsNone(report.impact_score)

    def test_unavailable_serialization_preserves_none(self):
        data = self.engine.evaluate(self.candidate).to_dict()
        for name in ("impact_score", "collection_impact", "quality_delta", "quality_after",
                     "completion_delta", "completion_after", "upgrade_impact", "want_list_impact",
                     "want_list_completed_delta", "series_priority_after", "series_priority_delta"):
            with self.subTest(field=name):
                self.assertIsNone(data[name])

    def test_evaluation_stops_before_simulation_or_collection_analysis(self):
        # A result hidden after an unsupported simulation is still fail-open.
        with patch.object(self.engine, "_simulate_collection", side_effect=AssertionError("simulation attempted")), \
             patch("acquisition_impact.CollectionQualityEngine", side_effect=AssertionError("quality attempted")), \
             patch("acquisition_impact.SeriesTracker", side_effect=AssertionError("series attempted")):
            report = self.engine.evaluate(self.candidate)
        self.assertIsNone(report.impact_score)


if __name__ == "__main__":
    unittest.main()
