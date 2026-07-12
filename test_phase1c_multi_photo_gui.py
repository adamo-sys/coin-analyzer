import os
import tempfile
import unittest
from datetime import datetime

from coin_collection import CoinCollection, CoinCollectionApp, CoinItem, ItemPhoto, PhotoRole
from coin_collection_gui import CoinCollectionGUI


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
            app = CoinCollectionApp()
            app.collection = CoinCollection(os.path.join(tmpdir, "collection.json"))
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
