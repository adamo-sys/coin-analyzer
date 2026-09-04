from __future__ import annotations

import inspect
import unittest

from denomination_label_audit import (
    DenominationAuditCategory,
    DenominationAuditRecord,
    audit_denomination_labels,
)
from coin_collection_gui import CoinCollectionGUI


class DenominationLabelAuditTests(unittest.TestCase):
    def test_equivalent_labels_aggregate_into_proposed_group(self) -> None:
        report = audit_denomination_labels(
            [
                DenominationAuditRecord("United States", "Two cents"),
                DenominationAuditRecord("USA", "2 cents"),
                DenominationAuditRecord("U.S.A.", "two cents"),
            ]
        )

        proposed = [
            finding
            for finding in report.findings
            if finding.category is DenominationAuditCategory.PROPOSED
        ]

        self.assertEqual(1, len(proposed))
        self.assertEqual("United States", proposed[0].jurisdiction)
        self.assertEqual("2 cents", proposed[0].canonical_denomination)
        self.assertEqual(2, proposed[0].count)
        self.assertEqual(
            ("Two cents", "two cents"),
            proposed[0].observed_labels,
        )

    def test_already_canonical_label_is_canonical(self) -> None:
        report = audit_denomination_labels(
            [DenominationAuditRecord("United States", "2 cents")]
        )

        self.assertEqual(1, len(report.findings))
        finding = report.findings[0]
        self.assertEqual(DenominationAuditCategory.CANONICAL, finding.category)
        self.assertEqual("2 cents", finding.canonical_denomination)

    def test_safe_alias_proposes_canonical_label(self) -> None:
        report = audit_denomination_labels(
            [DenominationAuditRecord("United States", "Two cents")]
        )

        finding = report.findings[0]
        self.assertEqual(DenominationAuditCategory.PROPOSED, finding.category)
        self.assertEqual("2 cents", finding.canonical_denomination)
        self.assertEqual(("Two cents",), finding.observed_labels)

    def test_unsupported_or_ambiguous_values_fail_closed_to_review(self) -> None:
        report = audit_denomination_labels(
            [
                DenominationAuditRecord("Canada", "25 cents"),
                DenominationAuditRecord("United States", "quarter-ish"),
                DenominationAuditRecord(None, None),
            ]
        )

        self.assertEqual(3, report.review_count)
        self.assertTrue(
            all(
                finding.category is DenominationAuditCategory.REVIEW
                for finding in report.findings
            )
        )

    def test_jurisdiction_specific_mapping_uses_canonical_context(self) -> None:
        report = audit_denomination_labels(
            [
                DenominationAuditRecord("Philippines", "10 piso"),
                DenominationAuditRecord("Philippines", "10 pesos"),
                DenominationAuditRecord("United States", "10 piso"),
            ]
        )

        proposed = next(
            finding
            for finding in report.findings
            if finding.category is DenominationAuditCategory.PROPOSED
            and finding.jurisdiction == "Philippines"
        )
        self.assertEqual("10 pesos", proposed.canonical_denomination)
        self.assertEqual(("10 piso",), proposed.observed_labels)

        self.assertTrue(
            any(
                finding.category is DenominationAuditCategory.REVIEW
                and finding.jurisdiction == "United States"
                for finding in report.findings
            )
        )

    def test_output_is_deterministic_independent_of_input_order(self) -> None:
        records = [
            DenominationAuditRecord("United States", "Two cents"),
            DenominationAuditRecord("Philippines", "10 piso"),
            DenominationAuditRecord("United States", "2 cents"),
            DenominationAuditRecord("Canada", "25 cents"),
        ]

        forward = audit_denomination_labels(records)
        reverse = audit_denomination_labels(reversed(records))

        self.assertEqual(forward, reverse)
        self.assertEqual(forward.to_dict(), reverse.to_dict())
        self.assertEqual(forward.format_text(), reverse.format_text())

    def test_boundary_omits_private_and_unrelated_fields(self) -> None:
        record = DenominationAuditRecord("United States", "2 cents")

        self.assertEqual(
            {
                "jurisdiction": "United States",
                "denomination": "2 cents",
            },
            record.to_dict(),
        )

        for forbidden in (
            "id",
            "notes",
            "image_path",
            "photos",
            "year",
            "grade",
            "date_added",
        ):
            self.assertFalse(hasattr(record, forbidden))

    def test_source_records_remain_unchanged(self) -> None:
        records = (
            DenominationAuditRecord("United States", "Two cents"),
            DenominationAuditRecord("Philippines", "10 piso"),
        )
        before = tuple(record.to_dict() for record in records)

        audit_denomination_labels(records)

        after = tuple(record.to_dict() for record in records)
        self.assertEqual(before, after)

    def test_desktop_projection_passes_only_allowed_fields(self) -> None:
        source = inspect.getsource(CoinCollectionGUI.open_denomination_label_audit)

        self.assertIn("item.country", source)
        self.assertIn("item.denomination", source)
        self.assertIn("DenominationAuditRecord", source)

        for forbidden in (
            "item.id",
            "item.notes",
            "item.image_path",
            "item.photos",
            "item.year",
            "item.grade",
            "item.to_dict",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()


