"""Versioned immutable contracts for persisted OCR review sessions.

This module defines schema and repository boundaries only.  It performs no
filesystem, database, environment, GUI, OCR, or collection work.  Persisted
state contains source facts and explicit human decisions; consolidation,
conflict targets, final projection, and Unit 1A presentation state are
recomputed through the existing Sprint 10 service.

The envelope currently requires ``reviewer_id`` because the existing
``OCRReportReview`` domain contract requires a nonblank reviewer identity.
That requirement is inherited domain behavior, not a permanent persistence
policy decision.  The same aggregate currently requires at least one field
review, so persisting a session before its first field review remains explicit
technical debt.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
    OCRConflictResolutionRequest,
)
from capture_import.workflow_ocr_consolidation import OCRConsolidationStatus
from capture_import.workflow_ocr_models import (
    ALLOWED_OCR_FIELDS,
    OCRConflict,
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRObservation,
    OCRReviewStatus,
)
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_service import OCRReviewMode
from capture_import.workflow_ocr_review_session import (
    OCRReviewSessionConflictResolutionRequest,
    OCRReviewSessionRequest,
    OCRReviewSessionResult,
    OCRReviewSessionService,
)


CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION = "1.0"

_ENVELOPE_FIELDS = frozenset(
    {
        "schema_version",
        "session_id",
        "source_fingerprint",
        "lifecycle_state",
        "review_mode",
        "reviewer_id",
        "source_report",
        "field_reviews",
        "conflict_resolutions",
    }
)
_REPORT_FIELDS = frozenset(
    {
        "provider_available",
        "observation_count",
        "candidate_count",
        "conflict_count",
        "review_status",
        "manual_review_required",
        "observations",
        "candidates",
        "conflicts",
    }
)
_OBSERVATION_FIELDS = frozenset(
    {
        "source_coin_id",
        "image_role",
        "artifact_key",
        "provider_id",
        "raw_text",
        "confidence_score",
    }
)
_CANDIDATE_FIELDS = frozenset(
    {
        "source_coin_id",
        "image_role",
        "artifact_key",
        "provider_id",
        "field_name",
        "raw_text",
        "normalized_value",
        "confidence_score",
        "evidence",
        "review_status",
    }
)
_CONFLICT_FIELDS = frozenset(
    {
        "source_coin_id",
        "field_name",
        "candidate_values",
        "reason",
        "review_status",
    }
)
_FIELD_REVIEW_FIELDS = frozenset(
    {
        "source_coin_id",
        "image_role",
        "artifact_key",
        "provider_id",
        "field_name",
        "original_value",
        "decision",
        "reviewed_value",
        "reason",
    }
)
_STORED_RESOLUTION_FIELDS = frozenset(
    {
        "source_coin_id",
        "field_name",
        "decision",
        "value",
    }
)

_MAX_SESSION_ID_CHARS = 256
_MAX_REVIEWER_ID_CHARS = 256
_MAX_SOURCE_FINGERPRINT_CHARS = 64


class UnsupportedOCRReviewSessionSchemaVersion(ValueError):
    """The envelope is well formed but uses an unsupported schema version."""


class OCRReviewSessionLifecycle(str, Enum):
    """Conservative persisted lifecycle states for an OCR review session."""

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


def _object(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a JSON object.")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} keys must be strings.")
    return value


def _fields(
    value: Mapping[str, Any],
    required: frozenset[str],
    name: str,
) -> None:
    missing = required.difference(value)
    if missing:
        raise ValueError(
            f"{name} is missing fields: {', '.join(sorted(missing))}."
        )
    unknown = set(value).difference(required)
    if unknown:
        raise ValueError(
            f"{name} contains unknown fields: "
            f"{', '.join(sorted(unknown))}."
        )


def _string(
    value: object,
    name: str,
    *,
    maximum: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string.")
    if not allow_empty and not value.strip():
        raise ValueError(f"{name} must not be blank.")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds its character limit.")
    return value


def _optional_string(
    value: object,
    name: str,
    *,
    maximum: int,
) -> str | None:
    if value is None:
        return None
    return _string(value, name, maximum=maximum)


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean.")
    return value


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")
    if value < 0:
        raise ValueError(f"{name} must not be negative.")
    return value


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric.")
    return float(value)


def _list(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list.")
    return value


def _enum(enum_type: type[Enum], value: object, name: str) -> Enum:
    text = _string(value, name, maximum=128)
    try:
        return enum_type(text)
    except ValueError as exc:
        raise ValueError(f"{name} is unsupported.") from exc


def _review_key(review: OCRFieldReview) -> tuple[str, ...]:
    return review.identity_key


@dataclass(frozen=True, slots=True)
class OCRStoredConflictResolution:
    """One explicit conflict decision without a derived consolidated target."""

    source_coin_id: str
    field_name: str
    decision: OCRConflictResolutionDecision
    value: str | None

    @property
    def identity(self) -> tuple[str, str]:
        return (self.source_coin_id, self.field_name)

    def validate(self) -> None:
        _string(
            self.source_coin_id,
            "source_coin_id",
            maximum=16_384,
        )
        field_name = _string(
            self.field_name,
            "field_name",
            maximum=64,
        )
        if field_name not in ALLOWED_OCR_FIELDS or field_name == "grade":
            raise ValueError("field_name is not supported.")
        OCRConflictResolutionRequest(
            decision=self.decision,
            value=self.value,
        ).validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "source_coin_id": self.source_coin_id,
            "field_name": self.field_name,
            "decision": self.decision.value,
            "value": self.value,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "OCRStoredConflictResolution":
        data = _object(value, "OCRStoredConflictResolution")
        _fields(
            data,
            _STORED_RESOLUTION_FIELDS,
            "OCRStoredConflictResolution",
        )
        result = cls(
            source_coin_id=_string(
                data["source_coin_id"],
                "source_coin_id",
                maximum=16_384,
            ),
            field_name=_string(
                data["field_name"],
                "field_name",
                maximum=64,
            ),
            decision=_enum(
                OCRConflictResolutionDecision,
                data["decision"],
                "decision",
            ),
            value=_optional_string(
                data["value"],
                "value",
                maximum=512,
            ),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class OCRReviewSessionReconstruction:
    """Immutable inputs accepted by Unit 1B and Sprint 10 orchestration."""

    source_report: OCRMetadataReport
    review: OCRReportReview
    conflict_resolutions: tuple[
        OCRReviewSessionConflictResolutionRequest,
        ...,
    ]
    mode: OCRReviewMode

    def validate(self) -> None:
        OCRReviewSessionRequest(
            source_report=self.source_report,
            review=self.review,
            mode=self.mode,
            conflict_resolution_requests=self.conflict_resolutions,
        ).validate()

    def to_session_request(self) -> OCRReviewSessionRequest:
        self.validate()
        return OCRReviewSessionRequest(
            source_report=self.source_report,
            review=self.review,
            mode=self.mode,
            conflict_resolution_requests=self.conflict_resolutions,
        )


@dataclass(frozen=True, slots=True)
class OCRReviewSessionEnvelope:
    """Versioned source facts and explicit decisions for one review session."""

    schema_version: str
    session_id: str
    source_fingerprint: str
    lifecycle_state: OCRReviewSessionLifecycle
    review_mode: OCRReviewMode
    reviewer_id: str
    source_report: OCRMetadataReport
    field_reviews: tuple[OCRFieldReview, ...]
    conflict_resolutions: tuple[OCRStoredConflictResolution, ...] = ()

    def validate(self) -> None:
        if not isinstance(self.schema_version, str):
            raise ValueError("schema_version must be a string.")
        if (
            self.schema_version
            != CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION
        ):
            raise UnsupportedOCRReviewSessionSchemaVersion(
                f"Unsupported OCR review session schema version: "
                f"{self.schema_version!r}."
            )
        _string(
            self.session_id,
            "session_id",
            maximum=_MAX_SESSION_ID_CHARS,
        )
        fingerprint = _string(
            self.source_fingerprint,
            "source_fingerprint",
            maximum=_MAX_SOURCE_FINGERPRINT_CHARS,
        )
        if (
            len(fingerprint) != _MAX_SOURCE_FINGERPRINT_CHARS
            or any(
                character not in "0123456789abcdef"
                for character in fingerprint
            )
        ):
            raise ValueError(
                "source_fingerprint must be a 64-character lowercase "
                "hexadecimal value."
            )
        if not isinstance(
            self.lifecycle_state,
            OCRReviewSessionLifecycle,
        ):
            raise TypeError(
                "lifecycle_state must be an OCRReviewSessionLifecycle."
            )
        if not isinstance(self.review_mode, OCRReviewMode):
            raise TypeError("review_mode must be an OCRReviewMode.")
        _string(
            self.reviewer_id,
            "reviewer_id",
            maximum=_MAX_REVIEWER_ID_CHARS,
        )
        if not isinstance(self.source_report, OCRMetadataReport):
            raise TypeError(
                "source_report must be an OCRMetadataReport."
            )
        if not isinstance(self.field_reviews, tuple):
            raise TypeError("field_reviews must be a tuple.")
        if not isinstance(self.conflict_resolutions, tuple):
            raise TypeError("conflict_resolutions must be a tuple.")

        self.source_report.validate()
        review = OCRReportReview(
            reviewer_id=self.reviewer_id,
            field_reviews=self.field_reviews,
        )
        review.validate()

        identities: set[tuple[str, str]] = set()
        for resolution in self.conflict_resolutions:
            if not isinstance(
                resolution,
                OCRStoredConflictResolution,
            ):
                raise TypeError(
                    "conflict_resolutions must contain "
                    "OCRStoredConflictResolution values."
                )
            resolution.validate()
            if resolution.identity in identities:
                raise ValueError(
                    "Duplicate stored conflict resolution identity."
                )
            identities.add(resolution.identity)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        ordered_reviews = tuple(
            sorted(self.field_reviews, key=_review_key)
        )
        ordered_resolutions = tuple(
            sorted(
                self.conflict_resolutions,
                key=lambda item: item.identity,
            )
        )
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "source_fingerprint": self.source_fingerprint,
            "lifecycle_state": self.lifecycle_state.value,
            "review_mode": self.review_mode.value,
            "reviewer_id": self.reviewer_id,
            "source_report": self.source_report.to_dict(),
            "field_reviews": [
                review.to_dict() for review in ordered_reviews
            ],
            "conflict_resolutions": [
                resolution.to_dict()
                for resolution in ordered_resolutions
            ],
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "OCRReviewSessionEnvelope":
        data = _object(value, "OCRReviewSessionEnvelope")
        _fields(data, _ENVELOPE_FIELDS, "OCRReviewSessionEnvelope")
        schema_version = _string(
            data["schema_version"],
            "schema_version",
            maximum=32,
        )
        if (
            schema_version
            != CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION
        ):
            raise UnsupportedOCRReviewSessionSchemaVersion(
                f"Unsupported OCR review session schema version: "
                f"{schema_version!r}."
            )
        field_reviews = _list(
            data["field_reviews"],
            "field_reviews",
        )
        conflict_resolutions = _list(
            data["conflict_resolutions"],
            "conflict_resolutions",
        )
        result = cls(
            schema_version=schema_version,
            session_id=_string(
                data["session_id"],
                "session_id",
                maximum=_MAX_SESSION_ID_CHARS,
            ),
            source_fingerprint=_string(
                data["source_fingerprint"],
                "source_fingerprint",
                maximum=_MAX_SOURCE_FINGERPRINT_CHARS,
            ),
            lifecycle_state=_enum(
                OCRReviewSessionLifecycle,
                data["lifecycle_state"],
                "lifecycle_state",
            ),
            review_mode=_enum(
                OCRReviewMode,
                data["review_mode"],
                "review_mode",
            ),
            reviewer_id=_string(
                data["reviewer_id"],
                "reviewer_id",
                maximum=_MAX_REVIEWER_ID_CHARS,
            ),
            source_report=_report_from_dict(data["source_report"]),
            field_reviews=tuple(
                _field_review_from_dict(item, index=index)
                for index, item in enumerate(field_reviews)
            ),
            conflict_resolutions=tuple(
                OCRStoredConflictResolution.from_dict(item)
                for item in conflict_resolutions
            ),
        )
        result.validate()
        return result

    def reconstruct(
        self,
        *,
        session_service: OCRReviewSessionService,
    ) -> OCRReviewSessionReconstruction:
        """Recompute exact conflict targets and return immutable session input."""

        self.validate()
        if self.lifecycle_state is OCRReviewSessionLifecycle.ABANDONED:
            raise ValueError(
                "ABANDONED OCR review sessions are not resumable."
            )
        reconstruction, _result = self._reconstruct_and_run(
            session_service=session_service
        )
        return reconstruction

    def validate_lifecycle(
        self,
        *,
        session_service: OCRReviewSessionService,
    ) -> None:
        """Delegate completed-state validation to Sprint 10 orchestration."""

        self.validate()
        _reconstruction, result = self._reconstruct_and_run(
            session_service=session_service
        )
        if (
            self.lifecycle_state is OCRReviewSessionLifecycle.COMPLETED
            and not result.is_complete
        ):
            raise ValueError(
                "COMPLETED OCR review session requires a complete final "
                "projection."
            )

    def _reconstruct_and_run(
        self,
        *,
        session_service: OCRReviewSessionService,
    ) -> tuple[OCRReviewSessionReconstruction, OCRReviewSessionResult]:
        if not isinstance(session_service, OCRReviewSessionService):
            raise TypeError(
                "session_service must be an OCRReviewSessionService."
            )
        review = OCRReportReview(
            reviewer_id=self.reviewer_id,
            field_reviews=tuple(
                sorted(self.field_reviews, key=_review_key)
            ),
        )
        baseline = session_service.run(
            request=OCRReviewSessionRequest(
                source_report=self.source_report,
                review=review,
                mode=self.review_mode,
            )
        )
        targets = {
            (field.source_coin_id, field.field_name): field
            for field in baseline.consolidation.fields
            if field.status is OCRConsolidationStatus.CONFLICT
        }

        targeted: list[OCRReviewSessionConflictResolutionRequest] = []
        for stored in sorted(
            self.conflict_resolutions,
            key=lambda item: item.identity,
        ):
            field = targets.get(stored.identity)
            if field is None:
                raise ValueError(
                    "Stored conflict resolution does not target a current "
                    f"consolidation conflict: {stored.identity!r}."
                )
            targeted.append(
                OCRReviewSessionConflictResolutionRequest(
                    field=field,
                    request=OCRConflictResolutionRequest(
                        decision=stored.decision,
                        value=stored.value,
                    ),
                )
            )

        reconstruction = OCRReviewSessionReconstruction(
            source_report=self.source_report,
            review=review,
            conflict_resolutions=tuple(targeted),
            mode=self.review_mode,
        )
        reconstruction.validate()
        result = session_service.run(
            request=reconstruction.to_session_request()
        )
        return reconstruction, result


@runtime_checkable
class OCRReviewSessionRepository(Protocol):
    """Persistence boundary for a future review-session implementation."""

    def save(self, envelope: OCRReviewSessionEnvelope) -> None:
        """Create or replace one validated envelope."""
        ...

    def get(
        self,
        session_id: str,
    ) -> OCRReviewSessionEnvelope | None:
        """Return one envelope by opaque identity, if it exists."""
        ...

    def exists(self, session_id: str) -> bool:
        """Return whether an envelope exists for the opaque identity."""
        ...


def _observation_from_dict(
    value: object,
    *,
    index: int,
) -> OCRObservation:
    name = f"source_report.observations[{index}]"
    data = _object(value, name)
    _fields(data, _OBSERVATION_FIELDS, name)
    result = OCRObservation(
        source_coin_id=_string(
            data["source_coin_id"],
            f"{name}.source_coin_id",
            maximum=16_384,
        ),
        image_role=_string(
            data["image_role"],
            f"{name}.image_role",
            maximum=16,
        ),
        artifact_key=_string(
            data["artifact_key"],
            f"{name}.artifact_key",
            maximum=255,
        ),
        provider_id=_string(
            data["provider_id"],
            f"{name}.provider_id",
            maximum=128,
        ),
        raw_text=_string(
            data["raw_text"],
            f"{name}.raw_text",
            maximum=4096,
            allow_empty=True,
        ),
        confidence_score=_number(
            data["confidence_score"],
            f"{name}.confidence_score",
        ),
    )
    result.validate()
    return result


def _candidate_from_dict(
    value: object,
    *,
    index: int,
) -> OCRFieldCandidate:
    name = f"source_report.candidates[{index}]"
    data = _object(value, name)
    _fields(data, _CANDIDATE_FIELDS, name)
    evidence = _list(data["evidence"], f"{name}.evidence")
    result = OCRFieldCandidate(
        source_coin_id=_string(
            data["source_coin_id"],
            f"{name}.source_coin_id",
            maximum=16_384,
        ),
        image_role=_string(
            data["image_role"],
            f"{name}.image_role",
            maximum=16,
        ),
        artifact_key=_string(
            data["artifact_key"],
            f"{name}.artifact_key",
            maximum=255,
        ),
        provider_id=_string(
            data["provider_id"],
            f"{name}.provider_id",
            maximum=128,
        ),
        field_name=_string(
            data["field_name"],
            f"{name}.field_name",
            maximum=64,
        ),
        raw_text=_string(
            data["raw_text"],
            f"{name}.raw_text",
            maximum=4096,
            allow_empty=True,
        ),
        normalized_value=_string(
            data["normalized_value"],
            f"{name}.normalized_value",
            maximum=512,
        ),
        confidence_score=_number(
            data["confidence_score"],
            f"{name}.confidence_score",
        ),
        evidence=tuple(
            _string(
                item,
                f"{name}.evidence[{item_index}]",
                maximum=512,
            )
            for item_index, item in enumerate(evidence)
        ),
        review_status=_enum(
            OCRReviewStatus,
            data["review_status"],
            f"{name}.review_status",
        ),
    )
    result.validate()
    return result


def _conflict_from_dict(
    value: object,
    *,
    index: int,
) -> OCRConflict:
    name = f"source_report.conflicts[{index}]"
    data = _object(value, name)
    _fields(data, _CONFLICT_FIELDS, name)
    candidate_values = _list(
        data["candidate_values"],
        f"{name}.candidate_values",
    )
    result = OCRConflict(
        source_coin_id=_string(
            data["source_coin_id"],
            f"{name}.source_coin_id",
            maximum=16_384,
        ),
        field_name=_string(
            data["field_name"],
            f"{name}.field_name",
            maximum=64,
        ),
        candidate_values=tuple(
            _string(
                item,
                f"{name}.candidate_values[{item_index}]",
                maximum=512,
            )
            for item_index, item in enumerate(candidate_values)
        ),
        reason=_string(
            data["reason"],
            f"{name}.reason",
            maximum=1024,
        ),
        review_status=_enum(
            OCRReviewStatus,
            data["review_status"],
            f"{name}.review_status",
        ),
    )
    result.validate()
    return result


def _report_from_dict(value: object) -> OCRMetadataReport:
    name = "source_report"
    data = _object(value, name)
    _fields(data, _REPORT_FIELDS, name)
    observations = _list(data["observations"], f"{name}.observations")
    candidates = _list(data["candidates"], f"{name}.candidates")
    conflicts = _list(data["conflicts"], f"{name}.conflicts")
    for count_name, expected, actual in (
        (
            "observation_count",
            _integer(
                data["observation_count"],
                f"{name}.observation_count",
            ),
            len(observations),
        ),
        (
            "candidate_count",
            _integer(
                data["candidate_count"],
                f"{name}.candidate_count",
            ),
            len(candidates),
        ),
        (
            "conflict_count",
            _integer(
                data["conflict_count"],
                f"{name}.conflict_count",
            ),
            len(conflicts),
        ),
    ):
        if expected != actual:
            raise ValueError(
                f"{name}.{count_name} does not match payload."
            )
    if not _boolean(
        data["manual_review_required"],
        f"{name}.manual_review_required",
    ):
        raise ValueError("source_report must require manual review.")
    result = OCRMetadataReport(
        provider_available=_boolean(
            data["provider_available"],
            f"{name}.provider_available",
        ),
        observations=tuple(
            _observation_from_dict(item, index=index)
            for index, item in enumerate(observations)
        ),
        candidates=tuple(
            _candidate_from_dict(item, index=index)
            for index, item in enumerate(candidates)
        ),
        conflicts=tuple(
            _conflict_from_dict(item, index=index)
            for index, item in enumerate(conflicts)
        ),
        review_status=_enum(
            OCRReviewStatus,
            data["review_status"],
            f"{name}.review_status",
        ),
    )
    result.validate()
    return result


def _field_review_from_dict(
    value: object,
    *,
    index: int,
) -> OCRFieldReview:
    name = f"field_reviews[{index}]"
    data = _object(value, name)
    _fields(data, _FIELD_REVIEW_FIELDS, name)
    result = OCRFieldReview(
        source_coin_id=_string(
            data["source_coin_id"],
            f"{name}.source_coin_id",
            maximum=256,
        ),
        image_role=_string(
            data["image_role"],
            f"{name}.image_role",
            maximum=256,
        ),
        artifact_key=_string(
            data["artifact_key"],
            f"{name}.artifact_key",
            maximum=256,
        ),
        provider_id=_string(
            data["provider_id"],
            f"{name}.provider_id",
            maximum=256,
        ),
        field_name=_string(
            data["field_name"],
            f"{name}.field_name",
            maximum=256,
        ),
        original_value=_string(
            data["original_value"],
            f"{name}.original_value",
            maximum=512,
        ),
        decision=_enum(
            OCRReviewDecision,
            data["decision"],
            f"{name}.decision",
        ),
        reviewed_value=_optional_string(
            data["reviewed_value"],
            f"{name}.reviewed_value",
            maximum=512,
        ),
        reason=_string(
            data["reason"],
            f"{name}.reason",
            maximum=2000,
        ),
    )
    result.validate()
    return result
