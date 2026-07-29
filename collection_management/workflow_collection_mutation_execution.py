"""Execute one immutable mutation command through an atomic repository seam.

This module consumes Unit 1F commands without recomputing approval, freshness,
eligibility, or authorization.  The repository remains responsible for keeping
authoritative comparison and replacement inside one atomic boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from collection_management.collection_mutation_repository import (
    ConditionalCollectionFieldChange,
    ConditionalCollectionMutationError,
    ConditionalCollectionMutationRepository,
    ConditionalCollectionMutationResult,
    ConditionalCollectionRecordNotFoundError,
    ConditionalCollectionRepositoryError,
    ConditionalCollectionStateConflictError,
    ConditionalCollectionVerificationError,
)
from collection_management.workflow_collection_mutation_command import (
    CollectionMutationCommand,
    CollectionMutationCommandError,
)


class CollectionMutationExecutionError(Exception):
    """A controlled collection mutation could not be executed safely."""


class InvalidCollectionMutationExecutionContextError(
    CollectionMutationExecutionError
):
    """The command, repository, or reconstructed result is invalid."""


class CollectionMutationTargetNotFoundError(
    CollectionMutationExecutionError
):
    """The command's exact target record does not exist."""

    def __init__(self, record_id: str) -> None:
        self.record_id = record_id
        super().__init__(
            f"Collection mutation target {record_id!r} was not found."
        )


class CollectionMutationStaleStateError(CollectionMutationExecutionError):
    """Authoritative state matches neither expected nor desired state."""

    def __init__(self, conflicted_fields: tuple[str, ...]) -> None:
        self.conflicted_fields = conflicted_fields
        super().__init__(
            "Collection mutation command is stale for fields "
            f"{conflicted_fields!r}."
        )


class CollectionMutationRepositoryError(CollectionMutationExecutionError):
    """The injected repository failed to complete its atomic operation."""


class CollectionMutationVerificationError(CollectionMutationExecutionError):
    """The repository replacement failed final exact-value verification."""


class CollectionMutationExecutionStatus(str, Enum):
    """Successful controlled mutation outcomes."""

    APPLIED = "APPLIED"
    ALREADY_APPLIED = "ALREADY_APPLIED"


@dataclass(frozen=True, slots=True)
class CollectionMutationExecutionResult:
    """Immutable evidence of one successful repository operation."""

    command: CollectionMutationCommand
    status: CollectionMutationExecutionStatus
    applied_fields: tuple[str, ...]
    already_applied_fields: tuple[str, ...]

    def validate(self) -> None:
        _validate_command(self.command)
        if not isinstance(self.status, CollectionMutationExecutionStatus):
            raise InvalidCollectionMutationExecutionContextError(
                "status must be a CollectionMutationExecutionStatus."
            )
        if not isinstance(self.applied_fields, tuple) or not isinstance(
            self.already_applied_fields, tuple
        ):
            raise InvalidCollectionMutationExecutionContextError(
                "Result field groups must be tuples."
            )
        expected_applied = tuple(
            field_name
            for field_name in self.command.target_fields
            if field_name in self.applied_fields
        )
        expected_already = tuple(
            field_name
            for field_name in self.command.target_fields
            if field_name in self.already_applied_fields
        )
        if (
            self.applied_fields != expected_applied
            or self.already_applied_fields != expected_already
        ):
            raise InvalidCollectionMutationExecutionContextError(
                "Result fields must retain command order."
            )
        combined = self.applied_fields + self.already_applied_fields
        if (
            len(set(combined)) != len(combined)
            or set(combined) != set(self.command.target_fields)
        ):
            raise InvalidCollectionMutationExecutionContextError(
                "Result fields must partition every command field exactly once."
            )
        expected_status = (
            CollectionMutationExecutionStatus.APPLIED
            if self.applied_fields
            else CollectionMutationExecutionStatus.ALREADY_APPLIED
        )
        if self.status is not expected_status:
            raise InvalidCollectionMutationExecutionContextError(
                "status does not match the exact repository outcome."
            )


class CollectionMutationExecutor:
    """Stateless command executor over one explicit atomic repository."""

    __slots__ = ("_repository",)

    def __init__(
        self,
        repository: ConditionalCollectionMutationRepository,
    ) -> None:
        if not isinstance(repository, ConditionalCollectionMutationRepository):
            raise InvalidCollectionMutationExecutionContextError(
                "repository must implement the conditional mutation contract."
            )
        self._repository = repository

    def execute(
        self,
        command: CollectionMutationCommand,
    ) -> CollectionMutationExecutionResult:
        _validate_command(command)
        changes = tuple(
            ConditionalCollectionFieldChange(
                field_name=item.target_field,
                expected_value=item.expected_current_value,
                desired_value=item.desired_value,
            )
            for item in command.items
        )
        for change in changes:
            try:
                change.validate()
            except ConditionalCollectionMutationError as error:
                raise InvalidCollectionMutationExecutionContextError(
                    str(error)
                ) from error

        try:
            repository_result = self._repository.mutate_fields_conditionally(
                command.target_record.record_id,
                changes,
            )
        except ConditionalCollectionRecordNotFoundError as error:
            if error.record_id != command.target_record.record_id:
                raise CollectionMutationRepositoryError(
                    "The collection repository returned mismatched missing-record "
                    "diagnostics."
                ) from error
            raise CollectionMutationTargetNotFoundError(error.record_id) from error
        except ConditionalCollectionStateConflictError as error:
            if (
                not isinstance(error.conflicted_fields, tuple)
                or not error.conflicted_fields
            ):
                raise CollectionMutationRepositoryError(
                    "The collection repository returned invalid stale-state "
                    "diagnostics."
                ) from error
            expected_conflicts = tuple(
                field_name
                for field_name in command.target_fields
                if field_name in error.conflicted_fields
            )
            if error.conflicted_fields != expected_conflicts:
                raise CollectionMutationRepositoryError(
                    "The collection repository returned invalid stale-state "
                    "diagnostics."
                ) from error
            raise CollectionMutationStaleStateError(
                error.conflicted_fields
            ) from error
        except ConditionalCollectionVerificationError as error:
            raise CollectionMutationVerificationError(
                "The collection repository could not verify the committed state."
            ) from error
        except ConditionalCollectionRepositoryError as error:
            raise CollectionMutationRepositoryError(
                "The collection repository failed during conditional mutation."
            ) from error
        except ConditionalCollectionMutationError as error:
            raise CollectionMutationRepositoryError(
                "The collection repository rejected the conditional mutation."
            ) from error
        except Exception as error:
            raise CollectionMutationRepositoryError(
                "The collection repository failed during conditional mutation."
            ) from error

        if not isinstance(
            repository_result,
            ConditionalCollectionMutationResult,
        ):
            raise CollectionMutationRepositoryError(
                "The collection repository returned an invalid mutation result."
            )
        try:
            repository_result.validate()
        except ConditionalCollectionMutationError as error:
            raise CollectionMutationRepositoryError(
                "The collection repository returned an invalid mutation result."
            ) from error

        result = CollectionMutationExecutionResult(
            command=command,
            status=(
                CollectionMutationExecutionStatus.APPLIED
                if repository_result.applied_fields
                else CollectionMutationExecutionStatus.ALREADY_APPLIED
            ),
            applied_fields=repository_result.applied_fields,
            already_applied_fields=repository_result.already_applied_fields,
        )
        try:
            result.validate()
        except InvalidCollectionMutationExecutionContextError as error:
            raise CollectionMutationRepositoryError(
                "The collection repository result does not align with the command."
            ) from error
        return result


def execute_collection_mutation(
    command: CollectionMutationCommand,
    repository: ConditionalCollectionMutationRepository,
) -> CollectionMutationExecutionResult:
    """Execute one command through an explicitly injected repository."""

    return CollectionMutationExecutor(repository).execute(command)


def _validate_command(command: object) -> None:
    if not isinstance(command, CollectionMutationCommand):
        raise InvalidCollectionMutationExecutionContextError(
            "command must be a CollectionMutationCommand."
        )
    try:
        command.validate()
    except (CollectionMutationCommandError, TypeError, ValueError) as error:
        raise InvalidCollectionMutationExecutionContextError(str(error)) from error
