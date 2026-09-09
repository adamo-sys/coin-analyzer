"""Headless tests for the Unit 9C Collector Work Queue GUI."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from coin_collection import (
    CoinItem,
    CollectionLoadState,
    IdentificationStatus,
    ItemPhoto,
    ItemType,
    PhotoRole,
)
from coin_collection_gui import CoinCollectionGUI
from collector_work_queue import WorkQueueTaskType, derive_work_queue
from collector_work_queue_gui import (
    WorkQueueFilter,
    WorkQueueWindow,
    default_work_queue_filter,
    filtered_work_queue_tasks,
)


class Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Button:
    def __init__(self):
        self.options = {}

    def configure(self, **options):
        self.options.update(options)

    config = configure


class Tree:
    def __init__(self):
        self.rows = {}
        self.selected = ()

    def get_children(self):
        return tuple(self.rows)

    def delete(self, row_id):
        self.rows.pop(row_id, None)
        if row_id in self.selected:
            self.selected = ()

    def insert(self, _parent, _where, iid, **options):
        self.rows[iid] = options
        return iid

    def selection(self):
        return self.selected


class NativeWindow:
    def __init__(self):
        self.exists = True
        self.destroy_calls = 0
        self.focus_calls = []

    def winfo_exists(self):
        return self.exists

    def destroy(self):
        self.destroy_calls += 1
        self.exists = False

    def deiconify(self):
        self.focus_calls.append("deiconify")

    def lift(self):
        self.focus_calls.append("lift")

    def focus_force(self):
        self.focus_calls.append("focus_force")


class Collection:
    def __init__(self, items=(), state=CollectionLoadState.LOADED):
        self.items = list(items)
        self.load_state = state

    def get_item(self, item_id):
        return next((item for item in self.items if item.id == item_id), None)


def item(item_id="item-1", **overrides):
    values = {
        "id": item_id,
        "image_path": "",
        "country": "Canada",
        "denomination": "5 cents",
        "year": "1899",
        "grade": "",
        "notes": "",
        "date_added": "2026-08-31",
        "identification_status": IdentificationStatus.IDENTIFIED,
        "item_type": ItemType.COIN,
        "photos": [ItemPhoto("back.jpg", PhotoRole.BACK)],
    }
    values.update(overrides)
    return CoinItem(**values)


def window_for(collection):
    window = WorkQueueWindow.__new__(WorkQueueWindow)
    window._collection_provider = lambda: collection
    window._open_editor = Mock()
    window._on_close = None
    window._projection = None
    window._row_task_ids = {}
    window._closed = False
    window.window = NativeWindow()
    window.filter_var = Var(WorkQueueFilter.ALL.value)
    window.state_var = Var()
    window.status_var = Var()
    window.summary_buttons = {task_type: Button() for task_type in WorkQueueTaskType}
    window.filter_buttons = {selected_filter: Button() for selected_filter in WorkQueueFilter}
    window.refresh_button = Button()
    window.action_button = Button()
    window.tree = Tree()
    return window


def select_first_row(window):
    row_id = next(iter(window.tree.rows))
    window.tree.selected = (row_id,)
    window.on_selection_changed()
    return row_id


class FilterModelTests(unittest.TestCase):
    def test_default_filter_is_highest_priority_nonzero_then_all(self):
        acquisition_only = derive_work_queue(
            Collection([item(shipping_cost=Decimal("0"))])
        )
        self.assertIs(
            default_work_queue_filter(acquisition_only),
            WorkQueueFilter.ACQUISITION,
        )
        with_photos = derive_work_queue(Collection([item(photos=[])]))
        self.assertIs(default_work_queue_filter(with_photos), WorkQueueFilter.PHOTOS)
        with_identity = derive_work_queue(
            Collection([item(identification_status=IdentificationStatus.PARTIAL)])
        )
        self.assertIs(default_work_queue_filter(with_identity), WorkQueueFilter.IDENTITY)
        empty = derive_work_queue(Collection([item()]))
        self.assertIs(default_work_queue_filter(empty), WorkQueueFilter.ALL)

    def test_all_filters_preserve_projection_order(self):
        projection = derive_work_queue(
            Collection(
                [
                    item(
                        "multi",
                        photos=[],
                        identification_status=IdentificationStatus.PARTIAL,
                        shipping_cost=Decimal("1"),
                    ),
                    item("photo", photos=[]),
                ]
            )
        )
        self.assertEqual(filtered_work_queue_tasks(projection, WorkQueueFilter.ALL), projection.tasks)
        expected_types = {
            WorkQueueFilter.IDENTITY: WorkQueueTaskType.UNRESOLVED_IDENTITY,
            WorkQueueFilter.PHOTOS: WorkQueueTaskType.MISSING_REVERSE_PHOTO,
            WorkQueueFilter.ACQUISITION: WorkQueueTaskType.MISSING_ACQUISITION_PRICE,
        }
        for selected_filter, task_type in expected_types.items():
            with self.subTest(selected_filter=selected_filter):
                tasks = filtered_work_queue_tasks(projection, selected_filter)
                self.assertTrue(tasks)
                self.assertTrue(all(task.task_type is task_type for task in tasks))
                self.assertEqual(
                    tasks,
                    tuple(task for task in projection.tasks if task.task_type is task_type),
                )


class WorkQueueWindowTests(unittest.TestCase):
    def test_refresh_uses_default_filter_and_exact_reconciled_counts(self):
        collection = Collection(
            [
                item(
                    "multi",
                    photos=[],
                    identification_status=IdentificationStatus.PARTIAL,
                    shipping_cost=Decimal("1"),
                ),
                item("complete"),
            ]
        )
        window = window_for(collection)

        window.refresh(choose_default=True)

        self.assertEqual(window.filter_var.get(), WorkQueueFilter.IDENTITY.value)
        self.assertEqual(len(window._projection.tasks), 3)
        self.assertEqual(sum(dict(window._projection.counts_by_type).values()), 3)
        self.assertEqual(len(window.tree.rows), 1)
        self.assertEqual(
            window.summary_buttons[WorkQueueTaskType.UNRESOLVED_IDENTITY].options["text"],
            "Confirm identity\n1",
        )
        self.assertEqual(window.filter_buttons[WorkQueueFilter.ALL].options["text"], "All 3")

    def test_rows_show_human_copy_but_hide_internal_identity(self):
        specimen = item(
            "private:stable:id",
            title="  Écu d’essai  ",
            photos=[],
            identification_status=IdentificationStatus.PARTIAL,
        )
        window = window_for(Collection([specimen]))
        window.refresh(choose_default=True)

        values = next(iter(window.tree.rows.values()))["values"]
        visible = " | ".join(str(value) for value in values)
        self.assertIn("Confirm identity", visible)
        self.assertIn("Écu d’essai", visible)
        self.assertIn("Identification is partial.", visible)
        self.assertNotIn("private:stable:id", visible)
        self.assertNotIn("work-queue:", visible)
        self.assertNotIn("UNRESOLVED_IDENTITY", visible)
        self.assertNotIn("identification_status=", visible)

    def test_each_filter_and_zero_count_state(self):
        specimen = item(
            photos=[],
            identification_status=IdentificationStatus.PARTIAL,
        )
        window = window_for(Collection([specimen]))
        window.refresh()
        expected = {
            WorkQueueFilter.ALL: 2,
            WorkQueueFilter.IDENTITY: 1,
            WorkQueueFilter.PHOTOS: 1,
            WorkQueueFilter.ACQUISITION: 0,
        }
        for selected_filter, count in expected.items():
            with self.subTest(selected_filter=selected_filter):
                window.select_filter(selected_filter)
                self.assertEqual(len(window.tree.rows), count)
        self.assertEqual(window.state_var.get(), "No tasks in this category.")

    def test_selection_updates_action_and_all_activation_paths_share_handler(self):
        window = window_for(Collection([item(photos=[])]))
        window.refresh(choose_default=True)
        select_first_row(window)
        self.assertEqual(window.action_button.options["text"], "Edit photos")
        source = inspect.getsource(WorkQueueWindow._build_widgets)
        self.assertIn('command=self.activate_selected_task', source)
        self.assertIn('self.tree.bind("<Double-1>", self.activate_selected_task)', source)
        self.assertIn('self.tree.bind("<Return>", self.activate_selected_task)', source)

    def test_replaced_record_with_reused_id_is_refused(self):
        specimen = item("unicode:é", photos=[])
        collection = Collection([specimen])
        window = window_for(collection)
        window.refresh(choose_default=True)
        select_first_row(window)

        replacement = item("unicode:é", photos=[])
        collection.items[:] = [replacement]
        window.activate_selected_task()

        window._open_editor.assert_not_called()
        self.assertIn("stale", window.status_var.get())

    def test_unchanged_bound_item_opens(self):
        specimen = item(photos=[])
        window = window_for(Collection([specimen]))
        window.refresh(choose_default=True)
        select_first_row(window)
        window.activate_selected_task()
        self.assertIs(window._open_editor.call_args.args[0], specimen)

    def test_replacement_collection_and_filter_cannot_rebind_stale_task(self):
        window = window_for(Collection([item(photos=[])]))
        window.refresh(choose_default=True)
        window._collection_provider = lambda: Collection([item(photos=[])])
        window.filter_var.set(WorkQueueFilter.ALL.value)
        window.render_selected_filter()
        select_first_row(window)
        window.activate_selected_task()
        window._open_editor.assert_not_called()
        self.assertIn("stale", window.status_var.get())

    def test_resolved_stale_task_is_refused_and_refreshed(self):
        specimen = item(identification_status=IdentificationStatus.PARTIAL)
        window = window_for(Collection([specimen]))
        window.refresh(choose_default=True)
        select_first_row(window)
        specimen.identification_status = IdentificationStatus.IDENTIFIED

        window.activate_selected_task()

        window._open_editor.assert_not_called()
        self.assertEqual(window.status_var.get(), "This task has already been resolved.")
        self.assertEqual(window.tree.rows, {})

    def test_missing_current_item_is_refused(self):
        specimen = item(photos=[])
        collection = Collection([specimen])
        window = window_for(collection)
        window.refresh(choose_default=True)
        select_first_row(window)

        collection.items.clear()

        window.activate_selected_task()

        window._open_editor.assert_not_called()
        self.assertIn("stale", window.status_var.get())

    def test_after_save_reports_resolved_or_still_present(self):
        specimen = item(identification_status=IdentificationStatus.PARTIAL)
        collection = Collection([specimen])
        window = window_for(collection)
        window.refresh(choose_default=True)
        task = window._projection.tasks[0]

        specimen.identification_status = IdentificationStatus.IDENTIFIED
        window._after_save(task.task_id, task.title)
        self.assertEqual(window.status_var.get(), "Resolved: Confirm identity.")

        specimen.identification_status = IdentificationStatus.PARTIAL
        window.refresh(choose_default=True)
        task = window._projection.tasks[0]
        specimen.grade = "MS-65"
        window._after_save(task.task_id, task.title)
        self.assertEqual(window.status_var.get(), "Saved. This task still needs attention.")

    def test_callback_after_closed_window_is_safe_noop(self):
        window = window_for(Collection([item(photos=[])]))
        window.refresh(choose_default=True)
        task = window._projection.tasks[0]
        window.close()
        window._after_save(task.task_id, task.title)
        self.assertEqual(window.window.destroy_calls, 1)

    def test_missing_invalid_and_valid_empty_states_are_distinct(self):
        missing = window_for(Collection([], CollectionLoadState.MISSING))
        missing.refresh()
        self.assertIn("No collection is available yet", missing.state_var.get())
        self.assertEqual(missing.action_button.options["state"], "disabled")

        invalid = window_for(Collection([], CollectionLoadState.FAILED))
        invalid.refresh()
        self.assertIn("Work Queue unavailable", invalid.state_var.get())
        self.assertNotIn("load", invalid.state_var.get().lower())

        empty = window_for(Collection([item()]))
        empty.refresh(choose_default=True)
        self.assertIn("Nothing needs attention", empty.state_var.get())

    def test_refresh_filtering_and_rendering_do_not_mutate_collection(self):
        specimen = item(
            photos=[
                ItemPhoto("later.jpg", PhotoRole.FRONT, False, "later", 99),
                ItemPhoto("earlier.jpg", PhotoRole.OTHER, True, "earlier", -7),
            ],
            identification_status=IdentificationStatus.PARTIAL,
        )
        collection = Collection([specimen])
        before = deepcopy(collection.items)
        photo_list_id = id(specimen.photos)
        photo_ids = tuple(id(photo) for photo in specimen.photos)
        window = window_for(collection)

        for _ in range(5):
            window.refresh(choose_default=True)
            for selected_filter in WorkQueueFilter:
                window.select_filter(selected_filter)

        self.assertEqual(collection.items, before)
        self.assertEqual(id(specimen.photos), photo_list_id)
        self.assertEqual(tuple(id(photo) for photo in specimen.photos), photo_ids)

    def test_nine_hundred_rows_render_synchronously(self):
        collection = Collection([item(f"item-{index:04d}", photos=[]) for index in range(900)])
        window = window_for(collection)
        window.refresh()
        window.select_filter(WorkQueueFilter.PHOTOS)
        self.assertEqual(len(window.tree.rows), 900)
        self.assertEqual(len(window._row_task_ids), 900)


class CoinCollectionGUIIntegrationTests(unittest.TestCase):
    def test_menu_contains_direct_first_class_work_queue_command(self):
        source = inspect.getsource(CoinCollectionGUI.create_menu_bar)
        command = 'menubar.add_command(label="Work Queue", command=self.open_work_queue)'
        self.assertIn(command, source)
        self.assertNotIn('tools_menu.add_command(label="Work Queue"', source)
        self.assertNotIn('reports_menu.add_command(label="Work Queue"', source)

    def test_open_work_queue_refreshes_and_focuses_existing_window(self):
        existing = Mock()
        existing.is_open.return_value = True
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui._work_queue_window = existing

        result = gui.open_work_queue()

        self.assertIs(result, existing)
        existing.refresh.assert_called_once_with(choose_default=True)
        existing.focus.assert_called_once_with()

    def test_open_work_queue_creates_one_window_with_current_collection_provider(self):
        collection = Collection([])
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = object()
        gui.app = SimpleNamespace(collection=collection)
        gui._work_queue_window = None
        created = Mock()

        with patch("coin_collection_gui.WorkQueueWindow", return_value=created) as factory:
            result = gui.open_work_queue()

        self.assertIs(result, created)
        kwargs = factory.call_args.kwargs
        self.assertIs(kwargs["collection_provider"](), collection)
        replacement = Collection([])
        gui.app.collection = replacement
        self.assertIs(kwargs["collection_provider"](), replacement)
        kwargs["on_close"]()
        self.assertIsNone(gui._work_queue_window)

    def test_successful_edit_finisher_invokes_callback_once(self):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.refresh_collection_list = Mock()
        dialog = Mock()
        callback = Mock()
        with patch("coin_collection_gui.messagebox.showinfo") as info:
            gui._finish_successful_item_edit(dialog, "stable:id", callback)
        gui.refresh_collection_list.assert_called_once_with()
        dialog.destroy.assert_called_once_with()
        callback.assert_called_once_with("stable:id")
        info.assert_called_once_with("Success", "Item updated")

    def test_successful_edit_finisher_bounds_callback_failure(self):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.refresh_collection_list = Mock()
        dialog = Mock()
        callback = Mock(side_effect=RuntimeError("private failure detail"))

        with (
            patch("coin_collection_gui.messagebox.showinfo") as info,
            patch("coin_collection_gui.messagebox.showwarning") as warning,
        ):
            gui._finish_successful_item_edit(dialog, "stable:id", callback)

        gui.refresh_collection_list.assert_called_once_with()
        dialog.destroy.assert_called_once_with()
        callback.assert_called_once_with("stable:id")
        info.assert_called_once_with("Success", "Item updated")
        warning.assert_called_once_with(
            "Work Queue Refresh",
            "The item was saved, but the Work Queue could not be refreshed. "
            "Reopen or refresh the Work Queue to see the latest tasks.",
        )
        self.assertNotIn("private failure detail", " ".join(warning.call_args.args))

    def test_editor_callback_is_only_reached_after_success_guard(self):
        source = inspect.getsource(CoinCollectionGUI.open_edit_item_window)
        failure_guard = source.index("if not result.success:")
        failure_return = source.index("return", failure_guard)
        success_finish = source.index("self._finish_successful_item_edit")
        self.assertLess(failure_guard, failure_return)
        self.assertLess(failure_return, success_finish)


if __name__ == "__main__":
    unittest.main()
