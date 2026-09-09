"""Synthetic foundation contracts independent of Work Queue presentation."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from coin_collection import (
    CoinCollection, CoinCollectionApp, CoinItem, IdentificationStatus, ItemType,
    ItemPhoto, PhotoRole, CaptureImportMediaProvenance, truthful_manual_identification_status,
)
from collection_item_reference import CollectionItemReference
from managed_media import OrdinaryEntryManagedMediaStore


def record(item_id='stable', **values):
    return CoinItem(id=item_id, image_path='', country='', denomination='', year='',
                    grade='', notes='', date_added='', **values)


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'collection.json'
        self.collection = CoinCollection(str(self.path))
        self.item = record()
        self.assertTrue(self.collection.add_item(self.item))
        self.app = CoinCollectionApp(self.collection)
        self.reference = CollectionItemReference.capture(self.collection, self.item)

    def edit(self, updates=None, photos=None):
        return self.app.update_collection_item(
            self.item.id, updates or {}, photos, expected_reference=self.reference)

    def test_legacy_load_does_not_rewrite(self):
        raw = b'[{"id":"legacy", "country":"Canada"}]'
        self.path.write_bytes(raw)
        collection = CoinCollection(str(self.path))
        self.assertEqual(collection.items[0].item_type, ItemType.COIN)
        self.assertEqual(collection.items[0].identification_status, IdentificationStatus.PARTIAL)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_explicit_typed_status_roundtrip(self):
        value = record(item_type=ItemType.BANKNOTE, identification_status=IdentificationStatus.IDENTIFIED)
        restored = CoinItem.from_dict(value.to_dict())
        self.assertIs(restored.item_type, ItemType.BANKNOTE)
        self.assertIs(restored.identification_status, IdentificationStatus.IDENTIFIED)

    def test_invalid_explicit_enums_rejected(self):
        for values in ({'item_type':'TOKEN'}, {'identification_status':'MAYBE'}, {'identification_status':None}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                CoinItem.from_dict({'id':'bad', **values})

    def test_truthful_manual_status(self):
        cases = [({}, 'UNIDENTIFIED'), ({'title':'Descriptive title'}, 'UNIDENTIFIED'),
                 ({'country':'Unknown','year':'n/a'}, 'UNIDENTIFIED'),
                 ({'issuer':'Canada'}, 'PARTIAL'), ({'reference':'KM-1'}, 'IDENTIFIED'),
                 ({'country':'Canada','denomination':'5 cents','year':'1899'}, 'IDENTIFIED')]
        for values, expected in cases:
            with self.subTest(values=values):
                self.assertEqual(truthful_manual_identification_status(values).value, expected)

    def test_incomplete_photo_free_entry(self):
        self.assertTrue(self.app.add_to_collection('', '', '', '', 'collector note'))
        created = self.collection.get_item(self.app.last_added_item_id)
        self.assertIs(created.identification_status, IdentificationStatus.UNIDENTIFIED)
        self.assertNotEqual(created.id, self.item.id)
        self.assertIsInstance(json.loads(self.path.read_text()), list)

    def test_duplicate_blank_and_id_changes_refused(self):
        before = self.path.read_bytes()
        self.assertFalse(self.collection.add_item(record()))
        self.assertFalse(self.collection.add_item(record(' ')))
        self.assertFalse(self.collection.update_item(self.item.id, {'id':'replacement'}))
        self.assertFalse(self.edit({'item_type':'BANKNOTE'}).success)
        self.assertEqual(self.path.read_bytes(), before)

    def test_reference_resolves_same_item_after_ordinary_edit(self):
        self.assertTrue(self.edit({'country':'Canada'}).success)
        self.assertIs(self.reference.resolve(self.collection), self.item)
        self.assertIs(self.item.identification_status, IdentificationStatus.PARTIAL)

    def test_collection_replacement_reused_id_refused(self):
        self.app.collection = CoinCollection(str(self.path))
        self.assertFalse(self.edit({'notes':'wrong target'}).success)
        self.assertEqual(self.app.collection.items[0].notes, '')

    def test_record_replacement_reused_id_refused(self):
        self.collection.items = [record()]
        self.assertFalse(self.edit({'notes':'wrong target'}).success)
        with self.assertRaises(ValueError):
            self.reference.resolve(self.collection)

    def test_reload_and_duplicate_reference_refused(self):
        self.collection.load_collection()
        with self.assertRaises(ValueError):
            self.reference.resolve(self.collection)
        self.collection.items.append(record())
        with self.assertRaises(ValueError):
            CollectionItemReference.capture(self.collection, self.collection.items[0])

    def test_new_photo_copied_and_source_preserved(self):
        source = self.path.parent / 'source.jpg'
        source.write_bytes(b'synthetic media')
        self.assertTrue(self.edit(photos=[ItemPhoto(str(source), PhotoRole.BACK)]).success)
        managed = Path(self.item.photos[0].path)
        self.assertNotEqual(managed, source)
        self.assertEqual(managed.read_bytes(), source.read_bytes())
        self.assertIs(self.item.photos[0].role, PhotoRole.BACK)
        self.assertTrue(self.edit(photos=[]).success)
        self.assertTrue(managed.exists())
        self.assertTrue(source.exists())

    def test_failed_save_rolls_back_only_attempt_media(self):
        source = self.path.parent / 'source.jpg'
        source.write_bytes(b'synthetic')
        before = self.path.read_bytes()
        with patch.object(self.collection, 'save_collection', return_value=False):
            self.assertFalse(self.edit(photos=[ItemPhoto(str(source))]).success)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.item.photos, [])
        self.assertTrue(source.exists())
        self.assertEqual(list(self.path.parent.glob('managed_media/ordinary/*/*')), [])

    def test_missing_existing_media_and_metadata_are_preserved_on_failure(self):
        photo = ItemPhoto(str(self.path.parent / 'offline.jpg'), PhotoRole.FRONT, False, '', 7)
        self.item.photos = [photo]
        with patch.object(self.collection, 'update_item', return_value=False):
            self.assertFalse(self.edit({'notes':'attempt'}).success)
        self.assertEqual(photo.display_order, 7)
        self.assertFalse(photo.is_primary)
        self.assertTrue(self.edit({'notes':'keep offline'}).success)
        self.assertEqual(self.item.photos[0].path, photo.path)

    def test_reference_rechecked_after_ingestion(self):
        source = self.path.parent / 'source.jpg'
        source.write_bytes(b'synthetic')
        original = OrdinaryEntryManagedMediaStore.ingest
        def replace(store, *args):
            result = original(store, *args)
            self.collection.items = [record()]
            return result
        with patch.object(OrdinaryEntryManagedMediaStore, 'ingest', replace):
            self.assertFalse(self.edit(photos=[ItemPhoto(str(source))]).success)
        self.assertEqual(self.collection.items[0].photos, [])
        self.assertEqual(list(self.path.parent.glob('managed_media/ordinary/*/*')), [])

    def test_rollback_retains_modified_attempt_file(self):
        source = self.path.parent / 'source.jpg'
        source.write_bytes(b'synthetic')
        store = OrdinaryEntryManagedMediaStore(str(self.path))
        ingestion = store.ingest('stable', [ItemPhoto(str(source))])
        copied = Path(ingestion.photos[0].path)
        copied.write_bytes(b'modified')
        self.assertEqual(store.rollback(ingestion), (str(copied),))
        self.assertTrue(copied.exists())

    def test_provenance_is_preserved_and_cannot_be_forged(self):
        provenance = CaptureImportMediaProvenance(
            schema_version='1.0', import_id='11111111-1111-4111-8111-111111111111',
            source_kind='PROCESSED_SNAPSHOT', package_sha256='a' * 64,
            processed_snapshot_id='22222222-2222-4222-8222-222222222222',
            artifact_key='coin/front', artifact_sha256='b' * 64, variant='NORMALIZED')
        path = str(self.path.parent / 'unavailable-import.jpg')
        self.item.photos = [ItemPhoto(path, capture_import_media=provenance)]
        self.assertTrue(self.edit(photos=[ItemPhoto(path, PhotoRole.BACK)]).success)
        self.assertEqual(self.item.photos[0].capture_import_media, provenance)
        forged = ItemPhoto(str(self.path.parent / 'new.jpg'), capture_import_media=provenance)
        with patch.object(OrdinaryEntryManagedMediaStore, 'ingest') as ingest:
            self.assertFalse(self.edit(photos=[forged]).success)
            ingest.assert_not_called()

    def test_editor_captures_reference_before_open_and_uses_it_at_save(self):
        # Callback wiring is covered here; native visual acceptance is separate.
        import inspect
        from coin_collection_gui import CoinCollectionGUI
        code = inspect.getsource(CoinCollectionGUI.open_edit_item_window)
        self.assertLess(code.index('CollectionItemReference.capture'), code.index('tk.Toplevel'))
        self.assertIn('expected_reference=edit_reference', code)
        self.assertIn('self.app.update_collection_item(', code)


if __name__ == '__main__':
    unittest.main()
