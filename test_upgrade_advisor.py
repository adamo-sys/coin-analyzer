"""Upgrade containment regressions using sanitized synthetic holdings."""
import csv
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from focused_collection_intelligence import CollectionIntelligenceResult, ExistingMatch, MatchStatus
from upgrade_advisor import UpgradeAdvisor


@dataclass
class MockCoinItem:
    id: str
    country: str
    denomination: str
    year: str
    grade: str
    estimate_cad: float = 0.0
    notes: str = ""


class TestUpgradeAdvisor(unittest.TestCase):
    def test_retained_holding_and_upgrade_status_cannot_outvote_review(self):
        holding = MockCoinItem("synthetic", "Canada", "1 cent", "1967", "VF-20", 5)
        upstream = CollectionIntelligenceResult(
            MatchStatus.BETTER_GRADE_UPGRADE,
            ExistingMatch("synthetic", "Canada", "1 cent", "1967", "VF-20"),
            "UNAVAILABLE", "UNAVAILABLE", "REVIEW", None,
        )
        with patch("upgrade_advisor.FocusedCollectionIntelligenceEngine") as engine:
            engine.return_value.analyze_candidate.return_value = upstream
            engine.return_value.find_exact_items.return_value = [holding]
            rec = UpgradeAdvisor([holding]).analyze_upgrade("Canada", "1 cent", "1967", "MS-65", 50)
        self.assert_unresolved(rec)
        self.assertEqual(rec.candidate_grade, "MS-65")
        self.assertEqual(rec.candidate_estimate, 50)
        self.assertIn("equivalence unresolved", rec.reason)

    def test_unresolved_identity_does_not_infer_positive_or_zero_melt(self):
        for country, denomination in (("Canada", "dollar"), ("", "1 cent")):
            with self.subTest(country=country, denomination=denomination):
                rec = UpgradeAdvisor([]).analyze_upgrade(country, denomination, "", "VF-20", 10)
                self.assert_unresolved(rec)
                self.assertIsNone(rec.candidate_melt_value_cad)
                self.assertEqual(rec.candidate_estimate, 10)
                self.assertIn("equivalence unresolved", rec.reason)
    def setUp(self):
        self.items = [MockCoinItem("1", "Canada", "1 cent", "1967", "VF-20", 5.0),
                      MockCoinItem("2", "Canada", "1 cent", "1967", "VF-30", 10.0)]
        self.advisor = UpgradeAdvisor(self.items)

    def assert_unresolved(self, rec):
        self.assertEqual(rec.verdict, "REVIEW")
        for field in ("existing_country", "existing_denomination", "existing_year",
                      "existing_grade", "existing_estimate", "existing_item_id",
                      "upgrade_score", "grade_improvement", "value_improvement",
                      "existing_melt_value_cad", "melt_value_improvement"):
            with self.subTest(field=field):
                self.assertIsNone(getattr(rec, field))
                self.assertIsNone(rec.to_dict()[field])
        for claim in ("keep your current coin", "no matching coin", "no grade difference"):
            self.assertNotIn(claim, rec.explanation.lower())
        self.assertIn("unavailable", rec.explanation.lower())

    def test_triplet_grade_cannot_authorize_upgrade_duplicate_or_hold(self):
        for grade in ("MS-65", "EF-40", "VF-30", "VG-8", "", "mystery"):
            with self.subTest(grade=grade):
                rec = self.advisor.analyze_upgrade("Canada", "1 cent", "1967", grade, 25.0)
                self.assert_unresolved(rec)
                self.assertEqual(rec.candidate_grade, grade)
                self.assertEqual(rec.candidate_estimate, 25.0)

    def test_empty_collection_does_not_establish_absence(self):
        self.assert_unresolved(UpgradeAdvisor([]).analyze_upgrade("Canada", "1 cent", "1967", "EF-40", 20.0))

    def test_different_triplet_does_not_establish_absence(self):
        self.assert_unresolved(self.advisor.analyze_upgrade("USA", "1 cent", "1900", "VF-20", 5.0))

    def test_missing_holding_grade_or_year_does_not_establish_upgrade_or_gap(self):
        for year, grade in (("1967", ""), ("", "VF-20"), ("1967", "mystery")):
            with self.subTest(year=year, grade=grade):
                advisor = UpgradeAdvisor([MockCoinItem("1", "Canada", "1 cent", year, grade)])
                self.assert_unresolved(advisor.analyze_upgrade("Canada", "1 cent", "1967", "EF-40", 20.0))

    def test_historical_note_variety_cannot_authorize_comparison(self):
        item = MockCoinItem("1", "Canada", "1 cent", "1859", "VG-8", 200.0, "Historical narrow 9 variety")
        self.assert_unresolved(UpgradeAdvisor([item]).analyze_upgrade("Canada", "1 cent", "1859", "VF-20", 250.0))

    def test_incomplete_candidate_cannot_establish_safe_purchase(self):
        for country, denom, year in (("", "1 cent", "1967"), ("Canada", "", "1967"), ("Canada", "1 cent", "")):
            with self.subTest(country=country, denom=denom, year=year):
                self.assert_unresolved(UpgradeAdvisor([]).analyze_upgrade(country, denom, year, "VF-20", 10.0))

    def test_unknown_grade_is_unavailable_instead_of_zero(self):
        for grade in ("", "mystery", "UNGRADED"):
            with self.subTest(grade=grade):
                self.assertIsNone(self.advisor._grade_score(grade))
                self.assertIsNone(self.advisor._calculate_grade_improvement(grade, "VF-20"))
                self.assertIsNone(self.advisor._calculate_grade_improvement("VF-20", grade))

    def test_no_highest_grade_fallback_without_authoritative_selection(self):
        self.assertIsNone(self.advisor._get_intelligence_best_item(SimpleNamespace(best_existing_match=None), self.items))

    def test_lost_wrong_or_ambiguous_selection_does_not_choose_holding(self):
        for item_id, holdings in (("missing", self.items), ("", self.items), ("1", [self.items[0], self.items[0]])):
            with self.subTest(item_id=item_id):
                result = SimpleNamespace(best_existing_match=SimpleNamespace(item_id=item_id))
                self.assertIsNone(self.advisor._get_intelligence_best_item(result, holdings))

    def test_silver_identity_does_not_supply_independent_melt_evidence(self):
        rec = self.advisor.analyze_upgrade("Canada", "dollar", "1935", "EF-40", 150.0)
        self.assert_unresolved(rec)
        self.assertIsNone(rec.candidate_melt_value_cad)
        self.assertIn("equivalence unresolved", rec.reason)
        self.assertNotIn("Candidate melt value", rec.explanation)
        self.assertEqual(rec.candidate_estimate, 150.0)

    def test_non_silver_identity_does_not_authorize_zero_melt(self):
        rec = self.advisor.analyze_upgrade("Canada", "1 cent", "1967", "EF-40", 20.0)
        self.assert_unresolved(rec)
        self.assertIsNone(rec.candidate_melt_value_cad)
        self.assertEqual(rec.candidate_estimate, 20)
        self.assertEqual(rec.candidate_grade, "EF-40")
        self.assertIn("equivalence unresolved", rec.reason)

    def test_collector_interest_does_not_boost_upgrade_score(self):
        rec = self.advisor.analyze_upgrade("Newfoundland", "50 cents", "1909", "VF-20", 75.0)
        self.assert_unresolved(rec)
        self.assertIn("Newfoundland", rec.explanation)
        self.assertIn("interest", rec.explanation.lower())

    def test_read_only_behavior(self):
        before = [vars(item).copy() for item in self.items]
        self.advisor.analyze_upgrade("Canada", "1 cent", "1967", "EF-40", 20.0)
        self.assertEqual([vars(item) for item in self.items], before)

    def test_csv_marks_unavailable_comparisons_explicitly(self):
        rec = self.advisor.analyze_upgrade("Canada", "1 cent", "1967", "EF-40", 20.0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recommendations.csv"
            self.assertTrue(self.advisor.export_to_csv([rec], str(path)))
            with path.open(newline="", encoding="utf-8") as source:
                row = next(csv.DictReader(source))
            self.assertEqual(row["verdict"], "REVIEW")
            for field in ("upgrade_score", "grade_improvement", "value_improvement", "existing_item_id", "existing_estimate", "melt_value_improvement"):
                self.assertEqual(row[field], "unavailable")
            self.assertEqual(row["candidate_estimate"], "20.0")

    def test_csv_supported_zero_remains_zero(self):
        rec = self.advisor.analyze_upgrade("Canada", "1 cent", "1967", "EF-40", 20.0)
        rec.upgrade_score = rec.grade_improvement = 0
        rec.value_improvement = rec.existing_estimate = rec.melt_value_improvement = 0.0
        # An explicitly supplied supported numeric value at the serialization
        # boundary remains zero; the unresolved advisor no longer infers it.
        rec.candidate_melt_value_cad = 0.0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zero.csv"
            self.assertTrue(self.advisor.export_to_csv([rec], str(path)))
            with path.open(newline="", encoding="utf-8") as source:
                row = next(csv.DictReader(source))
        for field in ("upgrade_score", "grade_improvement"):
            self.assertEqual(row[field], "0")
        for field in ("value_improvement", "existing_estimate", "melt_value_improvement", "candidate_melt_value_cad"):
            self.assertEqual(row[field], "0.0")


if __name__ == "__main__":
    unittest.main()
