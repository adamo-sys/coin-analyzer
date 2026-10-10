"""Action targeting tests retain real collection identity checks."""
import unittest
import copy
import os
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from coin_collection import CollectionLoadState
from tests.test_collection_shelf import Collection, item, shelf_page
from tests.test_collection_shelf import PROHIBITED_PHOTO_PATHS

try:
    from collection_shelf_gui import ShelfActions
except ModuleNotFoundError:
    ShelfActions = None


class ShelfActionTests(unittest.TestCase):
    def test_metadata_details_text_never_probes_photos(self):
        from coin_collection import ItemPhoto
        from coin_collection_gui import CoinCollectionGUI
        specimen = item("a", photos=[ItemPhoto("photo-trap.png", notes="recorded note")])
        before = copy.deepcopy(vars(specimen))
        with PhotoAccessTrap() as trap:
            text = CoinCollectionGUI.item_details_text(specimen, metadata_only=True)
        self.assertIn("photo-trap.png", text)
        self.assertIn("recorded note", text)
        self.assertEqual(trap.calls, [])
        self.assertEqual(vars(specimen), before)

    def test_metadata_details_prohibited_references_never_reach_filesystem(self):
        from coin_collection import ItemPhoto
        from coin_collection_gui import CoinCollectionGUI
        for path in PROHIBITED_PHOTO_PATHS:
            with self.subTest(path=path), PhotoAccessTrap() as trap:
                text = CoinCollectionGUI.item_details_text(
                    item("a", photos=[ItemPhoto(path)]), metadata_only=True)
                self.assertIn("not loaded", text.lower())
            self.assertEqual(trap.calls, [])

    def test_details_and_edit_photo_preparation_do_not_mutate_source(self):
        import copy
        from coin_collection import ItemPhoto
        from coin_collection_gui import CoinCollectionGUI
        specimen = item("a", photos=[ItemPhoto("b", is_primary=True, display_order=9),
                                     ItemPhoto("a", is_primary=True, display_order=2)])
        for prepare in (CoinCollectionGUI.item_details_text, CoinCollectionGUI.photos_from_item):
            before = copy.deepcopy(vars(specimen))
            prepare(specimen)
            self.assertEqual(vars(specimen), before)

    def test_details_edit_revalidate_at_click_and_pass_exact_record(self):
        self.assertIsNotNone(ShelfActions, "Shelf actions are missing")
        specimen = item("a")
        collection = Collection([specimen])
        calls = []
        actions = ShelfActions(lambda: collection, lambda value: calls.append(("details", value)),
                               lambda value: calls.append(("edit", value)))
        card = shelf_page(collection).cards[0]
        actions.open(card, "details")
        actions.open(card, "edit")
        self.assertEqual(calls, [("details", specimen), ("edit", specimen)])
        for mode in ("replaced", "deleted", "duplicate", "failed", "collection", "id"):
            with self.subTest(mode=mode):
                collection = Collection([specimen])
                card = shelf_page(collection).cards[0]
                if mode == "replaced": collection.items[:] = [item("a")]
                if mode == "deleted": collection.items.clear()
                if mode == "duplicate": collection.items.append(item("a"))
                if mode == "failed": collection.load_state = CollectionLoadState.FAILED
                if mode == "collection": collection = Collection([specimen])
                if mode == "id": specimen.id = "changed"
                for action in ("details", "edit"):
                    with self.assertRaises(ValueError): actions.open(card, action)
                specimen.id = "a"
        self.assertEqual(len(calls), 2)


class PhotoAccessTrap(ExitStack):
    """Count forbidden calls even when application code catches the exception.

    Storage/lock I/O is allowed; all synthetic photo references contain
    'photo-trap'. Helper/decoder calls are forbidden regardless of arguments.
    """
    def __enter__(self):
        super().__enter__()
        self.calls = []
        for target in (
            "collection_shelf.local_photo_path", "coin_collection_gui.local_photo_path",
            "collection_shelf._signature", "collection_shelf.load_thumbnail",
            "collection_shelf._local_windows_drive", "collection_shelf._windows_path_attributes",
            "coin_collection_gui.CoinCollectionGUI.photo_preview_status",
            "coin_collection_gui.SavedPhotoPreview", "PIL.Image.open",
            "PIL.ImageTk.PhotoImage", "coin_collection_gui.filedialog.askopenfilenames",
            "managed_media.OrdinaryEntryManagedMediaStore",
        ):
            self.enter_context(patch(target, side_effect=self.forbidden(target), create=True))
        # Include bindings held by rendering code, even if later removed.
        self.enter_context(patch("collection_shelf_gui.load_thumbnail",
                                 side_effect=self.forbidden("render thumbnail"), create=True))
        for target in ("os.stat", "os.lstat", "os.open", "os.path.exists", "os.path.isfile",
                       "os.path.abspath", "os.path.realpath", "builtins.open", "io.open",
                       "pathlib.Path.read_bytes", "pathlib.Path.resolve", "pathlib.Path.absolute"):
            module, name = target.rsplit(".", 1)
            import importlib
            owner = Path if module == "pathlib.Path" else importlib.import_module(module)
            original = getattr(owner, name)
            def guarded(path, *args, _original=original, _target=target, **kwargs):
                if "photo-trap" in str(path):
                    return self.forbidden(_target)(path)
                return _original(path, *args, **kwargs)
            self.enter_context(patch(target, side_effect=guarded, autospec=module == "pathlib.Path"))
        return self

    def forbidden(self, target):
        def reject(*args, **kwargs):
            self.calls.append(target)
            raise AssertionError(f"Prohibited photo access: {target}")
        return reject


class MetadataSaveTests(unittest.TestCase):
    def setUp(self):
        from coin_collection import CoinCollection, CoinCollectionApp
        from collection_item_reference import CollectionItemReference
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        # Load raw historical JSON; never canonicalize the fixture through to_dict.
        import json
        provenance = {
            "schema_version": "1.0", "import_id": "11111111-1111-4111-8111-111111111111",
            "source_kind": "PROCESSED_SNAPSHOT", "package_sha256": "a" * 64,
            "processed_snapshot_id": "22222222-2222-4222-8222-222222222222",
            "artifact_key": "synthetic", "artifact_sha256": "b" * 64, "variant": "NORMALIZED",
        }
        self.raw = [
            {"id": key, "image_path": "photo-trap-legacy.png", "photos": [
                {"path": "photo-trap.png", "role": "OTHER", "is_primary": True,
                 "notes": "photo note", "display_order": 9, "capture_import_media": provenance},
                {"path": "photo-trap-second.png", "role": "OTHER", "is_primary": True,
                 "notes": "second note", "display_order": 2},
            ]} for key in ("a", "unrelated")
        ] + [{"id": "legacy", "image_path": "photo-trap-legacy-only.png", "photos": []}]
        storage = Path(self.directory.name) / "collection.json"
        storage.write_text(json.dumps(self.raw), encoding="utf-8")
        self.collection = CoinCollection(str(storage))
        self.specimen = self.collection.items[0]
        self.app = CoinCollectionApp.__new__(CoinCollectionApp)
        self.app.collection = self.collection
        self.reference = CollectionItemReference.capture(self.collection, self.specimen)

    def test_metadata_save_preserves_photo_and_provenance_with_real_storage(self):
        from coin_collection import CoinCollection
        import json
        before = copy.deepcopy([vars(value) for value in self.collection.items])
        with PhotoAccessTrap() as trap:
            result = self.app.update_collection_item("a", {"grade": "VF", "purchase_price": "12.50"},
                expected_reference=self.reference, metadata_only=True)
        self.assertTrue(result.success, result.error)
        self.assertEqual(trap.calls, [])
        expected = copy.deepcopy(before)
        expected[0]["grade"] = "VF"
        from decimal import Decimal
        expected[0]["purchase_price"] = Decimal("12.50")
        self.assertEqual([vars(value) for value in self.collection.items], expected)
        persisted = json.loads(Path(self.collection.storage_path).read_text(encoding="utf-8"))
        for actual, original in zip(persisted, self.raw):
            self.assertEqual(actual["photos"], original["photos"])
            self.assertEqual(actual["image_path"], original["image_path"])
        self.assertEqual(persisted[0]["grade"], "VF")
        self.assertEqual(persisted[0]["purchase_price"], "12.50")
        reloaded = CoinCollection(self.collection.storage_path)
        self.assertEqual([vars(value) for value in reloaded.items], expected)

    def test_serialization_is_detached_but_ordinary_output_is_canonical(self):
        before = copy.deepcopy([vars(value) for value in self.collection.items])
        serialized = [value.to_dict() for value in self.collection.items]
        self.assertEqual([vars(value) for value in self.collection.items], before)
        self.assertEqual([photo["display_order"] for photo in serialized[0]["photos"]], [0, 1])
        self.assertEqual([photo["is_primary"] for photo in serialized[0]["photos"]], [True, False])
        self.assertEqual(serialized[0]["image_path"], "photo-trap-second.png")
        self.assertEqual(serialized[2]["photos"][0]["path"], "photo-trap-legacy-only.png")

    def test_photo_inputs_rejected_before_media_or_reference_access(self):
        from coin_collection import ItemPhoto
        before = Path(self.collection.storage_path).read_bytes()
        for updates, photos in (({"photos": []}, None), ({"image_path": "photo-trap-new.png"}, None),
                                ({}, []), ({}, [ItemPhoto("photo-trap-new.png")])):
            with self.subTest(updates=updates, photos=photos), PhotoAccessTrap() as trap:
                result = self.app.update_collection_item("a", updates, photos,
                    expected_reference=self.reference, metadata_only=True)
                self.assertFalse(result.success)
                self.assertEqual(trap.calls, [])
            self.assertEqual(Path(self.collection.storage_path).read_bytes(), before)

    def test_failed_storage_and_stale_records_do_not_report_success(self):
        before = copy.deepcopy([vars(value) for value in self.collection.items])
        disk_before = Path(self.collection.storage_path).read_bytes()
        references = [(value, list(value.photos)) for value in self.collection.items]
        with PhotoAccessTrap() as trap, patch("coin_collection.write_json_atomically", side_effect=OSError("synthetic failure")):
            result = self.app.update_collection_item("a", {"notes": "draft"},
                expected_reference=self.reference, metadata_only=True)
        self.assertFalse(result.success)
        self.assertEqual(trap.calls, [])
        self.assertEqual([vars(value) for value in self.collection.items], before)
        self.assertEqual(Path(self.collection.storage_path).read_bytes(), disk_before)
        for actual, (original, photos) in zip(self.collection.items, references):
            self.assertIs(actual, original)
            for photo, original_photo in zip(actual.photos, photos):
                self.assertIs(photo, original_photo)
        for mode in ("replaced", "deleted", "duplicate", "failed", "id", "collection"):
            self.collection.items = [self.specimen]
            self.collection.load_state = CollectionLoadState.LOADED
            self.specimen.id = "a"
            self.app.collection = self.collection
            if mode == "replaced": self.collection.items = [item("a")]
            if mode == "deleted": self.collection.items = []
            if mode == "duplicate": self.collection.items.append(item("a"))
            if mode == "failed": self.collection.load_state = CollectionLoadState.FAILED
            if mode == "id": self.specimen.id = "changed"
            if mode == "collection": self.app.collection = Collection([self.specimen])
            with self.subTest(mode=mode), PhotoAccessTrap() as trap:
                result = self.app.update_collection_item("a", {"notes": "draft"},
                    expected_reference=self.reference, metadata_only=True)
            self.assertFalse(result.success)
            self.assertEqual(trap.calls, [])
