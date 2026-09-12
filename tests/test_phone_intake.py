"""Offline Phone Intake contracts using synthetic images and real persistence."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from phone_drop_import import PhoneDropImporter
from phone_intake import PhoneIntake, PhoneIntakeError
from coin_collection import CoinCollection
from coin_collection_gui import CoinCollectionGUI
from capture_import.desktop_visual_identity_review import ConfirmedVisualIdentity, create_visual_identity_proposal
from capture_import.reviewed_coin_collection_entry import ReviewedCoinDraft, persist_reviewed_coin, ReviewedCoinPersistenceError, ReviewedCoinRecoveryRequiredError
from capture_import.standalone_image_intake import create_temporary_capture_package
from capture_import.visual_identity_provider import VisualIdentityCandidate, VisualIdentityReport


class PhoneIntakeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        cwd = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)
        self.photos = []
        for index, color in enumerate(('red', 'blue', 'green', 'yellow', 'purple', 'orange')):
            path = self.root / f'IMG_{9-index:04}.jpg'
            Image.new('RGB', (24, 24), color).save(path)
            self.photos.append(str(path))
        self.store = PhoneIntake(str(self.root / 'intake.json'))
        self.collection = CoinCollection(str(self.root / 'collection.json'))
        self.draft = ReviewedCoinDraft('source', 'Canada', '25 cents', '1967', type_design='Collector correction')

    def pair(self, indices=(0, 1)):
        return self.store.confirm_pair(*(self.photos[i] for i in indices))

    def save(self, pair_id):
        paths = self.store.review_paths(pair_id)
        source = create_temporary_capture_package(front_path=paths[0], reverse_path=paths[1])
        self.addCleanup(source.release)
        # Use the package source identity exactly as the production review does.
        import zipfile
        with zipfile.ZipFile(source.path) as archive:
            manifest = json.loads(archive.read('capture_package.json'))
        draft = ReviewedCoinDraft(manifest['coins'][0]['id'], 'Canada', '25 cents', '1967', type_design='Collector correction')
        intent = self.store.reserve(pair_id, self.collection.storage_path, draft)
        item = persist_reviewed_coin(collection=self.collection, draft=draft, source_package_path=source.path,
                                    item_id=intent['item_id'], date_added=intent['date_added'])
        return item

    def test_explicit_multi_coin_batch_retakes_orphans_order_restart_and_swap(self):
        first = self.pair((3, 0))
        second = self.pair((1, 4))
        self.store.swap(first)
        reopened = PhoneIntake(str(self.store.path))
        self.assertEqual(reopened.review_paths(first), (self.photos[0], self.photos[3]))
        self.assertEqual(reopened.review_paths(second), (self.photos[1], self.photos[4]))
        self.assertEqual(len(reopened.records()), 2)  # Retake/orphan never auto-paired.
        self.pair((2, 5))
        self.assertEqual(reopened.review_paths(first), (self.photos[0], self.photos[3]))

    def test_same_image_and_image_reuse_rejected(self):
        with self.assertRaises(PhoneIntakeError):
            self.pair((0, 0))
        self.pair()
        with self.assertRaises(PhoneIntakeError):
            self.pair((0, 3))

    def test_changed_image_blocks_review(self):
        pair_id = self.pair()
        Path(self.photos[0]).write_bytes(Path(self.photos[2]).read_bytes())
        with self.assertRaises(PhoneIntakeError):
            self.store.review_paths(pair_id)

    def test_renamed_duplicate_content_and_different_content_same_name(self):
        inbox = self.root / 'inbox'
        importer = PhoneDropImporter(str(inbox))
        first = importer.import_files(self.photos[:2])
        renamed = self.root / 'renamed.jpg'
        renamed.write_bytes(Path(self.photos[0]).read_bytes())
        second = importer.import_files([str(renamed)])
        self.assertEqual((first.copied_count, second.copied_count, second.duplicate_count), (2, 0, 1))
        self.assertEqual(second.duplicates[0].destination_path, first.imported[0].destination_path)
        renamed.write_bytes(Path(self.photos[2]).read_bytes())
        self.assertEqual(importer.import_files([str(renamed)]).copied_count, 1)

    def test_failed_copy_does_not_publish_partial_image_and_other_imports_survive(self):
        importer = PhoneDropImporter(str(self.root / 'inbox'))
        import shutil
        copy = shutil.copy2
        def copying(source, destination):
            if source == self.photos[0]:
                Path(destination).write_bytes(b'partial')
                raise OSError('incomplete download')
            return copy(source, destination)
        with patch('phone_drop_import.shutil.copy2', side_effect=copying):
            result = importer.import_files(self.photos[:2])
        self.assertEqual((result.copied_count, result.rejected_count), (1, 1))
        self.assertEqual(len(list((self.root / 'inbox').iterdir())), 1)

    def test_save_completion_reopen_and_other_pair_unchanged(self):
        pair_id, other = self.pair(), self.pair((2, 3))
        item = self.save(pair_id)
        self.assertEqual(self.store.complete(pair_id, self.collection.storage_path), item.id)
        reopened = PhoneIntake(str(self.store.path))
        self.assertEqual(reopened.records()[pair_id]['state'], 'SAVED')
        self.assertEqual(reopened.records()[other]['state'], 'READY')
        saved = CoinCollection(self.collection.storage_path).get_item(item.id)
        assert saved is not None
        self.assertEqual(saved.type_design, 'Collector correction')
        self.assertEqual(len(saved.photos), 2)
        with self.assertRaises(PhoneIntakeError):
            reopened.reserve(pair_id, self.collection.storage_path, self.draft)

    def test_completion_failure_recovery_never_resaves(self):
        pair_id = self.pair()
        item = self.save(pair_id)
        before = Path(self.collection.storage_path).read_bytes()
        with patch('phone_intake.write_json_atomically', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.store.complete(pair_id, self.collection.storage_path)
        reopened = PhoneIntake(str(self.store.path))
        self.assertEqual(reopened.records()[pair_id]['state'], 'SAVING')
        with self.assertRaises(PhoneIntakeError):
            reopened.review_paths(pair_id)
        self.assertEqual(reopened.complete(pair_id, self.collection.storage_path), item.id)
        self.assertEqual(reopened.complete(pair_id, self.collection.storage_path), item.id)
        self.assertEqual(Path(self.collection.storage_path).read_bytes(), before)
        self.assertEqual(len(CoinCollection(self.collection.storage_path).items), 1)

    def test_mpo_reconciliation_uses_canonical_media_and_checks_source_integrity(self):
        from hashlib import sha256

        front = Path(self.photos[0])
        first = Image.new("RGB", (64, 48), "red")
        second = Image.new("RGB", (64, 48), "blue")
        first.save(front, format="MPO", save_all=True, append_images=[second])

        original = front.read_bytes()
        pair_id = self.pair()
        item = self.save(pair_id)

        saved = CoinCollection(self.collection.storage_path).get_item(item.id)
        assert saved is not None
        saved_front = next(photo for photo in saved.photos if photo.role == "FRONT")
        saved_front_bytes = Path(saved_front.path).read_bytes()
        self.assertNotEqual(sha256(original).hexdigest(), sha256(saved_front_bytes).hexdigest())

        front.write_bytes(Path(self.photos[2]).read_bytes())
        with self.assertRaises(PhoneIntakeError):
            self.store.complete(pair_id, self.collection.storage_path)

        front.write_bytes(original)
        self.assertEqual(self.store.complete(pair_id, self.collection.storage_path), item.id)

    def test_unresolved_intent_wrong_collection_and_changed_record_fail_closed(self):
        pair_id = self.pair()
        self.store.reserve(pair_id, self.collection.storage_path, self.draft)
        with self.assertRaises(PhoneIntakeError):
            self.store.complete(pair_id, self.collection.storage_path)
        with self.assertRaises(PhoneIntakeError):
            self.store.complete(pair_id, str(self.root / 'other.json'))
        with self.assertRaises(PhoneIntakeError):
            self.store.reserve(pair_id, self.collection.storage_path, self.draft)

    def test_proven_clean_save_failure_releases_pair(self):
        pair_id = self.pair()
        self.store.reserve(pair_id, self.collection.storage_path, self.draft)
        self.store.clean_save_failure(pair_id, self.collection.storage_path)
        self.assertEqual(self.store.review_paths(pair_id), tuple(self.photos[:2]))

    def test_corrupt_intake_state_is_not_reset(self):
        self.pair()
        self.store.path.write_text('{broken')
        with self.assertRaises(PhoneIntakeError):
            self.pair((2, 3))
        self.assertEqual(self.store.path.read_text(), '{broken')

    @contextmanager
    def gui_review(self, pair_id):
        gui: Any = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = Mock()
        gui.app = SimpleNamespace(collection=self.collection)
        gui.refresh_collection_list = Mock()
        source = create_temporary_capture_package(front_path=self.photos[0], reverse_path=self.photos[1])
        self.addCleanup(source.release)
        from capture_import.desktop_visual_identity_review import create_visual_request_from_capture_package
        create_visual_request_from_capture_package(source.path)
        candidate = VisualIdentityCandidate(rank=1, country='Canada', denomination=None, year=None, type_design=None, evidence_observations=('Synthetic visible support',), supporting_image_roles=('obverse',), confidence=.99, provider_id='fixture', model_id='offline')
        report = VisualIdentityReport(outcome='CANDIDATES', candidates=(candidate,), provider_id='fixture', model_id='offline',
                                      response_id='fixture', input_tokens=None, output_tokens=None, raw_structured_result={})
        # Provider reports retain source request identity through proposal construction.
        proposal = create_visual_identity_proposal(report)
        gui._visual_review_proposal = proposal
        gui._visual_review_source = source
        gui._phone_intake_context = (self.store, pair_id, self.collection.storage_path, tuple(self.photos[:2]))
        with patch('coin_collection_gui.messagebox.askyesno', return_value=True) as ask, \
             patch('coin_collection_gui.messagebox.showinfo') as info, \
             patch('coin_collection_gui.messagebox.showwarning') as warning, \
             patch('coin_collection_gui.messagebox.showerror') as error:
            yield gui, ask, info, warning, error

    def test_cancel_defer_and_save_decline_leave_pair_available(self):
        pair_id = self.pair()
        for action in ('_reject_visual_review', '_defer_visual_review', 'decline'):
            with self.subTest(action=action):
                with self.gui_review(pair_id) as (gui, ask, info, warning, error):
                    if action == 'decline':
                        ask.return_value = False
                        gui._confirm_and_save_visual_review(ConfirmedVisualIdentity('Canada', '25 cents', '1967', 'Correction'))
                    else:
                        getattr(gui, action)()
                self.assertEqual(self.store.records()[pair_id]['state'], 'READY')
                self.assertFalse(Path(self.collection.storage_path).exists())

    def test_gui_clean_save_failure_and_uncertain_failure(self):
        pair_id = self.pair()
        for failure, expected in ((ReviewedCoinPersistenceError('not saved'), 'READY'), (ReviewedCoinRecoveryRequiredError(), 'SAVING')):
            with self.gui_review(pair_id) as (gui, ask, info, warning, error), patch(
                    'capture_import.reviewed_coin_collection_entry.persist_reviewed_coin', side_effect=failure) as persist:
                gui._confirm_and_save_visual_review(ConfirmedVisualIdentity('Canada', '25 cents', '1967', 'Correction'))
                persist.assert_called_once()
                error.assert_called_once()
            self.assertEqual(self.store.records()[pair_id]['state'], expected)

    def test_gui_success_completes_pair_and_uses_separate_save_confirmation(self):
        pair_id = self.pair()
        with self.gui_review(pair_id) as (gui, ask, info, warning, error):
            original = gui._visual_review_proposal.candidate
            gui._confirm_and_save_visual_review(ConfirmedVisualIdentity('Canada', '25 cents', '1967', 'Correction'))
            ask.assert_called_once()
            error.assert_not_called()
            warning.assert_not_called()
            self.assertIsNone(original.year)
            self.assertIsNone(original.type_design)
        self.assertEqual(self.store.records()[pair_id]['state'], 'SAVED')
        saved = CoinCollection(self.collection.storage_path).items[0]
        self.assertEqual(saved.type_design, 'Correction')
        self.assertEqual(len(saved.photos), 2)

    def test_gui_completion_failure_reports_saved_and_blocks_second_save_after_reopen(self):
        pair_id = self.pair()
        with self.gui_review(pair_id) as (gui, ask, info, warning, error), patch.object(self.store, 'complete', side_effect=OSError('state write failed')):
            gui._confirm_and_save_visual_review(ConfirmedVisualIdentity('Canada', '25 cents', '1967', 'Correction'))
            warning.assert_called_once()
            self.assertIn('Coin Saved', warning.call_args.args[0])
            error.assert_not_called()
        self.assertEqual(len(CoinCollection(self.collection.storage_path).items), 1)
        with self.gui_review(pair_id) as (gui, ask, info, warning, error), patch('capture_import.reviewed_coin_collection_entry.persist_reviewed_coin') as persist:
            gui._confirm_and_save_visual_review(ConfirmedVisualIdentity('Canada', '25 cents', '1967', 'Correction'))
            persist.assert_not_called()
            error.assert_called_once()
        PhoneIntake(str(self.store.path)).complete(pair_id, self.collection.storage_path)
        self.assertEqual(len(CoinCollection(self.collection.storage_path).items), 1)

    def test_gui_role_change_during_review_blocks_save(self):
        pair_id = self.pair()
        with self.gui_review(pair_id) as (gui, ask, info, warning, error), patch('capture_import.reviewed_coin_collection_entry.persist_reviewed_coin') as persist:
            self.store.swap(pair_id)
            gui._confirm_and_save_visual_review(ConfirmedVisualIdentity('Canada', '25 cents', '1967', 'Correction'))
            persist.assert_not_called()
            error.assert_called_once()

    def test_reservation_write_failure_prevents_persistence(self):
        pair_id = self.pair()
        with self.gui_review(pair_id) as (gui, ask, info, warning, error), patch('phone_intake.write_json_atomically', side_effect=OSError('disk full')), patch('capture_import.reviewed_coin_collection_entry.persist_reviewed_coin') as persist:
            gui._confirm_and_save_visual_review(ConfirmedVisualIdentity('Canada', '25 cents', '1967', 'Correction'))
            persist.assert_not_called()
            error.assert_called_once()
        self.assertEqual(self.store.records()[pair_id]['state'], 'READY')

    def test_replaced_saved_record_is_not_accepted_as_pair_completion(self):
        pair_id = self.pair()
        item = self.save(pair_id)
        self.collection.update_item(item.id, {'type_design': 'A different record'})
        with self.assertRaises(PhoneIntakeError):
            self.store.complete(pair_id, self.collection.storage_path)
        self.assertEqual(self.store.records()[pair_id]['state'], 'SAVING')

    def test_stale_collection_rolls_back_media_and_keeps_pair_ready(self):
        pair_id = self.pair()
        other = CoinCollection(self.collection.storage_path)
        self.assertTrue(other.save_collection())
        before = Path(self.collection.storage_path).read_bytes()
        with self.gui_review(pair_id) as (gui, ask, info, warning, error):
            gui._confirm_and_save_visual_review(ConfirmedVisualIdentity('Canada', '25 cents', '1967', 'Correction'))
            error.assert_called_once()
        self.assertEqual(self.store.records()[pair_id]['state'], 'READY')
        self.assertEqual(Path(self.collection.storage_path).read_bytes(), before)
        self.assertFalse(any(p.is_file() for p in (self.root / 'coin_photos/collection').rglob('*')))

    def test_native_pairing_widgets_display_roles_swap_and_handoff_without_provider(self):
        import tkinter as tk
        from tkinter import ttk
        from phone_intake_dialog import open_phone_intake
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        root.withdraw()
        self.addCleanup(root.destroy)
        imported = PhoneDropImporter().import_files(self.photos)
        gui = SimpleNamespace(root=root, app=SimpleNamespace(collection=self.collection), import_coin_images_with_visual_ai=Mock())
        with patch('socket.socket', side_effect=AssertionError('No network')), patch('phone_intake_dialog.messagebox.askyesno', return_value=True), patch('phone_intake_dialog.messagebox.showerror') as errors:
            window = open_phone_intake(gui)
            root.update()
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            widgets = list(descendants(window))
            buttons = {w.cget('text'): w for w in widgets if isinstance(w, ttk.Button)}
            files = next(w for w in widgets if isinstance(w, tk.Listbox))
            pairs = next(w for w in widgets if isinstance(w, ttk.Treeview))
            self.assertEqual(files.size(), 6)
            files.selection_set(0)
            buttons['Use as Front'].invoke()
            files.selection_clear(0, tk.END)
            files.selection_set(3)
            buttons['Use as Reverse'].invoke()
            buttons['Confirm Pair'].invoke()
            root.update()
            self.assertEqual(len(pairs.get_children()), 1)
            self.assertEqual(files.size(), 4)
            pair_id = pairs.selection()[0]
            store = PhoneIntake()
            before = store.review_paths(pair_id)
            buttons['Swap'].invoke()
            root.update()
            self.assertEqual(store.review_paths(pair_id), before[::-1])
            visible_labels = [str(w.cget('text')) for w in widgets if isinstance(w, ttk.Label)]
            self.assertTrue(any(text == 'Front\n' + Path(before[1]).name for text in visible_labels))
            self.assertTrue(any(text == 'Reverse\n' + Path(before[0]).name for text in visible_labels))
            buttons['Review Pair'].invoke()
            gui.import_coin_images_with_visual_ai.assert_called_once()
            self.assertEqual(gui.import_coin_images_with_visual_ai.call_args.kwargs['front_path'], before[1])
            self.assertEqual(len(imported.imported_paths), 6)
            errors.assert_not_called()

    def test_worker_handoff_preserves_pair_context_and_cancel_clears_it(self):
        pair_id = self.pair()
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled), self.gui_review(pair_id) as (gui, ask, info, warning, error):
                source = gui._visual_review_source
                context = gui._phone_intake_context
                gui._visual_review_source = None
                gui.capture_import_ready = True
                gui._finish_visual_identification = Mock()
                candidate = gui._visual_review_proposal.candidate
                report = VisualIdentityReport(outcome='CANDIDATES', candidates=(candidate,), provider_id='fixture', model_id='offline', response_id='fixture', input_tokens=None, output_tokens=None, raw_structured_result={})
                gui._visual_identity_provider = SimpleNamespace(identify=Mock(return_value=report))
                cancel_box = []
                def wait(cancel):
                    cancel_box.append(cancel)
                    return SimpleNamespace(winfo_exists=lambda: True, destroy=cancel)
                gui._create_visual_identification_wait = wait
                with patch('socket.socket', side_effect=AssertionError('No network')):
                    gui._start_visual_identification(source)
                    task = gui._visual_identification_task
                    task.worker.join(5)
                    self.assertFalse(task.worker.is_alive())
                    if cancelled:
                        cancel_box[0]()
                        self.assertIsNone(gui._phone_intake_context)
                        gui._finish_visual_identification.assert_not_called()
                    else:
                        gui.root.after.call_args.args[1]()
                        self.assertEqual(gui._phone_intake_context, context)
                        gui._finish_visual_identification.assert_called_once()

    def test_explicit_pair_images_cannot_be_consumed_by_legacy_group_handoff(self):
        from photo_inbox import PhotoInboxConfig, PhotoInboxManager
        from datetime import datetime, timedelta
        PhoneDropImporter().import_files(self.photos[:2])
        manager = PhotoInboxManager(PhotoInboxConfig(file_stability_seconds=0))
        manager.now_fn = lambda: datetime.now() + timedelta(seconds=10)
        manager.refresh()
        group = manager.get_pending_sets()[0]
        images = manager.get_photo_set_photos(group.id)
        PhoneIntake().confirm_pair(images[0].path, images[1].path)
        self.assertEqual(CoinCollectionGUI.photo_inbox_set_rows(manager), [])
        gui: Any = CoinCollectionGUI.__new__(CoinCollectionGUI)
        with self.assertRaises(ValueError):
            gui.item_photos_from_inbox_photo_set(manager, group.id)


if __name__ == '__main__':
    unittest.main()
