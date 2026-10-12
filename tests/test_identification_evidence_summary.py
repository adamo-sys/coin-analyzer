"""Synthetic recognition evidence through the production desktop boundary."""

import sys
import tkinter as tk
import unittest
import weakref
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from coin_recognition import CoinRecognizer
from tests import test_canadian_date_review as date_review


class IdentificationEvidenceSummaryTests(unittest.TestCase):
    # Reuse temporary collection setup; never read collection data or debug CSV.
    fixture = date_review.CanadianDateReviewTests()

    def detected_gui(self, directory, readings):
        with patch.object(CoinRecognizer, "configure_tesseract"):
            recognizer = CoinRecognizer()
        gui = self.fixture.gui(directory, None, recognizer)
        jobs = [(str(i), np.zeros((20, 20), dtype=np.uint8), "fixture") for i in range(len(readings))]
        ocr = Mock(side_effect=readings)
        with (
            patch("coin_recognition.cv2.imread", return_value=np.zeros((40, 40, 3), dtype=np.uint8)) as image_reader,
            patch.object(recognizer, "detect_coin_circle", return_value={
                "success": True, "center": (20, 20), "radius": 15, "diameter": 30}),
            patch.object(recognizer, "segment_coin", return_value=np.empty((0, 0), dtype=np.uint8)),
            patch.object(recognizer, "identify_orientation", return_value="reverse"),
            patch.object(recognizer, "crop_date_region", return_value=None),
            patch.object(recognizer, "build_embossed_text_jobs", return_value=jobs),
            patch.dict(sys.modules, {"pytesseract": SimpleNamespace(image_to_string=ocr)}),
        ):
            gui.run_detection()
        # Evidence formatting must not trigger extra image reads or OCR jobs.
        self.assertEqual(1, image_reader.call_count)
        self.assertEqual(len(readings), ocr.call_count)
        return gui

    def displayed(self, gui):
        return gui.detection_label.config.call_args.kwargs["text"]

    def test_supported_ocr_is_distinct_from_identity_and_remains_advisory(self):
        with TemporaryDirectory() as directory:
            gui = self.detected_gui(directory, ["CANADA ONE CENT 1959 private unrelated inscription", "1959"])
            text = self.displayed(gui)
            for phrase in ("OCR readings", "canada", "one cent", "1959", "Identity suggestions",
                           "Suggested Country: Canada", "Suggested Denomination: penny", "Suggested Year: 1959",
                           "not verified", "Country, Denomination, Year"):
                self.assertIn(phrase, text)
            self.assertNotIn("private unrelated", text)
            self.assertNotIn("%", gui.confidence_label.config.call_args.kwargs["text"])
            self.assertEqual([], gui.app.collection.items)
            self.assertEqual([], gui.confirmed_observation_store.load().records)
            with patch("coin_collection_gui.messagebox.showwarning"):
                gui.use_detection_results()
            self.assertEqual("1959", gui.year_var.get())
            self.assertEqual([], gui.confirmed_observation_store.load().records)

    def test_competing_country_denomination_and_dates_are_visible_without_promotion(self):
        with TemporaryDirectory() as directory:
            gui = self.detected_gui(directory, ["CANADA ONE CENT 1959", "USA FIVE CENTS 1969"])
            text = self.displayed(gui)
            for phrase in ("canada, usa", "five cents, one cent", "1959, 1969", "Country conflicting",
                           "Denomination conflicting", "Date uncertain", "not verified"):
                self.assertIn(phrase, text)
            self.assertEqual("Canada", gui.detection_result["country"])  # Legacy selection is retained.
            self.assertEqual("unknown", gui.detection_result["denomination"])
            self.assertIsNone(gui.detection_result["year"])
            self.assertEqual([], gui.app.collection.items)

    def test_partial_and_missing_evidence_do_not_become_inscriptions_or_identity(self):
        for readings in (["CANADA 19?9"], ["unreadable"]):
            with self.subTest(readings=readings), TemporaryDirectory() as directory:
                gui = self.detected_gui(directory, readings)
                text = self.displayed(gui)
                self.assertIn("Denomination unresolved", text)
                self.assertIn("Date uncertain", text)
                self.assertIn("Date: unavailable", text)
                self.assertIn("Other inscriptions: unavailable", text)
                if readings == ["unreadable"]:
                    self.assertIn("Country unresolved", text)
                    self.assertIn("Country: unavailable", text)
                self.assertNotIn("19?9", text)
                with patch("coin_collection_gui.messagebox.showwarning"):
                    gui.use_detection_results()
                self.assertEqual("", gui.year_var.get())

    def test_older_result_keeps_suggestions_but_does_not_claim_ocr_support(self):
        with TemporaryDirectory() as directory:
            gui = self.fixture.gui(directory, self.fixture.output("1959"))
            gui.run_detection()
            text = self.displayed(gui)
            for field in ("Country", "Denomination", "Date"):
                self.assertIn(field + ": unavailable", text)
            self.assertIn("Suggested Year: 1959", text)
            self.assertIn("not verified", text)

    def test_phrase_inferred_across_ocr_readings_is_not_displayed_as_observed(self):
        with TemporaryDirectory() as directory:
            gui = self.detected_gui(directory, ["CANADA ONE", "CENT 1959"])
            text = self.displayed(gui)
            self.assertIn("Denomination: unavailable", text)
            self.assertIn("Suggested Denomination: penny", text)
            self.assertEqual([], gui.detection_result["identification_evidence"]["denomination_matches"])
            self.assertEqual(["penny"], gui.detection_result["identification_evidence"]["denomination_candidates"])
            self.assertEqual([], gui.confirmed_observation_store.load().records)
            with patch("coin_collection_gui.messagebox.showwarning"):
                gui.use_detection_results()
            self.assertEqual("penny", gui.denomination_var.get())
            self.assertEqual([], gui.app.collection.items)
            self.assertEqual([], gui.confirmed_observation_store.load().records)
        with TemporaryDirectory() as directory:
            gui = self.detected_gui(directory, ["CANADA ONE\nCENT 1959"])
            self.assertEqual(["one cent"], gui.detection_result["identification_evidence"]["denomination_matches"])

    def test_adapter_bounds_only_named_evidence_and_preserves_findings(self):
        output = self.fixture.output("1959")
        output["identification_evidence"] = {
            "country_matches": ["canada", "canada", None, {}, "x" * 41],
            "country_candidates": ["Canada"],
            "denomination_matches": "one cent",
            "denomination_candidates": ["penny"],
            "ocr_full_text": "private transcript",
        }
        result = self.fixture.adapter(output)
        self.assertEqual({"country_matches": ["canada"], "country_candidates": ["Canada"],
                          "denomination_matches": [], "denomination_candidates": ["penny"]},
                         result.get("identification_evidence"))
        self.assertEqual("1959", result["year"])
        self.assertNotIn("private transcript", repr(result))
        for malformed in (None, "canada", [], 5):
            output["identification_evidence"] = malformed
            self.assertNotIn("identification_evidence", self.fixture.adapter(output))

    def test_evidence_stays_out_of_saved_identity_and_confirmed_snapshot(self):
        with TemporaryDirectory() as directory:
            gui = self.detected_gui(directory, ["CANADA ONE CENT 1959", "1969"])
            gui.year_var.set("1949")
            with patch("coin_collection_gui.messagebox.showwarning"), patch("coin_collection_gui.messagebox.showinfo"):
                gui.use_detection_results()
                gui.save_to_collection()
            self.assertEqual("1949", gui.app.collection.items[0].year)
            record = gui.confirmed_observation_store.load().records[0]
            self.assertEqual("1949", record.confirmed_values["year"])
            self.assertNotIn("identification_evidence", record.evidence_snapshot)
            self.assertEqual({"country", "denomination", "year"}, set(record.confirmed_values))

    def test_real_tk_label_shows_evidence_sections(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        root.withdraw()

        def exercise_labels():
            with TemporaryDirectory() as directory:
                gui = self.detected_gui(directory, ["CANADA ONE CENT 1959"])
                gui.detection_label = tk.Label(root, wraplength=250)
                gui.confidence_label = tk.Label(root, wraplength=250)
                # The real adapter result is replayed only to avoid running OCR twice.
                gui.app.run_denomination_detector = lambda result=gui.detection_result: result
                gui.run_detection()
                root.update_idletasks()
                self.assertIn("OCR readings", gui.detection_label.cget("text"))
                self.assertIn("not verified", gui.detection_label.cget("text"))
                return weakref.ref(gui)

        try:
            gui_reference = exercise_labels()
            self.assertIsNone(gui_reference(), "Tk fixture must not survive for collection on a worker thread")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
