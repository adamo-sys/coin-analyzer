import unittest

from denomination_label_audit import (
    CANONICAL,
    PROPOSED,
    REVIEW,
    audit_denomination_labels,
)


class DenominationLabelAuditTests(unittest.TestCase):
    def test_aggregates_safe_aliases_without_mutating_records(self):
        records = [
            {"id": "private-1", "country": "Canada", "denomination": "One Cent"},
            {"id": "private-2", "country": "Canada", "denomination": "One Cent"},
            {"id": "private-3", "country": "Canada", "denomination": "1 cent"},
        ]
        original = [dict(record) for record in records]

        audit = audit_denomination_labels(records)

        self.assertEqual(records, original)
        self.assertEqual(audit.record_count, 3)
        by_label = {finding.current_label: finding for finding in audit.findings}
        self.assertEqual(by_label["One Cent"].status, PROPOSED)
        self.assertEqual(by_label["One Cent"].proposed_label, "1 cent")
        self.assertEqual(by_label["One Cent"].record_count, 2)
        self.assertEqual(by_label["1 cent"].status, CANONICAL)

    def test_ambiguous_or_unsupported_values_require_review(self):
        audit = audit_denomination_labels(
            [
                {"country": "Canada", "denomination": ""},
                {"country": "Canada", "denomination": 1.0},
                {"country": "Canada", "denomination": "$1"},
            ]
        )

        self.assertEqual({finding.status for finding in audit.findings}, {REVIEW})
        self.assertTrue(all(finding.proposed_label is None for finding in audit.findings))

    def test_uses_jurisdiction_specific_mapping(self):
        finding = audit_denomination_labels(
            [{"country": "Philippines", "denomination": "10 piso"}]
        ).findings[0]

        self.assertEqual(finding.status, PROPOSED)
        self.assertEqual(finding.proposed_label, "10 pesos")

    def test_output_is_deterministic_and_omits_private_fields(self):
        records = [
            {
                "id": "do-not-report",
                "country": "Canada",
                "denomination": "One Cent",
                "notes": "private note",
            },
            {"country": "Australia", "denomination": "1 cent"},
            {"country": "Canada", "denomination": "one cent"},
        ]

        first = audit_denomination_labels(records).format_text()
        second = audit_denomination_labels(reversed(records)).format_text()

        self.assertEqual(first, second)
        self.assertNotIn("do-not-report", first)
        self.assertNotIn("private note", first)
        self.assertIn("no collection data was changed", first)


if __name__ == "__main__":
    unittest.main()
