"""Map completed OCR review output to one durable collection item.

This is the deliberately small application boundary between the immutable,
human-reviewed OCR workflow and the existing production collection API.
Draft creation is pure; collection mutation happens only in ``persist`` after
the desktop operator has explicitly confirmed the draft.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from coin_collection import CoinCollection, CoinItem

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
) -> CoinItem:
    """Persist one already-confirmed draft through ``CoinCollection``."""

    if not isinstance(collection, CoinCollection):
        raise TypeError("collection must be a CoinCollection.")
    if not isinstance(draft, ReviewedCoinDraft):
        raise TypeError("draft must be a ReviewedCoinDraft.")
    draft.validate()

    target_id = item_id or collection.generate_item_id()
    if collection.get_item(target_id) is not None:
        raise ReviewedCoinIdentityCollisionError(
            f"Collection record ID already exists: {target_id}."
        )

    item = CoinItem(
        id=target_id,
        image_path="",
        country=draft.country,
        denomination=draft.denomination,
        year=draft.year,
        grade="",
        notes="",
        date_added=date_added or datetime.now().isoformat(),
        auto_detected=False,
    )
    if not collection.add_item(item):
        detail = collection.last_save_error or "collection save failed"
        raise ReviewedCoinPersistenceError(
            f"The reviewed coin was not saved: {detail}"
        )
    return item
