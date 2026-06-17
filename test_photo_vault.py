"""Tests for metadata-only Photo Vault."""

import os
import tempfile
import unittest

from coin_collection import CoinItem
from collection_dashboard import CollectionDashboard
from photo_vault import PhotoRecord, PhotoVault


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


if __name__ == "__main__":
    unittest.main()
