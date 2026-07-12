import os
import tempfile
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from coin_collection import PhotoRole
from coin_collection_gui import CoinCollectionGUI
from photo_inbox import PhotoInboxConfig, PhotoInboxManager, PhotoSetState


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyText:
    def __init__(self, value=""):
        self.value = value

    def get(self, start, end):
        return self.value

    def delete(self, start, end):
        self.value = ""


class FixedClock:
    def __init__(self):
        self.current = datetime(2026, 7, 12, 10, 0, 0)

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)


class DummyApp:
    def __init__(self, succeeds=True):
        self.current_image_path = None
        self.last_added_item_id = ""
        self.succeeds = succeeds
        self.add_count = 0

    def add_to_collection(self, country, denomination, year, grade, notes, use_detection, photos=None):
        self.add_count += 1
        if not self.succeeds:
            return False
        self.last_added_item_id = "coin-created-1"
        return True


def make_gui(app=None):
    gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
    gui.app = app or DummyApp()
    gui.country_var = DummyVar("Canada")
    gui.denomination_var = DummyVar("Cent")
    gui.year_var = DummyVar("1920")
    gui.grade_var = DummyVar("VF-20")
    gui.notes_text = DummyText("notes")
    gui.current_item_photos = []
    gui.selected_photo_index = None
    gui.pending_inbox_manager = None
    gui.pending_inbox_photo_set_id = ""
    gui.pending_inbox_refresh_callback = None
    gui.pending_inbox_completion_done = False
    gui.detection_result = None
    gui.refresh_photo_list = lambda: None
    gui.display_selected_photo = lambda: None
    gui.refresh_collection_list = lambda: None
    gui.refresh_entry_suggestions = lambda: None
    return gui


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
    path = os.path.join(manager.config.inbox_folder, name)
    with open(path, "wb") as handle:
        handle.write(b"photo")
    timestamp = (manager.now_fn() - timedelta(minutes=5)).timestamp()
    os.utime(path, (timestamp, timestamp))
    return os.path.abspath(path)


class Phase2B2PhotoInboxCreateTests(unittest.TestCase):
    def test_create_new_disabled_with_no_selection(self):
        self.assertFalse(CoinCollectionGUI.can_create_new_from_inbox([], ""))

    def test_selected_pending_photo_set_enables_create_new(self):
        rows = [{"id": "set-1"}]
        self.assertTrue(CoinCollectionGUI.can_create_new_from_inbox(rows, "set-1"))

    def test_all_photo_set_images_preload_in_deterministic_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            front = write_photo(manager, "coin_front.jpg")
            back = write_photo(manager, "coin_back.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id
            gui = make_gui()

            loaded, skipped = gui.load_photo_set_into_entry_form(manager, photo_set_id)

            self.assertTrue(loaded)
            self.assertEqual([], skipped)
            self.assertEqual([back, front], [photo.path for photo in gui.current_item_photos])

    def test_default_roles_and_primary_are_deterministic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "coin_front.jpg")
            write_photo(manager, "coin_back.jpg")
            write_photo(manager, "coin_detail.jpg")
            manager.scan()
            gui = make_gui()

            gui.load_photo_set_into_entry_form(manager, manager.get_pending_sets()[0].id)

            self.assertEqual(
                [PhotoRole.FRONT, PhotoRole.BACK, PhotoRole.OTHER],
                [photo.role for photo in gui.current_item_photos],
            )
            self.assertEqual([True, False, False], [photo.is_primary for photo in gui.current_item_photos])
            self.assertEqual(gui.current_item_photos[0].path, gui.app.current_image_path)

    def test_manual_role_edits_are_preserved_before_save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "coin_front.jpg")
            manager.scan()
            gui = make_gui()
            gui.load_photo_set_into_entry_form(manager, manager.get_pending_sets()[0].id)

            edited = gui.update_photo_role_at_index(gui.current_item_photos, 0, PhotoRole.CERT_LABEL)

            self.assertEqual(PhotoRole.CERT_LABEL, edited[0].role)

    def test_cancel_clear_form_leaves_photo_set_pending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "coin_front.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id
            gui = make_gui()
            gui.load_photo_set_into_entry_form(manager, photo_set_id)

            gui.clear_form()

            self.assertEqual(PhotoSetState.NEW, manager.state.photo_sets[photo_set_id].state)
            self.assertEqual("", gui.pending_inbox_photo_set_id)

    def test_validation_failure_leaves_set_pending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "coin_front.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id
            app = DummyApp()
            gui = make_gui(app)
            gui.country_var.set("")
            gui.load_photo_set_into_entry_form(manager, photo_set_id)

            with patch("coin_collection_gui.messagebox.showwarning"):
                gui.save_to_collection()

            self.assertEqual(0, app.add_count)
            self.assertEqual(PhotoSetState.NEW, manager.state.photo_sets[photo_set_id].state)

    def test_save_failure_leaves_set_pending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "coin_front.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id
            app = DummyApp(succeeds=False)
            gui = make_gui(app)
            gui.load_photo_set_into_entry_form(manager, photo_set_id)

            with patch("coin_collection_gui.messagebox.showerror"):
                gui.save_to_collection()

            self.assertEqual(1, app.add_count)
            self.assertEqual(PhotoSetState.NEW, manager.state.photo_sets[photo_set_id].state)
            self.assertEqual(photo_set_id, gui.pending_inbox_photo_set_id)

    def test_successful_save_marks_set_attached_and_refreshes_inbox(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "coin_front.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id
            app = DummyApp()
            gui = make_gui(app)
            refresh_calls = []
            gui.load_photo_set_into_entry_form(manager, photo_set_id, refresh_callback=lambda: refresh_calls.append("refresh"))

            with patch("coin_collection_gui.messagebox.showinfo"):
                gui.save_to_collection()

            self.assertEqual(PhotoSetState.ATTACHED, manager.state.photo_sets[photo_set_id].state)
            self.assertEqual("coin-created-1", manager.state.photo_sets[photo_set_id].linked_item_id)
            self.assertEqual(["refresh"], refresh_calls)
            self.assertEqual("", gui.pending_inbox_photo_set_id)

    def test_repeated_completion_callback_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "coin_front.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id
            gui = make_gui()
            refresh_calls = []
            gui.load_photo_set_into_entry_form(manager, photo_set_id, refresh_callback=lambda: refresh_calls.append("refresh"))

            self.assertTrue(gui.complete_pending_inbox_create("coin-created-1"))
            self.assertFalse(gui.complete_pending_inbox_create("coin-created-1"))

            self.assertEqual(PhotoSetState.ATTACHED, manager.state.photo_sets[photo_set_id].state)
            self.assertEqual(["refresh"], refresh_calls)

    def test_no_duplicate_collection_item_from_completion_callback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = make_manager(tmpdir)
            write_photo(manager, "coin_front.jpg")
            manager.scan()
            app = DummyApp()
            gui = make_gui(app)
            gui.load_photo_set_into_entry_form(manager, manager.get_pending_sets()[0].id)

            with patch("coin_collection_gui.messagebox.showinfo"):
                gui.save_to_collection()
            gui.complete_pending_inbox_create("coin-created-1")

            self.assertEqual(1, app.add_count)

    def test_legacy_entry_flow_without_pending_inbox_still_saves(self):
        app = DummyApp()
        gui = make_gui(app)
        gui.current_item_photos, _ = gui.add_photo_paths_to_list([], ["front.jpg"])
        gui.sync_current_image_path_from_photos()

        with patch("coin_collection_gui.messagebox.showinfo"):
            gui.save_to_collection()

        self.assertEqual(1, app.add_count)
        self.assertEqual("", gui.pending_inbox_photo_set_id)


if __name__ == "__main__":
    unittest.main()
