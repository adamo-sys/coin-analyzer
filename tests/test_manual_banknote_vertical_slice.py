"""Focused non-display tests for the manual banknote product slice."""

from decimal import Decimal
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from coin_collection import (
    CoinCollection,
    CoinCollectionApp,
    Disposition,
    IdentificationStatus,
    ItemPhoto,
    ItemType,
    PhotoRole,
)
from coin_collection_gui import CoinCollectionGUI


T1 = "2026-08-30T14:00:00.000001Z"
T2 = "2026-08-30T14:05:00.000002Z"


def banknote_form(**updates):
    values = {
        "item_type": "BANKNOTE",
        "country": "Hong Kong",
        "issuer": "The Chartered Bank",
        "denomination": "Ten Dollars",
        "year": "1 January 1962 series",
        "title": "Chartered Bank ten-dollar note",
        "reference": "P-70",
        "grade": "VF",
        "notes": "Manual attribution; no recognition used.",
        "disposition": "SELL_TRADE",
        "identification_status": "IDENTIFIED",
        "acquisition_date": "2026-08-29",
        "purchase_price": "125.50",
        "purchase_currency": "HKD",
        "purchase_source": "Collector show vendor",
        "shipping_cost": "",
        "buyers_premium": "",
        "tax": "",
    }
    values.update(updates)
    return values


class ManualBanknoteFormMappingTests(unittest.TestCase):
    def test_supported_desktop_entry_form_exposes_type_and_disposition(self):
        source = inspect.getsource(CoinCollectionGUI.create_widgets)

        self.assertIn('self.item_type_var = tk.StringVar(value=ItemType.COIN.value)', source)
        self.assertIn('values=[value.value for value in ItemType]', source)
        self.assertIn(
            'self.disposition_var = tk.StringVar(value=Disposition.UNDECIDED.value)',
            source,
        )
        self.assertIn('values=[value.value for value in Disposition]', source)
        self.assertIn('self.issuer_var = tk.StringVar()', source)
        self.assertIn('self.title_var = tk.StringVar()', source)
        self.assertIn('self.reference_var = tk.StringVar()', source)

    def test_coin_form_mapping_remains_supported(self):
        mapped = CoinCollectionGUI.manual_item_values_from_text({
            **banknote_form(),
            "item_type": "COIN",
            "country": "France",
            "issuer": "Monnaie de Paris",
            "denomination": "2 euro",
            "year": "2002",
            "disposition": "KEEP",
            "identification_status": "",
        })

        self.assertIs(mapped["item_type"], ItemType.COIN)
        self.assertIs(mapped["disposition"], Disposition.KEEP)
        self.assertIs(
            mapped["identification_status"], IdentificationStatus.IDENTIFIED
        )
        self.assertEqual("Monnaie de Paris", mapped["issuer"])

    def test_banknote_form_mapping_is_neutral_and_preserves_acquisition(self):
        mapped = CoinCollectionGUI.manual_item_values_from_text(banknote_form())

        self.assertIs(mapped["item_type"], ItemType.BANKNOTE)
        self.assertEqual("The Chartered Bank", mapped["issuer"])
        self.assertEqual("Ten Dollars", mapped["denomination"])
        self.assertEqual("1 January 1962 series", mapped["year"])
        self.assertIs(mapped["disposition"], Disposition.SELL_TRADE)
        self.assertEqual(Decimal("125.50"), mapped["purchase_price"])
        self.assertEqual("HKD", mapped["purchase_currency"])
        self.assertEqual("Collector show vendor", mapped["purchase_source"])

    def test_default_disposition_and_derived_partial_status(self):
        mapped = CoinCollectionGUI.manual_item_values_from_text({
            "item_type": "BANKNOTE",
            "issuer": "Unknown local issuer",
            "denomination": "Five",
        })

        self.assertIs(mapped["disposition"], Disposition.UNDECIDED)
        self.assertIs(
            mapped["identification_status"], IdentificationStatus.PARTIAL
        )

    def test_invalid_closed_values_are_rejected_before_mapping(self):
        for field, value in (("item_type", "TOKEN"), ("disposition", "MAYBE")):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field):
                    CoinCollectionGUI.manual_item_values_from_text(
                        banknote_form(**{field: value})
                    )


class ManualBanknotePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "collection.json"
        self.collection = CoinCollection(str(self.path))
        self.app = CoinCollectionApp(collection=self.collection)

    def test_manual_add_reload_edit_is_one_authoritative_banknote(self):
        mapped = CoinCollectionGUI.manual_item_values_from_text(banknote_form())
        front_path = Path(self.temporary.name) / "note-front.jpg"
        back_path = Path(self.temporary.name) / "note-back.jpg"
        front_path.write_bytes(b"front")
        back_path.write_bytes(b"back")
        photos = [
            ItemPhoto(str(front_path), PhotoRole.FRONT, True, "front", 0),
            ItemPhoto(str(back_path), PhotoRole.BACK, False, "back", 1),
        ]

        with patch("coin_collection.utc_now_rfc3339", return_value=T1):
            self.assertTrue(
                self.app.add_to_collection(
                    mapped.pop("country"),
                    mapped.pop("denomination"),
                    mapped.pop("year"),
                    mapped.pop("grade"),
                    mapped.pop("notes"),
                    photos=photos,
                    **mapped,
                )
            )

        item_id = self.app.last_added_item_id
        self.assertTrue(item_id)
        self.assertEqual(1, len(self.collection.items))
        reloaded = CoinCollection(str(self.path))
        saved = reloaded.get_item(item_id)
        self.assertIsNotNone(saved)
        self.assertIs(saved.item_type, ItemType.BANKNOTE)
        self.assertEqual(T1, saved.updated_at)
        self.assertEqual(
            [PhotoRole.FRONT, PhotoRole.BACK],
            [photo.role for photo in saved.normalized_photos()],
        )
        self.assertEqual("2026-08-29", saved.acquisition_date)
        self.assertEqual(Decimal("125.50"), saved.purchase_price)

        with patch("coin_collection.utc_now_rfc3339", return_value=T2):
            self.assertTrue(reloaded.update_item(item_id, {
                "grade": "EF",
                "notes": "Updated after physical inspection.",
                "purchase_price": "130.00",
                "purchase_currency": "CAD",
                "purchase_source": "Estate vendor",
                "disposition": "KEEP",
            }))

        reopened = CoinCollection(str(self.path))
        updated = reopened.get_item(item_id)
        self.assertEqual(1, len(reopened.items))
        self.assertEqual(item_id, updated.id)
        self.assertIs(updated.item_type, ItemType.BANKNOTE)
        self.assertEqual(T2, updated.updated_at)
        self.assertEqual("EF", updated.grade)
        self.assertEqual(Decimal("130.00"), updated.purchase_price)
        self.assertEqual("CAD", updated.purchase_currency)
        self.assertEqual("Estate vendor", updated.purchase_source)
        self.assertIs(updated.disposition, Disposition.KEEP)
        self.assertEqual(
            [PhotoRole.FRONT, PhotoRole.BACK],
            [photo.role for photo in updated.normalized_photos()],
        )

        details = CoinCollectionGUI.item_details_text(updated)
        self.assertIn("Item Type: BANKNOTE", details)
        self.assertIn("Issuer: The Chartered Bank", details)
        self.assertIn("Disposition: KEEP", details)
        self.assertIn(f"Updated At: {T2}", details)
        self.assertIn(f"Primary: FRONT - {updated.photos[0].path}", details)
        self.assertIn(f"Photo: BACK - {updated.photos[1].path}", details)

    def test_banknote_needs_neither_recognition_nor_photo(self):
        self.assertIsNone(self.app.current_image_path)
        self.assertTrue(self.app.add_to_collection(
            "India",
            "One Rupee",
            "1940 issue",
            "Fine",
            "Manual entry",
            item_type="BANKNOTE",
            issuer="Government of India",
        ))
        self.assertEqual(1, len(CoinCollection(str(self.path)).items))

    def test_invalid_type_or_disposition_cannot_enter_authoritative_state(self):
        for kwargs in (
            {"item_type": "TOKEN"},
            {"item_type": "BANKNOTE", "disposition": "MAYBE"},
        ):
            with self.subTest(kwargs=kwargs):
                self.assertFalse(self.app.add_to_collection(
                    "Country", "Value", "Series", "", "", **kwargs
                ))
                self.assertEqual(0, len(self.collection.items))
                self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
