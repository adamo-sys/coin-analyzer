"""Synthetic regression coverage for the shared collection substring search."""

import tempfile
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from coin_collection import CoinCollection, CoinItem, IdentificationStatus, ItemPhoto
from coin_collection_gui import CoinCollectionGUI


def make_item(item_id="record-1", **fields):
    values = {
        "id": item_id, "image_path": "", "country": "", "denomination": "", "year": "",
        "grade": "", "notes": "", "date_added": "2026-10-05",
    }
    values.update(fields)
    return CoinItem(**values)


class CollectionSearchTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.storage_path = Path(self.tempdir.name) / "collection.json"
        self.collection = CoinCollection(str(self.storage_path))

    def test_new_fields_match_literal_substrings_case_insensitively(self):
        cases = (
            ("type_design", "John F. Kennedy portrait", "Kennedy", "kEnNeDy"),
            ("notes", "coin show pickup, weird eagle reverse", "weird eagle", "WeIrD EaGlE"),
            ("purchase_source", "Toronto Coin Shop", "Toronto Coin Shop", "tOrOnTo CoIn ShOp"),
        )
        for field, text, query, mixed_case in cases:
            with self.subTest(field=field):
                target = make_item(**{field: text})
                self.collection.items = [make_item("other"), target]
                for term in (query, mixed_case, f"  {query}\t", query[1:-1]):
                    self.assertEqual([target], self.collection.search_items(term))
                self.assertEqual([], self.collection.search_items("missing-zebra-xyz"))

    def test_all_existing_search_fields_remain_searchable(self):
        for field in ("id", "numista_n", "reference", "title", "country",
                      "denomination", "year", "issuer"):
            with self.subTest(field=field):
                target = make_item(**{field: "Legacy-Canada-Token"})
                self.collection.items = [target]
                self.assertEqual([target], self.collection.search_items("cAnAdA"))

    def test_null_and_blank_new_fields_do_not_become_none_text(self):
        for value in (None, ""):
            for field in ("type_design", "notes", "purchase_source"):
                with self.subTest(field=field, value=value):
                    target = make_item(**{field: value})
                    self.collection.items = [target]
                    self.assertEqual([], self.collection.search_items("None"))
                    self.assertEqual([], self.collection.search_items("missing-zebra-xyz"))

    def test_unidentified_notes_retrieve_without_populating_identity(self):
        target = make_item(notes="coin show pickup, weird eagle reverse")
        self.collection.items = [target]
        before = deepcopy(vars(target))
        self.assertEqual(IdentificationStatus.UNIDENTIFIED, target.identification_status)
        self.assertEqual([target], self.collection.search_items("weird eagle"))
        self.assertEqual(before, vars(target))
        for field in ("country", "denomination", "year", "issuer", "reference", "title"):
            self.assertEqual("", getattr(target, field))

    def test_order_and_full_record_state_are_preserved(self):
        first = make_item("z-record", notes="shared context",
                          photos=[ItemPhoto("synthetic.jpg", notes="photo context")],
                          purchase_price=Decimal("12.34"), purchase_source="Test seller")
        other = make_item("a-record", country="Canada")
        last = make_item("m-record", type_design="shared context")
        self.collection.items = [first, other, last]
        original_list = self.collection.items
        before = deepcopy([vars(item) for item in original_list])
        self.assertEqual([first, last], self.collection.search_items("shared context"))
        self.assertEqual([other], self.collection.search_items("Canada"))
        self.assertIs(original_list, self.collection.items)
        self.assertEqual([first, other, last], self.collection.items)
        self.assertEqual(before, [vars(item) for item in self.collection.items])
        self.assertFalse(self.storage_path.exists())

    def test_empty_and_whitespace_queries_preserve_existing_behavior(self):
        items = [make_item("z-record"), make_item("a-record")]
        self.collection.items = items
        self.assertIs(items, self.collection.search_items(""))
        self.assertEqual(items, self.collection.search_items("  \t"))

    def test_search_remains_literal_without_fuzzy_or_token_matching(self):
        target = make_item(type_design="Kennedy", notes="weird eagle",
                           purchase_source="Toronto Coin Shop")
        self.collection.items = [target]
        for query in ("Kenedy", "eagle weird", "Toronto Shop", "Kennedy|eagle"):
            with self.subTest(query=query):
                self.assertEqual([], self.collection.search_items(query))

    def test_unapproved_saved_text_is_not_newly_searchable(self):
        target = make_item(
            image_path="missing-zebra-xyz.jpg", grade="missing-zebra-xyz",
            comments="missing-zebra-xyz", currency="missing-zebra-xyz",
            photos=[ItemPhoto("missing-zebra-xyz.jpg", notes="missing-zebra-xyz")],
        )
        self.collection.items = [target]
        self.assertEqual([], self.collection.search_items("missing-zebra-xyz"))

    def test_photo_inbox_returns_first_25_in_collection_order_without_mutation(self):
        fields = ("type_design", "notes", "purchase_source")
        items = [
            make_item(f"record-{index:02}", **{fields[index % 3]: "shared context"})
            for index in range(29, -1, -1)
        ]
        self.collection.items = [make_item("nonmatch"), *items]
        before = deepcopy([vars(item) for item in self.collection.items])
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.app = SimpleNamespace(collection=self.collection)
        matches = gui.search_attach_targets("ShArEd CoNtExT")
        self.assertEqual(
            [f"record-{index:02}" for index in range(29, 4, -1)],
            [item.id for item in matches],
        )
        self.assertEqual(30, len(self.collection.search_items("shared context")))
        self.assertEqual(before, [vars(item) for item in self.collection.items])
        self.assertFalse(self.storage_path.exists())

    def test_photo_inbox_search_does_not_supply_an_attachment_selection(self):
        self.collection.items = [make_item(notes="weird eagle")]
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.app = SimpleNamespace(collection=self.collection)
        self.assertEqual(self.collection.items, gui.search_attach_targets("weird eagle"))
        result = gui.attach_photo_set_to_item(object(), "synthetic-set", None)
        self.assertFalse(result["success"])
        self.assertEqual("Select a collection item first.", result["error"])
        self.assertFalse(self.storage_path.exists())


if __name__ == "__main__":
    unittest.main()
