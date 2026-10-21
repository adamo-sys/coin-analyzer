"""Collection actions must retain the exact displayed synthetic record authority."""

import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from typing import Any
from unittest.mock import Mock, patch

from coin_collection import CoinCollection, CoinCollectionApp, CoinItem
from coin_collection_gui import CoinCollectionGUI
from tests import test_first_coin_workflow as first_coin_helpers
from tests.test_collector_work_queue_gui import Button, Tree, Var


class SelectionTree(Tree):
    def item(self, row_id):
        return self.rows[row_id]


class CollectionSelectionAuthorityTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "synthetic.json"
        self.collection = CoinCollection(str(self.path))
        self.original = self.item("001", "Original record")
        self.other = self.item("other", "Independent record")
        self.assertTrue(self.collection.add_item(self.original))
        self.assertTrue(self.collection.add_item(self.other))
        self.gui: Any = CoinCollectionGUI.__new__(CoinCollectionGUI)
        self.gui.app = CoinCollectionApp(collection=self.collection)
        self.gui.collection_tree = SelectionTree()
        self.gui.search_var = Var()
        self.gui.collection_resume_state_var = Var()
        self.gui.collection_task_var = Var()
        self.gui.show_collection_task_button = Button()
        self.gui.open_item_details_window = Mock()
        self.gui.open_edit_item_window = Mock()
        for name in ("showwarning", "showerror", "showinfo"):
            self.enterContext(patch("coin_collection_gui.messagebox." + name))
        self.confirm = self.enterContext(patch("coin_collection_gui.messagebox.askyesno", return_value=True))
        self.select_original()
        self.seed_bytes = self.path.read_bytes()

    @staticmethod
    def item(item_id, notes):
        return CoinItem(id=item_id, image_path="", country="Canada", denomination="5 cents",
                        year="1967", grade="VF", notes=notes, date_added="2026-10-20")

    def select_original(self):
        self.gui.refresh_collection_list()
        row_id = next(row_id for row_id, row in self.gui._collection_resume_rows.items()
                      if row.reference.item_id == "001")
        self.gui.collection_tree.selected = (row_id,)

    def test_current_details_and_edit_use_exact_record_without_writes(self):
        before = self.path.read_bytes()
        for action, opener in ((self.gui.view_item_details, self.gui.open_item_details_window),
                               (self.gui.edit_item, self.gui.open_edit_item_window)):
            action()
            opener.assert_called_once_with(self.original)
        self.assertEqual(self.path.read_bytes(), before)

    def test_stale_rows_cannot_open_or_delete_replacement_records(self):
        for transition in ("reload", "replace", "collection", "duplicate", "failed"):
            for action_name in ("view_item_details", "edit_item", "delete_item"):
                with self.subTest(transition=transition, action=action_name):
                    self.path.write_bytes(self.seed_bytes)
                    self.collection = CoinCollection(str(self.path))
                    self.gui.app.collection = self.collection
                    self.select_original()
                    if transition == "reload":
                        self.collection.load_collection()
                    elif transition == "replace":
                        self.collection.items[0] = self.item("001", "Replacement record")
                    elif transition == "collection":
                        self.gui.app.collection = CoinCollection(str(self.path))
                    elif transition == "duplicate":
                        self.collection.items.append(self.item("001", "Ambiguous record"))
                    else:
                        from coin_collection import CollectionLoadState
                        self.collection.load_state = CollectionLoadState.FAILED
                    before = self.path.read_bytes()
                    memory = copy.deepcopy([vars(item) for item in self.gui.app.collection.items])
                    self.gui.open_item_details_window.reset_mock()
                    self.gui.open_edit_item_window.reset_mock()
                    self.confirm.reset_mock()
                    getattr(self.gui, action_name)()
                    self.gui.open_item_details_window.assert_not_called()
                    self.gui.open_edit_item_window.assert_not_called()
                    self.confirm.assert_not_called()
                    self.assertEqual(self.path.read_bytes(), before)
                    self.assertEqual([vars(item) for item in self.gui.app.collection.items], memory)

    def test_unmapped_row_cannot_supply_mutation_authority(self):
        self.gui._collection_resume_rows = {}
        before = self.path.read_bytes()
        self.gui.edit_item()
        self.gui.open_edit_item_window.assert_not_called()
        self.gui.delete_item()
        self.confirm.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)

    def test_delete_revalidates_after_confirmation_reloads_collection(self):
        before = self.path.read_bytes()

        def confirm(*args, **kwargs):
            self.collection.load_collection()
            return True

        self.confirm.side_effect = confirm
        self.gui.delete_item()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual([item.id for item in self.collection.items], ["001", "other"])

    def test_explicit_current_delete_preserves_other_record(self):
        other_before = self.other.to_dict()
        self.gui.delete_item()
        reopened = CoinCollection(str(self.path))
        self.assertEqual([item.id for item in reopened.items], ["other"])
        self.assertEqual(reopened.items[0].to_dict(), other_before)

    def test_cancelled_delete_does_not_write(self):
        before = self.path.read_bytes()
        self.confirm.return_value = False
        self.gui.delete_item()
        self.assertEqual(self.path.read_bytes(), before)


class NativeCollectionWorkflowTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.storage = Path(directory) / "synthetic.json"
        self.collection = CoinCollection(str(self.storage))
        for item_id, notes in (("001", "Original record"), ("other", "Independent record")):
            self.assertTrue(self.collection.add_item(CollectionSelectionAuthorityTests.item(item_id, notes)))
        self.enterContext(patch("socket.socket", side_effect=AssertionError("Network forbidden")))
        self.enterContext(patch("coin_collection_gui.messagebox.showinfo"))
        self.errors = self.enterContext(patch("coin_collection_gui.messagebox.showerror"))
        self.warnings = self.enterContext(patch("coin_collection_gui.messagebox.showwarning"))
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Native Tk unavailable: {error}")
        self.addCleanup(root.destroy)
        root.withdraw()
        self.callback_errors = []
        root.report_callback_exception = lambda *args: self.callback_errors.append(args)
        self.gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        self.gui.root = root
        self.gui.app = CoinCollectionApp(collection=self.collection)
        self.gui.collection_tree = ttk.Treeview(root, columns=("id", "label", "status", "date"))
        self.gui.search_var = tk.StringVar(root)
        self.gui.collection_resume_state_var = tk.StringVar(root)
        self.gui.collection_task_var = tk.StringVar(root)
        self.gui.show_collection_task_button = ttk.Button(root)
        self.gui.refresh_collection_list()
        self.select("001")

    def select(self, item_id):
        row_id = next(row_id for row_id, row in self.gui._collection_resume_rows.items()
                      if row.reference.item_id == item_id)
        self.gui.collection_tree.selection_set(row_id)
        self.gui.on_collection_select()

    def editor(self):
        self.gui.edit_item()
        self.gui.root.update()
        return next(widget for widget in self.gui.root.winfo_children()
                    if isinstance(widget, tk.Toplevel) and widget.title() == "Edit Item")

    @staticmethod
    def widgets(parent):
        return first_coin_helpers.FirstCoinWorkflowTests.widgets(parent)

    def button(self, parent, text):
        return next(widget for widget in self.widgets(parent)
                    if isinstance(widget, ttk.Button) and widget.cget("text") == text)

    def test_numeric_id_opens_exact_details_and_editor(self):
        self.gui.view_item_details()
        self.gui.root.update()
        details_windows = [widget for widget in self.gui.root.winfo_children()
                           if isinstance(widget, tk.Toplevel) and widget.title() == "Item Details"]
        self.assertEqual(len(details_windows), 1, "The exact selected record must open details")
        details = details_windows[0]
        text = next(widget for widget in self.widgets(details) if isinstance(widget, tk.Text))
        self.assertIn("Original record", text.get("1.0", tk.END))
        details.destroy()
        dialog = self.editor()
        self.assertTrue(dialog.winfo_exists())
        self.assertFalse(self.callback_errors, self.callback_errors)
        self.errors.assert_not_called()
        self.warnings.assert_not_called()

    def test_draft_survives_selection_and_clear_search_then_saves_exact_record(self):
        before = self.storage.read_bytes()
        other = self.collection.get_item("other")
        assert other is not None
        other_before = other.to_dict()
        dialog = self.editor()
        combos = [widget for widget in self.widgets(dialog) if isinstance(widget, ttk.Combobox)]
        for widget, value in zip(combos[:5], ("France", "1 franc", "1970", "XF", "Synthetic design")):
            widget.set(value)
        notes = next(widget for widget in self.widgets(dialog)
                     if isinstance(widget, tk.Text) and str(widget.cget("state")) == "normal")
        notes.delete("1.0", tk.END)
        notes.insert("1.0", "Unsaved draft")
        self.select("other")
        self.gui.search_var.set("missing")
        self.gui.on_search(None)
        self.gui.clear_search()
        self.assertEqual(self.storage.read_bytes(), before)
        self.assertEqual([widget.get() for widget in combos[:5]],
                         ["France", "1 franc", "1970", "XF", "Synthetic design"])
        self.assertEqual(notes.get("1.0", tk.END).strip(), "Unsaved draft")
        self.button(dialog, "Save").invoke()
        self.gui.root.update()
        self.errors.assert_not_called()
        self.assertFalse(self.callback_errors, self.callback_errors)
        self.assertFalse(dialog.winfo_exists())
        reopened = CoinCollection(str(self.storage))
        saved = reopened.get_item("001")
        assert saved is not None
        self.assertEqual((saved.country, saved.denomination, saved.year, saved.grade, saved.type_design),
                         ("France", "1 franc", "1970", "XF", "Synthetic design"))
        self.assertTrue(saved.notes.startswith("Unsaved draft\n\nSaved identity correction history v1:"))
        other = reopened.get_item("other")
        assert other is not None
        self.assertEqual(other.to_dict(), other_before)

    def test_invalid_acquisition_retains_editor_and_does_not_write(self):
        before = self.storage.read_bytes()
        memory = copy.deepcopy([vars(item) for item in self.collection.items])
        dialog = self.editor()
        frame = next(widget for widget in self.widgets(dialog)
                     if isinstance(widget, ttk.LabelFrame) and widget.cget("text") == "Acquisition Details")
        price = next(widget for widget in frame.grid_slaves(row=1, column=1)
                     if isinstance(widget, ttk.Entry))
        price.insert(0, "-1")
        self.button(dialog, "Save").invoke()
        self.gui.root.update()
        self.warnings.assert_called_once()
        self.assertTrue(dialog.winfo_exists())
        self.assertEqual(price.get(), "-1")
        self.assertEqual(self.storage.read_bytes(), before)
        self.assertEqual([vars(item) for item in self.collection.items], memory)
        self.assertFalse(self.callback_errors, self.callback_errors)

    def test_editor_after_reload_refuses_save_and_retains_draft(self):
        dialog = self.editor()
        country = next(widget for widget in self.widgets(dialog) if isinstance(widget, ttk.Combobox))
        country.set("Draft country")
        before = self.storage.read_bytes()
        self.collection.load_collection()
        self.button(dialog, "Save").invoke()
        self.gui.root.update()
        self.errors.assert_called_once()
        self.assertTrue(dialog.winfo_exists())
        self.assertEqual(country.get(), "Draft country")
        self.assertEqual(self.storage.read_bytes(), before)
        self.assertFalse(self.callback_errors, self.callback_errors)


if __name__ == "__main__":
    unittest.main()
