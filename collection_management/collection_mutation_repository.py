"""Repository-neutral contracts for atomic conditional collection mutation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


CONDITIONAL_COLLECTION_MUTATION_FIELDS = frozenset(
    {"country", "denomination", "year"}
)


class ConditionalCollectionMutationError(Exception):
    """A conditional collection mutation could not be completed safely."""


class InvalidConditionalCollectionMutationError(
    ConditionalCollectionMutationError
):
    """The requested repository-neutral mutation is invalid."""


class ConditionalCollectionRecordNotFoundError(
    ConditionalCollectionMutationError
):
    """The exact requested collection record does not exist."""

    def __init__(self, record_id: str) -> None:
        self.record_id = record_id
        super().__init__(f"Collection record {record_id!r} was not found.")


class ConditionalCollectionStateConflictError(
    ConditionalCollectionMutationError
):
    """Authoritative state matches neither expected nor desired state."""

    def __init__(self, conflicted_fields: tuple[str, ...]) -> None:
        self.conflicted_fields = conflicted_fields
        super().__init__(
            "Collection record state is stale for fields "
            f"{conflicted_fields!r}."
        )


class ConditionalCollectionRepositoryError(
    ConditionalCollectionMutationError
):
    """The authoritative repository failed or was malformed."""


class ConditionalCollectionVerificationError(
    ConditionalCollectionMutationError
):
    """The committed state did not retain every exact desired value."""


@dataclass(frozen=True, slots=True)
class ConditionalCollectionFieldChange:
    """One repository-neutral expected/desired field transition."""

    field_name: str
    expected_value: str | None
    desired_value: str | None

    def validate(self) -> None:
        if self.field_name not in CONDITIONAL_COLLECTION_MUTATION_FIELDS:
            raise InvalidConditionalCollectionMutationError(
                f"Unsupported conditional collection field {self.field_name!r}."
            )
        for name, value in (
            ("expected_value", self.expected_value),
            ("desired_value", self.desired_value),
        ):
            if value is not None and not isinstance(value, str):
                raise InvalidConditionalCollectionMutationError(
                    f"{name} must be a string or None."
                )
        if self.expected_value == self.desired_value:
            raise InvalidConditionalCollectionMutationError(
                "Expected and desired values must differ."
            )


@dataclass(frozen=True, slots=True)
class ConditionalCollectionMutationResult:
    """Exact ordered repository outcome for one atomic batch."""

    applied_fields: tuple[str, ...]
    already_applied_fields: tuple[str, ...]

    def validate(self) -> None:
        if not isinstance(self.applied_fields, tuple) or not isinstance(
            self.already_applied_fields, tuple
        ):
            raise InvalidConditionalCollectionMutationError(
                "Conditional mutation result fields must be tuples."
            )
        combined = self.applied_fields + self.already_applied_fields
        if not combined or len(set(combined)) != len(combined):
            raise InvalidConditionalCollectionMutationError(
                "Conditional mutation result fields must be nonempty and unique."
            )
        if any(
            field_name not in CONDITIONAL_COLLECTION_MUTATION_FIELDS
            for field_name in combined
        ):
            raise InvalidConditionalCollectionMutationError(
                "Conditional mutation result contains an unsupported field."
            )


@runtime_checkable
class ConditionalCollectionMutationRepository(Protocol):
    """Minimal capability required by the controlled workflow executor."""

    def mutate_fields_conditionally(
        self,
        record_id: str,
        changes: tuple[ConditionalCollectionFieldChange, ...],
    ) -> ConditionalCollectionMutationResult:
        """Compare and replace exact field states inside one atomic boundary."""
