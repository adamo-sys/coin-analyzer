import os
import tempfile
import unittest
import copy
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch
from datetime import datetime
from PIL import Image, ImageDraw

from coin_collection import CoinCollection, CoinCollectionApp, CoinItem, ItemPhoto, PhotoRole, IdentificationStatus
from coin_collection_gui import CoinCollectionGUI


class PreviewScaleTests(unittest.TestCase):
    def test_fit_is_bounded_and_preserves_aspect_ratio(self):
        from coin_collection_gui import SavedPhotoPreview
        self.assertEqual(SavedPhotoPreview.fit_size((1200, 600), (300, 300)), (300, 150))
        self.assertEqual(SavedPhotoPreview.fit_size((100, 50), (300, 300)), (100, 50))
        self.assertEqual(SavedPhotoPreview.fit_size((600, 900), (300, 300)), (200, 300))


class SavedPhotoPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.front = self.directory / "front.png"
        self.back = self.directory / "reverse.png"
        image = Image.new("RGB", (1200, 600), "white")
        ImageDraw.Draw(image).text((100, 100), "SYNTHETIC 1920 A", fill="black")
        image.save(self.front)
        Image.new("RGB", (600, 900), "green").save(self.back)
        self.bytes = {path: path.read_bytes() for path in (self.front, self.back)}
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.root.geometry("300x100")
        self.collection = CoinCollection(str(self.directory / "collection.json"))
        self.item = CoinItem("preview", "", "", "", "", "", "collector notes", "2026-10-07",
            photos=[ItemPhoto(str(self.front), PhotoRole.FRONT, True, "front notes"),
                    ItemPhoto(str(self.back), PhotoRole.BACK, False, "reverse notes", 1)])
        self.assertTrue(self.collection.add_item(self.item))
        self.gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        self.gui.root = self.root
        self.gui.app = CoinCollectionApp(collection=self.collection)
        self.gui.refresh_collection_list = Mock()

    def widgets(self, parent):
        for child in parent.winfo_children():
            yield child
            yield from self.widgets(child)

    def open_editor(self):
        self.gui.open_edit_item_window(self.item)
        self.root.update()
        self.dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        self.preview = next(w for w in self.widgets(self.dialog) if hasattr(w, "show_photo"))
        self.tree = next(w for w in self.widgets(self.dialog) if isinstance(w, ttk.Treeview))

    def button(self, text):
        return next(w for w in self.widgets(self.dialog) if isinstance(w, ttk.Button) and w.cget("text") == text)

    def select(self, index):
        self.tree.selection_set(str(index))
        self.root.update()

    def test_initial_selection_exact_switch_and_read_only_metadata(self):
        before = copy.deepcopy(vars(self.item))
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.open_editor()
            self.assertEqual(self.preview.path, str(self.front))
            self.assertIsNotNone(self.preview.tk_image)
            self.assertIn("Front", self.preview.caption.get())
            self.select(1)
            self.assertEqual(self.preview.path, str(self.back))
            self.assertEqual(self.preview.source_image.size, (600, 900))
            self.assertIn("Reverse", self.preview.caption.get())
        self.assertEqual(vars(self.item), before)

    def test_one_photo_and_no_photo_opening(self):
        self.item.photos = self.item.photos[:1]
        self.open_editor()
        self.assertEqual(self.preview.path, str(self.front))
        self.assertGreater(self.preview.display_size[0], 0)
        self.button("Cancel").invoke()
        self.item.photos = []
        self.item.image_path = ""
        self.open_editor()
        self.assertEqual(self.preview.preview_status, "No photos attached")
        self.assertIsNone(self.preview.tk_image)

    def test_inscription_zoom_bounds_aspect_and_reset(self):
        self.open_editor()
        fit = self.preview.display_size
        self.button("Zoom In").invoke()
        larger = self.preview.display_size
        self.assertGreater(larger[0], fit[0])
        for _ in range(4):
            self.button("Zoom In").invoke()
        self.assertGreaterEqual(self.preview.display_size[0], fit[0] * 3)
        self.assertAlmostEqual(self.preview.display_size[0] / self.preview.display_size[1], 2, places=2)
        before = self.preview.scale
        self.button("Zoom Out").invoke()
        self.assertLess(self.preview.scale, before)
        for _ in range(40):
            self.button("Zoom In").invoke()
        maximum = self.preview.scale
        self.button("Zoom In").invoke()
        self.assertEqual(self.preview.scale, maximum)
        for _ in range(50):
            self.button("Zoom Out").invoke()
        self.assertGreater(self.preview.scale, 0)
        self.button("Reset / Fit").invoke()
        self.assertEqual(self.preview.display_size, fit)
        self.assertEqual(self.front.read_bytes(), self.bytes[self.front])

    def test_draft_add_reorder_remove_and_empty_preview(self):
        self.open_editor()
        extra = self.directory / "detail.png"
        Image.new("RGB", (100, 50), "red").save(extra)
        with patch("coin_collection_gui.filedialog.askopenfilenames", return_value=(str(extra),)):
            self.button("Add Photos").invoke()
        self.root.update()
        self.assertEqual(self.preview.path, str(extra))
        self.button("Move Up").invoke()
        self.root.update()
        self.assertEqual(self.preview.path, str(extra))
        self.button("Remove").invoke()
        self.root.update()
        self.assertEqual(self.preview.path, str(self.back))
        self.button("Remove").invoke()
        self.button("Remove").invoke()
        self.root.update()
        self.assertIsNone(self.preview.source_image)
        self.assertIsNone(self.preview.tk_image)
        self.assertEqual(self.preview.preview_status, "No photos attached")
        self.assertEqual(len(self.item.photos), 2)

    def test_role_notes_refresh_preserves_image_and_cancel_bytes(self):
        before = copy.deepcopy(vars(self.item))
        disk = Path(self.collection.storage_path).read_bytes()
        self.open_editor()
        combos = [w for w in self.widgets(self.dialog) if isinstance(w, ttk.Combobox)]
        role = next(w for w in combos if PhotoRole.FRONT.value in w.cget("values"))
        role.set(PhotoRole.OTHER.value)
        role.event_generate("<<ComboboxSelected>>")
        self.root.update()
        self.assertIn("Other", self.preview.caption.get())
        self.assertEqual(self.preview.path, str(self.front))
        photo_frame = self.tree.master
        notes = next(w for w in photo_frame.winfo_children() if isinstance(w, ttk.Entry))
        notes.delete(0, tk.END)
        notes.insert(0, "draft photo notes")
        notes.event_generate("<Return>")
        self.root.update()
        self.assertEqual(self.preview.path, str(self.front))
        self.assertEqual(self.preview.source_image.size, (1200, 600))
        self.button("Zoom In").invoke()
        self.button("Cancel").invoke()
        self.assertEqual(vars(self.item), before)
        self.assertEqual(Path(self.collection.storage_path).read_bytes(), disk)
        for path, data in self.bytes.items():
            self.assertEqual(path.read_bytes(), data)

    def test_missing_and_unreadable_do_not_block_edit_or_delete_metadata(self):
        bad = self.directory / "bad.png"
        bad.write_bytes(b"unreadable synthetic bytes")
        for path in (self.directory / "missing.png", bad):
            with self.subTest(path=path):
                self.item.photos = [ItemPhoto(str(path), PhotoRole.OTHER, True, "keep notes")]
                self.item.image_path = ""
                self.open_editor()
                self.assertEqual(self.preview.preview_status, "Photo unavailable")
                self.assertIsNone(self.preview.tk_image)
                self.assertEqual(self.item.photos[0].notes, "keep notes")
                self.assertFalse(self.button("Save").instate(("disabled",)))
                self.button("Remove").invoke()
                self.root.update()
                self.assertEqual(self.preview.preview_status, "No photos attached")
                self.preview.show_photo(ItemPhoto(""))
                self.assertEqual(self.preview.preview_status, "Photo unavailable")
                self.preview.show_photo(None)
                self.assertEqual(self.preview.preview_status, "No photos attached")
                self.button("Cancel").invoke()

    def test_work_queue_identity_task_opens_same_record_preview(self):
        self.gui.open_work_queue()
        window = self.gui._work_queue_window
        self.root.update()
        row = next(row for row in window.tree.get_children() if "Confirm identity" in window.tree.item(row)["values"])
        window.tree.selection_set(row)
        window.activate_selected_task()
        self.root.update()
        dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == "Edit Item")
        preview = next(w for w in self.widgets(dialog) if hasattr(w, "show_photo"))
        self.assertEqual(preview.path, str(self.front))
        self.assertEqual(self.item.country, "")
        self.assertEqual(self.item.year, "")

    def test_save_preserves_unresolved_identity_and_refreshes_queue(self):
        self.item.country = "Canada"
        self.item.identification_status = IdentificationStatus.PARTIAL
        self.assertTrue(self.collection.save_collection())
        self.gui.open_work_queue()
        window = self.gui._work_queue_window
        self.root.update()
        row = next(row for row in window.tree.get_children() if "Confirm identity" in window.tree.item(row)["values"])
        window.tree.selection_set(row)
        window.activate_selected_task()
        self.root.update()
        self.dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == "Edit Item")
        with patch("coin_collection_gui.messagebox.showinfo"), patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.button("Save").invoke()
        self.root.update()
        self.assertEqual(self.item.identification_status, IdentificationStatus.PARTIAL)
        self.assertEqual(self.item.year, "")
        self.assertEqual(window.status_var.get(), "Saved. This task still needs attention.")
        self.gui.refresh_collection_list.assert_called_once()
        for path, data in self.bytes.items():
            self.assertEqual(path.read_bytes(), data)

    def test_stale_reference_and_save_failure_keep_editor_open(self):
        self.open_editor()
        before = copy.deepcopy(vars(self.item))
        with patch("coin_collection.write_json_atomically", side_effect=OSError("synthetic write failure")), patch("coin_collection_gui.messagebox.showerror") as error:
            self.button("Save").invoke()
            self.assertTrue(error.called)
        self.assertEqual(vars(self.item), before)
        self.assertTrue(self.dialog.winfo_exists())
        self.collection.items = [copy.deepcopy(self.item)]
        with patch("coin_collection_gui.messagebox.showerror") as error:
            self.button("Save").invoke()
            self.assertTrue(error.called)
        self.assertTrue(self.dialog.winfo_exists())
        self.gui.refresh_collection_list.assert_not_called()


class Phase1CMultiPhotoGuiTests(unittest.TestCase):
    def make_item(self, image_path="", photos=None):
        return CoinItem(
            id="TEST-1",
            image_path=image_path,
            country="Canada",
            denomination="Cent",
            year="1920",
            grade="VF-20",
            notes="test item",
            date_added=datetime.now().isoformat(),
            photos=photos or [],
        )

    def test_multi_file_selection_state_assigns_roles_and_primary(self):
        photos, skipped = CoinCollectionGUI.add_photo_paths_to_list([], ["front.jpg", "back.jpg", "detail.jpg"])

        self.assertEqual([], skipped)
        self.assertEqual(["front.jpg", "back.jpg", "detail.jpg"], [photo.path for photo in photos])
        self.assertEqual([PhotoRole.FRONT, PhotoRole.BACK, PhotoRole.OTHER], [photo.role for photo in photos])
        self.assertEqual([True, False, False], [photo.is_primary for photo in photos])

    def test_duplicate_selection_handling_skips_existing_reference(self):
        photos, skipped = CoinCollectionGUI.add_photo_paths_to_list([], ["front.jpg", "front.jpg"])

        self.assertEqual(1, len(photos))
        self.assertEqual(["front.jpg"], skipped)

    def test_legacy_one_image_edit_flow_loads_synthesized_photo(self):
        item = self.make_item(image_path="legacy.jpg")

        photos = CoinCollectionGUI.photos_from_item(item)

        self.assertEqual(1, len(photos))
        self.assertEqual("legacy.jpg", photos[0].path)
        self.assertTrue(photos[0].is_primary)

    def test_photos_load_into_edit_form_with_roles(self):
        item = self.make_item(photos=[
            ItemPhoto("front.jpg", role=PhotoRole.FRONT, is_primary=True),
            ItemPhoto("back.jpg", role=PhotoRole.BACK),
        ])

        photos = CoinCollectionGUI.photos_from_item(item)

        self.assertEqual([PhotoRole.FRONT, PhotoRole.BACK], [photo.role for photo in photos])

    def test_primary_selection_produces_exactly_one_primary(self):
        photos = [ItemPhoto("front.jpg", is_primary=True), ItemPhoto("back.jpg")]

        updated = CoinCollectionGUI.set_primary_photo_at_index(photos, 1)

        self.assertEqual([False, True], [photo.is_primary for photo in updated])

    def test_no_primary_normalization_selects_first_photo(self):
        photos = [ItemPhoto("front.jpg"), ItemPhoto("back.jpg")]

        updated = CoinCollectionGUI.normalized_photo_state(photos)

        self.assertEqual([True, False], [photo.is_primary for photo in updated])

    def test_multiple_primary_normalization_keeps_first_primary(self):
        photos = [ItemPhoto("front.jpg", is_primary=True), ItemPhoto("back.jpg", is_primary=True)]

        updated = CoinCollectionGUI.normalized_photo_state(photos)

        self.assertEqual([True, False], [photo.is_primary for photo in updated])

    def test_remove_reference_without_deleting_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "front.jpg")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("not an image")

            updated = CoinCollectionGUI.remove_photo_at_index([ItemPhoto(path, is_primary=True)], 0)

            self.assertEqual([], updated)
            self.assertTrue(os.path.exists(path))

    def test_reorder_photos_updates_display_order_without_changing_primary(self):
        photos = [ItemPhoto("front.jpg", is_primary=True), ItemPhoto("back.jpg")]

        updated, selected = CoinCollectionGUI.move_photo_at_index(photos, 1, -1)

        self.assertEqual(0, selected)
        self.assertEqual(["back.jpg", "front.jpg"], [photo.path for photo in updated])
        self.assertEqual([False, True], [photo.is_primary for photo in updated])
        self.assertEqual([0, 1], [photo.display_order for photo in updated])

    def test_relabel_photo_roles_normalizes_unknown_to_other(self):
        updated = CoinCollectionGUI.update_photo_role_at_index([ItemPhoto("front.jpg")], 0, "mystery role")

        self.assertEqual(PhotoRole.OTHER, updated[0].role)

    def test_missing_file_degraded_display_keeps_metadata(self):
        photo = ItemPhoto("missing-file.jpg", is_primary=True)

        self.assertEqual("Image file not found", CoinCollectionGUI.photo_preview_status(photo))
        self.assertEqual("missing-file.jpg", CoinCollectionGUI.photo_detail_rows([photo])[0]["path"])

    def test_clear_form_photo_state_helper_normalizes_empty_state(self):
        self.assertEqual([], CoinCollectionGUI.normalized_photo_state([]))

    def test_save_round_trip_preserves_photos_and_primary_alias(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            collection = CoinCollection(os.path.join(tmpdir, "collection.json"))
            app = CoinCollectionApp(collection=collection)
            app.current_image_path = "front.jpg"
            photos = [
                ItemPhoto("front.jpg", role=PhotoRole.FRONT),
                ItemPhoto("back.jpg", role=PhotoRole.BACK, is_primary=True),
            ]

            self.assertTrue(app.add_to_collection("Canada", "Cent", "1920", "VF-20", "notes", photos=photos))
            saved = app.collection.get_all_items()[0]

            self.assertEqual("back.jpg", saved.image_path)
            self.assertEqual(["front.jpg", "back.jpg"], [photo.path for photo in saved.normalized_photos()])

    def test_edit_round_trip_updates_item_photos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            collection = CoinCollection(os.path.join(tmpdir, "collection.json"))
            item = self.make_item(image_path="front.jpg")
            collection.add_item(item)
            photos = CoinCollectionGUI.set_primary_photo_at_index([
                ItemPhoto("front.jpg", role=PhotoRole.FRONT),
                ItemPhoto("back.jpg", role=PhotoRole.BACK),
            ], 1)

            self.assertTrue(collection.update_item(item.id, {"photos": photos, "image_path": "back.jpg"}))
            updated = collection.get_item(item.id)

            self.assertEqual("back.jpg", updated.primary_image_path)
            self.assertEqual([False, True], [photo.is_primary for photo in updated.normalized_photos()])

    def test_item_details_gallery_text_includes_all_photos(self):
        item = self.make_item(photos=[
            ItemPhoto("front.jpg", role=PhotoRole.FRONT, is_primary=True, notes="obverse"),
            ItemPhoto("back.jpg", role=PhotoRole.BACK),
        ])

        details = CoinCollectionGUI.item_details_text(item)

        self.assertIn("Primary: FRONT - front.jpg", details)
        self.assertIn("Photo: BACK - back.jpg", details)
        self.assertIn("Photo Notes: obverse", details)

    def test_primary_image_remains_collection_list_alias(self):
        item = self.make_item(photos=[
            ItemPhoto("front.jpg", role=PhotoRole.FRONT),
            ItemPhoto("back.jpg", role=PhotoRole.BACK, is_primary=True),
        ])

        item.sync_image_path_from_primary()

        self.assertEqual("back.jpg", item.image_path)


if __name__ == "__main__":
    unittest.main()
