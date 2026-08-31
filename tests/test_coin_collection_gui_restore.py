import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from coin_collection import CoinCollection, CoinItem, CollectionLoadState
from coin_collection_gui import CoinCollectionGUI


def collection(state=CollectionLoadState.VALID, items=None, error=""):
    return SimpleNamespace(
        load_state=state,
        load_error=error,
        last_save_error="",
        items=list(items or []),
    )


def item(item_id, year):
    return CoinItem(
        id=item_id,
        image_path="",
        country="Canada",
        denomination="1 dollar",
        year=year,
        grade="",
        notes="",
        date_added="2026-08-30",
    )


def restore_result(
    *,
    success=True,
    status="Portable restore completed and reloaded",
    restored_files=None,
    errors=None,
):
    return SimpleNamespace(
        success=success,
        status=status,
        restored_files=list(restored_files or []),
        skipped_files=[],
        pre_restore_backup_path="safety.zip",
        errors=list(errors or []),
    )


class CollectionRestoreActivationTests(unittest.TestCase):
    def make_gui(self, active=None):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.app = SimpleNamespace(collection=active or collection())
        gui.backup_manager = SimpleNamespace(collection_json_path="data/collection.json")
        gui._collection_edit_windows = set()
        gui.capture_import_ready = True
        gui.capture_import_recovery = object()
        gui.capture_import_coordinator = object()
        gui.initialize_capture_import_recovery = Mock(return_value=True)
        gui.clear_form = Mock()
        gui.refresh_collection_list = Mock()
        gui.refresh_entry_suggestions = Mock()
        return gui

    def test_activation_reloads_rebinds_and_invalidates_old_collection(self):
        old = collection(items=["old"])
        restored = collection(items=["one", "two"])
        gui = self.make_gui(old)

        with patch("coin_collection_gui.CoinCollection", return_value=restored) as loader:
            count = gui._activate_restored_collection()

        loader.assert_called_once_with("data/collection.json")
        self.assertIs(gui.app.collection, restored)
        self.assertEqual(count, 2)
        self.assertEqual(old.load_state, CollectionLoadState.INVALID_OR_UNSUPPORTED)
        self.assertIn("Superseded", old.load_error)
        gui.initialize_capture_import_recovery.assert_called_once_with()
        gui.clear_form.assert_called_once_with()
        gui.refresh_collection_list.assert_called_once_with()
        gui.refresh_entry_suggestions.assert_called_once_with()

    def test_superseded_collection_reference_cannot_save_over_restored_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "collection.json"
            target.write_bytes(b"restored-authoritative-bytes")
            old = CoinCollection.__new__(CoinCollection)
            old.storage_path = str(target)
            old.items = []
            old.load_state = CollectionLoadState.VALID
            old.collection_format = None
            old.load_error = ""
            old.last_save_error = ""
            restored = collection(items=["restored"])
            gui = self.make_gui(old)
            gui.backup_manager.collection_json_path = str(target)

            with patch("coin_collection_gui.CoinCollection", return_value=restored):
                gui._activate_restored_collection()

            self.assertFalse(old.save_collection())
            self.assertEqual(target.read_bytes(), b"restored-authoritative-bytes")

    def test_real_post_restore_mutation_preserves_restored_roster_not_stale_roster(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "live" / "collection.json"
            restored_source = Path(directory) / "package" / "collection.json"
            old = CoinCollection(str(target))
            self.assertTrue(old.add_item(item("item-a", "1967")))
            packaged = CoinCollection(str(restored_source))
            self.assertTrue(packaged.add_item(item("item-b", "1987")))
            target.write_bytes(restored_source.read_bytes())

            gui = self.make_gui(old)
            gui.backup_manager.collection_json_path = str(target)
            count = gui._activate_restored_collection()

            self.assertEqual(count, 1)
            self.assertIsNot(gui.app.collection, old)
            self.assertEqual(
                [value.id for value in gui.app.collection.items], ["item-b"]
            )
            self.assertTrue(gui.app.collection.add_item(item("item-c", "2003")))
            reloaded = CoinCollection(str(target))
            self.assertEqual(
                [value.id for value in reloaded.items], ["item-b", "item-c"]
            )
            self.assertNotIn("item-a", [value.id for value in reloaded.items])

    def test_stale_edit_windows_are_destroyed(self):
        gui = self.make_gui()
        live = Mock()
        live.winfo_exists.return_value = True
        already_closed = Mock()
        already_closed.winfo_exists.return_value = False
        gui._collection_edit_windows.update((live, already_closed))

        gui._close_collection_edit_windows()

        live.destroy.assert_called_once_with()
        already_closed.destroy.assert_not_called()
        self.assertEqual(gui._collection_edit_windows, set())

    def test_invalid_post_publication_reload_blocks_old_and_new_instances(self):
        old = collection(items=["old"])
        invalid = collection(
            CollectionLoadState.INVALID_OR_UNSUPPORTED,
            error="malformed restored JSON",
        )
        gui = self.make_gui(old)

        with patch("coin_collection_gui.CoinCollection", return_value=invalid):
            with self.assertRaisesRegex(RuntimeError, "not VALID"):
                gui._activate_restored_collection()

        self.assertIs(gui.app.collection, invalid)
        self.assertEqual(old.load_state, CollectionLoadState.INVALID_OR_UNSUPPORTED)
        self.assertEqual(invalid.load_state, CollectionLoadState.INVALID_OR_UNSUPPORTED)
        gui.initialize_capture_import_recovery.assert_not_called()

    def test_rebind_or_refresh_failure_leaves_fresh_instance_active_but_blocked(self):
        old = collection(items=["old"])
        restored = collection(items=["restored"])
        gui = self.make_gui(old)
        gui.refresh_collection_list.side_effect = RuntimeError("tree refresh failed")

        with patch("coin_collection_gui.CoinCollection", return_value=restored):
            with self.assertRaisesRegex(RuntimeError, "activation failed"):
                gui._activate_restored_collection()

        self.assertIs(gui.app.collection, restored)
        self.assertEqual(restored.load_state, CollectionLoadState.INVALID_OR_UNSUPPORTED)
        self.assertIn("tree refresh failed", restored.load_error)
        self.assertEqual(old.load_state, CollectionLoadState.INVALID_OR_UNSUPPORTED)


class RestorePackageFlowTests(unittest.TestCase):
    def make_gui(self, result, *, load_result=None):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = object()
        gui.app = SimpleNamespace(collection=collection(items=["old"]))
        gui.backup_manager = Mock()
        gui.backup_manager.collection_json_path = "data/collection.json"
        gui.backup_manager.verify_backup_package.return_value = SimpleNamespace(
            success=True, errors=[]
        )
        gui.backup_manager.restore_from_backup_package.return_value = result
        gui.persistence_manager = Mock()
        gui.persistence_manager.state_path = "collection_data/app_state/app_state.json"
        gui.persistence_manager.load_state.return_value = load_result or SimpleNamespace(
            success=True, state=object(), errors=[], status="Loaded"
        )
        gui._apply_loaded_app_state = Mock()
        gui._activate_restored_collection = Mock(return_value=3)
        gui._collection_edit_windows = set()
        gui.capture_import_ready = True
        gui.capture_import_recovery = object()
        gui.capture_import_coordinator = object()
        return gui

    def run_restore(self, gui):
        with (
            patch("coin_collection_gui.filedialog.askopenfilename", return_value="backup.zip"),
            patch("coin_collection_gui.messagebox.askyesno", return_value=True),
            patch("coin_collection_gui.messagebox.showinfo") as info,
            patch("coin_collection_gui.messagebox.showwarning") as warning,
            patch("coin_collection_gui.messagebox.showerror") as error,
        ):
            gui.restore_backup_package()
        return info, warning, error

    def test_successful_portable_restore_activates_and_reports_item_count(self):
        gui = self.make_gui(
            restore_result(restored_files=["data/collection.json", "photo.jpg"])
        )

        info, warning, error = self.run_restore(gui)

        gui._activate_restored_collection.assert_called_once_with()
        gui.persistence_manager.load_state.assert_not_called()
        gui._apply_loaded_app_state.assert_not_called()
        error.assert_not_called()
        warning.assert_not_called()
        self.assertIn("Active collection items: 3", info.call_args.args[1])

    def test_session_state_failure_does_not_undo_collection_activation(self):
        restored = collection(items=["restored"])
        load_failure = SimpleNamespace(
            success=False,
            state=None,
            errors=["session JSON malformed"],
            status="Invalid session state",
        )
        gui = self.make_gui(
            restore_result(
                restored_files=[
                    "data/collection.json",
                    "collection_data/app_state/app_state.json",
                ]
            ),
            load_result=load_failure,
        )
        gui._activate_restored_collection.side_effect = lambda: (
            setattr(gui.app, "collection", restored) or 1
        )

        info, warning, error = self.run_restore(gui)

        self.assertIs(gui.app.collection, restored)
        info.assert_not_called()
        error.assert_not_called()
        self.assertIn("collection restore is active and valid", warning.call_args.args[1])

    def test_recovery_required_is_not_reported_as_success_and_blocks_mutation(self):
        gui = self.make_gui(
            restore_result(
                success=False,
                status="Portable restore requires recovery",
                errors=["published reload comparison failed"],
            )
        )

        info, warning, error = self.run_restore(gui)

        gui._activate_restored_collection.assert_not_called()
        self.assertEqual(
            gui.app.collection.load_state,
            CollectionLoadState.INVALID_OR_UNSUPPORTED,
        )
        info.assert_not_called()
        warning.assert_not_called()
        self.assertEqual(error.call_args.args[0], "Portable Restore Requires Recovery")

    def test_prepublication_failure_leaves_active_collection_unchanged(self):
        gui = self.make_gui(
            restore_result(
                success=False,
                status="Portable restore failed",
                errors=["destination collision"],
            )
        )
        active = gui.app.collection

        info, warning, error = self.run_restore(gui)

        self.assertIs(gui.app.collection, active)
        self.assertEqual(active.load_state, CollectionLoadState.VALID)
        gui._activate_restored_collection.assert_not_called()
        info.assert_not_called()
        warning.assert_not_called()
        self.assertEqual(error.call_args.args[0], "Restore Error")

    def test_legacy_collection_restore_uses_same_activation_boundary(self):
        absolute = os.path.abspath("data/collection.json")
        gui = self.make_gui(
            restore_result(status="Restore completed", restored_files=[absolute])
        )

        info, warning, error = self.run_restore(gui)

        gui._activate_restored_collection.assert_called_once_with()
        error.assert_not_called()
        self.assertIn("Active collection items: 3", info.call_args.args[1])

    def test_activation_failure_after_publication_surfaces_recovery_state(self):
        gui = self.make_gui(
            restore_result(restored_files=["data/collection.json"])
        )
        gui._activate_restored_collection.side_effect = RuntimeError("reload failed")

        info, warning, error = self.run_restore(gui)

        info.assert_not_called()
        warning.assert_not_called()
        self.assertEqual(
            gui.app.collection.load_state,
            CollectionLoadState.INVALID_OR_UNSUPPORTED,
        )
        self.assertIn("reload failed", error.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
