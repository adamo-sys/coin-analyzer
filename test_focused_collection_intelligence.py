"""Tests for focused collection intelligence candidate classification."""

import unittest

from coin_collection import CoinItem
from focused_collection_intelligence import (
    CandidateItem,
    FocusedCollectionIntelligenceEngine,
    MatchStatus,
)
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


class TestFocusedCollectionIntelligenceEngine(unittest.TestCase):
    """Verify deterministic candidate classification."""

    def test_incomplete_identity_never_creates_consequential_advice(self):
        cases = [
            ("higher grade", [make_item("1", "Canada", "10 cents", "1911", "VF-20")], "EF-40", ""),
            ("equal grade", [make_item("1", "Canada", "10 cents", "1911", "VF-20")], "VF-20", ""),
            ("unknown holding grade", [make_item("1", "Canada", "10 cents", "1911", "")], "VF-20", ""),
            ("missing holding year", [make_item("1", "Canada", "10 cents", "", "VF-20")], "VF-20", ""),
            ("historical variety", [make_item("1", "Canada", "10 cents", "1911", "VF-20", notes="Former attribution: narrow 9")], "EF-40", "narrow 9"),
            ("empty collection", [], "VF-20", ""),
            ("catalogue identifiers", [make_item("1", "Canada", "10 cents", "1911", "VF-20", reference="R", numista_n="123")], "EF-40", "R"),
        ]
        for label, items, grade, variety in cases:
            with self.subTest(case=label):
                candidate = CandidateItem("Canada", "10 cents", "1911", grade=grade, variety=variety)
                engine = FocusedCollectionIntelligenceEngine(items)
                result = engine.analyze_candidate(candidate)
                self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
                self.assertEqual(result.recommendation, "REVIEW")
                self.assertIsNone(result.best_existing_match)
                self.assertIsNone(result.confidence_score)
                self.assertIsNone(engine.find_exact_items(candidate))
                self.assertNotIn("Collection Gap", result.priority_reasons)
                self.assertNotIn("Upgrade Candidate", result.priority_reasons)
                self.assertNotIn("Duplicate Risk", result.priority_reasons)

    def test_unknown_grade_has_no_numeric_score(self):
        engine = FocusedCollectionIntelligenceEngine([])
        for grade in ["", "unknown", "MS+++", "ungraded"]:
            with self.subTest(grade=grade):
                self.assertIsNone(engine._grade_score(grade))

    def test_newfoundland_interest_without_upgrade(self):
        engine = FocusedCollectionIntelligenceEngine([
            make_item("1", "Newfoundland", "50 cents", "1909", "F-12")
        ])

        result = engine.analyze_candidate(CandidateItem(
            country="NFLD",
            denomination="50c",
            year="1909",
            grade="VF-20",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIn("High-Priority Series: Newfoundland", result.priority_reasons)

    def test_equal_grade_is_unresolved(self):
        engine = FocusedCollectionIntelligenceEngine([
            make_item("1", "Canada", "1 cent", "1967", "VF-30")
        ])

        result = engine.analyze_candidate(CandidateItem(
            country="Canada",
            denomination="1c",
            year="1967",
            grade="VF-30",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.recommendation, "REVIEW")

    def test_missing_grade_does_not_establish_ownership(self):
        engine = FocusedCollectionIntelligenceEngine([
            make_item("1", "Canada", "1 cent", "1967", "VF-30")
        ])

        result = engine.analyze_candidate(CandidateItem(
            country="Canada",
            denomination="1c",
            year="1967",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIn("Missing grade", result.warning_flags)

    def test_lower_grade_is_unresolved(self):
        engine = FocusedCollectionIntelligenceEngine([
            make_item("1", "Canada", "1 cent", "1967", "VF-30")
        ])

        result = engine.analyze_candidate(CandidateItem(
            country="Canada",
            denomination="penny",
            year="1967",
            grade="VG-8",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.recommendation, "REVIEW")

    def test_silver_interest_without_upgrade(self):
        engine = FocusedCollectionIntelligenceEngine([
            make_item("1", "Canada", "dollar", "1935", "VF-20")
        ])

        result = engine.analyze_candidate(CandidateItem(
            country="Canadian",
            denomination="silver dollar",
            year="1935",
            grade="EF-40",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertIn("High-Priority Series: Canadian silver", result.priority_reasons)

    def test_1859_large_cent_upgrade(self):
        engine = FocusedCollectionIntelligenceEngine([
            make_item("1", "Canada", "1 cent", "1859", "VG-8")
        ])

        result = engine.analyze_candidate(CandidateItem(
            country="Canada",
            denomination="large cent",
            year="1859",
            variety="narrow 9",
            grade="VF-20",
            notes="type-only candidate",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIn("equivalence unresolved", " ".join(result.warning_flags))

    def test_1859_large_cent_upgrade_with_variety_match(self):
        engine = FocusedCollectionIntelligenceEngine([
            make_item("1", "Canada", "1 cent", "1859", "VG-8", reference="Narrow 9")
        ])

        result = engine.analyze_candidate(CandidateItem(
            country="Canada",
            denomination="large cent",
            year="1859",
            variety="narrow 9",
            grade="VF-20",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertIn("High-Priority Series: 1859 Canadian Large Cent", result.priority_reasons)

    def test_explicit_want_list_interaction(self):
        intent = LegacyWantListIntent(
            sheet_name="WANT_LIST",
            row_number=2,
            legacy_id="w1",
            target_coin="Newfoundland 50 cents 1901",
            priority="High",
            target_grade="VF-20",
            budget=150.0,
            why_wanted="Gap target",
            status="Active",
            priority_score=75,
        )
        engine = FocusedCollectionIntelligenceEngine([], [intent])

        result = engine.analyze_candidate(CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1901",
            grade="VF-20",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertEqual(result.want_list_status, "ON_WANT_LIST")
        self.assertIn("Explicit WANT_LIST Target", result.priority_reasons)

    def test_want_list_interest_does_not_establish_duplicate(self):
        intent = LegacyWantListIntent(
            sheet_name="WANT_LIST",
            row_number=2,
            legacy_id="w1",
            target_coin="Canada 1 cent 1967",
            priority="High",
            target_grade="VF-30",
            budget=10.0,
            why_wanted="Already tracked target",
            status="Active",
            priority_score=75,
        )
        engine = FocusedCollectionIntelligenceEngine([
            make_item("1", "Canada", "1 cent", "1967", "VF-30")
        ], [intent])

        result = engine.analyze_candidate(CandidateItem(
            country="Canada",
            denomination="1c",
            year="1967",
            grade="VF-30",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.want_list_status, "ON_WANT_LIST")
        self.assertIn("Explicit WANT_LIST Target", result.priority_reasons)
        self.assertNotIn("Duplicate Risk", result.priority_reasons)

    def test_want_list_interest_does_not_establish_upgrade(self):
        intent = LegacyWantListIntent(
            sheet_name="WANT_LIST",
            row_number=2,
            legacy_id="w1",
            target_coin="Canada 10 cents 1911",
            priority="High",
            target_grade="EF-40",
            budget=50.0,
            why_wanted="Upgrade target",
            status="Active",
            priority_score=75,
        )
        engine = FocusedCollectionIntelligenceEngine([
            make_item("1", "Canada", "10 cents", "1911", "VF-20")
        ], [intent])

        result = engine.analyze_candidate(CandidateItem(
            country="Canada",
            denomination="dime",
            year="1911",
            grade="EF-40",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.want_list_status, "ON_WANT_LIST")
        self.assertNotIn("Upgrade Candidate", result.priority_reasons)

    def test_missing_date_does_not_establish_gap(self):
        unrelated_intent = LegacyWantListIntent(
            sheet_name="WANT_LIST",
            row_number=2,
            legacy_id="w1",
            target_coin="Canada 1 cent 1920",
            priority="Medium",
            target_grade="VF-20",
            budget=10.0,
            why_wanted="Different gap",
            status="Active",
            priority_score=50,
        )
        engine = FocusedCollectionIntelligenceEngine([
            make_item("1", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("2", "Newfoundland", "50 cents", "1902", "VF-20"),
        ], [unrelated_intent])

        result = engine.analyze_candidate(CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1901",
            grade="VF-20",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.want_list_status, "NOT_ON_WANT_LIST")
        self.assertNotIn("Collection Gap", result.priority_reasons)

    def test_missing_want_list_source_is_graceful(self):
        engine = FocusedCollectionIntelligenceEngine([])

        result = engine.analyze_candidate(CandidateItem(
            country="Canada",
            denomination="1 cent",
            year="1920",
            grade="VF-20",
        ))

        self.assertEqual(result.want_list_status, "WANT_LIST_UNAVAILABLE")

    def test_newfoundland_want_list_target(self):
        intent = LegacyWantListIntent(
            sheet_name="WANT_LIST",
            row_number=2,
            legacy_id="w1",
            target_coin="Newfoundland 50 cents 1904",
            priority="High",
            target_grade="VF-20",
            budget=125.0,
            why_wanted="Newfoundland date run",
            status="Active",
            priority_score=75,
        )
        engine = FocusedCollectionIntelligenceEngine([], [intent])

        result = engine.analyze_candidate(CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1904",
            grade="VF-20",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertIn("High-Priority Series: Newfoundland", result.priority_reasons)

    def test_canadian_silver_want_list_target(self):
        intent = LegacyWantListIntent(
            sheet_name="WANT_LIST",
            row_number=2,
            legacy_id="w1",
            target_coin="Canada silver dollar 1935",
            priority="High",
            target_grade="EF-40",
            budget=100.0,
            why_wanted="Canadian silver",
            status="Active",
            priority_score=75,
        )
        engine = FocusedCollectionIntelligenceEngine([], [intent])

        result = engine.analyze_candidate(CandidateItem(
            country="Canada",
            denomination="silver dollar",
            year="1935",
            grade="EF-40",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertIn("High-Priority Series: Canadian silver", result.priority_reasons)

    def test_random_world_base_metal_non_upgrade(self):
        engine = FocusedCollectionIntelligenceEngine([])

        result = engine.analyze_candidate(CandidateItem(
            country="Argentina",
            denomination="1 cent",
            year="1975",
            grade="VF-20",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIn("Low-priority world base-metal candidate", result.priority_reasons)

    def test_ambiguous_candidate_needs_review(self):
        engine = FocusedCollectionIntelligenceEngine([
            make_item("1", "Canada", "1 cent", "1967", "VF-20")
        ])

        result = engine.analyze_candidate(CandidateItem(
            country="Canda",
            denomination="1 cent",
            year="1967",
            grade="EF-40",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIn("Owned issue equivalence unresolved: canonical candidate identity unavailable", result.warning_flags)

    def test_certification_does_not_authorize_replacement(self):
        engine = FocusedCollectionIntelligenceEngine([
            make_item("1", "Canada", "10 cents", "1911", "VF-20", notes="raw coin")
        ])

        result = engine.analyze_candidate(CandidateItem(
            country="Canada",
            denomination="dime",
            year="1911",
            grade="EF-40",
            certifier="PCGS",
            certification_number="12345678",
        ))

        self.assertEqual(result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertNotIn("Certified candidate may replace raw example", result.priority_reasons)


if __name__ == "__main__":
    unittest.main()
