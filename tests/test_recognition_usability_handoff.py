from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import tkinter as tk

from coin_collection import ItemPhoto, PhotoRole
from coin_collection_gui import CoinCollectionGUI


class RecognitionUsabilityHandoffTests(unittest.TestCase):
    def test_incomplete_success_needs_paired_review(self):
        self.assertTrue(
            CoinCollectionGUI.recognition_result_needs_paired_review(
                {
                    "success": True,
                    "country": "unknown",
                    "denomination": "penny",
                    "year": "1859",
                }
            )
        )

    def test_complete_or_failed_result_does_not_need_paired_review(self):
        self.assertFalse(
            CoinCollectionGUI.recognition_result_needs_paired_review(
                {
                    "success": True,
                    "country": "Canada",
                    "denomination": "penny",
                    "year": "1859",
                }
            )
        )
        self.assertFalse(
            CoinCollectionGUI.recognition_result_needs_paired_review(
                {"success": False, "error": "Detection failed"}
            )
        )

    def test_pair_requires_explicit_front_and_back_roles(self):
        photos = [
            ItemPhoto("reverse.jpg", role=PhotoRole.BACK),
            ItemPhoto("obverse.jpg", role=PhotoRole.FRONT, is_primary=True),
        ]
        self.assertEqual(
            ("obverse.jpg", "reverse.jpg"),
            CoinCollectionGUI.paired_visual_review_paths(photos),
        )
        self.assertIsNone(
            CoinCollectionGUI.paired_visual_review_paths(
                [ItemPhoto("coin.jpg", role=PhotoRole.OTHER, is_primary=True)]
            )
        )

    def test_incomplete_detection_enables_handoff_for_attached_pair(self):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.app = SimpleNamespace(
            current_image_path="obverse.jpg",
            run_denomination_detector=Mock(
                return_value={
                    "success": True,
                    "country": "unknown",
                    "denomination": "penny",
                    "year": "1859",
                    "confidence": 1.0,
                    "year_confidence": 0.5,
                }
            ),
        )
        gui.current_item_photos = [
            ItemPhoto("obverse.jpg", role=PhotoRole.FRONT, is_primary=True),
            ItemPhoto("reverse.jpg", role=PhotoRole.BACK),
        ]
        gui.detection_label = Mock()
        gui.confidence_label = Mock()
        gui.visual_review_handoff_button = Mock()
        gui.log_detection = Mock()

        gui.run_detection()

        displayed = gui.detection_label.config.call_args.kwargs["text"]
        self.assertIn("Local evidence is incomplete", displayed)
        gui.visual_review_handoff_button.config.assert_called_with(state=tk.NORMAL)
        gui.log_detection.assert_called_once()

    def test_review_action_reuses_attached_paths_without_invoking_provider_itself(self):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.current_item_photos = [
            ItemPhoto("obverse.jpg", role=PhotoRole.FRONT, is_primary=True),
            ItemPhoto("reverse.jpg", role=PhotoRole.BACK),
        ]
        gui.import_coin_images_with_visual_ai = Mock()

        gui.review_attached_photos_with_visual_ai()

        gui.import_coin_images_with_visual_ai.assert_called_once_with(
            front_path="obverse.jpg",
            reverse_path="reverse.jpg",
        )

    def test_missing_pair_fails_closed(self):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = object()
        gui.current_item_photos = [
            ItemPhoto("obverse.jpg", role=PhotoRole.FRONT, is_primary=True)
        ]
        gui.visual_review_handoff_button = Mock()
        gui.import_coin_images_with_visual_ai = Mock()

        with patch("coin_collection_gui.messagebox.showwarning") as warning:
            gui.review_attached_photos_with_visual_ai()

        gui.import_coin_images_with_visual_ai.assert_not_called()
        gui.visual_review_handoff_button.config.assert_called_with(state=tk.DISABLED)
        warning.assert_called_once()

    def test_photo_refresh_disables_stale_handoff_when_pair_is_removed(self):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.current_item_photos = [
            ItemPhoto("obverse.jpg", role=PhotoRole.FRONT, is_primary=True)
        ]
        gui.selected_photo_index = 0
        gui.detection_result = {
            "success": True,
            "country": "unknown",
            "denomination": "penny",
            "year": "1859",
        }
        gui.photo_tree = Mock()
        gui.photo_tree.get_children.return_value = []
        gui.visual_review_handoff_button = Mock()

        gui.refresh_photo_list()

        gui.visual_review_handoff_button.config.assert_called_with(state=tk.DISABLED)


if __name__ == "__main__":
    unittest.main()
