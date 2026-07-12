import os
import tempfile
import unittest
from datetime import datetime, timedelta

from coin_collection import CoinItem, ItemPhoto, PhotoRole
from coin_collection_gui import CoinCollectionGUI
from photo_inbox import PhotoInboxConfig, PhotoInboxManager, PhotoSetState


class FixedClock:
    def __init__(self):
        self.current = datetime(2026, 7, 12, 11, 0, 0)

    def __call__(self):
        return self.current


class DummyCollection:
    def __init__(self, items=None, update_succeeds=True):
        self.items = list(items or [])
        self.update_succeeds = update_succeeds
        self.update_calls = []

    def get_all_items(self):
        return self.items

    def search_items(self, query):
        query = str(query or "").lower().strip()
        if not query:
            return self.items
        matches = []
        for item in self.items:
            searchable = f"{item.id} {item.country} {item.denomination} {item.year} {item.grade}".lower()
            if query in searchable:
                matches.append(item)
        return matches

    def update_item(self, item_id, updates):
        self.update_calls.append((item_id, updates))
        if not self.update_succeeds:
            return False
        for item in self.items:
            if item.id == item_id:
                for key, value in updates.items():
                    setattr(item, key, value)
                return True
        return False


class DummyApp:
    def __init__(self, collection):
        self.collection = collection


def make_gui(collection):
    gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
    gui.app = DummyApp(collection)
    gui.refresh_calls = 0
    gui.refresh_collection_list = lambda: setattr(gui, "refresh_calls", gui.refresh_calls + 1)
    return gui


def make_item(item_id="item-1", photos=None, image_path=""):
    return CoinItem(
        id=item_id,
        image_path=image_path,
        country="Canada",
        denomination="Cent",
        year="1920",
        grade="VF-20",
        notes="target",
        date_added="2026-07-12",
        photos=photos or [],
    )


def make_manager(tmpdir):
    clock = FixedClock()
    inbox = os.path.join(tmpdir, "incoming")
    os.makedirs(inbox, exist_ok=True)
    config = PhotoInboxConfig(
        inbox_folder=inbox,
        state_path=os.path.join(tmpdir, "photo_inbox_state.json"),
        file_stability_seconds=0,
        grouping_window_seconds=90,
    )
    return PhotoInboxManager(config=config, now_fn=clock)


def write_photo(manager, name):
    path = os.path.abspath(os.path.join(manager.config.inbox_folder, name))
    with open(path, "wb") as handle:
        handle.write(b"photo")
    timestamp = (manager.now_fn() - timedelta(minutes=5)).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path


class Phase2B3PhotoInboxAttachTests(unittest.TestCase):
    def test_attach_disabled_with_no_photo_set_selection(self):
        self.assertFalse(CoinCollectionGUI.can_attach_existing_from_inbox([], ""))

    def test_selected_pending_photo_set_enables_attach(self):
        self.assertTrue(CoinCollectionGUI.can_attach_existing_from_inbox([{"id": "set-1"}], "set-1"))

    def test_existing_item_search_selects_matching_target(self):
        target = make_item(item_id="coin-1904", photos=[ItemPhoto("front.jpg", is_primary=True)])
        other = make_item(item_id="coin-1910")
        gui = make_gui(DummyCollection([target, other]))

        matches = gui.search_attach_targets("1904")

        self.assertEqual([target], matches)

    def test_confirmation_summary_shows_correct_target(self):
        item = make_item(
            item_id="coin-1",
            photos=[ItemPhoto("front.jpg", role=PhotoRole.FRONT, is_primary=True)],
        )
        gui = make_gui(DummyCollection([item]))

        summary = gui.attach_target_summary(item)

        self.assertIn("ID: coin-1", summary)
        self.assertIn("Canada Cent 1920", summary)
        self.assertIn("Photos: 1", summary)
        self.assertIn("Primary image: front.jpg", summary)

    def test_append_new_photos_preserves_existing_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            first = write_photo(manager, "new_front.jpg")
            second = write_photo(manager, "new_back.jpg")
            manager.scan()
            item = make_item(photos=[ItemPhoto("existing.jpg", is_primary=True, display_order=0)])
            gui = make_gui(DummyCollection([item]))

            result = gui.merge_inbox_photos_into_item(item, manager, manager.get_pending_sets()[0].id)

            self.assertEqual(["existing.jpg", second, first], [photo.path for photo in result["photos"]])
            self.assertEqual(2, result["added_count"])

    def test_preserve_existing_roles_notes_and_primary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "new_front.jpg")
            manager.scan()
            existing = ItemPhoto(
                "existing.jpg",
                role=PhotoRole.CERT_LABEL,
                is_primary=True,
                notes="slab label",
                display_order=0,
            )
            item = make_item(photos=[existing])
            gui = make_gui(DummyCollection([item]))

            result = gui.merge_inbox_photos_into_item(item, manager, manager.get_pending_sets()[0].id)

            self.assertEqual(PhotoRole.CERT_LABEL, result["photos"][0].role)
            self.assertEqual("slab label", result["photos"][0].notes)
            self.assertTrue(result["photos"][0].is_primary)
            self.assertFalse(result["photos"][1].is_primary)

    def test_no_primary_normalizes_deterministically(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            first = write_photo(manager, "new_front.jpg")
            second = write_photo(manager, "new_back.jpg")
            manager.scan()
            item = make_item(photos=[], image_path="")
            gui = make_gui(DummyCollection([item]))

            result = gui.merge_inbox_photos_into_item(item, manager, manager.get_pending_sets()[0].id)

            self.assertEqual([second, first], [photo.path for photo in result["photos"]])
            self.assertEqual([True, False], [photo.is_primary for photo in result["photos"]])

    def test_duplicate_path_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            duplicate = write_photo(manager, "duplicate.jpg")
            write_photo(manager, "new.jpg")
            manager.scan()
            item = make_item(photos=[ItemPhoto(duplicate, is_primary=True)])
            gui = make_gui(DummyCollection([item]))

            result = gui.merge_inbox_photos_into_item(item, manager, manager.get_pending_sets()[0].id)

            self.assertEqual(1, result["added_count"])
            self.assertEqual(1, result["skipped_count"])
            self.assertEqual(2, len(result["photos"]))

    def test_all_duplicate_set_leaves_state_pending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            duplicate = write_photo(manager, "duplicate.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id
            item = make_item(photos=[ItemPhoto(duplicate, is_primary=True)])
            collection = DummyCollection([item])
            gui = make_gui(collection)

            result = gui.attach_photo_set_to_item(manager, photo_set_id, item)

            self.assertFalse(result["success"])
            self.assertEqual(0, len(collection.update_calls))
            self.assertEqual(PhotoSetState.NEW, manager.state.photo_sets[photo_set_id].state)

    def test_cancel_leaves_set_pending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "front.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id

            self.assertEqual(PhotoSetState.NEW, manager.state.photo_sets[photo_set_id].state)

    def test_validation_failure_leaves_set_pending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "front.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id
            gui = make_gui(DummyCollection([]))

            result = gui.attach_photo_set_to_item(manager, photo_set_id, None)

            self.assertFalse(result["success"])
            self.assertEqual(PhotoSetState.NEW, manager.state.photo_sets[photo_set_id].state)

    def test_save_failure_leaves_set_pending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "front.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id
            item = make_item(photos=[ItemPhoto("existing.jpg", is_primary=True)])
            collection = DummyCollection([item], update_succeeds=False)
            gui = make_gui(collection)

            result = gui.attach_photo_set_to_item(manager, photo_set_id, item)

            self.assertFalse(result["success"])
            self.assertEqual(PhotoSetState.NEW, manager.state.photo_sets[photo_set_id].state)

    def test_successful_attach_marks_set_attached_and_refreshes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "front.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id
            item = make_item(photos=[ItemPhoto("existing.jpg", is_primary=True)])
            collection = DummyCollection([item])
            gui = make_gui(collection)
            refresh_calls = []

            result = gui.attach_photo_set_to_item(
                manager,
                photo_set_id,
                item,
                refresh_callback=lambda: refresh_calls.append("refresh"),
            )

            self.assertTrue(result["success"])
            self.assertEqual(PhotoSetState.ATTACHED, manager.state.photo_sets[photo_set_id].state)
            self.assertEqual("item-1", manager.state.photo_sets[photo_set_id].linked_item_id)
            self.assertEqual(["refresh"], refresh_calls)
            self.assertEqual(1, gui.refresh_calls)

    def test_repeated_callback_is_idempotent_and_adds_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "front.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id
            item = make_item(photos=[ItemPhoto("existing.jpg", is_primary=True)])
            collection = DummyCollection([item])
            gui = make_gui(collection)

            first = gui.attach_photo_set_to_item(manager, photo_set_id, item)
            second = gui.attach_photo_set_to_item(manager, photo_set_id, item)

            self.assertTrue(first["success"])
            self.assertFalse(second["success"])
            paths = [photo.path for photo in item.normalized_photos()]
            self.assertEqual(len(paths), len(set(paths)))
            self.assertEqual(1, len(collection.update_calls))

    def test_legacy_primary_image_remains_visible_after_attach(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "new.jpg")
            manager.scan()
            item = make_item(photos=[], image_path="legacy.jpg")
            collection = DummyCollection([item])
            gui = make_gui(collection)

            result = gui.attach_photo_set_to_item(manager, manager.get_pending_sets()[0].id, item)

            self.assertTrue(result["success"])
            self.assertEqual("legacy.jpg", item.primary_image_path)


if __name__ == "__main__":
    unittest.main()
