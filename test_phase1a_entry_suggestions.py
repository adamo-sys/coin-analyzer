"""Tests for v8.7 Phase 1A editable collection-entry suggestions."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from coin_collection import CoinCollection
from coin_collection_gui import CoinCollectionGUI, GRADE_SUGGESTIONS
from test_backend import make_coin_item


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyText:
    def __init__(self, value="notes"):
        self.value = value

    def delete(self, start, end):
        self.value = ""


class DummyCombo(dict):
    pass


def make_gui(collection):
    gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
    gui.app = SimpleNamespace(collection=collection)
    gui.country_var = DummyVar()
    gui.denomination_var = DummyVar()
    gui.year_var = DummyVar()
    gui.grade_var = DummyVar()
    gui.notes_text = DummyText()
    gui.country_combo = DummyCombo()
    gui.denomination_combo = DummyCombo()
    gui.year_combo = DummyCombo()
    gui.grade_combo = DummyCombo()
    return gui


class TestPhase1AEntrySuggestions(unittest.TestCase):
    def make_collection(self):
        collection = CoinCollection(storage_path="")
        collection.items = [
            make_coin_item("can_cent_1920", country="Canada", denomination="1 cent", year="1920", grade="VF-20"),
            make_coin_item("can_cent_1921", country="Canada", denomination="1 cent", year="1921", grade="EF-40"),
            make_coin_item("nf_20c_1900", country="Newfoundland", denomination="20 cents", year="1900", grade="VG-8"),
            make_coin_item("token", country="Local Token", denomination="Trade token", year="Undated", grade="Custom label"),
        ]
        return collection

    def test_existing_records_populate_country_denomination_and_year_suggestions(self):
        collection = self.make_collection()

        self.assertIn("Canada", collection.get_field_suggestions("country"))
        self.assertIn("1 cent", collection.get_field_suggestions("denomination"))
        self.assertIn("1920", collection.get_field_suggestions("year"))

    def test_manual_custom_values_are_not_required_to_be_in_suggestions(self):
        gui = make_gui(self.make_collection())

        gui.country_var.set("Unlisted Colony")
        gui.denomination_var.set("Presentation medal")
        gui.year_var.set("No date")
        gui.grade_var.set("Collector note grade")

        self.assertEqual(gui.country_var.get(), "Unlisted Colony")
        self.assertEqual(gui.denomination_var.get(), "Presentation medal")
        self.assertEqual(gui.year_var.get(), "No date")
        self.assertEqual(gui.grade_var.get(), "Collector note grade")

    def test_country_updates_denomination_suggestions(self):
        gui = make_gui(self.make_collection())

        gui.country_var.set("Canada")
        gui.on_country_changed()

        denominations = list(gui.denomination_combo["values"])
        self.assertIn("1 cent", denominations)
        self.assertNotIn("20 cents", denominations)

    def test_year_suggestions_filter_by_country_and_denomination(self):
        gui = make_gui(self.make_collection())

        gui.country_var.set("Canada")
        gui.denomination_var.set("1 cent")

        self.assertEqual(gui.get_entry_suggestions("year"), ["1920", "1921"])

    def test_grade_list_available_and_editable(self):
        gui = make_gui(self.make_collection())

        self.assertIn("VF-20", gui.get_entry_suggestions("grade"))
        gui.grade_var.set("AU details - cleaned")
        self.assertEqual(gui.grade_var.get(), "AU details - cleaned")
        self.assertEqual(GRADE_SUGGESTIONS[0], "")

    def test_clear_form_resets_all_entry_fields(self):
        gui = make_gui(self.make_collection())
        gui.country_var.set("Canada")
        gui.denomination_var.set("1 cent")
        gui.year_var.set("1920")
        gui.grade_var.set("VF-20")

        gui.clear_form()

        self.assertEqual(gui.country_var.get(), "")
        self.assertEqual(gui.denomination_var.get(), "")
        self.assertEqual(gui.year_var.get(), "")
        self.assertEqual(gui.grade_var.get(), "")
        self.assertEqual(gui.notes_text.value, "")

    def test_detection_results_populate_combobox_stringvars(self):
        gui = make_gui(self.make_collection())
        gui.detection_result = {
            "success": True,
            "country": "Canada",
            "denomination": "1 cent",
            "year": "1921",
        }

        with patch("coin_collection_gui.messagebox.showwarning"):
            gui.use_detection_results()

        self.assertEqual(gui.country_var.get(), "Canada")
        self.assertEqual(gui.denomination_var.get(), "1 cent")
        self.assertEqual(gui.year_var.get(), "1921")

    def test_on_autocomplete_updates_combobox_values(self):
        gui = make_gui(self.make_collection())

        gui.on_autocomplete("country", "new")

        self.assertEqual(list(gui.country_combo["values"]), ["Newfoundland"])


if __name__ == "__main__":
    unittest.main()
