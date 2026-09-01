"""Synthetic adversarial tests for Product Unit 8M-B."""

from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from backup_manager import BackupManager
from coin_collection import CoinCollection, CollectionLoadState
import migrate_legacy_collection_ids as migration


def record(item_id, *, year="1974", photos=None, image_path="", **changes):
    value = {
        "id": item_id,
        "image_path": image_path,
        "country": "Syntheticland",
        "denomination": "2 cents",
        "year": year,
        "grade": "VF",
        "notes": "synthetic only",
        "date_added": "2026-01-01",
        "numista_n": item_id.removeprefix("numista_") if item_id.startswith("numista_") else "",
        "photos": list(photos or []),
        "item_type": "COIN",
        "disposition": "UNDECIDED",
        "identification_status": "IDENTIFIED",
    }
    value.update(changes)
    return value


class LegacyCollectionIdMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.collection = self.root / "data" / "collection.json"
        self.collection.parent.mkdir(parents=True)
        self.private = self.root / "private"
        self.plan = self.private / "plan.json"
        self.report = self.private / "report.json"
        self.portable = self.private / "portable.zip"
        self.inventory = migration._default_inventory_descriptor(self.collection)

    def create_plan(self, plan_path=None, **kwargs):
        return migration.create_plan(
            str(self.collection), str(plan_path or self.plan),
            reference_inventory=self.inventory, **kwargs,
        )

    def write(self, rows, *, v1=True):
        payload = {"schema_version": 1, "items": rows} if v1 else rows
        self.collection.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return self.collection.read_bytes()

    def plan_rows(self, rows, **kwargs):
        before = self.write(rows, **kwargs)
        result = self.create_plan()
        self.assertEqual(before, self.collection.read_bytes())
        return result

    def apply(self):
        return migration.apply_plan(
            str(self.plan), str(self.report),
            safety_dir=str(self.private / "safety"),
            portable_backup_path=str(self.portable),
        )

    def test_two_years_rekey_every_occurrence_and_preserve_unique_record(self):
        rows = [record("numista_1558", year="1974"), record("unique", year="2000"), record("numista_1558", year="1983")]
        source = deepcopy(rows)
        plan = self.plan_rows(rows)

        self.assertEqual(2, len(plan["occurrences"]))
        self.assertEqual([0, 2], [row["source_index"] for row in plan["occurrences"]])
        self.assertTrue(all(row["new_id"].startswith("coin_") for row in plan["occurrences"]))
        report = self.apply()
        self.assertEqual("SUCCEEDED", report["status"])
        loaded = CoinCollection(str(self.collection))
        self.assertIs(loaded.load_state, CollectionLoadState.VALID)
        self.assertEqual(3, len(loaded.items))
        self.assertEqual("unique", loaded.items[1].id)
        self.assertEqual(["1974", "2000", "1983"], [item.year for item in loaded.items])
        self.assertEqual([row["numista_n"] for row in source], [item.numista_n for item in loaded.items])
        self.assertEqual(3, len({item.id for item in loaded.items}))

    def test_three_and_twenty_occurrences_remain_separate_in_order(self):
        for count in (3, 20):
            with self.subTest(count=count):
                rows = [record("numista_42", year=str(index)) for index in range(count)]
                plan_path = self.private / f"plan-{count}.json"
                self.write(rows)
                plan = self.create_plan(plan_path)
                self.assertEqual(count, len(plan["occurrences"]))
                self.assertEqual(list(range(count)), [row["source_index"] for row in plan["occurrences"]])
                self.assertEqual(count, len({row["new_id"] for row in plan["occurrences"]}))

    def test_identical_looking_records_are_not_merged(self):
        same = record("numista_99")
        plan = self.plan_rows([deepcopy(same), deepcopy(same)])
        self.assertNotEqual(plan["occurrences"][0]["new_id"], plan["occurrences"][1]["new_id"])
        self.apply()
        loaded = CoinCollection(str(self.collection))
        self.assertEqual(2, len(loaded.items))
        self.assertEqual(2, len({item.id for item in loaded.items}))

    def test_plan_records_source_digest_and_reuses_planned_ids(self):
        original = self.plan_rows([record("numista_7"), record("numista_7", year="1975")])
        source = self.collection.read_bytes()
        self.assertEqual(len(source), original["source_byte_length"])
        self.assertEqual(sha256(source).hexdigest(), original["source_sha256"])
        ids = [row["new_id"] for row in original["occurrences"]]
        self.apply()
        loaded = CoinCollection(str(self.collection))
        self.assertEqual(ids, [item.id for item in loaded.items])

    def test_source_change_after_plan_refuses_without_safety_or_report(self):
        self.plan_rows([record("numista_7"), record("numista_7", year="1975")])
        self.collection.write_bytes(self.collection.read_bytes() + b" ")
        with self.assertRaisesRegex(migration.MigrationRefused, "does not match"):
            self.apply()
        self.assertFalse(self.report.exists())
        self.assertFalse((self.private / "safety").exists())

    def test_valid_collection_is_not_applicable_and_plan_is_not_written(self):
        before = self.write([record("unique")])
        result = self.create_plan()
        self.assertEqual("NOT_APPLICABLE", result["status"])
        self.assertFalse(self.plan.exists())
        self.assertEqual(before, self.collection.read_bytes())

    def test_malformed_future_unrelated_and_nonlegacy_duplicates_refuse(self):
        cases = []
        cases.append(b"{")
        cases.append(json.dumps({"schema_version": 2, "items": []}).encode())
        bad = record("numista_1")
        bad["item_type"] = "TOKEN"
        cases.append(json.dumps({"schema_version": 1, "items": [bad, deepcopy(bad)]}).encode())
        cases.append(json.dumps({"schema_version": 1, "items": [record("bad"), record("bad")]}).encode())
        for index, payload in enumerate(cases):
            with self.subTest(index=index):
                self.collection.write_bytes(payload)
                target = self.private / f"refused-{index}.json"
                with self.assertRaises(migration.MigrationRefused):
                    self.create_plan(target)
                self.assertFalse(target.exists())
                self.assertEqual(payload, self.collection.read_bytes())

    def test_raw_safety_copy_is_verified_and_original_source_is_preserved(self):
        self.plan_rows([record("numista_8"), record("numista_8", year="1976")])
        source = self.collection.read_bytes()
        report = self.apply()
        safety = report["safety_copy"]
        copied = Path(safety["copy_path"]).read_bytes()
        self.assertEqual(source, copied)
        self.assertEqual(sha256(source).hexdigest(), safety["source_sha256"])
        self.assertEqual(safety["source_sha256"], safety["copy_sha256"])

    def test_external_legacy_image_path_is_preserved_and_reported(self):
        external = str(self.root / "external" / "photo.jpg")
        plan = self.plan_rows([
            record("numista_10", image_path=external),
            record("numista_10", year="1976"),
        ])
        self.assertIn("EXTERNAL_PRESERVED", plan["occurrences"][0]["media_classification"])
        report = self.apply()
        self.assertEqual("MIGRATED_WITH_PORTABILITY_BLOCKER", report["status"])
        payload = json.loads(self.collection.read_text(encoding="utf-8"))
        self.assertEqual(external, payload["items"][0]["image_path"])

    def test_ordinary_media_is_copied_per_new_owner_and_metadata_is_preserved(self):
        old = self.collection.parent / "managed_media" / "ordinary" / "numista_11" / "front.jpg"
        old.parent.mkdir(parents=True)
        old.write_bytes(b"synthetic-photo")
        photo = {"path": str(old), "role": "FRONT", "is_primary": True, "notes": "keep", "display_order": 0}
        self.plan_rows([
            record("numista_11", photos=[photo], image_path=str(old)),
            record("numista_11", year="1976", photos=[deepcopy(photo)], image_path=str(old)),
        ])
        planned = [row["new_id"] for row in json.loads(self.plan.read_text(encoding="utf-8"))["occurrences"]]
        self.apply()
        payload = json.loads(self.collection.read_text(encoding="utf-8"))["items"]
        paths = [Path(row["photos"][0]["path"]) for row in payload]
        self.assertTrue(old.exists())
        self.assertEqual(2, len(set(paths)))
        for index, path in enumerate(paths):
            self.assertEqual(b"synthetic-photo", path.read_bytes())
            self.assertEqual(planned[index], path.parent.name)
            self.assertEqual("FRONT", payload[index]["photos"][0]["role"])
            self.assertEqual("keep", payload[index]["photos"][0]["notes"])
            self.assertTrue(payload[index]["photos"][0]["is_primary"])

    def test_copy_failure_leaves_collection_unchanged(self):
        old = self.collection.parent / "managed_media" / "ordinary" / "numista_12" / "x.jpg"
        old.parent.mkdir(parents=True)
        old.write_bytes(b"x")
        self.plan_rows([record("numista_12", image_path=str(old)), record("numista_12", year="2")])
        before = self.collection.read_bytes()
        with patch.object(migration, "_exclusive_copy", side_effect=OSError("copy failed")):
            with self.assertRaisesRegex(OSError, "copy failed"):
                self.apply()
        self.assertEqual(before, self.collection.read_bytes())

    def test_persistence_failure_leaves_source_and_original_media(self):
        old = self.collection.parent / "managed_media" / "ordinary" / "numista_13" / "x.jpg"
        old.parent.mkdir(parents=True)
        old.write_bytes(b"x")
        self.plan_rows([record("numista_13", image_path=str(old)), record("numista_13", year="2")])
        before = self.collection.read_bytes()
        with patch.object(migration, "write_json_atomically", side_effect=OSError("persist failed")):
            with self.assertRaisesRegex(OSError, "persist failed"):
                self.apply()
        self.assertEqual(before, self.collection.read_bytes())
        self.assertEqual(b"x", old.read_bytes())
        for occurrence in json.loads(self.plan.read_text(encoding="utf-8"))["occurrences"]:
            for media in occurrence["media"]:
                if media["classification"] == "ORDINARY_MANAGED_COPY":
                    self.assertFalse(Path(media["planned_reference"]).exists())

    def test_colliding_capture_lineage_refuses_but_noncolliding_is_untouched(self):
        provenance = {
            "schema_version": "1.0",
            "import_id": str(uuid4()),
            "source_kind": "PROCESSED_SNAPSHOT",
            "package_sha256": "a" * 64,
            "processed_snapshot_id": str(uuid4()),
            "artifact_key": "coin/front",
            "artifact_sha256": "b" * 64,
            "variant": "NORMALIZED",
        }
        capture = {"path": str(self.root / "coin_photos" / "collection" / "imports" / provenance["import_id"] / "numista_14" / "front.jpg"), "capture_import_media": provenance}
        before = self.write([record("numista_14", photos=[capture]), record("numista_14", year="2")])
        with self.assertRaisesRegex(migration.MigrationRefused, "capture-import"):
            self.create_plan()
        self.assertEqual(before, self.collection.read_bytes())

        noncolliding = record("coin_" + uuid4().hex, photos=[capture])
        plan = self.plan_rows([record("numista_15"), record("numista_15", year="2"), noncolliding])
        self.assertEqual(2, len(plan["occurrences"]))
        self.assertEqual(noncolliding["id"], json.loads(self.collection.read_text(encoding="utf-8"))["items"][2]["id"])

    def test_active_reference_stores_with_shared_id_refuse_and_unrelated_files_do_not_change(self):
        before = self.write([record("numista_16"), record("numista_16", year="2")])
        app_state = self.root / "collection_data" / "app_state" / "app_state.json"
        app_state.parent.mkdir(parents=True)
        app_state.write_text(json.dumps({"photo_records": [{"linked_collection_item_id": "numista_16"}]}), encoding="utf-8")
        unrelated = self.root / "unrelated.bin"
        unrelated.write_bytes(b"unchanged")
        unrelated_hash = sha256(unrelated.read_bytes()).hexdigest()
        with self.assertRaisesRegex(migration.MigrationRefused, "ambiguous"):
            self.create_plan()
        self.assertEqual(before, self.collection.read_bytes())
        self.assertEqual(unrelated_hash, sha256(unrelated.read_bytes()).hexdigest())

    def test_photo_inbox_confirmed_observation_and_capture_reference_refuse(self):
        targets = [
            self.root / "data" / "photo_inbox_state.json",
            self.root / "collection_data" / "app_state" / "confirmed_observations.json",
            self.root / "active-capture-journal.json",
        ]
        payloads = [
            {"photo_sets": {"x": {"linked_item_id": "numista_17"}}},
            {"records": [{"collection_item_id": "numista_17"}]},
            {"desktop_item_ids": ["numista_17"]},
        ]
        for index, (target, payload) in enumerate(zip(targets, payloads)):
            with self.subTest(index=index):
                if self.plan.exists():
                    self.plan.unlink()
                for old in targets:
                    if old.exists():
                        old.unlink()
                self.write([record("numista_17"), record("numista_17", year="2")])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(payload), encoding="utf-8")
                kwargs = {"reference_paths": [str(target)]} if index == 2 else {}
                with self.assertRaises(migration.MigrationRefused):
                    self.create_plan(**kwargs)

    def test_verify_report_and_portable_restore_preserve_new_ids(self):
        self.plan_rows([record("numista_18"), record("numista_18", year="2")])
        report = self.apply()
        self.assertTrue(report["portable_backup_verified"])
        verified = migration.verify_report(str(self.report))
        self.assertTrue(verified["success"])
        expected = [item.id for item in CoinCollection(str(self.collection)).items]

        restored_path = self.root / "restored" / "data" / "collection.json"
        manager = BackupManager(
            backup_dir=str(self.root / "restored" / "backups"),
            collection_json_path=str(restored_path),
        )
        restored = manager.restore_from_backup_package(str(self.portable), overwrite=True)
        self.assertTrue(restored.success, restored.errors)
        restored_collection = CoinCollection(str(restored_path))
        self.assertEqual(expected, [item.id for item in restored_collection.items])

    def test_cli_plan_apply_verify(self):
        self.write([record("numista_19"), record("numista_19", year="2")])
        inventory_path = self.private / "inventory.json"
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(json.dumps(self.inventory), encoding="utf-8")
        self.assertEqual(0, migration.main([
            "plan", "--collection", str(self.collection), "--plan", str(self.plan),
            "--reference-inventory", str(inventory_path),
        ]))
        self.assertEqual(0, migration.main([
            "apply", "--plan", str(self.plan), "--report", str(self.report),
            "--safety-dir", str(self.private / "safety"), "--portable-backup", str(self.portable),
        ]))
        self.assertEqual(0, migration.main(["verify", "--report", str(self.report)]))

    def test_v0_source_promotes_without_losing_unicode_or_order(self):
        rows = [
            record("numista_20", year="昭和五年", notes="Épreuve synthétique"),
            record("numista_20", year="١٩٧٥", notes="اختبار"),
        ]
        self.plan_rows(rows, v1=False)
        self.apply()
        payload = json.loads(self.collection.read_text(encoding="utf-8"))
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual(["昭和五年", "١٩٧٥"], [row["year"] for row in payload["items"]])
        self.assertEqual(["Épreuve synthétique", "اختبار"], [row["notes"] for row in payload["items"]])

    def test_edited_plan_cannot_redirect_managed_media(self):
        old = self.collection.parent / "managed_media" / "ordinary" / "numista_21" / "x.jpg"
        old.parent.mkdir(parents=True)
        old.write_bytes(b"x")
        self.plan_rows([record("numista_21", image_path=str(old)), record("numista_21", year="2")])
        value = json.loads(self.plan.read_text(encoding="utf-8"))
        value["occurrences"][0]["media"][0]["planned_reference"] = str(self.root / "unrelated.txt")
        self.plan.write_text(json.dumps(value), encoding="utf-8")
        before = self.collection.read_bytes()
        with self.assertRaisesRegex(migration.MigrationRefused, "ownership"):
            self.apply()
        self.assertEqual(before, self.collection.read_bytes())
        self.assertFalse((self.root / "unrelated.txt").exists())

    def test_active_reference_change_after_plan_refuses_before_safety_copy(self):
        self.plan_rows([record("numista_22"), record("numista_22", year="2")])
        state = self.root / "collection_data" / "app_state" / "app_state.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({"photo_records": []}), encoding="utf-8")
        before = self.collection.read_bytes()
        with self.assertRaisesRegex(migration.MigrationRefused, "changed after planning"):
            self.apply()
        self.assertEqual(before, self.collection.read_bytes())
        self.assertFalse((self.private / "safety").exists())

    def test_tampered_staged_media_prevents_publication_and_is_retained(self):
        old = self.collection.parent / "managed_media" / "ordinary" / "numista_23" / "x.jpg"
        old.parent.mkdir(parents=True)
        old.write_bytes(b"original")
        self.plan_rows([record("numista_23", image_path=str(old)), record("numista_23", year="2")])
        before = self.collection.read_bytes()
        real_verify = migration._verify_receipts

        def tamper(receipts):
            first = next(row for row in receipts if row["created"])
            Path(first["path"]).write_bytes(b"tampered")
            real_verify(receipts)

        with patch.object(migration, "_verify_receipts", side_effect=tamper):
            with self.assertRaises(migration.MigrationRefused):
                self.apply()
        self.assertEqual(before, self.collection.read_bytes())
        planned = json.loads(self.plan.read_text(encoding="utf-8"))["occurrences"][0]["media"][0]["planned_reference"]
        self.assertEqual(b"tampered", Path(planned).read_bytes())

    def test_historical_backup_is_never_rewritten(self):
        historical = self.root / "backups" / "historical.json"
        historical.parent.mkdir()
        historical.write_text(json.dumps({"id": "numista_24"}), encoding="utf-8")
        before = historical.read_bytes()
        self.plan_rows([record("numista_24"), record("numista_24", year="2")])
        self.apply()
        self.assertEqual(before, historical.read_bytes())

    def test_postpublication_reload_failure_emits_recovery_report_without_rollback(self):
        self.plan_rows([record("numista_25"), record("numista_25", year="2")])
        original_class = migration.CoinCollection

        class InvalidReload:
            def __init__(self, _path):
                self.load_state = CollectionLoadState.INVALID_OR_UNSUPPORTED
                self.items = []

        with patch.object(migration, "CoinCollection", InvalidReload):
            with self.assertRaises(migration.MigrationRecoveryRequired):
                self.apply()
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual("RECOVERY_REQUIRED", report["status"])
        self.assertTrue(report["recovery_required"])
        # Publication is retained for explicit recovery rather than silently rolled back.
        self.assertIs(original_class(str(self.collection)).load_state, CollectionLoadState.VALID)

    def test_reference_inventory_is_mandatory_closed_and_serialized(self):
        self.write([record("numista_26"), record("numista_26", year="2")])
        with self.assertRaisesRegex(migration.MigrationRefused, "inventory is required"):
            migration.create_plan(str(self.collection), str(self.plan))
        plan = self.create_plan()
        self.assertEqual(self.inventory, plan["reference_inventory"])
        self.assertEqual(self.inventory, json.loads(self.plan.read_text(encoding="utf-8"))["reference_inventory"])

    def test_declared_external_capture_workspace_blocks_or_proceeds_and_revalidates(self):
        workspace = self.root / "external-capture"
        workspace.mkdir()
        journal = workspace / "journal.json"
        self.inventory["stores"].append({"kind": "CAPTURE_WORKSPACE_ROOTS", "path": str(workspace), "required": True})
        self.write([record("numista_27"), record("numista_27", year="2")])
        journal.write_text(json.dumps({"item_id": "numista_27"}), encoding="utf-8")
        with self.assertRaisesRegex(migration.MigrationRefused, "ambiguous"):
            self.create_plan()
        journal.write_text(json.dumps({"item_id": "clean"}), encoding="utf-8")
        self.create_plan()
        journal.write_text(json.dumps({"item_id": "changed"}), encoding="utf-8")
        with self.assertRaisesRegex(migration.MigrationRefused, "changed after planning"):
            self.apply()

    def test_required_declared_store_cannot_be_undeclared_or_absent(self):
        self.write([record("numista_28"), record("numista_28", year="2")])
        incomplete = deepcopy(self.inventory)
        incomplete["stores"] = [row for row in incomplete["stores"] if row["kind"] != "CAPTURE_WORKSPACE_ROOTS"]
        with self.assertRaisesRegex(migration.MigrationRefused, "omits required categories"):
            migration.create_plan(str(self.collection), str(self.plan), reference_inventory=incomplete)
        self.inventory["stores"].append({"kind": "ADDITIONAL_ACTIVE_PRODUCTION_STORE", "path": str(self.root / "missing-required"), "required": True})
        with self.assertRaisesRegex(migration.MigrationRefused, "required active reference store is absent"):
            self.create_plan()

    def test_source_and_destination_redirected_ancestors_fail_closed(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "x.jpg").write_bytes(b"x")
        old_root = self.collection.parent / "managed_media" / "ordinary" / "numista_29"
        old_root.parent.mkdir(parents=True)
        try:
            old_root.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"directory symlinks unavailable: {error}")
        self.write([record("numista_29", image_path=str(old_root / "x.jpg")), record("numista_29", year="2")])
        with self.assertRaisesRegex(migration.MigrationRefused, "unsafe link/reparse"):
            self.create_plan()

        old_root.unlink()
        old_root.mkdir()
        (old_root / "x.jpg").write_bytes(b"x")
        self.create_plan()
        planned = json.loads(self.plan.read_text(encoding="utf-8"))["occurrences"][0]["media"][0]["planned_reference"]
        new_root = Path(planned).parent
        new_root.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(migration.MigrationRefused, "redirected|unsafe link/reparse"):
            self.apply()
        self.assertFalse((self.private / "safety").exists())

    def test_nested_redirected_source_ancestor_fails_but_plain_directory_succeeds(self):
        old_root = self.collection.parent / "managed_media" / "ordinary" / "numista_30"
        old_root.mkdir(parents=True)
        outside = self.root / "outside-nested"
        outside.mkdir()
        (outside / "x.jpg").write_bytes(b"x")
        nested = old_root / "nested"
        try:
            nested.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"directory symlinks unavailable: {error}")
        self.write([record("numista_30", image_path=str(nested / "x.jpg")), record("numista_30", year="2")])
        with self.assertRaises(migration.MigrationRefused):
            self.create_plan()
        nested.unlink()
        nested.mkdir()
        (nested / "x.jpg").write_bytes(b"x")
        plan = self.create_plan()
        self.assertEqual("ORDINARY_MANAGED_COPY", plan["occurrences"][0]["media_classification"])

    def _cleanup_receipt(self, path):
        data = path.read_bytes()
        return {
            "path": str(path), "created": True,
            "identity": list(migration.path_object_identity(path)),
            "parent_identity": list(migration.path_object_identity(path.parent)),
            "byte_length": len(data), "sha256": sha256(data).hexdigest(),
        }

    def test_cleanup_reproves_identity_bytes_and_preserves_replaced_reused_or_tampered(self):
        parent = self.root / "cleanup"
        parent.mkdir()
        normal = parent / "normal.bin"
        normal.write_bytes(b"normal")
        normal_receipt = self._cleanup_receipt(normal)
        self.assertEqual([], migration._cleanup_created([normal_receipt]))
        self.assertFalse(normal.exists())

        for name, replacement in (("tampered", b"other"), ("identical-replacement", b"same")):
            parent.mkdir(exist_ok=True)
            path = parent / name
            original = b"same"
            path.write_bytes(original)
            receipt = self._cleanup_receipt(path)
            path.unlink()
            path.write_bytes(replacement)
            self.assertEqual([str(path)], migration._cleanup_created([receipt]))
            self.assertTrue(path.exists())

        reused = parent / "reused"
        reused.write_bytes(b"existing")
        receipt = self._cleanup_receipt(reused)
        receipt["created"] = False
        self.assertEqual([], migration._cleanup_created([receipt]))
        self.assertTrue(reused.exists())

    def test_cleanup_refusal_is_exposed_as_prepublication_evidence(self):
        old = self.collection.parent / "managed_media" / "ordinary" / "numista_31" / "x.jpg"
        old.parent.mkdir(parents=True)
        old.write_bytes(b"x")
        self.plan_rows([record("numista_31", image_path=str(old)), record("numista_31", year="2")])
        retained = str(self.root / "retained.bin")
        with patch.object(migration, "write_json_atomically", side_effect=OSError("persist")), patch.object(migration, "_cleanup_created", return_value=[retained]):
            with self.assertRaises(migration.MigrationRefused) as caught:
                self.apply()
        self.assertEqual([retained], caught.exception.evidence["cleanup_refusals"])

    def test_verify_gate_rejects_non_success_statuses_and_cli_is_nonzero(self):
        self.plan_rows([record("numista_32"), record("numista_32", year="2")])
        self.apply()
        original = json.loads(self.report.read_text(encoding="utf-8"))
        cases = [
            ("RECOVERY_REQUIRED", True, True),
            ("MIGRATED_WITH_PORTABILITY_BLOCKER", False, False),
            ("SUCCEEDED", False, False),
        ]
        for status, recovery, portable in cases:
            with self.subTest(status=status, recovery=recovery, portable=portable):
                changed = deepcopy(original)
                changed["status"] = status
                changed["recovery_required"] = recovery
                changed["portable_backup_verified"] = portable
                self.report.write_text(json.dumps(changed), encoding="utf-8")
                result = migration.verify_report(str(self.report))
                self.assertFalse(result["success"])
                self.assertNotEqual(0, migration.main(["verify", "--report", str(self.report)]))
        self.report.write_text(json.dumps(original), encoding="utf-8")
        self.assertTrue(migration.verify_report(str(self.report))["success"])

    def test_verify_requires_present_independently_valid_portable_package(self):
        self.plan_rows([record("numista_33"), record("numista_33", year="2")])
        self.apply()
        with patch.object(BackupManager, "verify_backup_package", return_value=SimpleNamespace(success=False, errors=["synthetic failure"])):
            with self.assertRaisesRegex(migration.MigrationRefused, "no longer verifies"):
                migration.verify_report(str(self.report))
        self.portable.unlink()
        with self.assertRaisesRegex(migration.MigrationRefused, "missing"):
            migration.verify_report(str(self.report))
        self.report.unlink()

    def test_postpublication_report_and_fallback_failure_is_unmistakable(self):
        self.plan_rows([record("numista_34"), record("numista_34", year="2")])
        stderr = io.StringIO()
        with patch.object(migration, "_write_json_exclusively", side_effect=OSError("report storage unavailable")), patch("sys.stderr", stderr):
            code = migration.main([
                "apply", "--plan", str(self.plan), "--report", str(self.report),
                "--safety-dir", str(self.private / "safety"),
                "--portable-backup", str(self.portable),
            ])
        self.assertNotEqual(0, code)
        self.assertIn("MAY ALREADY BE MIGRATED / RECOVERY REQUIRED", stderr.getvalue())
        self.assertIs(CoinCollection(str(self.collection)).load_state, CollectionLoadState.VALID)
        self.assertTrue(any((self.private / "safety").glob("*.json")))

    def test_report_path_race_after_publication_is_recovery_required_without_rollback(self):
        self.plan_rows([record("numista_35"), record("numista_35", year="2")])
        real_write = migration._write_json_exclusively

        def collide(path, payload):
            path = Path(path)
            if path == self.report and not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("occupied", encoding="utf-8")
            return real_write(path, payload)

        with patch.object(migration, "_write_json_exclusively", side_effect=collide):
            with self.assertRaisesRegex(migration.MigrationRecoveryRequired, "MAY ALREADY"):
                self.apply()
        self.assertIs(CoinCollection(str(self.collection)).load_state, CollectionLoadState.VALID)
        self.assertEqual("occupied", self.report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
