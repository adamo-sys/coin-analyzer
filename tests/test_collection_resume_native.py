"""Opt-in real Tk startup Collection behavior with synthetic memory-only records."""
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import tkinter as tk
from tkinter import ttk

from coin_collection import IdentificationStatus
from coin_collection_gui import CoinCollectionGUI
from tests.test_collector_work_queue_gui import Collection, item


def descendants(parent):
    for child in parent.winfo_children():
        yield child
        yield from descendants(child)


@unittest.skipUnless(os.environ.get("RUN_WORK_QUEUE_NATIVE") == "1", "Opt-in native Tk acceptance")
class CollectionResumeNativeTests(unittest.TestCase):
    def test_startup_collection_and_exact_task_reveal_without_editor(self):
        root = tk.Tk()
        self.addCleanup(root.destroy)
        root.geometry("1000x700")
        errors = []
        root.report_callback_exception = lambda *args: errors.append(args)
        collection = Collection([item("synthetic-unidentified",country="",denomination="",year="",photos=[],
                                      identification_status=IdentificationStatus.UNIDENTIFIED)])
        collection.get_all_items = lambda: list(collection.items)
        collection.search_items = lambda text: list(collection.items)
        collection.get_field_suggestions = lambda *args, **kwargs: []
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = root
        gui.app = SimpleNamespace(collection=collection)
        gui.session_status_var = tk.StringVar(root, value="Synthetic acceptance")
        gui.photo_inbox_notification_var = tk.StringVar(root, value="")
        gui.photo_inbox_indicator_var = tk.StringVar(root, value="Photo Inbox")
        gui.entry_photos = []
        gui.open_edit_item_window = Mock()
        with patch("coin_collection_gui.CoinCollectionApp", side_effect=AssertionError("Live startup forbidden")):
            gui.create_widgets()
            gui.refresh_collection_list()
        root.update()
        self.assertTrue(gui.collection_tree.winfo_ismapped())
        self.assertIn("1 collection record",gui.collection_resume_state_var.get())
        row = gui.collection_tree.get_children()[0]
        self.assertEqual(gui.collection_tree.item(row,"values")[1:3],("Unidentified coin","Unidentified"))
        original = gui._collection_resume_rows[row].reference
        gui.collection_tree.selection_set(row)
        gui.collection_tree.focus(row)
        gui.collection_tree.event_generate("<<TreeviewSelect>>")
        root.update()
        self.assertIn("Maintenance task: Confirm identity",gui.collection_task_var.get())
        gui.show_collection_task_button.invoke()
        root.update()
        queue = gui._work_queue_window
        self.assertTrue(queue.window.winfo_ismapped())
        selected = queue._selected_task()
        self.assertEqual(selected.title,"Confirm identity")
        self.assertIs(queue._task_references[selected.task_id],original)
        gui.open_edit_item_window.assert_not_called()
        self.assertIs(root.focus_get(),queue.tree)
        # Real resized widgets must remain mapped and retain an expandable table.
        for geometry in ("1000x700","900x650"):
            root.geometry(geometry)
            root.update()
            self.assertTrue(gui.show_collection_task_button.winfo_ismapped())
            for widget in (gui.show_collection_task_button,gui.collection_tree):
                x=widget.winfo_rootx()-root.winfo_rootx();y=widget.winfo_rooty()-root.winfo_rooty()
                self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0)
                self.assertLessEqual(x+widget.winfo_width(),root.winfo_width())
                self.assertLessEqual(y+widget.winfo_height(),root.winfo_height())
            self.assertTrue(gui.collection_tree.bbox(row))
            self.assertGreater(gui.collection_tree.winfo_height(),40)
        self.assertFalse(errors)
