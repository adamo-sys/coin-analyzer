"""Synthetic first-coin lifecycle through application services and real Tk callbacks.

No live GUI constructor, recognition provider, private fixture, or default storage
is used. The Tk case skips when a display is unavailable; the service case always
runs. Native file selection and packaged application startup are not exercised.
"""

import tempfile
import tkinter as tk
import unittest
from decimal import Decimal
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from PIL import Image

from coin_collection import (
    CoinCollection,
    CoinCollectionApp,
    CollectionLoadState,
    IdentificationStatus,
    ItemPhoto,
    ItemType,
    PhotoRole,
)
from coin_collection_gui import CoinCollectionGUI
from collection_item_reference import CollectionItemReference


class FirstCoinWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.storage = self.directory / "new-collection" / "collection.json"
        self.front = self.directory / "synthetic-front.png"
        self.back = self.directory / "synthetic-back.png"
        self.second = self.directory / "synthetic-second.png"
        for path, color in ((self.front, "red"), (self.back, "blue"), (self.second, "green")):
            Image.new("RGB", (32, 24), color).save(path)
        self.source_bytes = {path: path.read_bytes() for path in (self.front, self.back, self.second)}
        self.enterContext(patch(
            "coin_collection.CoinCollectionApp._get_recognition_orchestrator",
            side_effect=AssertionError("Manual entry must not initialize recognition"),
        ))
        self.enterContext(patch("socket.socket", side_effect=AssertionError("Network forbidden")))

    def open_app(self):
        return CoinCollectionApp(collection=CoinCollection(str(self.storage)))

    def assert_first_record(self, app, item_id, notes="Synthetic collector entry"):
        item = app.collection.get_item(item_id)
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(
            (item.country, item.denomination, item.year, item.grade, item.notes),
            ("Canada", "25 cents", "1968", "VF-20", notes),
        )
        self.assertEqual(item.item_type, ItemType.COIN)
        self.assertEqual(item.identification_status, IdentificationStatus.IDENTIFIED)
        self.assertFalse(item.auto_detected)
        self.assertEqual(item.detection_confidence, 0.0)
        self.assertEqual(item.image_path, str(self.front))
        self.assertEqual(
            [(p.path, p.role, p.is_primary, p.display_order) for p in item.photos],
            [(str(self.front), PhotoRole.FRONT, True, 0),
             (str(self.back), PhotoRole.BACK, False, 1)],
        )
        self.assertTrue(item.date_added)
        for path, original in self.source_bytes.items():
            self.assertEqual(path.read_bytes(), original)
        return item

    def test_manual_first_save_reopen_edit_and_second_record_remain_independent(self):
        self.assertFalse(self.storage.exists())
        app = self.open_app()
        self.assertEqual(app.collection.load_state, CollectionLoadState.MISSING)
        self.assertEqual(app.collection.items, [])
        self.assertTrue(app.upload_image(str(self.front)))
        self.assertFalse(self.storage.exists(), "Selecting an image must not save a record")
        self.assertTrue(app.add_to_collection(
            "Canada", "25 cents", "1968", "VF-20", "Synthetic collector entry",
            photos=[ItemPhoto(str(self.front), PhotoRole.FRONT, True, "Obverse"),
                    ItemPhoto(str(self.back), PhotoRole.BACK, False, "Reverse", 1)],
            acquisition_date="2026-01-02", purchase_price=Decimal("3.25"),
            purchase_source="Synthetic fixture",
        ))
        self.assertTrue(self.storage.is_file())
        first_id = app.last_added_item_id
        self.assertTrue(first_id.strip())
        self.assertEqual(first_id, first_id.strip())
        del app

        app = self.open_app()
        self.assertEqual(app.collection.load_state, CollectionLoadState.LOADED)
        first = self.assert_first_record(app, first_id)
        self.assertEqual([p.notes for p in first.photos], ["Obverse", "Reverse"])
        self.assertEqual(
            (first.acquisition_date, first.purchase_price, first.purchase_source),
            ("2026-01-02", Decimal("3.25"), "Synthetic fixture"),
        )
        expected_after_edit = first.to_dict()
        expected_after_edit["notes"] = "Edited after reopening"
        result = app.update_collection_item(
            first_id, {"notes": "Edited after reopening"},
            expected_reference=CollectionItemReference.capture(app.collection, first),
        )
        self.assertTrue(result.success, result.error)
        del first, app

        app = self.open_app()
        first = self.assert_first_record(app, first_id, "Edited after reopening")
        self.assertEqual(first.to_dict(), expected_after_edit)
        first_snapshot = expected_after_edit
        self.assertTrue(app.upload_image(str(self.second)))
        self.assertTrue(app.add_to_collection(
            "France", "1 franc", "1970", "F-12", "Independent second coin",
            photos=[ItemPhoto(str(self.second), PhotoRole.FRONT, True)],
        ))
        second_id = app.last_added_item_id
        self.assertTrue(second_id.strip())
        self.assertNotEqual(first_id, second_id)
        del first, app

        app = self.open_app()
        self.assertEqual({item.id for item in app.collection.items}, {first_id, second_id})
        self.assertEqual(len(app.collection.items), 2)
        first = self.assert_first_record(app, first_id, "Edited after reopening")
        self.assertEqual(first.to_dict(), first_snapshot)
        second = app.collection.get_item(second_id)
        assert second is not None
        self.assertEqual(
            (second.country, second.denomination, second.year, second.grade, second.notes),
            ("France", "1 franc", "1970", "F-12", "Independent second coin"),
        )
        self.assertEqual(second.image_path, str(self.second))
        self.assertEqual([p.path for p in second.photos], [str(self.second)])
        self.assertTrue(app.update_collection_item(
            second_id, {"grade": "VF-20"},
            expected_reference=CollectionItemReference.capture(app.collection, second),
        ).success)
        del first, second, app
        app = self.open_app()
        first = self.assert_first_record(app, first_id, "Edited after reopening")
        self.assertEqual(first.to_dict(), first_snapshot)
        second = app.collection.get_item(second_id)
        assert second is not None
        self.assertEqual(second.grade, "VF-20")

    @staticmethod
    def widgets(parent):
        for child in parent.winfo_children():
            yield child
            yield from FirstCoinWorkflowTests.widgets(child)

    def button(self, parent, text):
        return next(widget for widget in self.widgets(parent)
                    if isinstance(widget, ttk.Button) and widget.cget("text") == text)

    @staticmethod
    def close_root(root):
        try:
            root.destroy()
        except tk.TclError:
            pass  # The lifecycle test may already have closed this root.

    def open_gui(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        root.withdraw()
        self.addCleanup(self.close_root, root)
        errors = []
        root.report_callback_exception = lambda *args: errors.append(args)
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = root
        gui.app = self.open_app()
        gui.session_status_var = tk.StringVar(root, value="Synthetic acceptance")
        gui.photo_inbox_notification_var = tk.StringVar(root, value="")
        gui.photo_inbox_indicator_var = tk.StringVar(root, value="Photo Inbox")
        gui.current_item_photos = []
        gui.selected_photo_index = None
        gui.pending_inbox_manager = None
        gui.detection_result = None
        gui._observed_source_revision = gui.app.image_source_revision
        gui.create_widgets()
        gui.refresh_collection_list()
        return gui, errors

    def test_real_tk_manual_callbacks_save_retrieve_edit_and_add_second_coin(self):
        self.enterContext(patch("coin_collection_gui.messagebox.showinfo"))
        for name in ("showerror", "showwarning"):
            self.enterContext(patch(
                f"coin_collection_gui.messagebox.{name}",
                side_effect=AssertionError("Unexpected workflow error or warning"),
            ))
        gui, errors = self.open_gui()
        self.assertFalse(self.storage.exists())
        with patch("coin_collection_gui.filedialog.askopenfilenames",
                   return_value=(str(self.front), str(self.back))):
            self.button(gui.root, "Add Photos").invoke()
        self.assertFalse(self.storage.exists())
        self.assertIsNotNone(gui.current_photo, "Real image preview should render")
        for name, value in (("country", "Canada"), ("denomination", "25 cents"),
                            ("year", "1968"), ("grade", "VF-20")):
            getattr(gui, name + "_var").set(value)
        gui.notes_text.insert("1.0", "Synthetic collector entry")
        self.button(gui.root, "Save to Collection").invoke()
        self.assertFalse(errors, errors)
        self.assertTrue(self.storage.is_file())
        first_id = gui.app.last_added_item_id
        self.assert_first_record(gui.app, first_id)
        self.assertEqual(gui.country_var.get(), "")
        self.assertEqual(gui.current_item_photos, [])
        self.assertEqual(len(gui.collection_tree.get_children()), 1)
        gui.root.destroy()

        gui, errors = self.open_gui()
        first = self.assert_first_record(gui.app, first_id)
        expected_after_edit = first.to_dict()
        expected_after_edit["notes"] = "Edited after reopening"
        row = gui.collection_tree.get_children()[0]
        self.assertEqual(gui.collection_tree.item(row, "values")[0], first_id)
        gui.collection_tree.selection_set(row)
        self.button(gui.root, "Edit Item").invoke()
        dialog = next(w for w in gui.root.winfo_children()
                      if isinstance(w, tk.Toplevel) and w.title() == "Edit Item")
        dialog.withdraw()
        notes = next(w for w in self.widgets(dialog)
                     if isinstance(w, tk.Text) and str(w.cget("state")) == "normal")
        notes.delete("1.0", tk.END)
        notes.insert("1.0", "Edited after reopening")
        self.button(dialog, "Save").invoke()
        self.assertFalse(errors, errors)
        self.assertFalse(dialog.winfo_exists())
        self.assert_first_record(gui.app, first_id, "Edited after reopening")
        gui.root.destroy()

        gui, errors = self.open_gui()
        first = self.assert_first_record(gui.app, first_id, "Edited after reopening")
        self.assertEqual(first.to_dict(), expected_after_edit)
        snapshot = expected_after_edit
        with patch("coin_collection_gui.filedialog.askopenfilenames",
                   return_value=(str(self.second),)):
            self.button(gui.root, "Add Photos").invoke()
        gui.country_var.set("France")
        gui.denomination_var.set("1 franc")
        gui.year_var.set("1970")
        gui.notes_text.insert("1.0", "Independent second coin")
        self.button(gui.root, "Save to Collection").invoke()
        self.assertFalse(errors, errors)
        second_id = gui.app.last_added_item_id
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(len(gui.collection_tree.get_children()), 2)
        gui.root.destroy()

        reopened = self.open_app()
        self.assertEqual(len(reopened.collection.items), 2)
        first = self.assert_first_record(reopened, first_id, "Edited after reopening")
        self.assertEqual(first.to_dict(), snapshot)
        second = reopened.collection.get_item(second_id)
        assert second is not None
        self.assertEqual((second.country, second.year, second.image_path),
                         ("France", "1970", str(self.second)))


if __name__ == "__main__":
    unittest.main()
