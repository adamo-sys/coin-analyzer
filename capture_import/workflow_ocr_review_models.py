"""Immutable human-review contracts for advisory OCR metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


_ALLOWED_FIELDS = frozenset(
    {
        "year",
        "denomination",
        "country",
        "monarch",
        "mintmark",
        "series_type",
        "banknote_prefix",
        "certification_number",
        "silver_indicator",
        "variety_keyword",
    }
)

_MAX_ID_LENGTH = 256
_MAX_VALUE_LENGTH = 512
_MAX_REASON_LENGTH = 2000


class OCRReviewDecision(str, Enum):
    """Explicit human decisions for one OCR field candidate."""

    APPROVE = "APPROVE"
    CORRECT = "CORRECT"
    REJECT = "REJECT"
    DEFER = "DEFER"


def _validate_text(
    value: object,
    *,
    name: str,
    maximum_length: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")

    if not allow_empty and not value.strip():
        raise ValueError(f"{name} must not be empty.")

    if len(value) > maximum_length:
        raise ValueError(
            f"{name} must not exceed {maximum_length} characters."
        )

    if any(ord(character) < 32 and character not in "\t" for character in value):
        raise ValueError(f"{name} contains prohibited control characters.")

    return value


@dataclass(frozen=True, slots=True)
class OCRFieldReview:
    """One auditable human decision for one OCR field candidate."""

    source_coin_id: str
    image_role: str
    artifact_key: str
    provider_id: str
    field_name: str
    original_value: str
    decision: OCRReviewDecision
    reviewed_value: str | None
    reason: str

    def validate(self) -> None:
        _validate_text(
            self.source_coin_id,
            name="source_coin_id",
            maximum_length=_MAX_ID_LENGTH,
        )
        _validate_text(
            self.image_role,
            name="image_role",
            maximum_length=_MAX_ID_LENGTH,
        )
        _validate_text(
            self.artifact_key,
            name="artifact_key",
            maximum_length=_MAX_ID_LENGTH,
        )
        _validate_text(
            self.provider_id,
            name="provider_id",
            maximum_length=_MAX_ID_LENGTH,
        )
        _validate_text(
            self.field_name,
            name="field_name",
            maximum_length=_MAX_ID_LENGTH,
        )
        _validate_text(
            self.original_value,
            name="original_value",
            maximum_length=_MAX_VALUE_LENGTH,
        )
        _validate_text(
            self.reason,
            name="reason",
            maximum_length=_MAX_REASON_LENGTH,
        )

        if self.field_name not in _ALLOWED_FIELDS:
            raise ValueError(
                f"Unsupported OCR review field: {self.field_name!r}."
            )

        if self.field_name == "grade":
            raise ValueError("OCR review must not accept grade fields.")

        if not isinstance(self.decision, OCRReviewDecision):
            raise TypeError(
                "decision must be an OCRReviewDecision."
            )

        if self.reviewed_value is not None:
            _validate_text(
                self.reviewed_value,
                name="reviewed_value",
                maximum_length=_MAX_VALUE_LENGTH,
            )

        if self.decision is OCRReviewDecision.APPROVE:
            if self.reviewed_value != self.original_value:
                raise ValueError(
                    "APPROVE requires reviewed_value to equal "
                    "original_value."
                )

        elif self.decision is OCRReviewDecision.CORRECT:
            if self.reviewed_value is None:
                raise ValueError(
                    "CORRECT requires reviewed_value."
                )
            if self.reviewed_value == self.original_value:
                raise ValueError(
                    "CORRECT requires a value different from "
                    "original_value."
                )

        elif self.reviewed_value is not None:
            raise ValueError(
                f"{self.decision.value} requires reviewed_value to be None."
            )

    @property
    def identity_key(self) -> tuple[str, ...]:
        return (
            self.source_coin_id,
            self.image_role,
            self.artifact_key,
            self.provider_id,
            self.field_name,
            self.original_value,
        )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "source_coin_id": self.source_coin_id,
            "image_role": self.image_role,
            "artifact_key": self.artifact_key,
            "provider_id": self.provider_id,
            "field_name": self.field_name,
            "original_value": self.original_value,
            "decision": self.decision.value,
            "reviewed_value": self.reviewed_value,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class OCRReportReview:
    """Immutable aggregate of human OCR-field review decisions."""

    reviewer_id: str
    field_reviews: tuple[OCRFieldReview, ...]

    def validate(self) -> None:
        _validate_text(
            self.reviewer_id,
            name="reviewer_id",
            maximum_length=_MAX_ID_LENGTH,
        )

        if not isinstance(self.field_reviews, tuple):
            raise TypeError("field_reviews must be a tuple.")

        if not self.field_reviews:
            raise ValueError(
                "field_reviews must contain at least one review."
            )

        identities: set[tuple[str, ...]] = set()

        for review in self.field_reviews:
            if not isinstance(review, OCRFieldReview):
                raise TypeError(
                    "field_reviews must contain only OCRFieldReview values."
                )

            review.validate()

            if review.identity_key in identities:
                raise ValueError(
                    "Duplicate OCR field review target."
                )

            identities.add(review.identity_key)

    def _count(self, decision: OCRReviewDecision) -> int:
        return sum(
            review.decision is decision
            for review in self.field_reviews
        )

    @property
    def approved_count(self) -> int:
        return self._count(OCRReviewDecision.APPROVE)

    @property
    def corrected_count(self) -> int:
        return self._count(OCRReviewDecision.CORRECT)

    @property
    def rejected_count(self) -> int:
        return self._count(OCRReviewDecision.REJECT)

    @property
    def deferred_count(self) -> int:
        return self._count(OCRReviewDecision.DEFER)

    @property
    def has_deferred_reviews(self) -> bool:
        return self.deferred_count > 0

    @property
    def is_complete(self) -> bool:
        return not self.has_deferred_reviews

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "reviewer_id": self.reviewer_id,
            "field_reviews": [
                review.to_dict()
                for review in self.field_reviews
            ],
            "summary": {
                "approved_count": self.approved_count,
                "corrected_count": self.corrected_count,
                "rejected_count": self.rejected_count,
                "deferred_count": self.deferred_count,
                "is_complete": self.is_complete,
            },
        }