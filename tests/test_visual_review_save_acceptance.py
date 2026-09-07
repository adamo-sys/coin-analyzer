"""Offline acceptance journeys across visual review and ordinary persistence."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from capture_import.desktop_visual_identity_review import ConfirmedVisualIdentity
from capture_import.image_store import ManagedCollectionImageStore
from capture_import.reviewed_coin_collection_entry import persist_reviewed_coin
from capture_import.snapshot import CapturePackageSnapshotService
from capture_import.standalone_image_intake import TemporaryCapturePackage
from capture_import.visual_identity_provider import VisualIdentityCandidate, VisualIdentityReport
from coin_collection import CoinCollection, CoinItem
from coin_collection_gui import CoinCollectionGUI


def _files(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


class VisualReviewSaveAcceptanceTests(unittest.TestCase):
    """Only provider answers and native UI are replaced; persistence stays real."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.storage = self.root / "collection.json"
        self.managed = self.root / "managed"
        self.managed.mkdir()
        # An unrelated owned asset must survive failed transaction cleanup.
        Image.new("RGB", (8, 8), "green").save(self.managed / "retained.png")
        self.front, self.reverse = self.root / "front.jpg", self.root / "reverse.png"
        Image.new("RGB", (24, 16), "red").save(self.front)
        Image.new("RGB", (16, 24), "blue").save(self.reverse)
        self.source_bytes = [self.front.read_bytes(), self.reverse.read_bytes()]
        self.collection = CoinCollection(str(self.storage))
        self.ui_thread = threading.get_ident()
        self.gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        self.gui.root = Mock()
        self.gui._create_visual_identification_wait = Mock(return_value=Mock())
        self.gui.app = SimpleNamespace(collection=self.collection)
        self.gui.capture_import_ready = True
        self.gui.refresh_collection_list = Mock()
        self.gui._visual_identity_provider = None
        self.store = ManagedCollectionImageStore(self.managed, collection_path_prefix="managed")

    def _seed(self):
        self.assertTrue(self.collection.add_item(CoinItem(
            id="seed", image_path="", country="Canada", denomination="25 cents",
            year="1967", grade="", notes="synthetic", date_added="2026-01-01",
        )))

    def _journey(self, *, expected_save, before_confirm=lambda: None):
        self.gui.refresh_collection_list.reset_mock()
        original_items = deepcopy(self.collection.items)
        managed_before = _files(self.managed)
        released = []
        requests = []
        provider_threads = []
        reviewed = []
        storage_at_confirmation = []
        original_release = TemporaryCapturePackage.release

        def release(source):
            released.append(source.path)
            original_release(source)

        def identify(request):
            provider_threads.append(threading.get_ident())
            requests.append(request)
            return VisualIdentityReport(
                outcome="CANDIDATES",
                candidates=(VisualIdentityCandidate(
                    rank=1, country="United States", denomination="Half Dollar",
                    year="1964", type_design="synthetic proposal", confidence=0.5,
                    evidence_observations=("Synthetic answer; no recognition performed",),
                    supporting_image_roles=("obverse", "reverse"),
                    provider_id="synthetic", model_id="offline",
                ),),
                provider_id="synthetic", model_id="offline", response_id="synthetic-only",
                input_tokens=None, output_tokens=None, raw_structured_result={},
            )

        self.gui._visual_identity_provider = SimpleNamespace(identify=identify)

        def persist(**kwargs):
            return persist_reviewed_coin(
                **kwargs, managed_image_store=self.store,
                snapshot_service=CapturePackageSnapshotService(self.root / "snapshots"),
                import_lock_path=self.root / "imports" / "package_import.lock",
                item_id="12345678-1234-4234-8234-123456789abc", date_added="2026-01-01",
            )

        def confirm(**kwargs):
            self.assertEqual(threading.get_ident(), self.ui_thread)
            self.assertEqual(self.collection.items, original_items)
            self.assertEqual(_files(self.managed), managed_before)
            before_confirm()
            storage_at_confirmation.append(
                self.storage.read_bytes() if self.storage.exists() else None
            )
            reviewed.append(kwargs["proposal"])
            # Deliberately differs from the synthetic provider answer.
            kwargs["on_confirm"](ConfirmedVisualIdentity(
                "Canada", "25 cents", "1967", "operator correction"
            ))
            return object()

        with (
            patch("coin_collection_gui.messagebox.askyesno", return_value=True) as ask,
            patch("coin_collection_gui.messagebox.showerror") as error,
            patch("coin_collection_gui.messagebox.showwarning") as warning,
            patch("coin_collection_gui.messagebox.showinfo") as info,
            patch("capture_import.desktop_visual_identity_review.create_visual_identity_review_dialog",
                  side_effect=confirm) as dialog,
            patch("capture_import.reviewed_coin_collection_entry.persist_reviewed_coin",
                  side_effect=persist) as persistence,
            patch.object(self.store, "copy", wraps=self.store.copy) as copy,
            patch.object(TemporaryCapturePackage, "release", autospec=True, side_effect=release),
        ):
            self.gui.import_coin_images_with_visual_ai(str(self.front), str(self.reverse))
            task = self.gui._visual_identification_task
            task.worker.join(5)  # Timeout guards a hang; no timing-based outcome.
            self.assertFalse(task.worker.is_alive(), "visual worker failed to complete")
            dialog.assert_not_called()
            persistence.assert_not_called()
            self.gui.root.after.call_args.args[1]()
            dialog.assert_called_once()
            persistence.assert_called_once()
            copy.assert_called_once()  # Exercise actual image cleanup after a stale rejection.
            warning.assert_not_called()
            self.assertEqual(ask.call_count, 2, "upload and save both require consent")
            self.assertIn("OpenAI", ask.call_args_list[0].args[0])
            if expected_save:
                error.assert_not_called()
                info.assert_called_once()
                self.assertEqual(info.call_args.args[0], "AI-Reviewed Coin Saved")
                self.gui.refresh_collection_list.assert_called_once()
            else:
                info.assert_not_called()
                self.gui.refresh_collection_list.assert_not_called()
                error.assert_called_once()
                self.assertEqual(error.call_args.args[0], "Collection Save Failed")
                message = error.call_args.args[1]
                for required in ("changed outside this window", "not saved", "Reload"):
                    self.assertIn(required, message)
                current = self.storage.read_bytes() if self.storage.exists() else None
                self.assertEqual(current, storage_at_confirmation[0], "newer storage changed")
                self.assertEqual(self.collection.items, original_items, "memory rollback failed")
                self.assertEqual(_files(self.managed), managed_before, "orphaned or removed photos")

        self.assertEqual(len(reviewed), 1)
        self.assertEqual(len(requests), 1)
        self.assertNotEqual(provider_threads[0], self.ui_thread)
        self.assertEqual([image.data for image in requests[0].images], self.source_bytes)
        self.assertEqual(len(released), 1, "temporary source must be released exactly once")
        self.assertFalse(released[0].parent.exists(), "temporary capture source leaked")
        self.assertEqual([self.front.read_bytes(), self.reverse.read_bytes()], self.source_bytes)
        self.assertFalse(any(path.is_file() for path in (self.root / "snapshots").rglob("*")))
        if expected_save:
            reopened = CoinCollection(str(self.storage))
            saved = reopened.get_item("12345678-1234-4234-8234-123456789abc")
            self.assertIsNotNone(saved)
            self.assertEqual((saved.country, saved.denomination, saved.year),
                             ("Canada", "25 cents", "1967"))
            self.assertEqual(len(saved.photos), 2)
            self.assertEqual([(self.root / photo.path).read_bytes()
                              for photo in saved.photos],
                             self.source_bytes)
            self.assertEqual({row.id for row in reopened.items},
                             {row.id for row in original_items} | {"12345678-1234-4234-8234-123456789abc"})
            for name, payload in managed_before.items():
                self.assertEqual((self.managed / name).read_bytes(), payload)
            self.assertNotIn("synthetic-only", self.storage.read_text("utf-8"))

    def test_unchanged_storage_saves_corrected_identity_and_photos_across_restart(self):
        self._seed()
        self._journey(expected_save=True)

    def test_competing_save_rolls_back_photos_until_explicit_reload_and_retry(self):
        self._seed()
        other = CoinCollection(str(self.storage))

        def external_save():
            self.assertTrue(other.update_item("seed", {"notes": "other window saved"}))

        self._journey(expected_save=False, before_confirm=external_save)
        self._journey(expected_save=False)  # Failed save must not adopt the newer baseline.
        self.collection.load_collection()
        self._journey(expected_save=True)
        self.assertEqual(CoinCollection(str(self.storage)).get_item("seed").notes,
                         "other window saved")

    def test_storage_appearing_during_first_run_review_requires_reload(self):
        def external_save():
            self.assertTrue(CoinCollection(str(self.storage)).save_collection())

        self._journey(expected_save=False, before_confirm=external_save)
        self.collection.load_collection()
        self._journey(expected_save=True)

    def test_storage_disappearing_during_review_is_not_recreated_without_reload(self):
        self._seed()
        self._journey(expected_save=False, before_confirm=self.storage.unlink)
        self.assertFalse(self.storage.exists())
        self.collection.load_collection()
        self._journey(expected_save=True)


if __name__ == "__main__":
    unittest.main()
