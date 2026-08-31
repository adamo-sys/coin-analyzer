"""Focused tests for the truthful incomplete manual-entry contract."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from coin_collection import (
    CoinCollection,
    CoinCollectionApp,
    CoinItem,
    CollectionLoadState,
    IdentificationStatus,
    ItemPhoto,
    ItemType,
)
from coin_collection_gui import CoinCollectionGUI


class _Value:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value


class _Text(_Value):
    def get(self, *_args):
        return self.value


class _CapturingApp:
    def __init__(self):
        self.current_image_path = ""
        self.last_added_item_id = "saved-item"
        self.calls = []

    def add_to_collection(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return True


def manual_values(**overrides):
    values = {
        "item_type": "COIN",
        "disposition": "UNDECIDED",
        "country": "",
        "issuer": "",
        "denomination": "",
        "year": "",
        "title": "",
        "reference": "",
        "grade": "",
        "notes": "",
    }
    values.update(overrides)
    return CoinCollectionGUI.manual_item_values_from_text(values)


class TruthfulStatusDerivationTests(unittest.TestCase):
    def assert_status(self, expected, **values):
        mapped = manual_values(**values)
        self.assertIs(expected, mapped["identification_status"])
        return mapped

    def test_coin_world_and_mystery_statuses(self):
        self.assert_status(
            IdentificationStatus.UNIDENTIFIED,
            notes="Unidentified copper-coloured piece with square hole.",
        )
        self.assert_status(
            IdentificationStatus.PARTIAL,
            country="Japan",
            issuer="Empire of Japan",
        )
        self.assert_status(
            IdentificationStatus.IDENTIFIED,
            country="Canada",
            denomination="25 cents",
            year="1967",
            identification_status="UNIDENTIFIED",
        )

    def test_partial_and_identified_banknotes(self):
        self.assert_status(
            IdentificationStatus.PARTIAL,
            item_type="BANKNOTE",
            issuer="Banque de France",
            year="Series 1941",
        )
        self.assert_status(
            IdentificationStatus.IDENTIFIED,
            item_type="BANKNOTE",
            issuer="Reichsbank",
            denomination="100 Mark",
            year="Series 1920",
        )

    def test_title_and_notes_preserve_mysteries_without_promoting_identity(self):
        for values in ({"title": "Mystery trade token"}, {"notes": "Found in old album"}):
            with self.subTest(values=values):
                mapped = self.assert_status(IdentificationStatus.UNIDENTIFIED, **values)
                self.assertTrue(CoinCollectionGUI.manual_item_is_meaningful(mapped))

    def test_placeholders_are_not_facts_and_are_preserved_verbatim(self):
        mapped = self.assert_status(
            IdentificationStatus.UNIDENTIFIED,
            country="Unknown",
            issuer="N/A",
            denomination="none",
            year="Not Applicable",
            reference="unidentified",
            identification_status="IDENTIFIED",
        )
        self.assertEqual("Unknown", mapped["country"])
        self.assertEqual("N/A", mapped["issuer"])
        self.assertFalse(CoinCollectionGUI.manual_item_is_meaningful(mapped))

    def test_reference_anchor_identifies_historical_or_token_material(self):
        mapped = self.assert_status(
            IdentificationStatus.IDENTIFIED,
            title="Upper Canada trade token",
            reference="Breton 719",
        )
        self.assertEqual("", mapped["country"])
        self.assertEqual("", mapped["denomination"])

    def test_empty_and_ownership_only_drafts_are_rejected_as_not_meaningful(self):
        self.assertFalse(CoinCollectionGUI.manual_item_is_meaningful(manual_values()))
        ownership_only = manual_values(
            disposition="KEEP",
            acquisition_date="2026-08-30",
            purchase_price="20.00",
            purchase_currency="CAD",
            purchase_source="Coin show",
        )
        self.assertFalse(CoinCollectionGUI.manual_item_is_meaningful(ownership_only))
        self.assertIs(
            IdentificationStatus.UNIDENTIFIED,
            ownership_only["identification_status"],
        )


class TruthfulManualPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "collection.json"
        self.collection = CoinCollection(str(self.path))
        self.app = CoinCollectionApp(collection=self.collection)

    def add_mapped(self, mapped, photos=()):
        values = dict(mapped)
        return self.app.add_to_collection(
            values.pop("country"),
            values.pop("denomination"),
            values.pop("year"),
            values.pop("grade"),
            values.pop("notes"),
            photos=list(photos),
            **values,
        )

    def test_unidentified_coin_with_photo_and_notes_round_trips(self):
        source = self.root / "mystery.jpg"
        source.write_bytes(b"mystery-photo")
        mapped = manual_values(notes="Unidentified token; lettering is worn.")
        photos = [ItemPhoto(str(source), is_primary=True)]

        self.assertTrue(CoinCollectionGUI.manual_item_is_meaningful(mapped, photos))
        self.assertTrue(self.add_mapped(mapped, photos))

        saved = CoinCollection(str(self.path)).items[0]
        self.assertIs(saved.identification_status, IdentificationStatus.UNIDENTIFIED)
        self.assertEqual("", saved.country)
        self.assertEqual("", saved.denomination)
        self.assertEqual(b"mystery-photo", Path(saved.photos[0].path).read_bytes())

    def test_incomplete_coin_without_photo_saves_when_notes_are_meaningful(self):
        mapped = manual_values(notes="Mystery item awaiting attribution")
        self.assertTrue(self.add_mapped(mapped))
        self.assertIs(
            IdentificationStatus.UNIDENTIFIED,
            CoinCollection(str(self.path)).items[0].identification_status,
        )

    def test_all_edit_transitions_preserve_stable_id_and_factual_values(self):
        initial = manual_values(notes="Mystery")
        self.assertTrue(self.add_mapped(initial))
        item_id = self.app.last_added_item_id

        states = (
            (manual_values(issuer="Kingdom of Italy", notes="Mystery"), IdentificationStatus.PARTIAL),
            (manual_values(issuer="Kingdom of Italy", denomination="10 Centesimi", year="1894", notes="Mystery"), IdentificationStatus.IDENTIFIED),
            (manual_values(issuer="Kingdom of Italy", denomination="10 Centesimi", notes="Mystery"), IdentificationStatus.PARTIAL),
            (manual_values(notes="Mystery"), IdentificationStatus.UNIDENTIFIED),
        )
        for updates, expected in states:
            with self.subTest(expected=expected.value):
                self.assertTrue(self.collection.update_item(item_id, updates))
                saved = CoinCollection(str(self.path)).get_item(item_id)
                self.assertIsNotNone(saved)
                self.assertEqual(item_id, saved.id)
                self.assertIs(expected, saved.identification_status)
                self.assertEqual(updates["issuer"], saved.issuer)
                self.assertEqual(updates["denomination"], saved.denomination)
                self.assertEqual(updates["year"], saved.year)

    def test_explicit_inconsistent_v1_status_remains_loadable(self):
        record = CoinItem(
            id="legacy-inconsistent",
            image_path="",
            country="",
            denomination="",
            year="",
            grade="",
            notes="Existing V1 record",
            date_added="2026-08-30",
            identification_status=IdentificationStatus.IDENTIFIED,
        ).to_dict()
        self.path.write_text(
            json.dumps({"schema_version": 1, "items": [record]}),
            encoding="utf-8",
        )

        loaded = CoinCollection(str(self.path))

        self.assertIs(loaded.load_state, CollectionLoadState.VALID)
        self.assertIs(
            loaded.items[0].identification_status,
            IdentificationStatus.IDENTIFIED,
        )


class TruthfulAutomationBoundaryTests(unittest.TestCase):
    def make_gui(self):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.app = _CapturingApp()
        gui.item_type_var = _Value(ItemType.COIN.value)
        gui.disposition_var = _Value("UNDECIDED")
        gui.identification_status_var = _Value("IDENTIFIED")
        gui.country_var = _Value("Unknown")
        gui.issuer_var = _Value("N/A")
        gui.denomination_var = _Value("N/A")
        gui.year_var = _Value("Unknown")
        gui.title_var = _Value("")
        gui.reference_var = _Value("")
        gui.grade_var = _Value("")
        gui.notes_text = _Text("Unresolved automation suggestion")
        gui.current_item_photos = []
        gui.pending_inbox_manager = None
        gui.pending_inbox_photo_set_id = ""
        gui.detection_result = {
            "success": True,
            "country": "Unknown",
            "denomination": "N/A",
            "year": "Unknown",
        }
        gui.sync_current_image_path_from_photos = Mock()
        gui.record_detection_observation_after_save = Mock()
        gui.log_correction = Mock()
        gui.clear_form = Mock()
        gui.refresh_collection_list = Mock()
        return gui

    def test_automation_placeholders_use_truthful_derivation_and_do_not_log_success(self):
        gui = self.make_gui()

        with patch("coin_collection_gui.messagebox.showinfo"):
            gui.save_to_collection()

        self.assertEqual(1, len(gui.app.calls))
        _args, kwargs = gui.app.calls[0]
        self.assertIs(
            IdentificationStatus.UNIDENTIFIED,
            kwargs["identification_status"],
        )
        gui.record_detection_observation_after_save.assert_not_called()
        gui.log_correction.assert_not_called()

    def test_gui_rejects_empty_or_ownership_only_creation(self):
        for acquisition in (
            None,
            {
                "acquisition_date": "2026-08-30",
                "purchase_price": "20.00",
                "purchase_currency": "CAD",
                "purchase_source": "Coin show",
                "shipping_cost": "",
                "buyers_premium": "",
                "tax": "",
            },
        ):
            with self.subTest(acquisition=bool(acquisition)):
                gui = self.make_gui()
                gui.country_var = _Value("")
                gui.issuer_var = _Value("")
                gui.denomination_var = _Value("")
                gui.year_var = _Value("")
                gui.notes_text = _Text("")
                gui.detection_result = None
                if acquisition is not None:
                    gui.acquisition_controls = {"values": lambda: acquisition}

                with patch("coin_collection_gui.messagebox.showwarning") as warning:
                    gui.save_to_collection()

                self.assertEqual([], gui.app.calls)
                warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
