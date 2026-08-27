"""Map completed OCR review output to one durable collection item.

This is the deliberately small application boundary between the immutable,
human-reviewed OCR workflow and the existing production collection API.
Draft creation is pure; collection mutation happens only in ``persist`` after
the desktop operator has explicitly confirmed the draft.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from coin_collection import CoinCollection, CoinItem

from .image_store import ManagedCollectionImageStore, OWNER_FILENAME
from .lock import PackageImportLock
from .package import CapturePackageValidator
from .snapshot import CapturePackageSnapshotService
from .workflow_confirmed_observation_mapper import (
    ConfirmedObservationMapper,
    ConfirmedObservationMappingInput,
)
from .workflow_confirmed_observation_readiness import (
    require_confirmed_observation_readiness,
)
from .workflow_ocr_review_models import OCRReportReview
from .workflow_ocr_review_service import OCRReviewMode
from .workflow_ocr_review_session import (
    OCRReviewSessionConflictResolutionRequest,
    OCRReviewSessionRequest,
    OCRReviewSessionService,
)
from .workflow_ocr_models import OCRMetadataReport


REQUIRED_COLLECTION_FIELDS = ("country", "denomination", "year")


class ReviewedCoinCollectionEntryError(ValueError):
    """A reviewed OCR result cannot safely enter the collection."""


class IncompleteReviewedCoinError(ReviewedCoinCollectionEntryError):
    """The operator review is incomplete or has unresolved conflicts."""


class MissingRequiredReviewedCoinFieldError(
    ReviewedCoinCollectionEntryError
):
    """A canonical coin field required by this bridge is absent."""


class MultipleReviewedCoinsError(ReviewedCoinCollectionEntryError):
    """One confirmation attempted to save more than one source coin."""


class ReviewedCoinIdentityCollisionError(ReviewedCoinCollectionEntryError):
    """The generated collection record ID already exists."""


class ReviewedCoinPersistenceError(ReviewedCoinCollectionEntryError):
    """The existing collection persistence operation failed."""


class ReviewedCoinRecoveryRequiredError(ReviewedCoinPersistenceError):
    """A reviewed save failed without proving a clean terminal state."""

    safe_message = (
        "The reviewed coin save did not reach a proven clean state. "
        "Recovery or operator attention is required."
    )

    def __init__(self) -> None:
        super().__init__(self.safe_message)


@dataclass(frozen=True, slots=True)
class ReviewedCoinDraft:
    """The single canonical collection record awaiting confirmation."""

    source_coin_id: str
    country: str
    denomination: str
    year: str
    unmapped_fields: tuple[tuple[str, str], ...] = ()

    def validate(self) -> None:
        if not isinstance(self.source_coin_id, str) or not self.source_coin_id.strip():
            raise ReviewedCoinCollectionEntryError(
                "The reviewed source coin ID is missing."
            )
        missing = tuple(
            name
            for name in REQUIRED_COLLECTION_FIELDS
            if not isinstance(getattr(self, name), str)
            or not getattr(self, name).strip()
        )
        if missing:
            raise MissingRequiredReviewedCoinFieldError(
                "Required reviewed field(s) missing: " + ", ".join(missing)
            )


def create_reviewed_coin_draft(
    *,
    source_report: OCRMetadataReport,
    report_review: OCRReportReview,
    conflict_resolutions: tuple[
        OCRReviewSessionConflictResolutionRequest, ...
    ] = (),
) -> ReviewedCoinDraft:
    """Validate a complete review and produce one non-mutating draft."""

    session_result = OCRReviewSessionService().run(
        request=OCRReviewSessionRequest(
            source_report=source_report,
            review=report_review,
            mode=OCRReviewMode.STRICT_COMPLETE,
            conflict_resolution_requests=conflict_resolutions,
        )
    )
    if not session_result.is_complete:
        raise IncompleteReviewedCoinError(
            "OCR review must be complete and every conflict resolved."
        )

    observation_sets = ConfirmedObservationMapper().map_review_session(
        ConfirmedObservationMappingInput(
            session_result=session_result,
            source_report=source_report,
            report_review=report_review,
        )
    )
    if len(observation_sets) != 1:
        raise MultipleReviewedCoinsError(
            "Exactly one reviewed source coin may be saved at a time."
        )

    confirmed = require_confirmed_observation_readiness(
        observation_sets[0]
    )
    values = {
        observation.field_name: (
            observation.canonical_value
            if observation.canonical_value is not None
            else observation.submitted_value
        ).strip()
        for observation in confirmed.observations
    }
    missing = tuple(
        name for name in REQUIRED_COLLECTION_FIELDS if not values.get(name)
    )
    if missing:
        raise MissingRequiredReviewedCoinFieldError(
            "Required reviewed field(s) missing: " + ", ".join(missing)
        )

    draft = ReviewedCoinDraft(
        source_coin_id=confirmed.source_coin_id,
        country=values["country"],
        denomination=values["denomination"],
        year=values["year"],
        unmapped_fields=tuple(
            sorted(
                (name, value)
                for name, value in values.items()
                if name not in REQUIRED_COLLECTION_FIELDS
            )
        ),
    )
    draft.validate()
    return draft


def persist_reviewed_coin(
    *,
    collection: CoinCollection,
    draft: ReviewedCoinDraft,
    item_id: str | None = None,
    date_added: str | None = None,
    source_package_path: str | Path | None = None,
    managed_image_store: ManagedCollectionImageStore | None = None,
    snapshot_service: CapturePackageSnapshotService | None = None,
    import_lock_path: str | Path = "data/imports/package_import.lock",
) -> CoinItem:
    """Persist one already-confirmed draft through ``CoinCollection``."""

    if not isinstance(collection, CoinCollection):
        raise TypeError("collection must be a CoinCollection.")
    if not isinstance(draft, ReviewedCoinDraft):
        raise TypeError("draft must be a ReviewedCoinDraft.")
    draft.validate()

    if source_package_path is not None:
        return _persist_reviewed_coin_with_managed_photos(
            collection=collection,
            draft=draft,
            source_package_path=Path(source_package_path),
            managed_image_store=(
                managed_image_store
                if managed_image_store is not None
                else ManagedCollectionImageStore("coin_photos/collection")
            ),
            snapshot_service=(
                snapshot_service
                if snapshot_service is not None
                else CapturePackageSnapshotService("data/imports/snapshots")
            ),
            import_lock_path=Path(import_lock_path),
            item_id=item_id,
            date_added=date_added,
        )
    if managed_image_store is not None or snapshot_service is not None:
        raise ValueError(
            "managed image services require source_package_path."
        )

    target_id = item_id or collection.generate_item_id()
    if collection.get_item(target_id) is not None:
        raise ReviewedCoinIdentityCollisionError(
            f"Collection record ID already exists: {target_id}."
        )

    item = _build_coin_item(
        draft=draft,
        item_id=target_id,
        date_added=date_added,
    )
    if not collection.add_item(item):
        detail = collection.last_save_error or "collection save failed"
        raise ReviewedCoinPersistenceError(
            f"The reviewed coin was not saved: {detail}"
        )
    return item


def _build_coin_item(
    *,
    draft: ReviewedCoinDraft,
    item_id: str,
    date_added: str | None,
    photos=(),
) -> CoinItem:
    photo_list = list(photos)
    image_path = photo_list[0].path if photo_list else ""
    return CoinItem(
        id=item_id,
        image_path=image_path,
        country=draft.country,
        denomination=draft.denomination,
        year=draft.year,
        grade="",
        notes="",
        date_added=date_added or datetime.now().isoformat(),
        auto_detected=False,
        photos=photo_list,
    )


def _persist_reviewed_coin_with_managed_photos(
    *,
    collection: CoinCollection,
    draft: ReviewedCoinDraft,
    source_package_path: Path,
    managed_image_store: ManagedCollectionImageStore,
    snapshot_service: CapturePackageSnapshotService,
    import_lock_path: Path,
    item_id: str | None,
    date_added: str | None,
) -> CoinItem:
    import_id = str(uuid4())
    ownership_token = str(uuid4())
    target_id = item_id or str(uuid4())
    lock = PackageImportLock.acquire(import_lock_path, import_id=import_id)
    snapshot = None
    plan = None
    created: list[str] = []
    try:
        if collection.get_item(target_id) is not None:
            raise ReviewedCoinIdentityCollisionError(
                f"Collection record ID already exists: {target_id}."
            )
        try:
            package_payload = source_package_path.read_bytes()
        except OSError as error:
            raise ReviewedCoinPersistenceError(
                "The reviewed coin images are no longer available."
            ) from error
        snapshot = snapshot_service.create_snapshot(
            source_package_path,
            sha256(package_payload).hexdigest(),
        )
        package = CapturePackageValidator().validate_snapshot(
            snapshot,
            source_package_path.name,
        )
        plan = managed_image_store.plan(
            package,
            import_id=import_id,
            ownership_token=ownership_token,
            source_to_desktop={draft.source_coin_id: target_id},
        )
        photos_by_source = managed_image_store.copy(
            snapshot,
            package,
            plan,
            created.append,
            import_lock=lock,
        )
        photos = photos_by_source.get(draft.source_coin_id, ())
        if len(photos) != 2:
            raise ReviewedCoinPersistenceError(
                "Both reviewed coin images must be retained."
            )
        snapshot.cleanup()
        snapshot = None
        item = _build_coin_item(
            draft=draft,
            item_id=target_id,
            date_added=date_added,
            photos=photos,
        )
        if not collection.add_item(item, import_lock=lock):
            detail = collection.last_save_error or "collection save failed"
            raise ReviewedCoinPersistenceError(
                f"The reviewed coin was not saved: {detail}"
            )
        return item
    except Exception as error:
        cleanup_error = None
        if plan is not None:
            marker = f"{plan.import_root_relative_path}/{OWNER_FILENAME}"
            try:
                managed_image_store.cleanup(
                    plan,
                    import_lock=lock,
                    ownership_recorded=marker in created,
                )
            except Exception as failure:
                cleanup_error = failure
        if cleanup_error is not None:
            raise ReviewedCoinRecoveryRequiredError() from cleanup_error
        if isinstance(error, ReviewedCoinCollectionEntryError):
            raise
        raise ReviewedCoinPersistenceError(
            "The reviewed coin and its images were not saved."
        ) from error
    finally:
        try:
            if snapshot is not None and snapshot.is_active:
                snapshot.cleanup()
        finally:
            lock.release()
