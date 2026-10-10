"""Synthetic native Tk acceptance, including widgets and window lifecycle."""
import copy
import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from tests.test_collection_shelf import Collection, item
from tests import test_collection_shelf_gui as shelf_tests

try:
    from collection_shelf_gui import CollectionShelfWindow
except ImportError:
    CollectionShelfWindow = None


@unittest.skipUnless(os.environ.get("RUN_WORK_QUEUE_NATIVE") == "1", "Opt-in native Tk acceptance")
class NativeShelfTests(unittest.TestCase):
    @staticmethod
    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from NativeShelfTests.descendants(child)

    def button(self, dialog, text):
        return next(widget for widget in self.descendants(dialog)
                    if isinstance(widget, __import__("tkinter.ttk", fromlist=["Button"]).Button)
                    and widget.cget("text") == text)

    def test_shelf_details_edit_save_cancel_failure_and_lifecycle_never_access_photos(self):
        from coin_collection_gui import CoinCollectionGUI
        from tkinter import ttk
        fixture = shelf_tests.MetadataSaveTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = self.root
        gui.app = fixture.app
        # Real metadata refresh after Save, without constructing the whole app.
        gui.collection_tree = ttk.Treeview(self.root, columns=("id", "label", "status", "date"))
        gui.collection_task_var = tk.StringVar(self.root)
        gui.collection_resume_state_var = tk.StringVar(self.root)
        gui.search_var = tk.StringVar(self.root)
        gui.show_collection_task_button = ttk.Button(self.root)
        before = copy.deepcopy(vars(fixture.specimen))
        trap = self.photo_trap
        with patch("coin_collection_gui.messagebox.showerror") as error, \
             patch("coin_collection_gui.messagebox.showinfo") as success:
            shelf = gui.open_collection_shelf()
            self.addCleanup(lambda: shelf.close() if shelf.is_open() else None)
            self.root.update()
            self.assertIs(gui.open_collection_shelf(), shelf)
            shelf.card_buttons[0][0].invoke()
            self.root.update()
            details = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)
                           and w.title() == "Item Details")
            texts = [w.get("1.0", tk.END) for w in self.descendants(details) if isinstance(w, tk.Text)]
            self.assertIn("photo-trap.png", "".join(texts))
            self.assertIn("photo note", "".join(texts))
            self.assertFalse(any(isinstance(w, ttk.Treeview) for w in self.descendants(details)))
            self.button(details, "Close").invoke()

            def open_edit():
                shelf.card_buttons[0][1].invoke()
                self.root.update()
                return next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)
                            and w.title() == "Edit Item")

            edit = open_edit()
            # Photo operations are absent, so there is no enabled event route.
            for label in ("Add Photos", "Remove", "Set Primary", "Move Up", "Move Down", "Zoom"):
                self.assertFalse(any(isinstance(w, ttk.Button) and w.cget("text") == label
                                     for w in self.descendants(edit)))
            notes = next(w for w in self.descendants(edit) if isinstance(w, tk.Text)
                         and str(w.cget("state")) == "normal")
            notes.delete("1.0", tk.END)
            notes.insert("1.0", "saved metadata")
            combos = [w for w in self.descendants(edit) if isinstance(w, ttk.Combobox)]
            combos[3].set("VF")
            with patch("coin_collection.write_json_atomically", side_effect=OSError("synthetic failure")):
                self.button(edit, "Save").invoke()
            self.root.update()
            error.assert_called_once()
            success.assert_not_called()
            self.assertTrue(edit.winfo_exists())
            self.assertEqual(notes.get("1.0", "end-1c"), "saved metadata")
            self.assertEqual(fixture.specimen.notes, before["notes"])
            self.button(edit, "Save").invoke()
            self.root.update()
            success.assert_called_once()
            self.assertFalse(edit.winfo_exists())
            self.assertEqual(fixture.specimen.notes, "saved metadata")
            self.assertEqual(fixture.specimen.grade, "VF")
            self.assertEqual(fixture.specimen.photos, before["photos"])

            edit = open_edit()
            notes = next(w for w in self.descendants(edit) if isinstance(w, tk.Text)
                         and str(w.cget("state")) == "normal")
            notes.insert(tk.END, "cancelled draft")
            self.button(edit, "Cancel").invoke()
            self.assertEqual(fixture.specimen.notes, "saved metadata")
            edit = open_edit()
            fixture.collection.items[:] = [item("a")]
            self.button(edit, "Save").invoke()
            self.root.update()
            self.assertTrue(edit.winfo_exists())
            self.assertEqual(error.call_count, 2)
            self.assertEqual(success.call_count, 1)
            self.button(edit, "Cancel").invoke()
            shelf.refresh()
            shelf.close()
            reopened = gui.open_collection_shelf()
            self.root.update()
            self.assertIsNot(reopened, shelf)
            reopened.close()
        self.assertEqual(trap.calls, [])
        self.assertEqual(self.callback_errors, [])

    def test_keyboard_actions_remain_visible_on_pages_and_resize(self):
        assert CollectionShelfWindow is not None
        collection = Collection([item(f"{n:03}") for n in range(49)])
        window = CollectionShelfWindow(self.root, lambda: collection, lambda value: None, lambda value: None)
        self.addCleanup(window.close)
        for page in (0, 1, 2, 0):
            window.refresh(page=page)
            for geometry in ("940x740", "780x480", "940x740"):
                window.window.geometry(geometry)
                self.root.update()
                first = window.card_buttons[0][0]
                first.focus_force()
                self.root.update()
                expected = [button for pair in window.card_buttons for button in pair]
                for index, button in enumerate(expected):
                    if index:
                        expected[index - 1].event_generate("<Tab>")
                        self.root.update()
                    self.assertEqual(window.window.focus_get(), button)
                    top = button.winfo_rooty() - window.canvas.winfo_rooty()
                    self.assertGreaterEqual(top, 0, (page, geometry, index, "above viewport"))
                    self.assertLessEqual(top + button.winfo_height(), window.canvas.winfo_height(),
                                         (page, geometry, index, "below viewport"))
                for button in reversed(expected[:-1]):
                    focused = window.window.focus_get()
                    assert focused is not None
                    focused.event_generate("<Shift-Tab>")
                    self.root.update()
                    self.assertEqual(window.window.focus_get(), button)
                    top = button.winfo_rooty() - window.canvas.winfo_rooty()
                    self.assertGreaterEqual(top, 0)
                    self.assertLessEqual(top + button.winfo_height(), window.canvas.winfo_height())
                expected[-1].focus_force()
                self.root.update()
                window.window.geometry("780x480")
                self.root.update()
                top = expected[-1].winfo_rooty() - window.canvas.winfo_rooty()
                self.assertGreaterEqual(top, 0)
                self.assertLessEqual(top + expected[-1].winfo_height(), window.canvas.winfo_height())
        self.assertEqual(self.callback_errors, [])

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Native Tk unavailable: {error}")
        self.root.title("Synthetic shelf acceptance")
        self.root.geometry("240x80+20+20")
        self.addCleanup(self.root.destroy)
        self.callback_errors = []
        self.root.report_callback_exception = lambda *args: self.callback_errors.append(args)
        self.photo_trap = self.enterContext(shelf_tests.PhotoAccessTrap())
        self.addCleanup(lambda: self.assertEqual(self.photo_trap.calls, []))

    def test_native_paging_search_thumbnails_actions_and_close(self):
        self.assertIsNotNone(CollectionShelfWindow, "Shelf window missing")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.png"
            Image.new("RGB", (300, 500), "green").save(path)
            collection = Collection([item(f"{n:03}", image_path=str(path), photos=[],
                                          notes="needle" if n == 48 else "") for n in range(49)])
            before = copy.deepcopy([vars(value) for value in collection.items])
            calls = []
            window = CollectionShelfWindow(self.root, lambda: collection,
                                           lambda value: calls.append(("details", value)),
                                           lambda value: calls.append(("edit", value)))
            self.root.update()
            self.assertTrue(window.is_open())
            self.assertEqual(len(window.card_frames), 24)
            self.assertEqual(window.images, [])
            self.assertIn("49", window.summary.get())
            window.next_button.invoke()
            self.root.update()
            self.assertEqual(len(window.card_frames), 24)
            window.next_button.invoke()
            self.root.update()
            self.assertEqual(len(window.card_frames), 1)
            self.assertEqual(str(window.next_button["state"]), "disabled")
            window.query.set("needle")
            window.search()
            self.root.update()
            self.assertEqual(window.page.index, 0)
            self.assertEqual(window.page.total, 1)
            card = window.page.cards[0]
            window.card_buttons[0][0].invoke()
            window.card_buttons[0][1].invoke()
            self.assertEqual(calls, [("details", collection.items[48]), ("edit", collection.items[48])])
            self.assertEqual([vars(value) for value in collection.items], before)
            collection.items[48] = item("048")
            with patch("collection_shelf_gui.messagebox.showwarning") as warning:
                window.open_card(card, "edit")
                self.assertEqual(len(calls), 2)
                warning.assert_called_once()
            window.close()
            self.assertFalse(window.is_open())
            self.assertEqual(window.images, [])
            self.assertEqual(self.callback_errors, [])

    def test_long_record_ids_and_controls_fit_minimum_window(self):
        self.assertIsNotNone(CollectionShelfWindow)
        collection = Collection([item(f"11111111-1111-4111-8111-{n:012}") for n in range(4)])
        window = CollectionShelfWindow(self.root, lambda: collection, lambda value: None, lambda value: None)
        self.addCleanup(window.close)
        window.window.geometry("780x480")
        self.root.update()
        for frame, buttons in zip(window.card_frames, window.card_buttons):
            self.assertLessEqual(frame.winfo_x() + frame.winfo_width(), window.canvas.winfo_width())
            for button in buttons:
                self.assertTrue(button.winfo_ismapped())
                self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                     frame.winfo_rootx() + frame.winfo_width())
        self.assertEqual(self.callback_errors, [])

    def test_main_gui_opens_reuses_and_reopens_shelf(self):
        from coin_collection_gui import CoinCollectionGUI
        from types import SimpleNamespace
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = self.root
        gui.app = SimpleNamespace(collection=Collection([item("a")]))
        gui.capture_import_ready = False
        gui.open_item_details_window = lambda value, **kwargs: None
        gui.open_edit_item_window = lambda value, on_saved=None, **kwargs: None
        self.assertTrue(callable(getattr(gui, "open_collection_shelf", None)), "Shelf entry point missing")
        gui.create_menu_bar()
        menubar = self.root.nametowidget(self.root["menu"])
        home_menu = self.root.nametowidget(menubar.entrycget("Collector Home", "menu"))
        entries = [home_menu.entrycget(index, "label") for index in range(home_menu.index(tk.END) + 1)]
        self.assertIn("Visual Collection Shelf", entries)
        home_menu.invoke(entries.index("Visual Collection Shelf"))
        self.assertTrue(gui._collection_shelf_window.is_open())
        first = gui.open_collection_shelf()
        self.assertIs(gui.open_collection_shelf(), first)
        first.close()
        second = gui.open_collection_shelf()
        self.assertIsNot(second, first)
        second.close()


@unittest.skipUnless(os.environ.get("RUN_WORK_QUEUE_NATIVE") == "1", "Opt-in native Tk acceptance")
class OrdinaryPreviewCompatibilityTests(unittest.TestCase):
    def test_relative_details_edit_and_dialog_local_shelf_isolation(self):
        from coin_collection_gui import CoinCollectionGUI, SavedPhotoPreview
        from coin_collection import CoinCollection, CoinCollectionApp
        from tests.test_collection_shelf_gui import PhotoAccessTrap
        import json
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        errors = []
        root.report_callback_exception = lambda *args: errors.append(args)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "child").mkdir()
            Image.new("RGB", (20, 20), "red").save(base / "synthetic.png")
            storage = base / "collection.json"
            storage.write_text(json.dumps([{"id": "relative", "image_path": "../synthetic.png",
                                          "photos": []}]), encoding="utf-8")
            app = CoinCollectionApp.__new__(CoinCollectionApp)
            app.collection = CoinCollection(str(storage))
            gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
            gui.root, gui.app = root, app
            specimen = app.collection.items[0]
            previous = os.getcwd()
            try:
                os.chdir(base / "child")
                before = copy.deepcopy(vars(specimen))
                with PhotoAccessTrap() as trap:
                    gui.open_item_details_window(specimen, metadata_only=True)
                    gui.open_edit_item_window(specimen, metadata_only=True)
                    root.update()
                self.assertEqual(trap.calls, [])
                # Keep shelf dialogs open while ordinary dialogs decode the same record.
                opened = []
                real_open = Image.open
                def decode(path, *args, **kwargs):
                    opened.append(str(path))
                    return real_open(path, *args, **kwargs)
                with patch("PIL.Image.open", side_effect=decode):
                    gui.open_item_details_window(specimen)
                    gui.open_edit_item_window(specimen)
                    root.update()
                self.assertGreaterEqual(opened.count("../synthetic.png"), 2)
                previews = [w for w in NativeShelfTests.descendants(root)
                            if isinstance(w, SavedPhotoPreview)]
                self.assertEqual(len(previews), 1)
                self.assertEqual(previews[0].preview_status, "")
                self.assertEqual(previews[0].source_image.size, (20, 20))
                self.assertEqual(vars(specimen), before)
                self.assertEqual(errors, [])
            finally:
                for child in root.winfo_children():
                    child.destroy()
                os.chdir(previous)
