"""Pure Collector Work Queue projection over authoritative collection state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
import re

from coin_collection import (
    CoinCollection,
    CoinItem,
    CollectionLoadState,
    IdentificationStatus,
    ItemPhoto,
    ItemType,
    PhotoRole,
)


class WorkQueueTaskType(str, Enum):
    UNRESOLVED_IDENTITY = "UNRESOLVED_IDENTITY"
    MISSING_REVERSE_PHOTO = "MISSING_REVERSE_PHOTO"
    MISSING_ACQUISITION_PRICE = "MISSING_ACQUISITION_PRICE"


class WorkQueuePriority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class WorkQueueProjectionError(RuntimeError):
    """Bounded fail-closed refusal to derive a Work Queue projection."""


@dataclass(frozen=True, slots=True)
class WorkQueueTask:
    task_id: str
    task_type: WorkQueueTaskType
    rule_version: int
    item_id: str
    priority: WorkQueuePriority
    title: str
    reason: str
    display_identity: str
    action_label: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkQueueProjection:
    collection_state: CollectionLoadState
    tasks: tuple[WorkQueueTask, ...]
    counts_by_type: tuple[tuple[WorkQueueTaskType, int], ...]


@dataclass(frozen=True, slots=True)
class _EffectivePhoto:
    path: str
    role: PhotoRole


_RULE_VERSIONS: Mapping[WorkQueueTaskType, int] = MappingProxyType(
    {
        WorkQueueTaskType.UNRESOLVED_IDENTITY: 1,
        WorkQueueTaskType.MISSING_REVERSE_PHOTO: 1,
        WorkQueueTaskType.MISSING_ACQUISITION_PRICE: 1,
    }
)

_TASK_TYPE_ORDER = {
    task_type: rank for rank, task_type in enumerate(WorkQueueTaskType)
}
_PRIORITY_ORDER = {
    priority: rank for rank, priority in enumerate(WorkQueuePriority)
}
_LEADING_ISO_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def derive_work_queue(collection: CoinCollection) -> WorkQueueProjection:
    """Derive an immutable queue without mutating or persisting collection state."""
    state = collection.load_state
    if state is CollectionLoadState.MISSING:
        return _projection(state, ())
    if state is not CollectionLoadState.LOADED:
        raise WorkQueueProjectionError(
            "Work Queue projection requires a valid collection; "
            f"current state is {_bounded_state_name(state)}."
        )

    items = tuple(collection.items)
    identifiers = [_stable_item_id(item) for item in items]
    if len(set(identifiers)) != len(identifiers):
        raise WorkQueueProjectionError("Work Queue requires unique stable item IDs.")
    tasks: list[WorkQueueTask] = []
    for item in items:
        item_id = _stable_item_id(item)
        display_identity = _display_identity(item)
        for task in _tasks_for_item(item, item_id, display_identity):
            tasks.append(task)

    item_dates = {
        _stable_item_id(item): _date_sort_key(item.date_added)
        for item in items
    }
    tasks.sort(key=lambda task: _task_sort_key(task, item_dates))
    return _projection(state, tuple(tasks))


def _tasks_for_item(
    item: CoinItem, item_id: str, display_identity: str
) -> tuple[WorkQueueTask, ...]:
    tasks: list[WorkQueueTask] = []

    status = item.identification_status
    if status is IdentificationStatus.PARTIAL or status is IdentificationStatus.UNIDENTIFIED:
        reason = (
            "Identification is partial."
            if status is IdentificationStatus.PARTIAL
            else "Identification has not been established."
        )
        tasks.append(
            _task(
                WorkQueueTaskType.UNRESOLVED_IDENTITY,
                item_id,
                WorkQueuePriority.P1,
                "Confirm identity",
                reason,
                display_identity,
                "Edit identity",
                (f"identification_status={status.value}",),
            )
        )
    elif status is not IdentificationStatus.IDENTIFIED:
        raise WorkQueueProjectionError(
            "Work Queue projection refused an unsupported identification status."
        )

    item_type = item.item_type
    if item_type is ItemType.COIN:
        photos = _effective_photo_snapshot(item)
        back_count = sum(photo.role is PhotoRole.BACK for photo in photos)
        if back_count == 0:
            tasks.append(
                _task(
                    WorkQueueTaskType.MISSING_REVERSE_PHOTO,
                    item_id,
                    WorkQueuePriority.P2,
                    "Add reverse photo",
                    "No photo is assigned the Back / Reverse role.",
                    display_identity,
                    "Edit photos",
                    (f"photo_count={len(photos)}", "back_role_count=0"),
                )
            )
    elif item_type is not ItemType.BANKNOTE:
        raise WorkQueueProjectionError(
            "Work Queue projection refused an unsupported item type."
        )

    if item.purchase_price is None:
        evidence = tuple(
            marker
            for value, marker in (
                (item.shipping_cost, "shipping_cost_present"),
                (item.buyers_premium, "buyers_premium_present"),
                (item.tax, "tax_present"),
            )
            if value is not None
        )
        if evidence:
            tasks.append(
                _task(
                    WorkQueueTaskType.MISSING_ACQUISITION_PRICE,
                    item_id,
                    WorkQueuePriority.P3,
                    "Record purchase price",
                    "Purchase-related costs are recorded, but the purchase price is missing.",
                    display_identity,
                    "Edit acquisition",
                    evidence + ("purchase_price_missing",),
                )
            )

    return tuple(tasks)


def _effective_photo_snapshot(item: CoinItem) -> tuple[_EffectivePhoto, ...]:
    """Copy only path/role semantics; never normalize authoritative photo objects."""
    raw_photos: Any = item.photos
    rows = raw_photos if isinstance(raw_photos, list) else [raw_photos]
    detached: list[_EffectivePhoto] = []
    for row in rows:
        path, role = _detached_path_and_role(row)
        if path:
            detached.append(_EffectivePhoto(path, role))
    if not detached:
        legacy_path = str(item.image_path or "").strip()
        if legacy_path:
            detached.append(_EffectivePhoto(legacy_path, PhotoRole.OTHER))
    return tuple(detached)


def _detached_path_and_role(row: Any) -> tuple[str, PhotoRole]:
    if isinstance(row, ItemPhoto):
        return str(row.path or "").strip(), PhotoRole.normalize(row.role)
    if isinstance(row, str):
        return row.strip(), PhotoRole.OTHER
    if isinstance(row, Mapping):
        path = str(row.get("path") or row.get("file_path") or "").strip()
        role = row.get("role") or row.get("photo_role") or row.get("photo_type")
        return path, PhotoRole.normalize(role)
    return "", PhotoRole.OTHER


def _display_identity(item: CoinItem) -> str:
    title = _trimmed(item.title)
    if title:
        return title
    issuer = _trimmed(item.issuer)
    country = _trimmed(item.country)
    components = [issuer or country]
    components.extend((_trimmed(item.denomination), _trimmed(item.year)))
    display = " · ".join(component for component in components if component)
    if display:
        return display
    if item.item_type is ItemType.COIN:
        return "Unidentified coin"
    if item.item_type is ItemType.BANKNOTE:
        return "Unidentified banknote"
    raise WorkQueueProjectionError(
        "Work Queue projection refused an unsupported item type."
    )


def _date_sort_key(value: Any) -> tuple[int, date]:
    text = str(value or "")
    match = _LEADING_ISO_DATE.match(text)
    if match:
        try:
            return 0, date.fromisoformat(match.group(1))
        except ValueError:
            pass
    return 1, date.max


def _task_sort_key(
    task: WorkQueueTask,
    date_keys: Mapping[str, tuple[int, date]],
) -> tuple[Any, ...]:
    item_date = date_keys[task.item_id]
    return (
        _PRIORITY_ORDER[task.priority],
        _TASK_TYPE_ORDER[task.task_type],
        *item_date,
        task.item_id,
    )


def _task(
    task_type: WorkQueueTaskType,
    item_id: str,
    priority: WorkQueuePriority,
    title: str,
    reason: str,
    display_identity: str,
    action_label: str,
    evidence: tuple[str, ...],
) -> WorkQueueTask:
    version = _RULE_VERSIONS[task_type]
    return WorkQueueTask(
        task_id=f"work-queue:{version}:{task_type.value}:{item_id}",
        task_type=task_type,
        rule_version=version,
        item_id=item_id,
        priority=priority,
        title=title,
        reason=reason,
        display_identity=display_identity,
        action_label=action_label,
        evidence=evidence,
    )


def _projection(
    state: CollectionLoadState, tasks: tuple[WorkQueueTask, ...]
) -> WorkQueueProjection:
    return WorkQueueProjection(
        collection_state=state,
        tasks=tasks,
        counts_by_type=tuple(
            (task_type, sum(task.task_type is task_type for task in tasks))
            for task_type in WorkQueueTaskType
        ),
    )


def _stable_item_id(item: CoinItem) -> str:
    if not isinstance(item.id, str) or not item.id.strip():
        raise WorkQueueProjectionError(
            "Work Queue projection requires a nonblank stable item ID."
        )
    return item.id


def _bounded_state_name(state: Any) -> str:
    return state.value if isinstance(state, CollectionLoadState) else "UNSUPPORTED"


def _trimmed(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "WorkQueuePriority",
    "WorkQueueProjection",
    "WorkQueueProjectionError",
    "WorkQueueTask",
    "WorkQueueTaskType",
    "derive_work_queue",
]
