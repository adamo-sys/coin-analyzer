"""Unit tests for the collection intelligence engine."""

import csv
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime
from enum import Enum
from types import SimpleNamespace
from unittest.mock import patch

from coin_collection import CoinItem, IdentificationStatus, ItemType
from collection_intelligence import CollectionIntelligenceEngine
from issue_equivalence import (
    EffectiveStatus, IssueDecision, IssueEquivalenceResult, IssueReason,
    ItemType as IssueItemType,
)
from legacy_portfolio_importer import LegacyWantListIntent


def make_item(item_id, country, denomination, year, grade="VF-20", **overrides):
    values = {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": grade,
        "notes": "",
        "date_added": datetime.now().isoformat(),
        "auto_detected": False,
        "detection_confidence": 0.0,
        "reference": "",
        "numista_n": "",
        "title": "",
        "quantity": 1,
        "estimate_cad": 0.0,
        "from_numista": True,
    }
    values.update(overrides)
    return CoinItem(**values)


class TestCollectionIntelligenceEngine(unittest.TestCase):
    """Verify reusable collection analysis behavior."""

    def setUp(self):
        self.items = [
            make_item("nf_1900", "Newfoundland", "50 cents", "1900", "F-12"),
            make_item("nf_1902", "Newfoundland", "50 cents", "1902", "VF-20"),
            make_item("can_1859_a", "Canada", "1 cent", "1859", "VG-8", reference="Narrow 9"),
            make_item("can_1859_b", "Canada", "1 cent", "1859", "VF-20", reference="Narrow 9"),
            make_item("can_1910", "Canada", "10 cents", "1910", "F-12"),
            make_item("can_1912", "Canada", "10 cents", "1912", "F-12"),
        ]
        self.engine = CollectionIntelligenceEngine(self.items)

    def test_analyze_by_country_counts_items(self):
        countries = self.engine.analyze_by_country()

        self.assertEqual(countries["Newfoundland"]["count"], 2)
        self.assertEqual(countries["Canada"]["count"], 4)

    def test_detect_missing_years_by_series(self):
        missing = self.engine.detect_missing_years()

        self.assertEqual(missing[("Newfoundland", "50 cents")], [1901])

    def test_completion_percentages(self):
        series = self.engine.analyze_by_series()

        self.assertAlmostEqual(series[("Newfoundland", "50 cents")]["completion_percentage"], 66.666, places=2)

    def test_detect_duplicates_and_upgrade_candidates(self):
        duplicates = self.engine.detect_duplicates()
        upgrades = self.engine.detect_upgrade_candidates()

        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["country"], "Canada")
        self.assertEqual(upgrades[0]["current_best_grade"], "VF-20")

    def test_newfoundland_missing_date_is_high_priority(self):
        targets = self.engine.generate_want_list(limit=10)

        self.assertEqual(targets[0].country, "Newfoundland")
        self.assertEqual(targets[0].year, "1901")
        self.assertIn("Newfoundland", targets[0].reason)

    def test_gap_report_markdown_contains_required_sections(self):
        markdown = self.engine.format_gap_report_markdown()

        self.assertIn("# Collection Gap Report", markdown)
        self.assertIn("## Series Gap Analysis", markdown)
        self.assertIn("## Missing Dates", markdown)
        self.assertIn("## Completion Percentages", markdown)
        self.assertIn("## Upgrade Opportunities", markdown)
        self.assertIn("## Priority Acquisition Targets", markdown)

    def test_gap_report_rows_include_priority_tiers_and_suggestions(self):
        rows = self.engine.generate_gap_report_rows()
        by_series = {row["series"]: row for row in rows}

        self.assertEqual(by_series["Newfoundland / 50 cents"]["priority_tier"], "Tier 1")
        self.assertEqual(by_series["Canada / 10 cents"]["priority_tier"], "Tier 1")
        self.assertEqual(by_series["Canada / 1 cent"]["priority_tier"], "Tier 2")
        self.assertEqual(by_series["Canada / 10 cents"]["missing_years"], "1911")
        self.assertIn("Acquire missing date", by_series["Canada / 10 cents"]["suggested_next_acquisitions"])
        self.assertAlmostEqual(
            by_series["Canada / 10 cents"]["completion_percentage"],
            66.666,
            places=2,
        )

    def test_gap_report_csv_export_is_read_only(self):
        before_ids = [item.id for item in self.items]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "gap_report.csv")

            self.assertTrue(self.engine.export_gap_report_csv(output_path))
            with open(output_path, "r", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual([item.id for item in self.items], before_ids)
        self.assertTrue(rows)
        self.assertEqual(
            set(rows[0].keys()),
            {
                "priority_tier",
                "series",
                "country",
                "denomination",
                "years_owned",
                "missing_years",
                "completion_percentage",
                "suggested_next_acquisitions",
            },
        )
        canada_silver = next(row for row in rows if row["series"] == "Canada / 10 cents")
        self.assertEqual(canada_silver["priority_tier"], "Tier 1")
        self.assertEqual(canada_silver["missing_years"], "1911")

    def test_want_list_csv_export(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "want_list.csv")

            self.assertTrue(self.engine.export_want_list_csv(output_path, limit=10))
            with open(output_path, "r", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(rows)
        self.assertEqual(rows[0]["country"], "Newfoundland")

    def test_want_list_generator_combines_collection_gaps_and_staged_intent(self):
        intents = [
            LegacyWantListIntent(
                sheet_name="WANT_LIST",
                row_number=2,
                legacy_id="legacy_want_list_2",
                target_coin="Newfoundland 50 Cents 1904",
                priority="High",
                target_grade="VF-20",
                budget=125.0,
                why_wanted="Explicit user priority",
                status="Active",
                priority_score=75,
            )
        ]

        targets = self.engine.generate_want_list(
            limit=10,
            staged_want_list_intents=intents,
        )

        self.assertEqual(targets[0].coin_label, "Newfoundland 50 Cents 1904")
        self.assertEqual(targets[0].target_type, "Explicit WANT_LIST Target")
        self.assertIn("Explicit WANT_LIST target", targets[0].reason)
        self.assertIn("Explicit user priority", targets[0].reason)
        self.assertTrue(any(target.year == "1901" for target in targets))

    def test_want_list_reasons_explain_gap_and_upgrade_targets(self):
        targets = self.engine.generate_want_list(limit=10)
        reasons = " ".join(target.reason for target in targets)

        self.assertIn("Missing Newfoundland date", reasons)
        self.assertIn("Completes date run", reasons)
        self.assertIn("Upgrade opportunity", reasons)

    def test_want_list_exports_include_rank_coin_and_staged_intent(self):
        intents = [
            LegacyWantListIntent(
                sheet_name="WANT_LIST",
                row_number=2,
                legacy_id="legacy_want_list_2",
                target_coin="Canada 10 Cents 1911",
                priority="High",
                target_grade="VF-20",
                budget=100.0,
                why_wanted="Explicit WANT_LIST target for silver gap",
                status="Active",
                priority_score=75,
            )
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "want_list.csv")
            md_path = os.path.join(temp_dir, "want_list.md")

            self.assertTrue(
                self.engine.export_want_list_csv(
                    csv_path,
                    limit=10,
                    staged_want_list_intents=intents,
                )
            )
            self.assertTrue(
                self.engine.export_want_list_markdown(
                    md_path,
                    limit=10,
                    staged_want_list_intents=intents,
                )
            )
            with open(csv_path, "r", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            with open(md_path, "r", encoding="utf-8") as handle:
                markdown = handle.read()

        self.assertEqual(rows[0]["rank"], "1")
        self.assertEqual(rows[0]["coin"], "Canada 10 Cents 1911")
        self.assertIn("Explicit WANT_LIST target", rows[0]["reason"])
        self.assertIn("Canada 10 Cents 1911", markdown)


class TestSameIssueReport(unittest.TestCase):
    """Synthetic records pin admission, pairwise evidence and report authority."""

    def item(self, record_id, **overrides):
        return make_item(record_id, "Canada", "1 cent", "1910",
                         type_design="Maple leaves",
                         identification_status=IdentificationStatus.IDENTIFIED,
                         **overrides)

    def analyze(self, *items):
        return CollectionIntelligenceEngine(items).analyze_same_issue_records()

    def test_complete_group_retains_exact_ids_projections_and_pair_evidence(self):
        result = self.analyze(self.item(" z ", quantity=2), self.item("A"), self.item("B"))
        self.assertEqual(result["record_count"], 3)
        self.assertEqual(result["same_issue_record_count"], 3)
        group = result["established_groups"][0]
        self.assertEqual(group["member_ids"], [" z ", "A", "B"])
        self.assertEqual(group["same_issue_record_count"], 3)
        self.assertEqual(len(group["comparisons"]), 3)
        for member in group["members"]:
            projection = member["operative_projection"]
            self.assertEqual(projection.subject_key, member["record_id"])
            self.assertIs(projection.item_type, IssueItemType.COIN)
            self.assertIs(projection.effective_status, EffectiveStatus.IDENTIFIED)
        self.assertEqual(group["members"][0]["recorded_quantity"], 2)

    def test_missing_required_fields_remain_unresolved(self):
        for field in ("country", "denomination", "year", "type_design"):
            with self.subTest(field=field):
                a = self.item("A")
                setattr(a, field, "")
                result = self.analyze(a, self.item("B"))
                self.assertEqual(result["established_groups"], [])
                self.assertIs(result["comparisons"][0]["result"].decision, IssueDecision.ABSTAIN)
                self.assertTrue(result["unresolved_records"])

    def test_required_conflict_is_supported_different_issue(self):
        a = self.item("A")
        a.year = "1911"
        result = self.analyze(a, self.item("B"))
        self.assertEqual(result["established_groups"], [])
        self.assertIs(result["comparisons"][0]["result"].decision, IssueDecision.DIFFERENT_ISSUE)

    def test_source_enums_are_explicitly_mapped_and_fail_closed(self):
        class Foreign(str, Enum):
            COIN = "COIN"
            IDENTIFIED = "IDENTIFIED"
        for field, values in (
            ("item_type", (None, "COIN", Foreign.COIN, IssueItemType.COIN, 1)),
            ("identification_status", (None, "IDENTIFIED", Foreign.IDENTIFIED,
                                       EffectiveStatus.IDENTIFIED, True)),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    a = self.item("A")
                    setattr(a, field, value)
                    result = self.analyze(a, self.item("B"))
                    self.assertEqual(result["established_groups"], [])
                    self.assertTrue(result["unresolved_records"])
        result = self.analyze(self.item("A", item_type=ItemType.BANKNOTE),
                              self.item("B", item_type=ItemType.BANKNOTE))
        self.assertIs(result["members"][0]["operative_projection"].item_type,
                      IssueItemType.BANKNOTE)
        self.assertEqual(result["same_issue_record_count"], 2)
        result = self.analyze(self.item("A"), self.item("B", item_type=ItemType.BANKNOTE))
        self.assertIs(result["comparisons"][0]["result"].decision, IssueDecision.DIFFERENT_ISSUE)

    def test_partial_and_unidentified_status_abstain(self):
        for status in (IdentificationStatus.PARTIAL, IdentificationStatus.UNIDENTIFIED):
            a = self.item("A")
            a.identification_status = status
            result = self.analyze(a, self.item("B"))
            self.assertEqual(result["established_groups"], [])
            self.assertIn(IssueReason.INELIGIBLE_STATUS,
                          result["comparisons"][0]["result"].reason_codes)

    def test_forged_source_enum_instances_are_not_supported_members(self):
        for field, enum_type, value in (("item_type", ItemType, "COIN"),
                                        ("identification_status", IdentificationStatus, "IDENTIFIED")):
            a = self.item("A")
            setattr(a, field, str.__new__(enum_type, value))
            result = self.analyze(a, self.item("B"))
            self.assertEqual(result["established_groups"], [])
            self.assertTrue(result["unresolved_records"])

    def test_optional_qualifiers_constrain_membership(self):
        for field, left, right, decision in (
            ("issuer", "Ottawa", "London", IssueDecision.DIFFERENT_ISSUE),
            ("reference", "KM#1", "KM#2", IssueDecision.ABSTAIN),
            ("numista_n", "N#1", "N#2", IssueDecision.ABSTAIN),
            ("issuer", "Ottawa", "", IssueDecision.ABSTAIN),
            ("reference", "KM#1", "", IssueDecision.ABSTAIN),
            ("numista_n", "N#1", "", IssueDecision.ABSTAIN),
        ):
            with self.subTest(field=field, right=right):
                result = self.analyze(self.item("A", **{field: left}),
                                      self.item("B", **{field: right}))
                self.assertEqual(result["established_groups"], [])
                self.assertIs(result["comparisons"][0]["result"].decision, decision)

    def test_nonoperative_evidence_cannot_fill_identity(self):
        a = self.item("A")
        a.type_design = ""
        for field in ("title", "notes", "comments", "history", "ocr", "series",
                      "detection_suggestions", "catalogue_search"):
            setattr(a, field, "Canada 1 cent 1910 Maple leaves")
        a.auto_detected = True
        a.detection_confidence = 1.0
        result = self.analyze(a, self.item("B"))
        self.assertEqual(result["established_groups"], [])
        self.assertIs(result["comparisons"][0]["result"].decision, IssueDecision.ABSTAIN)

    def test_malformed_structured_text_fails_closed(self):
        for field in ("country", "denomination", "year", "type_design", "issuer",
                      "reference", "numista_n"):
            a = self.item("A")
            setattr(a, field, 1910)
            result = self.analyze(a, self.item("B"))
            self.assertEqual(result["established_groups"], [])
            self.assertTrue(result["unresolved_records"])

    def test_bridge_pairs_do_not_create_nonclique_groups(self):
        # Synthetic comparator outcomes exercise the grouping invariant even
        # if today's real contract cannot produce these bridge patterns.
        for failed in (IssueDecision.ABSTAIN, IssueDecision.DIFFERENT_ISSUE):
            def compare(left, right):
                keys = (left.subject_key, right.subject_key)
                decision = failed if set(keys) == {"A", "C"} else IssueDecision.SAME_ISSUE
                return IssueEquivalenceResult(decision,
                    (IssueReason.MISSING_REQUIRED_IDENTITY if failed is IssueDecision.ABSTAIN
                     else IssueReason.TYPE_DESIGN_CONFLICT,), (), keys)
            with self.subTest(failed=failed), patch(
                    "collection_intelligence.compare_issue_identity", side_effect=compare):
                result = self.analyze(self.item("A"), self.item("B"), self.item("C"))
                self.assertFalse(any(len(g["member_ids"]) == 3
                                     for g in result["established_groups"]))
                self.assertEqual(len(result["comparisons"]), 3)
                evidence = {tuple(p["member_ids"]): p["result"].decision
                            for p in result["comparisons"]}
                self.assertIs(evidence[("B", "C")], IssueDecision.SAME_ISSUE)
                self.assertIs(evidence[("A", "C")], failed)
                markdown = CollectionIntelligenceEngine([
                    self.item("A"), self.item("B"), self.item("C")
                ]).format_same_issue_report_markdown()
                self.assertIn(failed.value.lower().replace("_", " "), markdown.lower())
                self.assertIn('"A"', markdown)
                self.assertIn('"C"', markdown)

    def test_projection_association_does_not_zip_sorted_comparator_values(self):
        a = self.item("A", issuer="Zulu")
        b = self.item("B", issuer="Alpha")
        result = self.analyze(a, b)
        self.assertEqual([m["operative_projection"].issuer for m in result["members"]],
                         ["Zulu", "Alpha"])
        self.assertEqual(result["comparisons"][0]["result"].subject_keys, ("A", "B"))

    def test_repeated_ids_exclude_all_occurrences_without_inflation(self):
        a = self.item("A", quantity=10)
        for repeated in (a, replace(a, year="1911")):
            result = self.analyze(a, repeated, self.item("B"))
            self.assertEqual(result["record_count"], 1)
            self.assertEqual(result["same_issue_record_count"], 0)
            self.assertEqual(result["established_groups"], [])
            self.assertEqual(len(result["unresolved_records"]), 2)
            self.assertTrue(all("ambiguous" in r["reason"].lower()
                                for r in result["unresolved_records"]))

    def test_missing_and_malformed_ids_are_not_repaired(self):
        for bad in (None, "", "  ", 42, True, "A\nB"):
            a = self.item("A")
            a.id = bad
            result = self.analyze(a, self.item("B"))
            self.assertEqual(result["record_count"], 1)
            self.assertEqual(result["established_groups"], [])
            self.assertTrue(result["unresolved_records"])
        a = SimpleNamespace(**vars(self.item("A")))
        del a.id
        self.assertTrue(self.analyze(a)["unresolved_records"])

    def test_quantity_is_per_entry_strict_integer_and_never_defaulted(self):
        for quantity, expected in ((1, 1), (2, 2), (True, None), (False, None),
                                   ("2", None), (2.0, None), (0, None), (-1, None),
                                   (None, None), ({}, None)):
            with self.subTest(quantity=quantity):
                result = self.analyze(self.item("A", quantity=quantity), self.item("B"))
                self.assertEqual(result["members"][0]["recorded_quantity"], expected)
                self.assertEqual(result["same_issue_record_count"], 2)
                self.assertNotIn("additional_copies", result)
        a = SimpleNamespace(**vars(self.item("A")))
        del a.quantity
        self.assertIsNone(self.analyze(a)["members"][0]["recorded_quantity"])

    def test_report_is_read_only_truthful_and_isolated_from_legacy_advice(self):
        items = [self.item("A", quantity=2), self.item("B"), self.item("C")]
        items[2].type_design = ""
        before = [vars(item).copy() for item in items]
        engine = CollectionIntelligenceEngine(items)
        with patch.object(engine, "detect_duplicates", side_effect=AssertionError), \
             patch.object(engine, "detect_upgrade_candidates", side_effect=AssertionError):
            markdown = engine.format_same_issue_report_markdown()
        self.assertEqual(before, [vars(item) for item in items])
        self.assertIn("same recorded issue/type", markdown)
        self.assertIn("2 distinct records", markdown)
        self.assertIn("recorded quantity: 2", markdown)
        self.assertIn('"C"', markdown)
        self.assertIn("Unresolved", markdown)
        self.assertIn("separate physical specimens are unverified", markdown)
        for forbidden in ("upgrade", "replacement", "sell", "trade", "not owned",
                          "not duplicate", "gap", "zero copies", "additional copies"):
            self.assertNotIn(forbidden, markdown.lower())


if __name__ == "__main__":
    unittest.main()
