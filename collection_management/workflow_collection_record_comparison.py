"""Pure exact comparison of mapped metadata with a caller-supplied snapshot.

This module does not locate or load collection records.  Callers must provide
an immutable snapshot that explicitly distinguishes a present field from an
absent or unavailable field.  The service classifies exact values only; it
does not construct proposals, choose operations, apply approval policy, or
mutate collection state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from collection_management.workflow_collection_change_plan_models import (
    CollectionRecordReference,
)
from collection_management.workflow_confirmed_collection_field_mapper import (
    CollectionTargetField,
    ConfirmedCollectionFieldMapping,
    ConfirmedCollectionFieldMappingResult,
)


class CollectionRecordFieldAvailability(str, Enum):
    """Caller-asserted availability of one current collection field."""

    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNAVAILABLE = "UNAVAILABLE"


class CollectionFieldComparisonOutcome(str, Enum):
    """Exact structural relationship between mapped and current values."""

    ABSENT = "ABSENT"
    EMPTY = "EMPTY"
    UNAVAILABLE = "UNAVAILABLE"
    EXACT_MATCH = "EXACT_MATCH"
    DIFFERENT = "DIFFERENT"


class CollectionRecordComparisonError(ValueError):
    """Mapped metadata cannot be compared with the supplied snapshot."""


class InvalidCollectionRecordComparisonContextError(
    CollectionRecordComparisonError
):
    """The mapping result or snapshot is inconsistent."""


class MissingCollectionRecordSnapshotFieldError(
    CollectionRecordComparisonError
):
    """The snapshot does not explicitly describe one mapped target."""

    def __init__(self, target_field: CollectionTargetField) -> None:
        self.target_field = target_field
        super().__init__(
            "Collection record snapshot is missing mapped target field "
            f"{target_field.value!r}."
        )


@dataclass(frozen=True, slots=True)
class CollectionRecordFieldSnapshot:
    """Explicit current state for one supported collection target."""

    target_field: CollectionTargetField
    availability: CollectionRecordFieldAvailability
    value: str | None

    def validate(self) -> None:
        if not isinstance(self.target_field, CollectionTargetField):
            raise TypeError(
                "target_field must be a CollectionTargetField."
            )
        if not isinstance(
            self.availability,
            CollectionRecordFieldAvailability,
        ):
            raise TypeError(
                "availability must be a "
                "CollectionRecordFieldAvailability."
            )
        if self.availability is CollectionRecordFieldAvailability.PRESENT:
            if not isinstance(self.value, str):
                raise TypeError(
                    "PRESENT collection fields require a string value."
                )
        elif self.value is not None:
            raise ValueError(
                "ABSENT and UNAVAILABLE collection fields must not carry "
                "a value."
            )


@dataclass(frozen=True, slots=True)
class CollectionRecordSnapshot:
    """Immutable caller-supplied state for one identified record."""

    target_record: CollectionRecordReference
    fields: tuple[CollectionRecordFieldSnapshot, ...]

    def validate(self) -> None:
        if not isinstance(self.target_record, CollectionRecordReference):
            raise TypeError(
                "target_record must be a CollectionRecordReference."
            )
        self.target_record.validate()
        if not isinstance(self.fields, tuple):
            raise TypeError("fields must be a tuple.")
        if not self.fields:
            raise ValueError("fields must contain at least one snapshot.")
        if any(
            not isinstance(field, CollectionRecordFieldSnapshot)
            for field in self.fields
        ):
            raise TypeError(
                "fields must contain CollectionRecordFieldSnapshot values."
            )
        expected_order = tuple(
            sorted(self.fields, key=lambda field: field.target_field.value)
        )
        if self.fields != expected_order:
            raise ValueError(
                "fields must be in deterministic target-field order."
            )
        targets: set[CollectionTargetField] = set()
        for field in self.fields:
            field.validate()
            if field.target_field in targets:
                raise ValueError("Duplicate snapshot target_field.")
            targets.add(field.target_field)


@dataclass(frozen=True, slots=True)
class CollectionFieldComparison:
    """One exact comparison retaining its mapped and current evidence."""

    mapping: ConfirmedCollectionFieldMapping
    current_field: CollectionRecordFieldSnapshot
    outcome: CollectionFieldComparisonOutcome

    @property
    def target_field(self) -> CollectionTargetField:
        return self.mapping.target_field

    @property
    def mapped_value(self) -> str:
        return self.mapping.mapped_value

    @property
    def current_value(self) -> str | None:
        return self.current_field.value

    def validate(self) -> None:
        if not isinstance(self.mapping, ConfirmedCollectionFieldMapping):
            raise TypeError(
                "mapping must be a ConfirmedCollectionFieldMapping."
            )
        self.mapping.validate()
        if not isinstance(
            self.current_field,
            CollectionRecordFieldSnapshot,
        ):
            raise TypeError(
                "current_field must be a "
                "CollectionRecordFieldSnapshot."
            )
        self.current_field.validate()
        if self.current_field.target_field is not self.mapping.target_field:
            raise ValueError(
                "current_field target must match mapping target_field."
            )
        if not isinstance(self.outcome, CollectionFieldComparisonOutcome):
            raise TypeError(
                "outcome must be a CollectionFieldComparisonOutcome."
            )
        expected = _classify(self.mapping, self.current_field)
        if self.outcome is not expected:
            raise ValueError(
                "outcome does not match the exact mapped/current values."
            )


@dataclass(frozen=True, slots=True)
class CollectionRecordComparisonResult:
    """Atomic comparisons for one mapping result and target record."""

    target_record: CollectionRecordReference
    mapping_result: ConfirmedCollectionFieldMappingResult
    comparisons: tuple[CollectionFieldComparison, ...]

    def validate(self) -> None:
        if not isinstance(self.target_record, CollectionRecordReference):
            raise TypeError(
                "target_record must be a CollectionRecordReference."
            )
        self.target_record.validate()
        if not isinstance(
            self.mapping_result,
            ConfirmedCollectionFieldMappingResult,
        ):
            raise TypeError(
                "mapping_result must be a "
                "ConfirmedCollectionFieldMappingResult."
            )
        self.mapping_result.validate()
        if not isinstance(self.comparisons, tuple):
            raise TypeError("comparisons must be a tuple.")
        if not self.comparisons:
            raise ValueError(
                "comparisons must contain at least one comparison."
            )
        if any(
            not isinstance(item, CollectionFieldComparison)
            for item in self.comparisons
        ):
            raise TypeError(
                "comparisons must contain CollectionFieldComparison values."
            )
        expected_order = tuple(
            sorted(
                self.comparisons,
                key=lambda item: item.target_field.value,
            )
        )
        if self.comparisons != expected_order:
            raise ValueError(
                "comparisons must be in deterministic target-field order."
            )

        expected_mappings = {
            mapping.target_field: mapping
            for mapping in self.mapping_result.mappings
        }
        if len(self.comparisons) != len(expected_mappings):
            raise ValueError(
                "comparisons must cover every mapped target exactly once."
            )
        seen: set[CollectionTargetField] = set()
        for comparison in self.comparisons:
            comparison.validate()
            target = comparison.target_field
            if target in seen:
                raise ValueError("Duplicate comparison target_field.")
            seen.add(target)
            if expected_mappings.get(target) != comparison.mapping:
                raise ValueError(
                    "comparison mapping must come from mapping_result."
                )
        if seen != set(expected_mappings):
            raise ValueError(
                "comparisons must cover every mapped target exactly once."
            )


class CollectionRecordComparisonService:
    """Stateless exact comparator with no collection access."""

    __slots__ = ()

    def compare(
        self,
        mapping_result: ConfirmedCollectionFieldMappingResult,
        snapshot: CollectionRecordSnapshot,
    ) -> CollectionRecordComparisonResult:
        if not isinstance(
            mapping_result,
            ConfirmedCollectionFieldMappingResult,
        ):
            raise TypeError(
                "mapping_result must be a "
                "ConfirmedCollectionFieldMappingResult."
            )
        if not isinstance(snapshot, CollectionRecordSnapshot):
            raise TypeError(
                "snapshot must be a CollectionRecordSnapshot."
            )
        try:
            mapping_result.validate()
            snapshot.validate()
        except CollectionRecordComparisonError:
            raise
        except (TypeError, ValueError) as error:
            raise InvalidCollectionRecordComparisonContextError(
                str(error)
            ) from error

        fields = {
            field.target_field: field
            for field in snapshot.fields
        }
        comparisons: list[CollectionFieldComparison] = []
        for mapping in mapping_result.mappings:
            current = fields.get(mapping.target_field)
            if current is None:
                raise MissingCollectionRecordSnapshotFieldError(
                    mapping.target_field
                )
            comparison = CollectionFieldComparison(
                mapping=mapping,
                current_field=current,
                outcome=_classify(mapping, current),
            )
            comparison.validate()
            comparisons.append(comparison)

        result = CollectionRecordComparisonResult(
            target_record=snapshot.target_record,
            mapping_result=mapping_result,
            comparisons=tuple(comparisons),
        )
        result.validate()
        return result


def compare_mapped_collection_fields(
    mapping_result: ConfirmedCollectionFieldMappingResult,
    snapshot: CollectionRecordSnapshot,
) -> CollectionRecordComparisonResult:
    """Compare mapped values without retaining service state."""

    return CollectionRecordComparisonService().compare(
        mapping_result,
        snapshot,
    )


def _classify(
    mapping: ConfirmedCollectionFieldMapping,
    current: CollectionRecordFieldSnapshot,
) -> CollectionFieldComparisonOutcome:
    return _classify_values(mapping.mapped_value, current)


def _classify_values(
    mapped_value: str,
    current: CollectionRecordFieldSnapshot,
) -> CollectionFieldComparisonOutcome:
    if current.availability is CollectionRecordFieldAvailability.ABSENT:
        return CollectionFieldComparisonOutcome.ABSENT
    if current.availability is CollectionRecordFieldAvailability.UNAVAILABLE:
        return CollectionFieldComparisonOutcome.UNAVAILABLE
    if current.value == mapped_value:
        return CollectionFieldComparisonOutcome.EXACT_MATCH
    if current.value == "":
        return CollectionFieldComparisonOutcome.EMPTY
    return CollectionFieldComparisonOutcome.DIFFERENT
