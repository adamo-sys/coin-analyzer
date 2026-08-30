"""Focused Product Unit 5B portable backup creation and verification tests."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import backup_manager

from backup_manager import BackupManager, MANIFEST_NAME
from coin_collection import (
    CaptureImportMediaProvenance,
    CoinCollection,
    CoinCollectionApp,
    CoinItem,
    ItemPhoto,
    ItemType,
    PhotoRole,
    serialize_collection_payload,
)


IMPORT_ID = "11111111-1111-4111-8111-111111111111"
SNAPSHOT_ID = "22222222-2222-4222-8222-222222222222"
OWNER_TOKEN = "33333333-3333-4333-8333-333333333333"
CAPTURE_ITEM_ID = "44444444-4444-4444-8444-444444444444"
PREFIXED_CAPTURE_ITEM_ID = "coin_44444444444444448444444444444444"


class PortableBackupManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.collection_path = self.root / "data" / "collection.json"
        self.backup = BackupManager(
            backup_dir=str(self.root / "backups"),
            collection_json_path=str(self.collection_path),
        )

    def _item(
        self,
        item_id: str,
        *,
        item_type: ItemType = ItemType.COIN,
        photos: list[ItemPhoto] | None = None,
    ) -> CoinItem:
        return CoinItem(
            id=item_id,
            image_path="",
            country="Canada",
            denomination="One Dollar",
            year="1967",
            grade="VF",
            notes="test",
            date_added="2026-08-30",
            item_type=item_type,
            photos=list(photos or []),
        )

    def _ordinary_photo(
        self,
        item_id: str,
        name: str,
        content: bytes,
        *,
        role: PhotoRole = PhotoRole.OTHER,
        primary: bool = False,
        order: int = 0,
        notes: str = "",
    ) -> ItemPhoto:
        path = (
            self.collection_path.parent
            / "managed_media"
            / "ordinary"
            / item_id
            / name
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return ItemPhoto(str(path), role, primary, notes, order)

    def _capture_photo(self, item_id: str, content: bytes) -> tuple[ItemPhoto, Path]:
        import_root = (
            self.root / "coin_photos" / "collection" / "imports" / IMPORT_ID
        )
        path = import_root / item_id / "front.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        owner = {
            "ownership_schema_version": "1.0",
            "import_id": IMPORT_ID,
            "random_ownership_token": OWNER_TOKEN,
        }
        (import_root / ".import-owner.json").write_text(
            json.dumps(owner, sort_keys=True), encoding="utf-8"
        )
        provenance = CaptureImportMediaProvenance(
            schema_version="1.0",
            import_id=IMPORT_ID,
            source_kind="PROCESSED_SNAPSHOT",
            package_sha256="a" * 64,
            processed_snapshot_id=SNAPSHOT_ID,
            artifact_key="coin/front",
            artifact_sha256=sha256(content).hexdigest(),
            variant="NORMALIZED",
        )
        return (
            ItemPhoto(
                str(path), PhotoRole.FRONT, True, "capture", 0,
                capture_import_media=provenance,
            ),
            import_root,
        )

    def _write_v1(self, items: list[CoinItem]) -> bytes:
        self.collection_path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            json.dumps(
                serialize_collection_payload(items),
                indent=2,
                ensure_ascii=False,
            ) + "\n"
        ).encode("utf-8")
        self.collection_path.write_bytes(content)
        return content

    def _create(self) -> Path:
        path = self.root / "portable.zip"
        result = self.backup.create_portable_backup_package(str(path))
        self.assertTrue(result.success, result.errors)
        self.assertTrue(path.is_file())
        self.assertTrue(self.backup.verify_backup_package(str(path)).success)
        return path

    def _rewrite_zip(self, path: Path, mutate) -> None:
        with zipfile.ZipFile(path, "r") as source:
            rows = [(info.filename, source.read(info)) for info in source.infolist()]
        replacement = path.with_suffix(".replacement.zip")
        with zipfile.ZipFile(replacement, "w", zipfile.ZIP_DEFLATED) as target:
            for name, content in mutate(rows):
                target.writestr(name, content)
        os.replace(replacement, path)

    @staticmethod
    def _mutate_manifest(rows, update):
        result = []
        for name, content in rows:
            if name == MANIFEST_NAME:
                payload = json.loads(content)
                update(payload)
                content = (json.dumps(payload, sort_keys=True) + "\n").encode()
            result.append((name, content))
        return result

    def test_mixed_coin_banknote_with_ordinary_managed_photos_succeeds(self) -> None:
        coin_id = "coin-stable"
        note_id = "note-stable"
        coin_photo = self._ordinary_photo(coin_id, "front.jpg", b"coin")
        note_photo = self._ordinary_photo(note_id, "front.png", b"note")
        self._write_v1([
            self._item(coin_id, photos=[coin_photo]),
            self._item(note_id, item_type=ItemType.BANKNOTE, photos=[note_photo]),
        ])

        path = self._create()

        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read(MANIFEST_NAME))
        self.assertEqual(1, manifest["portable_collection_backup_version"])
        self.assertEqual([coin_id, note_id], manifest["authoritative_collection"]["stable_ids"])
        self.assertEqual(2, len(manifest["photo_references"]))

    def test_photo_free_record_succeeds(self) -> None:
        self._write_v1([self._item("photo-free")])
        path = self._create()
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read(MANIFEST_NAME))
        self.assertEqual([], manifest["photo_references"])

    def test_existing_creation_boundary_can_request_portable_v1(self) -> None:
        self._write_v1([self._item("portable-dispatch")])
        path = self.root / "portable-dispatch.zip"

        result = self.backup.create_backup_package(str(path), portable=True)

        self.assertTrue(result.success, result.errors)
        self.assertEqual(
            1, result.manifest.portable_collection_backup_version
        )

    def test_multiple_photo_roles_order_and_collection_bytes_are_preserved(self) -> None:
        item_id = "multi-photo"
        back = self._ordinary_photo(
            item_id, "back.jpg", b"back", role=PhotoRole.BACK,
            primary=True, order=0, notes="reverse notes",
        )
        front = self._ordinary_photo(
            item_id, "front.jpg", b"front", role=PhotoRole.FRONT,
            order=1, notes="front notes",
        )
        original = self._write_v1([self._item(item_id, photos=[front, back])])

        path = self._create()

        with zipfile.ZipFile(path) as archive:
            self.assertEqual(original, archive.read("portable/collection/collection.json"))
            manifest = json.loads(archive.read(MANIFEST_NAME))
            packaged = {
                archive.read(row["archive_member"])
                for row in manifest["photo_references"]
            }
        self.assertEqual({b"front", b"back"}, packaged)

    def test_missing_managed_photo_fails_closed(self) -> None:
        item_id = "missing-photo"
        missing = self.collection_path.parent / "managed_media" / "ordinary" / item_id / "missing.jpg"
        self._write_v1([self._item(item_id, photos=[ItemPhoto(str(missing))])])
        target = self.root / "portable.zip"

        result = self.backup.create_portable_backup_package(str(target))

        self.assertFalse(result.success)
        self.assertFalse(target.exists())

    def test_external_unmanaged_photo_fails_with_item_and_reference(self) -> None:
        external = self.root / "external" / "source.jpg"
        external.parent.mkdir()
        external.write_bytes(b"external")
        self._write_v1([self._item("external-item", photos=[ItemPhoto(str(external))])])

        result = self.backup.create_portable_backup_package(str(self.root / "portable.zip"))

        self.assertFalse(result.success)
        diagnostic = " ".join(result.errors)
        self.assertIn("external-item", diagnostic)
        self.assertIn(str(external), diagnostic)
        self.assertIn("external/unmanaged", diagnostic)

    def test_tampered_packaged_media_fails_verification(self) -> None:
        item_id = "tamper-media"
        photo = self._ordinary_photo(item_id, "front.jpg", b"original")
        self._write_v1([self._item(item_id, photos=[photo])])
        path = self._create()

        self._rewrite_zip(path, lambda rows: [
            (name, b"tampered" if "/media/ordinary/" in name else content)
            for name, content in rows
        ])

        self.assertFalse(self.backup.verify_backup_package(str(path)).success)

    def test_tampered_collection_fails_verification(self) -> None:
        self._write_v1([self._item("collection-tamper")])
        path = self._create()

        def replace_collection_and_declared_digest(rows):
            replacement = b"{}"
            replacement_digest = sha256(replacement).hexdigest()
            result = []
            for name, content in rows:
                if name.endswith("/collection.json"):
                    content = replacement
                elif name == MANIFEST_NAME:
                    manifest = json.loads(content)
                    manifest["authoritative_collection"]["byte_length"] = len(replacement)
                    manifest["authoritative_collection"]["sha256"] = replacement_digest
                    collection_member = next(
                        row for row in manifest["members"]
                        if row["member_type"] == "authoritative_collection"
                    )
                    collection_member["byte_length"] = len(replacement)
                    collection_member["sha256"] = replacement_digest
                    content = (json.dumps(manifest, sort_keys=True) + "\n").encode()
                result.append((name, content))
            return result

        self._rewrite_zip(path, replace_collection_and_declared_digest)
        verified = self.backup.verify_backup_package(str(path))

        self.assertFalse(verified.success)
        self.assertIn("INVALID_OR_UNSUPPORTED", " ".join(verified.errors))

    def test_tampered_manifest_hash_and_size_fail_verification(self) -> None:
        for field, value in (("sha256", "0" * 64), ("byte_length", 999)):
            with self.subTest(field=field):
                self._write_v1([self._item(f"manifest-{field}")])
                path = self.root / f"{field}.zip"
                result = self.backup.create_portable_backup_package(str(path))
                self.assertTrue(result.success, result.errors)
                self._rewrite_zip(path, lambda rows, f=field, v=value: self._mutate_manifest(
                    rows, lambda payload: payload["members"][0].__setitem__(f, v)
                ))
                self.assertFalse(self.backup.verify_backup_package(str(path)).success)

    def test_item_count_mismatch_fails_verification(self) -> None:
        self._write_v1([self._item("count")])
        path = self._create()
        self._rewrite_zip(path, lambda rows: self._mutate_manifest(
            rows, lambda payload: payload["authoritative_collection"].__setitem__("item_count", 2)
        ))
        self.assertFalse(self.backup.verify_backup_package(str(path)).success)

    def test_stable_id_roster_mismatch_fails_verification(self) -> None:
        self._write_v1([self._item("roster")])
        path = self._create()
        self._rewrite_zip(path, lambda rows: self._mutate_manifest(
            rows, lambda payload: payload["authoritative_collection"].__setitem__("stable_ids", ["other"])
        ))
        self.assertFalse(self.backup.verify_backup_package(str(path)).success)

    def test_unsafe_zip_member_path_traversal_fails_verification(self) -> None:
        self._write_v1([self._item("unsafe")])
        path = self._create()
        self._rewrite_zip(path, lambda rows: rows + [("../escape", b"danger")])
        self.assertFalse(self.backup.verify_backup_package(str(path)).success)

    def test_absolute_drive_and_backslash_zip_members_fail_verification(self) -> None:
        for index, unsafe_name in enumerate((
            "/absolute.jpg",
            "C:/drive.jpg",
            "portable\\media\\alias.jpg",
        )):
            with self.subTest(unsafe_name=unsafe_name):
                self._write_v1([self._item(f"unsafe-{index}")])
                path = self.root / f"unsafe-{index}.zip"
                created = self.backup.create_portable_backup_package(str(path))
                self.assertTrue(created.success, created.errors)
                self._rewrite_zip(path, lambda rows, name=unsafe_name: rows + [
                    (name, b"danger")
                ])
                self.assertFalse(
                    self.backup.verify_backup_package(str(path)).success
                )

    def test_normalized_archive_member_collision_fails_verification(self) -> None:
        self._write_v1([self._item("collision")])
        path = self._create()
        self._rewrite_zip(path, lambda rows: rows + [
            ("PORTABLE/COLLECTION/COLLECTION.JSON", b"collision")
        ])
        self.assertFalse(self.backup.verify_backup_package(str(path)).success)

    def test_archive_file_directory_prefix_collisions_fail_verification(self) -> None:
        for index, names in enumerate((
            ("portable/media/x", "portable/media/x/file.jpg"),
            ("PORTABLE/MEDIA/Y", "portable/media/y/file.jpg"),
        )):
            with self.subTest(names=names):
                self._write_v1([self._item(f"prefix-collision-{index}")])
                path = self.root / f"prefix-collision-{index}.zip"
                created = self.backup.create_portable_backup_package(str(path))
                self.assertTrue(created.success, created.errors)
                self._rewrite_zip(path, lambda rows, values=names: rows + [
                    (name, b"collision") for name in values
                ])

                verified = self.backup.verify_backup_package(str(path))

                self.assertFalse(verified.success)
                self.assertIn(
                    "file/directory prefix collision", " ".join(verified.errors)
                )

    def test_symlink_like_zip_member_fails_verification(self) -> None:
        self._write_v1([self._item("symlink-member")])
        path = self._create()
        with zipfile.ZipFile(path, "r") as source:
            rows = [(info, source.read(info)) for info in source.infolist()]
        replacement = path.with_suffix(".replacement.zip")
        with zipfile.ZipFile(replacement, "w", zipfile.ZIP_DEFLATED) as target:
            for info, content in rows:
                target.writestr(info, content)
            link = zipfile.ZipInfo("portable/media/ordinary/link.jpg")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            target.writestr(link, b"target")
        os.replace(replacement, path)

        verified = self.backup.verify_backup_package(str(path))

        self.assertFalse(verified.success)
        self.assertIn("not a plain regular file", " ".join(verified.errors))

    def test_unsupported_portable_version_fails_verification(self) -> None:
        self._write_v1([self._item("version")])
        path = self._create()
        self._rewrite_zip(path, lambda rows: self._mutate_manifest(
            rows, lambda payload: payload.__setitem__("portable_collection_backup_version", 2)
        ))
        self.assertFalse(self.backup.verify_backup_package(str(path)).success)

    def test_v0_backup_is_observational_and_does_not_rewrite_live_collection(self) -> None:
        self.collection_path.parent.mkdir(parents=True)
        original = b'[ {"id": "legacy-stable", "country": "Canada"} ]\n'
        self.collection_path.write_bytes(original)

        self._create()

        self.assertEqual(original, self.collection_path.read_bytes())

    def test_invalid_authoritative_collection_fails_without_package(self) -> None:
        self.collection_path.parent.mkdir(parents=True)
        self.collection_path.write_bytes(b"{malformed")
        target = self.root / "invalid.zip"

        result = self.backup.create_portable_backup_package(str(target))

        self.assertFalse(result.success)
        self.assertFalse(target.exists())
        self.assertIn("INVALID_OR_UNSUPPORTED", " ".join(result.errors))

    def test_destination_appearing_at_publication_is_not_overwritten(self) -> None:
        self._write_v1([self._item("publication-race")])
        target = self.root / "publication-race.zip"
        concurrent_bytes = b"created by another process"
        real_link = os.link

        def create_destination_then_publish(source, destination):
            Path(destination).write_bytes(concurrent_bytes)
            return real_link(source, destination)

        with patch(
            "backup_manager.os.link", side_effect=create_destination_then_publish
        ):
            result = self.backup.create_portable_backup_package(str(target))

        self.assertFalse(result.success)
        self.assertEqual(concurrent_bytes, target.read_bytes())
        self.assertEqual([], list(self.root.glob(f".{target.name}.*.partial")))

    def test_source_mutation_during_packaging_fails_without_package(self) -> None:
        item_id = "changing-media"
        photo = self._ordinary_photo(item_id, "front.jpg", b"before")
        managed_path = Path(photo.path)
        self._write_v1([self._item(item_id, photos=[photo])])
        target = self.root / "changing.zip"
        original_read = backup_manager._read_stable_regular_file
        first_media_read = True

        def read_then_change(path, label):
            nonlocal first_media_read
            payload = original_read(path, label)
            if Path(path) == managed_path and first_media_read:
                first_media_read = False
                managed_path.write_bytes(b"after")
            return payload

        with patch(
            "backup_manager._read_stable_regular_file",
            side_effect=read_then_change,
        ):
            result = self.backup.create_portable_backup_package(str(target))

        self.assertFalse(result.success)
        self.assertFalse(target.exists())
        self.assertIn("changed", " ".join(result.errors))

    def test_capture_import_media_and_owner_provenance_travel_and_verify(self) -> None:
        photo, _root = self._capture_photo(CAPTURE_ITEM_ID, b"capture bytes")
        self._write_v1([self._item(CAPTURE_ITEM_ID, photos=[photo])])
        path = self._create()

        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read(MANIFEST_NAME))
            mapping = manifest["photo_references"][0]
            self.assertEqual("capture_import", mapping["ownership"])
            self.assertEqual(IMPORT_ID, mapping["capture_import_id"])
            self.assertIn(mapping["owner_archive_member"], archive.namelist())
            collection = json.loads(archive.read("portable/collection/collection.json"))
        self.assertEqual(
            IMPORT_ID,
            collection["items"][0]["photos"][0]["capture_import_media"]["import_id"],
        )

    def test_prefixed_stable_item_id_capture_import_package_verifies(self) -> None:
        photo, _root = self._capture_photo(
            PREFIXED_CAPTURE_ITEM_ID, b"prefixed capture bytes"
        )
        self._write_v1([
            self._item(PREFIXED_CAPTURE_ITEM_ID, photos=[photo])
        ])

        path = self._create()
        verified = self.backup.verify_backup_package(str(path))

        self.assertTrue(verified.success, verified.errors)
        self.assertEqual(
            [PREFIXED_CAPTURE_ITEM_ID],
            verified.manifest.authoritative_collection["stable_ids"],
        )

    def test_missing_owner_fails_creation_and_tampered_owner_fails_verification(self) -> None:
        photo, import_root = self._capture_photo(CAPTURE_ITEM_ID, b"capture bytes")
        self._write_v1([self._item(CAPTURE_ITEM_ID, photos=[photo])])
        (import_root / ".import-owner.json").unlink()
        failed = self.backup.create_portable_backup_package(str(self.root / "missing-owner.zip"))
        self.assertFalse(failed.success)
        self.assertFalse((self.root / "missing-owner.zip").exists())

        photo, _ = self._capture_photo(CAPTURE_ITEM_ID, b"capture bytes")
        self._write_v1([self._item(CAPTURE_ITEM_ID, photos=[photo])])
        path = self._create()
        self._rewrite_zip(path, lambda rows: [
            (name, b"{}" if name.endswith(".import-owner.json") else content)
            for name, content in rows
        ])
        self.assertFalse(self.backup.verify_backup_package(str(path)).success)

    def test_source_tree_can_disappear_after_successful_creation(self) -> None:
        photo, import_root = self._capture_photo(CAPTURE_ITEM_ID, b"portable")
        self._write_v1([self._item(CAPTURE_ITEM_ID, photos=[photo])])
        path = self._create()

        shutil.rmtree(import_root)

        self.assertTrue(self.backup.verify_backup_package(str(path)).success)

    def test_original_ordinary_source_can_disappear_after_package_creation(self) -> None:
        source = self.root / "external-source" / "front.jpg"
        source.parent.mkdir()
        source.write_bytes(b"original source bytes")
        collection = CoinCollection(str(self.collection_path))
        app = CoinCollectionApp(collection=collection)
        app.current_image_path = str(source)
        self.assertTrue(app.add_to_collection(
            "Canada", "One Cent", "1920", "VF", "managed before backup"
        ))
        packaged = self._create()

        shutil.rmtree(source.parent)

        self.assertTrue(self.backup.verify_backup_package(str(packaged)).success)

    def test_imports_shaped_external_path_without_provenance_fails(self) -> None:
        import_root = self.root / "external" / "imports" / IMPORT_ID
        path = import_root / CAPTURE_ITEM_ID / "front.jpg"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"not capture owned")
        (import_root / ".import-owner.json").write_text(json.dumps({
            "ownership_schema_version": "1.0",
            "import_id": IMPORT_ID,
            "random_ownership_token": OWNER_TOKEN,
        }), encoding="utf-8")
        self._write_v1([
            self._item(CAPTURE_ITEM_ID, photos=[ItemPhoto(str(path))])
        ])

        result = self.backup.create_portable_backup_package(
            str(self.root / "unmanaged-imports-shape.zip")
        )

        self.assertFalse(result.success)
        self.assertIn("external/unmanaged", " ".join(result.errors))

    def test_capture_reference_for_different_item_fails_creation(self) -> None:
        photo, _root = self._capture_photo(CAPTURE_ITEM_ID, b"capture bytes")
        different_id = "55555555-5555-4555-8555-555555555555"
        self._write_v1([self._item(different_id, photos=[photo])])

        result = self.backup.create_portable_backup_package(
            str(self.root / "mismatched-item.zip")
        )

        self.assertFalse(result.success)
        self.assertIn("canonical item-owned suffix", " ".join(result.errors))


if __name__ == "__main__":
    unittest.main()
