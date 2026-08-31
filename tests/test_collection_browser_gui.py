"""Headless tests for the Unit 6C mixed-collection Tk browser integration."""

from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from coin_collection import (
    CaptureImportMediaProvenance,
    CoinItem,
    CollectionLoadState,
    Disposition,
    IdentificationStatus,
    ItemPhoto,
    ItemType,
)
from coin_collection_gui import CoinCollectionGUI
from collection_browser import CollectionBrowserSort


class Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Combo:
    def __init__(self):
        self.values = ()

    def configure(self, **values):
        self.values = values.get("values", self.values)


class Tree:
    def __init__(self):
        self.rows = {}
        self.selected = ()

    def get_children(self):
        return tuple(self.rows)

    def delete(self, item):
        self.rows.pop(item, None)
        if item in self.selected:
            self.selected = ()

    def insert(self, _parent, _where, iid, **values):
        self.rows[iid] = values
        return iid

    def selection(self):
        return self.selected

    def selection_remove(self, item):
        if item in self.selected:
            self.selected = ()


class Collection:
    def __init__(self, items, state=CollectionLoadState.VALID):
        self.items = items
        self.load_state = state
        self.last_save_error = ""
        self.delete_calls = []

    def get_all_items(self):
        return self.items

    def get_item(self, item_id):
        return next((item for item in self.items if item.id == item_id), None)

    def delete_item(self, item_id):
        self.delete_calls.append(item_id)
        if self.load_state is not CollectionLoadState.VALID:
            return False
        before = len(self.items)
        self.items[:] = [item for item in self.items if item.id != item_id]
        return len(self.items) != before


def item(item_id, **updates):
    values = {
        "id": item_id,
        "image_path": "",
        "country": "",
        "denomination": "",
        "year": "",
        "grade": "",
        "notes": "",
        "date_added": "2026-08-30",
        "item_type": ItemType.COIN,
        "disposition": Disposition.UNDECIDED,
        "identification_status": IdentificationStatus.UNIDENTIFIED,
        "updated_at": None,
        "_initialize_updated_at": False,
    }
    values.update(updates)
    return CoinItem(**values)


def mixed_items():
    return [
        item(
            "canadian",
            country="Canada",
            issuer="Royal Canadian Mint",
            denomination="25 cents",
            year="1967",
            grade="MS-63",
            notes="Bobcat",
            disposition=Disposition.KEEP,
            identification_status=IdentificationStatus.IDENTIFIED,
            updated_at="2026-08-30T10:00:00Z",
            purchase_price=Decimal("12.50"),
            purchase_currency="CAD",
        ),
        item(
            "world",
            country="Japan",
            issuer="Empire of Japan",
            denomination="10 sen",
            disposition=Disposition.UPGRADE,
            identification_status=IdentificationStatus.PARTIAL,
        ),
        item(
            "banknote",
            item_type=ItemType.BANKNOTE,
            issuer="The Chartered Bank",
            denomination="Ten Dollars",
            year="Series 1962",
            disposition=Disposition.SELL_TRADE,
            identification_status=IdentificationStatus.IDENTIFIED,
            updated_at="2026-08-30T11:00:00Z",
        ),
        item("mystery", notes="Unidentified bronze object"),
    ]


def gui_for(items=None, state=CollectionLoadState.VALID):
    gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
    gui.app = SimpleNamespace(collection=Collection(list(items or []), state))
    gui.collection_tree = Tree()
    gui.search_var = Var()
    gui.browser_type_var = Var("All")
    gui.browser_disposition_var = Var("All")
    gui.browser_identification_var = Var("All")
    gui.browser_issuer_country_var = Var("All")
    gui.browser_sort_var = Var("Collection order")
    gui.browser_result_count_var = Var("0 items")
    gui.browser_issuer_country_combo = Combo()
    gui._browser_row_item_ids = {}
    gui._browser_thumbnail_refs = {}
    gui._browser_fallback_thumbnail = None
    gui.browser_thumbnail = Mock(side_effect=lambda path: object())
    gui.open_item_details_window = Mock()
    gui.open_edit_item_window = Mock()
    return gui


class BrowserRefreshTests(unittest.TestCase):
    def test_mixed_sparse_rows_result_count_and_stable_mapping(self):
        gui = gui_for(mixed_items())

        gui.refresh_collection_list()

        self.assertEqual(gui.browser_result_count_var.get(), "4 items")
        self.assertEqual(tuple(gui._browser_row_item_ids.values()), ("canadian", "world", "banknote", "mystery"))
        values = [row["values"] for row in gui.collection_tree.rows.values()]
        self.assertEqual([row[0] for row in values], ["COIN", "COIN", "BANKNOTE", "COIN"])
        self.assertEqual(values[1][7], "PARTIAL")
        self.assertEqual(values[3][1:5], ("—", "—", "—", "—"))

    def test_search_and_all_filters_delegate_through_projection(self):
        gui = gui_for(mixed_items())
        gui.search_var.set("chartered")
        gui.browser_type_var.set("Banknote")
        gui.browser_disposition_var.set("Sell/Trade")
        gui.browser_identification_var.set("Identified")
        gui.browser_issuer_country_var.set("The Chartered Bank")

        gui.refresh_collection_list()

        self.assertEqual(tuple(gui._browser_row_item_ids.values()), ("banknote",))

    def test_each_filter_control(self):
        cases = (
            ("browser_type_var", "Coin", ("canadian", "world", "mystery")),
            ("browser_type_var", "Banknote", ("banknote",)),
            ("browser_disposition_var", "Keep", ("canadian",)),
            ("browser_disposition_var", "Upgrade", ("world",)),
            ("browser_disposition_var", "Sell/Trade", ("banknote",)),
            ("browser_disposition_var", "Undecided", ("mystery",)),
            ("browser_identification_var", "Identified", ("canadian", "banknote")),
            ("browser_identification_var", "Partial", ("world",)),
            ("browser_identification_var", "Unidentified", ("mystery",)),
            ("browser_issuer_country_var", "Japan", ("world",)),
        )
        for attribute, value, expected in cases:
            with self.subTest(attribute=attribute, value=value):
                gui = gui_for(mixed_items())
                getattr(gui, attribute).set(value)
                gui.refresh_collection_list()
                self.assertEqual(tuple(gui._browser_row_item_ids.values()), expected)

    def test_every_sort_selection_and_reset(self):
        expected = {
            "Collection order": ("canadian", "world", "banknote", "mystery"),
            "Recently updated": ("banknote", "canadian", "world", "mystery"),
            "Issuer/Country A-Z": ("world", "canadian", "banknote", "mystery"),
            "Denomination A-Z": ("world", "canadian", "banknote", "mystery"),
            "Date/Year/Series A-Z": ("canadian", "banknote", "world", "mystery"),
        }
        gui = gui_for(mixed_items())
        for selection, order in expected.items():
            with self.subTest(selection=selection):
                gui.browser_sort_var.set(selection)
                gui.refresh_collection_list()
                self.assertEqual(tuple(gui._browser_row_item_ids.values()), order)
        gui.search_var.set("coin")
        gui.browser_type_var.set("Banknote")
        gui.browser_disposition_var.set("Keep")
        gui.browser_identification_var.set("Partial")
        gui.browser_issuer_country_var.set("Japan")
        gui.reset_collection_browser()
        self.assertEqual(gui.search_var.get(), "")
        self.assertEqual(
            (gui.browser_type_var.get(), gui.browser_disposition_var.get(), gui.browser_identification_var.get(), gui.browser_issuer_country_var.get(), gui.browser_sort_var.get()),
            ("All", "All", "All", "All", "Collection order"),
        )

    def test_dynamic_options_refresh_after_collection_change(self):
        gui = gui_for(mixed_items()[:1])
        gui.refresh_collection_list()
        self.assertIn("Canada", gui.browser_issuer_country_combo.values)

        gui.app.collection.items[:] = [mixed_items()[2]]
        gui.browser_issuer_country_var.set("Canada")
        gui.refresh_collection_list()

        self.assertNotIn("Canada", gui.browser_issuer_country_combo.values)
        self.assertEqual(gui.browser_issuer_country_var.get(), "All")

    def test_refresh_rebuilds_thumbnail_references_and_does_not_mutate(self):
        items = mixed_items()
        before = deepcopy(items)
        gui = gui_for(items)
        gui.refresh_collection_list()
        first_refs = gui._browser_thumbnail_refs
        gui.refresh_collection_list()

        self.assertIsNot(gui._browser_thumbnail_refs, first_refs)
        self.assertFalse(any(value in gui._browser_thumbnail_refs.values() for value in first_refs.values()))
        self.assertEqual(items, before)
        self.assertEqual([value.id for value in items], ["canadian", "world", "banknote", "mystery"])

    def test_invalid_collection_is_not_projected_or_actionable(self):
        gui = gui_for(mixed_items(), CollectionLoadState.INVALID_OR_UNSUPPORTED)
        gui.collection_tree.selected = ("browser-row-0",)
        gui._browser_row_item_ids = {"browser-row-0": "canadian"}

        gui.refresh_collection_list()

        self.assertEqual(gui.collection_tree.rows, {})
        self.assertEqual(gui.browser_result_count_var.get(), "Collection unavailable")


class ThumbnailTests(unittest.TestCase):
    def test_missing_and_corrupt_paths_share_neutral_fallback(self):
        gui = gui_for()
        gui.browser_thumbnail = CoinCollectionGUI.browser_thumbnail.__get__(gui)
        with TemporaryDirectory() as directory, patch("coin_collection_gui.ImageTk.PhotoImage", side_effect=lambda image: object()):
            corrupt = Path(directory, "bad.jpg")
            corrupt.write_bytes(b"not an image")
            missing = gui.browser_thumbnail(str(Path(directory, "missing.jpg")))
            unreadable = gui.browser_thumbnail(str(corrupt))
        self.assertIs(missing, unreadable)

    def test_valid_ordinary_and_capture_paths_create_in_memory_thumbnails(self):
        with TemporaryDirectory() as directory:
            path = Path(directory, "photo.png")
            Image.new("RGB", (80, 80), "red").save(path)
            original = path.read_bytes()
            gui = gui_for()
            gui.browser_thumbnail = CoinCollectionGUI.browser_thumbnail.__get__(gui)
            created = []
            with patch("coin_collection_gui.ImageTk.PhotoImage", side_effect=lambda image: created.append(image.copy()) or object()):
                ordinary = gui.browser_thumbnail(str(path))
                capture = gui.browser_thumbnail(str(path))
            self.assertIsNotNone(ordinary)
            self.assertIsNotNone(capture)
            self.assertEqual(len(created), 2)
            self.assertEqual(path.read_bytes(), original)

    def test_capture_import_row_uses_same_read_only_path_boundary(self):
        provenance = CaptureImportMediaProvenance(
            "1.0", "12345678-1234-4234-8234-123456789abc", "PROCESSED_SNAPSHOT",
            "a" * 64, "87654321-4321-4321-8321-cba987654321", "front", "b" * 64, "NORMALIZED",
        )
        value = item("capture", photos=[ItemPhoto("managed/capture/front.jpg", is_primary=True, capture_import_media=provenance)])
        gui = gui_for([value])
        gui.refresh_collection_list()
        gui.browser_thumbnail.assert_called_once_with("managed/capture/front.jpg")
        self.assertIs(value.photos[0].capture_import_media, provenance)


class StableActionTests(unittest.TestCase):
    def test_details_text_does_not_normalize_authoritative_photo_metadata(self):
        value = item(
            "details",
            photos=[
                ItemPhoto("back.jpg", is_primary=False, display_order=4),
                ItemPhoto("front.jpg", is_primary=True, display_order=2),
            ],
        )
        before = deepcopy(value)

        text = CoinCollectionGUI.item_details_text(value)

        self.assertIn("Image: front.jpg", text)
        self.assertEqual(value, before)

    def test_details_and_edit_resolve_stable_id_against_current_collection(self):
        gui = gui_for(mixed_items())
        gui.refresh_collection_list()
        gui.collection_tree.selected = ("browser-row-1",)
        gui.app.collection.items.reverse()

        gui.view_item_details()
        gui.edit_item()

        self.assertEqual(gui.open_item_details_window.call_args.args[0].id, "world")
        self.assertEqual(gui.open_edit_item_window.call_args.args[0].id, "world")

    def test_delete_resolves_stable_id_and_refreshes(self):
        gui = gui_for(mixed_items())
        gui.refresh_collection_list()
        gui.collection_tree.selected = ("browser-row-2",)
        with patch("coin_collection_gui.messagebox.askyesno", return_value=True), patch("coin_collection_gui.messagebox.showinfo"):
            gui.delete_item()
        self.assertEqual(gui.app.collection.delete_calls, ["banknote"])
        self.assertNotIn("banknote", gui._browser_row_item_ids.values())

    def test_stale_selection_never_targets_another_item(self):
        gui = gui_for(mixed_items())
        gui.refresh_collection_list()
        gui.collection_tree.selected = ("browser-row-1",)
        gui.app.collection.items[:] = [value for value in gui.app.collection.items if value.id != "world"]
        with patch("coin_collection_gui.messagebox.showwarning") as warning:
            gui.edit_item()
        gui.open_edit_item_window.assert_not_called()
        warning.assert_called_once()
        self.assertNotIn("world", gui._browser_row_item_ids.values())

    def test_stale_selection_after_delete_fails_safely(self):
        gui = gui_for(mixed_items())
        gui.refresh_collection_list()
        gui.collection_tree.selected = ("browser-row-0",)
        gui.app.collection.items.pop(0)
        with patch("coin_collection_gui.messagebox.showwarning"):
            gui.view_item_details()
        gui.open_item_details_window.assert_not_called()

    def test_filter_refresh_clears_stale_tree_selection(self):
        gui = gui_for(mixed_items())
        gui.refresh_collection_list()
        gui.collection_tree.selected = ("browser-row-1",)
        gui.browser_type_var.set("Banknote")
        gui.refresh_collection_list()
        with patch("coin_collection_gui.messagebox.showwarning"):
            gui.edit_item()
        gui.open_edit_item_window.assert_not_called()

    def test_delete_aborts_if_restore_replaces_active_collection_during_confirmation(self):
        gui = gui_for(mixed_items())
        gui.refresh_collection_list()
        gui.collection_tree.selected = ("browser-row-0",)
        restored = Collection([item("restored", item_type=ItemType.BANKNOTE)])

        def replace_collection(*_args):
            gui.app.collection = restored
            return True

        with patch("coin_collection_gui.messagebox.askyesno", side_effect=replace_collection), patch("coin_collection_gui.messagebox.showwarning"):
            gui.delete_item()
        self.assertEqual(restored.delete_calls, [])
        self.assertEqual(tuple(gui._browser_row_item_ids.values()), ("restored",))

    def test_invalid_collection_cannot_delete(self):
        gui = gui_for(mixed_items(), CollectionLoadState.INVALID_OR_UNSUPPORTED)
        gui.collection_tree.selected = ("stale",)
        gui._browser_row_item_ids = {"stale": "canadian"}
        with patch("coin_collection_gui.messagebox.showerror"):
            gui.delete_item()
        self.assertEqual(gui.app.collection.delete_calls, [])

    def test_fresh_collection_refresh_replaces_restore_boundary_mapping(self):
        gui = gui_for([item("old", country="Canada")])
        gui.refresh_collection_list()
        old_map = gui._browser_row_item_ids
        gui.app.collection = Collection([item("restored", item_type=ItemType.BANKNOTE)])
        gui.refresh_collection_list()
        self.assertIsNot(gui._browser_row_item_ids, old_map)
        self.assertEqual(tuple(gui._browser_row_item_ids.values()), ("restored",))


if __name__ == "__main__":
    unittest.main()
