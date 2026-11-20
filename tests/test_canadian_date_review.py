"""Synthetic desktop date evidence, manual-entry, and persistence contracts."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import tkinter as tk
import sys
import numpy as np

from coin_recognition import CoinRecognizer
import unittest
from unittest.mock import Mock, patch

from coin_collection import CoinCollection, CoinCollectionApp
from coin_collection_gui import CoinCollectionGUI
from confirmed_observations import ConfirmedObservationStore, ObservationOutcome
from legacy_coin_recognition_capability import LegacyCoinRecognitionCapability, to_legacy_detector_result
from legacy_recognition_orchestration import RecognitionCapabilityRegistry, RecognitionOrchestrator


class CanadianDateReviewTests(unittest.TestCase):
    def output(self, year=None, candidates=None):
        return dict(success=True, country="Canada", denomination="penny", year=year,
                    year_candidates=candidates, denomination_confidence=1.0,
                    year_confidence=0.6 if year else 0.0)

    def adapter(self, output):
        capability = LegacyCoinRecognitionCapability(lambda: SimpleNamespace(detect_coin=lambda _: output))
        return to_legacy_detector_result(capability.execute("synthetic.jpg"))

    def gui(self, directory, output, recognizer=None):
        capability = LegacyCoinRecognitionCapability(lambda: recognizer or SimpleNamespace(detect_coin=lambda _: output))
        registry = RecognitionCapabilityRegistry([capability])
        app = CoinCollectionApp(collection=CoinCollection(str(Path(directory) / "collection.json")),
                                recognition_orchestrator=RecognitionOrchestrator(registry))
        app.current_image_path = "synthetic.jpg"
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.app = app
        gui.current_item_photos = []
        gui.detection_label = Mock()
        gui.confidence_label = Mock()
        gui.visual_review_handoff_button = Mock()
        gui.log_detection = Mock()  # Existing debug CSV must not touch local data.
        interpreter = tk.Tcl()
        for name in ("country", "denomination", "year", "grade"):
            setattr(gui, name + "_var", tk.StringVar(interpreter, value=""))
        gui.notes_text = Mock()
        gui.notes_text.get.return_value = ""
        gui.refresh_entry_suggestions = Mock()
        gui.sync_current_image_path_from_photos = Mock()
        gui.pending_inbox_manager = None
        gui.confirmed_observation_store = ConfirmedObservationStore(str(Path(directory) / "observations.jsonl"))
        gui.log_correction = Mock()
        gui.clear_form = Mock()
        gui.refresh_collection_list = Mock()
        return gui

    def test_adapter_sanitizes_distinct_complete_years_without_promoting_them(self):
        candidates = [dict(year="1969", source="private", confidence=0.9), dict(year="1959"),
                      dict(year="1969"), dict(year=1979), dict(year="195"), dict(year="19?9"),
                      dict(year=True), dict(year="１９５９"), "1959", None, {}, dict(year=[1959])]
        result = self.adapter(self.output(candidates=candidates))
        self.assertEqual(["1959", "1969", "1979"], result.get("year_candidates"))
        self.assertIsNone(result["year"])
        self.assertNotIn("private", repr(result))

    def test_malformed_candidate_containers_are_empty_and_do_not_invent_years(self):
        for candidates in (None, {}, "1959", 1959, [None, {}, dict(year="19")]):
            with self.subTest(candidates=candidates):
                result = self.adapter(self.output(candidates=candidates))
                self.assertEqual([], result.get("year_candidates"))
                self.assertIsNone(result["year"])

    def test_conflicting_evidence_reaches_desktop_review_without_year_prefill(self):
        with TemporaryDirectory() as directory:
            gui = self.gui(directory, self.output(candidates=[dict(year="1959"), dict(year="1969"), dict(year="1979")]))
            gui.run_detection()
            text = gui.detection_label.config.call_args.kwargs["text"]
            for phrase in ("Date uncertain", "1959, 1969, 1979", "conflicting OCR", "correct year may be different", "manually", "clearer photo"):
                self.assertIn(phrase.lower(), text.lower())
            self.assertNotIn("Suggested Year: None", text)
            self.assertIn("unavailable", gui.confidence_label.config.call_args.kwargs["text"].lower())
            with patch("coin_collection_gui.messagebox.showwarning"):
                gui.use_detection_results()
            self.assertEqual("", gui.year_var.get())
            self.assertTrue(gui.recognition_result_needs_paired_review(gui.detection_result))
            self.assertEqual([], gui.app.collection.items)

    def test_partial_or_unreadable_date_has_guidance_without_candidates(self):
        with TemporaryDirectory() as directory:
            for candidates in ([], [dict(year="195")], [dict(year="19?9")]):
                gui = self.gui(directory, self.output(candidates=candidates))
                gui.run_detection()
                text = gui.detection_label.config.call_args.kwargs["text"]
                self.assertIn("Date uncertain", text)
                self.assertIn("complete year", text)
                self.assertNotIn("Plausible OCR years", text)
                self.assertIn("clearer photo", text)

    def test_clear_date_preserves_successful_suggestion_and_manual_save(self):
        with TemporaryDirectory() as directory:
            gui = self.gui(directory, self.output("1959", [dict(year="1959"), dict(year="1959")]))
            gui.run_detection()
            text = gui.detection_label.config.call_args.kwargs["text"]
            self.assertIn("Suggested Year: 1959", text)
            self.assertNotIn("uncertain", text)
            with patch("coin_collection_gui.messagebox.showwarning"), patch("coin_collection_gui.messagebox.showinfo"):
                gui.use_detection_results()
                gui.save_to_collection()
            self.assertEqual("1959", gui.app.collection.items[0].year)
            records = gui.confirmed_observation_store.load().records
            self.assertEqual(ObservationOutcome.ACCEPTED, records[0].outcome)

    def test_unresolved_save_is_not_confirmed_and_explicit_correction_can_save(self):
        with TemporaryDirectory() as directory:
            gui = self.gui(directory, self.output(candidates=[dict(year="1959"), dict(year="1969")]))
            gui.run_detection()
            with patch("coin_collection_gui.messagebox.showwarning"), patch("coin_collection_gui.messagebox.showinfo"):
                gui.use_detection_results()
                gui.save_to_collection()
                self.assertEqual("", gui.app.collection.items[0].year)
                self.assertEqual([], gui.confirmed_observation_store.load().records)
                gui.year_var.set("1949")  # Explicit manual correction outside candidate list.
                gui.save_to_collection()
            reloaded = CoinCollection(str(Path(directory) / "collection.json"))
            self.assertEqual(["", "1949"], [item.year for item in reloaded.items])
            records = gui.confirmed_observation_store.load().records
            self.assertEqual(1, len(records))
            self.assertEqual(ObservationOutcome.CORRECTED, records[0].outcome)
            self.assertEqual("1949", records[0].confirmed_values["year"])

    def test_unresolved_prefill_preserves_explicit_manual_year(self):
        with TemporaryDirectory() as directory:
            gui = self.gui(directory, self.output())
            gui.run_detection()
            gui.year_var.set("1949")
            with patch("coin_collection_gui.messagebox.showwarning"):
                gui.use_detection_results()
            self.assertEqual("1949", gui.year_var.get())

    def test_synthetic_ocr_runs_through_real_recognizer_adapter_and_gui(self):
        for readings, expected_year, expected_candidates in (
            (["CANADA ONE CENT 1959", "1969"], None, ["1959", "1969"]),
            (["CANADA ONE CENT 195", "19?9"], None, []),
            (["CANADA ONE CENT 1959", "1959"], "1959", ["1959"]),
        ):
            with self.subTest(readings=readings), TemporaryDirectory() as directory:
                with patch.object(CoinRecognizer, "configure_tesseract"):
                    recognizer = CoinRecognizer()
                jobs = [(str(i), np.zeros((20, 20), dtype=np.uint8), "fixture") for i in range(2)]
                fake_ocr = SimpleNamespace(image_to_string=Mock(side_effect=readings))
                gui = self.gui(directory, None, recognizer)
                with (
                    patch("coin_recognition.cv2.imread", return_value=np.zeros((40, 40, 3), dtype=np.uint8)),
                    patch.object(recognizer, "detect_coin_circle", return_value={
                        "success": True, "center": (20, 20), "radius": 15, "diameter": 30}),
                    patch.object(recognizer, "segment_coin", return_value=np.empty((0, 0), dtype=np.uint8)),
                    patch.object(recognizer, "identify_orientation", return_value="reverse"),
                    patch.object(recognizer, "crop_date_region", return_value=None),
                    patch.object(recognizer, "build_embossed_text_jobs", return_value=jobs),
                    patch.dict(sys.modules, {"pytesseract": fake_ocr}),
                ):
                    gui.run_detection()
                self.assertEqual(expected_year, gui.detection_result["year"])
                self.assertEqual(expected_candidates, gui.detection_result["year_candidates"])
                self.assertEqual("Canada", gui.detection_result["country"])
                with patch("coin_collection_gui.messagebox.showwarning"):
                    gui.use_detection_results()
                self.assertEqual(expected_year or "", gui.year_var.get())
                self.assertEqual([], gui.app.collection.items)

    def test_uncertainty_is_displayed_in_real_tk_label(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        root.withdraw()
        try:
            with TemporaryDirectory() as directory:
                gui = self.gui(directory, self.output(candidates=[dict(year="1959"), dict(year="1969")]))
                gui.detection_label = tk.Label(root)
                gui.confidence_label = tk.Label(root)
                gui.run_detection()
                root.update_idletasks()
                self.assertIn("Date uncertain", gui.detection_label.cget("text"))
                self.assertIn("1959, 1969", gui.detection_label.cget("text"))
                self.assertIn("unavailable", gui.confidence_label.cget("text"))
        finally:
            root.destroy()

    def test_unresolved_marker_cannot_create_confirmed_observation(self):
        with TemporaryDirectory() as directory:
            gui = self.gui(directory, self.output())
            gui.run_detection()
            for year in ("", "None", "unknown", "195", "19?9", "unreadable", "n/a", "not applicable", "unidentified"):
                gui.record_detection_observation_after_save("Canada", "penny", year, [])
            self.assertEqual([], gui.confirmed_observation_store.load().records)


if __name__ == "__main__":
    unittest.main()
