"""Tests for pure exact collection-record comparison."""

from __future__ import annotations

import ast
from dataclasses import replace
import importlib
import inspect
import unittest

from tests.frozen_dataclass_compat import (
    assert_frozen_slotted_assignment_rejected,
)

from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationProvenance,
    ConfirmedObservationSource,
)
from collection_management.workflow_collection_change_plan_models import (
    CollectionRecordReference,
)
from collection_management.workflow_confirmed_collection_field_mapper import (
    CollectionTargetField,
    ConfirmedCollectionFieldMapping,
    ConfirmedCollectionFieldMappingResult,
)
import collection_management.workflow_collection_record_comparison as comparison_module
from collection_management.workflow_collection_record_comparison import (
    CollectionFieldComparison,
    CollectionFieldComparisonOutcome,
    CollectionRecordComparisonError,
    CollectionRecordComparisonResult,
    CollectionRecordComparisonService,
    CollectionRecordFieldAvailability,
    CollectionRecordFieldSnapshot,
    CollectionRecordSnapshot,
    InvalidCollectionRecordComparisonContextError,
    MissingCollectionRecordSnapshotFieldError,
    compare_mapped_collection_fields,
)


_MODULE = "collection_management.workflow_collection_record_comparison"
_VALUES = {
    CollectionTargetField.COUNTRY: "Canada",
    CollectionTargetField.DENOMINATION: "25 cents",
    CollectionTargetField.YEAR: "1967",
}


def _observation(
    target: CollectionTargetField,
    value: str | None = None,
    *,
    source_coin_id: str = "source-coin-1",
    reviewer_id: str = "collector-1",
) -> ConfirmedFieldObservation:
    submitted = _VALUES[target] if value is None else value
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id=source_coin_id,
        field_name=target.value,
        submitted_value=submitted,
        canonical_value=None,
        reviewer_id=reviewer_id,
        provenance=(
            ConfirmedObservationProvenance(
                provider_id="test-ocr",
                image_role="front",
                artifact_key=f"crop-{target.value}",
                source_value=submitted,
                confidence_score=95.0,
                evidence=("collector confirmed",),
            ),
        ),
        source_type=ConfirmedObservationSource.OCR_REVIEW,
        rationale="Confirmed by collector.",
    )


def _mapping(
    target: CollectionTargetField,
    value: str | None = None,
) -> ConfirmedCollectionFieldMapping:
    observation = _observation(target, value)
    result = ConfirmedCollectionFieldMapping(
        source_observation=observation,
        target_field=target,
        mapped_value=observation.submitted_value,
    )
    result.validate()
    return result


def _mapping_result(
    *targets: CollectionTargetField,
) -> ConfirmedCollectionFieldMappingResult:
    selected = targets or (CollectionTargetField.COUNTRY,)
    mappings = tuple(
        sorted(
            (_mapping(target) for target in selected),
            key=lambda item: item.target_field.value,
        )
    )
    result = ConfirmedCollectionFieldMappingResult(
        source_coin_id="source-coin-1",
        reviewer_id="collector-1",
        mappings=mappings,
        review_session_id="review-session-1",
        source_fingerprint="opaque-source-fingerprint",
    )
    result.validate()
    return result


def _field(
    target: CollectionTargetField,
    value: str | None = None,
    *,
    availability: CollectionRecordFieldAvailability = (
        CollectionRecordFieldAvailability.PRESENT
    ),
) -> CollectionRecordFieldSnapshot:
    if availability is CollectionRecordFieldAvailability.PRESENT:
        selected_value = _VALUES[target] if value is None else value
    else:
        selected_value = None
    return CollectionRecordFieldSnapshot(
        target_field=target,
        availability=availability,
        value=selected_value,
    )


def _snapshot(
    *fields: CollectionRecordFieldSnapshot,
    record_id: str = "record-1",
) -> CollectionRecordSnapshot:
    selected = fields or (_field(CollectionTargetField.COUNTRY),)
    return CollectionRecordSnapshot(
        target_record=CollectionRecordReference(record_id=record_id),
        fields=tuple(
            sorted(selected, key=lambda item: item.target_field.value)
        ),
    )


class SnapshotContractTests(unittest.TestCase):
    def test_availability_vocabulary_is_exact(self) -> None:
        self.assertEqual(
            tuple(item.value for item in CollectionRecordFieldAvailability),
            ("PRESENT", "ABSENT", "UNAVAILABLE"),
        )

    def test_outcome_vocabulary_is_exact(self) -> None:
        self.assertEqual(
            tuple(item.value for item in CollectionFieldComparisonOutcome),
            (
                "ABSENT",
                "EMPTY",
                "UNAVAILABLE",
                "EXACT_MATCH",
                "DIFFERENT",
            ),
        )

    def test_present_accepts_exact_empty_string(self) -> None:
        field = _field(CollectionTargetField.COUNTRY, "")
        field.validate()
        self.assertEqual(field.value, "")

    def test_present_requires_string(self) -> None:
        field = CollectionRecordFieldSnapshot(
            target_field=CollectionTargetField.COUNTRY,
            availability=CollectionRecordFieldAvailability.PRESENT,
            value=None,
        )
        with self.assertRaisesRegex(TypeError, "require a string"):
            field.validate()

    def test_absent_requires_no_value(self) -> None:
        field = CollectionRecordFieldSnapshot(
            target_field=CollectionTargetField.COUNTRY,
            availability=CollectionRecordFieldAvailability.ABSENT,
            value="",
        )
        with self.assertRaisesRegex(ValueError, "must not carry"):
            field.validate()

    def test_unavailable_requires_no_value(self) -> None:
        field = CollectionRecordFieldSnapshot(
            target_field=CollectionTargetField.COUNTRY,
            availability=CollectionRecordFieldAvailability.UNAVAILABLE,
            value="Canada",
        )
        with self.assertRaisesRegex(ValueError, "must not carry"):
            field.validate()

    def test_snapshot_requires_deterministic_order(self) -> None:
        snapshot = CollectionRecordSnapshot(
            target_record=CollectionRecordReference("record-1"),
            fields=(
                _field(CollectionTargetField.YEAR),
                _field(CollectionTargetField.COUNTRY),
            ),
        )
        with self.assertRaisesRegex(ValueError, "deterministic"):
            snapshot.validate()

    def test_snapshot_rejects_duplicate_target(self) -> None:
        snapshot = _snapshot(
            _field(CollectionTargetField.COUNTRY),
            _field(CollectionTargetField.COUNTRY),
        )
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            snapshot.validate()

    def test_snapshot_requires_nonempty_tuple(self) -> None:
        snapshot = CollectionRecordSnapshot(
            target_record=CollectionRecordReference("record-1"),
            fields=(),
        )
        with self.assertRaisesRegex(ValueError, "at least one"):
            snapshot.validate()

    def test_snapshot_reuses_record_reference_contract(self) -> None:
        snapshot = _snapshot(record_id="record/exact identity")
        snapshot.validate()
        self.assertEqual(
            snapshot.target_record,
            CollectionRecordReference("record/exact identity"),
        )

    def test_snapshot_rejects_blank_record_id(self) -> None:
        snapshot = _snapshot(record_id="   ")
        with self.assertRaisesRegex(ValueError, "record_id"):
            snapshot.validate()

    def test_snapshot_rejects_unsupported_extra_target_type(self) -> None:
        field = CollectionRecordFieldSnapshot(
            target_field="future_field",  # type: ignore[arg-type]
            availability=CollectionRecordFieldAvailability.PRESENT,
            value="value",
        )
        with self.assertRaisesRegex(TypeError, "CollectionTargetField"):
            field.validate()


class ExactClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = CollectionRecordComparisonService()
        self.mapping_result = _mapping_result(
            CollectionTargetField.COUNTRY
        )

    def _compare(
        self,
        field: CollectionRecordFieldSnapshot,
    ) -> CollectionFieldComparison:
        return self.service.compare(
            self.mapping_result,
            _snapshot(field),
        ).comparisons[0]

    def test_absent_is_distinct(self) -> None:
        comparison = self._compare(
            _field(
                CollectionTargetField.COUNTRY,
                availability=CollectionRecordFieldAvailability.ABSENT,
            )
        )
        self.assertIs(
            comparison.outcome,
            CollectionFieldComparisonOutcome.ABSENT,
        )
        self.assertIsNone(comparison.current_value)

    def test_empty_is_distinct(self) -> None:
        comparison = self._compare(
            _field(CollectionTargetField.COUNTRY, "")
        )
        self.assertIs(
            comparison.outcome,
            CollectionFieldComparisonOutcome.EMPTY,
        )
        self.assertEqual(comparison.current_value, "")

    def test_unavailable_is_distinct(self) -> None:
        comparison = self._compare(
            _field(
                CollectionTargetField.COUNTRY,
                availability=CollectionRecordFieldAvailability.UNAVAILABLE,
            )
        )
        self.assertIs(
            comparison.outcome,
            CollectionFieldComparisonOutcome.UNAVAILABLE,
        )
        self.assertIsNone(comparison.current_value)

    def test_exact_match_uses_exact_string_equality(self) -> None:
        comparison = self._compare(
            _field(CollectionTargetField.COUNTRY, "Canada")
        )
        self.assertIs(
            comparison.outcome,
            CollectionFieldComparisonOutcome.EXACT_MATCH,
        )

    def test_case_difference_is_different(self) -> None:
        comparison = self._compare(
            _field(CollectionTargetField.COUNTRY, "canada")
        )
        self.assertIs(
            comparison.outcome,
            CollectionFieldComparisonOutcome.DIFFERENT,
        )

    def test_whitespace_difference_is_different(self) -> None:
        comparison = self._compare(
            _field(CollectionTargetField.COUNTRY, " Canada ")
        )
        self.assertIs(
            comparison.outcome,
            CollectionFieldComparisonOutcome.DIFFERENT,
        )

    def test_punctuation_difference_is_different(self) -> None:
        comparison = self._compare(
            _field(CollectionTargetField.COUNTRY, "Canada.")
        )
        self.assertIs(
            comparison.outcome,
            CollectionFieldComparisonOutcome.DIFFERENT,
        )

    def test_numeric_looking_values_remain_exact_strings(self) -> None:
        mapping = ConfirmedCollectionFieldMapping(
            source_observation=_observation(
                CollectionTargetField.YEAR,
                "01967",
            ),
            target_field=CollectionTargetField.YEAR,
            mapped_value="01967",
        )
        mapping_result = ConfirmedCollectionFieldMappingResult(
            source_coin_id="source-coin-1",
            reviewer_id="collector-1",
            mappings=(mapping,),
        )
        result = self.service.compare(
            mapping_result,
            _snapshot(_field(CollectionTargetField.YEAR, "1967")),
        )
        self.assertEqual(result.comparisons[0].mapped_value, "01967")
        self.assertEqual(result.comparisons[0].current_value, "1967")
        self.assertIs(
            result.comparisons[0].outcome,
            CollectionFieldComparisonOutcome.DIFFERENT,
        )

    def test_unicode_is_not_normalized(self) -> None:
        mapping = ConfirmedCollectionFieldMapping(
            source_observation=_observation(
                CollectionTargetField.COUNTRY,
                "Caf\u00e9",
            ),
            target_field=CollectionTargetField.COUNTRY,
            mapped_value="Caf\u00e9",
        )
        mapping_result = replace(
            self.mapping_result,
            mappings=(mapping,),
        )
        result = self.service.compare(
            mapping_result,
            _snapshot(
                _field(
                    CollectionTargetField.COUNTRY,
                    "Cafe\u0301",
                )
            ),
        )
        self.assertIs(
            result.comparisons[0].outcome,
            CollectionFieldComparisonOutcome.DIFFERENT,
        )

    def test_empty_current_and_empty_mapped_value_are_exact(self) -> None:
        current = _field(CollectionTargetField.COUNTRY, "")
        self.assertIs(
            comparison_module._classify_values("", current),
            CollectionFieldComparisonOutcome.EXACT_MATCH,
        )

    def test_empty_current_and_nonempty_mapped_value_are_empty(self) -> None:
        current = _field(CollectionTargetField.COUNTRY, "")
        self.assertIs(
            comparison_module._classify_values("Canada", current),
            CollectionFieldComparisonOutcome.EMPTY,
        )

    def test_empty_mapped_and_nonempty_current_value_are_different(
        self,
    ) -> None:
        current = _field(CollectionTargetField.COUNTRY, "Canada")
        self.assertIs(
            comparison_module._classify_values("", current),
            CollectionFieldComparisonOutcome.DIFFERENT,
        )

    def test_comparison_contract_rejects_false_outcome(self) -> None:
        comparison = CollectionFieldComparison(
            mapping=self.mapping_result.mappings[0],
            current_field=_field(
                CollectionTargetField.COUNTRY,
                "Canada",
            ),
            outcome=CollectionFieldComparisonOutcome.DIFFERENT,
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            comparison.validate()

    def test_comparison_contract_rejects_mismatched_target(self) -> None:
        comparison = CollectionFieldComparison(
            mapping=self.mapping_result.mappings[0],
            current_field=_field(CollectionTargetField.YEAR),
            outcome=CollectionFieldComparisonOutcome.DIFFERENT,
        )
        with self.assertRaisesRegex(ValueError, "target"):
            comparison.validate()


class ComparisonServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = CollectionRecordComparisonService()
        self.mapping_result = _mapping_result(
            CollectionTargetField.YEAR,
            CollectionTargetField.COUNTRY,
            CollectionTargetField.DENOMINATION,
        )
        self.snapshot = _snapshot(
            _field(CollectionTargetField.YEAR, "1968"),
            _field(CollectionTargetField.COUNTRY, "Canada"),
            _field(CollectionTargetField.DENOMINATION, ""),
        )

    def test_multiple_fields_compare_in_deterministic_target_order(
        self,
    ) -> None:
        result = self.service.compare(
            self.mapping_result,
            self.snapshot,
        )
        self.assertEqual(
            tuple(item.target_field.value for item in result.comparisons),
            ("country", "denomination", "year"),
        )
        self.assertEqual(
            tuple(item.outcome for item in result.comparisons),
            (
                CollectionFieldComparisonOutcome.EXACT_MATCH,
                CollectionFieldComparisonOutcome.EMPTY,
                CollectionFieldComparisonOutcome.DIFFERENT,
            ),
        )

    def test_complete_mapping_evidence_is_retained(self) -> None:
        result = self.service.compare(
            self.mapping_result,
            self.snapshot,
        )
        self.assertIs(result.mapping_result, self.mapping_result)
        for comparison, mapping in zip(
            result.comparisons,
            self.mapping_result.mappings,
        ):
            self.assertIs(comparison.mapping, mapping)
            self.assertIs(
                comparison.mapping.source_observation,
                mapping.source_observation,
            )

    def test_target_record_is_preserved_exactly(self) -> None:
        result = self.service.compare(
            self.mapping_result,
            self.snapshot,
        )
        self.assertIs(result.target_record, self.snapshot.target_record)

    def test_mapping_linkage_is_preserved(self) -> None:
        result = self.service.compare(
            self.mapping_result,
            self.snapshot,
        )
        self.assertEqual(
            result.mapping_result.review_session_id,
            "review-session-1",
        )
        self.assertEqual(
            result.mapping_result.source_fingerprint,
            "opaque-source-fingerprint",
        )
        self.assertEqual(
            result.mapping_result.source_coin_id,
            "source-coin-1",
        )
        self.assertEqual(
            result.mapping_result.reviewer_id,
            "collector-1",
        )

    def test_source_coin_id_remains_distinct_from_record_id(self) -> None:
        result = self.service.compare(
            self.mapping_result,
            self.snapshot,
        )
        self.assertEqual(result.target_record.record_id, "record-1")
        self.assertEqual(
            result.mapping_result.source_coin_id,
            "source-coin-1",
        )
        self.assertNotEqual(
            result.target_record.record_id,
            result.mapping_result.source_coin_id,
        )

    def test_missing_mapped_field_fails_closed(self) -> None:
        with self.assertRaises(
            MissingCollectionRecordSnapshotFieldError
        ) as captured:
            self.service.compare(
                self.mapping_result,
                _snapshot(_field(CollectionTargetField.COUNTRY)),
            )
        self.assertIs(
            captured.exception.target_field,
            CollectionTargetField.DENOMINATION,
        )

    def test_extra_supported_snapshot_fields_are_ignored(self) -> None:
        mapping_result = _mapping_result(CollectionTargetField.COUNTRY)
        snapshot = _snapshot(
            _field(CollectionTargetField.COUNTRY),
            _field(CollectionTargetField.YEAR),
        )
        result = self.service.compare(mapping_result, snapshot)
        self.assertEqual(len(result.comparisons), 1)
        self.assertIs(
            result.comparisons[0].target_field,
            CollectionTargetField.COUNTRY,
        )

    def test_invalid_mapping_context_fails_before_output(self) -> None:
        invalid = replace(
            self.mapping_result,
            source_coin_id="different-source",
        )
        with self.assertRaises(
            InvalidCollectionRecordComparisonContextError
        ):
            self.service.compare(invalid, self.snapshot)

    def test_invalid_snapshot_context_fails_before_output(self) -> None:
        invalid = replace(
            self.snapshot,
            fields=tuple(reversed(self.snapshot.fields)),
        )
        with self.assertRaises(
            InvalidCollectionRecordComparisonContextError
        ):
            self.service.compare(self.mapping_result, invalid)

    def test_input_types_are_strict(self) -> None:
        with self.assertRaises(TypeError):
            self.service.compare(object(), self.snapshot)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            self.service.compare(
                self.mapping_result,
                object(),  # type: ignore[arg-type]
            )

    def test_convenience_function_matches_service(self) -> None:
        expected = self.service.compare(
            self.mapping_result,
            self.snapshot,
        )
        actual = compare_mapped_collection_fields(
            self.mapping_result,
            self.snapshot,
        )
        self.assertEqual(actual, expected)

    def test_equivalent_inputs_produce_equivalent_outputs(self) -> None:
        first = self.service.compare(
            self.mapping_result,
            self.snapshot,
        )
        second = self.service.compare(
            self.mapping_result,
            self.snapshot,
        )
        self.assertEqual(first, second)

    def test_inputs_remain_unchanged_after_success(self) -> None:
        before_mapping = repr(self.mapping_result)
        before_snapshot = repr(self.snapshot)
        self.service.compare(self.mapping_result, self.snapshot)
        self.assertEqual(repr(self.mapping_result), before_mapping)
        self.assertEqual(repr(self.snapshot), before_snapshot)

    def test_inputs_remain_unchanged_after_failure(self) -> None:
        snapshot = _snapshot(_field(CollectionTargetField.COUNTRY))
        before_mapping = repr(self.mapping_result)
        before_snapshot = repr(snapshot)
        with self.assertRaises(MissingCollectionRecordSnapshotFieldError):
            self.service.compare(self.mapping_result, snapshot)
        self.assertEqual(repr(self.mapping_result), before_mapping)
        self.assertEqual(repr(snapshot), before_snapshot)

    def test_result_rejects_partial_comparisons(self) -> None:
        valid = self.service.compare(
            self.mapping_result,
            self.snapshot,
        )
        partial = replace(valid, comparisons=valid.comparisons[:-1])
        with self.assertRaisesRegex(ValueError, "every mapped target"):
            partial.validate()

    def test_result_rejects_foreign_mapping(self) -> None:
        valid = self.service.compare(
            self.mapping_result,
            self.snapshot,
        )
        foreign = _mapping(CollectionTargetField.COUNTRY, "France")
        comparison = replace(
            valid.comparisons[0],
            mapping=foreign,
            outcome=CollectionFieldComparisonOutcome.DIFFERENT,
        )
        invalid = replace(
            valid,
            comparisons=(comparison,) + valid.comparisons[1:],
        )
        with self.assertRaisesRegex(ValueError, "mapping_result"):
            invalid.validate()


class ImmutabilityAndBoundaryTests(unittest.TestCase):
    def test_contracts_are_frozen_and_slotted(self) -> None:
        values = (
            _field(CollectionTargetField.COUNTRY),
            _snapshot(_field(CollectionTargetField.COUNTRY)),
            CollectionRecordComparisonService().compare(
                _mapping_result(CollectionTargetField.COUNTRY),
                _snapshot(_field(CollectionTargetField.COUNTRY)),
            ).comparisons[0],
            CollectionRecordComparisonService().compare(
                _mapping_result(CollectionTargetField.COUNTRY),
                _snapshot(_field(CollectionTargetField.COUNTRY)),
            ),
        )
        for value in values:
            with self.subTest(contract=type(value).__name__):
                self.assertFalse(hasattr(value, "__dict__"))
                with assert_frozen_slotted_assignment_rejected(self, value):
                    value.extra = "mutation"  # type: ignore[attr-defined]

    def test_service_is_stateless_and_slotted(self) -> None:
        service = CollectionRecordComparisonService()
        self.assertFalse(hasattr(service, "__dict__"))

    def test_error_hierarchy_is_narrow(self) -> None:
        self.assertTrue(
            issubclass(
                InvalidCollectionRecordComparisonContextError,
                CollectionRecordComparisonError,
            )
        )
        self.assertTrue(
            issubclass(
                MissingCollectionRecordSnapshotFieldError,
                CollectionRecordComparisonError,
            )
        )

    def test_no_speculative_serialization_surface(self) -> None:
        for contract in (
            CollectionRecordFieldSnapshot,
            CollectionRecordSnapshot,
            CollectionFieldComparison,
            CollectionRecordComparisonResult,
        ):
            with self.subTest(contract=contract.__name__):
                self.assertFalse(hasattr(contract, "to_dict"))
                self.assertFalse(hasattr(contract, "from_dict"))

    def test_result_contains_no_plan_or_mutation_fields(self) -> None:
        self.assertEqual(
            tuple(CollectionRecordComparisonResult.__dataclass_fields__),
            ("target_record", "mapping_result", "comparisons"),
        )
        self.assertEqual(
            tuple(CollectionFieldComparison.__dataclass_fields__),
            ("mapping", "current_field", "outcome"),
        )

    def test_import_boundary_has_no_forbidden_dependencies(self) -> None:
        module = importlib.import_module(_MODULE)
        tree = ast.parse(inspect.getsource(module))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        forbidden = (
            "coin_collection",
            "repository",
            "persistence",
            "desktop",
            "gui",
            "tkinter",
            "workflow_ocr",
            "pathlib",
            "os",
            "requests",
            "urllib",
            "uuid",
            "datetime",
        )
        for fragment in forbidden:
            with self.subTest(fragment=fragment):
                self.assertFalse(
                    any(fragment in item.casefold() for item in imported),
                    imported,
                )

    def test_module_has_no_proposal_or_mutation_surface(self) -> None:
        module = importlib.import_module(_MODULE)
        source = inspect.getsource(module)
        for fragment in (
            "CollectionFieldChangeProposal",
            "CollectionChangePlan",
            "CollectionChangeOperation",
            "approval_requirement",
            "reason_code",
            "proposed_value",
            "execute(",
            "apply(",
            "save(",
            "open(",
            "getenv",
            "uuid4",
            "datetime.now",
        ):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, source)

    def test_public_api_is_bounded(self) -> None:
        module = importlib.import_module(_MODULE)
        public = {
            name
            for name, value in vars(module).items()
            if (
                not name.startswith("_")
                and getattr(value, "__module__", None) == _MODULE
            )
        }
        self.assertEqual(
            public,
            {
                "CollectionRecordFieldAvailability",
                "CollectionFieldComparisonOutcome",
                "CollectionRecordComparisonError",
                "InvalidCollectionRecordComparisonContextError",
                "MissingCollectionRecordSnapshotFieldError",
                "CollectionRecordFieldSnapshot",
                "CollectionRecordSnapshot",
                "CollectionFieldComparison",
                "CollectionRecordComparisonResult",
                "CollectionRecordComparisonService",
                "compare_mapped_collection_fields",
            },
        )


if __name__ == "__main__":
    unittest.main()
