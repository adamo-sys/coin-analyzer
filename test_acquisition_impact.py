"""Tests for acquisition impact simulation."""

import unittest

from acquisition_impact import AcquisitionImpactEngine, AcquisitionImpactReport
from coin_collection import CoinItem
from collection_dashboard import CollectionDashboard
from focused_collection_intelligence import CandidateItem
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
    def test_duplicate_candidate_low_impact(self):
        items = [make_item("1", "Canada", "1 cent", "1967", "VF-30")]
        candidate = CandidateItem("Canada", "1 cent", "1967", grade="VF-30", asking_price=5)

        report = AcquisitionImpactEngine(items).evaluate(candidate)

        self.assertIsInstance(report, AcquisitionImpactReport)
        self.assertLessEqual(report.impact_score, 10)
        self.assertEqual(report.collection_impact, "LOW")
        self.assertEqual(report.quality_delta, 0)

    def test_upgrade_candidate_has_upgrade_impact(self):
        items = [make_item("1", "Canada", "10 cents", "1911", "VF-20")]
        candidate = CandidateItem("Canada", "10 cents", "1911", grade="EF-40", certifier="PCGS", asking_price=80)

        report = AcquisitionImpactEngine(items).evaluate(candidate)

        self.assertGreater(report.impact_score, 30)
        self.assertIn(report.upgrade_impact, {"UPGRADE_CANDIDATE", "RESOLVES_UPGRADE_OPPORTUNITY"})
        self.assertTrue(any("Upgrade" in reason for reason in report.recommendation_reasoning))

    def test_want_list_target_impact(self):
        items = [make_item("1", "Canada", "dollar", "1934", "VF-20")]
        intents = [make_intent("Canada 1935 silver dollar")]
        candidate = CandidateItem("Canada", "dollar", "1935", grade="EF-40", certifier="PCGS", asking_price=120)

        report = AcquisitionImpactEngine(items, intents).evaluate(candidate)

        self.assertGreaterEqual(report.want_list_completed_delta, 1)
        self.assertEqual(report.want_list_impact, "COMPLETES_WANT_LIST_TARGET")
        self.assertTrue(any("WANT_LIST" in reason for reason in report.recommendation_reasoning))

    def test_collection_gap_filler_completion_delta(self):
        items = [
            make_item("1", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("2", "Newfoundland", "50 cents", "1902", "VF-20"),
        ]
        candidate = CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", certifier="PCGS", asking_price=80)

        report = AcquisitionImpactEngine(items).evaluate(candidate)

        self.assertGreater(report.completion_delta, 0)
        self.assertEqual(report.completion_after, 100.0)
        self.assertIn(report.collection_impact, {"MEDIUM", "HIGH", "MAJOR"})

    def test_major_newfoundland_target(self):
        items = [
            make_item("1", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("2", "Newfoundland", "50 cents", "1902", "VF-20"),
        ]
        intents = [make_intent("Newfoundland 50 cents 1901", priority_score=90)]
        candidate = CandidateItem("Newfoundland", "50 cents", "1901", grade="EF-40", certifier="PCGS", asking_price=150)

        report = AcquisitionImpactEngine(items, intents).evaluate(candidate)

        self.assertGreaterEqual(report.impact_score, 70)
        self.assertIn(report.collection_impact, {"HIGH", "MAJOR"})

    def test_random_world_base_metal_coin_low_impact(self):
        candidate = CandidateItem("Argentina", "1 cent", "1975", grade="VF-20", asking_price=1)

        report = AcquisitionImpactEngine([], []).evaluate(candidate)

        self.assertLessEqual(report.impact_score, 5)
        self.assertEqual(report.collection_impact, "LOW")
        self.assertIn("No measurable collection improvement detected", report.recommendation_reasoning)

    def test_quality_score_delta(self):
        items = [
            make_item("1", "Newfoundland", "20 cents", "1900", "VF-20"),
            make_item("2", "Newfoundland", "20 cents", "1902", "VF-20"),
        ]
        candidate = CandidateItem("Newfoundland", "20 cents", "1901", grade="EF-40", certifier="PCGS", asking_price=90)

        report = AcquisitionImpactEngine(items).evaluate(candidate)

        self.assertNotEqual(report.quality_after, report.quality_before)
        self.assertEqual(report.quality_delta, report.quality_after - report.quality_before)

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

        self.assertGreater(result.acquisition_impact_score, 0)
        self.assertGreater(result.completion_impact, 0)
        self.assertTrue(result.recommendation_reasoning)
        self.assertIsNotNone(result.acquisition_impact_report)


if __name__ == "__main__":
    unittest.main()
