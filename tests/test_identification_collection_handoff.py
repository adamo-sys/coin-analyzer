"""Deterministic desktop handoff with real temporary persistence and Tk variables."""

import unittest
import tkinter as tk
import weakref
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from coin_collection import CoinCollection
from coin_collection_gui import CoinCollectionGUI
from tests import test_canadian_date_review as date_review


class IdentificationCollectionHandoffTests(unittest.TestCase):
    fixture = date_review.CanadianDateReviewTests()

    def gui(self, directory, year="1959"):
        gui = self.fixture.gui(directory, self.fixture.output(year))
        gui.initialize_identity_handoff()
        gui.run_detection()
        return gui

    def test_manual_values_and_cleared_corrections_are_protected(self):
        with TemporaryDirectory() as directory:
            gui = self.gui(directory)
            gui.country_var.set("USA")
            gui.year_var.set("1949")
            gui.denomination_var.set("nickel")
            gui.denomination_var.set("")
            gui.use_detection_results()
            self.assertEqual(("USA", "", "1949"), tuple(
                getattr(gui, name + "_var").get() for name in ("country", "denomination", "year")))
            self.assertEqual("Manually entered / corrected", gui.identity_origin_text("year"))

    def test_suggestions_are_unconfirmed_until_save_and_save_reloads_exact_values(self):
        with TemporaryDirectory() as directory:
            gui = self.gui(directory)
            gui.use_detection_results()
            self.assertEqual("Suggested / unconfirmed", gui.identity_origin_text("year"))
            self.assertEqual([], gui.app.collection.items)
            self.assertEqual([], gui.confirmed_observation_store.load().records)
            gui.year_var.set("1949")
            with patch("coin_collection_gui.messagebox.showinfo"):
                gui.save_to_collection()
            item = CoinCollection(gui.app.collection.storage_path).items[0]
            self.assertEqual(("Canada", "penny", "1949"), (item.country, item.denomination, item.year))
            self.assertFalse(item.auto_detected)
            self.assertEqual(0, item.detection_confidence)
            record = gui.confirmed_observation_store.load().records[0]
            self.assertEqual("1949", record.confirmed_values["year"])
            self.assertNotIn("confidence", record.evidence_snapshot)
            self.assertNotIn("year_confidence", record.evidence_snapshot)

    def test_rerun_drops_copied_suggestions_but_keeps_manual_values(self):
        with TemporaryDirectory() as directory:
            gui = self.gui(directory)
            gui.use_detection_results()
            gui.country_var.set("USA")
            gui.run_detection()
            self.assertEqual("USA", gui.country_var.get())
            self.assertEqual("", gui.year_var.get())
            self.assertEqual("", gui.denomination_var.get())
            self.assertEqual([], gui.confirmed_observation_store.load().records)

    def test_unknown_and_conflicting_suggestions_stay_out_of_form(self):
        with TemporaryDirectory() as directory:
            gui = self.gui(directory)
            assert gui.detection_result is not None
            gui.detection_result.update(country="unknown", denomination="unknown", year="1959",
                                        year_candidates=["1959", "1969"])
            gui.use_detection_results()
            self.assertEqual(("", "", ""), tuple(
                getattr(gui, name + "_var").get() for name in ("country", "denomination", "year")))
            self.assertEqual([], gui.confirmed_observation_store.load().records)

    def test_repeated_apply_and_save_do_not_duplicate_record(self):
        with TemporaryDirectory() as directory:
            gui = self.gui(directory)
            gui.clear_form = lambda: CoinCollectionGUI.clear_form(gui)
            gui.refresh_photo_list = Mock()
            gui.clear_pending_inbox_create = Mock()
            with patch("coin_collection_gui.messagebox.showinfo"), patch("coin_collection_gui.messagebox.showwarning"):
                gui.use_detection_results()
                gui.use_detection_results()
                gui.save_to_collection()
                gui.save_to_collection()
            self.assertEqual(1, len(CoinCollection(gui.app.collection.storage_path).items))
            self.assertEqual(1, len(gui.confirmed_observation_store.load().records))
            self.assertEqual("Not supplied", gui.identity_origin_text("year"))

    def test_tk_traces_do_not_retain_gui_and_track_same_value_manual_acceptance(self):
        with TemporaryDirectory() as directory:
            gui = self.gui(directory)
            gui.use_detection_results()
            gui.year_var.set("1959")
            self.assertEqual("Manually entered / corrected", gui.identity_origin_text("year"))
            variables = [gui.country_var, gui.denomination_var, gui.year_var]
            reference = weakref.ref(gui)
            del gui
            self.assertIsNone(reference(), "Trace callbacks must not retain a GUI for worker-thread finalization")
            for variable in variables:
                variable.set("")

    def test_existing_values_have_unknown_origin_and_are_kept(self):
        with TemporaryDirectory() as directory:
            gui = self.fixture.gui(directory, self.fixture.output("1959"))
            gui.year_var.set("1949")
            gui.run_detection()
            gui.use_detection_results()
            self.assertEqual("1949", gui.year_var.get())
            self.assertEqual("Origin unknown / review", gui.identity_origin_text("year"))

    def test_failed_save_does_not_confirm_suggestions(self):
        with TemporaryDirectory() as directory:
            gui = self.gui(directory)
            gui.use_detection_results()
            with patch.object(gui.app.collection, "add_item", return_value=False), patch(
                "coin_collection_gui.messagebox.showerror"
            ):
                gui.save_to_collection()
            self.assertEqual([], gui.app.collection.items)
            self.assertEqual([], gui.confirmed_observation_store.load().records)
            self.assertEqual("Suggested / unconfirmed", gui.identity_origin_text("year"))

    def test_real_tk_origin_labels_update_and_release_on_main_thread(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        root.withdraw()
        try:
            with TemporaryDirectory() as directory:
                gui = self.gui(directory)
                gui.identity_origin_labels = {field: tk.Label(root) for field in ("country", "denomination", "year")}
                gui.use_detection_results()
                root.update_idletasks()
                self.assertIn("unconfirmed", gui.identity_origin_labels["year"].cget("text"))
                gui.year_var.set("1949")
                self.assertIn("Manually", gui.identity_origin_labels["year"].cget("text"))
                gui.refresh_photo_list = Mock()
                gui.clear_image()
                self.assertEqual("1949", gui.year_var.get())
                self.assertEqual("", gui.country_var.get())
                reference = weakref.ref(gui)
                del gui
                self.assertIsNone(reference())
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
