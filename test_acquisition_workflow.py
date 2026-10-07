"""Tests for deterministic acquisition workflow guidance."""

import unittest
from unittest.mock import patch

from acquisition_workflow import AcquisitionWorkflow
from coin_collection import CoinItem
from focused_collection_intelligence import CandidateItem, CollectionIntelligenceResult, ExistingMatch, MatchStatus
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

    def test_want_list_interest_at_fair_price_still_requires_identity_review(self):
        workflow = AcquisitionWorkflow([], [make_intent("Newfoundland 50 cents 1904")])

        decision = workflow.evaluate(CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1904",
            grade="VF-20",
            asking_price=125.0,
        ))

        self.assertEqual(decision.collection_intelligence_status, "NEEDS_REVIEW")
        self.assertEqual(decision.recommendation, "REVIEW")
        self.assertIsNone(decision.max_rational_price)
        self.assertEqual(decision.want_list_status, "ON_WANT_LIST")

    def test_want_list_interest_does_not_establish_overpricing(self):
        workflow = AcquisitionWorkflow([], [make_intent("Canada 1 cent 1920")])

        decision = workflow.evaluate(CandidateItem(
            country="Canada",
            denomination="1 cent",
            year="1920",
            grade="VF-20",
            asking_price=145.0,
            certifier="PCGS",
        ))

        self.assertEqual(decision.recommendation, "REVIEW")
        self.assertIsNone(decision.max_rational_price)
        self.assertEqual(decision.asking_price, 145.0)
        self.assertEqual(decision.want_list_status, "ON_WANT_LIST")

    def test_higher_grade_without_issue_identity_requires_review(self):
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

        self.assertEqual(decision.collection_intelligence_status, "NEEDS_REVIEW")
        self.assertEqual(decision.upgrade_status, "UNRESOLVED")
        self.assertEqual(decision.recommendation, "REVIEW")
        self.assertIsNone(decision.max_rational_price)

    def test_equal_grade_without_issue_identity_requires_review(self):
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

        self.assertEqual(decision.recommendation, "REVIEW")
        self.assertEqual(decision.upgrade_status, "UNRESOLVED")
        self.assertIsNone(decision.max_rational_price)

    def test_lower_grade_without_issue_identity_requires_review(self):
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

        self.assertEqual(decision.upgrade_status, "UNRESOLVED")
        self.assertEqual(decision.recommendation, "REVIEW")
        self.assertIsNone(decision.max_rational_price)

    def test_absent_year_match_does_not_establish_collection_gap(self):
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

        self.assertEqual(decision.collection_intelligence_status, "NEEDS_REVIEW")
        self.assertEqual(decision.recommendation, "REVIEW")
        self.assertNotIn("Collection Gap", decision.priority_reasons)
        self.assertIsNone(decision.max_rational_price)

    def test_low_collector_interest_does_not_resolve_acquisition_suitability(self):
        workflow = AcquisitionWorkflow([])

        decision = workflow.evaluate(CandidateItem(
            country="Argentina",
            denomination="1 cent",
            year="1975",
            grade="VF-20",
            asking_price=1.0,
        ))

        self.assertEqual(decision.recommendation, "REVIEW")
        self.assertIsNone(decision.max_rational_price)
        self.assertIn("Low-priority world base-metal candidate", decision.priority_reasons)

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

    def test_raw_candidate_with_unavailable_value_requires_identity_review(self):
        workflow = AcquisitionWorkflow([], [make_intent("Newfoundland 50 cents 1904")])

        decision = workflow.evaluate(CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1904",
            grade="VF-20",
            asking_price=260.0,
            notes="raw coin",
        ))

        self.assertEqual(decision.recommendation, "REVIEW")
        self.assertIsNone(decision.max_rational_price)
        self.assertEqual(decision.asking_price, 260.0)
        self.assertTrue(any("issue equivalence unresolved" in warning for warning in decision.warning_flags))

    def test_missing_asking_price_remains_visible_during_identity_review(self):
        workflow = AcquisitionWorkflow([], [make_intent("Canada 1 cent 1920")])

        decision = workflow.evaluate(CandidateItem(
            country="Canada",
            denomination="1 cent",
            year="1920",
            grade="VF-20",
        ))

        self.assertEqual(decision.recommendation, "REVIEW")
        self.assertIsNone(decision.max_rational_price)
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

        self.assertEqual(decision.recommendation, "REVIEW")
        self.assertIsNone(decision.max_rational_price)
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

        self.assertEqual(decision.recommendation, "REVIEW")
        self.assertIsNone(decision.max_rational_price)
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

        self.assertEqual(decision.recommendation, "REVIEW")
        self.assertIsNone(decision.max_rational_price)
        self.assertIn("High-Priority Series: 1859 Canadian Large Cent", decision.priority_reasons)


class TestUnresolvedAcquisitionWorkflow(unittest.TestCase):
    """Unresolved identity cannot authorize a purchase, rejection, or price."""

    def test_retained_decisive_intelligence_cannot_outvote_unavailable_identity(self):
        for status, recommendation, confidence in (
            (MatchStatus.BETTER_GRADE_UPGRADE, "BUY", 95),
            (MatchStatus.SAME_GRADE_DUPLICATE, "PASS", 95),
            (MatchStatus.COLLECTION_GAP, "BUY", 95),
            (MatchStatus.BETTER_GRADE_UPGRADE, "BUY", None),
        ):
            with self.subTest(status=status, confidence=confidence):
                upstream = CollectionIntelligenceResult(
                    status, None, "UNAVAILABLE", "UNAVAILABLE", recommendation, confidence,
                    priority_reasons=["Collection Gap", "Upgrade Candidate", "Explicit WANT_LIST Target"],
                    want_list_status="ON_WANT_LIST",
                )
                workflow = AcquisitionWorkflow([])
                with patch.object(workflow.intelligence_engine, "analyze_candidate", return_value=upstream):
                    decision = workflow.evaluate(CandidateItem(asking_price=1))
                self.assert_unresolved_decision(decision)
                self.assertEqual(decision.asking_price, 1)
                self.assertIn("Explicit WANT_LIST Target", decision.priority_reasons)
                self.assertTrue(any("unresolved" in warning.lower() for warning in decision.warning_flags))

    def assert_unresolved_decision(self, decision):
        expected = {
            "collection_intelligence_status": "NEEDS_REVIEW",
            "owned_current_match_summary": "UNRESOLVED: owned issue equivalence unavailable",
            "upgrade_status": "UNRESOLVED",
            "recommendation": "REVIEW",
            "max_rational_price": None,
            "confidence_score": None,
        }
        payload = decision.to_dict()
        for key, value in expected.items():
            with self.subTest(field=key):
                self.assertEqual(payload[key], value)
        for unsupported in ("Collection Gap", "Upgrade Candidate", "Certified candidate may replace raw example"):
            with self.subTest(reason=unsupported):
                self.assertNotIn(unsupported, decision.priority_reasons)

    def test_missing_design_higher_grade_cannot_authorize_upgrade_buy_or_price(self):
        workflow = AcquisitionWorkflow([make_item("1", "Canada", "10 cents", "1911", "VF-20")])
        decision = workflow.evaluate(CandidateItem(
            country="Canada", denomination="dime", year="1911", grade="EF-40",
            certifier="PCGS", asking_price=90.0,
        ))
        self.assert_unresolved_decision(decision)

    def test_missing_design_equal_grade_cannot_authorize_duplicate_pass_or_zero_price(self):
        workflow = AcquisitionWorkflow([make_item("1", "Canada", "1 cent", "1967", "VF-30")])
        decision = workflow.evaluate(CandidateItem(
            country="Canada", denomination="1c", year="1967", grade="VF-30", asking_price=5.0,
        ))
        self.assert_unresolved_decision(decision)

    def test_missing_holding_year_cannot_authorize_gap_buy_or_newness(self):
        workflow = AcquisitionWorkflow([make_item("1", "Newfoundland", "50 cents", "", "VF-20")])
        decision = workflow.evaluate(CandidateItem(
            country="Newfoundland", denomination="50 cents", year="1901", grade="VF-20",
            asking_price=80.0, certifier="PCGS",
        ))
        self.assert_unresolved_decision(decision)
        self.assertIn("High-Priority Series: Newfoundland", decision.priority_reasons)

    def test_incomplete_candidate_empty_collection_does_not_assert_unowned(self):
        decision = AcquisitionWorkflow([]).evaluate(CandidateItem(country="Argentina", asking_price=1.0))
        self.assert_unresolved_decision(decision)
        self.assertNotEqual(decision.owned_current_match_summary, "No current owned match.")
        self.assertIn("Missing denomination", decision.warning_flags)
        self.assertIn("Missing year", decision.warning_flags)

    def test_explicit_interest_survives_without_authorizing_purchase_or_price(self):
        workflow = AcquisitionWorkflow([], [make_intent("Newfoundland 50 cents 1904")])
        decision = workflow.evaluate(CandidateItem(
            country="Newfoundland", denomination="50 cents", year="1904", grade="VF-20",
            asking_price=125.0, certifier="PCGS",
        ))
        self.assert_unresolved_decision(decision)
        self.assertEqual(decision.want_list_status, "ON_WANT_LIST")
        self.assertIn("Explicit WANT_LIST Target", decision.priority_reasons)
        self.assertIn("High-Priority Series: Newfoundland", decision.priority_reasons)
        self.assertEqual(decision.asking_price, 125.0)

    def test_upstream_review_overrides_legacy_status_scores_and_identity_reasons(self):
        # Inject boundary results to exercise mapping independently of today's
        # engine, which always emits NEEDS_REVIEW for legacy candidate identity.
        for status in MatchStatus:
            with self.subTest(upstream_status=status):
                upstream = CollectionIntelligenceResult(
                    match_status=status, best_existing_match=None,
                    grade_comparison="UNAVAILABLE", collection_impact="UNAVAILABLE",
                    recommendation="REVIEW", confidence_score=95,
                    priority_reasons=["Explicit WANT_LIST Target", "Collection Gap", "Upgrade Candidate",
                                      "Certified candidate may replace raw example"],
                    warning_flags=["Owned issue equivalence unresolved"], want_list_status="ON_WANT_LIST",
                )
                workflow = AcquisitionWorkflow([])
                with patch.object(workflow.intelligence_engine, "analyze_candidate", return_value=upstream):
                    decision = workflow.evaluate(CandidateItem(asking_price=1.0, certifier="PCGS"))
                self.assert_unresolved_decision(decision)
                self.assertIn("Explicit WANT_LIST Target", decision.priority_reasons)
                self.assertIn("Owned issue equivalence unresolved", decision.warning_flags)

    def test_needs_review_status_blocks_stale_buy_and_descriptive_holding(self):
        upstream = CollectionIntelligenceResult(
            match_status=MatchStatus.NEEDS_REVIEW,
            best_existing_match=ExistingMatch(
                item_id="synthetic-1", country="Canada", denomination="10 cents",
                year="1911", grade="VF-20", match_type="similarity",
            ),
            grade_comparison="UNAVAILABLE", collection_impact="UNAVAILABLE",
            recommendation="BUY", confidence_score=None,
        )
        workflow = AcquisitionWorkflow([])
        with patch.object(workflow.intelligence_engine, "analyze_candidate", return_value=upstream):
            decision = workflow.evaluate(CandidateItem(asking_price=1.0))
        self.assert_unresolved_decision(decision)


if __name__ == "__main__":
    unittest.main()
