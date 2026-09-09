"""Tk presentation and navigation for the derived Collector Work Queue."""

from __future__ import annotations

from enum import Enum
import tkinter as tk
from tkinter import ttk
from typing import Callable

from coin_collection import CoinCollection, CollectionLoadState
from collection_item_reference import CollectionItemReference
from collector_work_queue import (
    WorkQueueProjection,
    WorkQueueProjectionError,
    WorkQueueTask,
    WorkQueueTaskType,
    derive_work_queue,
)


class WorkQueueFilter(str, Enum):
    ALL = "ALL"
    IDENTITY = "IDENTITY"
    PHOTOS = "PHOTOS"
    ACQUISITION = "ACQUISITION"


_FILTER_TASK_TYPES = {
    WorkQueueFilter.IDENTITY: WorkQueueTaskType.UNRESOLVED_IDENTITY,
    WorkQueueFilter.PHOTOS: WorkQueueTaskType.MISSING_REVERSE_PHOTO,
    WorkQueueFilter.ACQUISITION: WorkQueueTaskType.MISSING_ACQUISITION_PRICE,
}

_SUMMARY_LABELS = {
    WorkQueueTaskType.UNRESOLVED_IDENTITY: "Confirm identity",
    WorkQueueTaskType.MISSING_REVERSE_PHOTO: "Add reverse photo",
    WorkQueueTaskType.MISSING_ACQUISITION_PRICE: "Record purchase price",
}

_FILTER_LABELS = {
    WorkQueueFilter.ALL: "All",
    WorkQueueFilter.IDENTITY: "Identity",
    WorkQueueFilter.PHOTOS: "Photos",
    WorkQueueFilter.ACQUISITION: "Acquisition",
}


def filtered_work_queue_tasks(
    projection: WorkQueueProjection, selected_filter: WorkQueueFilter
) -> tuple[WorkQueueTask, ...]:
    """Filter tasks without changing their projection-defined order."""
    if selected_filter is WorkQueueFilter.ALL:
        return projection.tasks
    task_type = _FILTER_TASK_TYPES[selected_filter]
    return tuple(task for task in projection.tasks if task.task_type is task_type)


def default_work_queue_filter(projection: WorkQueueProjection) -> WorkQueueFilter:
    """Choose the highest-priority nonempty category for a manageable landing view."""
    counts = dict(projection.counts_by_type)
    for selected_filter in (
        WorkQueueFilter.IDENTITY,
        WorkQueueFilter.PHOTOS,
        WorkQueueFilter.ACQUISITION,
    ):
        if counts[_FILTER_TASK_TYPES[selected_filter]]:
            return selected_filter
    return WorkQueueFilter.ALL


class WorkQueueWindow:
    """One reusable Work Queue window over the current active collection."""

    def __init__(
        self,
        parent,
        collection_provider: Callable[[], CoinCollection],
        open_editor: Callable[[object, Callable[..., None]], None],
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self._collection_provider = collection_provider
        self._open_editor = open_editor
        self._on_close = on_close
        self._projection: WorkQueueProjection | None = None
        self._row_task_ids: dict[str, str] = {}
        self._closed = False

        self.window = tk.Toplevel(parent)
        self.window.title("Collector Work Queue")
        self.window.geometry("1000x700")
        self.window.minsize(760, 480)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.filter_var = tk.StringVar(value=WorkQueueFilter.ALL.value)
        self.state_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Select a task to address it.")

        self._build_widgets()
        self.refresh(choose_default=True)

    def _build_widgets(self) -> None:
        container = ttk.Frame(self.window, padding="12")
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(4, weight=1)

        ttk.Label(
            container,
            text="Collector Work Queue",
            font=("TkDefaultFont", 16, "bold"),
        ).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(
            container,
            text="Factual maintenance derived from your current collection.",
        ).grid(row=1, column=0, sticky=tk.W, pady=(2, 10))

        summary = ttk.Frame(container)
        summary.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        for column in range(3):
            summary.columnconfigure(column, weight=1)
        self.summary_buttons: dict[WorkQueueTaskType, ttk.Button] = {}
        for column, (task_type, label) in enumerate(_SUMMARY_LABELS.items()):
            selected_filter = next(
                key for key, value in _FILTER_TASK_TYPES.items() if value is task_type
            )
            button = ttk.Button(
                summary,
                text=f"{label}\n0",
                command=lambda value=selected_filter: self.select_filter(value),
            )
            button.grid(
                row=0,
                column=column,
                sticky=(tk.W, tk.E),
                padx=(0 if column == 0 else 4, 0 if column == 2 else 4),
            )
            self.summary_buttons[task_type] = button

        filter_frame = ttk.LabelFrame(container, text="Show", padding="6")
        filter_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        self.filter_buttons: dict[WorkQueueFilter, ttk.Radiobutton] = {}
        for column, selected_filter in enumerate(WorkQueueFilter):
            button = ttk.Radiobutton(
                filter_frame,
                text=f"{_FILTER_LABELS[selected_filter]} 0",
                value=selected_filter.value,
                variable=self.filter_var,
                command=self.render_selected_filter,
            )
            button.grid(row=0, column=column, sticky=tk.W, padx=(0, 14))
            self.filter_buttons[selected_filter] = button

        list_frame = ttk.Frame(container)
        list_frame.grid(row=4, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)

        ttk.Label(list_frame, textvariable=self.state_var).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 5)
        )
        columns = ("priority", "task", "item", "reason", "action")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        headings = {
            "priority": "Priority",
            "task": "Task",
            "item": "Item",
            "reason": "Reason",
            "action": "Action",
        }
        widths = {
            "priority": 70,
            "task": 165,
            "item": 235,
            "reason": 330,
            "action": 135,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                minwidth=60,
                stretch=column in {"item", "reason"},
            )
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        self.tree.bind("<<TreeviewSelect>>", self.on_selection_changed)
        self.tree.bind("<Double-1>", self.activate_selected_task)
        self.tree.bind("<Return>", self.activate_selected_task)

        footer = ttk.Frame(container)
        footer.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky=tk.W)
        self.refresh_button = ttk.Button(footer, text="Refresh", command=self.refresh)
        self.refresh_button.grid(row=0, column=1, padx=(6, 0))
        self.action_button = ttk.Button(
            footer,
            text="Open Item",
            command=self.activate_selected_task,
            state=tk.DISABLED,
        )
        self.action_button.grid(row=0, column=2, padx=(6, 0))
        ttk.Button(footer, text="Close", command=self.close).grid(
            row=0, column=3, padx=(6, 0)
        )

    def is_open(self) -> bool:
        if self._closed:
            return False
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def focus(self) -> None:
        if self.is_open():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.window.destroy()
        finally:
            if self._on_close is not None:
                self._on_close()

    def select_filter(self, selected_filter: WorkQueueFilter) -> None:
        self.filter_var.set(selected_filter.value)
        self.render_selected_filter()

    def refresh(
        self,
        *,
        choose_default: bool = False,
        status_message: str | None = None,
    ) -> None:
        if not self.is_open():
            return
        collection = self._collection_provider()
        self._task_references = {}
        try:
            projection = derive_work_queue(collection)
            items = {item.id: item for item in collection.items}
            self._task_references = {
                task.task_id: CollectionItemReference.capture(collection, items[task.item_id])
                for task in projection.tasks
            }
        except (WorkQueueProjectionError, ValueError):
            self._task_references = {}
            self._projection = None
            self._update_counts(None)
            self._set_projection_controls_enabled(False)
            self._clear_rows()
            self.state_var.set(
                "Work Queue unavailable. The active collection is not valid, "
                "so maintenance tasks cannot be derived safely."
            )
            self.status_var.set("Work Queue unavailable.")
            return

        self._projection = projection
        self._update_counts(projection)
        if projection.collection_state is CollectionLoadState.MISSING:
            self._set_projection_controls_enabled(False)
            self._clear_rows()
            self.state_var.set(
                "No collection is available yet. "
                "Add or import an item to begin using the Work Queue."
            )
            self.status_var.set("No collection is available yet.")
            return

        self._set_projection_controls_enabled(True)
        if choose_default:
            self.filter_var.set(default_work_queue_filter(projection).value)
        else:
            self._selected_filter()
        self.render_selected_filter()
        if status_message is not None:
            self.status_var.set(status_message)

    def _update_counts(self, projection: WorkQueueProjection | None) -> None:
        counts = dict(projection.counts_by_type) if projection is not None else {}
        total = len(projection.tasks) if projection is not None else 0
        for task_type, button in self.summary_buttons.items():
            button.configure(text=f"{_SUMMARY_LABELS[task_type]}\n{counts.get(task_type, 0)}")
        filter_counts = {
            WorkQueueFilter.ALL: total,
            **{
                selected_filter: counts.get(task_type, 0)
                for selected_filter, task_type in _FILTER_TASK_TYPES.items()
            },
        }
        for selected_filter, button in self.filter_buttons.items():
            button.configure(
                text=f"{_FILTER_LABELS[selected_filter]} {filter_counts[selected_filter]}"
            )

    def _set_projection_controls_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for button in self.summary_buttons.values():
            button.configure(state=state)
        for button in self.filter_buttons.values():
            button.configure(state=state)
        if not enabled:
            self.action_button.configure(state=tk.DISABLED, text="Open Item")

    def _selected_filter(self) -> WorkQueueFilter:
        try:
            return WorkQueueFilter(self.filter_var.get())
        except ValueError:
            self.filter_var.set(WorkQueueFilter.ALL.value)
            return WorkQueueFilter.ALL

    def _clear_rows(self) -> None:
        for row_id in self.tree.get_children():
            self.tree.delete(row_id)
        self._row_task_ids = {}
        self.action_button.configure(state=tk.DISABLED, text="Open Item")

    def render_selected_filter(self) -> None:
        self._clear_rows()
        if self._projection is None:
            return
        tasks = filtered_work_queue_tasks(self._projection, self._selected_filter())
        for index, task in enumerate(tasks):
            row_id = f"work-queue-row-{index}"
            self.tree.insert(
                "",
                tk.END,
                iid=row_id,
                values=(
                    task.priority.value,
                    task.title,
                    task.display_identity,
                    task.reason,
                    task.action_label,
                ),
            )
            self._row_task_ids[row_id] = task.task_id
        if tasks:
            self.state_var.set(f"{len(tasks)} task{'s' if len(tasks) != 1 else ''} shown.")
            self.status_var.set("Select a task to address it.")
        elif self._projection.tasks:
            self.state_var.set("No tasks in this category.")
            self.status_var.set("Choose another category or refresh.")
        else:
            self.state_var.set(
                "Nothing needs attention. "
                "Your current collection has no unresolved Work Queue tasks."
            )
            self.status_var.set("Nothing needs attention.")

    def _selected_task(self) -> WorkQueueTask | None:
        if self._projection is None:
            return None
        selection = self.tree.selection()
        if not selection:
            return None
        task_id = self._row_task_ids.get(selection[0])
        return next(
            (task for task in self._projection.tasks if task.task_id == task_id),
            None,
        )

    def on_selection_changed(self, event=None) -> None:
        task = self._selected_task()
        if task is None:
            self.action_button.configure(state=tk.DISABLED, text="Open Item")
            return
        self.action_button.configure(state=tk.NORMAL, text=task.action_label)
        self.status_var.set(f"Selected: {task.title}.")

    def activate_selected_task(self, event=None) -> None:
        selected_task = self._selected_task()
        if selected_task is None:
            self.status_var.set("Select a task to address it.")
            return

        collection = self._collection_provider()
        if collection.load_state is not CollectionLoadState.LOADED:
            self.refresh()
            return
        try:
            reference = self._task_references[selected_task.task_id]
            current_item = reference.resolve(collection)
        except (ValueError, KeyError):
            self.refresh(status_message="This task is stale. Select a current task after refresh.")
            return
        try:
            fresh_projection = derive_work_queue(collection)
        except WorkQueueProjectionError:
            self.refresh()
            return
        fresh_task = next(
            (
                task
                for task in fresh_projection.tasks
                if task.task_id == selected_task.task_id
            ),
            None,
        )
        if fresh_task is None:
            self.refresh(status_message="This task has already been resolved.")
            return
        self._open_editor(
            current_item,
            lambda *args: self._after_save(fresh_task.task_id, fresh_task.title, reference),
        )

    def _after_save(self, task_id: str, task_title: str, reference=None) -> None:
        if not self.is_open():
            return
        collection = self._collection_provider()
        if reference is not None:
            try:
                reference.resolve(collection)
            except ValueError:
                self.refresh(status_message="The active item changed; select a current task.")
                return
        try:
            projection = derive_work_queue(collection)
        except WorkQueueProjectionError:
            self.refresh()
            return
        remains = any(task.task_id == task_id for task in projection.tasks)
        status = (
            "Saved. This task still needs attention."
            if remains
            else f"Resolved: {task_title}."
        )
        self.refresh(status_message=status)


__all__ = [
    "WorkQueueFilter",
    "WorkQueueWindow",
    "default_work_queue_filter",
    "filtered_work_queue_tasks",
]
