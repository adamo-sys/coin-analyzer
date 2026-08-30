"""Focused P0-E tests for ordinary-entry collection-managed photos."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from coin_collection import (
    CoinCollection,
    CoinCollectionApp,
    ItemPhoto,
    ItemType,
    PhotoRole,
)
from managed_media import OrdinaryEntryManagedMediaStore


class OrdinaryEntryManagedMediaTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.collection_path = self.root / "collection.json"
        self.collection = CoinCollection(str(self.collection_path))
        self.app = CoinCollectionApp(collection=self.collection)

    def _source(self, relative_path: str, content: bytes) -> Path:
        path = self.root / "sources" / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_manual_coin_photo_is_managed_and_survives_source_removal(self):
        source = self._source("coin-front.JPG", b"coin-front-original\x00\xff")
        original = source.read_bytes()
        self.app.current_image_path = str(source)

        self.assertTrue(self.app.add_to_collection(
            "Canada", "Cent", "1920", "VF-20", "ordinary coin"
        ))

        saved = CoinCollection(str(self.collection_path)).items[0]
        managed = Path(saved.photos[0].path)
        self.assertNotEqual(source, managed)
        self.assertEqual(original, source.read_bytes())
        self.assertEqual(original, managed.read_bytes())
        self.assertEqual(".jpg", managed.suffix)
        self.assertEqual(
            self.root / "managed_media" / "ordinary" / saved.id,
            managed.parent,
        )
        self.assertEqual(str(managed), saved.image_path)

        moved = source.with_name("source-moved.JPG")
        source.rename(moved)
        moved.unlink()
        self.assertFalse(source.exists())
        self.assertEqual(original, managed.read_bytes())
        self.assertEqual(str(managed), CoinCollection(
            str(self.collection_path)
        ).items[0].photos[0].path)

    def test_banknote_front_back_metadata_and_primary_are_preserved(self):
        front = self._source("front.png", b"banknote-front")
        back = self._source("back.jpeg", b"banknote-back")
        original_front = front.read_bytes()
        original_back = back.read_bytes()
        photos = [
            ItemPhoto(str(front), PhotoRole.FRONT, False, "front note", 1),
            ItemPhoto(str(back), PhotoRole.BACK, True, "back note", 0),
        ]

        self.assertTrue(self.app.add_to_collection(
            "Hong Kong",
            "Ten Dollars",
            "1962 series",
            "VF",
            "ordinary banknote",
            photos=photos,
            item_type=ItemType.BANKNOTE,
        ))

        saved = CoinCollection(str(self.collection_path)).items[0]
        self.assertIs(saved.item_type, ItemType.BANKNOTE)
        self.assertEqual(
            [PhotoRole.BACK, PhotoRole.FRONT],
            [photo.role for photo in saved.photos],
        )
        self.assertEqual([True, False], [photo.is_primary for photo in saved.photos])
        self.assertEqual(["back note", "front note"], [p.notes for p in saved.photos])
        self.assertEqual([0, 1], [photo.display_order for photo in saved.photos])
        self.assertEqual(str(Path(saved.photos[0].path)), saved.image_path)
        self.assertEqual(original_front, front.read_bytes())
        self.assertEqual(original_back, back.read_bytes())
        self.assertEqual(original_back, Path(saved.photos[0].path).read_bytes())
        self.assertEqual(original_front, Path(saved.photos[1].path).read_bytes())

    def test_same_basename_sources_never_overwrite_each_other(self):
        first = self._source("first/photo.jpg", b"first bytes")
        second = self._source("second/photo.jpg", b"second bytes")

        self.assertTrue(self.app.add_to_collection(
            "Canada",
            "Dollar",
            "2024",
            "MS",
            "two photos",
            photos=[
                ItemPhoto(str(first), PhotoRole.FRONT, True, "", 0),
                ItemPhoto(str(second), PhotoRole.BACK, False, "", 1),
            ],
        ))

        paths = [Path(photo.path) for photo in self.collection.items[0].photos]
        self.assertEqual(2, len(set(paths)))
        self.assertEqual([b"first bytes", b"second bytes"], [p.read_bytes() for p in paths])

    @patch("atomic_json.os.replace", side_effect=OSError("simulated persistence failure"))
    def test_failed_authoritative_persistence_rolls_back_new_managed_files(self, _replace):
        source = self._source("failed-save.webp", b"must remain unchanged")
        original = source.read_bytes()
        self.app.current_image_path = str(source)

        self.assertFalse(self.app.add_to_collection(
            "Canada", "Five Cents", "1945", "VF", "will fail"
        ))

        self.assertEqual([], self.collection.items)
        self.assertFalse(self.collection_path.exists())
        self.assertEqual(original, source.read_bytes())
        managed_root = self.root / "managed_media" / "ordinary"
        self.assertEqual([], list(managed_root.rglob("*")) if managed_root.exists() else [])

    def test_copy_failure_cleans_earlier_copies_without_persisting(self):
        source = self._source("good.jpg", b"good")
        missing = self.root / "sources" / "missing.jpg"

        self.assertFalse(self.app.add_to_collection(
            "Canada",
            "Cent",
            "1920",
            "VF",
            "copy failure",
            photos=[ItemPhoto(str(source)), ItemPhoto(str(missing))],
        ))

        self.assertEqual([], self.collection.items)
        self.assertFalse(self.collection_path.exists())
        self.assertEqual(b"good", source.read_bytes())
        managed_root = self.root / "managed_media" / "ordinary"
        self.assertEqual([], list(managed_root.rglob("*")) if managed_root.exists() else [])

    def test_rollback_does_not_delete_a_replacement_file(self):
        source = self._source("identity.jpg", b"source")
        store = OrdinaryEntryManagedMediaStore(str(self.collection_path))
        ingestion = store.ingest(
            "coin_00000000000000000000000000000000",
            [ItemPhoto(str(source), is_primary=True)],
        )
        managed = Path(ingestion.photos[0].path)
        managed.unlink()
        managed.write_bytes(b"replacement")

        retained = store.rollback(ingestion)

        self.assertEqual((str(managed),), retained)
        self.assertEqual(b"replacement", managed.read_bytes())


if __name__ == "__main__":
    unittest.main()
