"""Synthetic photo guidance contracts; no private photos or collection data."""

import tkinter as tk
import unittest
import weakref
from copy import deepcopy
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import identification_recapture_guidance as guidance
from coin_collection import ItemPhoto, PhotoRole
from tests import test_identification_evidence_summary as evidence_tests


class RecaptureGuidanceTests(unittest.TestCase):
    def result(self, years, year=None):
        return {"success": True, "country": "Canada", "denomination": "penny",
                "year": year, "year_candidates": years}

    def test_missing_and_conflicting_dates_produce_one_distinct_instruction(self):
        for years, expected in (([], "No complete date was read. Take a closer photo of the coin's date."),
                                (["1969", "1959", "1969"],
                                 "The date readings disagree. Try a clearer close-up of the date.")):
            with self.subTest(years=years):
                self.assertEqual((expected,), guidance.build_recapture_guidance(self.result(years)))

    def test_single_complete_reading_does_not_request_date_retake(self):
        for years in (["1959"], ["1959", "1959"]):
            for year in (None, "1959"):
                self.assertEqual((), guidance.build_recapture_guidance(self.result(years, year)))
        self.assertEqual((), guidance.build_recapture_guidance(self.result([], "1959")))

    def test_unknown_or_malformed_evidence_does_not_establish_missing_date(self):
        for years in (None, "1959", {}, ["19?9"], [True], ["１９５９"]):
            self.assertEqual((), guidance.build_recapture_guidance(self.result(years)))
        self.assertEqual((), guidance.build_recapture_guidance({"success": True}))
        self.assertEqual((), guidance.build_recapture_guidance({"success": False, "year_candidates": []}))

    def test_reverse_requires_explicit_missing_input_and_unresolved_identity(self):
        result = self.result(["1959"])
        self.assertEqual((), guidance.build_recapture_guidance(result))
        self.assertEqual(("Photograph the reverse side to provide additional identification evidence.",),
                         guidance.build_recapture_guidance(result, reverse_missing=True))
        self.assertEqual((), guidance.build_recapture_guidance(self.result(["1959"], "1959"),
                                                             reverse_missing=True))

    def test_output_is_bounded_deterministic_and_cannot_promote_evidence(self):
        result = self.result(["1969", "1959", "1959"])
        result.update(mintmark="unresolved", blur=True, glare=True, lighting="poor")
        before = deepcopy(result)
        suggestions = guidance.build_recapture_guidance(result, reverse_missing=True)
        self.assertEqual(2, len(suggestions))
        self.assertEqual(len(set(suggestions)), len(suggestions))
        self.assertEqual(suggestions, guidance.build_recapture_guidance(result, reverse_missing=True))
        self.assertEqual(before, result)
        self.assertIn("date readings disagree", suggestions[0])
        for unsupported in ("mintmark", "blur", "glare", "lighting", "shake", "obstruction"):
            self.assertNotIn(unsupported, " ".join(suggestions))


class RecaptureGuiTests(unittest.TestCase):
    fixture = evidence_tests.IdentificationEvidenceSummaryTests()

    def displayed(self, gui):
        return gui.detection_label.config.call_args.kwargs["text"]

    def test_real_recognizer_adapter_guidance_keeps_evidence_and_manual_authority(self):
        for readings, phrase in ((["CANADA ONE CENT 19?9"], "Take a closer photo"),
                                 (["CANADA ONE CENT 1959", "1969"], "date readings disagree"),
                                 (["CANADA ONE CENT 1959", "1959"], None)):
            with self.subTest(readings=readings), TemporaryDirectory() as directory:
                gui = self.fixture.detected_gui(directory, readings)
                text = self.displayed(gui)
                self.assertTrue(text.startswith(gui.identification_evidence_summary(gui.detection_result)))
                if phrase:
                    self.assertIn("Photo suggestions (optional; not identity evidence)", text)
                    self.assertEqual(1, text.count(phrase))
                    gui.year_var.set("1949")
                    with patch("coin_collection_gui.messagebox.showwarning"), patch("coin_collection_gui.messagebox.showinfo"):
                        gui.use_detection_results()
                        gui.save_to_collection()
                    self.assertEqual("1949", gui.app.collection.items[0].year)
                    record = gui.confirmed_observation_store.load().records[0]
                    self.assertEqual("1949", record.confirmed_values["year"])
                    self.assertNotIn("Photo suggestions", repr(record))
                    self.assertNotIn("recapture_guidance", gui.detection_result)
                else:
                    self.assertNotIn("Photo suggestions", text)

    def test_reverse_is_established_from_all_supplied_photo_roles_not_ocr_orientation(self):
        for roles, current, expected in (
            ([PhotoRole.FRONT], "front.jpg", True),
            ([PhotoRole.FRONT, PhotoRole.FRONT], "front.jpg", True),
            ([PhotoRole.FRONT, PhotoRole.BACK], "front.jpg", False),
            ([PhotoRole.FRONT, PhotoRole.OTHER], "front.jpg", False),
            ([PhotoRole.BACK], "front.jpg", False),
            ([], "front.jpg", False),
            ([PhotoRole.FRONT], "unattached.jpg", False),
        ):
            with self.subTest(roles=roles, current=current), TemporaryDirectory() as directory:
                gui = self.fixture.detected_gui(directory, ["CANADA ONE CENT 19?9"])
                gui.current_item_photos = [ItemPhoto(path="front.jpg" if i == 0 else "other.jpg", role=role)
                                          for i, role in enumerate(roles)]
                gui.app.current_image_path = current
                result = gui.detection_result
                gui.app.run_denomination_detector = lambda result=result: result
                gui.run_detection()
                self.assertEqual(expected, "Photograph the reverse side" in self.displayed(gui))

    def test_repeated_analysis_manual_correction_and_clear_do_not_keep_stale_guidance(self):
        with TemporaryDirectory() as directory:
            gui = self.fixture.detected_gui(directory, ["CANADA ONE CENT 1959", "1969"])
            gui.year_var.set("1949")
            result = gui.detection_result
            gui.app.run_denomination_detector = lambda: result
            gui.run_detection()
            self.assertEqual(1, self.displayed(gui).count("date readings disagree"))
            self.assertEqual("1949", gui.year_var.get())
            result = self.fixture.fixture.adapter(self.fixture.fixture.output("1959", [{"year": "1959"}]))
            gui.run_detection()
            self.assertNotIn("Photo suggestions", self.displayed(gui))
            result = {"success": False, "error": "synthetic failure"}
            gui.run_detection()
            self.assertNotIn("Photo suggestions", self.displayed(gui))
            gui.image_label = Mock()
            gui.refresh_photo_list = Mock()
            gui.clear_image()
            self.assertEqual("No detection results", self.displayed(gui))
            self.assertIsNone(gui.detection_result)
            self.assertEqual("1949", gui.year_var.get())

    def test_real_tk_guidance_and_clear_release_fixture_on_owning_thread(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        root.withdraw()

        def exercise():
            with TemporaryDirectory() as directory:
                gui = self.fixture.detected_gui(directory, ["CANADA ONE CENT 1959", "1969"])
                gui.detection_label = tk.Label(root, wraplength=250)
                gui.confidence_label = tk.Label(root, wraplength=250)
                gui.image_label = tk.Label(root)
                gui.refresh_photo_list = Mock()
                gui.app.run_denomination_detector = lambda result=gui.detection_result: result
                gui.run_detection()
                root.update_idletasks()
                self.assertIn("date readings disagree", gui.detection_label.cget("text"))
                self.assertIn("OCR readings", gui.detection_label.cget("text"))
                gui.clear_image()
                self.assertEqual("No detection results", gui.detection_label.cget("text"))
                return weakref.ref(gui)

        try:
            reference = exercise()
            self.assertIsNone(reference(), "No GUI cycle may defer Tcl finalization to a worker")
        finally:
            root.destroy()
