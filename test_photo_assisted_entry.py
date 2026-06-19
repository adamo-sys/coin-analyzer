"""Tests for v2.5 Photo-Assisted Entry."""

import json
import os
import tempfile
import unittest
import zipfile

from backup_manager import BackupManager
from coin_collection import CoinItem
from legacy_portfolio_importer import LegacyWantListIntent
from persistence_manager import AppState, PersistenceManager
from photo_assisted_entry import PhotoAssistedEntry, PhotoCandidate, PhotoReviewReport
from photo_vault import PhotoRecord


def make_item(item_id, country, denomination, year, grade):
    return CoinItem(
        id=item_id,
        image_path="",
        country=country,
        denomination=denomination,
        year=year,
        grade=grade,
        notes="",
        date_added="2026-06-18",
    )


def make_intent(target_coin):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id="photo-want-1",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Photo-assisted target",
        status="Active",
        priority_score=85,
    )


class TestPhotoAssistedEntry(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("1", "Newfoundland", "50 cents", "1900", "F-12"),
            make_item("2", "Canada", "1 cent", "1859", "VG-8"),
        ]
        self.want_list = [make_intent("Newfoundland 50 cents 1904")]

    def test_photo_candidate_creation(self):
        candidate = PhotoCandidate(
            title="Newfoundland 50 cents 1904 VF20",
            front_photo="front.jpg",
            reverse_photo="reverse.jpg",
            reference_photos=["ref1.jpg", "ref2.jpg"],
            asking_price="$120",
            notes="Dealer table candidate",
        )

        self.assertEqual(candidate.asking_price, 120.0)
        self.assertEqual(len(candidate.photo_references), 4)
        self.assertTrue(candidate.candidate_id.startswith("photo-"))
        self.assertNotIn("ocr", candidate.to_dict())

    def test_photo_linking_and_photo_vault_integration(self):
        engine = PhotoAssistedEntry(self.items, self.want_list)
        candidate = engine.create_candidate(
            "Newfoundland 50 cents 1904 VF20",
            front_photo="front.jpg",
            reverse_photo="reverse.jpg",
            reference_photos=["large-96-reference.jpg"],
        )

        linked = engine.link_candidate_photos(candidate)

        self.assertEqual(len(linked), 3)
        self.assertEqual(len(engine.photo_vault.records), 3)
        self.assertTrue(all(record.linked_candidate_id == candidate.candidate_id for record in linked))
        self.assertEqual(linked[0].photo_type, "Candidate Photo")
        self.assertEqual(linked[-1].photo_type, "Reference Photo")

    def test_mobile_companion_integration(self):
        candidate = PhotoCandidate(
            title="Newfoundland 50 cents 1904 VF20",
            front_photo="photo-1",
            asking_price=120,
            source="Coin shop",
        )
        mobile = candidate.to_mobile_entry()
        shopping = candidate.to_shopping_candidate()

        self.assertEqual(mobile.item_title, candidate.title)
        self.assertEqual(mobile.photo_reference_id, "photo-1")
        self.assertEqual(shopping.photo_reference_ids, ["photo-1"])
        self.assertEqual(shopping.recommendation_source, "Photo-Assisted Entry")

    def test_photo_review_report_generation(self):
        engine = PhotoAssistedEntry(self.items, self.want_list)
        candidate = engine.create_candidate(
            "Newfoundland 50 cents 1904 VF20",
            front_photo="front.jpg",
            reverse_photo="reverse.jpg",
            asking_price=120,
        )

        report = engine.analyze_candidate(candidate)

        self.assertIsInstance(report, PhotoReviewReport)
        self.assertEqual(len(report.attached_photos), 2)
        self.assertIn(report.mobile_analysis_report.recommendation, {"BUY", "PASS", "NEGOTIATE", "WATCH", "REVIEW"})
        self.assertIn("# Photo Review Report", report.format_markdown())
        self.assertTrue(any("Photo reference missing" in warning for warning in report.warnings))

    def test_photo_review_export_generation(self):
        engine = PhotoAssistedEntry(self.items, self.want_list)
        report = engine.analyze_candidate(engine.create_candidate(
            "Newfoundland 50 cents 1904 VF20",
            front_photo="front.jpg",
            asking_price=120,
        ))

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "photo-review.csv")
            md_path = os.path.join(temp_dir, "photo-review.md")

            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("photo_references", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("Recommendation Context", handle.read())

    def test_persistence_round_trip_for_photo_candidates(self):
        candidate = PhotoCandidate(
            title="Canada 1 cent 1859 VF20",
            front_photo="front.jpg",
            asking_price=60,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PersistenceManager(state_dir=os.path.join(temp_dir, "state"))
            saved = manager.save_state(AppState(photo_candidates=[candidate]))
            loaded = manager.load_state()

            self.assertTrue(saved.success)
            self.assertEqual(len(loaded.state.photo_candidates), 1)
            self.assertEqual(loaded.state.photo_candidates[0].title, candidate.title)
            self.assertEqual(loaded.state.photo_candidates[0].front_photo, "front.jpg")

    def test_backup_compatibility_metadata_only(self):
        candidate = PhotoCandidate(
            title="Newfoundland 50 cents 1904 VF20",
            front_photo="coin_photos/candidates/active/missing-front.jpg",
            asking_price=120,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = os.path.join(temp_dir, "collection_data", "app_state")
            data_dir = os.path.join(temp_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            collection_json = os.path.join(data_dir, "collection.json")
            with open(collection_json, "w", encoding="utf-8") as handle:
                json.dump([], handle)
            manager = PersistenceManager(state_dir=state_dir)
            manager.save_state(AppState(photo_candidates=[candidate]))
            backup = BackupManager(
                backup_dir=os.path.join(temp_dir, "backups"),
                persistence_manager=manager,
                collection_json_path=collection_json,
            )

            result = backup.create_backup_package()

            self.assertTrue(result.success)
            with zipfile.ZipFile(result.package_path, "r") as archive:
                names = archive.namelist()
                self.assertIn("collection_data/app_state/app_state.json", names)
                self.assertNotIn("coin_photos/candidates/active/missing-front.jpg", names)
                payload = json.loads(archive.read("collection_data/app_state/app_state.json").decode("utf-8"))
            self.assertEqual(payload["photo_candidates"][0]["front_photo"], candidate.front_photo)

    def test_existing_photo_records_are_reused(self):
        record = PhotoRecord(
            file_path="front.jpg",
            photo_type="Candidate Photo",
            linked_candidate_id="existing",
            linked_coin_name="Existing Candidate",
        )
        engine = PhotoAssistedEntry(self.items, self.want_list, photo_records=[record])

        self.assertEqual(len(engine.photo_vault.records), 1)
        report = engine.analyze_candidate(engine.create_candidate(
            "Canada 1 cent 1859 VF20",
            front_photo="front.jpg",
            asking_price=60,
        ))
        self.assertGreaterEqual(len(engine.photo_vault.records), 2)
        self.assertTrue(report.recommendation_context)


if __name__ == "__main__":
    unittest.main()
