"""Pure mapping from complete human-reviewed OCR sessions to confirmed data.

The mapper consumes only immutable Sprint 10 results and source inputs and emits
collection-independent Sprint 13 contracts.  It performs no normalization,
persistence, collection mapping, mutation, I/O, or automatic invocation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationProvenance,
    ConfirmedObservationSet,
    ConfirmedObservationSource,
)
from .workflow_ocr_final_projection import OCRFinalProjectedField
from .workflow_ocr_models import (
    ALLOWED_OCR_FIELDS,
    OCRFieldCandidate,
    OCRMetadataReport,
)
from .workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
)
from .workflow_ocr_review_session import OCRReviewSessionResult


CandidateIdentity = tuple[str, str, str, str, str, str]
FieldIdentity = tuple[str, str]


class ConfirmedObservationMappingError(ValueError):
    """A reviewed OCR session cannot safely cross the confirmed-data boundary."""


class IncompleteConfirmedObservationSourceError(
    ConfirmedObservationMappingError
):
    """The reviewed source does not have a complete resolved projection."""


class UnsupportedConfirmedObservationFieldError(
    ConfirmedObservationMappingError
):
    """A final field is grade or outside the current OCR field vocabulary."""


class DuplicateConfirmedObservationFieldError(
    ConfirmedObservationMappingError
):
    """A source coin has more than one final value for one scalar field."""


class MissingConfirmedObservationProvenanceError(
    ConfirmedObservationMappingError
):
    """A final field has no exact source/report/review provenance."""


class MalformedConfirmedObservationSourceError(
    ConfirmedObservationMappingError
):
    """Reviewed inputs are inconsistent or contain an invalid final value."""


@dataclass(frozen=True, slots=True)
class ConfirmedObservationMappingInput:
    """Minimum immutable source proving review and provenance fidelity."""

    session_result: OCRReviewSessionResult
    source_report: OCRMetadataReport
    report_review: OCRReportReview
    review_session_id: str | None = None
    source_fingerprint: str | None = None

    def validate(self) -> None:
        if not isinstance(self.session_result, OCRReviewSessionResult):
            raise TypeError(
                "session_result must be an OCRReviewSessionResult."
            )
        if not isinstance(self.source_report, OCRMetadataReport):
            raise TypeError("source_report must be an OCRMetadataReport.")
        if not isinstance(self.report_review, OCRReportReview):
            raise TypeError("report_review must be an OCRReportReview.")
        if (
            self.review_session_id is not None
            and not isinstance(self.review_session_id, str)
        ):
            raise TypeError("review_session_id must be a string or None.")
        if (
            self.source_fingerprint is not None
            and not isinstance(self.source_fingerprint, str)
        ):
            raise TypeError("source_fingerprint must be a string or None.")
        self.source_report.validate()
        self.report_review.validate()
        self.session_result.validate()


class ConfirmedObservationMapper:
    """Stateless fail-closed mapper for complete reviewed OCR sessions."""

    __slots__ = ()

    def map_review_session(
        self,
        source: ConfirmedObservationMappingInput,
    ) -> tuple[ConfirmedObservationSet, ...]:
        if not isinstance(source, ConfirmedObservationMappingInput):
            raise TypeError(
                "source must be a ConfirmedObservationMappingInput."
            )

        self._preflight_projection(source.session_result)
        source.validate()
        result = source.session_result
        reconciliation = result.reconciliation

        if reconciliation.reviewer_id != source.report_review.reviewer_id:
            raise MalformedConfirmedObservationSourceError(
                "Review-session and report-review identities do not match."
            )
        if (
            reconciliation.deferred_count
            or reconciliation.missing_count
            or not reconciliation.is_complete
            or not result.final_projection.is_complete
            or not result.is_complete
        ):
            raise IncompleteConfirmedObservationSourceError(
                "Only complete reviewed OCR sessions may map to confirmed "
                "observations."
            )

        final_fields = result.final_projection.final_fields
        if not final_fields:
            raise IncompleteConfirmedObservationSourceError(
                "A confirmed-observation mapping requires at least one "
                "resolved final field."
            )

        candidates = self._candidate_index(source.source_report)
        reviews = self._review_index(source.report_review)
        grouped: dict[str, list[ConfirmedFieldObservation]] = {}

        for final_field in final_fields:
            observation = self._map_field(
                final_field,
                reviewer_id=source.report_review.reviewer_id,
                candidates=candidates,
                reviews=reviews,
            )
            grouped.setdefault(
                observation.source_coin_id,
                [],
            ).append(observation)

        sets = []
        for source_coin_id in sorted(grouped):
            observations = tuple(
                sorted(
                    grouped[source_coin_id],
                    key=lambda item: item.field_name,
                )
            )
            confirmed_set = ConfirmedObservationSet(
                schema_version=(
                    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION
                ),
                source_coin_id=source_coin_id,
                reviewer_id=source.report_review.reviewer_id,
                observations=observations,
                review_session_id=source.review_session_id,
                source_fingerprint=source.source_fingerprint,
            )
            confirmed_set.validate()
            sets.append(confirmed_set)

        return tuple(sets)

    @staticmethod
    def _preflight_projection(result: object) -> None:
        if not isinstance(result, OCRReviewSessionResult):
            raise TypeError(
                "session_result must be an OCRReviewSessionResult."
            )
        projection = result.final_projection
        final_fields = getattr(projection, "final_fields", None)
        unresolved_fields = getattr(projection, "unresolved_fields", None)
        if not isinstance(final_fields, tuple):
            raise MalformedConfirmedObservationSourceError(
                "final_fields must be an immutable tuple."
            )
        if not isinstance(unresolved_fields, tuple):
            raise MalformedConfirmedObservationSourceError(
                "unresolved_fields must be an immutable tuple."
            )
        if unresolved_fields:
            raise IncompleteConfirmedObservationSourceError(
                "Unresolved or deferred final fields cannot be confirmed."
            )

        identities: set[FieldIdentity] = set()
        for field in final_fields:
            if not isinstance(field, OCRFinalProjectedField):
                raise MalformedConfirmedObservationSourceError(
                    "final_fields must contain OCRFinalProjectedField values."
                )
            field_name = field.source_field.field_name
            if field_name == "grade":
                raise UnsupportedConfirmedObservationFieldError(
                    "Grade cannot map to a confirmed observation."
                )
            if field_name not in ALLOWED_OCR_FIELDS:
                raise UnsupportedConfirmedObservationFieldError(
                    f"Unsupported confirmed-observation field: "
                    f"{field_name!r}."
                )
            if (
                not isinstance(field.final_value, str)
                or not field.final_value.strip()
            ):
                raise MalformedConfirmedObservationSourceError(
                    "Every confirmed final field requires a nonblank value."
                )
            if not field.source_field.provenance:
                raise MissingConfirmedObservationProvenanceError(
                    "Every OCR_REVIEW field requires source provenance."
                )
            if field.identity in identities:
                raise DuplicateConfirmedObservationFieldError(
                    f"Duplicate final field identity: {field.identity!r}."
                )
            identities.add(field.identity)

    @staticmethod
    def _candidate_index(
        report: OCRMetadataReport,
    ) -> dict[CandidateIdentity, OCRFieldCandidate]:
        result: dict[CandidateIdentity, OCRFieldCandidate] = {}
        for candidate in report.candidates:
            identity = _candidate_identity(candidate)
            if identity in result:
                raise MalformedConfirmedObservationSourceError(
                    f"Duplicate source candidate identity: {identity!r}."
                )
            result[identity] = candidate
        return result

    @staticmethod
    def _review_index(
        review: OCRReportReview,
    ) -> dict[CandidateIdentity, OCRFieldReview]:
        result: dict[CandidateIdentity, OCRFieldReview] = {}
        for field_review in review.field_reviews:
            identity = _review_identity(field_review)
            if identity in result:
                raise MalformedConfirmedObservationSourceError(
                    f"Duplicate field-review identity: {identity!r}."
                )
            result[identity] = field_review
        return result

    def _map_field(
        self,
        field: OCRFinalProjectedField,
        *,
        reviewer_id: str,
        candidates: dict[CandidateIdentity, OCRFieldCandidate],
        reviews: dict[CandidateIdentity, OCRFieldReview],
    ) -> ConfirmedFieldObservation:
        provenance = []
        for source in field.source_field.provenance:
            identity = (
                field.source_field.source_coin_id,
                source.image_role,
                source.artifact_key,
                source.provider_id,
                field.source_field.field_name,
                source.original_value,
            )
            candidate = candidates.get(identity)
            review = reviews.get(identity)
            if candidate is None or review is None:
                raise MissingConfirmedObservationProvenanceError(
                    "Final provenance does not match the source report and "
                    "human review."
                )
            if (
                review.decision is not source.decision
                or review.reviewed_value != source.accepted_value
                or review.reason != source.reason
            ):
                raise MissingConfirmedObservationProvenanceError(
                    "Final provenance does not match the exact human "
                    "decision."
                )
            mapped = ConfirmedObservationProvenance(
                provider_id=source.provider_id,
                image_role=source.image_role,
                artifact_key=source.artifact_key,
                source_value=source.original_value,
                confidence_score=candidate.confidence_score,
                evidence=candidate.evidence,
            )
            mapped.validate()
            provenance.append(mapped)

        observation = ConfirmedFieldObservation(
            schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
            source_coin_id=field.source_field.source_coin_id,
            field_name=field.source_field.field_name,
            submitted_value=field.final_value,
            canonical_value=None,
            reviewer_id=reviewer_id,
            provenance=tuple(
                sorted(provenance, key=lambda item: item.identity)
            ),
            source_type=ConfirmedObservationSource.OCR_REVIEW,
            rationale=None,
        )
        observation.validate()
        return observation


def map_review_session(
    source: ConfirmedObservationMappingInput,
) -> tuple[ConfirmedObservationSet, ...]:
    """Map one complete reviewed session without retaining mapper state."""

    return ConfirmedObservationMapper().map_review_session(source)


def _candidate_identity(
    candidate: OCRFieldCandidate,
) -> CandidateIdentity:
    return (
        candidate.source_coin_id,
        candidate.image_role,
        candidate.artifact_key,
        candidate.provider_id,
        candidate.field_name,
        candidate.normalized_value,
    )


def _review_identity(review: OCRFieldReview) -> CandidateIdentity:
    return (
        review.source_coin_id,
        review.image_role,
        review.artifact_key,
        review.provider_id,
        review.field_name,
        review.original_value,
    )
