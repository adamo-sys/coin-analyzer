"""Synthetic regressions for coherent saved manual identity transitions."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from coin_collection import CoinCollection, CoinCollectionApp, CoinItem, IdentificationStatus
from coin_collection_gui import CoinCollectionGUI
from collection_item_reference import CollectionItemReference
from collector_work_queue import derive_work_queue

HISTORY = "Saved identity correction history v1:"
KEYS = ("country", "denomination", "year", "type_design", "title", "issuer", "reference",
        "numista_n", "currency", "face_value", "auto_detected", "detection_confidence",
        "from_numista", "identification_status")
RESET = {"title": "", "issuer": "", "reference": "", "numista_n": "", "currency": "",
         "face_value": "", "auto_detected": False, "detection_confidence": 0.0, "from_numista": False}
CLEAR = dict.fromkeys(("country", "denomination", "year", "type_design"), "")


class SavedIdentityCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "collection.json"
        self.collection = CoinCollection(str(self.path))

    def item(self):
        return CoinItem("synthetic-one", "", "Oldland", "Old Unit", "1900", "VF",
            'Collector notes\nIdentification review at initial save:\nAI-assisted visual proposal\nunchanged #370 summary',
            "2026-09-11", title='SYNTHETIC "OLD"\nIDENTITY', issuer="Old Issuer",
            type_design="Old Design", reference="SYNTH-OLD-REF-999", numista_n="SYNTH-OLD-N-999",
            currency="Old Currency", face_value="1", auto_detected=True, detection_confidence=0.87,
            from_numista=True, identification_status=IdentificationStatus.IDENTIFIED,
            acquisition_date="2026-09-10", purchase_price=Decimal("12.34"),
            purchase_source="Synthetic seller", quantity=3, comments="Synthetic ownership", estimate_cad=20)

    def seed(self):
        item = self.item()
        self.assertTrue(self.collection.add_item(item))
        return item

    def assert_cascade(self, item):
        for key, value in RESET.items():
            self.assertEqual(getattr(item, key), value, key)

    def history(self, notes):
        block = notes.split(HISTORY + "\n")[-1]
        self.assertTrue(block.startswith("Superseded values; historical, not current identity.\n"
            "Saving these values did not independently corroborate them.\n"))
        self.assertTrue(block.endswith("\nEnd saved identity correction history v1."))
        return json.loads(block.splitlines()[2])

    def test_each_material_trigger_invalidates_all_dependencies_and_records_literal_history(self):
        for index, updates in enumerate(({"country": "Newland"}, {"denomination": "New Unit"}, {"year": "2020"},
                        {"type_design": "Old Desgin"}, CLEAR)):
            with self.subTest(updates=updates):
                self.path = Path(self.temp.name) / f"trigger-{index}.json"
                self.collection = CoinCollection(str(self.path))
                item = self.seed()
                before = copy.deepcopy(vars(item))
                self.assertTrue(self.collection.update_item(item.id, updates))
                self.assert_cascade(item)
                self.assertEqual(list(self.history(item.notes)), list(KEYS))
                for key in KEYS:
                    self.assertEqual(self.history(item.notes)[key], before[key])
                self.assertTrue(item.notes.startswith(before["notes"] + "\n\n"))
                saved = CoinCollection(str(self.path)).items[0]
                self.assertEqual(saved.notes, item.notes)

    def test_nonmaterial_and_presentation_edits_preserve_legacy_metadata_status_and_history(self):
        item = self.seed()
        item.identification_status = IdentificationStatus.UNIDENTIFIED
        for updates in ({"grade": "XF"}, {"notes": "New collector notes"},
                        {"purchase_source": "Another seller"}, {"quantity": 4, "comments": "new", "estimate_cad": 22},
                        {"country": "  OLDLAND  ", "type_design": "Old\t Design"}):
            with self.subTest(updates=updates):
                self.assertTrue(self.collection.update_item(item.id, updates))
                self.assertEqual(item.title, 'SYNTHETIC "OLD"\nIDENTITY')
                self.assertTrue(item.from_numista)
                self.assertEqual(item.identification_status, IdentificationStatus.UNIDENTIFIED)
                self.assertNotIn(HISTORY, item.notes)
        self.assertEqual(item.country, "  OLDLAND  ")
        app = CoinCollectionApp(collection=self.collection)
        self.assertTrue(app.update_collection_item(item.id, {}, expected_reference=
            CollectionItemReference.capture(self.collection, item)).success)
        self.assertEqual(item.identification_status, IdentificationStatus.UNIDENTIFIED)

    def test_final_status_overrides_supplied_catalogue_and_status(self):
        for identity, status in ((CLEAR, IdentificationStatus.UNIDENTIFIED),
                ({**CLEAR, "country": "Newland"}, IdentificationStatus.PARTIAL),
                ({**CLEAR, "country": "unknown", "denomination": "unknown", "year": "N/A"}, IdentificationStatus.UNIDENTIFIED),
                ({"country": "Newland", "denomination": "New Unit", "year": "2020"}, IdentificationStatus.IDENTIFIED)):
            with self.subTest(identity=identity):
                self.collection = CoinCollection(str(self.path))
                self.collection.items = []
                self.assertTrue(self.collection.save_collection())
                item = self.seed()
                self.assertTrue(self.collection.update_item(item.id, {**identity,
                    "title": "stale", "issuer": "stale", "reference": "stale", "from_numista": True,
                    "identification_status": IdentificationStatus.IDENTIFIED}))
                self.assert_cascade(item)
                self.assertEqual(item.identification_status, status)

    def test_population_and_retry_and_later_transition_have_publication_history(self):
        item = self.seed()
        self.assertTrue(self.collection.update_item(item.id, CLEAR))
        self.assertEqual(item.notes.count(HISTORY), 1)
        self.assertTrue(self.collection.update_item(item.id, CLEAR))
        self.collection = CoinCollection(str(self.path))
        item = self.collection.items[0]
        self.assertTrue(self.collection.update_item(item.id, CLEAR))
        self.assertEqual(item.notes.count(HISTORY), 1)
        self.assertTrue(self.collection.update_item(item.id, {"type_design": "New Design", "notes": item.notes + "\nnew note"}))
        self.assertEqual(item.notes.count(HISTORY), 2)
        self.assertEqual(item.identification_status, IdentificationStatus.UNIDENTIFIED)
        self.assertTrue(self.collection.update_item(item.id, CLEAR))
        self.assertEqual(item.notes.count(HISTORY), 3)

    def test_save_failure_and_stale_baseline_restore_every_field(self):
        for stale in (False, True):
            with self.subTest(stale=stale):
                self.collection = CoinCollection(str(self.path))
                if not self.collection.items:
                    self.seed()
                item = self.collection.items[0]
                before = copy.deepcopy(vars(item))
                if stale:
                    self.path.write_bytes(self.path.read_bytes() + b"\n")
                disk = self.path.read_bytes()
                with patch("coin_collection.write_json_atomically", side_effect=OSError("synthetic failure")):
                    self.assertFalse(self.collection.update_item(item.id, {**CLEAR, "notes": "submitted", "grade": "AU"}))
                self.assertEqual(vars(item), before)
                self.assertEqual(self.path.read_bytes(), disk)

    def test_consumers_numista_replacement_and_specimen_are_preserved(self):
        from numista_importer import NumistaImporter
        from collection_resume import collection_resume_rows
        import pandas as pd
        item = self.seed()
        before = copy.deepcopy(vars(item))
        self.assertTrue(self.collection.update_item(item.id, CLEAR))
        for key in ("id", "date_added", "acquisition_date", "purchase_price", "purchase_source", "quantity", "comments", "estimate_cad", "photos", "image_path"):
            self.assertEqual(getattr(item, key), before[key])
        self.assertEqual(collection_resume_rows(self.collection)[0].label, "Unidentified coin")
        self.assertIn("Confirm identity", [task.title for task in derive_work_queue(self.collection).tasks])
        self.assertEqual(self.collection.search_items("SYNTH-OLD-REF-999"), [item])
        self.assertFalse(NumistaImporter(self.collection).is_duplicate(self.item()))
        with patch("numista_importer.pd.read_excel", return_value=pd.DataFrame()):
            self.assertEqual(NumistaImporter(self.collection).import_from_excel("synthetic.xlsx"), (0, 0))
        self.assertEqual([saved.id for saved in CoinCollection(str(self.path)).items], [item.id])

    def test_submitted_notes_are_base_and_matching_old_history_is_not_deduplicated(self):
        item = self.seed()
        original = copy.deepcopy(vars(item))
        self.assertTrue(self.collection.update_item(item.id, {"country": "Newland", "notes": "Submitted notes"}))
        self.assertTrue(item.notes.startswith("Submitted notes\n\n" + HISTORY))
        first = item.notes
        # A later transition can supersede exactly the same recorded values.
        # Notes content is never the publication/idempotence gate.
        for key in KEYS:
            setattr(item, key, original[key])
        self.assertTrue(self.collection.save_collection())
        self.assertTrue(self.collection.update_item(item.id, {"country": "Newland"}))
        self.assertEqual(item.notes.count(HISTORY), 2)
        self.assertEqual(item.notes, first + "\n\n" + first.split("\n\n", 1)[1])

    def test_failed_material_app_edit_rolls_back_generated_fields_and_new_media(self):
        item = self.seed()
        before = copy.deepcopy(vars(item))
        disk = self.path.read_bytes()
        source = Path(self.temp.name) / "attempt.png"
        Image.new("RGB", (20, 20), "green").save(source)
        app = CoinCollectionApp(collection=self.collection)
        with patch("coin_collection.write_json_atomically", side_effect=OSError("before publication")):
            result = app.update_collection_item(item.id, {**CLEAR, "notes": "submitted"},
                photos=[{"path": str(source)}], expected_reference=CollectionItemReference.capture(self.collection, item))
        self.assertFalse(result.success)
        self.assertEqual(vars(item), before)
        self.assertEqual(self.path.read_bytes(), disk)
        self.assertEqual(result.retained_attempt_media, ())
        self.assertEqual(list((Path(self.temp.name) / "managed_media" / "ordinary").rglob("*.png")), [])
        self.assertTrue(source.exists())

    def test_native_actual_editor_direct_clear_and_two_step_journeys(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = root
        gui.refresh_collection_list = Mock()
        for journey in ((CLEAR,), ({"country": "Newland", "denomination": "New Unit", "year": "2020", "type_design": "New Design"}, CLEAR)):
            self.collection = CoinCollection(str(self.path))
            self.collection.items = []
            self.assertTrue(self.collection.save_collection())
            item = self.seed()
            image = Path(self.temp.name) / "generated.png"
            Image.new("RGB", (30, 30), "blue").save(image)
            gui.app = CoinCollectionApp(collection=self.collection)
            result = gui.app.update_collection_item(item.id, {}, photos=[{"path": str(image)}],
                expected_reference=CollectionItemReference.capture(self.collection, item))
            self.assertTrue(result.success, result.error)
            self.assertNotIn(HISTORY, item.notes)
            self.assertTrue(item.from_numista)
            media_before = [photo.to_dict() for photo in item.photos]
            media_bytes = (Path(self.temp.name) / item.image_path).read_bytes()
            for updates in journey:
                with patch("coin_collection_gui.messagebox.showinfo"), patch("socket.socket", side_effect=AssertionError("network forbidden")):
                    gui.open_edit_item_window(item)
                    root.update()
                    dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
                    form = dialog.winfo_children()[0]
                    for name, label in (("country", "Country:"), ("denomination", "Denomination:"), ("year", "Year:"), ("type_design", "Type / design:")):
                        widget = next(w for w in form.winfo_children() if isinstance(w, ttk.Label) and w.cget("text") == label)
                        entry = next(w for w in form.grid_slaves(row=widget.grid_info()["row"], column=1) if isinstance(w, ttk.Combobox))
                        entry.set(updates[name])
                    button = next(w for frame in form.winfo_children() for w in frame.winfo_children() if isinstance(w, ttk.Button) and w.cget("text") == "Save")
                    button.invoke()
                    root.update()
            saved = CoinCollection(str(self.path)).items[0]
            self.assertEqual(saved.identification_status, IdentificationStatus.UNIDENTIFIED)
            self.assert_cascade(saved)
            self.assertEqual(saved.notes.count(HISTORY), len(journey))
            self.assertEqual([photo.to_dict() for photo in saved.photos], media_before)
            self.assertEqual((Path(self.temp.name) / saved.image_path).read_bytes(), media_bytes)
            self.assertEqual(saved.purchase_price, Decimal("12.34"))
            self.assertEqual(saved.comments, "Synthetic ownership")
            from collection_resume import collection_resume_rows
            reopened = CoinCollection(str(self.path))
            self.assertEqual(collection_resume_rows(reopened)[0].label, "Unidentified coin")
            self.assertIn("Confirm identity", [task.title for task in derive_work_queue(reopened).tasks])
