"""Deterministic worker/GUI handoff tests using synthetic sources and events."""

from contextlib import ExitStack
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import Mock, patch

from capture_import.desktop_visual_identity_execution import VisualIdentityReviewTask
from coin_collection_gui import CoinCollectionGUI


class Root:
    def __init__(self):
        self.owner = threading.get_ident()
        self.callbacks = []

    def after(self, delay, callback):
        assert threading.get_ident() == self.owner
        self.callbacks.append(callback)

    def poll(self):
        callbacks, self.callbacks = self.callbacks, []
        for callback in callbacks:
            callback()


class WaitDialog:
    def __init__(self, root, cancel):
        self.root = root
        self.cancel = cancel
        self.exists = True

    def winfo_exists(self):
        assert threading.get_ident() == self.root.owner
        return self.exists

    def destroy(self):
        assert threading.get_ident() == self.root.owner
        self.exists = False
        self.cancel()  # Simulate the Destroy binding, including reentrancy.


class VisualIdentityExecutionTests(unittest.TestCase):
    def setup_gui(self, stack, provider):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = Root()
        gui.capture_import_ready = True
        gui.app = SimpleNamespace(collection=Mock())
        gui._visual_identity_provider_factory = provider
        source = SimpleNamespace(path="synthetic-package", release=Mock())
        stack.enter_context(patch(
            "capture_import.standalone_image_intake.create_temporary_capture_package",
            return_value=source,
        ))
        disclosure = stack.enter_context(patch(
            "coin_collection_gui.messagebox.askyesno", return_value=True,
        ))
        build = stack.enter_context(patch(
            "capture_import.desktop_visual_identity_review.create_visual_request_from_capture_package",
            return_value=object(),
        ))
        proposal = stack.enter_context(patch(
            "capture_import.desktop_visual_identity_review.create_visual_identity_proposal",
            return_value=object(),
        ))
        review = stack.enter_context(patch(
            "capture_import.desktop_visual_identity_review.create_visual_identity_review_dialog",
        ))
        persist = stack.enter_context(patch(
            "capture_import.reviewed_coin_collection_entry.persist_reviewed_coin",
        ))
        errors = stack.enter_context(patch("coin_collection_gui.messagebox.showerror"))
        warnings = stack.enter_context(patch("coin_collection_gui.messagebox.showwarning"))
        info = stack.enter_context(patch("coin_collection_gui.messagebox.showinfo"))
        dialogs = []

        def wait(cancel):
            dialog = WaitDialog(gui.root, cancel)
            dialogs.append(dialog)
            return dialog

        gui._create_visual_identification_wait = wait
        return SimpleNamespace(**locals())

    def start(self, context):
        context.gui.import_coin_images_with_visual_ai("synthetic-front", "synthetic-back")
        return getattr(context.gui, "_visual_identification_task", None)

    def join(self, task):
        task.worker.join(5)
        self.assertFalse(task.worker.is_alive(), "synthetic worker timed out")

    def test_all_three_stages_and_provider_creation_run_off_ui_thread(self):
        with ExitStack() as stack:
            threads = []
            provider = Mock()
            c = self.setup_gui(stack, lambda: threads.append(threading.get_ident()) or provider)
            c.build.side_effect = lambda path: threads.append(threading.get_ident()) or object()
            provider.identify.side_effect = lambda request: threads.append(threading.get_ident()) or object()
            c.proposal.side_effect = lambda report: threads.append(threading.get_ident()) or object()
            task = self.start(c)
            self.join(task)
            self.assertTrue(task.worker.daemon)
            self.assertEqual(threads, [task.worker.ident] * 4)
            self.assertNotEqual(task.worker.ident, c.gui.root.owner)
            c.review.assert_not_called()
            c.source.release.assert_not_called()
            c.review.side_effect = lambda **kw: self.assertEqual(threading.get_ident(), c.gui.root.owner)
            c.gui.root.poll()
            c.review.assert_called_once()
            self.assertIs(c.review.call_args.kwargs["on_confirm"].__self__, c.gui)
            self.assertIs(c.gui._visual_review_source, c.source)
            c.gui._defer_visual_review()
            c.gui._release_visual_review_source()
            c.source.release.assert_called_once()
            c.persist.assert_not_called()

    def test_cancel_inflight_suppresses_late_success_and_failure(self):
        for fails in (False, True):
            with self.subTest(fails=fails), ExitStack() as stack:
                entered, finish = threading.Event(), threading.Event()
                def identify(request):
                    entered.set()
                    if not finish.wait(5):
                        raise AssertionError("test did not unblock provider")
                    if fails:
                        raise RuntimeError("private-provider-error")
                    return object()
                provider = Mock(identify=identify)
                c = self.setup_gui(stack, lambda: provider)
                logs = stack.enter_context(patch("coin_collection_gui._LOGGER.warning"))
                task = self.start(c)
                try:
                    self.assertTrue(entered.wait(5))
                    c.gui.root.poll()  # Responsive polling while the worker is blocked.
                    c.dialogs[0].cancel()
                    c.dialogs[0].cancel()
                    c.source.release.assert_not_called()
                finally:
                    finish.set()
                    self.join(task)
                c.gui.root.poll()
                c.source.release.assert_called_once()
                c.review.assert_not_called()
                c.persist.assert_not_called()
                c.errors.assert_not_called()
                c.warnings.assert_not_called()
                logs.assert_not_called()
                self.assertEqual(c.gui.app.collection.mock_calls, [])

    def test_cancel_queued_completion_releases_once_and_never_reviews(self):
        with ExitStack() as stack:
            c = self.setup_gui(stack, lambda: Mock())
            task = self.start(c)
            self.join(task)
            c.source.release.assert_not_called()
            c.dialogs[0].destroy()  # Same path used when the root closes.
            task.cancel()
            c.gui.root.poll()
            c.source.release.assert_called_once()
            c.review.assert_not_called()
            c.persist.assert_not_called()

    def test_start_failure_and_wait_creation_failure_release_once(self):
        for phase in ("wait", "thread", "after"):
            with self.subTest(phase=phase), ExitStack() as stack:
                c = self.setup_gui(stack, lambda: Mock())
                if phase == "wait":
                    c.gui._create_visual_identification_wait = Mock(side_effect=RuntimeError("wait"))
                elif phase == "thread":
                    stack.enter_context(patch("threading.Thread.start", side_effect=RuntimeError("start")))
                else:
                    c.gui.root.after = Mock(side_effect=RuntimeError("after"))
                tasks = []
                real_start = VisualIdentityReviewTask.start
                def start(task):
                    tasks.append(task)
                    real_start(task)
                stack.enter_context(patch.object(VisualIdentityReviewTask, "start", start))
                with self.assertRaises(RuntimeError):
                    self.start(c)
                for task in tasks:
                    if task.worker.ident is not None:
                        self.join(task)
                c.source.release.assert_called_once()
                c.review.assert_not_called()

    def test_disclosure_decline_never_starts_worker_or_creates_provider(self):
        with ExitStack() as stack:
            factory = Mock()
            c = self.setup_gui(stack, factory)
            c.disclosure.return_value = False
            with patch.object(VisualIdentityReviewTask, "start") as start:
                self.start(c)
            start.assert_not_called()
            factory.assert_not_called()
            c.source.release.assert_called_once()
            c.build.assert_not_called()

    def test_active_review_cannot_be_replaced(self):
        with ExitStack() as stack:
            c = self.setup_gui(stack, lambda: Mock())
            task = self.start(c)
            self.start(c)
            c.disclosure.assert_called_once()
            self.join(task)
            c.gui.root.poll()
            self.start(c)
            c.disclosure.assert_called_once()
            c.gui._defer_visual_review()
            c.source.release.assert_called_once()

    def test_review_dialog_failure_releases_transferred_source(self):
        with ExitStack() as stack:
            c = self.setup_gui(stack, lambda: Mock())
            c.review.side_effect = RuntimeError("dialog")
            task = self.start(c)
            self.join(task)
            with self.assertRaisesRegex(RuntimeError, "dialog"):
                c.gui.root.poll()
            c.source.release.assert_called_once()

    def test_cancelled_worker_cannot_replace_a_new_request(self):
        with ExitStack() as stack:
            entered, finish = threading.Event(), threading.Event()
            def identify(request):
                entered.set()
                finish.wait(5)
                return object()
            c = self.setup_gui(stack, lambda: Mock(identify=identify))
            old = self.start(c)
            try:
                self.assertTrue(entered.wait(5))
                c.dialogs[0].destroy()
                replacement = object()
                c.gui._visual_identification_task = replacement
            finally:
                finish.set()
                self.join(old)
            c.gui.root.poll()
            self.assertIs(c.gui._visual_identification_task, replacement)
            c.source.release.assert_called_once()
            c.review.assert_not_called()

    def test_repeated_start_cannot_release_a_running_source(self):
        entered, finish = threading.Event(), threading.Event()
        source = SimpleNamespace(path="synthetic", release=Mock())
        def work(path):
            entered.set()
            finish.wait(5)
        task = VisualIdentityReviewTask(source, work)
        task.start()
        try:
            self.assertTrue(entered.wait(5))
            with self.assertRaises(RuntimeError):
                task.start()
            task.cancel()
            source.release.assert_not_called()
        finally:
            finish.set()
            self.join(task)
        source.release.assert_called_once()

    def test_active_failure_is_reported_on_ui_thread_and_cleans_once(self):
        with ExitStack() as stack:
            provider = Mock()
            provider.identify.side_effect = RuntimeError("private-key-or-image")
            c = self.setup_gui(stack, lambda: provider)
            logs = stack.enter_context(patch("coin_collection_gui._LOGGER.warning"))
            c.errors.side_effect = lambda *args, **kw: self.assertEqual(
                threading.get_ident(), c.gui.root.owner,
            )
            task = self.start(c)
            self.join(task)
            c.errors.assert_not_called()
            c.gui.root.poll()
            c.errors.assert_called_once()
            c.source.release.assert_called_once()
            self.assertNotIn("private-key-or-image", repr(c.errors.call_args))
            self.assertNotIn("private-key-or-image", repr(logs.call_args))
            c.persist.assert_not_called()
            self.assertEqual(c.gui.app.collection.mock_calls, [])

    def test_wait_ui_wires_cancel_and_destroy_on_ui_thread(self):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = Root()
        dialog = Mock()
        cancel = Mock()
        with patch("coin_collection_gui.tk.Toplevel", return_value=dialog), \
             patch("coin_collection_gui.ttk.Label"), \
             patch("coin_collection_gui.ttk.Progressbar") as progress, \
             patch("coin_collection_gui.ttk.Button") as button:
            self.assertIs(gui._create_visual_identification_wait(cancel), dialog)
        self.assertIs(button.call_args.kwargs["command"], cancel)
        dialog.protocol.assert_called_once_with("WM_DELETE_WINDOW", cancel)
        progress.return_value.start.assert_called_once()
        destroy = dialog.bind.call_args.args[1]
        destroy(SimpleNamespace(widget=object()))
        cancel.assert_not_called()
        destroy(SimpleNamespace(widget=dialog))
        cancel.assert_called_once()


if __name__ == "__main__":
    unittest.main()
