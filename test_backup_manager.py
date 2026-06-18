"""Tests for v2.2 data safety and backup hardening."""

import json
import os
import tempfile
import unittest

from backup_manager import BackupManager, BackupManifest, DataSafetyValidator
from coin_collection import CoinItem
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from persistence_manager import AppState, PersistenceManager
from photo_vault import PhotoRecord
from smart_shopping_assistant import ShoppingCandidate


def make_managers(temp_dir):
    state_dir = os.path.join(temp_dir, "collection_data", "app_state")
    backup_dir = os.path.join(temp_dir, "backups", "packages")
    persistence = PersistenceManager(state_dir=state_dir)
    backup = BackupManager(backup_dir=backup_dir, persistence_manager=persistence)
    return persistence, backup


def make_item():
    return CoinItem(
        id="1",
        image_path="",
        country="Newfoundland",
        denomination="20 cents",
        year="1900",
        grade="VF-20",
        notes="",
        date_added="2026-06-18",
    )


class TestBackupManager(unittest.TestCase):
    def test_backup_package_creation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_managers(temp_dir)
            persistence.save_state(AppState(app_preferences={"last_tool": "Collector Home"}))

            result = backup.create_backup_package()

            self.assertTrue(result.success)
            self.assertTrue(os.path.exists(result.package_path))
            self.assertTrue(result.manifest.included_files)

    def test_backup_manifest_creation(self):
        manifest = BackupManifest(backup_created_at="2026-06-18 12:00:00")
        payload = manifest.to_dict()
        restored = BackupManifest.from_dict(payload)

        self.assertEqual(restored.backup_created_at, "2026-06-18 12:00:00")
        self.assertIn("# Backup Manifest", restored.format_markdown())

    def test_backup_package_verification(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_managers(temp_dir)
            persistence.save_state(AppState())
            package = backup.create_backup_package()

            verified = backup.verify_backup_package(package.package_path)

            self.assertTrue(verified.success)
            self.assertEqual(verified.status, "Backup verified")

    def test_backup_listing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_managers(temp_dir)
            persistence.save_state(AppState())
            backup.create_backup_package()

            backups = backup.list_available_backups()

            self.assertEqual(len(backups), 1)
            self.assertTrue(backups[0]["name"].endswith(".zip"))

    def test_restore_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_managers(temp_dir)
            persistence.save_state(AppState(app_preferences={"restore": "source"}))
            package = backup.create_backup_package()

            verified = backup.verify_backup_package(package.package_path)

            self.assertTrue(verified.success)
            self.assertIsNotNone(verified.manifest)

    def test_pre_restore_backup_creation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_managers(temp_dir)
            persistence.save_state(AppState(app_preferences={"value": "original"}))
            package = backup.create_backup_package()
            persistence.save_state(AppState(app_preferences={"value": "current"}))

            result = backup.restore_from_backup_package(package.package_path, restore_root=temp_dir, overwrite=True)

            self.assertTrue(result.success)
            self.assertTrue(result.pre_restore_backup_path)
            self.assertTrue(os.path.exists(result.pre_restore_backup_path))

    def test_partial_restore_handling(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_managers(temp_dir)
            persistence.save_state(AppState(app_preferences={"value": "original"}))
            package = backup.create_backup_package()
            persistence.save_state(AppState(app_preferences={"value": "current"}))

            result = backup.restore_from_backup_package(package.package_path, restore_root=temp_dir, overwrite=False)

            self.assertTrue(result.success)
            self.assertTrue(result.skipped_files)

    def test_corrupt_backup_handling(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _, backup = make_managers(temp_dir)
            bad_path = os.path.join(temp_dir, "bad.zip")
            with open(bad_path, "w", encoding="utf-8") as handle:
                handle.write("not a zip")

            result = backup.verify_backup_package(bad_path)

            self.assertFalse(result.success)
            self.assertEqual(result.status, "Backup verification failed")

    def test_missing_app_state_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_managers(temp_dir)
            os.makedirs(backup.backup_dir, exist_ok=True)

            report = DataSafetyValidator(persistence, backup.backup_dir).validate()

            self.assertEqual(report.status, "WARNING")
            self.assertTrue(any(issue.area == "App State" for issue in report.issues))

    def test_missing_collection_workbook_path_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_managers(temp_dir)
            os.makedirs(backup.backup_dir, exist_ok=True)
            missing = os.path.join(temp_dir, "missing.xlsx")
            persistence.save_state(AppState(collection_workbook_path=missing))

            report = DataSafetyValidator(persistence, backup.backup_dir).validate()

            self.assertEqual(report.status, "WARNING")
            self.assertTrue(any("missing.xlsx" in issue.message for issue in report.issues))

    def test_missing_photo_references_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_managers(temp_dir)
            os.makedirs(backup.backup_dir, exist_ok=True)
            missing_photo = os.path.join(temp_dir, "missing.jpg")
            persistence.save_state(AppState(photo_records=[PhotoRecord(missing_photo, "Collection Photo")]))

            report = DataSafetyValidator(persistence, backup.backup_dir).validate()

            self.assertEqual(report.status, "WARNING")
            self.assertTrue(any(issue.area == "Photo Vault" for issue in report.issues))

    def test_data_safety_pass(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_managers(temp_dir)
            os.makedirs(backup.backup_dir, exist_ok=True)
            persistence.save_state(AppState())

            report = DataSafetyValidator(persistence, backup.backup_dir).validate()

            self.assertEqual(report.status, "PASS")

    def test_data_safety_fail_for_corrupt_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_managers(temp_dir)
            os.makedirs(persistence.state_dir, exist_ok=True)
            os.makedirs(backup.backup_dir, exist_ok=True)
            with open(persistence.state_path, "w", encoding="utf-8") as handle:
                handle.write("{bad json")

            report = DataSafetyValidator(persistence, backup.backup_dir).validate()

            self.assertEqual(report.status, "FAIL")

    def test_export_bundle_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _, backup = make_managers(temp_dir)
            output_dir = os.path.join(temp_dir, "bundle")
            market = MarketAwarenessEngine(
                observations=[ObservedPriceRecord("Newfoundland 20 cents 1900", "Newfoundland", "20 cents", "1900", "VF-20", 25, 3, "test")]
            )
            photos = [PhotoRecord("coin_photos/collection/Newfoundland/1900.jpg", "Collection Photo", linked_collection_item_id="1")]
            candidates = [ShoppingCandidate("Newfoundland 50 cents 1904", asking_price=120, shipping=5)]

            result = backup.export_collector_bundle(
                output_dir,
                items=[make_item()],
                shopping_candidates=candidates,
                market_awareness_engine=market,
                photo_records=photos,
            )

            self.assertTrue(result.success)
            self.assertTrue(os.path.exists(os.path.join(output_dir, "collection_health_report.md")))
            self.assertTrue(os.path.exists(os.path.join(output_dir, "collector_export_bundle_index.csv")))
            self.assertTrue(os.path.exists(os.path.join(output_dir, "backup_manifest.json")))


if __name__ == "__main__":
    unittest.main()
