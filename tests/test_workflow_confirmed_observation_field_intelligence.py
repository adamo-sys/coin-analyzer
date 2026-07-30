from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

import capture_import.workflow_confirmed_observation_field_intelligence as module
from capture_import.workflow_confirmed_observation_field_intelligence import (
    ConfirmedObservationFieldIntelligenceAssessment,
    DuplicateFieldIntelligenceFindingError,
    FieldIntelligenceContractError,
    FieldIntelligenceFinding,
    FieldIntelligenceStatus,
    InvalidFieldIntelligenceContextError,
    MisalignedFieldIntelligenceFindingError,
)
from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationProvenance,
    ConfirmedObservationSet,
    ConfirmedObservationSource,
)
from capture_import.workflow_ocr_models import ALLOWED_OCR_FIELDS


PUBLIC_API = [
    "FieldIntelligenceContractError",
    "InvalidFieldIntelligenceContextError",
    "DuplicateFieldIntelligenceFindingError",
    "MisalignedFieldIntelligenceFindingError",
    "FieldIntelligenceStatus",
    "FieldIntelligenceFinding",
    "ConfirmedObservationFieldIntelligenceAssessment",
]
CANONICAL_FIELDS = tuple(sorted(ALLOWED_OCR_FIELDS))
MODULE_PATH = (
    Path(__file__).parents[1]
    / "capture_import"
    / "workflow_confirmed_observation_field_intelligence.py"
)


def _provenance() -> ConfirmedObservationProvenance:
    return ConfirmedObservationProvenance(
        provider_id="provider",
        image_role="front",
        artifact_key="artifact",
        source_value="observed",
        evidence=("evidence",),
    )


def _observation(
    field_name: str,
    *,
    submitted_value: str | None = None,
) -> ConfirmedFieldObservation:
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id="coin-1",
        field_name=field_name,
        submitted_value=submitted_value or f"value-{field_name}",
        canonical_value=None,
        reviewer_id="reviewer-1",
        provenance=(_provenance(),),
        source_type=ConfirmedObservationSource.OCR_REVIEW,
        rationale="reviewed",
    )


def _source(*field_names: str) -> ConfirmedObservationSet:
    selected = field_names or ("country", "year")
    return ConfirmedObservationSet(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id="coin-1",
        reviewer_id="reviewer-1",
        observations=tuple(
            _observation(field_name)
            for field_name in sorted(selected)
        ),
        review_session_id="session-1",
        source_fingerprint="opaque-fingerprint",
    )


def _finding(
    rule_id: str = "coin-year.canada.25c-v1",
    *,
    source_fields: tuple[str, ...] = ("country", "year"),
    status: FieldIntelligenceStatus = FieldIntelligenceStatus.VALID,
    diagnostic_code: str = "MATCHED",
) -> FieldIntelligenceFinding:
    return FieldIntelligenceFinding(
        rule_id=rule_id,
        source_fields=source_fields,
        status=status,
        diagnostic_code=diagnostic_code,
    )


class PublicContractTests(unittest.TestCase):
    def test_exact_public_api(self) -> None:
        self.assertEqual(module.__all__, PUBLIC_API)
        defined_public = {
            name
            for name, value in vars(module).items()
            if not name.startswith("_")
            and getattr(value, "__module__", None) == module.__name__
        }
        self.assertEqual(defined_public, set(PUBLIC_API))

    def test_no_serializer_persistence_policy_or_readiness_api(self) -> None:
        forbidden = {
            "to_dict",
            "from_dict",
            "save",
            "load",
            "serialize",
            "deserialize",
            "evaluate",
            "assess",
            "require_valid",
            "is_ready",
            "schema_version",
        }
        for name in PUBLIC_API:
            self.assertTrue(
                forbidden.isdisjoint(dir(getattr(module, name))),
                name,
            )
        self.assertTrue(forbidden.isdisjoint(module.__all__))

    def test_error_hierarchy_is_small_and_machine_actionable(self) -> None:
        self.assertTrue(issubclass(FieldIntelligenceContractError, ValueError))
        for error_type in (
            InvalidFieldIntelligenceContextError,
            DuplicateFieldIntelligenceFindingError,
            MisalignedFieldIntelligenceFindingError,
        ):
            self.assertTrue(
                issubclass(error_type, FieldIntelligenceContractError)
            )
            self.assertIs(error_type.__base__, FieldIntelligenceContractError)

    def test_status_vocabulary_and_order_are_exact(self) -> None:
        self.assertEqual(
            tuple(FieldIntelligenceStatus),
            (
                FieldIntelligenceStatus.VALID,
                FieldIntelligenceStatus.INVALID,
                FieldIntelligenceStatus.NOT_EVALUATED,
            ),
        )
        self.assertEqual(
            tuple(item.value for item in FieldIntelligenceStatus),
            ("VALID", "INVALID", "NOT_EVALUATED"),
        )


class RuleIdentifierTests(unittest.TestCase):
    def test_shortest_and_maximum_rule_ids(self) -> None:
        for value in ("a", "a" + "0" * 127):
            with self.subTest(value_length=len(value)):
                self.assertEqual(_finding(value).rule_id, value)

    def test_representative_future_rule_ids_are_opaque_and_valid(self) -> None:
        values = (
            "coin-year.canada.25c-v1",
            "denomination-country.canada-v1",
            "monarch-year.elizabeth-ii-canada-v1",
            "mintmark.canada-v1",
            "certification.pcgs-v1",
            "variety.canada-v1",
            "banknote.newfoundland-v1",
        )
        self.assertEqual(
            tuple(_finding(value).rule_id for value in values),
            values,
        )

    def test_malformed_rule_ids_raise_typed_error(self) -> None:
        values = (
            "",
            "A",
            "1rule",
            "rule id",
            "rule/id",
            r"rule\id",
            "rule:id",
            "https://rule",
            "../rule",
            "a" * 129,
            1,
            True,
            None,
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(
                    InvalidFieldIntelligenceContextError
                ):
                    _finding(value)  # type: ignore[arg-type]


class DiagnosticCodeTests(unittest.TestCase):
    def test_shortest_and_maximum_codes(self) -> None:
        for value in ("A", "A" + "0" * 63):
            with self.subTest(value_length=len(value)):
                self.assertEqual(
                    _finding(diagnostic_code=value).diagnostic_code,
                    value,
                )

    def test_every_status_requires_a_valid_code(self) -> None:
        for status, code in (
            (FieldIntelligenceStatus.VALID, "MATCHED"),
            (FieldIntelligenceStatus.INVALID, "YEAR_OUT_OF_RANGE"),
            (
                FieldIntelligenceStatus.NOT_EVALUATED,
                "REQUIRED_CONTEXT_MISSING",
            ),
        ):
            with self.subTest(status=status):
                self.assertEqual(
                    _finding(status=status, diagnostic_code=code).status,
                    status,
                )

    def test_malformed_codes_raise_typed_error(self) -> None:
        values = (
            "",
            "matched",
            "MATCHED CODE",
            "MATCHED-CODE",
            "PATH/CODE",
            r"PATH\CODE",
            "A" * 65,
            1,
            True,
            None,
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(
                    InvalidFieldIntelligenceContextError
                ):
                    _finding(diagnostic_code=value)  # type: ignore[arg-type]


class SourceFieldTests(unittest.TestCase):
    def test_one_multiple_and_all_canonical_fields(self) -> None:
        values = (
            ("country",),
            ("country", "denomination", "year"),
            CANONICAL_FIELDS,
        )
        for value in values:
            with self.subTest(value=value):
                self.assertIs(_finding(source_fields=value).source_fields, value)

    def test_noncanonical_order_is_never_silently_sorted(self) -> None:
        values = (
            ("year", "country"),
            ("country", "year", "denomination"),
            tuple(reversed(CANONICAL_FIELDS)),
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(
                    InvalidFieldIntelligenceContextError
                ):
                    _finding(source_fields=value)

    def test_duplicates_unknowns_empty_and_wrong_collections_fail(self) -> None:
        values = (
            (),
            ("country", "country"),
            ("country", "year", "year"),
            ("grade",),
            ("unknown",),
            ["country"],
            ("country", 1),
            ("country", True),
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(
                    InvalidFieldIntelligenceContextError
                ):
                    _finding(source_fields=value)  # type: ignore[arg-type]


class FindingContractTests(unittest.TestCase):
    def test_all_statuses_are_advisory_stored_outcomes(self) -> None:
        findings = tuple(
            _finding(
                rule_id=f"rule-{index}",
                status=status,
                diagnostic_code=code,
            )
            for index, (status, code) in enumerate(
                (
                    (FieldIntelligenceStatus.VALID, "MATCHED"),
                    (FieldIntelligenceStatus.INVALID, "MISMATCHED"),
                    (
                        FieldIntelligenceStatus.NOT_EVALUATED,
                        "AUTHORITY_COVERAGE_UNKNOWN",
                    ),
                )
            )
        )
        self.assertEqual(
            tuple(finding.status for finding in findings),
            tuple(FieldIntelligenceStatus),
        )

    def test_raw_status_strings_are_rejected(self) -> None:
        for value in ("VALID", "INVALID", "NOT_EVALUATED", None, True):
            with self.subTest(value=value):
                with self.assertRaises(
                    InvalidFieldIntelligenceContextError
                ):
                    _finding(status=value)  # type: ignore[arg-type]

    def test_finding_is_frozen_slotted_and_deterministic(self) -> None:
        first = _finding()
        second = _finding()
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertFalse(hasattr(first, "__dict__"))
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            first.rule_id = "changed"  # type: ignore[misc]

    def test_finding_stores_no_source_values_provenance_or_metadata(self) -> None:
        finding = _finding()
        self.assertEqual(
            finding.__slots__,
            ("rule_id", "source_fields", "status", "diagnostic_code"),
        )
        for name in (
            "source",
            "observation",
            "submitted_value",
            "canonical_value",
            "provenance",
            "message",
            "metadata",
            "timestamp",
            "rule_version",
            "authority_url",
        ):
            self.assertFalse(hasattr(finding, name))

    def test_validate_rejects_object_level_reconstruction_attack(self) -> None:
        malformed = object.__new__(FieldIntelligenceFinding)
        object.__setattr__(malformed, "rule_id", "bad/id")
        object.__setattr__(malformed, "source_fields", ("country",))
        object.__setattr__(
            malformed,
            "status",
            FieldIntelligenceStatus.VALID,
        )
        object.__setattr__(malformed, "diagnostic_code", "MATCHED")
        with self.assertRaises(InvalidFieldIntelligenceContextError):
            malformed.validate()


class AssessmentContractTests(unittest.TestCase):
    def test_empty_findings_means_no_rules_reported_not_valid(self) -> None:
        source = _source()
        assessment = ConfirmedObservationFieldIntelligenceAssessment(
            source=source,
            findings=(),
        )
        self.assertIs(assessment.source, source)
        self.assertEqual(assessment.findings, ())
        self.assertEqual(assessment.evaluated_findings, ())
        self.assertEqual(assessment.valid_findings, ())
        self.assertFalse(assessment.has_invalid_findings)
        self.assertFalse(assessment.has_not_evaluated_findings)
        self.assertFalse(hasattr(assessment, "status"))
        self.assertFalse(hasattr(assessment, "is_valid"))
        self.assertFalse(hasattr(assessment, "is_ready"))

    def test_mixed_findings_preserve_exact_source_and_finding_identities(
        self,
    ) -> None:
        source = _source("country", "denomination", "year")
        valid = _finding("a-rule")
        invalid = _finding(
            "b-rule",
            status=FieldIntelligenceStatus.INVALID,
            diagnostic_code="MISMATCHED",
        )
        not_evaluated = _finding(
            "c-rule",
            source_fields=("denomination",),
            status=FieldIntelligenceStatus.NOT_EVALUATED,
            diagnostic_code="AUTHORITY_COVERAGE_UNKNOWN",
        )
        findings = (valid, invalid, not_evaluated)
        assessment = ConfirmedObservationFieldIntelligenceAssessment(
            source=source,
            findings=findings,
        )
        self.assertIs(assessment.source, source)
        self.assertIs(assessment.findings, findings)
        self.assertIs(assessment.findings[0], valid)
        self.assertIs(assessment.valid_findings[0], valid)
        self.assertIs(assessment.invalid_findings[0], invalid)
        self.assertIs(
            assessment.not_evaluated_findings[0],
            not_evaluated,
        )
        self.assertIs(assessment.evaluated_findings[0], valid)
        self.assertIs(assessment.evaluated_findings[1], invalid)
        self.assertEqual(
            assessment.rule_ids,
            ("a-rule", "b-rule", "c-rule"),
        )
        self.assertTrue(assessment.has_invalid_findings)
        self.assertTrue(assessment.has_not_evaluated_findings)

    def test_equal_distinct_source_is_retained_without_copying(self) -> None:
        first = _source()
        second = _source()
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        assessment = ConfirmedObservationFieldIntelligenceAssessment(
            source=second,
            findings=(_finding(),),
        )
        self.assertIs(assessment.source, second)
        self.assertIsNot(assessment.source, first)
        self.assertIs(
            assessment.source.observations[0],
            second.observations[0],
        )

    def test_multiple_rules_may_reference_same_fields(self) -> None:
        assessment = ConfirmedObservationFieldIntelligenceAssessment(
            source=_source(),
            findings=(_finding("a-rule"), _finding("b-rule")),
        )
        self.assertEqual(
            tuple(item.source_fields for item in assessment.findings),
            (("country", "year"), ("country", "year")),
        )

    def test_findings_must_be_in_lexical_rule_order(self) -> None:
        for findings in (
            (_finding("b-rule"), _finding("a-rule")),
            (
                _finding("a-rule"),
                _finding("c-rule"),
                _finding("b-rule"),
            ),
        ):
            with self.subTest(findings=findings):
                with self.assertRaises(
                    InvalidFieldIntelligenceContextError
                ):
                    ConfirmedObservationFieldIntelligenceAssessment(
                        source=_source(),
                        findings=findings,
                    )

    def test_duplicate_rule_ids_fail_in_adjacent_and_final_positions(
        self,
    ) -> None:
        values = (
            (_finding("a-rule"), _finding("a-rule")),
            (
                _finding("a-rule"),
                _finding("b-rule"),
                _finding("a-rule"),
            ),
        )
        for findings in values:
            with self.subTest(findings=findings):
                with self.assertRaises(
                    DuplicateFieldIntelligenceFindingError
                ):
                    ConfirmedObservationFieldIntelligenceAssessment(
                        source=_source(),
                        findings=findings,
                    )

    def test_reference_to_absent_source_field_fails(self) -> None:
        source = _source("country")
        with self.assertRaises(MisalignedFieldIntelligenceFindingError):
            ConfirmedObservationFieldIntelligenceAssessment(
                source=source,
                findings=(_finding(),),
            )

    def test_wrong_source_findings_and_nested_types_raise_typed_error(
        self,
    ) -> None:
        cases = (
            {"source": object(), "findings": ()},
            {"source": _source(), "findings": []},
            {"source": _source(), "findings": (_finding(), object())},
        )
        for values in cases:
            with self.subTest(values=values):
                with self.assertRaises(
                    InvalidFieldIntelligenceContextError
                ):
                    ConfirmedObservationFieldIntelligenceAssessment(
                        **values  # type: ignore[arg-type]
                    )

    def test_invalid_source_reconstruction_is_wrapped_in_typed_error(
        self,
    ) -> None:
        observation = _observation("country")
        malformed = ConfirmedObservationSet(
            schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
            source_coin_id="coin-1",
            reviewer_id="reviewer-1",
            observations=(observation, observation),
        )
        with self.assertRaises(InvalidFieldIntelligenceContextError):
            ConfirmedObservationFieldIntelligenceAssessment(
                source=malformed,
                findings=(),
            )

    def test_malformed_nested_finding_is_revalidated(self) -> None:
        malformed = object.__new__(FieldIntelligenceFinding)
        object.__setattr__(malformed, "rule_id", "bad/id")
        object.__setattr__(malformed, "source_fields", ("country",))
        object.__setattr__(
            malformed,
            "status",
            FieldIntelligenceStatus.VALID,
        )
        object.__setattr__(malformed, "diagnostic_code", "MATCHED")
        with self.assertRaises(InvalidFieldIntelligenceContextError):
            ConfirmedObservationFieldIntelligenceAssessment(
                source=_source(),
                findings=(malformed,),
            )

    def test_assessment_is_frozen_slotted_and_tuple_backed(self) -> None:
        assessment = ConfirmedObservationFieldIntelligenceAssessment(
            source=_source(),
            findings=(_finding(),),
        )
        self.assertFalse(hasattr(assessment, "__dict__"))
        self.assertIsInstance(assessment.findings, tuple)
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            assessment.findings = ()  # type: ignore[misc]

    def test_source_and_nested_objects_remain_unchanged(self) -> None:
        source = _source()
        finding = _finding()
        before_source = source.to_dict()
        before_finding = (
            finding.rule_id,
            finding.source_fields,
            finding.status,
            finding.diagnostic_code,
        )
        ConfirmedObservationFieldIntelligenceAssessment(
            source=source,
            findings=(finding,),
        )
        self.assertEqual(source.to_dict(), before_source)
        self.assertEqual(
            (
                finding.rule_id,
                finding.source_fields,
                finding.status,
                finding.diagnostic_code,
            ),
            before_finding,
        )


class ErrorAndArchitectureTests(unittest.TestCase):
    def test_contract_error_instances_reject_attribute_mutation(self) -> None:
        for error_type in (
            FieldIntelligenceContractError,
            InvalidFieldIntelligenceContextError,
            DuplicateFieldIntelligenceFindingError,
            MisalignedFieldIntelligenceFindingError,
        ):
            error = error_type("bounded message")
            with self.subTest(error_type=error_type):
                with self.assertRaises(AttributeError):
                    error.args = ("changed",)
                with self.assertRaises(AttributeError):
                    error.context = "changed"  # type: ignore[attr-defined]

    def test_all_validation_failures_use_unit_1a_error_hierarchy(self) -> None:
        operations = (
            lambda: _finding("BAD"),
            lambda: _finding(source_fields=()),
            lambda: _finding(status="VALID"),  # type: ignore[arg-type]
            lambda: _finding(diagnostic_code="bad"),
            lambda: ConfirmedObservationFieldIntelligenceAssessment(
                source=_source("country"),
                findings=(_finding(),),
            ),
            lambda: ConfirmedObservationFieldIntelligenceAssessment(
                source=_source(),
                findings=(_finding("a"), _finding("a")),
            ),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaises(FieldIntelligenceContractError):
                    operation()

    def test_import_boundary_is_exact_and_has_no_forbidden_dependencies(
        self,
    ) -> None:
        source_text = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        direct_imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertEqual(
            imports,
            {
                "__future__",
                "dataclasses",
                "enum",
                "workflow_confirmed_observation_models",
                "workflow_ocr_models",
            },
        )
        self.assertEqual(direct_imports, {"re"})

        forbidden = (
            "readiness",
            "compatibility",
            "canonicalization",
            "mapper",
            "collection_management",
            "mutation",
            "persistence",
            "provider",
            "runtime",
            "desktop",
            "gui",
            "pathlib",
            "filesystem",
            "datetime",
            "uuid",
            "random",
            "logging",
            "canadian_reference_provider",
            "series_definitions",
            "ocr_validation",
        )
        lowered = source_text.casefold()
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(f"import {token}", lowered)
                self.assertNotIn(f"from {token}", lowered)

    def test_contract_has_no_hidden_side_effect_or_durable_surface(
        self,
    ) -> None:
        source_text = MODULE_PATH.read_text(encoding="utf-8").casefold()
        forbidden_calls = (
            "open(",
            "getenv(",
            "environ",
            "datetime.now",
            "uuid",
            "random.",
            "logging.",
            "to_dict",
            "from_dict",
            "schema_version",
            "repository",
            "save(",
            "load(",
        )
        for token in forbidden_calls:
            with self.subTest(token=token):
                self.assertNotIn(token, source_text)


if __name__ == "__main__":
    unittest.main()
