import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta

from photo_inbox import (
    InboxPhotoState,
    PhotoInboxConfig,
    PhotoInboxManager,
    PhotoSetState,
    REFERENCE_IN_PLACE,
)


class FixedClock:
    def __init__(self, start=None):
        self.current = start or datetime(2026, 7, 11, 12, 0, 0)

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)


class PhotoInboxManagerTests(unittest.TestCase):
    def make_manager(self, tmpdir, clock=None, stability=0, grouping=90):
        inbox = os.path.join(tmpdir, "incoming")
        state_path = os.path.join(tmpdir, "state.json")
        os.makedirs(inbox, exist_ok=True)
        config = PhotoInboxConfig(
            inbox_folder=inbox,
            state_path=state_path,
            file_stability_seconds=stability,
            grouping_window_seconds=grouping,
        )
        return PhotoInboxManager(config=config, now_fn=clock or FixedClock())

    def write_photo(self, folder, name, content=b"photo", modified_at=None):
        path = os.path.join(folder, name)
        with open(path, "wb") as handle:
            handle.write(content)
        if modified_at is not None:
            timestamp = modified_at.timestamp()
            os.utime(path, (timestamp, timestamp))
        return path

    def test_empty_inbox_returns_no_pending_sets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = self.make_manager(tmpdir)

            result = manager.scan()

            self.assertEqual(0, result.discovered)
            self.assertEqual([], manager.get_pending_sets())

    def test_one_photo_creates_one_pending_photo_set(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            manager = self.make_manager(tmpdir, clock=clock)
            self.write_photo(manager.config.inbox_folder, "front.jpg", modified_at=clock.current - timedelta(minutes=5))

            result = manager.scan()
            pending = manager.get_pending_sets()

            self.assertEqual(1, result.discovered)
            self.assertEqual(1, len(pending))
            self.assertEqual(PhotoSetState.NEW, pending[0].state)
            self.assertEqual(1, len(manager.get_photo_set_photos(pending[0].id)))

    def test_multiple_photos_group_within_time_window(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            manager = self.make_manager(tmpdir, clock=clock, grouping=90)
            self.write_photo(manager.config.inbox_folder, "coin_front.jpg", modified_at=clock.current - timedelta(minutes=5))
            self.write_photo(manager.config.inbox_folder, "coin_back.jpg", modified_at=clock.current - timedelta(minutes=5))

            manager.scan()
            pending = manager.get_pending_sets()

            self.assertEqual(1, len(pending))
            self.assertEqual(2, len(pending[0].photo_ids))

    def test_deterministic_grouping_repeats_identical_photo_sets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            manager = self.make_manager(tmpdir, clock=clock)
            self.write_photo(manager.config.inbox_folder, "front.jpg", modified_at=clock.current - timedelta(minutes=5))
            self.write_photo(manager.config.inbox_folder, "back.jpg", modified_at=clock.current - timedelta(minutes=5))

            manager.scan()
            first_ids = [photo_set.id for photo_set in manager.get_pending_sets()]
            clock.advance(60)
            manager.scan()
            second_ids = [photo_set.id for photo_set in manager.get_pending_sets()]

            self.assertEqual(first_ids, second_ids)

    def test_duplicate_prevention_repeated_scan_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            manager = self.make_manager(tmpdir, clock=clock)
            self.write_photo(manager.config.inbox_folder, "front.jpg", modified_at=clock.current - timedelta(minutes=5))

            first = manager.scan()
            second = manager.scan()

            self.assertEqual(1, first.discovered)
            self.assertEqual(0, second.discovered)
            self.assertEqual(1, len(manager.state.photos))
            self.assertEqual(1, len(manager.state.photo_sets))

    def test_configurable_folder_is_used(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            custom = os.path.join(tmpdir, "custom_inbox")
            os.makedirs(custom, exist_ok=True)
            config = PhotoInboxConfig(
                inbox_folder=custom,
                state_path=os.path.join(tmpdir, "state.json"),
                file_stability_seconds=0,
            )
            manager = PhotoInboxManager(config=config, now_fn=clock)
            self.write_photo(custom, "custom.png", modified_at=clock.current - timedelta(minutes=5))

            manager.scan()

            self.assertEqual(custom, manager.config.inbox_folder)
            self.assertEqual(1, len(manager.get_pending_sets()))

    def test_unsupported_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = self.make_manager(tmpdir)
            self.write_photo(manager.config.inbox_folder, "notes.txt", content=b"not a photo")

            result = manager.scan()

            self.assertEqual(1, result.unsupported)
            self.assertEqual(0, len(manager.state.photos))

    def test_partial_file_remains_stabilizing_until_stable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            manager = self.make_manager(tmpdir, clock=clock, stability=30)
            self.write_photo(manager.config.inbox_folder, "syncing.jpg", modified_at=clock.current)

            first = manager.scan()
            pending_after_first_scan = manager.get_pending_sets()
            clock.advance(31)
            second = manager.scan()

            self.assertEqual(1, first.stabilizing)
            self.assertEqual(0, len(pending_after_first_scan))
            self.assertEqual(1, second.ready)
            self.assertEqual(1, len(manager.get_pending_sets()))

    def test_grouping_window_separates_unrelated_sets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            manager = self.make_manager(tmpdir, clock=clock, grouping=10)
            self.write_photo(manager.config.inbox_folder, "alpha_front.jpg", modified_at=clock.current - timedelta(minutes=5))
            manager.scan()
            clock.advance(20)
            self.write_photo(manager.config.inbox_folder, "beta_front.jpg", modified_at=clock.current - timedelta(minutes=5))
            manager.scan()

            self.assertEqual(2, len(manager.get_pending_sets()))

    def test_filename_similarity_can_group_outside_time_window(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            manager = self.make_manager(tmpdir, clock=clock, grouping=1)
            self.write_photo(manager.config.inbox_folder, "lot42_front.jpg", modified_at=clock.current - timedelta(minutes=5))
            manager.scan()
            clock.advance(5)
            self.write_photo(manager.config.inbox_folder, "lot42_back.jpg", modified_at=clock.current - timedelta(minutes=5))
            manager.scan()

            pending = manager.get_pending_sets()
            self.assertEqual(1, len(pending))
            self.assertEqual(2, len(pending[0].photo_ids))

    def test_missing_files_are_marked_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            manager = self.make_manager(tmpdir, clock=clock)
            path = self.write_photo(manager.config.inbox_folder, "front.jpg", modified_at=clock.current - timedelta(minutes=5))
            manager.scan()
            os.remove(path)

            result = manager.scan()
            photo = next(iter(manager.state.photos.values()))

            self.assertEqual(1, result.missing)
            self.assertEqual(InboxPhotoState.MISSING, photo.state)

    def test_state_transitions_are_persisted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            manager = self.make_manager(tmpdir, clock=clock)
            self.write_photo(manager.config.inbox_folder, "front.jpg", modified_at=clock.current - timedelta(minutes=5))
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id

            self.assertTrue(manager.mark_processing(photo_set_id))
            self.assertTrue(manager.mark_deferred(photo_set_id))
            reloaded = PhotoInboxManager(config=manager.config, now_fn=clock)

            self.assertEqual(PhotoSetState.DEFERRED, reloaded.state.photo_sets[photo_set_id].state)
            self.assertEqual(1, len(reloaded.get_pending_sets()))

    def test_mark_ignored_removes_set_from_pending_without_deleting_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            manager = self.make_manager(tmpdir, clock=clock)
            path = self.write_photo(manager.config.inbox_folder, "front.jpg", modified_at=clock.current - timedelta(minutes=5))
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id

            self.assertTrue(manager.mark_ignored(photo_set_id))

            self.assertEqual([], manager.get_pending_sets())
            self.assertTrue(os.path.exists(path))

    def test_mark_attached_records_item_id_and_keeps_file_in_place(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            manager = self.make_manager(tmpdir, clock=clock)
            path = self.write_photo(manager.config.inbox_folder, "front.jpg", modified_at=clock.current - timedelta(minutes=5))
            manager.scan()
            photo_set_id = manager.get_pending_sets()[0].id

            self.assertTrue(manager.mark_attached(photo_set_id, item_id="coin-1"))
            photo_set = manager.state.photo_sets[photo_set_id]

            self.assertEqual(PhotoSetState.ATTACHED, photo_set.state)
            self.assertEqual("coin-1", photo_set.linked_item_id)
            self.assertTrue(os.path.exists(path))
            self.assertEqual(REFERENCE_IN_PLACE, manager.config.file_management_mode)

    def test_malformed_metadata_loads_gracefully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox = os.path.join(tmpdir, "incoming")
            os.makedirs(inbox, exist_ok=True)
            state_path = os.path.join(tmpdir, "state.json")
            with open(state_path, "w", encoding="utf-8") as handle:
                handle.write("{not-json")

            manager = PhotoInboxManager(
                config=PhotoInboxConfig(inbox_folder=inbox, state_path=state_path),
                now_fn=FixedClock(),
            )

            self.assertTrue(manager.state.errors)
            self.assertEqual([], manager.get_pending_sets())

    def test_state_file_contains_no_file_management_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clock = FixedClock()
            manager = self.make_manager(tmpdir, clock=clock)
            path = self.write_photo(manager.config.inbox_folder, "front.jpg", modified_at=clock.current - timedelta(minutes=5))

            manager.scan()
            with open(manager.config.state_path, "r", encoding="utf-8") as handle:
                state_text = handle.read()

            self.assertIn(os.path.basename(path), state_text)
            self.assertNotIn("copy", state_text.lower())
            self.assertNotIn("move", state_text.lower())
            self.assertNotIn("delete", state_text.lower())


if __name__ == "__main__":
    unittest.main()
