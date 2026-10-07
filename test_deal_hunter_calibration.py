"""Tests for v3.6 Deal Hunter calibration."""

import csv
import json
import os
import tempfile
import unittest
from dataclasses import replace

from coin_collection import CoinItem
from deal_hunter_calibration import CalibrationCase, CalibrationCaseResult, DealHunterCalibrationEngine, DealHunterCalibrationReport
from deal_hunter import DealHunterResult, DealListing, ParsedDealCandidate
from deal_hunter_ranking import DealHunterRankingEngine, RankedDeal, RankingScore
from legacy_portfolio_importer import LegacyWantListIntent
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from opportunity_engine import OpportunityReport


FIXTURE_PATH = os.path.join("test_data", "deal_hunter", "calibration_cases.csv")


def make_item(item_id, country, denomination, year, grade, **overrides):
    data = {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": grade,
        "notes": "",
        "date_added": "2026-06-21",
    }
    data.update(overrides)
    return CoinItem(**data)


def make_intent(target_coin, priority_score=90):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id=f"cal_{target_coin}",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Deal Hunter calibration target",
        status="Active",
        priority_score=priority_score,
    )


class TestDealHunterCalibration(unittest.TestCase):
    def test_fresh_review_dominates_retained_supported_ranking(self):
        from deal_hunter import DealHunter

        fresh = DealHunter([]).analyze_listing(DealListing("Unattributed coin lot", 80, 5))
        older = replace(fresh, collection_status="Supported boundary", recommendation="WATCH",
                        priority_score=90, collection_fit_score=90, max_rational_price=100)
        ranked = RankedDeal(1, older.listing, older, RankingScore(90), "WATCH", "Supported boundary", "Within $100", [], "Review", "Manual")
        for category in ("TOP_3", "TOP_10", "TOP_UNDER_100"):
            with self.subTest(category=category):
                case = CalibrationCase("fresh", fresh.listing.title, 80, 5,
                                       expected_recommendation="REVIEW", expected_rank_category=category)
                row = DealHunterCalibrationEngine([])._evaluate_case(case, fresh, ranked)
                self.assertIsNone(row.ranking_miss)
                self.assertFalse(row.accepted)
                self.assertNotEqual(DealHunterCalibrationReport([row]).status, "PASS")
        case = CalibrationCase("no-ranking", fresh.listing.title, 80, 5, expected_recommendation="REVIEW")
        self.assertTrue(DealHunterCalibrationEngine([])._evaluate_case(case, fresh, ranked).accepted)

    def test_real_needs_review_blocks_retained_numeric_ranking(self):
        from deal_hunter import DealHunter

        fresh = DealHunter([]).analyze_listing(DealListing("Unattributed coin lot", 80, 5))
        self.assertEqual(fresh.collection_status, "needs review")
        for status in ("BUY", "WATCH", "PASS"):
            stale = replace(fresh, recommendation=status, priority_score=90, collection_fit_score=90, max_rational_price=100)
            ranked = RankedDeal(1, stale.listing, stale, RankingScore(90), status, stale.collection_status, "Within $100", [], "Review", "Manual")
            with self.subTest(status=status):
                self.assertIsNone(DealHunterCalibrationEngine._ranking_miss("TOP_3", ranked))

    def test_stale_rank_unavailable_or_review_cannot_satisfy_ranking(self):
        result = DealHunterCalibrationEngine([]).run([CalibrationCase("review", "Unattributed coin lot", expected_recommendation="REVIEW")]).case_results[0].deal_result
        for category in ("TOP_3", "TOP_10", "TOP_UNDER_100"):
            for score in (None, 90):
                case = CalibrationCase("required", result.listing.title, expected_recommendation="REVIEW", expected_rank_category=category)
                ranked = RankedDeal(1, result.listing, result, RankingScore(score), "REVIEW", "Unavailable", "Within budget")
                evaluated = self.engine._evaluate_case(case, result, ranked)
                self.assertIsNone(evaluated.ranking_miss)
                self.assertFalse(evaluated.passed)
                self.assertEqual(result.listing.total_cost, 0)

    def test_public_default_pass_cannot_override_unavailable_required_ranking(self):
        case = CalibrationCase("required", "Unattributed coin lot", expected_recommendation="REVIEW", expected_rank_category="TOP_3")
        result = self.engine.run([case]).case_results[0].deal_result
        row = CalibrationCaseResult(case, result)
        report = DealHunterCalibrationReport([row])
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(report.passed_cases, 0)
        self.assertFalse(row.to_dict()["passed"])
        self.assertIn("required: Unattributed coin lot", report.format_markdown())
        self.assertEqual(DealHunterCalibrationReport([replace(row, ranking_miss=False)]).status, "REVIEW")

    def setUp(self):
        self.items = [
            make_item("nf1900", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("nf1902", "Newfoundland", "50 cents", "1902", "VF-20"),
            make_item("ca1911", "Canada", "10 cents", "1911", "VF-20"),
            make_item("lc1859", "Canada", "1 cent", "1859", "G-4"),
        ]
        self.intents = [
            make_intent("Newfoundland 50 cents 1901", 95),
            make_intent("Canada chartered banknote BCS VF25", 80),
        ]
        self.market = MarketAwarenessEngine(observations=[
            ObservedPriceRecord("1901 Newfoundland 50 cents", "Newfoundland", "50 cents", "1901", "VF-20", 90),
            ObservedPriceRecord("1911 Canada 10 cents", "Canada", "10 cents", "1911", "EF-40", 70),
        ])
        self.engine = DealHunterCalibrationEngine(self.items, self.intents, self.market)

    def test_calibration_case_creation(self):
        case = CalibrationCase.from_dict({
            "case_id": "sample",
            "title": "1901 Newfoundland 50 cents VF20",
            "price_cad": "80",
            "shipping_cad": "5",
            "expected_recommendation": "buy",
            "expected_risk_flags": "HIGH_SHIPPING|UNCLEAR_GRADE",
        })

        self.assertEqual(case.expected_recommendation, "BUY")
        self.assertEqual(case.price_cad, 80.0)
        self.assertEqual(case.shipping_cad, 5.0)
        self.assertEqual(case.expected_risk_flags, ["HIGH_SHIPPING", "UNCLEAR_GRADE"])
        self.assertEqual(case.to_listing().total_cost, 85.0)

    def test_review_uncertainty_vocabulary(self):
        result = self.engine.run([CalibrationCase(
            "uncertainty", "1901 Newfoundland 50 cents", expected_recommendation="REVIEW",
        )]).case_results[0].deal_result
        for explanation in [
            "Owned issue equivalence unresolved.",
            "Canonical candidate identity unavailable.",
            "Owned issue equivalence unresolved: canonical candidate identity unavailable.",
            "review", "unclear", "ambiguous", "currency", "lot",
        ]:
            with self.subTest(explanation=explanation):
                explained = replace(result, reasons=[], warnings=[explanation],
                                    risk_flags=[], counterargument="")
                self.assertEqual(self.engine._explanation_findings("REVIEW", explained), [])

    def test_review_requires_actual_uncertainty_language(self):
        result = self.engine.run([CalibrationCase(
            "no_uncertainty", "1901 Newfoundland 50 cents", expected_recommendation="REVIEW",
        )]).case_results[0].deal_result
        for explanation in ["Attractive listing", "unresolvedness", "unavailableish"]:
            with self.subTest(explanation=explanation):
                explained = replace(result, reasons=[], warnings=[explanation],
                                    risk_flags=[], counterargument="")
                self.assertEqual(self.engine._explanation_findings("REVIEW", explained),
                                 ["REVIEW explanation does not identify uncertainty"])

    def test_uncertainty_words_do_not_validate_decisive_advice(self):
        result = self.engine.run([CalibrationCase(
            "decisive", "1901 Newfoundland 50 cents", expected_recommendation="REVIEW",
        )]).case_results[0].deal_result
        for word in ["unresolved", "unavailable"]:
            for recommendation, findings in [
                ("BUY", ["BUY recommendation missing counterargument",
                         "BUY recommendation missing positive reasons"]),
                ("PASS", ["PASS explanation does not clearly describe risk, duplicate, or poor fit"]),
                ("WATCH", []),
            ]:
                with self.subTest(word=word, recommendation=recommendation):
                    explained = replace(result, recommendation=recommendation, reasons=[],
                                        warnings=[word], risk_flags=[], counterargument="")
                    self.assertEqual(self.engine._explanation_findings(recommendation, explained), findings)
                    case = CalibrationCase("unsupported", "1901 Newfoundland 50 cents",
                                           expected_recommendation=recommendation)
                    evaluated = self.engine._evaluate_case(case, replace(result, warnings=[word]), None)
                    self.assertFalse(evaluated.passed)
                    self.assertIn(f"Expected {recommendation}, got REVIEW", evaluated.findings)

    def test_load_fixture_cases(self):
        cases = self.engine.load_cases(FIXTURE_PATH)

        self.assertGreaterEqual(len(cases), 15)
        self.assertTrue(any(case.case_id == "raw_overgraded" for case in cases))

    def test_calibration_report_generation(self):
        report = self.engine.run(self.engine.load_cases(FIXTURE_PATH))

        self.assertEqual(report.total_cases, 15)
        # The CSV retains historical decisive expectations. Report the mismatch
        # honestly; REVIEW is neither a false BUY nor a false PASS.
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(report.failed_cases, 15)
        self.assertEqual(len(report.false_reviews), 11)
        self.assertEqual(len(report.false_buys), 0)
        self.assertEqual(len(report.false_passes), 0)
        self.assertTrue(all(row.deal_result.recommendation == "REVIEW" for row in report.case_results))
        self.assertTrue(all(row.ranked_deal is None for row in report.case_results))
        # Test-only migration preserves independent risks and descriptive rationale.
        migrated = [replace(case, expected_recommendation="REVIEW", expected_rank_category="",
                            expected_priority_reason="" if case.expected_priority_reason in
                            {"Potential upgrade", "Duplicate"} else case.expected_priority_reason)
                    for case in self.engine.load_cases(FIXTURE_PATH)]
        current = self.engine.run(migrated)
        self.assertEqual(current.total_cases, 15)
        self.assertEqual(current.status, "PASS")
        self.assertEqual(current.failed_cases, 0)
        self.assertEqual(current.missing_risk_flag_cases, [])
        self.assertEqual(len(current.false_reviews), 0)
        self.assertIn("Total cases: 15", current.format_markdown())

    def test_false_buy_detection(self):
        case = CalibrationCase(
            "false_buy",
            "1901 Newfoundland 50 cents VF20 PCGS",
            price_cad=80,
            shipping_cad=5,
            expected_recommendation="PASS",
        )

        report = self.engine.run([case])

        self.assertEqual(len(report.false_buys), 0)
        self.assertEqual(len(report.false_passes), 0)
        self.assertEqual(len(report.false_reviews), 1)
        self.assertEqual(report.case_results[0].deal_result.recommendation, "REVIEW")
        self.assertIn("Expected PASS, got REVIEW", report.case_results[0].findings)
        self.assertEqual(report.case_results[0].deal_result.listing.total_cost, 85)
        self.assertEqual(report.status, "REVIEW")

    def test_false_pass_detection(self):
        case = CalibrationCase(
            "false_pass",
            "France 10 centimes 1975",
            price_cad=1,
            shipping_cad=5,
            expected_recommendation="BUY",
        )

        report = self.engine.run([case])

        self.assertEqual(len(report.false_passes), 0)
        self.assertEqual(len(report.false_buys), 0)
        self.assertEqual(len(report.false_reviews), 1)
        self.assertEqual(report.case_results[0].deal_result.recommendation, "REVIEW")
        self.assertIn("Expected BUY, got REVIEW", report.case_results[0].findings)
        self.assertEqual(report.case_results[0].deal_result.listing.total_cost, 6)
        self.assertEqual(report.status, "REVIEW")

    def test_ranking_miss_detection(self):
        case = CalibrationCase(
            "ranking_miss",
            "1901 Newfoundland 50 cents VF20 PCGS",
            price_cad=80,
            shipping_cad=5,
            expected_recommendation="BUY",
            expected_rank_category="LOW_PRIORITY",
        )

        report = self.engine.run([case])

        self.assertEqual(report.ranking_misses, [])
        self.assertIsNone(report.case_results[0].ranking_miss)
        self.assertFalse(report.case_results[0].passed)

    def test_supported_ranking_rule_boundaries(self):
        result = DealHunterResult(
            DealListing("Supported downstream", 80, 5), ParsedDealCandidate(),
            "Supported boundary", 80, 20, 70, 0, 100, "WATCH", "Manual review")
        # Downstream numeric contract only; no positive issue equivalence claimed.
        for category, rank, score, cost, expected in [
            ("TOP_3", 3, 35, 85, False), ("TOP_3", 4, 35, 85, True),
            ("TOP_10", 10, 35, 85, False), ("TOP_10", 11, 35, 85, True),
            ("NOT_TOP_10", 10, 35, 85, True), ("NOT_TOP_10", 11, 35, 85, False),
            ("TOP_UNDER_100", 10, 35, 100, False),
            ("TOP_UNDER_100", 11, 35, 100, True),
            ("TOP_UNDER_100", 10, 35, 101, True),
            ("LOW_PRIORITY", 1, 35, 85, False), ("LOW_PRIORITY", 1, 36, 85, True),
            ("LOW_PRIORITY", 2, 0, 0, False),
        ]:
            with self.subTest(category=category, rank=rank, score=score, cost=cost):
                ranked = RankedDeal(rank, replace(result.listing, price_cad=cost, shipping_cad=0),
                                    result, RankingScore(score), "WATCH", "Supported", "Within budget")
                self.assertIs(self.engine._ranking_miss(category, ranked), expected)
                case = CalibrationCase("supported", result.listing.title,
                                       expected_recommendation="WATCH", expected_rank_category=category)
                evaluated = self.engine._evaluate_case(case, result, ranked)
                self.assertIs(evaluated.ranking_miss, expected)
                self.assertIs(evaluated.passed, not expected)

    def test_unavailable_ranking_evidence(self):
        result = self.engine.run([CalibrationCase("unranked", "Unattributed coin lot")]).case_results[0].deal_result
        ranking = DealHunterRankingEngine([])
        unranked = ranking._rank_result(result, None)
        self.assertIsNone(unranked.rank)
        self.assertIsNone(unranked.ranking_score.score)
        for category in ["TOP_3", "TOP_10", "NOT_TOP_10", "TOP_UNDER_100", "LOW_PRIORITY"]:
            with self.subTest(category=category):
                self.assertIsNone(self.engine._ranking_miss(category, unranked))
                self.assertIsNone(self.engine._ranking_miss(category, None))
        supported = DealHunterResult(DealListing("Supported downstream", 80, 5), ParsedDealCandidate(),
                                     "Supported boundary", 80, 20, 70, 0, 100, "WATCH", "Manual review")
        intermediate = ranking._rank_result(supported, OpportunityReport(None, "Boundary", "Supported", 75))
        self.assertIsNotNone(intermediate.ranking_score.score)
        self.assertIsNone(intermediate.rank)
        self.assertIsNone(self.engine._ranking_miss("TOP_3", intermediate))
        # LOW_PRIORITY only requires the score, which is available before rank assignment.
        self.assertIs(self.engine._ranking_miss("LOW_PRIORITY", intermediate), True)

    def test_unavailable_ranking_cannot_satisfy_required_non_miss(self):
        case = CalibrationCase("required", "Unattributed coin lot", expected_recommendation="REVIEW",
                               expected_rank_category="TOP_3")
        result = self.engine.run([case]).case_results[0].deal_result
        row = self.engine._evaluate_case(case, result, None)
        self.assertIsNone(row.ranking_miss)
        self.assertIsNot(row.ranking_miss, False)
        self.assertFalse(row.passed)
        self.assertTrue(any("unavailable" in finding.lower() for finding in row.findings))
        # Existing uncertainty acceptance remains legitimate without a requested ranking comparison.
        unconstrained = self.engine._evaluate_case(replace(case, expected_rank_category=""), result, None)
        self.assertIsNone(unconstrained.ranking_miss)
        self.assertTrue(unconstrained.passed)

    def test_tristate_default_and_exports(self):
        case = CalibrationCase("export", "Unattributed coin lot", expected_recommendation="REVIEW")
        result = self.engine.run([case]).case_results[0].deal_result
        default = CalibrationCaseResult(case, result)
        self.assertIsNone(default.ranking_miss)
        rows = [replace(default, ranking_miss=value) for value in (True, False, None)]
        payload = json.loads(json.dumps([row.to_dict() for row in rows]))
        for row, value in zip(payload, (True, False, None)):
            self.assertIs(row["ranking_miss"], value)
        report = DealHunterCalibrationReport(rows)
        self.assertEqual(report.ranking_misses, [rows[0]])
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "tristate.csv")
            report.export_csv(path)
            with open(path, newline="", encoding="utf-8") as handle:
                self.assertEqual([row["ranking_miss"] for row in csv.DictReader(handle)],
                                 ["True", "False", "unavailable"])

    def test_missing_risk_flag_detection(self):
        case = CalibrationCase(
            "missing_risk",
            "1901 Newfoundland 50 cents VF20 PCGS",
            price_cad=80,
            shipping_cad=5,
            expected_recommendation="BUY",
            expected_risk_flags=["NON_EXISTENT_RISK"],
        )

        report = self.engine.run([case])

        self.assertEqual(len(report.missing_risk_flag_cases), 1)

    def test_newfoundland_calibration(self):
        case = CalibrationCase(
            "newfoundland_upgrade",
            "1900 Newfoundland 50 cents EF40 ICCS",
            price_cad=90,
            shipping_cad=5,
            expected_recommendation="REVIEW",
            expected_priority_reason="unresolved",
        )

        report = self.engine.run([case])

        self.assertEqual(report.status, "PASS")
        for row in report.case_results:
            self.assertEqual(row.deal_result.recommendation, "REVIEW")
            self.assertIsNone(row.deal_result.priority_score)
            self.assertIsNone(row.deal_result.collection_fit_score)
            self.assertIsNone(row.deal_result.max_rational_price)
            self.assertIsNone(row.ranked_deal)
        self.assertEqual(report.missing_risk_flag_cases, [])

        self.assertEqual(report.case_results[0].deal_result.parsed_candidate.country, "Newfoundland")
        self.assertEqual(report.case_results[0].deal_result.listing.total_cost, 95)

    def test_banknote_calibration(self):
        case = CalibrationCase(
            "banknote_target",
            "Canada chartered banknote BCS VF25",
            price_cad=120,
            shipping_cad=10,
            expected_recommendation="REVIEW",
            expected_priority_reason="Canadian banknote target",
        )

        report = self.engine.run([case])

        self.assertEqual(report.status, "PASS")
        for row in report.case_results:
            self.assertEqual(row.deal_result.recommendation, "REVIEW")
            self.assertIsNone(row.deal_result.priority_score)
            self.assertIsNone(row.deal_result.collection_fit_score)
            self.assertIsNone(row.deal_result.max_rational_price)
            self.assertIsNone(row.ranked_deal)
        self.assertEqual(report.missing_risk_flag_cases, [])

        self.assertIn("banknote", report.case_results[0].deal_result.parsed_candidate.keywords)
        self.assertEqual(report.case_results[0].deal_result.listing.total_cost, 130)

    def test_high_shipping_calibration(self):
        case = CalibrationCase(
            "high_shipping",
            "1901 Newfoundland 50 cents VF20 PCGS",
            price_cad=20,
            shipping_cad=60,
            expected_recommendation="REVIEW",
            expected_risk_flags=["HIGH_SHIPPING"],
            expected_priority_reason="High shipping",
        )

        report = self.engine.run([case])

        self.assertEqual(report.status, "PASS")
        for row in report.case_results:
            self.assertEqual(row.deal_result.recommendation, "REVIEW")
            self.assertIsNone(row.deal_result.priority_score)
            self.assertIsNone(row.deal_result.collection_fit_score)
            self.assertIsNone(row.deal_result.max_rational_price)
            self.assertIsNone(row.ranked_deal)
        self.assertEqual(report.missing_risk_flag_cases, [])

        result = report.case_results[0].deal_result
        self.assertEqual(result.listing.price_cad, 20)
        self.assertEqual(result.listing.shipping_cad, 60)
        self.assertEqual(result.listing.total_cost, 80)
        self.assertIn("HIGH_SHIPPING", result.risk_flags)
        self.assertTrue(any("shipping" in warning.lower() for warning in result.warnings))

    def test_duplicate_calibration(self):
        cases = [
            CalibrationCase("same", "1900 Newfoundland 50 cents VF20 ICCS", price_cad=75, shipping_cad=5, expected_recommendation="REVIEW", expected_priority_reason="unresolved"),
            CalibrationCase("lower", "1900 Newfoundland 50 cents VG8", price_cad=25, shipping_cad=5, expected_recommendation="REVIEW", expected_priority_reason="unresolved"),
        ]

        report = self.engine.run(cases)

        self.assertEqual(report.status, "PASS")
        for row in report.case_results:
            self.assertEqual(row.deal_result.recommendation, "REVIEW")
            self.assertIsNone(row.deal_result.priority_score)
            self.assertIsNone(row.deal_result.collection_fit_score)
            self.assertIsNone(row.deal_result.max_rational_price)
            self.assertIsNone(row.ranked_deal)
        self.assertEqual(report.missing_risk_flag_cases, [])

        self.assertEqual([row.deal_result.listing.total_cost for row in report.case_results], [80, 30])

    def test_export_generation(self):
        report = self.engine.run(self.engine.load_cases(FIXTURE_PATH))
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "calibration.csv")
            md_path = os.path.join(temp_dir, "calibration.md")

            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("false_buy", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("Deal Hunter Calibration Report", handle.read())


if __name__ == "__main__":
    unittest.main()
