"""Tests for metadata-only Photo Vault."""

import os
import tempfile
import unittest

from coin_collection import CoinItem, ItemPhoto, PhotoRole
from collection_dashboard import CollectionDashboard
from photo_assisted_entry import PhotoCandidate
from photo_vault import PhotoRecord, PhotoVault, PhotoVaultIntegrityAudit


def make_item(item_id, country, denomination, year, grade, **overrides):
    data = {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": grade,
        "notes": "",
        "date_added": "2026-06-17",
    }
    data.update(overrides)
    return CoinItem(**data)


class TestPhotoVault(unittest.TestCase):
    def setUp(self):
        self.collection_item = make_item(
            "nfld_1945_5c",
            "Newfoundland",
            "5 cents",
            "1945",
            "AU-55",
            notes="ICCS certified XSZ431",
        )
        self.raw_item = make_item("nfld_1904h_50c", "Newfoundland", "50 cents", "1904", "EF-40")

    def test_photo_record_creation(self):
        record = PhotoRecord(
            file_path="coin_photos/collection/Newfoundland/1945_5c_obv.jpg",
            photo_type="Collection Photo",
            linked_collection_item_id="nfld_1945_5c",
            linked_coin_name="Newfoundland 1945 5 cents AU55",
            iccs_number="xsz431",
        )

        self.assertEqual(record.photo_type, "Collection Photo")
        self.assertEqual(record.iccs_number, "XSZ431")
        self.assertTrue(record.created_date)

    def test_collection_photo_linking(self):
        vault = PhotoVault(collection_items=[self.collection_item])
        record = vault.link_collection_photo(
            "coin_photos/collection/Newfoundland/1945_5c_obv.jpg",
            self.collection_item,
            iccs_number="XSZ431",
        )

        self.assertEqual(record.linked_collection_item_id, "nfld_1945_5c")
        status = vault.collection_photo_statuses()[0]
        self.assertTrue(status.has_photos)
        self.assertEqual(status.photo_count, 1)
        self.assertIn("XSZ431", status.certification_numbers)

    def test_candidate_photo_linking(self):
        vault = PhotoVault()
        record = vault.link_candidate_photo(
            "coin_photos/candidates/active/listing_123.jpg",
            candidate_id="listing_123",
            coin_name="Newfoundland 1904H 50 cents EF40",
            notes="Active auction",
        )

        self.assertEqual(record.photo_type, "Candidate Photo")
        self.assertEqual(record.linked_candidate_id, "listing_123")
        self.assertIn("active", vault.expected_folder_for_type("Candidate Photo"))

    def test_reference_photo_linking(self):
        vault = PhotoVault()
        record = vault.link_reference_photo(
            "coin_photos/references/1859_wide_9.jpg",
            "1859 Large Cent Wide 9",
            notes="Wide 9 reference",
        )

        self.assertEqual(record.photo_type, "Reference Photo")
        self.assertIn("Wide 9", record.notes)

    def test_certification_lookup(self):
        vault = PhotoVault([
            PhotoRecord(
                "coin_photos/collection/Newfoundland/1945_5c_obv.jpg",
                "Collection Photo",
                linked_collection_item_id="nfld_1945_5c",
                linked_coin_name="1945 Newfoundland 5 cents AU55",
                iccs_number="XSZ431",
            )
        ])

        matches = vault.find_by_certification_number("xsz431")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].linked_coin_name, "1945 Newfoundland 5 cents AU55")

    def test_dashboard_integration(self):
        records = [
            PhotoRecord(
                "coin_photos/collection/Newfoundland/1945_5c_obv.jpg",
                "Collection Photo",
                linked_collection_item_id="nfld_1945_5c",
                linked_coin_name="1945 Newfoundland 5 cents AU55",
                iccs_number="XSZ431",
            )
        ]

        data = CollectionDashboard([self.collection_item, self.raw_item], photo_records=records).generate_dashboard()

        self.assertIsNotNone(data.photo_coverage)
        self.assertEqual(data.photo_coverage.items_with_photos, 1)
        self.assertEqual(data.photo_coverage.items_without_photos, 1)
        self.assertEqual(data.photo_coverage.photo_coverage_percentage, 50.0)

    def test_search_functionality(self):
        vault = PhotoVault([
            PhotoRecord(
                "coin_photos/references/large_96.jpg",
                "Reference Photo",
                linked_coin_name="Large 96",
                notes="Large 96 reference image",
            ),
            PhotoRecord(
                "coin_photos/sold/sold_1945_5c.jpg",
                "Sold Photo",
                linked_coin_name="1945 Newfoundland 5 cents",
                notes="Sold example",
            ),
        ])

        self.assertEqual(len(vault.search("large_96")), 1)
        self.assertEqual(len(vault.search("sold example")), 1)
        self.assertEqual(len(vault.search("Newfoundland")), 1)

    def test_export_support(self):
        vault = PhotoVault([
            PhotoRecord(
                "coin_photos/collection/Newfoundland/1945_5c_obv.jpg",
                "Collection Photo",
                linked_collection_item_id="nfld_1945_5c",
                linked_coin_name="1945 Newfoundland 5 cents AU55",
                iccs_number="XSZ431",
            )
        ], collection_items=[self.collection_item])
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "photo_vault.csv")
            md_path = os.path.join(temp_dir, "photo_vault.md")

            self.assertTrue(vault.export_csv(csv_path))
            self.assertTrue(vault.export_markdown(md_path))

            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("XSZ431", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("# Photo Vault", handle.read())

    def test_missing_photo_reference_detection(self):
        report = PhotoVaultIntegrityAudit([
            PhotoRecord("missing_photo.jpg", "Collection Photo", linked_collection_item_id="nfld_1945_5c"),
        ], [self.collection_item]).run()

        self.assertEqual(report.missing_photo_references, 1)
        self.assertTrue(any(issue.issue_type == "Missing Photo Reference" for issue in report.findings))

    def test_duplicate_photo_reference_detection(self):
        records = [
            PhotoRecord("same.jpg", "Collection Photo", linked_collection_item_id="nfld_1945_5c"),
            PhotoRecord("same.jpg", "Candidate Photo", linked_candidate_id="candidate-1"),
        ]

        report = PhotoVaultIntegrityAudit(records, [self.collection_item]).run()

        self.assertEqual(report.duplicate_photo_references, 1)
        self.assertTrue(any(issue.issue_type == "Duplicate Photo Reference" for issue in report.findings))

    def test_unlinked_photo_detection(self):
        report = PhotoVaultIntegrityAudit([
            PhotoRecord("unlinked.jpg", "Reference Photo"),
        ]).run()

        self.assertTrue(any(issue.issue_type == "Unlinked Photo Record" for issue in report.findings))

    def test_collection_item_without_photo_detection(self):
        report = PhotoVaultIntegrityAudit([], [self.collection_item, self.raw_item]).run()

        self.assertEqual(report.collection_photo_coverage_percentage, 0.0)
        self.assertTrue(any(issue.issue_type == "Collection Item Without Photo" for issue in report.findings))

    def test_certified_item_without_photo_detection(self):
        report = PhotoVaultIntegrityAudit([], [self.collection_item]).run()

        self.assertEqual(report.certified_item_photo_coverage_percentage, 0.0)
        self.assertTrue(any(issue.issue_type == "Certified Item Without Photo" for issue in report.findings))

    def test_candidate_photo_coverage(self):
        candidates = [
            PhotoCandidate("Newfoundland 50 cents 1904", front_photo="front.jpg"),
            PhotoCandidate("Canada 1 cent 1859"),
        ]

        report = PhotoVaultIntegrityAudit([], photo_candidates=candidates).run()

        self.assertEqual(report.candidate_photo_coverage_percentage, 50.0)
        self.assertTrue(any(issue.issue_type == "Candidate Without Photo" for issue in report.findings))
        self.assertTrue(any(issue.issue_type == "Missing Reverse Photo" for issue in report.findings))

    def test_invalid_extension_detection(self):
        report = PhotoVaultIntegrityAudit([
            PhotoRecord("photo.txt", "Candidate Photo", linked_candidate_id="candidate-1"),
        ]).run()

        self.assertTrue(any(issue.issue_type == "Invalid File Extension" for issue in report.findings))

    def test_unsupported_path_detection(self):
        report = PhotoVaultIntegrityAudit([
            PhotoRecord("https://example.com/photo.jpg", "Candidate Photo", linked_candidate_id="candidate-1"),
        ]).run()

        self.assertTrue(any(issue.issue_type == "Unsupported File Path" for issue in report.findings))

    def test_search_by_filename_certification_and_type(self):
        vault = PhotoVault([
            PhotoRecord(
                "coin_photos/collection/Newfoundland/1945_5c_slab.jpg",
                "Collection Photo",
                linked_coin_name="1945 Newfoundland 5 cents AU55",
                notes="Slab image",
                iccs_number="XSZ431",
            )
        ])

        self.assertEqual(len(vault.search("1945_5c_slab")), 1)
        self.assertEqual(len(vault.search("Collection Photo")), 1)
        self.assertEqual(len(vault.find_by_certification_number("xsz431")), 1)

    def test_photo_coverage_export_generation(self):
        report = PhotoVaultIntegrityAudit([
            PhotoRecord("missing.jpg", "Candidate Photo", linked_candidate_id="candidate-1"),
        ]).run()

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "photo_audit.csv")
            md_path = os.path.join(temp_dir, "photo_audit.md")

            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("issue_type", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("# Photo Vault Audit", handle.read())

    def test_item_owned_photos_count_for_collection_coverage(self):
        item = make_item(
            "with_owned_photo",
            "Canada",
            "1 cent",
            "1920",
            "VF-20",
            image_path="owned_front.jpg",
            photos=[ItemPhoto("owned_front.jpg", PhotoRole.FRONT, True, "", 0)],
        )

        summary = PhotoVault(collection_items=[item]).coverage_summary()

        self.assertEqual(summary.items_with_photos, 1)
        self.assertEqual(summary.items_without_photos, 0)
        self.assertEqual(summary.total_photos, 1)

    def test_photo_vault_still_supports_supplemental_photo_records(self):
        self.collection_item.image_path = "owned.jpg"
        record = PhotoRecord("supplemental.jpg", "Collection Photo", linked_collection_item_id="nfld_1945_5c")

        summary = PhotoVault([record], [self.collection_item]).coverage_summary()

        self.assertEqual(summary.items_with_photos, 1)
        self.assertEqual(summary.total_photos, 2)

    def test_item_owned_missing_duplicate_and_invalid_photo_paths_are_audited(self):
        item = make_item(
            "audit_photos",
            "Canada",
            "1 cent",
            "1920",
            "VF-20",
            image_path="missing.txt",
            photos=[
                ItemPhoto("missing.txt", PhotoRole.FRONT, True, "", 0),
                ItemPhoto("missing.txt", PhotoRole.BACK, False, "", 1),
            ],
        )

        report = PhotoVaultIntegrityAudit(collection_items=[item]).run()
        issue_types = [issue.issue_type for issue in report.findings]

        self.assertIn("Missing Photo Reference", issue_types)
        self.assertIn("Duplicate Photo Reference", issue_types)
        self.assertIn("Invalid File Extension", issue_types)
        self.assertFalse(any(issue.issue_type == "Collection Item Without Photo" for issue in report.findings))

    def test_photo_vault_search_indexes_item_owned_photos(self):
        item = make_item(
            "search_photo",
            "Canada",
            "1 cent",
            "1920",
            "VF-20",
            image_path="coin_photos/collection/Canada/searchable_front.jpg",
        )

        matches = PhotoVault(collection_items=[item]).search("searchable_front")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].linked_collection_item_id, "search_photo")


if __name__ == "__main__":
    unittest.main()
