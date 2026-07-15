"""Tests for v2.2 data safety and backup hardening."""

import json
import os
import tempfile
import unittest
import zipfile

from backup_manager import BackupManager, BackupManifest, CollectionRecoveryReport, DataSafetyValidator
from coin_collection import CoinItem
from confirmed_observations import ConfirmedObservationRecord, ConfirmedObservationStore, FeedbackCategory, ObservationOutcome
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from persistence_manager import AppState, PersistenceManager
from photo_assisted_entry import PhotoCandidate
from photo_vault import PhotoRecord
from smart_shopping_assistant import ShoppingCandidate


def make_managers(temp_dir):
    state_dir = os.path.join(temp_dir, "collection_data", "app_state")
    backup_dir = os.path.join(temp_dir, "backups", "packages")
    collection_json_path = os.path.join(temp_dir, "data", "collection.json")
    persistence = PersistenceManager(state_dir=state_dir)
    backup = BackupManager(
        backup_dir=backup_dir,
        persistence_manager=persistence,
        collection_json_path=collection_json_path,
    )
    return persistence, backup, collection_json_path


def write_collection_json(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump([{"id": "1", "country": "Newfoundland", "denomination": "20 cents", "year": "1900"}], handle)


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
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            persistence.save_state(AppState(app_preferences={"last_tool": "Collector Home"}))

            result = backup.create_backup_package()

            self.assertTrue(result.success)
            self.assertTrue(os.path.exists(result.package_path))
            self.assertTrue(result.manifest.included_files)
            self.assertEqual(result.manifest.collection_json_backed_up, "YES")
            self.assertEqual(result.manifest.app_state_backed_up, "YES")

    def test_backup_manifest_creation(self):
        manifest = BackupManifest(backup_created_at="2026-06-18 12:00:00", collection_json_backed_up="YES")
        payload = manifest.to_dict()
        restored = BackupManifest.from_dict(payload)

        self.assertEqual(restored.backup_created_at, "2026-06-18 12:00:00")
        self.assertEqual(restored.collection_json_backed_up, "YES")
        self.assertIn("# Backup Manifest", restored.format_markdown())
        self.assertIn("collection_json_backed_up: YES", restored.format_markdown())

    def test_backup_package_verification(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            persistence.save_state(AppState())
            package = backup.create_backup_package()

            verified = backup.verify_backup_package(package.package_path)

            self.assertTrue(verified.success)
            self.assertEqual(verified.status, "Backup verified")

    def test_backup_listing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            persistence.save_state(AppState())
            backup.create_backup_package()

            backups = backup.list_available_backups()

            self.assertEqual(len(backups), 1)
            self.assertTrue(backups[0]["name"].endswith(".zip"))

    def test_restore_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            persistence.save_state(AppState(app_preferences={"restore": "source"}))
            package = backup.create_backup_package()

            verified = backup.verify_backup_package(package.package_path)

            self.assertTrue(verified.success)
            self.assertIsNotNone(verified.manifest)

    def test_pre_restore_backup_creation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            persistence.save_state(AppState(app_preferences={"value": "original"}))
            package = backup.create_backup_package()
            persistence.save_state(AppState(app_preferences={"value": "current"}))

            result = backup.restore_from_backup_package(package.package_path, restore_root=temp_dir, overwrite=True)

            self.assertTrue(result.success)
            self.assertTrue(result.pre_restore_backup_path)
            self.assertTrue(os.path.exists(result.pre_restore_backup_path))

    def test_partial_restore_handling(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            persistence.save_state(AppState(app_preferences={"value": "original"}))
            package = backup.create_backup_package()
            persistence.save_state(AppState(app_preferences={"value": "current"}))

            result = backup.restore_from_backup_package(package.package_path, restore_root=temp_dir, overwrite=False)

            self.assertTrue(result.success)
            self.assertTrue(result.skipped_files)

    def test_corrupt_backup_handling(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _, backup, _ = make_managers(temp_dir)
            bad_path = os.path.join(temp_dir, "bad.zip")
            with open(bad_path, "w", encoding="utf-8") as handle:
                handle.write("not a zip")

            result = backup.verify_backup_package(bad_path)

            self.assertFalse(result.success)
            self.assertEqual(result.status, "Backup verification failed")

    def test_missing_app_state_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            os.makedirs(backup.backup_dir, exist_ok=True)

            report = DataSafetyValidator(persistence, backup.backup_dir, collection_json).validate()

            self.assertEqual(report.status, "WARNING")
            self.assertTrue(any(issue.area == "App State" for issue in report.issues))

    def test_missing_collection_workbook_path_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            os.makedirs(backup.backup_dir, exist_ok=True)
            missing = os.path.join(temp_dir, "missing.xlsx")
            persistence.save_state(AppState(collection_workbook_path=missing))

            report = DataSafetyValidator(persistence, backup.backup_dir, collection_json).validate()

            self.assertEqual(report.status, "WARNING")
            self.assertTrue(any("missing.xlsx" in issue.message for issue in report.issues))

    def test_missing_photo_references_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            os.makedirs(backup.backup_dir, exist_ok=True)
            missing_photo = os.path.join(temp_dir, "missing.jpg")
            persistence.save_state(AppState(photo_records=[PhotoRecord(missing_photo, "Collection Photo")]))

            report = DataSafetyValidator(persistence, backup.backup_dir, collection_json).validate()

            self.assertEqual(report.status, "WARNING")
            self.assertTrue(any(issue.area == "Photo Vault" for issue in report.issues))

    def test_photo_vault_audit_warnings_in_data_safety(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            os.makedirs(backup.backup_dir, exist_ok=True)
            persistence.save_state(AppState(
                photo_records=[
                    PhotoRecord("duplicate.jpg", "Candidate Photo", linked_candidate_id="one"),
                    PhotoRecord("duplicate.jpg", "Candidate Photo", linked_candidate_id="two"),
                ],
                photo_candidates=[PhotoCandidate("Candidate without photo")],
            ))

            report = DataSafetyValidator(persistence, backup.backup_dir, collection_json).validate()

            self.assertEqual(report.status, "WARNING")
            self.assertTrue(any("Duplicate Photo Reference" in issue.message for issue in report.issues))
            self.assertTrue(any("Candidate Without Photo" in issue.message for issue in report.issues))

    def test_data_safety_pass(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            os.makedirs(backup.backup_dir, exist_ok=True)
            persistence.save_state(AppState())
            backup.create_backup_package()

            report = DataSafetyValidator(persistence, backup.backup_dir, collection_json).validate()

            self.assertEqual(report.status, "PASS")

    def test_data_safety_fail_for_corrupt_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            os.makedirs(persistence.state_dir, exist_ok=True)
            os.makedirs(backup.backup_dir, exist_ok=True)
            with open(persistence.state_path, "w", encoding="utf-8") as handle:
                handle.write("{bad json")

            report = DataSafetyValidator(persistence, backup.backup_dir, collection_json).validate()

            self.assertEqual(report.status, "FAIL")

    def test_export_bundle_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _, backup, _ = make_managers(temp_dir)
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

    def test_collection_json_included_in_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            persistence.save_state(AppState())

            result = backup.create_backup_package()

            self.assertTrue(result.success)
            self.assertEqual(result.manifest.collection_json_backed_up, "YES")
            with zipfile.ZipFile(result.package_path, "r") as archive:
                self.assertIn("data/collection.json", archive.namelist())

    def test_confirmed_observations_are_included_and_verified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            persistence.save_state(AppState())
            store = ConfirmedObservationStore(os.path.join(
                persistence.state_dir,
                "confirmed_observations.json",
            ))
            observation = ConfirmedObservationRecord(
                observation_id="backup-observation",
                created_at="2026-07-15T12:00:00Z",
                outcome=ObservationOutcome.ACCEPTED,
                category=FeedbackCategory.OTHER,
                suggested_values={"year": "1907"},
                confirmed_values={"year": "1907"},
                engine_name="coin_recognition",
                engine_version="unknown",
                recognition_method="coin_recognition",
                application_version="v8.8.0",
                source_workflow="test",
            )
            self.assertTrue(store.append(observation).success)

            package = backup.create_backup_package()
            verified = backup.verify_backup_package(package.package_path)

            self.assertTrue(verified.success)
            self.assertTrue(any(
                record.archive_path == "collection_data/app_state/confirmed_observations.json"
                for record in package.manifest.included_files
            ))

    def test_missing_collection_json_reports_fail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            os.makedirs(backup.backup_dir, exist_ok=True)
            persistence.save_state(AppState())

            report = DataSafetyValidator(persistence, backup.backup_dir, collection_json).validate()

            self.assertEqual(report.status, "FAIL")
            self.assertTrue(any(issue.area == "Collection JSON" for issue in report.issues))

    def test_workbook_backup_success_from_persisted_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            workbook_path = os.path.join(temp_dir, "Adam_Collection_MASTER_Filled.xlsx")
            with open(workbook_path, "wb") as handle:
                handle.write(b"workbook bytes")
            persistence.save_state(AppState(
                collection_workbook_path=workbook_path,
                photo_records=[PhotoRecord("coin_photos/collection/nf.jpg", "Collection Photo")],
                photo_candidates=[PhotoCandidate("Newfoundland 50 cents 1904", front_photo="front.jpg")],
            ))

            result = backup.create_backup_package()

            self.assertTrue(result.success)
            self.assertEqual(result.manifest.workbook_backed_up, "YES")
            with zipfile.ZipFile(result.package_path, "r") as archive:
                self.assertIn("collection_workbook/Adam_Collection_MASTER_Filled.xlsx", archive.namelist())

    def test_missing_workbook_reports_warning_but_backup_succeeds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            missing_workbook = os.path.join(temp_dir, "missing.xlsx")
            persistence.save_state(AppState(collection_workbook_path=missing_workbook))

            result = backup.create_backup_package()

            self.assertTrue(result.success)
            self.assertEqual(result.manifest.workbook_backed_up, "NO")
            self.assertIn(missing_workbook, result.manifest.missing_files)
            self.assertTrue(any("workbook" in warning.lower() for warning in result.warnings))

    def test_manifest_reports_recovery_flags(self):
        manifest = BackupManifest(
            backup_created_at="2026-06-18 12:00:00",
            collection_json_backed_up=True,
            workbook_backed_up=False,
            app_state_backed_up=True,
        )

        payload = manifest.to_dict()
        restored = BackupManifest.from_dict(payload)

        self.assertEqual(payload["collection_json_backed_up"], "YES")
        self.assertEqual(payload["workbook_backed_up"], "NO")
        self.assertEqual(restored.app_state_backed_up, "YES")

    def test_collection_recovery_report_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            workbook_path = os.path.join(temp_dir, "collection.xlsx")
            with open(workbook_path, "wb") as handle:
                handle.write(b"workbook")
            persistence.save_state(AppState(collection_workbook_path=workbook_path))
            package = backup.create_backup_package()

            report = backup.collection_recovery_report(package.package_path)

            self.assertIsInstance(report, CollectionRecoveryReport)
            self.assertEqual(report.status, "PASS")
            self.assertEqual(report.collection_json_backed_up, "YES")
            self.assertTrue(any("ownership" in item for item in report.recoverable))
            self.assertIn("photo metadata stored in app state", report.recoverable)
            self.assertIn("photo candidate metadata stored in app state", report.recoverable)
            self.assertTrue(any("Photo files copied: NO" in warning for warning in report.warnings))

    def test_validator_warns_when_latest_backup_lacks_collection_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup, collection_json = make_managers(temp_dir)
            write_collection_json(collection_json)
            persistence.save_state(AppState())
            manifest = BackupManifest(backup_created_at="2026-06-18 12:00:00")
            package_path = os.path.join(backup.backup_dir, "legacy.zip")
            os.makedirs(backup.backup_dir, exist_ok=True)
            with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("backup_manifest.json", json.dumps(manifest.to_dict()))
                archive.writestr("backup_manifest.md", manifest.format_markdown())

            report = DataSafetyValidator(persistence, backup.backup_dir, collection_json).validate()

            self.assertEqual(report.status, "WARNING")
            self.assertTrue(any(issue.area == "Collection JSON Backup" for issue in report.issues))


if __name__ == "__main__":
    unittest.main()
