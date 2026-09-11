"""Collector-owned type/design round trips; no recognition or provider calls."""
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch

from coin_collection import CoinCollection, CoinCollectionApp, CoinItem
from coin_collection_gui import CoinCollectionGUI
from collection_item_reference import CollectionItemReference
from collector_work_queue import derive_work_queue
from capture_import.desktop_visual_identity_review import (
    ConfirmedVisualIdentity, create_visual_identity_proposal,
)
from capture_import.reviewed_coin_collection_entry import persist_reviewed_coin
from tests.test_desktop_visual_identity_review import _report


class TypeDesignPersistenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "collection.json"
        self.collection = CoinCollection(str(self.path))

    def item(self):
        return CoinItem("one", "", "Canada", "25 cents", "1967", "", "notes", "2026-09-11",
                        title="catalog title", reference="KM1", numista_n="123",
                        comments="comments", type_design="Collector design")

    def test_review_correction_persists_without_inference_or_proposal_mutation(self):
        proposal = create_visual_identity_proposal(_report())
        original = proposal.candidate.type_design
        draft = ConfirmedVisualIdentity("Canada", "25 cents", "1967", "  Collector design  ").to_reviewed_coin_draft(proposal)
        self.assertEqual(draft.type_design, "Collector design")
        self.assertNotIn("type_design", dict(draft.unmapped_fields))
        persist_reviewed_coin(collection=self.collection, draft=draft)
        saved = CoinCollection(str(self.path)).items[0]
        self.assertEqual(saved.type_design, "Collector design")
        self.assertEqual(proposal.candidate.type_design, original)
        self.assertEqual((saved.notes, saved.title, saved.reference, saved.numista_n), ("", "", "", ""))

    def test_json_legacy_and_catalog_semantics(self):
        item = self.item()
        row = item.to_dict()
        self.assertEqual(CoinItem.from_dict(row).type_design, "Collector design")
        del row["type_design"]
        restored = CoinItem.from_dict(row)
        self.assertEqual(restored.type_design, "")
        self.assertEqual((restored.notes, restored.title, restored.reference, restored.numista_n, restored.comments),
                         ("notes", "catalog title", "KM1", "123", "comments"))
        self.assertEqual(restored.identification_status, item.identification_status)

    def test_csv_round_trip_and_legacy(self):
        self.assertTrue(self.collection.add_item(self.item()))
        csv_path = self.path.with_suffix(".csv")
        self.assertTrue(self.collection.export_to_csv(str(csv_path)))
        imported = CoinCollection(str(self.path.with_name("imported.json")))
        self.assertEqual(imported.import_from_csv(str(csv_path))[0], 1)
        self.assertEqual(CoinCollection(imported.storage_path).items[0].type_design, "Collector design")
        csv_path.write_text("country,denomination,year,notes\nCanada,5 cents,1940,legacy note\n", encoding="utf-8")
        self.assertEqual(imported.import_from_csv(str(csv_path))[0], 1)
        self.assertEqual(imported.items[-1].type_design, "")
        self.assertEqual(imported.items[-1].notes, "legacy note")

    def test_unrelated_edit_and_clear_preserve_status_queue_and_catalog(self):
        item = self.item()
        self.assertTrue(self.collection.add_item(item))
        app = CoinCollectionApp(collection=self.collection)
        tasks = derive_work_queue(self.collection).tasks
        for updates, expected in (({"grade": "VF"}, "Collector design"), ({"type_design": ""}, "")):
            current = self.collection.items[0]
            result = app.update_collection_item(current.id, updates,
                expected_reference=CollectionItemReference.capture(self.collection, current))
            self.assertTrue(result.success, result.error)
            saved = CoinCollection(str(self.path)).items[0]
            self.assertEqual(saved.type_design, expected)
            self.assertEqual(saved.identification_status, item.identification_status)
            self.assertEqual((saved.notes, saved.title, saved.reference, saved.numista_n, saved.comments),
                             ("notes", "catalog title", "KM1", "123", "comments"))
            self.assertEqual(derive_work_queue(self.collection).tasks, tasks)

    def test_native_editor_modifies_and_clears_persisted_value(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        self.assertTrue(self.collection.add_item(self.item()))
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = root
        gui.app = CoinCollectionApp(collection=self.collection)
        gui.refresh_collection_list = Mock()
        for value in ("Edited design", ""):
            with patch("coin_collection_gui.messagebox.showinfo"), patch("socket.socket", side_effect=AssertionError("network forbidden")):
                gui.open_edit_item_window(self.collection.items[0])
                root.update()
                dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
                form = dialog.winfo_children()[0]
                label = next(w for w in form.winfo_children() if isinstance(w, ttk.Label) and w.cget("text") == "Type / design:")
                row = label.grid_info()["row"]
                entry = next(w for w in form.grid_slaves(row=row, column=1) if isinstance(w, ttk.Combobox))
                self.assertEqual(entry.get(), self.collection.items[0].type_design)
                entry.set(value)
                buttons = [w for frame in form.winfo_children() for w in frame.winfo_children()
                           if isinstance(w, ttk.Button) and w.cget("text") == "Save"]
                self.assertEqual(len(buttons), 1)
                buttons[0].invoke()
                saved = CoinCollection(str(self.path)).items[0]
                self.assertEqual(saved.type_design, value)
                self.assertIn("Type / design: " + (value or "\u2014"), gui.item_details_text(saved))


if __name__ == "__main__":
    unittest.main()
