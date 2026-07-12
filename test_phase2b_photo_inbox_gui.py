import os
import tempfile
import unittest
from datetime import datetime, timedelta

from coin_collection_gui import CoinCollectionGUI
from photo_inbox import PhotoInboxConfig, PhotoInboxManager, PhotoSetState


class FixedClock:
    def __init__(self):
        self.current = datetime(2026, 7, 12, 9, 0, 0)

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)


class Phase2BPhotoInboxGuiTests(unittest.TestCase):
    def make_manager(self, tmpdir):
        inbox = os.path.join(tmpdir, "incoming")
        os.makedirs(inbox, exist_ok=True)
        clock = FixedClock()
        config = PhotoInboxConfig(
            inbox_folder=inbox,
            state_path=os.path.join(tmpdir, "photo_inbox_state.json"),
            file_stability_seconds=0,
            grouping_window_seconds=90,
        )
        return PhotoInboxManager(config=config, now_fn=clock)

    def write_photo(self, manager, name):
        folder = manager.config.inbox_folder
        path = os.path.join(folder, name)
        with open(path, "wb") as handle:
            handle.write(b"photo")
        timestamp = (manager.now_fn() - timedelta(minutes=5)).timestamp()
        os.utime(path, (timestamp, timestamp))
        return path

    def test_photo_inbox_set_rows_show_pending_sets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = self.make_manager(tmpdir)
            self.write_photo(manager, "coin_front.jpg")
            self.write_photo(manager, "coin_back.jpg")
            manager.scan()

            rows = CoinCollectionGUI.photo_inbox_set_rows(manager)

            self.assertEqual(1, len(rows))
            self.assertEqual("NEW", rows[0]["state"])
            self.assertEqual(2, rows[0]["photo_count"])
            self.assertIn("coin_", rows[0]["suggested_label"])

    def test_photo_inbox_photo_rows_show_selected_set_photos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = self.make_manager(tmpdir)
            front = self.write_photo(manager, "coin_front.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id

            rows = CoinCollectionGUI.photo_inbox_photo_rows(manager, photo_set_id)

            self.assertEqual(1, len(rows))
            self.assertEqual("ASSIGNED", rows[0]["state"])
            self.assertEqual("coin_front.jpg", rows[0]["filename"])
            self.assertEqual(os.path.abspath(front), rows[0]["path"])

    def test_photo_inbox_scan_summary_is_collector_readable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = self.make_manager(tmpdir)
            self.write_photo(manager, "coin_front.jpg")

            scan_result = manager.scan()
            summary = CoinCollectionGUI.photo_inbox_scan_summary(scan_result, len(manager.get_pending_sets()))

            self.assertIn("Pending sets: 1", summary)
            self.assertIn("Discovered: 1", summary)
            self.assertIn("Stabilizing: 0", summary)

    def test_defer_and_ignore_remain_backend_state_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = self.make_manager(tmpdir)
            self.write_photo(manager, "coin_front.jpg")
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id

            self.assertTrue(manager.mark_deferred(photo_set_id))
            self.assertEqual(PhotoSetState.DEFERRED, manager.state.photo_sets[photo_set_id].state)
            self.assertEqual(1, len(CoinCollectionGUI.photo_inbox_set_rows(manager)))

            self.assertTrue(manager.mark_ignored(photo_set_id))
            self.assertEqual([], CoinCollectionGUI.photo_inbox_set_rows(manager))


if __name__ == "__main__":
    unittest.main()
