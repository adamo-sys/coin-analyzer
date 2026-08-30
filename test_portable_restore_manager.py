"""Focused Product Unit 5C staged portable restore tests."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import backup_manager
from backup_manager import BackupManager
from coin_collection import (
    CaptureImportMediaProvenance,
    CoinCollection,
    CoinItem,
    CollectionFormat,
    CollectionLoadState,
    ItemPhoto,
    ItemType,
    PhotoRole,
    serialize_collection_payload,
)


IMPORT_ID = "11111111-1111-4111-8111-111111111111"
SNAPSHOT_ID = "22222222-2222-4222-8222-222222222222"
OWNER_TOKEN = "33333333-3333-4333-8333-333333333333"
CAPTURE_ITEM_ID = "44444444-4444-4444-8444-444444444444"


class PortableRestoreManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source_root = self.root / "source"
        self.destination_root = self.root / "destination"
        self.source_collection = self.source_root / "data" / "collection.json"
        self.destination_collection = self.destination_root / "data" / "collection.json"
        self.source = BackupManager(
            backup_dir=str(self.source_root / "backups"),
            collection_json_path=str(self.source_collection),
        )
        self.destination = BackupManager(
            backup_dir=str(self.destination_root / "backups"),
            collection_json_path=str(self.destination_collection),
        )

    @staticmethod
    def _item(
        item_id: str,
        *,
        item_type: ItemType = ItemType.COIN,
        photos: list[ItemPhoto] | None = None,
        notes: str = "collector notes",
    ) -> CoinItem:
        return CoinItem(
            id=item_id,
            image_path="",
            country="Canada",
            denomination="One Dollar",
            year="1967",
            grade="VF",
            notes=notes,
            date_added="2026-08-30",
            item_type=item_type,
            photos=list(photos or []),
        )

    @staticmethod
    def _write_v1(path: Path, items: list[CoinItem]) -> bytes:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps(serialize_collection_payload(items), indent=2, ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        path.write_bytes(payload)
        return payload

    def _ordinary_photo(
        self, item_id: str, name: str, content: bytes
    ) -> ItemPhoto:
        path = (
            self.source_collection.parent / "managed_media" / "ordinary"
            / item_id / name
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return ItemPhoto(str(path), PhotoRole.FRONT, True, "photo notes", 0)

    def _capture_photo(self, content: bytes) -> ItemPhoto:
        root = (
            self.source_root / "coin_photos" / "collection" / "imports"
            / IMPORT_ID
        )
        path = root / CAPTURE_ITEM_ID / "front.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        (root / ".import-owner.json").write_text(json.dumps({
            "ownership_schema_version": "1.0",
            "import_id": IMPORT_ID,
            "random_ownership_token": OWNER_TOKEN,
        }, sort_keys=True), encoding="utf-8")
        return ItemPhoto(
            str(path), PhotoRole.FRONT, True, "capture notes", 0,
            CaptureImportMediaProvenance(
                schema_version="1.0",
                import_id=IMPORT_ID,
                source_kind="PROCESSED_SNAPSHOT",
                package_sha256="a" * 64,
                processed_snapshot_id=SNAPSHOT_ID,
                artifact_key="coin/front",
                artifact_sha256=sha256(content).hexdigest(),
                variant="NORMALIZED",
            ),
        )

    def _existing_capture_root(
        self, owner: bytes | None, media: bytes = b"capture"
    ) -> tuple[Path, Path]:
        root = (
            self.destination_root / "coin_photos" / "collection" / "imports"
            / IMPORT_ID
        )
        media_path = root / CAPTURE_ITEM_ID / "front.jpg"
        media_path.parent.mkdir(parents=True)
        media_path.write_bytes(media)
        if owner is not None:
            (root / ".import-owner.json").write_bytes(owner)
        return root, media_path

    def _package(self, items: list[CoinItem], *, legacy_v0: bool = False) -> Path:
        self.source_collection.parent.mkdir(parents=True, exist_ok=True)
        if legacy_v0:
            self.source_collection.write_text(
                json.dumps([item.to_dict() for item in items]), encoding="utf-8"
            )
        else:
            self._write_v1(self.source_collection, items)
        package = self.source_root / "portable.zip"
        result = self.source.create_portable_backup_package(str(package))
        self.assertTrue(result.success, result.errors)
        return package

    def _restore(self, package: Path):
        return self.destination.restore_from_backup_package(
            str(package), restore_root=str(self.destination_root), overwrite=True
        )

    @staticmethod
    def _rewrite_package(package: Path, mutate) -> None:
        with zipfile.ZipFile(package, "r") as source:
            rows = [(info.filename, source.read(info)) for info in source.infolist()]
        replacement = package.with_suffix(".replacement.zip")
        with zipfile.ZipFile(replacement, "w", zipfile.ZIP_DEFLATED) as target:
            for name, content in mutate(rows):
                target.writestr(name, content)
        os.replace(replacement, package)

    def _current(self, items: list[CoinItem] | None = None) -> bytes:
        return self._write_v1(
            self.destination_collection,
            items or [self._item("current", notes="current remains")],
        )

    def test_valid_mixed_restore_preserves_ids_values_and_ordinary_media(self) -> None:
        coin_photo = self._ordinary_photo("coin-stable", "front.jpg", b"coin")
        package = self._package([
            self._item("coin-stable", photos=[coin_photo], notes="coin value"),
            self._item("note-stable", item_type=ItemType.BANKNOTE, notes="note value"),
        ])

        result = self._restore(package)

        self.assertTrue(result.success, result.errors)
        loaded = CoinCollection(str(self.destination_collection))
        self.assertEqual(CollectionLoadState.VALID, loaded.load_state)
        self.assertEqual(["coin-stable", "note-stable"], [item.id for item in loaded.items])
        self.assertEqual(["coin value", "note value"], [item.notes for item in loaded.items])
        restored_photo = Path(loaded.items[0].photos[0].path)
        self.assertEqual(b"coin", restored_photo.read_bytes())
        self.assertTrue(restored_photo.is_relative_to(
            self.destination_collection.parent / "managed_media" / "ordinary"
        ))
        self.assertEqual("MISSING", result.pre_restore_safety_status)

    def test_photo_free_restore_and_source_package_can_disappear(self) -> None:
        package = self._package([self._item("photo-free")])

        result = self._restore(package)
        package.unlink()

        self.assertTrue(result.success, result.errors)
        loaded = CoinCollection(str(self.destination_collection))
        self.assertEqual("photo-free", loaded.items[0].id)
        self.assertEqual([], loaded.items[0].photos)

    def test_capture_media_owner_and_provenance_restore(self) -> None:
        package = self._package([
            self._item(CAPTURE_ITEM_ID, photos=[self._capture_photo(b"capture")])
        ])

        result = self._restore(package)

        self.assertTrue(result.success, result.errors)
        loaded = CoinCollection(str(self.destination_collection))
        photo = loaded.items[0].photos[0]
        self.assertEqual(IMPORT_ID, photo.capture_import_media.import_id)
        self.assertEqual(b"capture", Path(photo.path).read_bytes())
        owner = Path(photo.path).parents[1] / ".import-owner.json"
        self.assertEqual(IMPORT_ID, json.loads(owner.read_text())["import_id"])

    def test_identical_owned_media_is_reused_and_not_cleaned(self) -> None:
        package = self._package([
            self._item("reused", photos=[self._ordinary_photo("reused", "front.jpg", b"same")])
        ])
        existing = (
            self.destination_collection.parent / "managed_media" / "ordinary"
            / "reused" / "front.jpg"
        )
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"same")
        identity = os.stat(existing, follow_symlinks=False)

        result = self._restore(package)

        self.assertTrue(result.success, result.errors)
        after = os.stat(existing, follow_symlinks=False)
        self.assertEqual((identity.st_dev, identity.st_ino), (after.st_dev, after.st_ino))
        self.assertIn(str(existing), result.skipped_files)

    def test_invalid_package_fails_before_safety_or_live_mutation(self) -> None:
        package = self._package([self._item("incoming")])
        previous = self._current()
        package.write_bytes(b"not a zip")

        result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual("", result.pre_restore_backup_path)
        self.assertEqual(previous, self.destination_collection.read_bytes())

    def test_staged_hash_mismatch_fails_without_live_mutation(self) -> None:
        package = self._package([self._item("incoming")])
        previous = self._current()
        real_read = backup_manager._read_stable_regular_file

        def corrupt_staged(path, label):
            payload = real_read(path, label)
            if label.startswith("Staged portable member portable/collection"):
                return payload + b" "
            return payload

        with patch("backup_manager._read_stable_regular_file", side_effect=corrupt_staged):
            result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual(previous, self.destination_collection.read_bytes())
        self.assertEqual("", result.pre_restore_backup_path)

    def test_packaged_collection_semantic_mismatch_fails_before_staging(self) -> None:
        package = self._package([self._item("incoming")])
        previous = self._current()

        def replace_collection(rows):
            replacement = b"{}"
            digest = sha256(replacement).hexdigest()
            changed = []
            for name, content in rows:
                if name == "portable/collection/collection.json":
                    content = replacement
                elif name == backup_manager.MANIFEST_NAME:
                    manifest = json.loads(content)
                    manifest["authoritative_collection"]["byte_length"] = len(replacement)
                    manifest["authoritative_collection"]["sha256"] = digest
                    member = next(
                        row for row in manifest["members"]
                        if row["member_type"] == "authoritative_collection"
                    )
                    member["byte_length"] = len(replacement)
                    member["sha256"] = digest
                    content = json.dumps(manifest).encode("utf-8")
                changed.append((name, content))
            return changed

        self._rewrite_package(package, replace_collection)
        result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual("", result.pre_restore_backup_path)
        self.assertEqual(previous, self.destination_collection.read_bytes())

    def test_staged_collection_semantic_mismatch_fails_without_live_mutation(self) -> None:
        package = self._package([self._item("incoming")])
        previous = self._current()
        real_read = backup_manager._read_stable_regular_file
        replacement = b"{}"
        replacement_digest = sha256(replacement).hexdigest()

        def make_staged_package_semantically_invalid(path, label):
            payload = real_read(path, label)
            if label == "Staged portable member portable/collection/collection.json":
                return replacement
            if label == f"Staged portable member {backup_manager.MANIFEST_NAME}":
                manifest = json.loads(payload)
                manifest["authoritative_collection"]["byte_length"] = len(replacement)
                manifest["authoritative_collection"]["sha256"] = replacement_digest
                member = next(
                    row for row in manifest["members"]
                    if row["member_type"] == "authoritative_collection"
                )
                member["byte_length"] = len(replacement)
                member["sha256"] = replacement_digest
                return json.dumps(manifest).encode("utf-8")
            return payload

        with patch(
            "backup_manager._read_stable_regular_file",
            side_effect=make_staged_package_semantically_invalid,
        ):
            result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual("", result.pre_restore_backup_path)
        self.assertEqual(previous, self.destination_collection.read_bytes())
        self.assertIn("INVALID_OR_UNSUPPORTED", " ".join(result.errors))

    def test_missing_staged_required_media_fails_before_publication(self) -> None:
        package = self._package([
            self._item("missing-stage", photos=[
                self._ordinary_photo("missing-stage", "front.jpg", b"media")
            ])
        ])
        previous = self._current()
        original_stage = self.destination._stage_portable_backup

        def remove_media(*args, **kwargs):
            staged = original_stage(*args, **kwargs)
            media = next(
                path for name, path in staged.member_paths.items() if "/media/" in name
            )
            media.unlink()
            return staged

        with patch.object(self.destination, "_stage_portable_backup", side_effect=remove_media):
            result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual(previous, self.destination_collection.read_bytes())

    def test_valid_current_state_creates_complete_verified_portable_safety_backup(self) -> None:
        package = self._package([self._item("incoming")])
        self._current()

        result = self._restore(package)

        self.assertTrue(result.success, result.errors)
        self.assertEqual("VALID", result.pre_restore_safety_status)
        self.assertEqual("complete_portable_v1", result.pre_restore_safety_metadata["artifact_kind"])
        self.assertTrue(self.destination.verify_backup_package(
            result.pre_restore_backup_path
        ).success)

    def test_valid_current_safety_backup_contains_current_managed_media(self) -> None:
        package = self._package([self._item("incoming")])
        current_media = (
            self.destination_collection.parent / "managed_media" / "ordinary"
            / "current-photo" / "front.jpg"
        )
        current_media.parent.mkdir(parents=True)
        current_media.write_bytes(b"current photo")
        self._write_v1(self.destination_collection, [
            self._item("current-photo", photos=[ItemPhoto(str(current_media))])
        ])

        result = self._restore(package)

        self.assertTrue(result.success, result.errors)
        verified = self.destination.verify_backup_package(result.pre_restore_backup_path)
        self.assertTrue(verified.success, verified.errors)
        self.assertEqual(1, len(verified.manifest.photo_references))

    def test_invalid_current_state_gets_exact_verified_raw_safety_artifact(self) -> None:
        package = self._package([self._item("incoming")])
        invalid = b"{not valid json\x00exact"
        self.destination_collection.parent.mkdir(parents=True)
        self.destination_collection.write_bytes(invalid)

        result = self._restore(package)

        self.assertTrue(result.success, result.errors)
        self.assertEqual("INVALID_OR_UNSUPPORTED", result.pre_restore_safety_status)
        self.assertEqual(invalid, Path(result.pre_restore_backup_path).read_bytes())
        self.assertFalse(result.pre_restore_safety_metadata["semantically_restorable"])

    def test_missing_current_state_gets_verified_missing_record(self) -> None:
        package = self._package([self._item("incoming")])

        result = self._restore(package)

        self.assertTrue(result.success, result.errors)
        record = json.loads(Path(result.pre_restore_backup_path).read_text())
        self.assertEqual("MISSING", record["authoritative_collection_state"])
        self.assertTrue(result.pre_restore_safety_metadata["verified"])

    def test_safety_artifact_failure_aborts_without_mutation(self) -> None:
        package = self._package([self._item("incoming")])
        previous = self._current()

        with patch.object(
            self.destination, "_create_portable_restore_safety",
            side_effect=OSError("safety unavailable"),
        ):
            result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual(previous, self.destination_collection.read_bytes())

    def test_differing_media_collision_fails_closed_and_unrelated_file_remains(self) -> None:
        package = self._package([
            self._item("collision", photos=[
                self._ordinary_photo("collision", "front.jpg", b"incoming")
            ])
        ])
        previous = self._current()
        destination = (
            self.destination_collection.parent / "managed_media" / "ordinary"
            / "collision" / "front.jpg"
        )
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"different")
        unrelated = destination.parent / "unrelated.txt"
        unrelated.write_bytes(b"untouched")

        result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual(b"different", destination.read_bytes())
        self.assertEqual(b"untouched", unrelated.read_bytes())
        self.assertEqual(previous, self.destination_collection.read_bytes())

    def test_file_directory_collision_fails_closed(self) -> None:
        package = self._package([
            self._item("directory", photos=[
                self._ordinary_photo("directory", "front.jpg", b"incoming")
            ])
        ])
        previous = self._current()
        destination = (
            self.destination_collection.parent / "managed_media" / "ordinary"
            / "directory" / "front.jpg"
        )
        destination.mkdir(parents=True)

        result = self._restore(package)

        self.assertFalse(result.success)
        self.assertTrue(destination.is_dir())
        self.assertEqual(previous, self.destination_collection.read_bytes())

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links unavailable")
    def test_link_destination_fails_closed_when_supported(self) -> None:
        package = self._package([
            self._item("linked", photos=[
                self._ordinary_photo("linked", "front.jpg", b"incoming")
            ])
        ])
        destination = (
            self.destination_collection.parent / "managed_media" / "ordinary"
            / "linked" / "front.jpg"
        )
        destination.parent.mkdir(parents=True)
        target = self.root / "outside.jpg"
        target.write_bytes(b"outside")
        try:
            os.symlink(target, destination)
        except OSError as error:
            self.skipTest(f"symbolic links unavailable: {error}")

        result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual(b"outside", target.read_bytes())

    def test_wrong_capture_ownership_fails_closed(self) -> None:
        package = self._package([
            self._item(CAPTURE_ITEM_ID, photos=[self._capture_photo(b"capture")])
        ])
        live_root = (
            self.destination_root / "coin_photos" / "collection" / "imports"
            / IMPORT_ID
        )
        live_root.mkdir(parents=True)
        (live_root / ".import-owner.json").write_text(json.dumps({
            "ownership_schema_version": "1.0",
            "import_id": IMPORT_ID,
            "random_ownership_token": "55555555-5555-4555-8555-555555555555",
        }), encoding="utf-8")

        result = self._restore(package)

        self.assertFalse(result.success)
        self.assertIn("differing bytes", " ".join(result.errors))

    def test_existing_capture_root_with_matching_owner_and_media_is_reused(self) -> None:
        package = self._package([
            self._item(CAPTURE_ITEM_ID, photos=[self._capture_photo(b"capture")])
        ])
        staged_owner = (
            self.source_root / "coin_photos" / "collection" / "imports"
            / IMPORT_ID / ".import-owner.json"
        ).read_bytes()
        root, media = self._existing_capture_root(staged_owner)
        owner = root / ".import-owner.json"
        owner_identity = os.stat(owner, follow_symlinks=False)
        media_identity = os.stat(media, follow_symlinks=False)

        result = self._restore(package)

        self.assertTrue(result.success, result.errors)
        after_owner = os.stat(owner, follow_symlinks=False)
        after_media = os.stat(media, follow_symlinks=False)
        self.assertEqual(
            (owner_identity.st_dev, owner_identity.st_ino),
            (after_owner.st_dev, after_owner.st_ino),
        )
        self.assertEqual(
            (media_identity.st_dev, media_identity.st_ino),
            (after_media.st_dev, after_media.st_ino),
        )
        self.assertIn(str(owner), result.skipped_files)
        self.assertIn(str(media), result.skipped_files)

    def test_matching_capture_media_without_owner_does_not_authorize_reuse(self) -> None:
        package = self._package([
            self._item(CAPTURE_ITEM_ID, photos=[self._capture_photo(b"capture")])
        ])
        previous = self._current()
        root, media = self._existing_capture_root(None)
        unrelated = root / "unrelated.txt"
        unrelated.write_bytes(b"untouched")

        with patch.object(self.destination, "_publish_portable_file") as publish:
            result = self._restore(package)

        self.assertFalse(result.success)
        publish.assert_not_called()
        self.assertEqual(b"capture", media.read_bytes())
        self.assertEqual(b"untouched", unrelated.read_bytes())
        self.assertEqual(previous, self.destination_collection.read_bytes())

    def test_existing_capture_root_with_malformed_owner_fails_closed(self) -> None:
        package = self._package([
            self._item(CAPTURE_ITEM_ID, photos=[self._capture_photo(b"capture")])
        ])
        previous = self._current()
        _root, media = self._existing_capture_root(b"{not owner json")

        with patch.object(self.destination, "_publish_portable_file") as publish:
            result = self._restore(package)

        self.assertFalse(result.success)
        publish.assert_not_called()
        self.assertEqual(b"capture", media.read_bytes())
        self.assertEqual(previous, self.destination_collection.read_bytes())

    def test_existing_capture_root_with_wrong_import_id_owner_fails_closed(self) -> None:
        package = self._package([
            self._item(CAPTURE_ITEM_ID, photos=[self._capture_photo(b"capture")])
        ])
        previous = self._current()
        wrong_owner = json.dumps({
            "ownership_schema_version": "1.0",
            "import_id": "66666666-6666-4666-8666-666666666666",
            "random_ownership_token": OWNER_TOKEN,
        }, sort_keys=True).encode("utf-8")
        _root, media = self._existing_capture_root(wrong_owner)

        with patch.object(self.destination, "_publish_portable_file") as publish:
            result = self._restore(package)

        self.assertFalse(result.success)
        publish.assert_not_called()
        self.assertEqual(b"capture", media.read_bytes())
        self.assertEqual(previous, self.destination_collection.read_bytes())

    def test_existing_capture_root_with_different_valid_owner_bytes_fails_closed(self) -> None:
        package = self._package([
            self._item(CAPTURE_ITEM_ID, photos=[self._capture_photo(b"capture")])
        ])
        previous = self._current()
        different_owner = json.dumps({
            "ownership_schema_version": "1.0",
            "import_id": IMPORT_ID,
            "random_ownership_token": "55555555-5555-4555-8555-555555555555",
        }, sort_keys=True).encode("utf-8")
        _root, media = self._existing_capture_root(different_owner)

        with patch.object(self.destination, "_publish_portable_file") as publish:
            result = self._restore(package)

        self.assertFalse(result.success)
        publish.assert_not_called()
        self.assertIn("differing bytes", " ".join(result.errors))
        self.assertEqual(b"capture", media.read_bytes())
        self.assertEqual(previous, self.destination_collection.read_bytes())

    def test_existing_capture_root_with_directory_owner_fails_closed(self) -> None:
        package = self._package([
            self._item(CAPTURE_ITEM_ID, photos=[self._capture_photo(b"capture")])
        ])
        previous = self._current()
        root, media = self._existing_capture_root(None)
        (root / ".import-owner.json").mkdir()

        with patch.object(self.destination, "_publish_portable_file") as publish:
            result = self._restore(package)

        self.assertFalse(result.success)
        publish.assert_not_called()
        self.assertEqual(b"capture", media.read_bytes())
        self.assertEqual(previous, self.destination_collection.read_bytes())

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links unavailable")
    def test_existing_capture_root_with_linked_owner_fails_closed_when_supported(self) -> None:
        package = self._package([
            self._item(CAPTURE_ITEM_ID, photos=[self._capture_photo(b"capture")])
        ])
        previous = self._current()
        root, media = self._existing_capture_root(None)
        outside = self.root / "outside-owner.json"
        outside.write_bytes((
            self.source_root / "coin_photos" / "collection" / "imports"
            / IMPORT_ID / ".import-owner.json"
        ).read_bytes())
        try:
            os.symlink(outside, root / ".import-owner.json")
        except OSError as error:
            self.skipTest(f"symbolic links unavailable: {error}")

        with patch.object(self.destination, "_publish_portable_file") as publish:
            result = self._restore(package)

        self.assertFalse(result.success)
        publish.assert_not_called()
        self.assertEqual(b"capture", media.read_bytes())
        self.assertEqual(previous, self.destination_collection.read_bytes())

    def test_media_publication_failure_rolls_back_created_media_only(self) -> None:
        package = self._package([
            self._item("one", photos=[self._ordinary_photo("one", "one.jpg", b"one")]),
            self._item("two", photos=[self._ordinary_photo("two", "two.jpg", b"two")]),
        ])
        previous = self._current()
        original_publish = self.destination._publish_portable_file
        calls = 0

        def fail_second(entry, created):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("media publication failed")
            return original_publish(entry, created)

        with patch.object(self.destination, "_publish_portable_file", side_effect=fail_second):
            result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual(previous, self.destination_collection.read_bytes())
        self.assertFalse((self.destination_collection.parent / "managed_media" / "ordinary" / "one" / "one.jpg").exists())

    def test_collection_write_failure_keeps_previous_collection_and_cleans_media(self) -> None:
        package = self._package([
            self._item("write-fail", photos=[
                self._ordinary_photo("write-fail", "front.jpg", b"media")
            ])
        ])
        previous = self._current()

        with patch("backup_manager.write_json_atomically", side_effect=OSError("write failed")):
            result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual(previous, self.destination_collection.read_bytes())
        self.assertFalse((
            self.destination_collection.parent / "managed_media" / "ordinary"
            / "write-fail" / "front.jpg"
        ).exists())

    def test_collection_write_failure_never_removes_reused_media(self) -> None:
        package = self._package([
            self._item("reused-fail", photos=[
                self._ordinary_photo("reused-fail", "front.jpg", b"reused")
            ])
        ])
        previous = self._current()
        existing = (
            self.destination_collection.parent / "managed_media" / "ordinary"
            / "reused-fail" / "front.jpg"
        )
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"reused")

        with patch("backup_manager.write_json_atomically", side_effect=OSError("write failed")):
            result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual(previous, self.destination_collection.read_bytes())
        self.assertEqual(b"reused", existing.read_bytes())

    def test_cleanup_identity_race_retains_replacement_and_reports_warning(self) -> None:
        package = self._package([
            self._item("one", photos=[self._ordinary_photo("one", "one.jpg", b"one")]),
            self._item("two", photos=[self._ordinary_photo("two", "two.jpg", b"two")]),
        ])
        previous = self._current()
        original_publish = self.destination._publish_portable_file
        first_destination: Path | None = None
        calls = 0

        def replace_then_fail(entry, created):
            nonlocal calls, first_destination
            calls += 1
            if calls == 1:
                original_publish(entry, created)
                first_destination = entry.destination
                entry.destination.unlink()
                entry.destination.write_bytes(b"replacement")
                return None
            raise OSError("later publication failure")

        with patch.object(self.destination, "_publish_portable_file", side_effect=replace_then_fail):
            result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual(previous, self.destination_collection.read_bytes())
        self.assertEqual(b"replacement", first_destination.read_bytes())
        self.assertTrue(any("identity-ambiguous" in value for value in result.warnings))

    def test_post_publication_mismatch_blocks_success_and_exposes_safety(self) -> None:
        package = self._package([self._item("incoming")])
        self._current()

        with patch.object(
            self.destination, "_reload_and_compare_portable",
            side_effect=ValueError("simulated reload mismatch"),
        ):
            result = self._restore(package)

        self.assertFalse(result.success)
        self.assertEqual("Portable restore requires recovery", result.status)
        self.assertTrue(Path(result.pre_restore_backup_path).is_file())
        self.assertIn("recovery", " ".join(result.errors).lower())
        loaded = CoinCollection(str(self.destination_collection))
        self.assertEqual("incoming", loaded.items[0].id)

    def test_legacy_v0_portable_restore_transitions_to_v1_without_id_or_metadata_change(self) -> None:
        package = self._package([
            self._item("legacy-stable", notes="legacy collector metadata")
        ], legacy_v0=True)

        result = self._restore(package)

        self.assertTrue(result.success, result.errors)
        loaded = CoinCollection(str(self.destination_collection))
        self.assertEqual(CollectionFormat.V1, loaded.collection_format)
        self.assertEqual("legacy-stable", loaded.items[0].id)
        self.assertEqual("legacy collector metadata", loaded.items[0].notes)

    def test_portable_dispatch_never_calls_legacy_verification_or_restore_path(self) -> None:
        package = self._package([self._item("portable-only")])

        with patch.object(
            BackupManager, "_verify_legacy_backup_archive",
            side_effect=AssertionError("portable fell through legacy verification"),
        ):
            result = self._restore(package)

        self.assertTrue(result.success, result.errors)


if __name__ == "__main__":
    unittest.main()
