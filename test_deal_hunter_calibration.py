"""Tests for v3.6 Deal Hunter calibration."""

import os
import tempfile
import unittest

from coin_collection import CoinItem
from deal_hunter_calibration import CalibrationCase, DealHunterCalibrationEngine
from legacy_portfolio_importer import LegacyWantListIntent
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord


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

    def test_load_fixture_cases(self):
        cases = self.engine.load_cases(FIXTURE_PATH)

        self.assertGreaterEqual(len(cases), 15)
        self.assertTrue(any(case.case_id == "raw_overgraded" for case in cases))

    def test_calibration_report_generation(self):
        report = self.engine.run(self.engine.load_cases(FIXTURE_PATH))

        self.assertEqual(report.total_cases, 15)
        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.failed_cases, 0)
        self.assertEqual(len(report.false_buys), 0)
        self.assertEqual(len(report.false_passes), 0)

    def test_false_buy_detection(self):
        case = CalibrationCase(
            "false_buy",
            "1901 Newfoundland 50 cents VF20 PCGS",
            price_cad=80,
            shipping_cad=5,
            expected_recommendation="PASS",
        )

        report = self.engine.run([case])

        self.assertEqual(len(report.false_buys), 1)
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

        self.assertEqual(len(report.false_passes), 1)
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

        self.assertEqual(len(report.ranking_misses), 1)

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
            expected_recommendation="BUY",
            expected_rank_category="TOP_10",
            expected_priority_reason="Potential upgrade",
        )

        report = self.engine.run([case])

        self.assertEqual(report.status, "PASS")

    def test_banknote_calibration(self):
        case = CalibrationCase(
            "banknote_target",
            "Canada chartered banknote BCS VF25",
            price_cad=120,
            shipping_cad=10,
            expected_recommendation="NEGOTIATE",
            expected_rank_category="TOP_10",
            expected_priority_reason="Canadian banknote target",
        )

        report = self.engine.run([case])

        self.assertEqual(report.status, "PASS")

    def test_high_shipping_calibration(self):
        case = CalibrationCase(
            "high_shipping",
            "1901 Newfoundland 50 cents VF20 PCGS",
            price_cad=20,
            shipping_cad=60,
            expected_recommendation="NEGOTIATE",
            expected_rank_category="TOP_10",
            expected_risk_flags=["HIGH_SHIPPING"],
            expected_priority_reason="High shipping",
        )

        report = self.engine.run([case])

        self.assertEqual(report.status, "PASS")

    def test_duplicate_calibration(self):
        cases = [
            CalibrationCase("same", "1900 Newfoundland 50 cents VF20 ICCS", price_cad=75, shipping_cad=5, expected_recommendation="PASS", expected_priority_reason="Duplicate"),
            CalibrationCase("lower", "1900 Newfoundland 50 cents VG8", price_cad=25, shipping_cad=5, expected_recommendation="PASS", expected_priority_reason="Duplicate"),
        ]

        report = self.engine.run(cases)

        self.assertEqual(report.status, "PASS")

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
