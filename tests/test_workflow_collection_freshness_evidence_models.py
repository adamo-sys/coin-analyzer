"""Tests for immutable collection freshness-evidence contracts."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import importlib
import inspect
import json
import unicodedata
import unittest

from tests.frozen_dataclass_compat import (
    assert_frozen_slotted_assignment_rejected,
)

from collection_management.workflow_collection_change_plan_models import (
    CollectionRecordReference,
)
from collection_management.workflow_collection_freshness_evidence_models import (
    CURRENT_COLLECTION_FRESHNESS_EVIDENCE_SCHEMA_VERSION,
    CollectionFreshnessEvidenceError,
    CollectionFreshnessFieldAvailability,
    CollectionFreshnessFieldEvidence,
    CollectionRecordFreshnessEvidence,
    DuplicateCollectionFreshnessEvidenceFieldError,
    InvalidCollectionFreshnessEvidenceContextError,
    InvalidCollectionFreshnessEvidenceTimestampError,
    UnsupportedCollectionFreshnessEvidenceSchemaVersion,
)


_MODULE = (
    "collection_management.workflow_collection_freshness_evidence_models"
)
_TIME = "2026-07-28T19:00:00Z"


def _record(record_id: str = "coin-001") -> CollectionRecordReference:
    return CollectionRecordReference(record_id=record_id)


def _field(
    target_field: str = "country",
    availability: CollectionFreshnessFieldAvailability = (
        CollectionFreshnessFieldAvailability.PRESENT
    ),
    value: str | None = "Canada",
) -> CollectionFreshnessFieldEvidence:
    return CollectionFreshnessFieldEvidence(
        target_field=target_field,
        availability=availability,
        value=value,
    )


def _evidence(
    *fields: CollectionFreshnessFieldEvidence,
    observed_at: str = _TIME,
) -> CollectionRecordFreshnessEvidence:
    return CollectionRecordFreshnessEvidence(
        schema_version=(
            CURRENT_COLLECTION_FRESHNESS_EVIDENCE_SCHEMA_VERSION
        ),
        target_record=_record(),
        fields=fields or (_field(),),
        observed_at=observed_at,
    )


class SchemaAndPublicAPITests(unittest.TestCase):
    def test_current_schema_version_is_explicit(self) -> None:
        self.assertEqual(
            CURRENT_COLLECTION_FRESHNESS_EVIDENCE_SCHEMA_VERSION,
            "1",
        )
        value = _evidence()
        value.validate()
        self.assertEqual(value.to_dict()["schema_version"], "1")

    def test_unsupported_and_future_versions_are_typed(self) -> None:
        for version in ("0", "2", "999"):
            with self.subTest(version=version):
                value = replace(_evidence(), schema_version=version)
                with self.assertRaises(
                    UnsupportedCollectionFreshnessEvidenceSchemaVersion
                ):
                    value.validate()

    def test_deserialization_does_not_default_schema_version(self) -> None:
        payload = _evidence().to_dict()
        del payload["schema_version"]
        with self.assertRaises(
            InvalidCollectionFreshnessEvidenceContextError
        ):
            CollectionRecordFreshnessEvidence.from_dict(payload)

    def test_schema_version_wrong_type_is_rejected(self) -> None:
        payload = _evidence().to_dict()
        payload["schema_version"] = 1
        with self.assertRaises(TypeError):
            CollectionRecordFreshnessEvidence.from_dict(payload)

    def test_error_hierarchy_is_narrow(self) -> None:
        for error_type in (
            UnsupportedCollectionFreshnessEvidenceSchemaVersion,
            InvalidCollectionFreshnessEvidenceContextError,
            DuplicateCollectionFreshnessEvidenceFieldError,
            InvalidCollectionFreshnessEvidenceTimestampError,
        ):
            with self.subTest(error_type=error_type):
                self.assertTrue(
                    issubclass(
                        error_type,
                        CollectionFreshnessEvidenceError,
                    )
                )

    def test_public_api_is_exact(self) -> None:
        module = importlib.import_module(_MODULE)
        public = {
            name
            for name, value in vars(module).items()
            if (
                not name.startswith("_")
                and (
                    name
                    == "CURRENT_COLLECTION_FRESHNESS_EVIDENCE_SCHEMA_VERSION"
                    or getattr(value, "__module__", None) == _MODULE
                )
            )
        }
        self.assertEqual(
            public,
            {
                "CURRENT_COLLECTION_FRESHNESS_EVIDENCE_SCHEMA_VERSION",
                "CollectionFreshnessEvidenceError",
                "UnsupportedCollectionFreshnessEvidenceSchemaVersion",
                "InvalidCollectionFreshnessEvidenceContextError",
                "DuplicateCollectionFreshnessEvidenceFieldError",
                "InvalidCollectionFreshnessEvidenceTimestampError",
                "CollectionFreshnessFieldAvailability",
                "CollectionFreshnessFieldEvidence",
                "CollectionRecordFreshnessEvidence",
            },
        )


class FieldAvailabilityTests(unittest.TestCase):
    def test_availability_vocabulary_is_exact(self) -> None:
        self.assertEqual(
            tuple(
                item.value for item in CollectionFreshnessFieldAvailability
            ),
            ("PRESENT", "ABSENT", "UNAVAILABLE"),
        )

    def test_present_accepts_nonempty_and_empty_strings(self) -> None:
        for value in ("Canada", ""):
            with self.subTest(value=value):
                field = _field(value=value)
                field.validate()
                self.assertEqual(field.value, value)

    def test_present_rejects_none(self) -> None:
        field = _field(value=None)
        with self.assertRaises(
            InvalidCollectionFreshnessEvidenceContextError
        ):
            field.validate()

    def test_absent_requires_none(self) -> None:
        field = _field(
            availability=CollectionFreshnessFieldAvailability.ABSENT,
            value=None,
        )
        field.validate()
        for value in ("", "Canada"):
            with self.subTest(value=value):
                with self.assertRaises(
                    InvalidCollectionFreshnessEvidenceContextError
                ):
                    replace(field, value=value).validate()

    def test_unavailable_requires_none(self) -> None:
        field = _field(
            availability=CollectionFreshnessFieldAvailability.UNAVAILABLE,
            value=None,
        )
        field.validate()
        for value in ("", "Canada"):
            with self.subTest(value=value):
                with self.assertRaises(
                    InvalidCollectionFreshnessEvidenceContextError
                ):
                    replace(field, value=value).validate()

    def test_availability_type_and_serialized_value_are_strict(self) -> None:
        with self.assertRaises(TypeError):
            replace(_field(), availability="PRESENT").validate()  # type: ignore[arg-type]
        payload = _field().to_dict()
        payload["availability"] = "FRESH"
        with self.assertRaises(
            InvalidCollectionFreshnessEvidenceContextError
        ):
            CollectionFreshnessFieldEvidence.from_dict(payload)

    def test_no_freshness_verdict_vocabulary_exists(self) -> None:
        forbidden = {
            "FRESH",
            "STALE",
            "MATCH",
            "MISMATCH",
            "CHANGED",
            "UNCHANGED",
            "VALID",
            "INVALID",
            "READY",
            "ELIGIBLE",
        }
        self.assertTrue(
            forbidden.isdisjoint(
                item.value for item in CollectionFreshnessFieldAvailability
            )
        )


class PerFieldContractTests(unittest.TestCase):
    def test_exact_target_field_is_preserved(self) -> None:
        field = _field(target_field="custom_collection_field")
        field.validate()
        self.assertEqual(
            field.to_dict()["target_field"],
            "custom_collection_field",
        )

    def test_target_field_uses_exact_plan_token_grammar(self) -> None:
        for target_field in (
            "country",
            "denomination",
            "year",
            "certification_number",
            "multi_word_field",
            "country_",
        ):
            with self.subTest(target_field=target_field):
                _field(target_field=target_field).validate()
        for target_field in (
            "",
            "Country",
            "country name",
            "country-name",
            "_country",
            " country",
            "country ",
            "1country",
            "countré",
            "a" * 129,
        ):
            with self.subTest(target_field=target_field):
                with self.assertRaises(
                    InvalidCollectionFreshnessEvidenceContextError
                ):
                    _field(target_field=target_field).validate()

    def test_target_field_wrong_type_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            _field(target_field=1).validate()  # type: ignore[arg-type]

    def test_field_serialization_shape_is_closed(self) -> None:
        field = _field()
        self.assertEqual(
            set(field.to_dict()),
            {"target_field", "availability", "value"},
        )
        for mutation in ("unknown", "missing"):
            with self.subTest(mutation=mutation):
                payload = field.to_dict()
                if mutation == "unknown":
                    payload["extra"] = True
                else:
                    del payload["value"]
                with self.assertRaises(
                    InvalidCollectionFreshnessEvidenceContextError
                ):
                    CollectionFreshnessFieldEvidence.from_dict(payload)

    def test_field_deserialization_requires_object(self) -> None:
        for value in (None, [], "field"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    CollectionFreshnessFieldEvidence.from_dict(value)  # type: ignore[arg-type]

    def test_field_round_trip_is_exact(self) -> None:
        for field in (
            _field(),
            _field(value=""),
            _field(
                availability=CollectionFreshnessFieldAvailability.ABSENT,
                value=None,
            ),
            _field(
                availability=(
                    CollectionFreshnessFieldAvailability.UNAVAILABLE
                ),
                value=None,
            ),
        ):
            with self.subTest(field=field):
                self.assertEqual(
                    CollectionFreshnessFieldEvidence.from_dict(
                        field.to_dict()
                    ),
                    field,
                )


class RecordEvidenceTests(unittest.TestCase):
    def test_one_field_and_ordered_partial_subset_are_valid(self) -> None:
        one = _evidence(_field("country"))
        many = _evidence(
            _field("country"),
            _field("year", value="1967"),
        )
        one.validate()
        many.validate()
        self.assertEqual(
            tuple(field.target_field for field in many.fields),
            ("country", "year"),
        )

    def test_empty_field_tuple_is_rejected(self) -> None:
        value = replace(_evidence(), fields=())
        with self.assertRaises(
            InvalidCollectionFreshnessEvidenceContextError
        ):
            value.validate()

    def test_excessive_field_count_is_rejected(self) -> None:
        fields = tuple(
            _field(f"field_{index:03d}")
            for index in range(301)
        )
        value = replace(_evidence(), fields=fields)
        with self.assertRaises(
            InvalidCollectionFreshnessEvidenceContextError
        ):
            value.validate()

    def test_target_record_is_exact_and_required(self) -> None:
        target = _record("record:exact/001")
        value = replace(_evidence(), target_record=target)
        value.validate()
        self.assertIs(value.target_record, target)
        self.assertEqual(
            value.to_dict()["target_record"],
            {"record_id": "record:exact/001"},
        )
        with self.assertRaises(TypeError):
            replace(value, target_record="record").validate()  # type: ignore[arg-type]

    def test_omission_is_distinct_from_explicit_unavailable(self) -> None:
        omitted = _evidence(_field("country"))
        unavailable = _evidence(
            _field("country"),
            _field(
                "year",
                availability=(
                    CollectionFreshnessFieldAvailability.UNAVAILABLE
                ),
                value=None,
            ),
        )
        omitted.validate()
        unavailable.validate()
        self.assertNotEqual(omitted, unavailable)
        self.assertNotIn(
            "year",
            {field.target_field for field in omitted.fields},
        )
        self.assertIs(
            unavailable.fields[1].availability,
            CollectionFreshnessFieldAvailability.UNAVAILABLE,
        )

    def test_no_plan_linkage_revision_or_verdict_fields_exist(self) -> None:
        fields = set(
            CollectionRecordFreshnessEvidence.__dataclass_fields__
        )
        self.assertEqual(
            fields,
            {"schema_version", "target_record", "fields", "observed_at"},
        )
        self.assertTrue(
            fields.isdisjoint(
                {
                    "source_coin_id",
                    "review_session_id",
                    "source_fingerprint",
                    "plan_schema_version",
                    "record_revision",
                    "is_fresh",
                    "is_stale",
                    "eligible",
                    "authorized",
                }
            )
        )

    def test_fields_must_be_tuple_of_exact_contracts(self) -> None:
        with self.assertRaises(TypeError):
            replace(_evidence(), fields=[_field()]).validate()  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            replace(_evidence(), fields=(object(),)).validate()  # type: ignore[arg-type]


class TimestampTests(unittest.TestCase):
    def test_whole_and_fractional_utc_timestamps_are_exact(self) -> None:
        timestamps = (
            "2026-07-28T19:00:00Z",
            "2026-07-28T19:00:00.1Z",
            "2026-07-28T19:00:00.123456789Z",
        )
        for timestamp in timestamps:
            with self.subTest(timestamp=timestamp):
                value = _evidence(observed_at=timestamp)
                value.validate()
                self.assertEqual(value.observed_at, timestamp)
                self.assertEqual(
                    value.to_dict()["observed_at"],
                    timestamp,
                )

    def test_invalid_timestamp_forms_are_typed(self) -> None:
        invalid = (
            "2026-02-30T19:00:00Z",
            "2025-02-29T19:00:00Z",
            "2026-13-28T19:00:00Z",
            "2026-07-32T19:00:00Z",
            "2026-07-28T24:00:00Z",
            "2026-07-28T19:60:00Z",
            "2026-07-28T19:00:60Z",
            "2026-07-28T19:00:00",
            "2026-07-28T19:00:00z",
            "2026-07-28T19:00:00+00:00",
            "2026-07-28T19:00:00-04:00",
            "2026-07-28T19:00Z",
            "2026-07-28",
            " 2026-07-28T19:00:00Z",
            "2026-07-28T19:00:00Z ",
            "2026-07-28 T19:00:00Z",
            "",
        )
        for timestamp in invalid:
            with self.subTest(timestamp=timestamp):
                with self.assertRaises(
                    InvalidCollectionFreshnessEvidenceTimestampError
                ):
                    _evidence(observed_at=timestamp).validate()

    def test_timestamp_is_required_and_has_no_default(self) -> None:
        payload = _evidence().to_dict()
        del payload["observed_at"]
        with self.assertRaises(
            InvalidCollectionFreshnessEvidenceContextError
        ):
            CollectionRecordFreshnessEvidence.from_dict(payload)
        with self.assertRaises(TypeError):
            replace(_evidence(), observed_at=None).validate()  # type: ignore[arg-type]


class OrderingAndDuplicateTests(unittest.TestCase):
    def test_reversed_order_is_rejected_without_sorting(self) -> None:
        fields = (
            _field("year", value="1967"),
            _field("country"),
        )
        value = _evidence(*fields)
        before = value.fields
        with self.assertRaises(
            InvalidCollectionFreshnessEvidenceContextError
        ):
            value.validate()
        self.assertIs(value.fields, before)

    def test_adjacent_and_nonadjacent_duplicates_are_typed(self) -> None:
        cases = (
            (
                _field("country"),
                _field("country", value="Canada"),
            ),
            (
                _field("country"),
                _field("year", value="1967"),
                _field("country", value="Canada"),
            ),
        )
        for fields in cases:
            with self.subTest(fields=fields):
                with self.assertRaises(
                    DuplicateCollectionFreshnessEvidenceFieldError
                ) as captured:
                    _evidence(*fields).validate()
                self.assertEqual(
                    captured.exception.target_field,
                    "country",
                )

    def test_serialized_order_is_deterministic(self) -> None:
        value = _evidence(
            _field("country"),
            _field("denomination", value="25 cents"),
            _field("year", value="1967"),
        )
        expected = ["country", "denomination", "year"]
        self.assertEqual(
            [
                field["target_field"]
                for field in value.to_dict()["fields"]
            ],
            expected,
        )

    def test_deserialization_rejects_reversed_and_middle_disorder(
        self,
    ) -> None:
        payload = _evidence(
            _field("country"),
            _field("denomination", value="25 cents"),
            _field("year", value="1967"),
        ).to_dict()
        for fields in (
            list(reversed(payload["fields"])),
            [
                payload["fields"][0],
                payload["fields"][2],
                payload["fields"][1],
            ],
        ):
            with self.subTest(fields=fields):
                changed = dict(payload)
                changed["fields"] = fields
                with self.assertRaises(
                    InvalidCollectionFreshnessEvidenceContextError
                ):
                    CollectionRecordFreshnessEvidence.from_dict(changed)

    def test_deserialization_rejects_duplicate_targets(self) -> None:
        payload = _evidence(
            _field("country"),
            _field("year", value="1967"),
        ).to_dict()
        duplicate = dict(payload["fields"][0])
        duplicate["availability"] = "UNAVAILABLE"
        duplicate["value"] = None
        payload["fields"].append(duplicate)
        with self.assertRaises(
            DuplicateCollectionFreshnessEvidenceFieldError
        ) as captured:
            CollectionRecordFreshnessEvidence.from_dict(payload)
        self.assertEqual(captured.exception.target_field, "country")


class ExactValueTests(unittest.TestCase):
    def test_exact_string_values_are_preserved(self) -> None:
        values = (
            "",
            " Canada ",
            "CaNaDa",
            "25 cents",
            "01967",
            "Montréal",
            "C$ 1.00 / proof-like",
        )
        for exact in values:
            with self.subTest(exact=exact):
                field = _field(value=exact)
                field.validate()
                restored = CollectionFreshnessFieldEvidence.from_dict(
                    field.to_dict()
                )
                self.assertEqual(restored.value, exact)

    def test_values_are_not_unicode_normalized_silently(self) -> None:
        decomposed = unicodedata.normalize("NFD", "Montréal")
        self.assertNotEqual(decomposed, "Montréal")
        with self.assertRaises(
            InvalidCollectionFreshnessEvidenceContextError
        ):
            _field(value=decomposed).validate()

    def test_control_surrogate_and_overlong_values_are_rejected(self) -> None:
        for value in ("line\nbreak", "\ud800", "x" * 4097):
            with self.subTest(value=value[:20]):
                with self.assertRaises(
                    InvalidCollectionFreshnessEvidenceContextError
                ):
                    _field(value=value).validate()


class SerializationAndAtomicityTests(unittest.TestCase):
    def test_record_serialization_shape_is_closed_and_json_safe(self) -> None:
        value = _evidence(
            _field("country"),
            _field(
                "year",
                availability=(
                    CollectionFreshnessFieldAvailability.UNAVAILABLE
                ),
                value=None,
            ),
        )
        payload = value.to_dict()
        self.assertEqual(
            set(payload),
            {"schema_version", "target_record", "fields", "observed_at"},
        )
        self.assertIsInstance(json.dumps(payload), str)

    def test_record_round_trip_is_exact_and_stable(self) -> None:
        value = _evidence(
            _field("country", value=" Canada "),
            _field("denomination", value=""),
            _field(
                "year",
                availability=(
                    CollectionFreshnessFieldAvailability.ABSENT
                ),
                value=None,
            ),
            observed_at="2026-07-28T19:00:00.123Z",
        )
        first = value.to_dict()
        restored = CollectionRecordFreshnessEvidence.from_dict(first)
        second = restored.to_dict()
        self.assertEqual(restored, value)
        self.assertEqual(first, second)

    def test_record_unknown_and_missing_fields_are_rejected(self) -> None:
        for mutation in ("unknown", "missing"):
            with self.subTest(mutation=mutation):
                payload = _evidence().to_dict()
                if mutation == "unknown":
                    payload["record_revision"] = "1"
                else:
                    del payload["fields"]
                with self.assertRaises(
                    InvalidCollectionFreshnessEvidenceContextError
                ):
                    CollectionRecordFreshnessEvidence.from_dict(payload)

    def test_record_and_nested_record_shapes_are_strict(self) -> None:
        for value in (None, [], "record"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    CollectionRecordFreshnessEvidence.from_dict(value)  # type: ignore[arg-type]

        for mutation in ("unknown", "missing"):
            with self.subTest(mutation=mutation):
                payload = _evidence().to_dict()
                if mutation == "unknown":
                    payload["target_record"]["extra"] = True
                else:
                    del payload["target_record"]["record_id"]
                with self.assertRaises((TypeError, ValueError)):
                    CollectionRecordFreshnessEvidence.from_dict(payload)

    def test_serialized_fields_must_be_list(self) -> None:
        payload = _evidence().to_dict()
        payload["fields"] = tuple(payload["fields"])
        with self.assertRaises(TypeError):
            CollectionRecordFreshnessEvidence.from_dict(payload)

    def test_malformed_final_field_is_atomic(self) -> None:
        valid = _field("country")
        invalid = _field(
            "year",
            availability=CollectionFreshnessFieldAvailability.ABSENT,
            value="1967",
        )
        source = (valid, invalid)
        value = replace(_evidence(), fields=source)
        with self.assertRaises(
            InvalidCollectionFreshnessEvidenceContextError
        ):
            value.validate()
        self.assertIs(value.fields, source)
        self.assertEqual(valid.value, "Canada")
        self.assertEqual(invalid.value, "1967")

    def test_deserialization_of_malformed_final_field_is_atomic(self) -> None:
        payload = _evidence(
            _field("country"),
            _field("year", value="1967"),
        ).to_dict()
        payload["fields"][1]["availability"] = "ABSENT"
        with self.assertRaises(
            InvalidCollectionFreshnessEvidenceContextError
        ):
            CollectionRecordFreshnessEvidence.from_dict(payload)

    def test_deserialization_validates_timestamp_before_nested_fields(
        self,
    ) -> None:
        payload = _evidence().to_dict()
        payload["observed_at"] = "2026-07-28T24:00:00Z"
        payload["fields"][0]["availability"] = "FRESH"
        with self.assertRaises(
            InvalidCollectionFreshnessEvidenceTimestampError
        ):
            CollectionRecordFreshnessEvidence.from_dict(payload)


class ImmutabilityAndArchitectureTests(unittest.TestCase):
    def test_contracts_are_frozen_and_slotted(self) -> None:
        field = _field()
        evidence = _evidence(field)
        for value in (field, evidence):
            with self.subTest(value=value):
                self.assertFalse(hasattr(value, "__dict__"))
                with assert_frozen_slotted_assignment_rejected(self, value):
                    value.extra = True  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            field.value = "changed"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            evidence.fields = ()  # type: ignore[misc]
        for value, name, changed in (
            (field, "target_field", "year"),
            (
                field,
                "availability",
                CollectionFreshnessFieldAvailability.ABSENT,
            ),
            (field, "value", "changed"),
            (evidence, "target_record", _record("changed")),
            (evidence, "observed_at", "2026-07-28T20:00:00Z"),
            (evidence, "schema_version", "2"),
        ):
            with self.subTest(value=value, name=name):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, name, changed)

    def test_repeated_construction_and_serialization_are_deterministic(
        self,
    ) -> None:
        first = _evidence(_field())
        second = _evidence(_field())
        self.assertEqual(first, second)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.to_dict(), first.to_dict())

    def test_import_boundary_is_narrow(self) -> None:
        module = importlib.import_module(_MODULE)
        tree = ast.parse(inspect.getsource(module))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        forbidden = (
            "approval",
            "policy",
            "repository",
            "persistence",
            "mutation",
            "execution",
            "desktop",
            "gui",
            "tkinter",
            "workflow_ocr",
            "pathlib",
            "requests",
            "urllib",
            "uuid",
            "random",
        )
        for fragment in forbidden:
            with self.subTest(fragment=fragment):
                self.assertFalse(
                    any(fragment in name.casefold() for name in imported),
                    imported,
                )
        self.assertNotIn("os", imported)

    def test_module_has_no_generated_or_automatic_surface(self) -> None:
        module = importlib.import_module(_MODULE)
        source = inspect.getsource(module)
        for fragment in (
            "datetime.now",
            "datetime.utcnow",
            "uuid4",
            "getenv",
            "open(",
            "save(",
            "execute(",
            "apply(",
            "is_fresh",
            "is_stale",
            "authorized",
            "eligible",
            "record_revision",
        ):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, source)


if __name__ == "__main__":
    unittest.main()
