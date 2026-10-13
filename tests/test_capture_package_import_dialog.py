"""Synthetic Windows/Tk import states with a deliberately delayed worker."""

import gc
import threading
import time
import tkinter as tk
import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock, patch

from capture_import.coordinator import PreparedPackageImport
from capture_import.enums import DuplicateDecision
from capture_import.transaction import PackageImportExecutionResult, Schema3TransactionGenesisResult
from capture_import.ui import CapturePackageImportDialog
from coin_collection import CoinCollection
from tests.capture_package_fixtures import package_bytes


class CapturePackageImportDialogTests(unittest.TestCase):
    def setUp(self):
        # Reclaim previous Tk fixtures on the GUI thread before spawning workers.
        gc.collect()
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        self.root.geometry("1x1+0+0")
        self.addCleanup(self.root.destroy)
        self.callback_errors = []
        callback_errors = self.callback_errors
        self.root.report_callback_exception = lambda *args: callback_errors.append(args)
        self.coordinator = Mock()
        self.on_success = Mock()
        with patch("capture_import.ui.build_default_import_services", return_value=(Mock(), self.coordinator)), patch.object(
            CapturePackageImportDialog, "_start_prepare"
        ):
            self.dialog = CapturePackageImportDialog(
                self.root, "synthetic.ca-package", Mock(), on_success=self.on_success
            )
        self.addCleanup(self.close_dialog)

    def close_dialog(self):
        if self.dialog.window.winfo_exists():
            self.dialog.window.destroy()

    def preview(self):
        prepared = Mock(spec=PreparedPackageImport)
        prepared.preview = SimpleNamespace(session_name="Synthetic", proposals=(), duplicate_count=0, decisions=())
        prepared.snapshot = SimpleNamespace(is_active=True)
        self.dialog._prepared = cast(PreparedPackageImport, prepared)
        self.dialog._render_preview()
        self.root.update()

    def pump_until(self, predicate, timeout=3):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertTrue(predicate(), "Tk completion callback did not arrive")

    def prepare_real_dialog(self, directory):
        self.dialog.cancel()
        source = Path(directory) / "synthetic.ca-package"
        source.write_bytes(package_bytes())
        collection = CoinCollection(str(Path(directory) / "collection.json"))
        self.on_close = Mock()
        self.dialog = CapturePackageImportDialog(
            self.root, str(source), collection, on_success=self.on_success,
            on_close=self.on_close,
        )
        self.pump_until(lambda: self.dialog._prepared is not None or self.callback_errors, timeout=10)
        self.assertEqual([], self.callback_errors)
        return collection

    def commit_real_dialog(self):
        results = []
        real_commit = self.dialog._coordinator.commit

        def capture(*args, **kwargs):
            result = real_commit(*args, **kwargs)
            results.append(result)
            return result

        with patch.object(self.dialog._coordinator, "commit", side_effect=capture) as commits:
            self.dialog.commit()
            self.dialog.commit()  # Immediate repeat must not run another transaction.
            self.pump_until(lambda: self.dialog._closed or self.callback_errors, timeout=15)
            self.assertEqual([], self.callback_errors)
            self.dialog.commit()  # The closed entry must not be committed again either.
            commits.assert_called_once()
        self.assertFalse(self.dialog.window.winfo_exists())
        self.assertIsNone(self.root.grab_current())
        self.on_close.assert_called_once()
        self.on_success.assert_called_once()
        return results[0]

    def test_actual_schema3_completion_reports_verified_counts_and_closes(self):
        with TemporaryDirectory() as directory, chdir(directory), patch(
            "capture_import.ui.messagebox.showinfo"
        ) as success:
            collection = self.prepare_real_dialog(directory)
            success.side_effect = lambda *_args: self.assertFalse(self.dialog.progress.winfo_ismapped())
            result = self.commit_real_dialog()
            self.assertIsInstance(result, Schema3TransactionGenesisResult)
            self.assertEqual(1, result.journal.imported_count)
            self.assertEqual(2, len(result.journal.verified_image_inventory))
            self.assertIn("✓ 1 coin(s)", success.call_args.args[1])
            self.assertIn("✓ 2 image(s)", success.call_args.args[1])
            self.assertIn("✓ 0 skipped", success.call_args.args[1])
            reloaded = CoinCollection(collection.storage_path)
            self.assertEqual(1, len(reloaded.items))
            self.assertEqual("1967", reloaded.items[0].year)

    def test_actual_all_skip_completion_uses_legacy_result_without_saving(self):
        with TemporaryDirectory() as directory, chdir(directory), patch(
            "capture_import.ui.messagebox.showinfo"
        ) as success:
            collection = self.prepare_real_dialog(directory)
            for variable in self.dialog._decision_vars.values():
                variable.set(DuplicateDecision.SKIP.value)
            result = self.commit_real_dialog()
            self.assertIsInstance(result, PackageImportExecutionResult)
            self.assertEqual(0, result.imported_count)
            self.assertEqual(1, result.skipped_count)
            self.assertIn("✓ 0 coin(s)", success.call_args.args[1])
            self.assertIn("✓ 0 image(s)", success.call_args.args[1])
            self.assertIn("✓ 1 skipped", success.call_args.args[1])
            self.assertFalse(Path(collection.storage_path).exists())

    def test_actual_collection_change_error_restores_cancel_without_duplicate_save(self):
        with TemporaryDirectory() as directory, chdir(directory), patch(
            "capture_import.ui.messagebox.showerror"
        ) as error:
            collection = self.prepare_real_dialog(directory)
            # Change only this temporary collection after its preview baseline.
            Path(collection.storage_path).write_text("[]", encoding="utf-8")
            self.dialog.commit()
            self.pump_until(lambda: not self.dialog._committing, timeout=10)
            error.assert_called_once()
            self.assertEqual([], self.callback_errors)
            self.assertFalse(self.dialog.progress.winfo_ismapped())
            self.assertTrue(self.dialog.import_button.instate(["disabled"]))
            self.assertFalse(self.dialog.cancel_button.instate(["disabled"]))
            self.assertEqual([], CoinCollection(collection.storage_path).items)
            self.dialog.cancel()
            self.assertFalse(self.dialog.window.winfo_exists())
            self.assertIsNone(self.root.grab_current())
            self.on_success.assert_not_called()
            self.on_close.assert_called_once()

    def start_delayed_commit(self, error=None):
        release = threading.Event()
        finished = threading.Event()

        def commit(*_args):
            try:
                if not release.wait(3):
                    raise RuntimeError("Synthetic worker timed out")
                if error:
                    raise error
                return SimpleNamespace(imported_count=1, image_count=2, skipped_count=0)
            finally:
                finished.set()

        self.coordinator.commit.side_effect = commit
        # Cleanup runs before widget destruction even when an assertion fails.
        self.addCleanup(lambda: finished.wait(3))
        self.addCleanup(release.set)
        self.dialog.commit()
        self.root.update()
        return release

    def test_preparation_can_cancel_without_collection_commit(self):
        self.assertTrue(self.dialog.import_button.instate(["disabled"]))
        self.assertFalse(self.dialog.cancel_button.instate(["disabled"]))
        self.dialog.cancel()
        self.coordinator.commit.assert_not_called()
        self.assertFalse(self.dialog.window.winfo_exists())
        self.assertEqual([], self.callback_errors)

    def test_delayed_commit_shows_activity_blocks_repeat_and_finishes(self):
        self.preview()
        release = self.start_delayed_commit()
        self.assertTrue(self.dialog.progress.winfo_exists(), "Commit must retain an activity indicator")
        self.assertTrue(self.dialog.progress.winfo_ismapped())
        first = float(self.dialog.progress["value"])
        self.pump_until(lambda: float(self.dialog.progress["value"]) != first)
        self.assertIn("Cancel is unavailable", self.dialog.status.get())
        self.assertTrue(self.dialog.import_button.instate(["disabled"]))
        self.assertTrue(self.dialog.cancel_button.instate(["disabled"]))
        self.dialog.commit()
        self.dialog.cancel()
        self.assertFalse(self.dialog._closed)
        self.coordinator.commit.assert_called_once()
        with patch("capture_import.ui.messagebox.showinfo"):
            release.set()
            self.pump_until(lambda: self.dialog._closed)
        self.on_success.assert_called_once()
        self.assertIsNone(self.root.grab_current())
        self.assertEqual([], self.callback_errors)

    def test_ocr_ready_hides_activity_without_enabling_import(self):
        handoff = object()
        callback = Mock()
        self.dialog._ocr_handoff = handoff
        self.dialog._on_ocr_handoff = callback
        self.dialog._render_ocr_ready()
        self.root.update()
        self.assertFalse(self.dialog.progress.winfo_ismapped())
        self.assertTrue(self.dialog.import_button.instate(["disabled"]))
        self.assertFalse(self.dialog.cancel_button.instate(["disabled"]))
        callback.assert_called_once_with(self.dialog.window, handoff)
        self.coordinator.commit.assert_not_called()
        self.dialog.cancel()
        self.assertEqual([], self.callback_errors)

    def test_commit_error_stops_activity_and_allows_close(self):
        self.preview()
        release = self.start_delayed_commit(RuntimeError("Synthetic failure"))
        with patch("capture_import.ui.messagebox.showerror"):
            release.set()
            self.pump_until(lambda: not self.dialog._committing)
        self.assertTrue(self.dialog.progress.winfo_exists())
        self.assertFalse(self.dialog.progress.winfo_ismapped())
        self.assertFalse(self.dialog.cancel_button.instate(["disabled"]))
        self.dialog.cancel()
        self.assertIsNone(self.root.grab_current())
        self.assertEqual([], self.callback_errors)
