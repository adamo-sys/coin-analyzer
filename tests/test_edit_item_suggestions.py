"""Editor-local suggestions through real composition, search, and guarded Save."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from coin_collection import CoinCollection, CoinCollectionApp, CoinItem
from coin_collection_gui import CoinCollectionGUI


class Variable:
    def __init__(self, value=""):
        self.value = value
        self.callbacks = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        for callback in self.callbacks:
            callback("variable", "", "write")

    def trace_add(self, mode, callback):
        self.callbacks.append(callback)
        return str(len(self.callbacks))


class Combo(dict):
    def __init__(self, *args, **options):
        super().__init__(options)
        self.variable = options["textvariable"]
        self.grid = MagicMock()


class Text:
    def __init__(self, *args, **kwargs):
        self.value = ""
        self.grid = MagicMock()
        self.configure = MagicMock()

    def insert(self, index, value):
        self.value += value

    def get(self, *args):
        return self.value


class EditItemSuggestionsTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "synthetic-collection.json"
        self.collection = CoinCollection(str(self.path))
        self.item = self.make_item("saved", "Canada", "5 cents", "1967")
        self.item.title = "Prior identity"
        self.item.notes = "Collector notes"
        self.collection.items = [
            self.item,
            self.make_item("ca-other", "Canada", "1 cent", "1980"),
            self.make_item("ca-year", "Canada", "5 cents", "1968"),
            self.make_item("us-same", "USA", "5 cents", "2001"),
            self.make_item("us-other", "USA", "quarter", "2002"),
        ]
        self.assertTrue(self.collection.save_collection())
        self.gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        self.gui.root = MagicMock()
        self.gui.app = CoinCollectionApp(collection=self.collection)
        self.enterContext(patch.object(self.gui, "country_var", Variable("USA"), create=True))
        self.enterContext(patch.object(self.gui, "denomination_var", Variable("quarter"), create=True))
        self.gui.refresh_collection_list = MagicMock()
        # Acquisition UI is unrelated; retain its real normalization and Save.
        self.enterContext(patch.object(self.gui, "create_acquisition_fields", return_value={"values": dict}))
        self.combos = []
        self.buttons = {}
        self.dialog = MagicMock()

        def combo(*args, **kwargs):
            widget = Combo(*args, **kwargs)
            self.combos.append(widget)
            return widget

        def button(*args, **kwargs):
            widget = MagicMock()
            if "text" in kwargs:
                self.buttons[kwargs["text"]] = kwargs["command"]
            return widget

        for target, replacement in (
            ("tk.StringVar", Variable), ("tk.BooleanVar", Variable),
            ("tk.Toplevel", MagicMock(return_value=self.dialog)), ("tk.Text", Text),
            ("ttk.Frame", MagicMock()), ("ttk.LabelFrame", MagicMock()),
            ("ttk.Label", MagicMock()), ("ttk.Combobox", combo), ("ttk.Button", button),
        ):
            self.enterContext(patch("coin_collection_gui." + target, replacement))
        self.errors = self.enterContext(patch("coin_collection_gui.messagebox.showerror"))
        self.enterContext(patch("coin_collection_gui.messagebox.showinfo"))
        self.enterContext(patch("socket.socket", side_effect=AssertionError("Network forbidden")))
        self.before = copy.deepcopy([vars(item) for item in self.collection.items])
        self.disk_before = self.path.read_bytes()
        self.gui.open_edit_item_window(self.item, metadata_only=True)
        self.country, self.denomination, self.year = self.combos[:3]

    @staticmethod
    def make_item(item_id, country, denomination, year):
        return CoinItem(id=item_id, image_path="", country=country,
                        denomination=denomination, year=year, grade="", notes="",
                        date_added="2026-10-20", photos=[])

    def assert_not_saved(self):
        self.assertEqual([vars(item) for item in self.collection.items], self.before)
        self.assertEqual(self.path.read_bytes(), self.disk_before)
        self.assertEqual(self.gui.country_var.get(), "USA")
        self.assertEqual(self.gui.denomination_var.get(), "quarter")

    def test_initial_lists_use_saved_context_independently_of_main_form(self):
        self.assertEqual(self.country["values"], ["Canada", "USA"])
        self.assertEqual(self.denomination["values"], ["1 cent", "5 cents"])
        self.assertEqual(self.year["values"], ["1967", "1968"])
        self.assertEqual([combo.variable.get() for combo in self.combos[:3]],
                         ["Canada", "5 cents", "1967"])
        self.assert_not_saved()

    def test_country_change_refreshes_dependents_without_replacing_values(self):
        self.country.variable.set("USA")
        self.assertEqual(self.denomination["values"], ["5 cents", "quarter"])
        self.assertEqual(self.year["values"], ["2001"])
        self.assertEqual(self.denomination.variable.get(), "5 cents")
        self.assertEqual(self.year.variable.get(), "1967")
        self.assert_not_saved()

    def test_denomination_change_refreshes_years_using_editor_country(self):
        self.denomination.variable.set("1 cent")
        self.assertEqual(self.year["values"], ["1980"])
        self.assertEqual(self.year.variable.get(), "1967")
        self.assert_not_saved()

    def test_main_form_changes_do_not_change_editor_context(self):
        self.gui.country_var.set("Elsewhere")
        self.gui.denomination_var.set("Other")
        self.denomination.variable.set("1 cent")
        self.assertEqual(self.year["values"], ["1980"])
        self.assertEqual(self.country.variable.get(), "Canada")

    def test_free_text_and_empty_context_preserve_existing_suggestion_semantics(self):
        self.country.variable.set("Custom country")
        self.denomination.variable.set("Custom denomination")
        self.year.variable.set("Custom date")
        self.assertEqual(self.denomination["values"], [])
        self.assertEqual(self.year["values"], [])
        for combo in self.combos[:3]:
            self.assertNotEqual(combo.get("state", "normal"), "readonly")
        self.assertEqual(self.year.variable.get(), "Custom date")
        self.country.variable.set("")
        self.denomination.variable.set("")
        self.assertEqual(self.denomination["values"], ["1 cent", "5 cents", "quarter"])
        self.assertEqual(self.year["values"], ["1967", "1968", "1980", "2001", "2002"])
        self.assertEqual(self.year.variable.get(), "Custom date")
        self.assert_not_saved()

    def test_explicit_save_publishes_custom_values_and_invalidates_old_identity(self):
        self.country.variable.set("Custom country")
        self.denomination.variable.set("Custom denomination")
        self.year.variable.set("Custom date")
        self.assert_not_saved()
        self.buttons["Save"]()
        self.errors.assert_not_called()
        saved = CoinCollection(str(self.path)).get_item("saved")
        assert saved is not None
        self.assertEqual((saved.country, saved.denomination, saved.year),
                         ("Custom country", "Custom denomination", "Custom date"))
        self.assertEqual(saved.title, "")
        self.assertIn("Saved identity correction history v1:", saved.notes)
        self.dialog.destroy.assert_called_once()

    def test_stale_disk_rejects_save_and_retains_draft(self):
        self.country.variable.set("Custom country")
        other = CoinCollection(str(self.path))
        self.assertTrue(other.update_item("saved", {"notes": "Independent edit"}))
        disk = self.path.read_bytes()
        self.buttons["Save"]()
        self.errors.assert_called_once()
        self.assertEqual(self.path.read_bytes(), disk)
        self.assertEqual([vars(item) for item in self.collection.items], self.before)
        self.assertEqual(self.country.variable.get(), "Custom country")
        self.dialog.destroy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
