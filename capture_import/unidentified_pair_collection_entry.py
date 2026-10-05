"""Persist a confirmed Phone Intake pair without asserting an identity."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from coin_collection import CoinCollection, CoinItem, normalize_acquisition_values
from phone_intake import PhoneIntake

from .image_store import ManagedCollectionImageStore
from .reviewed_coin_collection_entry import (
    ReviewedCoinRecoveryRequiredError,
    _persist_coin_with_managed_photos,
)
from .snapshot import CapturePackageSnapshotService
from .standalone_image_intake import create_temporary_capture_package


class UnidentifiedPairReconciliationRequiredError(ValueError):
    """A reserved pair could not be proven ready or finalized; do not resave."""

    def __init__(self, item_id: str | None = None) -> None:
        self.item_id = item_id
        super().__init__(
            f"Coin {item_id} was saved; reconcile this pair before any further action."
            if item_id else "Save outcome requires Phone Intake reconciliation; do not resave this pair."
        )


def save_unidentified_phone_pair(
    *,
    store: PhoneIntake,
    collection: CoinCollection,
    pair_id: str,
    expected_images: dict[str, Any],
    acquisition: Mapping[str, Any] | None = None,
    notes: str = "",
) -> CoinItem:
    """Use the existing reservation, managed-media commit, and reconciliation path."""
    values = normalize_acquisition_values(acquisition or {})
    front = expected_images["front"]["path"]
    reverse = expected_images["reverse"]["path"]
    source = create_temporary_capture_package(front_path=front, reverse_path=reverse)
    try:
        intent = store.reserve_unidentified(pair_id, collection.storage_path, expected_images)
        try:
            item = persist_unidentified_pair(
                collection=collection,
                source_package_path=source.path,
                item_id=intent["item_id"],
                date_added=intent["date_added"],
                acquisition=values,
                notes=notes,
            )
        except Exception as error:
            if isinstance(error, ReviewedCoinRecoveryRequiredError):
                raise UnidentifiedPairReconciliationRequiredError() from error
            try:
                store.clean_save_failure(pair_id, collection.storage_path)
            except Exception as cleanup_error:
                raise UnidentifiedPairReconciliationRequiredError() from cleanup_error
            raise
        try:
            store.complete(pair_id, collection.storage_path)
        except Exception as error:
            raise UnidentifiedPairReconciliationRequiredError(item.id) from error
        return item
    finally:
        source.release()


def persist_unidentified_pair(
    *,
    collection: CoinCollection,
    source_package_path: str | Path,
    item_id: str,
    date_added: str,
    acquisition: Mapping[str, Any] | None = None,
    notes: str = "",
    managed_image_store: ManagedCollectionImageStore | None = None,
    snapshot_service: CapturePackageSnapshotService | None = None,
    import_lock_path: str | Path = "data/imports/package_import.lock",
) -> CoinItem:
    """Commit the one-coin temporary pair package with blank identity fields."""
    if not isinstance(collection, CoinCollection):
        raise TypeError("collection must be a CoinCollection.")
    if not isinstance(notes, str):
        raise ValueError("Notes must be text.")
    values = normalize_acquisition_values(acquisition or {})

    def build_item(target_id: str, photos: tuple) -> CoinItem:
        return CoinItem(
            id=target_id,
            image_path=photos[0].path,
            country="",
            denomination="",
            year="",
            type_design="",
            grade="",
            notes=notes,
            date_added=date_added or datetime.now().isoformat(),
            auto_detected=False,
            photos=list(photos),
            **values,
        )

    return _persist_coin_with_managed_photos(
        collection=collection,
        source_package_path=Path(source_package_path),
        source_coin_id="coin-1",  # The one-coin temporary pair package adapter.
        build_item=build_item,
        managed_image_store=managed_image_store or ManagedCollectionImageStore("coin_photos/collection"),
        snapshot_service=snapshot_service or CapturePackageSnapshotService("data/imports/snapshots"),
        import_lock_path=Path(import_lock_path),
        item_id=item_id,
    )
