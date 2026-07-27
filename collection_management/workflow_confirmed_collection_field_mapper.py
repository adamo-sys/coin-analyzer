"""Pure mapping from READY confirmed metadata to collection field targets.

The mapper exposes only source-verified field correspondences.  It does not
read collection records, compare values, select change operations, construct
plans, approve proposals, persist state, or mutate any object.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from capture_import.workflow_confirmed_observation_models import (
    ConfirmedFieldObservation,
    ConfirmedObservationSet,
)
from capture_import.workflow_confirmed_observation_readiness import (
    ConfirmedObservationReadinessResult,
    ConfirmedObservationReadinessStatus,
)


class CollectionTargetField(str, Enum):
    """Exact active CoinItem string fields supported by this mapper."""

    COUNTRY = "country"
    DENOMINATION = "denomination"
    YEAR = "year"


class ConfirmedCollectionFieldMappingError(ValueError):
    """A READY observation cannot be mapped safely to a collection field."""


class UnsupportedConfirmedCollectionFieldError(
    ConfirmedCollectionFieldMappingError
):
    """The confirmed field has no exact active collection target."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(
            f"Confirmed field {field_name!r} has no supported collection "
            "target."
        )


class AmbiguousConfirmedCollectionFieldError(
    ConfirmedCollectionFieldMappingError
):
    """The confirmed field resembles multiple non-equivalent targets."""

    def __init__(
        self,
        *,
        field_name: str,
        required_context: str,
    ) -> None:
        self.field_name = field_name
        self.required_context = required_context
        super().__init__(
            f"Confirmed field {field_name!r} requires "
            f"{required_context}; no target was selected."
        )


class DuplicateCollectionTargetFieldError(
    ConfirmedCollectionFieldMappingError
):
    """More than one confirmed source would emit the same target field."""

    def __init__(self, target_field: CollectionTargetField) -> None:
        self.target_field = target_field
        super().__init__(
            f"Duplicate collection target field: {target_field.value!r}."
        )


class InvalidConfirmedCollectionMappingContextError(
    ConfirmedCollectionFieldMappingError
):
    """The supplied readiness result is inconsistent with its source set."""


_SUPPORTED_FIELD_MAPPINGS: MappingProxyType[
    str,
    CollectionTargetField,
] = MappingProxyType(
    {
        "country": CollectionTargetField.COUNTRY,
        "denomination": CollectionTargetField.DENOMINATION,
        "year": CollectionTargetField.YEAR,
    }
)

# Record-kind technical debt: the active CoinItem model has no authoritative
# coin/banknote discriminator.  This mapper therefore supports only exact
# targets that are safe for the shared flat schema and never infers kind from
# source fields, denomination, source type, or provenance.  Kind-specific
# mappings require a later explicit collection-schema policy.
#
# These fields resemble legacy or auxiliary fields, but the active CoinItem
# schema has no single equivalent.  A later architecture unit must choose an
# explicit schema policy before any target can be selected.
_AMBIGUOUS_FIELDS = frozenset(
    {
        "certification_number",
        "series_type",
    }
)
_AMBIGUOUS_CONTEXT = (
    "an explicit collection-schema mapping policy"
)


@dataclass(frozen=True, slots=True)
class ConfirmedCollectionFieldMapping:
    """One exact collection target and its full confirmed source."""

    source_observation: ConfirmedFieldObservation
    target_field: CollectionTargetField
    mapped_value: str

    @property
    def source_value(self) -> str:
        if self.source_observation.canonical_value is not None:
            return self.source_observation.canonical_value
        return self.source_observation.submitted_value

    def validate(self) -> None:
        if not isinstance(
            self.source_observation,
            ConfirmedFieldObservation,
        ):
            raise TypeError(
                "source_observation must be a ConfirmedFieldObservation."
            )
        self.source_observation.validate()
        if not isinstance(self.target_field, CollectionTargetField):
            raise TypeError(
                "target_field must be a CollectionTargetField."
            )
        expected_target = _SUPPORTED_FIELD_MAPPINGS.get(
            self.source_observation.field_name
        )
        if expected_target is not self.target_field:
            raise ValueError(
                "target_field does not match the exact supported mapping "
                "for source_observation.field_name."
            )
        if not isinstance(self.mapped_value, str):
            raise TypeError("mapped_value must be a string.")
        if self.mapped_value != self.source_value:
            raise ValueError(
                "mapped_value must exactly match the source observation's "
                "canonical value when present, otherwise its submitted value."
            )


@dataclass(frozen=True, slots=True)
class ConfirmedCollectionFieldMappingResult:
    """Atomic deterministic mappings for one READY confirmed set."""

    source_coin_id: str
    reviewer_id: str
    mappings: tuple[ConfirmedCollectionFieldMapping, ...]
    review_session_id: str | None = None
    source_fingerprint: str | None = None

    def validate(self) -> None:
        _required_text(self.source_coin_id, "source_coin_id")
        _required_text(self.reviewer_id, "reviewer_id")
        _optional_text(self.review_session_id, "review_session_id")
        _optional_text(self.source_fingerprint, "source_fingerprint")
        if not isinstance(self.mappings, tuple):
            raise TypeError("mappings must be a tuple.")
        if not self.mappings:
            raise ValueError("mappings must contain at least one field.")
        if any(
            not isinstance(item, ConfirmedCollectionFieldMapping)
            for item in self.mappings
        ):
            raise TypeError(
                "mappings must contain ConfirmedCollectionFieldMapping "
                "values."
            )
        expected_order = tuple(
            sorted(
                self.mappings,
                key=lambda item: item.target_field.value,
            )
        )
        if self.mappings != expected_order:
            raise ValueError(
                "mappings must be in deterministic target-field order."
            )

        targets: set[CollectionTargetField] = set()
        sources: set[str] = set()
        for mapping in self.mappings:
            mapping.validate()
            observation = mapping.source_observation
            if observation.source_coin_id != self.source_coin_id:
                raise ValueError(
                    "All mappings must use the result source_coin_id."
                )
            if observation.reviewer_id != self.reviewer_id:
                raise ValueError(
                    "All mappings must use the result reviewer_id."
                )
            if mapping.target_field in targets:
                raise DuplicateCollectionTargetFieldError(
                    mapping.target_field
                )
            targets.add(mapping.target_field)
            if observation.field_name in sources:
                raise ValueError("Duplicate confirmed source field.")
            sources.add(observation.field_name)


class ConfirmedCollectionFieldMapper:
    """Stateless fail-closed mapper for genuine Unit 1F result objects."""

    __slots__ = ()

    def map(
        self,
        readiness: ConfirmedObservationReadinessResult,
    ) -> ConfirmedCollectionFieldMappingResult:
        if not isinstance(
            readiness,
            ConfirmedObservationReadinessResult,
        ):
            raise TypeError(
                "readiness must be a "
                "ConfirmedObservationReadinessResult."
            )
        if readiness.status is not ConfirmedObservationReadinessStatus.READY:
            raise InvalidConfirmedCollectionMappingContextError(
                "Only READY confirmed observations may be mapped."
            )
        source = readiness.canonicalized_observation_set
        if not isinstance(source, ConfirmedObservationSet):
            raise InvalidConfirmedCollectionMappingContextError(
                "Readiness must contain a ConfirmedObservationSet."
            )
        source.validate()
        if readiness.source_coin_id != source.source_coin_id:
            raise InvalidConfirmedCollectionMappingContextError(
                "Readiness source_coin_id does not match its confirmed set."
            )

        mappings: list[ConfirmedCollectionFieldMapping] = []
        targets: set[CollectionTargetField] = set()
        for observation in source.observations:
            target = self._target_for(observation.field_name)
            if target in targets:
                raise DuplicateCollectionTargetFieldError(target)
            mapping = ConfirmedCollectionFieldMapping(
                source_observation=observation,
                target_field=target,
                mapped_value=(
                    observation.canonical_value
                    if observation.canonical_value is not None
                    else observation.submitted_value
                ),
            )
            mapping.validate()
            mappings.append(mapping)
            targets.add(target)

        result = ConfirmedCollectionFieldMappingResult(
            source_coin_id=source.source_coin_id,
            reviewer_id=source.reviewer_id,
            mappings=tuple(
                sorted(
                    mappings,
                    key=lambda item: item.target_field.value,
                )
            ),
            review_session_id=source.review_session_id,
            source_fingerprint=source.source_fingerprint,
        )
        result.validate()
        return result

    @staticmethod
    def _target_for(field_name: str) -> CollectionTargetField:
        target = _SUPPORTED_FIELD_MAPPINGS.get(field_name)
        if target is not None:
            return target
        if field_name in _AMBIGUOUS_FIELDS:
            raise AmbiguousConfirmedCollectionFieldError(
                field_name=field_name,
                required_context=_AMBIGUOUS_CONTEXT,
            )
        raise UnsupportedConfirmedCollectionFieldError(field_name)


def map_ready_confirmed_observations(
    readiness: ConfirmedObservationReadinessResult,
) -> ConfirmedCollectionFieldMappingResult:
    """Map one READY result without retaining mapper state."""

    return ConfirmedCollectionFieldMapper().map(readiness)


def _required_text(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value.strip():
        raise ValueError(f"{name} must not be blank.")


def _optional_text(value: object, name: str) -> None:
    if value is None:
        return
    _required_text(value, name)
