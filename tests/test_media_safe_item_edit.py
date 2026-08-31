"""Adversarial Product Unit 6D tests for media-safe existing-item editing."""

from hashlib import sha256
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from backup_manager import BackupManager
from coin_collection import (
    CaptureImportMediaProvenance,
    CoinCollection,
    CoinCollectionApp,
    CoinItem,
    CollectionLoadState,
    IdentificationStatus,
    ItemPhoto,
    ItemType,
    PhotoRole,
)
from coin_collection_gui import CoinCollectionGUI


IMPORT_ID = "11111111-1111-4111-8111-111111111111"
SNAPSHOT_ID = "22222222-2222-4222-8222-222222222222"
OWNER_TOKEN = "33333333-3333-4333-8333-333333333333"
ITEM_ID = "coin_44444444444444448444444444444444"


class MediaSafeItemEditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.collection_path = self.root / "data" / "collection.json"
        self.collection = CoinCollection(str(self.collection_path))
        self.app = CoinCollectionApp(collection=self.collection)

    def _source(self, name, content):
        path = self.root / "sources" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def _ordinary(self, name="ordinary.jpg", content=b"ordinary"):
        path = self.root / "data" / "managed_media" / "ordinary" / ITEM_ID / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return ItemPhoto(str(path), PhotoRole.BACK, False, "ordinary note", 1)

    def _capture(self, content=b"capture"):
        import_root = self.root / "coin_photos" / "collection" / "imports" / IMPORT_ID
        path = import_root / ITEM_ID / "front.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        (import_root / ".import-owner.json").write_text(json.dumps({
            "ownership_schema_version": "1.0",
            "import_id": IMPORT_ID,
            "random_ownership_token": OWNER_TOKEN,
        }, sort_keys=True), encoding="utf-8")
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
        return ItemPhoto(
            str(path), PhotoRole.FRONT, True, "capture note", 0,
            capture_import_media=provenance,
        )

    def _save_item(self, photos=None, **overrides):
        values = dict(
            id=ITEM_ID,
            image_path="",
            country="Canada",
            issuer="",
            denomination="One Dollar",
            year="1967",
            grade="VF",
            notes="before",
            date_added="2026-08-30",
            item_type=ItemType.COIN,
            photos=list(photos or []),
        )
        values.update(overrides)
        item = CoinItem(**values)
        self.assertTrue(self.collection.add_item(item))
        return item

    def test_text_only_edit_preserves_capture_provenance_and_ordinary_metadata(self):
        capture = self._capture()
        ordinary = self._ordinary()
        item = self._save_item([capture, ordinary])
        before = [photo.to_dict() for photo in item.photos]

        result = self.app.update_collection_item(item.id, {"notes": "after"})

        self.assertTrue(result.success, result.error)
        saved = CoinCollection(str(self.collection_path)).items[0]
        self.assertEqual(before, [photo.to_dict() for photo in saved.photos])
        self.assertEqual("after", saved.notes)
        self.assertEqual(ITEM_ID, saved.id)

    def test_gui_clone_preserves_provenance_and_edit_delegates_to_safe_boundary(self):
        capture = self._capture()
        clone = CoinCollectionGUI.clone_photos([capture])[0]
        self.assertEqual(capture.to_dict(), clone.to_dict())
        source = inspect.getsource(CoinCollectionGUI.open_edit_item_window)
        self.assertIn("self.app.update_collection_item(item.id, updates, photos)", source)
        self.assertNotIn("self.app.collection.update_item(item.id, updates)", source)
        self.assertIn('ttk.Label(type_frame, textvariable=item_type_var)', source)
        self.assertNotIn('values=[value.value for value in ItemType]', source)

    def test_mixed_retained_media_and_new_external_photo_succeeds(self):
        capture = self._capture()
        ordinary = self._ordinary()
        source = self._source("new.png", b"new bytes")
        source_before = source.read_bytes()
        item = self._save_item([capture, ordinary])
        requested = [capture, ordinary, ItemPhoto(str(source), PhotoRole.DETAIL, False, "new", 2)]

        with patch.object(
            self.app._managed_media_store,
            "ingest",
            wraps=self.app._managed_media_store.ingest,
        ) as ingest, patch.object(
            self.collection,
            "update_item",
            wraps=self.collection.update_item,
        ) as update_item:
            result = self.app.update_collection_item(
                item.id, {"grade": "EF"}, requested
            )

        self.assertTrue(result.success, result.error)
        ingest.assert_called_once()
        ingested_item_id, ingested_photos = ingest.call_args.args
        self.assertEqual(ITEM_ID, ingested_item_id)
        self.assertEqual([str(source)], [photo.path for photo in ingested_photos])
        update_item.assert_called_once()
        saved = CoinCollection(str(self.collection_path)).items[0]
        new_photo = saved.photos[2]
        self.assertEqual(self.root / "data" / "managed_media" / "ordinary" / ITEM_ID, Path(new_photo.path).parent)
        self.assertEqual(source_before, Path(new_photo.path).read_bytes())
        self.assertEqual(source_before, source.read_bytes())
        source.unlink()
        self.assertEqual(source_before, Path(new_photo.path).read_bytes())
        self.assertEqual(capture.capture_import_media.to_dict(), saved.photos[0].capture_import_media.to_dict())

    def test_requested_photo_order_roles_notes_and_primary_persist(self):
        capture = self._capture()
        ordinary = self._ordinary()
        source = self._source("detail.jpg", b"detail")
        item = self._save_item([capture, ordinary])
        requested = [
            ItemPhoto(str(source), PhotoRole.DETAIL, False, "detail note", 0),
            ItemPhoto(ordinary.path, PhotoRole.EDGE, True, "edited ordinary", 1),
            ItemPhoto(
                capture.path,
                PhotoRole.HOLDER_FRONT,
                False,
                "edited capture",
                2,
                capture_import_media=capture.capture_import_media,
            ),
        ]

        result = self.app.update_collection_item(item.id, {}, requested)

        self.assertTrue(result.success, result.error)
        saved = CoinCollection(str(self.collection_path)).items[0]
        self.assertEqual(
            [PhotoRole.DETAIL, PhotoRole.EDGE, PhotoRole.HOLDER_FRONT],
            [photo.role for photo in saved.photos],
        )
        self.assertEqual(
            ["detail note", "edited ordinary", "edited capture"],
            [photo.notes for photo in saved.photos],
        )
        self.assertEqual([0, 1, 2], [photo.display_order for photo in saved.photos])
        self.assertEqual([False, True, False], [photo.is_primary for photo in saved.photos])
        self.assertEqual(ordinary.path, saved.image_path)
        self.assertEqual(
            capture.capture_import_media.to_dict(),
            saved.photos[2].capture_import_media.to_dict(),
        )

    def test_partial_copy_failure_removes_only_attempt_media(self):
        ordinary = self._ordinary(content=b"retain")
        item = self._save_item([ordinary])
        good = self._source("good.jpg", b"good")
        missing = self.root / "sources" / "missing.jpg"

        result = self.app.update_collection_item(item.id, {}, [
            ordinary, ItemPhoto(str(good)), ItemPhoto(str(missing)),
        ])

        self.assertFalse(result.success)
        self.assertEqual(b"retain", Path(ordinary.path).read_bytes())
        self.assertEqual([ordinary.to_dict()], [p.to_dict() for p in self.collection.items[0].photos])
        managed = Path(ordinary.path).parent
        self.assertEqual([Path(ordinary.path)], list(managed.glob("*")))

    def test_persistence_failure_restores_item_and_rolls_back_new_media(self):
        ordinary = self._ordinary()
        item = self._save_item([ordinary])
        source = self._source("new.jpg", b"new")
        before = item.to_dict()

        with patch("atomic_json.os.replace", side_effect=OSError("persist failed")):
            result = self.app.update_collection_item(
                item.id, {"notes": "changed"}, [ordinary, ItemPhoto(str(source))]
            )

        self.assertFalse(result.success)
        self.assertEqual(before, item.to_dict())
        self.assertEqual([Path(ordinary.path)], list(Path(ordinary.path).parent.glob("*")))

    def test_tampered_attempt_file_is_retained_by_rollback(self):
        item = self._save_item([])
        source = self._source("new.jpg", b"new")
        original_update = self.collection.update_item

        def tamper_then_fail(item_id, updates):
            new_path = Path(updates["photos"][0].path)
            new_path.write_bytes(b"tampered")
            self.collection.last_save_error = "simulated"
            return False

        self.collection.update_item = tamper_then_fail
        self.addCleanup(setattr, self.collection, "update_item", original_update)
        result = self.app.update_collection_item(item.id, {}, [ItemPhoto(str(source))])

        self.assertFalse(result.success)
        self.assertEqual(1, len(result.retained_attempt_media))
        self.assertEqual(b"tampered", Path(result.retained_attempt_media[0]).read_bytes())
        self.assertEqual([], item.photos)

    def test_removed_references_leave_ordinary_and_capture_files_untouched(self):
        capture = self._capture()
        ordinary = self._ordinary()
        item = self._save_item([capture, ordinary])

        result = self.app.update_collection_item(item.id, {}, [])

        self.assertTrue(result.success, result.error)
        self.assertEqual([], self.collection.items[0].photos)
        self.assertTrue(Path(capture.path).is_file())
        self.assertTrue(Path(ordinary.path).is_file())
        self.assertTrue((Path(capture.path).parents[1] / ".import-owner.json").is_file())

    def test_capture_media_is_never_sent_to_ordinary_ingestion(self):
        capture = self._capture()
        item = self._save_item([capture])
        with patch.object(self.app._managed_media_store, "ingest", wraps=self.app._managed_media_store.ingest) as ingest:
            result = self.app.update_collection_item(item.id, {"notes": "text"}, [capture])
        self.assertTrue(result.success, result.error)
        ingest.assert_not_called()

    def test_new_forged_capture_provenance_fails_before_ingestion(self):
        capture = self._capture()
        item = self._save_item([])
        forged = ItemPhoto(str(self._source("forged.jpg", b"x")), capture_import_media=capture.capture_import_media)
        with patch.object(self.app._managed_media_store, "ingest") as ingest:
            result = self.app.update_collection_item(item.id, {}, [forged])
        self.assertFalse(result.success)
        ingest.assert_not_called()

    def test_stable_id_and_item_type_mutations_fail_before_media(self):
        item = self._save_item([])
        source = self._source("new.jpg", b"new")
        for updates in ({"id": "other"}, {"item_type": ItemType.BANKNOTE}):
            with self.subTest(updates=updates), patch.object(self.app._managed_media_store, "ingest") as ingest:
                result = self.app.update_collection_item(item.id, updates, [ItemPhoto(str(source))])
                self.assertFalse(result.success)
                ingest.assert_not_called()
        self.assertEqual(ITEM_ID, item.id)
        self.assertIs(ItemType.COIN, item.item_type)

    def test_status_recomputes_for_all_truthful_transitions(self):
        item = self._save_item([], country="", denomination="", year="", notes="mystery")
        cases = [
            ({"issuer": "Kingdom of Italy"}, IdentificationStatus.PARTIAL),
            ({"issuer": "Kingdom of Italy", "denomination": "10 Centesimi", "year": "1894"}, IdentificationStatus.IDENTIFIED),
            ({"issuer": "", "denomination": "", "year": ""}, IdentificationStatus.UNIDENTIFIED),
        ]
        for updates, expected in cases:
            result = self.app.update_collection_item(item.id, updates)
            self.assertTrue(result.success, result.error)
            self.assertIs(expected, item.identification_status)

    def test_stale_and_invalid_collection_fail_before_media_creation(self):
        item = self._save_item([])
        source = self._source("new.jpg", b"new")
        with patch.object(self.app._managed_media_store, "ingest") as ingest:
            self.assertFalse(self.app.update_collection_item("missing", {}, [ItemPhoto(str(source))]).success)
            self.collection.load_state = CollectionLoadState.INVALID_OR_UNSUPPORTED
            self.assertFalse(self.app.update_collection_item(item.id, {}, [ItemPhoto(str(source))]).success)
            ingest.assert_not_called()

    def test_portable_backup_succeeds_after_mixed_media_edit(self):
        capture = self._capture()
        ordinary = self._ordinary()
        item = self._save_item([capture, ordinary])
        source = self._source("new.jpg", b"new")
        result = self.app.update_collection_item(item.id, {}, [capture, ordinary, ItemPhoto(str(source))])
        self.assertTrue(result.success, result.error)

        manager = BackupManager(
            backup_dir=str(self.root / "backups"),
            collection_json_path=str(self.collection_path),
        )
        package = self.root / "mixed.zip"
        created = manager.create_portable_backup_package(str(package))
        self.assertTrue(created.success, created.errors)
        self.assertTrue(manager.verify_backup_package(str(package)).success)


if __name__ == "__main__":
    unittest.main()
