"""Tests for READY confirmed-observation collection-field mapping."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import importlib
import inspect
from pathlib import Path
from types import MappingProxyType
import unittest
from unittest.mock import patch

from tests.frozen_dataclass_compat import (
    assert_frozen_slotted_assignment_rejected,
)

from coin_collection import CoinItem
from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationProvenance,
    ConfirmedObservationSet,
    ConfirmedObservationSource,
)
from capture_import.workflow_confirmed_observation_readiness import (
    ConfirmedObservationReadinessResult,
    ConfirmedObservationReadinessStatus,
    assess_confirmed_observation_readiness,
)
import collection_management.workflow_confirmed_collection_field_mapper as mapper_module
from collection_management.workflow_confirmed_collection_field_mapper import (
    AmbiguousConfirmedCollectionFieldError,
    CollectionTargetField,
    ConfirmedCollectionFieldMapper,
    ConfirmedCollectionFieldMapping,
    ConfirmedCollectionFieldMappingError,
    ConfirmedCollectionFieldMappingResult,
    DuplicateCollectionTargetFieldError,
    InvalidConfirmedCollectionMappingContextError,
    UnsupportedConfirmedCollectionFieldError,
    map_ready_confirmed_observations,
)


_MODULE = (
    "collection_management.workflow_confirmed_collection_field_mapper"
)
_VALUES = {
    "year": "1967",
    "denomination": "25 cents",
    "country": "Canada",
    "monarch": "Elizabeth II",
    "mintmark": "H",
    "series_type": "Type II",
    "banknote_prefix": "AB12345",
    "certification_number": "PCGS12345",
    "silver_indicator": "yes",
    "variety_keyword": "8 over 9",
}


def _provenance(
    source_value: str,
) -> tuple[ConfirmedObservationProvenance, ...]:
    return (
        ConfirmedObservationProvenance(
            provider_id="test-ocr",
            image_role="front",
            artifact_key="crop-front",
            source_value=source_value,
            confidence_score=93.0,
            evidence=("visible source",),
        ),
    )


def _observation(
    field_name: str = "country",
    value: str | None = None,
    *,
    canonical_value: str | None = None,
    source_coin_id: str = "source-coin-1",
    reviewer_id: str = "collector-1",
) -> ConfirmedFieldObservation:
    submitted = _VALUES.get(field_name, "value") if value is None else value
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id=source_coin_id,
        field_name=field_name,
        submitted_value=submitted,
        canonical_value=canonical_value,
        reviewer_id=reviewer_id,
        provenance=_provenance(submitted),
        source_type=ConfirmedObservationSource.OCR_REVIEW,
        rationale="Confirmed by collector.",
    )


def _set(
    *observations: ConfirmedFieldObservation,
    review_session_id: str | None = "review-session-1",
    source_fingerprint: str | None = "opaque-source-fingerprint",
) -> ConfirmedObservationSet:
    selected = observations or (_observation(),)
    return ConfirmedObservationSet(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id=selected[0].source_coin_id,
        reviewer_id=selected[0].reviewer_id,
        observations=tuple(
            sorted(selected, key=lambda item: item.field_name)
        ),
        review_session_id=review_session_id,
        source_fingerprint=source_fingerprint,
    )


def _ready(
    *observations: ConfirmedFieldObservation,
) -> ConfirmedObservationReadinessResult:
    return assess_confirmed_observation_readiness(_set(*observations))


class MappingTableTests(unittest.TestCase):
    def test_target_vocabulary_is_exact_and_bounded(self) -> None:
        self.assertEqual(
            tuple(item.value for item in CollectionTargetField),
            ("country", "denomination", "year"),
        )

    def test_supported_mapping_table_is_exact_and_immutable(self) -> None:
        table = mapper_module._SUPPORTED_FIELD_MAPPINGS
        self.assertIsInstance(table, MappingProxyType)
        self.assertEqual(
            dict(table),
            {
                "country": CollectionTargetField.COUNTRY,
                "denomination": CollectionTargetField.DENOMINATION,
                "year": CollectionTargetField.YEAR,
            },
        )
        with self.assertRaises(TypeError):
            table["future"] = CollectionTargetField.YEAR

    def test_every_target_exists_on_active_coin_item(self) -> None:
        active_fields = frozenset(CoinItem.__dataclass_fields__)
        self.assertTrue(
            {
                target.value
                for target in mapper_module._SUPPORTED_FIELD_MAPPINGS.values()
            }.issubset(active_fields)
        )

    def test_no_record_kind_is_invented(self) -> None:
        module = importlib.import_module(_MODULE)
        self.assertFalse(hasattr(module, "CollectionRecordKind"))
        self.assertNotIn(
            "record_kind",
            ConfirmedCollectionFieldMappingResult.__dataclass_fields__,
        )

    def test_ambiguous_field_set_is_explicit_and_immutable(self) -> None:
        self.assertIsInstance(mapper_module._AMBIGUOUS_FIELDS, frozenset)
        self.assertEqual(
            mapper_module._AMBIGUOUS_FIELDS,
            frozenset({"certification_number", "series_type"}),
        )


class ReadinessBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = ConfirmedCollectionFieldMapper()

    def test_real_ready_result_is_accepted(self) -> None:
        readiness = _ready(_observation("country"))

        result = self.mapper.map(readiness)

        self.assertEqual(len(result.mappings), 1)
        self.assertEqual(result.mappings[0].mapped_value, "Canada")

    def test_raw_confirmed_set_is_rejected_by_api_shape(self) -> None:
        with self.assertRaisesRegex(TypeError, "readiness"):
            self.mapper.map(_set(_observation("country")))

    def test_arbitrary_ready_flag_object_is_rejected(self) -> None:
        fake = type("FakeReady", (), {"is_ready": True})()
        with self.assertRaisesRegex(TypeError, "readiness"):
            self.mapper.map(fake)

    def test_non_enum_ready_status_is_rejected(self) -> None:
        readiness = replace(_ready(), status="READY")
        with self.assertRaises(
            InvalidConfirmedCollectionMappingContextError
        ):
            self.mapper.map(readiness)

    def test_mismatched_readiness_source_id_is_rejected(self) -> None:
        readiness = replace(_ready(), source_coin_id="other-source")
        with self.assertRaisesRegex(
            InvalidConfirmedCollectionMappingContextError,
            "source_coin_id",
        ):
            self.mapper.map(readiness)

    def test_malformed_readiness_set_is_rejected(self) -> None:
        readiness = replace(
            _ready(),
            canonicalized_observation_set=object(),
        )
        with self.assertRaisesRegex(
            InvalidConfirmedCollectionMappingContextError,
            "ConfirmedObservationSet",
        ):
            self.mapper.map(readiness)

    def test_mapper_does_not_reinvoke_readiness(self) -> None:
        source = inspect.getsource(ConfirmedCollectionFieldMapper.map)
        self.assertNotIn("assess_confirmed_observation_readiness", source)
        self.assertNotIn("require_confirmed_observation_readiness", source)

    def test_readiness_and_source_set_remain_unchanged(self) -> None:
        readiness = _ready(_observation("country", "  Canada  "))
        before = readiness.to_dict()

        self.mapper.map(readiness)

        self.assertEqual(readiness.to_dict(), before)
        self.assertEqual(
            readiness.canonicalized_observation_set.observations[
                0
            ].submitted_value,
            "  Canada  ",
        )


class BasicMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = ConfirmedCollectionFieldMapper()

    def test_one_field_maps_to_exact_active_target(self) -> None:
        source = _observation("year", "1967")
        readiness = _ready(source)
        mapping = self.mapper.map(readiness).mappings[0]

        self.assertIs(mapping.target_field, CollectionTargetField.YEAR)
        self.assertEqual(mapping.mapped_value, "1967")
        self.assertIs(
            mapping.source_observation,
            readiness.canonicalized_observation_set.observations[0],
        )

    def test_all_safe_fields_map_in_target_order(self) -> None:
        readiness = _ready(
            _observation("year"),
            _observation("country"),
            _observation("denomination"),
        )

        result = self.mapper.map(readiness)

        self.assertEqual(
            tuple(item.target_field.value for item in result.mappings),
            ("country", "denomination", "year"),
        )
        self.assertEqual(
            tuple(item.mapped_value for item in result.mappings),
            ("Canada", "25 cents", "1967"),
        )

    def test_full_source_observation_is_retained(self) -> None:
        source = _observation("country")
        readiness = _ready(source)
        mapping = self.mapper.map(readiness).mappings[0]

        self.assertIs(
            mapping.source_observation,
            readiness.canonicalized_observation_set.observations[0],
        )
        self.assertEqual(mapping.source_observation.reviewer_id, "collector-1")
        self.assertEqual(mapping.source_observation.provenance, source.provenance)
        self.assertEqual(mapping.source_observation.rationale, source.rationale)
        self.assertIs(
            mapping.source_observation.source_type,
            ConfirmedObservationSource.OCR_REVIEW,
        )

    def test_aggregate_linkage_is_preserved(self) -> None:
        source_set = _set(
            _observation("country"),
            review_session_id="session-exact",
            source_fingerprint="fingerprint/exact",
        )
        readiness = assess_confirmed_observation_readiness(source_set)

        result = self.mapper.map(readiness)

        self.assertEqual(result.source_coin_id, "source-coin-1")
        self.assertEqual(result.reviewer_id, "collector-1")
        self.assertEqual(result.review_session_id, "session-exact")
        self.assertEqual(result.source_fingerprint, "fingerprint/exact")

    def test_optional_linkage_remains_none(self) -> None:
        readiness = assess_confirmed_observation_readiness(
            _set(
                _observation("country"),
                review_session_id=None,
                source_fingerprint=None,
            )
        )

        result = self.mapper.map(readiness)

        self.assertIsNone(result.review_session_id)
        self.assertIsNone(result.source_fingerprint)

    def test_exact_whitespace_and_case_are_preserved(self) -> None:
        source = _observation("country", "  CANADA  ")

        mapping = self.mapper.map(_ready(source)).mappings[0]

        self.assertEqual(mapping.mapped_value, "  CANADA  ")
        self.assertEqual(mapping.source_observation.submitted_value, "  CANADA  ")

    def test_convenience_function_matches_stateless_mapper(self) -> None:
        readiness = _ready(_observation("denomination"))
        self.assertEqual(
            map_ready_confirmed_observations(readiness),
            self.mapper.map(readiness),
        )

    def test_equivalent_inputs_produce_equivalent_outputs(self) -> None:
        first = self.mapper.map(_ready(_observation("country")))
        second = self.mapper.map(_ready(_observation("country")))
        self.assertEqual(first, second)


class EffectiveValueTests(unittest.TestCase):
    def test_mapping_contract_uses_submitted_value_when_canonical_absent(
        self,
    ) -> None:
        source = _observation("country", "CANADA")
        mapping = ConfirmedCollectionFieldMapping(
            source_observation=source,
            target_field=CollectionTargetField.COUNTRY,
            mapped_value="CANADA",
        )

        mapping.validate()

        self.assertEqual(mapping.source_value, "CANADA")

    def test_mapping_contract_uses_canonical_when_present(self) -> None:
        source = _observation(
            "country",
            "CANADA",
            canonical_value="Canada",
        )
        mapping = ConfirmedCollectionFieldMapping(
            source_observation=source,
            target_field=CollectionTargetField.COUNTRY,
            mapped_value="Canada",
        )

        mapping.validate()

        self.assertEqual(mapping.source_value, "Canada")
        self.assertEqual(source.submitted_value, "CANADA")
        self.assertEqual(source.canonical_value, "Canada")

    def test_submitted_value_is_rejected_when_canonical_exists(self) -> None:
        source = _observation(
            "country",
            "CANADA",
            canonical_value="Canada",
        )
        mapping = ConfirmedCollectionFieldMapping(
            source_observation=source,
            target_field=CollectionTargetField.COUNTRY,
            mapped_value="CANADA",
        )

        with self.assertRaisesRegex(ValueError, "canonical value"):
            mapping.validate()

    def test_mapped_value_is_never_coerced(self) -> None:
        source = _observation("year", "1967")
        mapping = ConfirmedCollectionFieldMapping(
            source_observation=source,
            target_field=CollectionTargetField.YEAR,
            mapped_value=1967,
        )

        with self.assertRaisesRegex(TypeError, "string"):
            mapping.validate()

    def test_mapping_contract_rejects_wrong_target(self) -> None:
        source = _observation("country")
        mapping = ConfirmedCollectionFieldMapping(
            source_observation=source,
            target_field=CollectionTargetField.YEAR,
            mapped_value="Canada",
        )

        with self.assertRaisesRegex(ValueError, "exact supported mapping"):
            mapping.validate()

    def test_silver_canonicalization_is_preserved_before_unsupported_error(
        self,
    ) -> None:
        readiness = _ready(_observation("silver_indicator", "YES"))
        canonicalized = readiness.canonicalized_observation_set.observations[0]
        self.assertEqual(canonicalized.canonical_value, "true")

        with self.assertRaises(
            UnsupportedConfirmedCollectionFieldError
        ):
            ConfirmedCollectionFieldMapper().map(readiness)

        self.assertEqual(canonicalized.submitted_value, "YES")
        self.assertEqual(canonicalized.canonical_value, "true")


class UnsupportedAndAmbiguousFieldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = ConfirmedCollectionFieldMapper()

    def test_source_verified_unsupported_fields_fail_explicitly(self) -> None:
        fields = (
            "monarch",
            "mintmark",
            "banknote_prefix",
            "silver_indicator",
            "variety_keyword",
        )
        for field_name in fields:
            with self.subTest(field_name=field_name):
                with self.assertRaises(
                    UnsupportedConfirmedCollectionFieldError
                ) as caught:
                    self.mapper.map(_ready(_observation(field_name)))
                self.assertEqual(caught.exception.field_name, field_name)

    def test_ambiguous_fields_fail_with_required_context(self) -> None:
        for field_name in ("certification_number", "series_type"):
            with self.subTest(field_name=field_name):
                with self.assertRaises(
                    AmbiguousConfirmedCollectionFieldError
                ) as caught:
                    self.mapper.map(_ready(_observation(field_name)))
                self.assertEqual(caught.exception.field_name, field_name)
                self.assertEqual(
                    caught.exception.required_context,
                    "an explicit collection-schema mapping policy",
                )

    def test_arbitrary_future_field_fails_closed(self) -> None:
        observation = _observation("future_field", "future value")
        source = _set(observation)
        source.validate()
        readiness = ConfirmedObservationReadinessResult(
            source_coin_id=source.source_coin_id,
            status=ConfirmedObservationReadinessStatus.READY,
            canonicalized_observation_set=source,
            compatibility_results=(),
        )

        with self.assertRaises(
            UnsupportedConfirmedCollectionFieldError
        ) as caught:
            self.mapper.map(readiness)

        self.assertEqual(caught.exception.field_name, "future_field")

    def test_later_unsupported_field_returns_no_partial_result(self) -> None:
        readiness = _ready(
            _observation("country"),
            _observation("mintmark"),
        )
        captured = None

        with self.assertRaises(
            UnsupportedConfirmedCollectionFieldError
        ):
            captured = self.mapper.map(readiness)

        self.assertIsNone(captured)
        self.assertEqual(
            readiness.canonicalized_observation_set.observations[0].field_name,
            "country",
        )

    def test_error_hierarchy_is_specific(self) -> None:
        for error_type in (
            UnsupportedConfirmedCollectionFieldError,
            AmbiguousConfirmedCollectionFieldError,
            DuplicateCollectionTargetFieldError,
            InvalidConfirmedCollectionMappingContextError,
        ):
            with self.subTest(error_type=error_type.__name__):
                self.assertTrue(
                    issubclass(
                        error_type,
                        ConfirmedCollectionFieldMappingError,
                    )
                )


class DuplicateAndAggregateTests(unittest.TestCase):
    def test_duplicate_target_is_rejected_atomically(self) -> None:
        readiness = _ready(
            _observation("country"),
            _observation("denomination"),
        )
        duplicate_table = MappingProxyType(
            {
                "country": CollectionTargetField.COUNTRY,
                "denomination": CollectionTargetField.COUNTRY,
                "year": CollectionTargetField.YEAR,
            }
        )

        with patch.object(
            mapper_module,
            "_SUPPORTED_FIELD_MAPPINGS",
            duplicate_table,
        ):
            with self.assertRaises(
                DuplicateCollectionTargetFieldError
            ) as caught:
                ConfirmedCollectionFieldMapper().map(readiness)

        self.assertIs(
            caught.exception.target_field,
            CollectionTargetField.COUNTRY,
        )

    def test_result_requires_deterministic_target_order(self) -> None:
        result = ConfirmedCollectionFieldMapper().map(
            _ready(
                _observation("country"),
                _observation("year"),
            )
        )
        reversed_result = replace(
            result,
            mappings=tuple(reversed(result.mappings)),
        )

        with self.assertRaisesRegex(ValueError, "deterministic"):
            reversed_result.validate()

    def test_result_rejects_duplicate_source_field(self) -> None:
        mapping = ConfirmedCollectionFieldMapper().map(_ready()).mappings[0]
        duplicate = replace(
            mapping,
            target_field=CollectionTargetField.YEAR,
        )
        result = ConfirmedCollectionFieldMappingResult(
            source_coin_id="source-coin-1",
            reviewer_id="collector-1",
            mappings=(mapping, duplicate),
        )

        with self.assertRaises(ValueError):
            result.validate()

    def test_result_rejects_mixed_source_coin_or_reviewer(self) -> None:
        mapping = ConfirmedCollectionFieldMapper().map(_ready()).mappings[0]
        for name, value in (
            ("source_coin_id", "other-source"),
            ("reviewer_id", "other-reviewer"),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, name):
                    replace(
                        ConfirmedCollectionFieldMappingResult(
                            source_coin_id="source-coin-1",
                            reviewer_id="collector-1",
                            mappings=(mapping,),
                        ),
                        **{name: value},
                    ).validate()

    def test_result_requires_nonempty_immutable_mappings(self) -> None:
        for mappings, error in (
            ((), ValueError),
            ([], TypeError),
            ((object(),), TypeError),
        ):
            with self.subTest(mappings=mappings):
                with self.assertRaises(error):
                    ConfirmedCollectionFieldMappingResult(
                        source_coin_id="source-coin-1",
                        reviewer_id="collector-1",
                        mappings=mappings,
                    ).validate()


class ImmutabilityAndArchitectureTests(unittest.TestCase):
    def test_dtos_are_frozen_and_slotted(self) -> None:
        result = ConfirmedCollectionFieldMapper().map(_ready())
        values = (result.mappings[0], result)
        for value in values:
            with self.subTest(value=type(value).__name__):
                field_name = next(iter(value.__dataclass_fields__))
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, field_name, object())
                with assert_frozen_slotted_assignment_rejected(self, value):
                    value.unexpected = object()

    def test_mapper_is_stateless(self) -> None:
        mapper = ConfirmedCollectionFieldMapper()
        self.assertEqual(ConfirmedCollectionFieldMapper.__slots__, ())
        self.assertFalse(hasattr(mapper, "__dict__"))

    def test_output_contains_no_change_plan_or_execution_fields(self) -> None:
        mapping_fields = tuple(
            ConfirmedCollectionFieldMapping.__dataclass_fields__
        )
        result_fields = tuple(
            ConfirmedCollectionFieldMappingResult.__dataclass_fields__
        )
        self.assertEqual(
            mapping_fields,
            ("source_observation", "target_field", "mapped_value"),
        )
        self.assertEqual(
            result_fields,
            (
                "source_coin_id",
                "reviewer_id",
                "mappings",
                "review_session_id",
                "source_fingerprint",
            ),
        )
        forbidden = (
            "current_value",
            "operation",
            "approval",
            "reason_code",
            "plan",
            "status",
        )
        self.assertFalse(
            any(
                fragment in field
                for field in mapping_fields + result_fields
                for fragment in forbidden
            )
        )

    def test_serialization_is_deliberately_omitted(self) -> None:
        self.assertFalse(hasattr(ConfirmedCollectionFieldMapping, "to_dict"))
        self.assertFalse(
            hasattr(ConfirmedCollectionFieldMappingResult, "to_dict")
        )

    def test_import_boundary_has_no_forbidden_dependencies(self) -> None:
        module = importlib.import_module(_MODULE)
        tree = ast.parse(inspect.getsource(module))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        forbidden = (
            "coin_collection",
            "workflow_collection_change_plan_models",
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

    def test_module_has_no_mutation_or_operation_selection_surface(self) -> None:
        module = importlib.import_module(_MODULE)
        source = inspect.getsource(module)
        for fragment in (
            "CollectionChangePlan",
            "CollectionFieldChangeProposal",
            "CollectionChangeOperation",
            "current_value",
            "approved_by",
            "approved_at",
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
                and (
                    getattr(value, "__module__", None) == _MODULE
                    or name == "map_ready_confirmed_observations"
                )
            )
        }
        self.assertEqual(
            public,
            {
                "CollectionTargetField",
                "ConfirmedCollectionFieldMappingError",
                "UnsupportedConfirmedCollectionFieldError",
                "AmbiguousConfirmedCollectionFieldError",
                "DuplicateCollectionTargetFieldError",
                "InvalidConfirmedCollectionMappingContextError",
                "ConfirmedCollectionFieldMapping",
                "ConfirmedCollectionFieldMappingResult",
                "ConfirmedCollectionFieldMapper",
                "map_ready_confirmed_observations",
            },
        )


if __name__ == "__main__":
    unittest.main()
