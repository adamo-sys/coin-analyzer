"""Focused tests for the pure mixed-collection browser projection."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from coin_collection import (
    CaptureImportMediaProvenance,
    CoinCollection,
    CoinItem,
    Disposition,
    IdentificationStatus,
    ItemPhoto,
    ItemType,
    PhotoRole,
)
from collection_browser import (
    ABSENCE_MARKER,
    CollectionBrowserCriteria,
    CollectionBrowserSort,
    issuer_country_filter_options,
    project_collection,
)


T1 = "2026-08-30T10:00:00.000001Z"
T2 = "2026-08-30T11:00:00.000002Z"


def make_item(item_id: str, **updates) -> CoinItem:
    values = {
        "id": item_id,
        "image_path": "",
        "country": "",
        "denomination": "",
        "year": "",
        "grade": "",
        "notes": "",
        "date_added": "2026-08-30",
        "issuer": "",
        "title": "",
        "reference": "",
        "numista_n": "",
        "item_type": ItemType.COIN,
        "disposition": Disposition.UNDECIDED,
        "identification_status": IdentificationStatus.UNIDENTIFIED,
        "updated_at": None,
        "_initialize_updated_at": False,
    }
    values.update(updates)
    return CoinItem(**values)


def mixed_items() -> list[CoinItem]:
    return [
        make_item(
            "coin-ca",
            country="Canada",
            issuer="Royal Canadian Mint",
            denomination="25 cents",
            year="1967",
            title="Centennial quarter",
            reference="KM# 68",
            numista_n="N# 1234",
            notes="Bobcat reverse",
            grade="MS-63",
            disposition=Disposition.KEEP,
            identification_status=IdentificationStatus.IDENTIFIED,
            updated_at=T1,
            purchase_price=Decimal("12.50"),
            purchase_currency="CAD",
        ),
        make_item(
            "coin-jp",
            country="Japan",
            issuer="Empire of Japan",
            denomination="10 sen",
            notes="Partially attributed world coin",
            disposition=Disposition.UPGRADE,
            identification_status=IdentificationStatus.PARTIAL,
        ),
        make_item(
            "note-hk",
            item_type=ItemType.BANKNOTE,
            country="Hong Kong",
            issuer="The Chartered Bank",
            denomination="Ten Dollars",
            year="Series 1962",
            title="Chartered Bank ten-dollar note",
            reference="P-70",
            notes="Manual banknote attribution",
            grade="VF",
            disposition=Disposition.SELL_TRADE,
            identification_status=IdentificationStatus.IDENTIFIED,
            updated_at=T2,
        ),
        make_item(
            "mystery",
            image_path="managed_media/mystery/front.jpg",
            notes="Unidentified bronze-coloured object",
            identification_status=IdentificationStatus.UNIDENTIFIED,
        ),
    ]


class ProjectionShapeTests(unittest.TestCase):
    def test_mixed_projection_is_immutable_and_preserves_stable_ids(self):
        items = mixed_items()
        rows = project_collection(items)

        self.assertEqual([row.item_id for row in rows], [item.id for item in items])
        self.assertEqual([row.item_type for row in rows], ["COIN", "COIN", "BANKNOTE", "COIN"])
        self.assertNotIn(CoinItem, {field.type for field in fields(rows[0])})
        self.assertFalse(
            any(
                isinstance(getattr(rows[0], field.name), CoinItem)
                for field in fields(rows[0])
            )
        )
        with self.assertRaises(FrozenInstanceError):
            rows[0].item_id = "different"

    def test_sparse_partial_and_unidentified_rows_use_presentation_marker(self):
        rows = project_collection(mixed_items())

        self.assertEqual(rows[1].date_series, ABSENCE_MARKER)
        self.assertEqual(rows[1].identification_status, "PARTIAL")
        self.assertEqual(rows[3].issuer_country, ABSENCE_MARKER)
        self.assertEqual(rows[3].denomination, ABSENCE_MARKER)
        self.assertEqual(rows[3].identification_status, "UNIDENTIFIED")

    def test_absence_marker_is_not_factual_or_searchable(self):
        items = mixed_items()
        before = deepcopy(items)

        self.assertEqual(project_collection(items, CollectionBrowserCriteria(search_text=ABSENCE_MARKER)), ())
        self.assertEqual(items, before)

    def test_issuer_country_display_rule_is_truthful_and_deterministic(self):
        rows = project_collection(mixed_items())

        self.assertEqual(rows[0].issuer_country, "Royal Canadian Mint / Canada")
        self.assertEqual(rows[3].issuer_country, ABSENCE_MARKER)

    def test_truthful_status_is_displayed_without_recomputation(self):
        inconsistent = make_item(
            "explicit-status",
            country="Canada",
            denomination="1 dollar",
            year="2020",
            identification_status=IdentificationStatus.PARTIAL,
        )

        row = project_collection([inconsistent])[0]

        self.assertEqual(row.identification_status, "PARTIAL")
        self.assertIs(inconsistent.identification_status, IdentificationStatus.PARTIAL)


class SearchAndFilterTests(unittest.TestCase):
    def setUp(self):
        self.items = mixed_items()

    def ids(self, **criteria):
        rows = project_collection(self.items, CollectionBrowserCriteria(**criteria))
        return [row.item_id for row in rows]

    def test_searches_every_frozen_factual_field(self):
        examples = {
            "coin-ca": "coin-ca",
            "canada": "coin-ca",
            "empire": "coin-jp",
            "25 cents": "coin-ca",
            "1962": "note-hk",
            "centennial": "coin-ca",
            "p-70": "note-hk",
            "bronze-coloured": "mystery",
            "ms-63": "coin-ca",
            "n# 1234": "coin-ca",
        }
        for query, expected in examples.items():
            with self.subTest(query=query):
                self.assertEqual(self.ids(search_text=query), [expected])

    def test_search_is_case_insensitive_and_blank_is_unrestricted(self):
        self.assertEqual(self.ids(search_text="cHaRtErEd"), ["note-hk"])
        self.assertEqual(self.ids(search_text="   "), [item.id for item in self.items])

    def test_item_type_filters(self):
        self.assertEqual(self.ids(item_type="BANKNOTE"), ["note-hk"])
        self.assertEqual(self.ids(item_type=ItemType.COIN), ["coin-ca", "coin-jp", "mystery"])
        self.assertEqual(self.ids(item_type="ALL"), [item.id for item in self.items])

    def test_each_disposition_filter(self):
        expected = {
            Disposition.KEEP: ["coin-ca"],
            Disposition.UPGRADE: ["coin-jp"],
            Disposition.SELL_TRADE: ["note-hk"],
            Disposition.UNDECIDED: ["mystery"],
        }
        for disposition, item_ids in expected.items():
            with self.subTest(disposition=disposition):
                self.assertEqual(self.ids(disposition=disposition), item_ids)

    def test_each_identification_filter(self):
        expected = {
            IdentificationStatus.IDENTIFIED: ["coin-ca", "note-hk"],
            IdentificationStatus.PARTIAL: ["coin-jp"],
            IdentificationStatus.UNIDENTIFIED: ["mystery"],
        }
        for status, item_ids in expected.items():
            with self.subTest(status=status):
                self.assertEqual(self.ids(identification_status=status), item_ids)

    def test_issuer_and_country_exact_filters_are_case_insensitive(self):
        self.assertEqual(self.ids(issuer_or_country="ROYAL CANADIAN MINT"), ["coin-ca"])
        self.assertEqual(self.ids(issuer_or_country="hong kong"), ["note-hk"])
        self.assertEqual(self.ids(issuer_or_country="ALL"), [item.id for item in self.items])

    def test_filters_are_conjunctive_and_combine_with_search(self):
        self.assertEqual(
            self.ids(item_type="COIN", disposition="KEEP", issuer_or_country="Canada"),
            ["coin-ca"],
        )
        self.assertEqual(
            self.ids(search_text="manual", item_type="BANKNOTE", disposition="SELL_TRADE"),
            ["note-hk"],
        )
        self.assertEqual(self.ids(search_text="Canada", item_type="BANKNOTE"), [])

    def test_invalid_criteria_fail_explicitly(self):
        invalid = (
            {"item_type": "TOKEN"},
            {"disposition": "SELL"},
            {"identification_status": "UNKNOWN"},
            {"sort_order": "PRICE"},
            {"search_text": 12},
            {"issuer_or_country": 12},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                CollectionBrowserCriteria(**values)
        with self.assertRaises(ValueError):
            project_collection(self.items, object())


class SortingTests(unittest.TestCase):
    def setUp(self):
        self.items = mixed_items()

    def sorted_ids(self, sort_order):
        return [
            row.item_id
            for row in project_collection(
                self.items, CollectionBrowserCriteria(sort_order=sort_order)
            )
        ]

    def test_collection_order_is_preserved(self):
        self.assertEqual(
            self.sorted_ids(CollectionBrowserSort.COLLECTION_ORDER),
            ["coin-ca", "coin-jp", "note-hk", "mystery"],
        )

    def test_recently_updated_is_newest_first_with_invalid_and_missing_last(self):
        self.items[1].updated_at = T1
        self.items[3].updated_at = "not-a-timestamp"

        self.assertEqual(
            self.sorted_ids(CollectionBrowserSort.RECENTLY_UPDATED),
            ["note-hk", "coin-ca", "coin-jp", "mystery"],
        )

    def test_text_sorts_are_case_insensitive_sparse_and_stable(self):
        expected = {
            CollectionBrowserSort.ISSUER_COUNTRY: ["coin-jp", "coin-ca", "note-hk", "mystery"],
            CollectionBrowserSort.DENOMINATION: ["coin-jp", "coin-ca", "note-hk", "mystery"],
            CollectionBrowserSort.DATE_SERIES: ["coin-ca", "note-hk", "coin-jp", "mystery"],
        }
        for sort_order, item_ids in expected.items():
            with self.subTest(sort_order=sort_order):
                self.assertEqual(self.sorted_ids(sort_order), item_ids)

    def test_every_sort_leaves_authoritative_order_and_items_unchanged(self):
        original_order = list(self.items)
        original_values = deepcopy(self.items)

        for sort_order in CollectionBrowserSort:
            project_collection(self.items, CollectionBrowserCriteria(sort_order=sort_order))

        self.assertEqual(self.items, original_order)
        self.assertEqual(self.items, original_values)


class AcquisitionAndPhotoTests(unittest.TestCase):
    def test_acquisition_display_preserves_price_currency_date_and_source(self):
        item = make_item(
            "acquired",
            purchase_price=Decimal("125.50"),
            purchase_currency="HKD",
            acquisition_date="2026-08-29",
            purchase_source="Collector show",
        )

        self.assertEqual(
            project_collection([item])[0].acquisition,
            "HKD 125.50 · 2026-08-29 · Collector show",
        )

    def test_malformed_runtime_acquisition_value_degrades_safely(self):
        item = make_item("bad-price")
        item.purchase_price = object()

        self.assertEqual(project_collection([item])[0].acquisition, ABSENCE_MARKER)

    def test_ordinary_primary_photo_path_is_projected_without_mutation(self):
        item = make_item(
            "ordinary-photo",
            photos=[
                ItemPhoto("managed/back.jpg", PhotoRole.BACK, False, "", 1),
                ItemPhoto("managed/front.jpg", PhotoRole.FRONT, True, "", 0),
            ],
        )
        before = deepcopy(item)

        self.assertEqual(project_collection([item])[0].thumbnail_path, "managed/front.jpg")
        self.assertEqual(item, before)

    def test_capture_import_primary_photo_path_is_projected_without_conversion(self):
        provenance = CaptureImportMediaProvenance(
            schema_version="1.0",
            import_id="12345678-1234-4234-8234-123456789abc",
            source_kind="PROCESSED_SNAPSHOT",
            package_sha256="a" * 64,
            processed_snapshot_id="87654321-4321-4321-8321-cba987654321",
            artifact_key="front",
            artifact_sha256="b" * 64,
            variant="NORMALIZED",
        )
        photo = ItemPhoto(
            "imports/managed/front.jpg",
            PhotoRole.FRONT,
            True,
            "",
            0,
            provenance,
        )
        item = make_item("capture-photo", photos=[photo])

        self.assertEqual(project_collection([item])[0].thumbnail_path, photo.path)
        self.assertIs(item.photos[0].capture_import_media, provenance)

    def test_no_photo_exposes_empty_path(self):
        self.assertEqual(project_collection([make_item("no-photo")])[0].thumbnail_path, "")

    def test_projection_does_not_read_or_write_media(self):
        with TemporaryDirectory() as directory:
            photo_path = Path(directory, "photo.jpg")
            photo_path.write_bytes(b"not actually decoded")
            item = make_item(
                "media-observation",
                photos=[ItemPhoto(str(photo_path), is_primary=True)],
            )
            before_bytes = photo_path.read_bytes()
            before_stat = photo_path.stat()

            project_collection([item])

            self.assertEqual(photo_path.read_bytes(), before_bytes)
            self.assertEqual(photo_path.stat().st_mtime_ns, before_stat.st_mtime_ns)


class IntegrationBoundaryTests(unittest.TestCase):
    def test_filter_options_are_deterministic_and_deduplicate_case_variants(self):
        items = mixed_items()
        items.append(make_item("case-variant", country="canada", issuer="Bank of Japan"))

        self.assertEqual(
            issuer_country_filter_options(items),
            (
                "Bank of Japan",
                "Canada",
                "Empire of Japan",
                "Hong Kong",
                "Japan",
                "Royal Canadian Mint",
                "The Chartered Bank",
            ),
        )

    def test_projection_never_calls_collection_save_or_changes_persisted_bytes(self):
        with TemporaryDirectory() as directory:
            path = Path(directory, "collection.json")
            payload = [
                {
                    "id": "legacy",
                    "image_path": "legacy.jpg",
                    "country": "Canada",
                    "denomination": "5 cents",
                    "year": "1937",
                    "grade": "F",
                    "notes": "Legacy record",
                    "date_added": "2020-01-01",
                }
            ]
            path.write_text(json.dumps(payload), encoding="utf-8")
            collection = CoinCollection(str(path))
            before = path.read_bytes()

            with patch.object(collection, "save_collection") as save:
                rows = project_collection(collection.get_all_items())

            self.assertEqual(path.read_bytes(), before)
            save.assert_not_called()
            self.assertEqual(rows[0].item_id, "legacy")
            self.assertEqual(rows[0].item_type, "COIN")
            self.assertEqual(rows[0].disposition, "UNDECIDED")
            self.assertEqual(rows[0].identification_status, "IDENTIFIED")


if __name__ == "__main__":
    unittest.main()
