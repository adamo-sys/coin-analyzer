"""Tests for deterministic acquisition workflow guidance."""

import unittest

from acquisition_workflow import AcquisitionWorkflow
from coin_collection import CoinItem
from focused_collection_intelligence import CandidateItem
from legacy_portfolio_importer import LegacyWantListIntent


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


def make_intent(target_coin, priority="High", target_grade="VF-20", budget=100.0):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id="legacy_want_list_2",
        target_coin=target_coin,
        priority=priority,
        target_grade=target_grade,
        budget=budget,
        why_wanted="Acquisition workflow test",
        status="Active",
        priority_score=75,
    )


class TestAcquisitionWorkflow(unittest.TestCase):
    """Verify acquisition recommendations stay deterministic and intelligence-driven."""

    def test_want_list_target_at_fair_price_is_buy(self):
        workflow = AcquisitionWorkflow([], [make_intent("Newfoundland 50 cents 1904")])

        decision = workflow.evaluate(CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1904",
            grade="VF-20",
            asking_price=125.0,
        ))

        self.assertEqual(decision.collection_intelligence_status, "WANT_LIST_MATCH")
        self.assertEqual(decision.recommendation, "BUY")
        self.assertEqual(decision.want_list_status, "ON_WANT_LIST")

    def test_want_list_target_overpriced_is_negotiate_or_watch(self):
        workflow = AcquisitionWorkflow([], [make_intent("Canada 1 cent 1920")])

        decision = workflow.evaluate(CandidateItem(
            country="Canada",
            denomination="1 cent",
            year="1920",
            grade="VF-20",
            asking_price=145.0,
            certifier="PCGS",
        ))

        self.assertIn(decision.recommendation, {"NEGOTIATE", "WATCH"})

    def test_better_grade_upgrade_at_fair_price_is_buy(self):
        workflow = AcquisitionWorkflow([
            make_item("1", "Canada", "10 cents", "1911", "VF-20")
        ])

        decision = workflow.evaluate(CandidateItem(
            country="Canada",
            denomination="dime",
            year="1911",
            grade="EF-40",
            certifier="PCGS",
            asking_price=90.0,
        ))

        self.assertEqual(decision.collection_intelligence_status, "BETTER_GRADE_UPGRADE")
        self.assertEqual(decision.upgrade_status, "UPGRADE")
        self.assertEqual(decision.recommendation, "BUY")

    def test_same_grade_duplicate_is_pass(self):
        workflow = AcquisitionWorkflow([
            make_item("1", "Canada", "1 cent", "1967", "VF-30")
        ])

        decision = workflow.evaluate(CandidateItem(
            country="Canada",
            denomination="1c",
            year="1967",
            grade="VF-30",
            asking_price=5.0,
        ))

        self.assertEqual(decision.recommendation, "PASS")

    def test_lower_grade_candidate_is_pass(self):
        workflow = AcquisitionWorkflow([
            make_item("1", "Canada", "1 cent", "1967", "VF-30")
        ])

        decision = workflow.evaluate(CandidateItem(
            country="Canada",
            denomination="1c",
            year="1967",
            grade="VG-8",
            asking_price=2.0,
        ))

        self.assertEqual(decision.upgrade_status, "DOWNGRADE")
        self.assertEqual(decision.recommendation, "PASS")

    def test_collection_gap_at_fair_price_is_buy_or_watch(self):
        workflow = AcquisitionWorkflow([
            make_item("1", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("2", "Newfoundland", "50 cents", "1902", "VF-20"),
        ])

        decision = workflow.evaluate(CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1901",
            grade="VF-20",
            asking_price=80.0,
            certifier="PCGS",
        ))

        self.assertEqual(decision.collection_intelligence_status, "COLLECTION_GAP")
        self.assertIn(decision.recommendation, {"BUY", "WATCH"})

    def test_random_world_base_metal_item_is_pass(self):
        workflow = AcquisitionWorkflow([])

        decision = workflow.evaluate(CandidateItem(
            country="Argentina",
            denomination="1 cent",
            year="1975",
            grade="VF-20",
            asking_price=1.0,
        ))

        self.assertEqual(decision.recommendation, "PASS")

    def test_ambiguous_variety_is_review(self):
        workflow = AcquisitionWorkflow([
            make_item("1", "Canada", "1 cent", "1859", "VG-8")
        ])

        decision = workflow.evaluate(CandidateItem(
            country="Canada",
            denomination="large cent",
            year="1859",
            variety="narrow 9",
            grade="VF-20",
            asking_price=75.0,
        ))

        self.assertEqual(decision.collection_intelligence_status, "NEEDS_REVIEW")
        self.assertEqual(decision.recommendation, "REVIEW")

    def test_raw_expensive_candidate_is_review_or_negotiate(self):
        workflow = AcquisitionWorkflow([], [make_intent("Newfoundland 50 cents 1904")])

        decision = workflow.evaluate(CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1904",
            grade="VF-20",
            asking_price=260.0,
            notes="raw coin",
        ))

        self.assertIn(decision.recommendation, {"REVIEW", "NEGOTIATE"})
        self.assertIn("Raw expensive candidate requires manual review", decision.warning_flags)

    def test_missing_asking_price_is_watch_or_review(self):
        workflow = AcquisitionWorkflow([], [make_intent("Canada 1 cent 1920")])

        decision = workflow.evaluate(CandidateItem(
            country="Canada",
            denomination="1 cent",
            year="1920",
            grade="VF-20",
        ))

        self.assertIn(decision.recommendation, {"WATCH", "REVIEW"})
        self.assertIn("Missing asking price", decision.warning_flags)

    def test_canadian_silver_priority_case(self):
        workflow = AcquisitionWorkflow([], [make_intent("Canada silver dollar 1935")])

        decision = workflow.evaluate(CandidateItem(
            country="Canada",
            denomination="silver dollar",
            year="1935",
            grade="EF-40",
            asking_price=120.0,
            certifier="PCGS",
        ))

        self.assertEqual(decision.recommendation, "BUY")
        self.assertIn("High-Priority Series: Canadian silver", decision.priority_reasons)

    def test_newfoundland_priority_case(self):
        workflow = AcquisitionWorkflow([], [make_intent("Newfoundland 50 cents 1904")])

        decision = workflow.evaluate(CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1904",
            grade="VF-20",
            asking_price=125.0,
            certifier="PCGS",
        ))

        self.assertEqual(decision.recommendation, "BUY")
        self.assertIn("High-Priority Series: Newfoundland", decision.priority_reasons)

    def test_1859_large_cent_priority_case(self):
        workflow = AcquisitionWorkflow([], [make_intent("Canada 1859 large cent")])

        decision = workflow.evaluate(CandidateItem(
            country="Canada",
            denomination="large cent",
            year="1859",
            grade="VF-20",
            asking_price=125.0,
            certifier="PCGS",
        ))

        self.assertEqual(decision.recommendation, "BUY")
        self.assertIn("High-Priority Series: 1859 Canadian Large Cent", decision.priority_reasons)


if __name__ == "__main__":
    unittest.main()
