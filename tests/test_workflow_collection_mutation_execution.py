"""Tests for controlled, atomic collection mutation execution."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import atomic_json
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coin_collection import CoinCollection
from collection_management.collection_mutation_repository import (
    CONDITIONAL_COLLECTION_MUTATION_FIELDS,
    ConditionalCollectionFieldChange,
    ConditionalCollectionMutationError,
    ConditionalCollectionMutationRepository,
    ConditionalCollectionMutationResult,
    ConditionalCollectionRecordNotFoundError,
    ConditionalCollectionRepositoryError,
    ConditionalCollectionStateConflictError,
    ConditionalCollectionVerificationError,
    InvalidConditionalCollectionMutationError,
)
import collection_management.collection_mutation_repository as repository_module
from collection_management.workflow_collection_change_approval_models import (
    CollectionChangeApprovalDecision,
)
from collection_management.workflow_collection_change_plan_models import (
    CollectionChangeOperation,
)
from collection_management.workflow_collection_mutation_command import (
    build_collection_mutation_command,
)
from collection_management.workflow_collection_mutation_execution import (
    CollectionMutationExecutionError,
    CollectionMutationExecutionResult,
    CollectionMutationExecutionStatus,
    CollectionMutationExecutor,
    CollectionMutationRepositoryError,
    CollectionMutationStaleStateError,
    CollectionMutationTargetNotFoundError,
    CollectionMutationVerificationError,
    InvalidCollectionMutationExecutionContextError,
    execute_collection_mutation,
)
from capture_import.lock import PackageImportLock
import collection_management.workflow_collection_mutation_execution as execution_module
from tests.test_workflow_collection_mutation_command import (
    _eligibility,
    _proposal,
)


_MODULE = "collection_management.workflow_collection_mutation_execution"
_REPOSITORY_MODULE = "collection_management.collection_mutation_repository"
class _FlushFailingHandle:
    def __init__(self, handle) -> None:
        self._handle = handle

    def __enter__(self):
        self._handle.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self._handle.__exit__(exc_type, exc, traceback)

    def write(self, value):
        return self._handle.write(value)

    def flush(self) -> None:
        raise OSError("simulated flush failure")

    def fileno(self) -> int:
        return self._handle.fileno()


class _AtomicOsFailureProxy:
    def __init__(self, *, fail_flush: bool = False, fail_fsync: bool = False):
        self._fail_flush = fail_flush
        self._fail_fsync = fail_fsync

    def __getattr__(self, name):
        return getattr(os, name)

    def fdopen(self, file_descriptor, *args, **kwargs):
        handle = os.fdopen(file_descriptor, *args, **kwargs)
        if self._fail_flush:
            return _FlushFailingHandle(handle)
        return handle

    def fsync(self, file_descriptor) -> None:
        if self._fail_fsync:
            raise OSError("simulated atomic-file fsync failure")
        os.fsync(file_descriptor)


def _command(
    *specifications: tuple[
        str,
        CollectionChangeOperation,
        str | None,
        str,
    ],
):
    proposals = tuple(
        _proposal(
            field_name,
            operation,
            current_value=current,
            proposed_value=desired,
        )
        for field_name, operation, current, desired in specifications
    )
    decisions = {
        field_name: CollectionChangeApprovalDecision.APPROVE
        for field_name, _, _, _ in specifications
    }
    return build_collection_mutation_command(
        _eligibility(proposals, decisions)
    )


class _FakeRepository:
    def __init__(
        self,
        result: ConditionalCollectionMutationResult
        | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[
            tuple[str, tuple[ConditionalCollectionFieldChange, ...]]
        ] = []

    def mutate_fields_conditionally(
        self,
        record_id: str,
        changes: tuple[ConditionalCollectionFieldChange, ...],
    ) -> ConditionalCollectionMutationResult:
        self.calls.append((record_id, changes))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class PublicContractTests(unittest.TestCase):
    def test_public_api_is_exact(self) -> None:
        expected = {
            "CollectionMutationExecutionError",
            "InvalidCollectionMutationExecutionContextError",
            "CollectionMutationTargetNotFoundError",
            "CollectionMutationStaleStateError",
            "CollectionMutationRepositoryError",
            "CollectionMutationVerificationError",
            "CollectionMutationExecutionStatus",
            "CollectionMutationExecutionResult",
            "CollectionMutationExecutor",
            "execute_collection_mutation",
        }
        actual = {
            name
            for name, value in vars(execution_module).items()
            if not name.startswith("_")
            and getattr(value, "__module__", None) == _MODULE
        }
        self.assertEqual(actual, expected)

    def test_repository_contract_public_api_and_allowlist_are_exact(self) -> None:
        expected = {
            "CONDITIONAL_COLLECTION_MUTATION_FIELDS",
            "ConditionalCollectionMutationError",
            "InvalidConditionalCollectionMutationError",
            "ConditionalCollectionRecordNotFoundError",
            "ConditionalCollectionStateConflictError",
            "ConditionalCollectionRepositoryError",
            "ConditionalCollectionVerificationError",
            "ConditionalCollectionFieldChange",
            "ConditionalCollectionMutationResult",
            "ConditionalCollectionMutationRepository",
        }
        actual = {
            name
            for name, value in vars(repository_module).items()
            if not name.startswith("_")
            and (
                name == "CONDITIONAL_COLLECTION_MUTATION_FIELDS"
                or getattr(value, "__module__", None) == _REPOSITORY_MODULE
            )
        }
        self.assertEqual(actual, expected)
        self.assertEqual(
            CONDITIONAL_COLLECTION_MUTATION_FIELDS,
            frozenset({"country", "denomination", "year"}),
        )
        self.assertIsInstance(
            _FakeRepository(
                ConditionalCollectionMutationResult(("country",), ())
            ),
            ConditionalCollectionMutationRepository,
        )

    def test_repository_contracts_are_frozen_slotted_and_strict(self) -> None:
        change = ConditionalCollectionFieldChange("country", None, "Canada")
        change.validate()
        result = ConditionalCollectionMutationResult(("country",), ())
        result.validate()
        for value in (change, result):
            self.assertFalse(hasattr(value, "__dict__"))
            with self.assertRaises(FrozenInstanceError):
                value.extra = "forbidden"  # type: ignore[attr-defined]
        for invalid in (
            ConditionalCollectionFieldChange("grade", "MS65", "MS66"),
            ConditionalCollectionFieldChange("country", "same", "same"),
            ConditionalCollectionFieldChange("country", 1, "Canada"),  # type: ignore[arg-type]
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(
                    InvalidConditionalCollectionMutationError
                ):
                    invalid.validate()
        for invalid_result in (
            ConditionalCollectionMutationResult((), ()),
            ConditionalCollectionMutationResult(("country",), ("country",)),
            ConditionalCollectionMutationResult(("grade",), ()),
        ):
            with self.subTest(invalid_result=invalid_result):
                with self.assertRaises(ConditionalCollectionMutationError):
                    invalid_result.validate()

    def test_field_allowlist_rejects_every_nonmapped_spelling(self) -> None:
        invalid_names = (
            "id",
            "record_id",
            "schema_version",
            "source_fingerprint",
            "timestamp",
            "notes",
            "unknown",
            "country.name",
            "country/name",
            "__dict__",
            "Country",
            " country",
            "country ",
            "nation",
        )
        for field_name in invalid_names:
            with self.subTest(field_name=field_name):
                with self.assertRaises(
                    InvalidConditionalCollectionMutationError
                ):
                    ConditionalCollectionFieldChange(
                        field_name,
                        "old",
                        "new",
                    ).validate()

    def test_repository_and_workflow_error_hierarchies_are_exact(self) -> None:
        for error_type in (
            InvalidConditionalCollectionMutationError,
            ConditionalCollectionRecordNotFoundError,
            ConditionalCollectionStateConflictError,
            ConditionalCollectionRepositoryError,
            ConditionalCollectionVerificationError,
        ):
            self.assertTrue(
                issubclass(error_type, ConditionalCollectionMutationError)
            )
        for error_type in (
            InvalidCollectionMutationExecutionContextError,
            CollectionMutationTargetNotFoundError,
            CollectionMutationStaleStateError,
            CollectionMutationRepositoryError,
            CollectionMutationVerificationError,
        ):
            self.assertTrue(
                issubclass(error_type, CollectionMutationExecutionError)
            )

    def test_invalid_command_and_repository_are_rejected_before_access(self) -> None:
        with self.assertRaises(InvalidCollectionMutationExecutionContextError):
            CollectionMutationExecutor(object())  # type: ignore[arg-type]
        repository = _FakeRepository()
        with self.assertRaises(InvalidCollectionMutationExecutionContextError):
            CollectionMutationExecutor(repository).execute(object())  # type: ignore[arg-type]
        self.assertEqual(repository.calls, [])

    def test_result_is_frozen_slotted_and_reconstruction_is_strict(self) -> None:
        command = _command(
            ("country", CollectionChangeOperation.UPDATE, "old", "Canada"),
            (
                "denomination",
                CollectionChangeOperation.UPDATE,
                "old-denomination",
                "25 cents",
            ),
            ("year", CollectionChangeOperation.UPDATE, "old-year", "1967"),
        )
        result = CollectionMutationExecutionResult(
            command=command,
            status=CollectionMutationExecutionStatus.APPLIED,
            applied_fields=("country", "year"),
            already_applied_fields=("denomination",),
        )
        result.validate()
        self.assertFalse(hasattr(result, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            result.status = CollectionMutationExecutionStatus.ALREADY_APPLIED  # type: ignore[misc]
        for malformed in (
            replace(result, status=CollectionMutationExecutionStatus.ALREADY_APPLIED),
            replace(result, applied_fields=()),
            replace(result, status="APPLIED"),  # type: ignore[arg-type]
            replace(result, command=object()),  # type: ignore[arg-type]
            replace(result, applied_fields=["country", "year"]),  # type: ignore[arg-type]
            replace(result, applied_fields=("year", "country")),
            replace(result, applied_fields=("country", "country")),
            replace(
                result,
                already_applied_fields=("denomination", "denomination"),
            ),
            replace(result, already_applied_fields=("country", "denomination")),
            replace(result, applied_fields=("country",)),
            replace(result, applied_fields=("country", "grade")),
            replace(
                result,
                command=replace(command, items=(object(),)),  # type: ignore[arg-type]
            ),
            CollectionMutationExecutionResult(
                command=command,
                status=CollectionMutationExecutionStatus.ALREADY_APPLIED,
                applied_fields=(),
                already_applied_fields=("country", "denomination"),
            ),
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaises(
                    InvalidCollectionMutationExecutionContextError
                ):
                    malformed.validate()


class ExecutorBehaviorTests(unittest.TestCase):
    def test_executor_translates_exact_command_values_once(self) -> None:
        command = _command(
            ("country", CollectionChangeOperation.ADD, None, "Canada"),
            ("year", CollectionChangeOperation.UPDATE, "", "1967"),
        )
        repository = _FakeRepository(
            ConditionalCollectionMutationResult(
                applied_fields=("country", "year"),
                already_applied_fields=(),
            )
        )

        result = execute_collection_mutation(command, repository)

        self.assertIs(result.command, command)
        self.assertIs(result.status, CollectionMutationExecutionStatus.APPLIED)
        self.assertEqual(len(repository.calls), 1)
        record_id, changes = repository.calls[0]
        self.assertEqual(record_id, "record-1")
        self.assertEqual(
            changes,
            (
                ConditionalCollectionFieldChange("country", None, "Canada"),
                ConditionalCollectionFieldChange("year", "", "1967"),
            ),
        )

    def test_mixed_and_fully_already_applied_results_are_deterministic(self) -> None:
        command = _command(
            ("country", CollectionChangeOperation.UPDATE, "old", "Canada"),
            ("year", CollectionChangeOperation.UPDATE, "old", "1967"),
        )
        mixed = execute_collection_mutation(
            command,
            _FakeRepository(
                ConditionalCollectionMutationResult(
                    applied_fields=("year",),
                    already_applied_fields=("country",),
                )
            ),
        )
        self.assertIs(mixed.status, CollectionMutationExecutionStatus.APPLIED)
        self.assertEqual(mixed.applied_fields, ("year",))
        self.assertEqual(mixed.already_applied_fields, ("country",))

        repeated = execute_collection_mutation(
            command,
            _FakeRepository(
                ConditionalCollectionMutationResult(
                    applied_fields=(),
                    already_applied_fields=("country", "year"),
                )
            ),
        )
        self.assertIs(
            repeated.status,
            CollectionMutationExecutionStatus.ALREADY_APPLIED,
        )

    def test_repository_failures_are_typed_and_chained(self) -> None:
        command = _command(
            ("country", CollectionChangeOperation.UPDATE, "old", "Canada"),
        )
        cases = (
            (
                ConditionalCollectionRecordNotFoundError("record-1"),
                CollectionMutationTargetNotFoundError,
            ),
            (
                ConditionalCollectionStateConflictError(("country",)),
                CollectionMutationStaleStateError,
            ),
            (
                ConditionalCollectionRepositoryError("failed"),
                CollectionMutationRepositoryError,
            ),
            (
                ConditionalCollectionVerificationError("failed"),
                CollectionMutationVerificationError,
            ),
            (OSError("failed"), CollectionMutationRepositoryError),
        )
        for source, expected in cases:
            with self.subTest(source=type(source).__name__):
                with self.assertRaises(expected) as raised:
                    execute_collection_mutation(
                        command,
                        _FakeRepository(error=source),
                    )
                self.assertIs(raised.exception.__cause__, source)

    def test_malformed_repository_error_diagnostics_fail_closed(self) -> None:
        command = _command(
            ("country", CollectionChangeOperation.UPDATE, "old", "Canada"),
            ("year", CollectionChangeOperation.UPDATE, "old-year", "1967"),
        )
        malformed_stale_list = ConditionalCollectionStateConflictError(
            ("country",)
        )
        malformed_stale_list.conflicted_fields = ["country"]  # type: ignore[assignment]
        errors = (
            ConditionalCollectionRecordNotFoundError("different-record"),
            ConditionalCollectionStateConflictError(("grade",)),
            ConditionalCollectionStateConflictError(("year", "country")),
            ConditionalCollectionStateConflictError(("country", "country")),
            ConditionalCollectionStateConflictError(()),
            malformed_stale_list,
        )
        for source in errors:
            with self.subTest(source=source):
                with self.assertRaises(
                    CollectionMutationRepositoryError
                ) as raised:
                    execute_collection_mutation(
                        command,
                        _FakeRepository(error=source),
                    )
                self.assertIs(raised.exception.__cause__, source)

    def test_wrapped_messages_do_not_republish_repository_details(self) -> None:
        command = _command(
            ("country", CollectionChangeOperation.UPDATE, "old", "Canada"),
        )
        secret = "credential=do-not-copy"
        cases = (
            (
                ConditionalCollectionVerificationError(secret),
                CollectionMutationVerificationError,
            ),
            (
                InvalidConditionalCollectionMutationError(secret),
                CollectionMutationRepositoryError,
            ),
            (OSError(secret), CollectionMutationRepositoryError),
        )
        for source, expected in cases:
            with self.subTest(source=type(source).__name__):
                with self.assertRaises(expected) as raised:
                    execute_collection_mutation(
                        command,
                        _FakeRepository(error=source),
                    )
                self.assertNotIn(secret, str(raised.exception))

    def test_invalid_repository_result_fails_closed(self) -> None:
        command = _command(
            ("country", CollectionChangeOperation.UPDATE, "old", "Canada"),
        )
        repository = _FakeRepository(
            ConditionalCollectionMutationResult(
                applied_fields=("year",),
                already_applied_fields=(),
            )
        )
        with self.assertRaises(CollectionMutationRepositoryError):
            execute_collection_mutation(command, repository)

    def test_malformed_and_duplicate_commands_fail_before_repository_access(
        self,
    ) -> None:
        command = _command(
            ("country", CollectionChangeOperation.UPDATE, "old", "Canada"),
        )
        repository = _FakeRepository()
        for malformed in (
            replace(command, items=()),
            replace(command, items=(command.items[0], command.items[0])),
        ):
            with self.subTest(item_count=len(malformed.items)):
                with self.assertRaises(
                    InvalidCollectionMutationExecutionContextError
                ):
                    execute_collection_mutation(malformed, repository)
        self.assertEqual(repository.calls, [])


class ConcreteRepositoryCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "collection.json"

    def _write(self, records: list[dict[str, object]]) -> None:
        self.path.write_text(
            json.dumps(records, ensure_ascii=False),
            encoding="utf-8",
        )

    def _read(self) -> list[dict[str, object]]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _repository(self) -> CoinCollection:
        return CoinCollection(str(self.path))

    def test_atomic_multi_field_apply_preserves_unrelated_raw_data(self) -> None:
        self._write(
            [
                {
                    "id": "record-1",
                    "country": "old-country",
                    "denomination": "",
                    "year": "old-year",
                    "future_field": {"preserve": True},
                },
                {"id": "record-2", "country": "France"},
            ]
        )
        repository = self._repository()

        result = repository.mutate_fields_conditionally(
            "record-1",
            (
                ConditionalCollectionFieldChange(
                    "country", "old-country", "Canada"
                ),
                ConditionalCollectionFieldChange("year", "old-year", "1967"),
            ),
        )

        self.assertEqual(result.applied_fields, ("country", "year"))
        records = self._read()
        self.assertEqual(records[0]["country"], "Canada")
        self.assertEqual(records[0]["year"], "1967")
        self.assertEqual(records[0]["denomination"], "")
        self.assertEqual(records[0]["future_field"], {"preserve": True})
        self.assertEqual(records[1], {"id": "record-2", "country": "France"})

    def test_absent_and_empty_are_exactly_distinct(self) -> None:
        self._write([{"id": "record-1", "country": ""}])
        repository = self._repository()
        before = self.path.read_bytes()
        with self.assertRaises(ConditionalCollectionStateConflictError):
            repository.mutate_fields_conditionally(
                "record-1",
                (
                    ConditionalCollectionFieldChange(
                        "country", None, "Canada"
                    ),
                ),
            )
        self.assertEqual(self.path.read_bytes(), before)

        result = repository.mutate_fields_conditionally(
            "record-1",
            (
                ConditionalCollectionFieldChange(
                    "year", None, "1967"
                ),
            ),
        )
        self.assertEqual(result.applied_fields, ("year",))
        self.assertEqual(self._read()[0]["year"], "1967")

    def test_mixed_already_applied_and_expected_state_uses_one_replace(self) -> None:
        self._write(
            [
                {
                    "id": "record-1",
                    "country": "Canada",
                    "year": "old-year",
                }
            ]
        )
        repository = self._repository()
        with patch(
            "coin_collection.write_json_atomically",
            wraps=atomic_json.write_json_atomically,
        ) as writer:
            result = repository.mutate_fields_conditionally(
                "record-1",
                (
                    ConditionalCollectionFieldChange(
                        "country", "old-country", "Canada"
                    ),
                    ConditionalCollectionFieldChange(
                        "year", "old-year", "1967"
                    ),
                ),
            )
        self.assertEqual(writer.call_count, 1)
        self.assertEqual(result.applied_fields, ("year",))
        self.assertEqual(result.already_applied_fields, ("country",))

    def test_stale_field_rejects_entire_batch_without_write(self) -> None:
        self._write(
            [
                {
                    "id": "record-1",
                    "country": "unexpected",
                    "year": "old-year",
                }
            ]
        )
        repository = self._repository()
        before = self.path.read_bytes()
        with patch("coin_collection.write_json_atomically") as writer:
            with self.assertRaises(
                ConditionalCollectionStateConflictError
            ) as raised:
                repository.mutate_fields_conditionally(
                    "record-1",
                    (
                        ConditionalCollectionFieldChange(
                            "country", "old-country", "Canada"
                        ),
                        ConditionalCollectionFieldChange(
                            "year", "old-year", "1967"
                        ),
                    ),
                )
        self.assertEqual(raised.exception.conflicted_fields, ("country",))
        writer.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)

    def test_multiple_conflicts_retain_command_order_and_write_nothing(self) -> None:
        self._write(
            [
                {
                    "id": "record-1",
                    "country": "unexpected-country",
                    "denomination": "old-denomination",
                    "year": "unexpected-year",
                }
            ]
        )
        repository = self._repository()
        before = self.path.read_bytes()
        with self.assertRaises(
            ConditionalCollectionStateConflictError
        ) as raised:
            repository.mutate_fields_conditionally(
                "record-1",
                (
                    ConditionalCollectionFieldChange(
                        "country", "old-country", "Canada"
                    ),
                    ConditionalCollectionFieldChange(
                        "denomination", "old-denomination", "25 cents"
                    ),
                    ConditionalCollectionFieldChange(
                        "year", "old-year", "1967"
                    ),
                ),
            )
        self.assertEqual(
            raised.exception.conflicted_fields,
            ("country", "year"),
        )
        self.assertEqual(self.path.read_bytes(), before)

    def test_already_desired_plus_conflict_rejects_entire_batch(self) -> None:
        self._write(
            [
                {
                    "id": "record-1",
                    "country": "Canada",
                    "year": "unexpected-year",
                }
            ]
        )
        repository = self._repository()
        before = self.path.read_bytes()
        with self.assertRaises(
            ConditionalCollectionStateConflictError
        ) as raised:
            repository.mutate_fields_conditionally(
                "record-1",
                (
                    ConditionalCollectionFieldChange(
                        "country", "old-country", "Canada"
                    ),
                    ConditionalCollectionFieldChange(
                        "year", "old-year", "1967"
                    ),
                ),
            )
        self.assertEqual(raised.exception.conflicted_fields, ("year",))
        self.assertEqual(self.path.read_bytes(), before)

    def test_fully_already_applied_is_a_write_free_success(self) -> None:
        self._write([{"id": "record-1", "country": "Canada"}])
        repository = self._repository()
        before = self.path.read_bytes()
        with patch("coin_collection.write_json_atomically") as writer:
            result = repository.mutate_fields_conditionally(
                "record-1",
                (
                    ConditionalCollectionFieldChange(
                        "country", "old-country", "Canada"
                    ),
                ),
            )
        writer.assert_not_called()
        self.assertEqual(result.applied_fields, ())
        self.assertEqual(result.already_applied_fields, ("country",))
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_duplicate_null_and_unsupported_states_fail_closed(self) -> None:
        cases = (
            (
                [{"id": "other"}],
                ConditionalCollectionRecordNotFoundError,
                ConditionalCollectionFieldChange(
                    "country", "old", "Canada"
                ),
            ),
            (
                [{"id": "record-1"}, {"id": "record-1"}],
                ConditionalCollectionRepositoryError,
                ConditionalCollectionFieldChange(
                    "country", None, "Canada"
                ),
            ),
            (
                [{"id": "record-1", "country": None}],
                ConditionalCollectionRepositoryError,
                ConditionalCollectionFieldChange(
                    "country", None, "Canada"
                ),
            ),
            (
                [{"id": "record-1", "grade": "MS65"}],
                InvalidConditionalCollectionMutationError,
                ConditionalCollectionFieldChange(
                    "grade", "MS65", "MS66"
                ),
            ),
        )
        for records, expected, change in cases:
            with self.subTest(expected=expected.__name__):
                self._write(records)
                repository = self._repository()
                before = self.path.read_bytes()
                with self.assertRaises(expected):
                    repository.mutate_fields_conditionally(
                        "record-1", (change,)
                    )
                self.assertEqual(self.path.read_bytes(), before)

    def test_duplicate_changes_and_fuzzy_record_ids_are_rejected(self) -> None:
        self._write([{"id": "Record-1", "country": "old"}])
        repository = self._repository()
        change = ConditionalCollectionFieldChange(
            "country", "old", "Canada"
        )
        before = self.path.read_bytes()
        for record_id in ("record-1", " Record-1", "Record-1 "):
            with self.subTest(record_id=record_id):
                with self.assertRaises(
                    ConditionalCollectionRecordNotFoundError
                ):
                    repository.mutate_fields_conditionally(
                        record_id, (change,)
                    )
        with self.assertRaises(InvalidConditionalCollectionMutationError):
            repository.mutate_fields_conditionally(
                "Record-1", (change, change)
            )
        self.assertEqual(self.path.read_bytes(), before)

    def test_malformed_repository_content_fails_without_repair_or_creation(
        self,
    ) -> None:
        self.path.write_text("{not-json", encoding="utf-8")
        repository = self._repository()
        before = self.path.read_bytes()
        with self.assertRaises(ConditionalCollectionRepositoryError) as raised:
            repository.mutate_fields_conditionally(
                "record-1",
                (
                    ConditionalCollectionFieldChange(
                        "country", None, "Canada"
                    ),
                ),
            )
        self.assertEqual(
            str(raised.exception),
            "The collection repository could not complete the conditional "
            "mutation.",
        )
        self.assertEqual(self.path.read_bytes(), before)

    def test_replace_failure_preserves_prior_bytes_and_cleans_temporary(self) -> None:
        self._write([{"id": "record-1", "country": "old"}])
        repository = self._repository()
        before = self.path.read_bytes()
        with patch(
            "atomic_json.os.replace",
            side_effect=OSError("simulated replacement failure"),
        ):
            with self.assertRaises(ConditionalCollectionRepositoryError):
                repository.mutate_fields_conditionally(
                    "record-1",
                    (
                        ConditionalCollectionFieldChange(
                            "country", "old", "Canada"
                        ),
                    ),
                )
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(
            list(Path(self.temporary.name).glob("*.tmp")),
            [],
        )

    def test_all_pre_replace_failure_stages_preserve_prior_bytes(self) -> None:
        def execute_with_failure(failure_patch) -> None:
            self._write([{"id": "record-1", "country": "old"}])
            repository = self._repository()
            before = self.path.read_bytes()
            with failure_patch:
                with self.assertRaises(ConditionalCollectionRepositoryError):
                    repository.mutate_fields_conditionally(
                        "record-1",
                        (
                            ConditionalCollectionFieldChange(
                                "country", "old", "Canada"
                            ),
                        ),
                    )
            self.assertEqual(self.path.read_bytes(), before)
            self.assertEqual(
                tuple(
                    path
                    for path in Path(self.temporary.name).iterdir()
                    if path.suffix == ".tmp"
                ),
                (),
            )

        failures = (
            (
                "temporary creation",
                patch(
                    "atomic_json.tempfile.mkstemp",
                    side_effect=OSError("simulated temporary creation failure"),
                ),
            ),
            (
                "temporary write",
                patch(
                    "atomic_json.json.dump",
                    side_effect=OSError("simulated temporary write failure"),
                ),
            ),
            (
                "flush",
                patch(
                    "atomic_json.os",
                    _AtomicOsFailureProxy(fail_flush=True),
                ),
            ),
        )
        for name, failure_patch in failures:
            with self.subTest(stage=name):
                execute_with_failure(failure_patch)

        with self.subTest(stage="fsync"):
            execute_with_failure(
                patch(
                    "atomic_json.os",
                    _AtomicOsFailureProxy(fail_fsync=True),
                )
            )

    def test_verification_reread_failure_reports_post_replace_uncertainty(
        self,
    ) -> None:
        self._write([{"id": "record-1", "country": "old"}])
        repository = self._repository()
        original_loader = repository._load_raw_record_for_conditional_mutation
        calls = 0

        def fail_second_load(record_id: str):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated verification read failure")
            return original_loader(record_id)

        with patch.object(
            repository,
            "_load_raw_record_for_conditional_mutation",
            side_effect=fail_second_load,
        ):
            with self.assertRaises(
                ConditionalCollectionVerificationError
            ) as raised:
                repository.mutate_fields_conditionally(
                    "record-1",
                    (
                        ConditionalCollectionFieldChange(
                            "country", "old", "Canada"
                        ),
                    ),
                )
        self.assertIsInstance(raised.exception.__cause__, OSError)
        self.assertEqual(self._read()[0]["country"], "Canada")

    def test_target_disappearance_during_verification_is_verification_failure(
        self,
    ) -> None:
        self._write([{"id": "record-1", "country": "old"}])
        repository = self._repository()
        original_loader = repository._load_raw_record_for_conditional_mutation
        calls = 0

        def disappear_on_second_load(record_id: str):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ConditionalCollectionRecordNotFoundError(record_id)
            return original_loader(record_id)

        with patch.object(
            repository,
            "_load_raw_record_for_conditional_mutation",
            side_effect=disappear_on_second_load,
        ):
            with self.assertRaises(
                ConditionalCollectionVerificationError
            ) as raised:
                repository.mutate_fields_conditionally(
                    "record-1",
                    (
                        ConditionalCollectionFieldChange(
                            "country", "old", "Canada"
                        ),
                    ),
                )
        self.assertIsInstance(
            raised.exception.__cause__,
            ConditionalCollectionRecordNotFoundError,
        )
        self.assertEqual(self._read()[0]["country"], "Canada")

    def test_structural_clear_removes_key_without_touching_other_fields(self) -> None:
        self._write(
            [
                {
                    "id": "record-1",
                    "country": "Canada",
                    "year": "1967",
                }
            ]
        )
        result = self._repository().mutate_fields_conditionally(
            "record-1",
            (
                ConditionalCollectionFieldChange(
                    "country", "Canada", None
                ),
            ),
        )
        self.assertEqual(result.applied_fields, ("country",))
        self.assertNotIn("country", self._read()[0])
        self.assertEqual(self._read()[0]["year"], "1967")

    def test_exact_string_values_are_never_normalized(self) -> None:
        values = (
            (" leading ", " trailing "),
            ("canada", "Canada"),
            ("001967", "1967"),
            ("25-cent!", "25 cents?"),
            ("Québec", "Qu\u00e9bec "),
        )
        for index, (expected, desired) in enumerate(values):
            with self.subTest(expected=expected, desired=desired):
                self._write(
                    [{"id": "record-1", "country": expected}]
                )
                result = self._repository().mutate_fields_conditionally(
                    "record-1",
                    (
                        ConditionalCollectionFieldChange(
                            "country", expected, desired
                        ),
                    ),
                )
                self.assertEqual(result.applied_fields, ("country",))
                self.assertEqual(self._read()[0]["country"], desired)

    def test_exact_conflicts_preserve_space_and_unicode_code_points(self) -> None:
        exact_cases = (
            (None, " "),
            ("", " "),
            ("Québec", "Que\u0301bec"),
        )
        for expected, actual in exact_cases:
            with self.subTest(expected=expected, actual=actual):
                self._write(
                    [{"id": "record-1", "country": actual}]
                )
                before = self.path.read_bytes()
                with self.assertRaises(
                    ConditionalCollectionStateConflictError
                ):
                    self._repository().mutate_fields_conditionally(
                        "record-1",
                        (
                            ConditionalCollectionFieldChange(
                                "country", expected, "Canada"
                            ),
                        ),
                    )
                self.assertEqual(self.path.read_bytes(), before)

    def test_same_command_is_idempotent_and_second_execution_does_not_write(
        self,
    ) -> None:
        self._write([{"id": "record-1", "country": "old-country"}])
        repository = self._repository()
        command = _command(
            (
                "country",
                CollectionChangeOperation.UPDATE,
                "old-country",
                "Canada",
            ),
        )
        first = execute_collection_mutation(command, repository)
        with patch("coin_collection.write_json_atomically") as writer:
            second = execute_collection_mutation(command, repository)
        self.assertIs(first.status, CollectionMutationExecutionStatus.APPLIED)
        self.assertIs(
            second.status,
            CollectionMutationExecutionStatus.ALREADY_APPLIED,
        )
        writer.assert_not_called()

    def test_existing_global_lease_blocks_check_and_write_entry(self) -> None:
        self._write([{"id": "record-1", "country": "old"}])
        repository = self._repository()
        lock_path = (
            Path(self.temporary.name)
            / "imports"
            / "package_import.lock"
        )
        before = self.path.read_bytes()
        with PackageImportLock.acquire(lock_path):
            with self.assertRaises(ConditionalCollectionRepositoryError):
                repository.mutate_fields_conditionally(
                    "record-1",
                    (
                        ConditionalCollectionFieldChange(
                            "country", "old", "Canada"
                        ),
                    ),
                )
        self.assertEqual(self.path.read_bytes(), before)

    def test_final_verification_failure_is_explicit(self) -> None:
        self._write([{"id": "record-1", "country": "old"}])
        repository = self._repository()
        original_loader = repository._load_raw_record_for_conditional_mutation
        calls = 0

        def load_with_failed_verification(record_id: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return original_loader(record_id)
            payload, target = original_loader(record_id)
            target["country"] = "intervening-external-write"
            return payload, target

        with patch.object(
            repository,
            "_load_raw_record_for_conditional_mutation",
            side_effect=load_with_failed_verification,
        ):
            with self.assertRaisesRegex(
                ConditionalCollectionVerificationError,
                "desired 'country' value",
            ):
                repository.mutate_fields_conditionally(
                    "record-1",
                    (
                        ConditionalCollectionFieldChange(
                            "country", "old", "Canada"
                        ),
                    ),
                )

    def test_executor_and_concrete_repository_integration(self) -> None:
        self._write([{"id": "record-1", "country": "old-country"}])
        command = _command(
            (
                "country",
                CollectionChangeOperation.UPDATE,
                "old-country",
                "Canada",
            ),
        )

        result = execute_collection_mutation(command, self._repository())

        self.assertIs(result.status, CollectionMutationExecutionStatus.APPLIED)
        self.assertEqual(self._read()[0]["country"], "Canada")
