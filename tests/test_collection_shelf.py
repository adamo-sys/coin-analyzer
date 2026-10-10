"""Synthetic read-only shelf contracts; no collector material."""
import copy
import tempfile
import unittest
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch

from PIL import Image
from coin_collection import CoinCollection, CollectionLoadState, IdentificationStatus, ItemPhoto
from tests.test_collector_work_queue_gui import item


PROHIBITED_PHOTO_PATHS = (
    "https://example.invalid/photo", r"\\server\share\photo", "//server/share/photo",
    "\\/server/share/photo", "/\\server/share/photo",
    r"\\?\UNC\server\share\photo", "//?/UNC/server/share/photo",
    r"\\.\UNC\server\share\photo", r"\??\UNC\server\share\photo",
    r"\\?\C:\photo.png", r"\\.\C:\photo.png", r"C:photo.png",
    r"C:\photos\NUL.png", r"C:\photos\photo.png:stream", "file:photo.png",
    "photo\x00.png", r"C:\photos\.. \photo.png",
    r"C:\photos\nonexistent\..\photo.png", r"C:\photos\..\photo.png",
    "C:/photos/nonexistent/../photo.png", "nonexistent\\../photo.png",
    r"..\photo.png", r".\nonexistent\..\redirect\photo.png",
)


def Collection(items, state=CollectionLoadState.LOADED):
    """Real read-only collection API without loading collector storage."""
    collection = CoinCollection.__new__(CoinCollection)
    collection.items = items
    collection.load_state = state
    collection.load_error = ""
    return collection

try:
    from collection_shelf import shelf_page, load_thumbnail
except ModuleNotFoundError:
    shelf_page = load_thumbnail = None


class ShelfTests(unittest.TestCase):
    def test_browsing_uses_detached_metadata_without_photo_access(self):
        from tests.test_collection_shelf_gui import PhotoAccessTrap
        specimens = [item(f"{n:03}", photos=[ItemPhoto("photo-trap.png")],
                          notes="needle" if n == 48 else "") for n in range(49)]
        before = copy.deepcopy([vars(value) for value in specimens])
        with PhotoAccessTrap() as trap:
            collection = Collection(specimens)
            for index, count in ((0, 24), (1, 24), (2, 1)):
                page = self.page(collection, page=index)
                self.assertEqual(len(page.cards), count)
                for card in page.cards:
                    self.assertIn("not loaded", card.photo.status.lower())
                    self.assertEqual(card.photo.path, "photo-trap.png")
                    self.assertIsNone(card.photo.signature)
            self.assertEqual(self.page(collection, query="needle").total, 1)
        self.assertEqual(trap.calls, [])
        self.assertEqual([vars(value) for value in specimens], before)

    def preview_without_widgets(self):
        from coin_collection_gui import SavedPhotoPreview
        from unittest.mock import MagicMock
        preview = SavedPhotoPreview.__new__(SavedPhotoPreview)
        preview.caption = MagicMock()
        preview.path = ""
        preview.has_photo = False
        preview.fit = MagicMock()
        return preview

    @unittest.skipUnless(__import__("os").name == "nt", "Native Windows attributes")
    def test_windows_validation_does_not_use_lstat_that_can_resolve_reparse_types(self):
        from collection_shelf import local_photo_path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.png"
            Image.new("RGB", (20, 20), "red").save(path)
            with patch("os.lstat", side_effect=AssertionError("Potential reparse resolution")):
                self.assertEqual(local_photo_path(str(path)), str(path))

    @unittest.skipUnless(__import__("os").name == "nt", "Win32 error translation")
    def test_attribute_query_failures_preserve_missing_and_unavailable_states(self):
        import ctypes
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from collection_shelf import _windows_path_attributes
        from coin_collection_gui import CoinCollectionGUI
        for code, error_type in ((2, FileNotFoundError), (3, FileNotFoundError), (5, PermissionError)):
            query = MagicMock(return_value=0xFFFFFFFF)
            with self.subTest(code=code), \
                 patch("ctypes.WinDLL", return_value=SimpleNamespace(GetFileAttributesW=query)), \
                 patch("ctypes.get_last_error", return_value=code), \
                 patch("os.stat", side_effect=error_type("synthetic metadata failure")), \
                 patch("collection_shelf._local_windows_drive", return_value=True):
                with self.assertRaises(error_type):
                    _windows_path_attributes(r"C:\photos")
                card = self.page(Collection([item("a", image_path=r"C:\photos\photo.png", photos=[])])).cards[0]
                self.assertIn("not loaded", card.photo.status.lower())
    @unittest.skipUnless(__import__("os").name == "nt", "Native Windows normalization")
    def test_missing_parent_traversal_resolves_existing_file_but_is_rejected(self):
        from collection_shelf import local_photo_path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.png"
            Image.new("RGB", (20, 20), "red").save(path)
            traversal = str(Path(directory) / "nonexistent" / ".." / "synthetic.png")
            # Windows collapses this even though the intermediate directory is absent.
            self.assertTrue(__import__("os").path.isfile(traversal))
            self.assertEqual(Path(traversal).read_bytes(), path.read_bytes())
            self.assertIsNone(local_photo_path(traversal))

    @unittest.skipUnless(__import__("os").name == "nt", "Windows ancestor inspection")
    def test_reparse_at_root_ancestor_or_leaf_stops_shelf_consumers(self):
        import stat
        from collection_shelf import ShelfPhoto
        from coin_collection_gui import CoinCollectionGUI, SavedPhotoPreview
        assert load_thumbnail is not None
        path = r"C:\photos\synthetic.png"
        prefixes = ["C:\\", r"C:\photos", path]
        for blocked in prefixes:
            visited = []
            def inspect(current):
                visited.append(current)
                self.assertIn(current, prefixes[:prefixes.index(blocked) + 1])
                return stat.FILE_ATTRIBUTE_REPARSE_POINT if current == blocked else 0
            with self.subTest(blocked=blocked), ExitStack() as stack:
                stack.enter_context(patch("collection_shelf._local_windows_drive", return_value=True))
                stack.enter_context(patch("collection_shelf._windows_path_attributes", side_effect=inspect))
                access = [stack.enter_context(patch(target, side_effect=AssertionError(target)))
                          for target in ("os.lstat", "os.stat", "os.path.exists", "pathlib.Path.read_bytes",
                                         "builtins.open", "PIL.Image.open")]
                card = self.page(Collection([item("a", image_path=path, photos=[])])).cards[0]
                self.assertIn("not loaded", card.photo.status)
                self.assertIn("local", load_thumbnail(ShelfPhoto(path, ""))[1])
                self.assertTrue(visited)
                for operation in access:
                    operation.assert_not_called()

    @unittest.skipUnless(__import__("os").name == "nt", "Native Windows junction")
    def test_native_junction_and_missing_parent_traversal_are_rejected(self):
        import _winapi
        import os
        from collection_shelf import local_photo_path
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            Image.new("RGB", (20, 20), "red").save(target / "synthetic.png")
            junction = root / "redirect"
            # Guarded native Windows test; cross-platform stubs omit this API.
            _winapi.CreateJunction(str(target), str(junction))  # pyright: ignore[reportAttributeAccessIssue]
            try:
                for suffix in (r"redirect\synthetic.png", r".\redirect/synthetic.png",
                               r"missing\..\redirect\synthetic.png",
                               r"missing/../redirect\synthetic.png",
                               r"redirect\..\target\synthetic.png"):
                    raw = directory + "\\" + suffix
                    self.assertTrue(os.path.isfile(raw), raw)
                    self.assertIsNone(local_photo_path(raw), raw)
            finally:
                os.rmdir(junction)

    @unittest.skipUnless(__import__("os").name == "nt", "Windows missing prefix")
    def test_missing_prefix_stops_inspection_without_hiding_an_existing_target(self):
        from collection_shelf import local_photo_path
        visited = []
        def inspect(current):
            visited.append(current)
            if current == r"C:\missing":
                raise FileNotFoundError(current)
            return 0
        with patch("collection_shelf._local_windows_drive", return_value=True), \
             patch("collection_shelf._windows_path_attributes", side_effect=inspect):
            self.assertEqual(local_photo_path(r"C:/./missing\nested/photo.png"),
                             r"C:\missing\nested\photo.png")
        self.assertEqual(visited, ["C:\\", r"C:\missing"])

    def test_dot_and_mixed_separators_keep_local_saved_preview_working(self):
        import os
        from coin_collection_gui import CoinCollectionGUI, SavedPhotoPreview
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.png"
            Image.new("RGB", (20, 20), "red").save(path)
            raw = directory + ("/./synthetic.png" if os.name != "nt" else "\\./synthetic.png")
            self.assertEqual(CoinCollectionGUI.photo_preview_status(ItemPhoto(raw)), "")
            preview = self.preview_without_widgets()
            SavedPhotoPreview.show_photo(preview, ItemPhoto(raw))
            self.assertEqual(preview.preview_status, "")
            assert preview.source_image is not None
            self.assertEqual(preview.source_image.size, (20, 20))
            preview.source_image.close()

    def test_ordinary_preview_accepts_parent_and_simple_relative_references(self):
        import os
        from coin_collection_gui import CoinCollectionGUI, SavedPhotoPreview
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "child").mkdir()
            Image.new("RGB", (20, 20), "red").save(root / "synthetic.png")
            Image.new("RGB", (20, 20), "blue").save(root / "child" / "synthetic.png")
            previous = os.getcwd()
            try:
                os.chdir(root / "child")
                for reference in ("../synthetic.png", "synthetic.png"):
                    with self.subTest(reference=reference):
                        photo = ItemPhoto(reference)
                        self.assertEqual(CoinCollectionGUI.photo_preview_status(photo), "")
                        self.assertEqual(CoinCollectionGUI.photo_detail_rows([photo])[0]["status"], "")
                        preview = self.preview_without_widgets()
                        SavedPhotoPreview.show_photo(preview, photo)
                        self.assertEqual(preview.preview_status, "")
                        assert preview.source_image is not None
                        self.assertEqual(preview.source_image.size, (20, 20))
                        preview.source_image.close()
            finally:
                os.chdir(previous)

    def page(self, collection, **kwargs):
        self.assertIsNotNone(shelf_page, "Shelf projection is missing")
        assert shelf_page is not None
        return shelf_page(collection, **kwargs)

    def test_pagination_boundaries_and_clamping(self):
        for count, lengths in ((0, [0]), (1, [1]), (24, [24]),
                               (25, [24, 1]), (48, [24, 24]), (49, [24, 24, 1])):
            with self.subTest(count=count):
                collection = Collection([item(f"{n:03}") for n in range(count)])
                seen = []
                for index, length in enumerate(lengths):
                    page = self.page(collection, page=index)
                    self.assertEqual(len(page.cards), length)
                    self.assertEqual(page.total, count)
                    self.assertEqual(page.pages, len(lengths))
                    seen.extend(card.reference.item_id for card in page.cards)
                self.assertEqual(seen, [f"{n:03}" for n in range(count)])
                self.assertEqual(self.page(collection, page=999).index, len(lengths)-1)
                self.assertEqual(self.page(collection, page=-1).index, 0)

    def test_detached_projection_never_normalizes_source_metadata(self):
        photos = [ItemPhoto("missing-b", is_primary=True, display_order=9),
                  ItemPhoto("missing-a", is_primary=True, display_order=2)]
        specimen = item("a", photos=photos, image_path="legacy")
        before = copy.deepcopy(vars(specimen))
        card = self.page(Collection([specimen])).cards[0]
        self.assertEqual(vars(specimen), before)
        self.assertEqual(Path(card.photo.path).name, "missing-a")
        specimen.title = "Changed source"
        self.assertNotEqual(card.label, specimen.title)
        self.assertIs(specimen.photos[0], photos[0])

    def test_truthful_labels_dates_search_and_quantity_are_reused(self):
        collection = Collection([item("old", date_added="2026-01-01", notes="needle"),
                                 item("new", date_added="2026-10-01", quantity=99,
                                      identification_status=IdentificationStatus.UNIDENTIFIED),
                                 item("unknown", date_added="invalid")])
        page = self.page(collection)
        self.assertEqual([c.reference.item_id for c in page.cards], ["new", "old", "unknown"])
        self.assertEqual((page.cards[0].label, page.cards[0].status, page.cards[0].recorded_date),
                         ("Unidentified coin", "Unidentified", "2026-10-01"))
        self.assertEqual(self.page(collection, query=" needle ").total, 1)

    def test_absent_missing_corrupt_legacy_and_changed_photos(self):
        assert load_thumbnail is not None
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.png"
            specimen = item("a", photos=[], image_path=str(path))
            for data in (None, b"not an image", b"different bytes"):
                if data is not None:
                    path.write_bytes(data)
                card = self.page(Collection([specimen])).cards[0]
                self.assertEqual(card.photo.path, str(path))
                self.assertIn("not loaded", card.photo.status)
                self.assertIsNone(load_thumbnail(card.photo)[0])
        card = self.page(Collection([item("none", photos=[], image_path="")])).cards[0]
        self.assertIn("No photo reference recorded", card.photo.status)

    def test_missing_primary_never_substitutes_secondary_or_legacy(self):
        assert load_thumbnail is not None
        specimen = item("a", image_path="legacy", photos=[
            ItemPhoto("missing-primary", is_primary=True), ItemPhoto("secondary")])
        card = self.page(Collection([specimen])).cards[0]
        self.assertEqual(Path(card.photo.path).name, "missing-primary")
        self.assertIsNone(load_thumbnail(card.photo)[0])

    def test_missing_failed_and_ambiguous_collection_fail_closed(self):
        self.assertEqual(self.page(Collection([], CollectionLoadState.MISSING)).total, 0)
        for collection in (Collection([], CollectionLoadState.FAILED),
                           Collection([item("same"), item("same")])):
            with self.assertRaises(ValueError):
                self.page(collection)

    def test_network_photo_paths_are_not_accessed(self):
        assert load_thumbnail is not None
        from unittest.mock import patch
        for path in ("https://example.invalid/photo", "\\\\server\\share\\photo", "//server/share/photo"):
            with patch("os.stat", side_effect=AssertionError("Network access")):
                card = self.page(Collection([item("a", photos=[], image_path=path)])).cards[0]
                self.assertIsNone(load_thumbnail(card.photo)[0])

    def test_prohibited_paths_never_reach_filesystem_or_decoder(self):
        from collection_shelf import ShelfPhoto
        assert load_thumbnail is not None
        for path in PROHIBITED_PHOTO_PATHS:
            with self.subTest(path=path), ExitStack() as stack:
                access = [stack.enter_context(patch(target, side_effect=AssertionError(target)))
                          for target in ("os.stat", "os.lstat", "collection_shelf._windows_path_attributes", "os.path.exists",
                                         "pathlib.Path.absolute", "pathlib.Path.resolve",
                                         "pathlib.Path.read_bytes", "builtins.open", "PIL.Image.open")]
                card = self.page(Collection([item("a", photos=[], image_path=path)])).cards[0]
                self.assertIn("not loaded", card.photo.status)
                self.assertIsNone(load_thumbnail(card.photo)[0])
                image, status = load_thumbnail(ShelfPhoto(path, ""))
                self.assertIsNone(image)
                self.assertIn("local", status)
                for operation in access:
                    operation.assert_not_called()

    def test_relative_path_under_network_cwd_never_accesses_filesystem(self):
        from collection_shelf import local_photo_path
        with patch("os.getcwd", return_value="\\/server/share"), \
             patch("os.lstat") as lstat, patch("os.stat") as stat:
            self.assertIsNone(local_photo_path("photo.png"))
            lstat.assert_not_called()
            stat.assert_not_called()

    @unittest.skipUnless(__import__("os").name == "nt", "Windows drive and redirect checks")
    def test_drive_classification_uses_only_local_device_namespace(self):
        import ctypes
        from collection_shelf import _local_windows_drive
        # Guarded native Windows test; cross-platform stubs omit this loader.
        kernel32 = ctypes.windll.kernel32  # pyright: ignore[reportAttributeAccessIssue]
        for target, allowed in ((r"\Device\HarddiskVolume3", True),
                                (r"\Device\LanmanRedirector\server\share", False),
                                (r"\Device\Mup\server\share", False),
                                (r"\??\UNC\server\share", False),
                                (r"\??\C:\redirect", False), ("", False)):
            def query(name, buffer, size):
                self.assertEqual(name, "Z:")
                buffer.value = target
                return len(target) + 1 if target else 0
            with self.subTest(target=target), \
                 patch.object(kernel32, "QueryDosDeviceW", side_effect=query), \
                 patch.object(kernel32, "GetDriveTypeW", side_effect=AssertionError("Volume query")), \
                 patch("os.stat") as metadata, patch("os.lstat") as lstat:
                self.assertEqual(_local_windows_drive("Z:\\"), allowed)
                metadata.assert_not_called()
                lstat.assert_not_called()

    @unittest.skipUnless(__import__("os").name == "nt", "Windows drive and redirect checks")
    def test_mapped_drive_and_reparse_points_never_follow_target(self):
        import stat
        from collection_shelf import local_photo_path
        from coin_collection_gui import CoinCollectionGUI
        with patch("collection_shelf._local_windows_drive", return_value=False), \
             patch("collection_shelf._windows_path_attributes", side_effect=AssertionError("Mapped drive access")), \
             patch("os.lstat") as lstat, patch("os.stat") as metadata, \
             patch("os.path.exists") as exists:
            card = self.page(Collection([item("a", photos=[], image_path=r"Z:\photo.png")])).cards[0]
            self.assertIn("not loaded", card.photo.status)
            lstat.assert_not_called()
            metadata.assert_not_called()
            exists.assert_not_called()
        with patch("collection_shelf._local_windows_drive", return_value=True), \
             patch("collection_shelf._windows_path_attributes", return_value=stat.FILE_ATTRIBUTE_REPARSE_POINT) as attributes, \
             patch("os.lstat") as lstat, \
             patch("os.stat") as metadata, patch("os.path.exists") as exists:
            self.assertIsNone(local_photo_path(r"C:\redirect\photo.png"))
            attributes.assert_called_once_with("C:\\")
            lstat.assert_not_called()
            metadata.assert_not_called()
            exists.assert_not_called()

    def test_local_relative_photo_is_bound_and_unavailable_is_truthful(self):
        from collection_shelf import local_photo_path
        assert load_thumbnail is not None
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.png"
            Image.new("RGB", (20, 20), "red").save(path)
            with patch("os.getcwd", return_value=directory):
                self.assertEqual(local_photo_path("synthetic.png"), str(path))
                card = self.page(Collection([item("a", photos=[], image_path="synthetic.png")])).cards[0]
            self.assertEqual(card.photo.path, "synthetic.png")
            self.assertIn("not loaded", card.photo.status)
            with patch("os.stat", side_effect=AssertionError("Photo stat")) as metadata:
                self.page(Collection([item("a", photos=[], image_path=str(path))]))
                metadata.assert_not_called()

    def test_managed_photo_changed_since_save_refuses_preview(self):
        assert load_thumbnail is not None
        import hashlib
        from coin_collection import CaptureImportMediaProvenance
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "managed.png"
            Image.new("RGB", (100, 100), "red").save(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            provenance = CaptureImportMediaProvenance(
                "1.0", "11111111-1111-4111-8111-111111111111", "PROCESSED_SNAPSHOT",
                "a" * 64, "22222222-2222-4222-8222-222222222222", "synthetic", digest, "NORMALIZED")
            from collection_shelf import ShelfPhoto, _signature
            # Shared preview helper remains compatible outside shelf rendering.
            snapshot = ShelfPhoto(str(path), "", _signature(str(path)), provenance.artifact_sha256)
            image, status = load_thumbnail(snapshot)
            self.assertEqual(status, "")
            assert image is not None
            image.close()
            Image.new("RGB", (100, 100), "blue").save(path)
            image, status = load_thumbnail(snapshot)
            self.assertIsNone(image)
            self.assertIn("changed", status.lower())

    def test_browsing_does_not_serialize_persist_or_create_cache(self):
        from unittest.mock import patch
        from coin_collection import CoinItem
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.png"
            Image.new("RGB", (80, 60), "red").save(path)
            collection = Collection([item("a", photos=[], image_path=str(path))])
            before = {entry.name: entry.read_bytes() for entry in Path(directory).iterdir()}
            with patch.object(CoinItem, "to_dict", side_effect=AssertionError("Serialization")), \
                 patch.object(CoinCollection, "save_collection", side_effect=AssertionError("Persistence")):
                page = self.page(collection)
                self.assertIn("not loaded", page.cards[0].photo.status)
            self.assertEqual({entry.name: entry.read_bytes() for entry in Path(directory).iterdir()}, before)
