"""Tests for the Collection Quality Engine."""

import os
import tempfile
import unittest

from collection_dashboard import CollectionDashboard
from collection_quality import CollectionQualityEngine, CollectionQualityReport
from coin_collection import CoinItem, IdentificationStatus, ItemType
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


def make_intent(target_coin, priority="High", priority_score=75):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id=f"want_{target_coin}",
        target_coin=target_coin,
        priority=priority,
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Quality test target",
        status="Active",
        priority_score=priority_score,
    )


class TestCollectionQualityEngine(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("1", "Newfoundland", "20 cents", "1900", "F-12"),
            make_item("2", "Newfoundland", "20 cents", "1901", "VF-20"),
            make_item("3", "Newfoundland", "20 cents", "1903", "EF-40", notes="PCGS certified"),
            make_item("4", "Canada", "10 cents", "1911", "VF-20"),
            make_item("5", "Canada", "10 cents", "1911", "EF-40"),
            make_item("6", "Canada", "1 cent", "1859", "VG-8"),
            make_item("7", "United States", "1 cent", "1975", "VF-20"),
        ]

    def test_empty_collection(self):
        report = CollectionQualityEngine([]).generate_report()

        self.assertIsInstance(report, CollectionQualityReport)
        self.assertEqual(report.overall_quality_score, 0)
        self.assertEqual(report.category_score("Completeness"), 0)
        self.assertTrue(any("No collection data" in weakness.title for weakness in report.weaknesses))

    def test_small_collection(self):
        report = CollectionQualityEngine(self.items).generate_report()

        self.assertGreater(report.overall_quality_score, 0)
        self.assertEqual(len(report.category_scores), 5)
        self.assertTrue(report.recommended_actions)

    def test_large_collection(self):
        items = [
            make_item(str(index), f"Country {index % 6}", f"{index % 9} cents", str(1900 + index), "VF-20")
            for index in range(30)
        ]
        report = CollectionQualityEngine(items).generate_report()

        self.assertEqual(report.supporting_metrics["total_items"], 30)
        self.assertGreaterEqual(report.category_score("Diversity"), 80)

    def test_completeness_scoring(self):
        report = CollectionQualityEngine(self.items).generate_report()
        completeness = next(category for category in report.category_scores if category.name == "Completeness")

        self.assertGreater(completeness.score, 0)
        self.assertGreaterEqual(completeness.metrics["missing_dates"], 1)

    def test_upgrade_scoring(self):
        report = CollectionQualityEngine(self.items).generate_report()
        upgrade = next(category for category in report.category_scores if category.name == "Upgrade")

        self.assertLess(upgrade.score, 100)
        self.assertEqual(upgrade.metrics["upgrade_opportunities"], 1)

    def test_want_list_scoring(self):
        intents = [
            make_intent("Newfoundland 20 cents 1901"),
            make_intent("Newfoundland 50 cents 1904"),
        ]
        report = CollectionQualityEngine(self.items, intents).generate_report()
        want_score = next(category for category in report.category_scores if category.name == "WANT_LIST Progress")

        self.assertEqual(want_score.metrics["want_list_items"], 2)
        self.assertEqual(want_score.metrics["completed_targets"], 1)
        self.assertEqual(want_score.metrics["remaining_targets"], 1)

    def test_diversity_scoring(self):
        report = CollectionQualityEngine(self.items).generate_report()

        self.assertGreater(report.category_score("Diversity"), 0)
        self.assertEqual(report.supporting_metrics["series_count"], 4)

    def test_certification_scoring(self):
        report = CollectionQualityEngine(self.items).generate_report()
        certification = next(category for category in report.category_scores if category.name == "Certification")

        self.assertEqual(certification.metrics["certified_items"], 1)
        self.assertEqual(certification.metrics["raw_items"], 6)

    def test_strength_generation(self):
        report = CollectionQualityEngine(self.items).generate_report()

        self.assertTrue(any("Newfoundland" in strength.title for strength in report.strengths))

    def test_weakness_generation(self):
        report = CollectionQualityEngine(self.items, [make_intent("Newfoundland 50 cents 1904")]).generate_report()

        self.assertTrue(report.weaknesses)
        self.assertTrue(any("WANT_LIST" in weakness.title or "completion" in weakness.title for weakness in report.weaknesses))

    def test_recommended_actions(self):
        report = CollectionQualityEngine(self.items, [make_intent("Newfoundland 50 cents 1904")]).generate_report()

        self.assertTrue(report.recommended_actions)
        self.assertEqual(report.recommended_actions[0].rank, 1)
        self.assertTrue(any("Acquire" in action.action or "Complete" in action.action for action in report.recommended_actions))

    def test_dashboard_integration(self):
        data = CollectionDashboard(self.items, [make_intent("Newfoundland 50 cents 1904")]).generate_dashboard()

        self.assertIsNotNone(data.quality_report)
        self.assertGreater(data.quality_report.overall_quality_score, 0)
        self.assertTrue(data.quality_report.recommended_actions)

    def test_export_support(self):
        engine = CollectionQualityEngine(self.items, [make_intent("Newfoundland 50 cents 1904")])
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "quality.csv")
            md_path = os.path.join(temp_dir, "quality.md")

            self.assertTrue(engine.export_csv(csv_path))
            self.assertTrue(engine.export_markdown(md_path))

            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("Overall", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("# Collection Quality Report", handle.read())


class TestRecommendationContainment(unittest.TestCase):
    def assert_no_disposition(self, actions):
        text = " ".join(
            f"{action.action} {action.why_it_matters} {action.expected_impact}"
            for action in actions
        ).lower()
        for phrase in ("upgrade", "replace", "keep current best", "reduce", "sell", "trade", "redundant"):
            self.assertNotIn(phrase, text)
        for phrase in ("no duplicates", "no action needed", "no replacement", "optimal"):
            self.assertNotIn(phrase, text)

    def test_legacy_groups_never_authorize_replacement_or_reduction(self):
        cases = [
            ("weak fields", {}, {}, "F-12", "EF-40"),
            ("unidentified", {"identification_status": IdentificationStatus.UNIDENTIFIED}, {}, "F-12", "EF-40"),
            ("ineligible identity", {"identification_status": IdentificationStatus.PARTIAL}, {}, "F-12", "EF-40"),
            ("different types", {"item_type": ItemType.BANKNOTE}, {}, "F-12", "EF-40"),
            ("grade only", {}, {}, "VF-20", "AU-50"),
            ("equal grades", {}, {}, "VF-20", "VF-20"),
            ("group quantity", {"quantity": 4}, {"quantity": 3}, "F-12", "EF-40"),
        ]
        for name, first, second, first_grade, second_grade in cases:
            with self.subTest(name=name):
                items = [
                    make_item("a", "Canada", "10 cents", "1911", first_grade, **first),
                    make_item("b", "Canada", "10 cents", "1911", second_grade, **second),
                ]
                engine = CollectionQualityEngine(items)
                self.assertTrue(engine.intelligence.detect_duplicates())
                report = engine.generate_report()
                self.assert_no_disposition(report.recommended_actions)
                self.assertFalse(any(a.action.startswith("Acquire") for a in report.recommended_actions))
                # Omitted advice does not turn unavailable authority into a negative metric.
                self.assertEqual(report.supporting_metrics["duplicate_groups"], 1)

    def test_recorded_quantity_does_not_authorize_reduction(self):
        engine = CollectionQualityEngine([
            make_item("a", "Canada", "10 cents", "1911", "VF-20", quantity=5),
        ])
        self.assertTrue(engine.intelligence.detect_duplicates())
        report = engine.generate_report()
        self.assert_no_disposition(report.recommended_actions)
        self.assertEqual(report.supporting_metrics["duplicate_groups"], 1)

    def test_upgrade_target_is_omitted_but_matching_explicit_want_is_preserved(self):
        items = [
            make_item("a", "Canada", "10 cents", "1911", "F-12"),
            make_item("b", "Canada", "10 cents", "1911", "EF-40"),
        ]
        engine = CollectionQualityEngine(items, [make_intent("Canada 10 cents 1911")])
        targets = engine.intelligence.generate_want_list(staged_want_list_intents=engine.staged_want_list_intents)
        self.assertEqual({t.target_type for t in targets}, {"Upgrade Candidate", "Explicit WANT_LIST Target"})
        report = engine.generate_report()
        acquisitions = [a for a in report.recommended_actions if a.action.startswith("Acquire")]
        self.assertEqual(len(acquisitions), 1)
        self.assertEqual(acquisitions[0].action, "Acquire Canada 10 cents 1911")
        self.assertIn("Explicit WANT_LIST", acquisitions[0].why_it_matters)
        self.assert_no_disposition(report.recommended_actions)

    def test_legacy_targets_cannot_crowd_out_explicit_want_before_filtering(self):
        items = [
            make_item(f"{year}-{grade}", "Newfoundland", "20 cents", str(year), grade)
            for year in range(1900, 1912)
            for grade in ("F-12", "EF-40")
        ]
        report = CollectionQualityEngine(items, [make_intent("France 1 franc 2000", priority_score=0)]).generate_report()
        self.assertEqual([a.action for a in report.recommended_actions], ["Acquire France 1 franc 2000"])
        self.assertEqual(report.supporting_metrics["priority_targets"], 10)
        self.assert_no_disposition(report.recommended_actions)

    def test_unrelated_gap_recommendations_remain(self):
        items = [
            make_item("a", "Canada", "10 cents", "1911", "F-12"),
            make_item("b", "Canada", "10 cents", "1911", "EF-40"),
            make_item("c", "Canada", "10 cents", "1913", "VF-20"),
        ]
        report = CollectionQualityEngine(items).generate_report()
        self.assertEqual({a.action for a in report.recommended_actions}, {
            "Complete Canada / 10 cents", "Acquire Canada 10 cents 1912",
        })
        self.assert_no_disposition(report.recommended_actions)

    def test_exported_recommendations_preserve_containment(self):
        import csv

        engine = CollectionQualityEngine([
            make_item("a", "Canada", "10 cents", "1911", "F-12"),
            make_item("b", "Canada", "10 cents", "1911", "EF-40"),
        ], [make_intent("France 1 franc 2000")])
        with tempfile.TemporaryDirectory() as directory:
            md_path = os.path.join(directory, "quality.md")
            csv_path = os.path.join(directory, "quality.csv")
            self.assertTrue(engine.export_markdown(md_path))
            self.assertTrue(engine.export_csv(csv_path))
            with open(md_path, encoding="utf-8") as handle:
                recommendations = handle.read().split("## Recommended Actions\n", 1)[1].split("## Supporting Metrics", 1)[0]
            self.assertIn("Acquire France 1 franc 2000", recommendations)
            self.assertNotIn("Acquire Canada 10 cents 1911", recommendations)
            self.assertNotIn("replace", recommendations.lower())
            self.assertNotIn("reduce", recommendations.lower())
            with open(csv_path, encoding="utf-8", newline="") as handle:
                rows = [row for row in csv.reader(handle) if row[0] == "Recommended Action"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][1], "Acquire France 1 franc 2000")
            self.assertIn("Explicit WANT_LIST", rows[0][3])


if __name__ == "__main__":
    unittest.main()
