"""Detached startup Collection orientation; maintenance remains Work Queue-owned."""
from dataclasses import dataclass
from datetime import date
import re

from coin_collection import CoinCollection, CollectionLoadState, IdentificationStatus, ItemType
from collection_item_reference import CollectionItemReference
from collector_work_queue import WorkQueueTask, WorkQueueProjectionError, derive_work_queue


@dataclass(frozen=True)
class CollectionResumeRow:
    reference: CollectionItemReference
    label: str
    status: str
    recorded_date: str
    task: WorkQueueTask | None


def collection_resume_rows(collection: CoinCollection) -> tuple[CollectionResumeRow, ...]:
    """Read recorded fields and detached queue metadata without normalization or I/O."""
    try:
        projection = derive_work_queue(collection)
    except WorkQueueProjectionError as error:
        raise ValueError("Collection orientation is unavailable.") from error
    tasks = {}
    for task in projection.tasks:
        tasks.setdefault(task.item_id, task)
    rows = []
    for item in collection.items if projection.collection_state is CollectionLoadState.LOADED else ():
        reference = CollectionItemReference.capture(collection, item)
        status = item.identification_status
        if not isinstance(status, IdentificationStatus):
            raise ValueError("Collection orientation requires a supported identification status.")
        unknown_label = "Unidentified coin" if item.item_type is ItemType.COIN else "Unidentified banknote"
        if status is IdentificationStatus.UNIDENTIFIED:
            label = unknown_label
        else:
            components = [str(item.issuer or "").strip() or str(item.country or "").strip(),
                          str(item.denomination or "").strip(), str(item.year or "").strip()]
            label = str(item.title or "").strip() or " · ".join(part for part in components if part) or unknown_label
        recorded_date = "Unknown"
        match = re.match(r"^(\d{4}-\d{2}-\d{2})", str(item.date_added or ""))
        if match:
            try:
                recorded_date = date.fromisoformat(match.group(1)).isoformat()
            except ValueError:
                pass
        rows.append(CollectionResumeRow(reference, label, status.value.capitalize(),
                                        recorded_date, tasks.get(item.id)))
    rows.sort(key=lambda row: (row.recorded_date == "Unknown",
                              -date.fromisoformat(row.recorded_date).toordinal() if row.recorded_date != "Unknown" else 0,
                              row.reference.item_id))
    return tuple(rows)
