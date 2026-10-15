"""Synthetic source transitions through the real app and GUI entry state."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from coin_collection import ItemPhoto
from coin_collection_gui import CoinCollectionGUI
from tests import test_canadian_date_review as date_review


class StaleDetectionInvalidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.front = self.directory / "front.png"
        self.back = self.directory / "back.png"
        Image.new("RGB", (8, 8), "red").save(self.front)
        Image.new("RGB", (8, 8), "blue").save(self.back)
        fixture = date_review.CanadianDateReviewTests()
        self.gui = fixture.gui(self.temp.name, fixture.output("1959"))
        self.gui.sync_current_image_path_from_photos = lambda: CoinCollectionGUI.sync_current_image_path_from_photos(self.gui)
        self.gui.current_item_photos = [ItemPhoto(str(self.front), is_primary=True)]
        self.gui.selected_photo_index = 0
        self.gui.image_label = Mock()
        self.gui.advanced_id_label = Mock()
        self.gui.refresh_photo_list = Mock()
        self.gui.display_selected_photo = Mock()
        self.gui.sync_current_image_path_from_photos()
        self.gui.initialize_identity_handoff()

    def detect_and_apply(self):
        self.gui.run_detection()
        self.gui.use_detection_results()
        self.assertEqual("1959", self.gui.year_var.get())

    def assert_invalid(self):
        self.assertIsNone(self.gui.detection_result)
        self.assertIsNone(self.gui.app.current_detection_result)
        self.assertEqual("", self.gui.year_var.get())
        self.assertEqual("", self.gui.denomination_var.get())
        self.assertEqual("", self.gui.advanced_id_label.config.call_args.kwargs["text"])
        with patch("coin_collection_gui.messagebox.showwarning"):
            self.gui.use_detection_results()
        self.assertEqual("", self.gui.year_var.get())

    def test_initial_detection_and_changed_primary_preserve_manual_fields_and_disk(self):
        self.detect_and_apply()
        self.gui.country_var.set("France")
        self.gui.grade_var.set("VF-20")
        self.gui.notes_text.get.return_value = "manual notes"
        before = {str(p.relative_to(self.directory)): p.read_bytes() if p.is_file() else None
                  for p in self.directory.rglob("*")}
        with patch("builtins.open", side_effect=AssertionError("transition must not open files")):
            self.gui.current_item_photos = [ItemPhoto(str(self.back), is_primary=True)]
            self.gui.sync_current_image_path_from_photos()
        self.assert_invalid()
        self.assertEqual("France", self.gui.country_var.get())
        self.assertEqual("VF-20", self.gui.grade_var.get())
        self.gui.notes_text.delete.assert_not_called()
        self.assertEqual([], self.gui.app.collection.items)
        self.assertEqual(before, {str(p.relative_to(self.directory)): p.read_bytes() if p.is_file() else None
                  for p in self.directory.rglob("*")})

    def test_invalidation_preserves_existing_saved_records_and_creates_no_files(self):
        self.assertTrue(self.gui.app.add_to_collection("France", "centime", "1949", "VF-20", "saved notes"))
        self.detect_and_apply()
        before = {str(p.relative_to(self.directory)): p.read_bytes() if p.is_file() else None
                  for p in self.directory.rglob("*")}
        saved = self.gui.app.collection.items[0].to_dict()
        for path in (self.back, self.front, None):
            self.gui.current_item_photos = [ItemPhoto(str(path), is_primary=True)] if path else []
            self.gui.sync_current_image_path_from_photos()
            self.assertEqual(saved, self.gui.app.collection.items[0].to_dict())
            self.assertEqual(before, {str(p.relative_to(self.directory)): p.read_bytes() if p.is_file() else None
                  for p in self.directory.rglob("*")})

    def test_detection_backed_save_rechecks_replaced_or_missing_source(self):
        for transition in ("replace", "delete"):
            with self.subTest(transition=transition):
                Image.new("RGB", (8, 8), "red").save(self.front)
                self.gui.app.current_image_path = str(self.front)
                self.gui.app.run_denomination_detector()
                if transition == "replace":
                    Image.new("RGB", (17, 17), "green").save(self.front)
                else:
                    self.front.unlink()

                self.assertTrue(self.gui.app.add_to_collection(
                    "France", "centime", "1949", "VF-20", "manual notes",
                    use_detection=True,
                ))
                item = self.gui.app.collection.items[-1]
                self.assertEqual("France", item.country)
                self.assertEqual("centime", item.denomination)
                self.assertEqual("1949", item.year)
                self.assertEqual("VF-20", item.grade)
                self.assertEqual("manual notes", item.notes)
                self.assertFalse(item.auto_detected)
                self.assertEqual(0.0, item.detection_confidence)
                self.assertIsNone(self.gui.app.current_detection_result)

    def test_detection_backed_save_resolves_final_primary_before_using_advice(self):
        self.gui.app.run_denomination_detector()
        self.assertTrue(self.gui.app.add_to_collection(
            "France", "centime", "1949", "VF-20", "manual notes",
            use_detection=True,
            photos=[ItemPhoto(str(self.front)), ItemPhoto(str(self.back), is_primary=True)],
        ))
        item = self.gui.app.collection.items[-1]
        self.assertEqual(str(self.back), item.image_path)
        self.assertEqual("France", item.country)
        self.assertEqual("centime", item.denomination)
        self.assertFalse(item.auto_detected)
        self.assertEqual(0.0, item.detection_confidence)
        self.assertIsNone(self.gui.app.current_detection_result)

    def test_detection_backed_save_keeps_valid_advice_for_unchanged_primary(self):
        self.gui.app.run_denomination_detector()
        self.assertTrue(self.gui.app.add_to_collection(
            "France", "centime", "1949", "VF-20", "manual notes",
            use_detection=True,
            photos=[ItemPhoto(str(self.back)), ItemPhoto(str(self.front), is_primary=True)],
        ))
        item = self.gui.app.collection.items[-1]
        self.assertEqual(str(self.front), item.image_path)
        self.assertEqual("Canada", item.country)
        self.assertEqual("penny", item.denomination)
        self.assertEqual("1949", item.year)
        self.assertTrue(item.auto_detected)
        self.assertEqual(1.0, item.detection_confidence)

    def test_current_advanced_identification_still_renders(self):
        self.gui.use_identifier = True
        self.gui.identifier = SimpleNamespace(identify_coin=lambda _: {
            "success": True, "year": "1959", "confidence": .5, "method": "template"})
        self.gui.run_advanced_id()
        self.assertIn("Year: 1959", self.gui.advanced_id_label.config.call_args.kwargs["text"])
        self.gui.sync_current_image_path_from_photos()
        self.assertIn("Year: 1959", self.gui.advanced_id_label.config.call_args.kwargs["text"])

    def test_clear_invalidates_both_caches_and_advanced_id(self):
        self.detect_and_apply()
        self.gui.clear_image()
        self.assert_invalid()
        self.assertIsNone(self.gui.app.current_image_path)

    def test_unchanged_source_secondary_attachment_preview_and_reorder_keep_results(self):
        self.detect_and_apply()
        result = self.gui.detection_result
        self.gui.current_item_photos.append(ItemPhoto(str(self.back)))
        self.gui.sync_current_image_path_from_photos()
        self.gui.selected_photo_index = 1
        self.gui.move_selected_photo_up()
        self.assertIs(result, self.gui.detection_result)
        self.assertEqual("1959", self.gui.year_var.get())
        self.gui.app.current_image_path = str(self.front.parent) + "/./" + self.front.name
        self.gui.sync_current_image_path_from_photos()
        self.assertIs(result, self.gui.detection_result)

    def test_primary_selection_and_removal_invalidate(self):
        for action in ("set_selected_photo_primary", "remove_selected_photo"):
            with self.subTest(action=action):
                self.gui.current_item_photos = [ItemPhoto(str(self.front), is_primary=True), ItemPhoto(str(self.back))]
                self.gui.sync_current_image_path_from_photos()
                self.detect_and_apply()
                self.gui.selected_photo_index = 1 if action == "set_selected_photo_primary" else 0
                getattr(self.gui, action)()
                self.assert_invalid()

    def test_late_detection_after_replacement_clear_and_aba_cannot_repopulate(self):
        for transition in ("replace", "clear", "aba"):
            with self.subTest(transition=transition):
                self.gui.current_item_photos = [ItemPhoto(str(self.front), is_primary=True)]
                self.gui.sync_current_image_path_from_photos()
                original_run = self.gui.app._recognition_orchestrator.run
                def obsolete(_path, original_run=original_run, transition=transition):
                    state = original_run(_path)
                    if transition == "clear":
                        self.gui.clear_image()
                    else:
                        self.gui.current_item_photos = [ItemPhoto(str(self.back), is_primary=True)]
                        self.gui.sync_current_image_path_from_photos()
                        if transition == "aba":
                            self.gui.current_item_photos = [ItemPhoto(str(self.front), is_primary=True)]
                            self.gui.sync_current_image_path_from_photos()
                    return state
                with patch.object(self.gui.app._recognition_orchestrator, "run", side_effect=obsolete):
                    self.gui.run_detection()
                self.assert_invalid()

    def test_obsolete_completion_preserves_new_current_source_result(self):
        def obsolete(_path):
            self.gui.current_item_photos = [ItemPhoto(str(self.back), is_primary=True)]
            self.gui.sync_current_image_path_from_photos()
            with patch.object(self.gui.app._recognition_orchestrator, "run", wraps=self.original_run):
                self.gui.run_detection()
                self.gui.use_detection_results()
            return SimpleNamespace(results=[])
        self.original_run = self.gui.app._recognition_orchestrator.run
        with patch.object(self.gui.app._recognition_orchestrator, "run", side_effect=obsolete):
            self.gui.run_detection()
        self.assertEqual("1959", self.gui.year_var.get())
        self.assertTrue(self.gui.detection_result["success"])
        self.assertTrue(self.gui.app.current_detection_result["success"])

    def test_same_path_replacement_during_detection_reconciles_already_advanced_app(self):
        self.detect_and_apply()
        self.gui.country_var.set("France")
        self.gui.advanced_id_label.config(text="Year: 1959")
        old_result = self.gui.detection_result
        old_revision = self.gui.app.image_source_revision
        original_run = self.gui.app._recognition_orchestrator.run

        def replace_while_processing(path):
            state = original_run(path)
            Image.new("RGB", (17, 17), "green").save(self.front)
            self.assertNotEqual(old_revision, self.gui.app.image_source_revision)
            self.assertIsNone(self.gui.app.current_detection_result)
            self.assertIs(old_result, self.gui.detection_result)
            return state

        with patch.object(self.gui.app._recognition_orchestrator, "run",
                          side_effect=replace_while_processing):
            self.gui.run_detection()
        self.assert_invalid()
        self.gui.sync_current_image_path_from_photos()
        self.assert_invalid()
        self.assertEqual("France", self.gui.country_var.get())
        self.assertEqual("manual", self.gui._identity_origins["country"])

    def test_same_path_replacement_during_advanced_id_reconciles_success_and_error(self):
        self.gui.use_identifier = True
        for raises in (False, True):
            with self.subTest(raises=raises):
                self.detect_and_apply()
                self.gui.advanced_id_label.config(text="Year: 1959")

                def identify(_path, raises=raises):
                    Image.new("RGB", (19 if raises else 17, 17), "green").save(self.front)
                    _ = self.gui.app.image_source_revision
                    if raises:
                        raise ValueError("obsolete error")
                    return {"success": True, "year": "1959", "confidence": .5, "method": "template"}

                self.gui.identifier = SimpleNamespace(identify_coin=identify)
                with patch("coin_collection_gui.messagebox.showerror") as error:
                    self.gui.run_advanced_id()
                self.assert_invalid()
                self.gui.sync_current_image_path_from_photos()
                self.assert_invalid()
                error.assert_not_called()

    def test_same_path_nested_newer_results_survive_obsolete_outer_completions(self):
        self.gui.use_identifier = True
        original_run = self.gui.app._recognition_orchestrator.run
        for operation in ("detection", "advanced", "advanced_error"):
            with self.subTest(operation=operation):
                self.detect_and_apply()
                nested = {}

                def complete_new_source(_path, operation=operation, nested=nested):
                    Image.new("RGB", (23 + len(operation), 17), "green").save(self.front)
                    _ = self.gui.app.image_source_revision
                    with patch.object(self.gui.app._recognition_orchestrator, "run",
                                      wraps=original_run):
                        self.gui.run_detection()
                        self.gui.use_detection_results()
                    self.gui.identifier = SimpleNamespace(identify_coin=lambda _: {
                        "success": True, "year": "1969", "confidence": .5, "method": "template"})
                    self.gui.run_advanced_id()
                    nested["result"] = self.gui.detection_result
                    if operation == "advanced_error":
                        raise ValueError("obsolete error")
                    return SimpleNamespace(results=[])

                with patch("coin_collection_gui.messagebox.showerror") as error:
                    if operation == "detection":
                        with patch.object(self.gui.app._recognition_orchestrator, "run",
                                          side_effect=complete_new_source):
                            self.gui.run_detection()
                    else:
                        self.gui.identifier = SimpleNamespace(identify_coin=complete_new_source)
                        self.gui.run_advanced_id()
                self.gui.sync_current_image_path_from_photos()
                self.assertIs(nested["result"], self.gui.detection_result)
                self.assertIs(nested["result"], self.gui.app.current_detection_result)
                self.assertEqual("1959", self.gui.year_var.get())
                self.assertEqual("suggested", self.gui._identity_origins["year"])
                self.assertIn("Year: 1969", self.gui.advanced_id_label.config.call_args.kwargs["text"])
                error.assert_not_called()

    def test_same_path_replaced_image_invalidates_but_unchanged_reselection_does_not(self):
        self.detect_and_apply()
        result = self.gui.detection_result
        self.gui.sync_current_image_path_from_photos()
        self.assertIs(result, self.gui.detection_result)
        Image.new("RGB", (17, 17), "green").save(self.front)
        self.gui.sync_current_image_path_from_photos()
        self.assert_invalid()

    def test_apply_rechecks_source_metadata_before_using_cached_result(self):
        self.detect_and_apply()
        Image.new("RGB", (17, 17), "green").save(self.front)
        with patch("coin_collection_gui.messagebox.showwarning"):
            self.gui.use_detection_results()
        self.assert_invalid()

    def test_late_advanced_identification_does_not_render_or_report_obsolete_errors(self):
        self.gui.use_identifier = True
        for raises in (False, True):
            def identify(_path, raises=raises):
                self.gui.clear_image()
                if raises:
                    raise ValueError("obsolete error")
                return {"success": True, "year": "1959", "confidence": .5, "method": "template"}
            self.gui.current_item_photos = [ItemPhoto(str(self.front), is_primary=True)]
            self.gui.sync_current_image_path_from_photos()
            self.gui.identifier = SimpleNamespace(identify_coin=identify)
            with patch("coin_collection_gui.messagebox.showerror") as error:
                self.gui.run_advanced_id()
            self.assertEqual("", self.gui.advanced_id_label.config.call_args.kwargs["text"])
            error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
