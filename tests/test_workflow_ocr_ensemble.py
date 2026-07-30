from __future__ import annotations

from dataclasses import FrozenInstanceError
import unicodedata
import unittest

from capture_import.workflow_ocr_ensemble import (
    InvalidOCRProviderEnsembleContextError,
    OCRProviderEnsembleContractError,
    OCRProviderEnsembleFieldFinding,
    OCRProviderEnsembleFieldStatus,
    OCRProviderEnsembleResult,
    OCRProviderEnsembleValueGroup,
    OCRProviderFieldEvidence,
    OCRProviderFieldEvidenceStatus,
    compare_ocr_provider_outcomes,
)
from capture_import.workflow_ocr_provider_contracts import (
    OCRProviderExecutionError,
)
from capture_import.workflow_ocr_provider_execution import (
    OCRProviderExecutionBatch,
    OCRProviderExecutionOutcome,
    OCRProviderExecutionStatus,
    OCRProviderFailureCategory,
    execute_selected_ocr_providers,
)
from tests import test_workflow_ocr_provider_execution as fx


PUBLIC_API = {
    "OCRProviderEnsembleContractError",
    "InvalidOCRProviderEnsembleContextError",
    "OCRProviderFieldEvidenceStatus",
    "OCRProviderEnsembleFieldStatus",
    "OCRProviderFieldEvidence",
    "OCRProviderEnsembleValueGroup",
    "OCRProviderEnsembleFieldFinding",
    "OCRProviderEnsembleResult",
    "compare_ocr_provider_outcomes",
}


def execution_batch(
    *behaviors: object,
    fields: tuple[str, ...] = ("country",),
) -> OCRProviderExecutionBatch:
    provider_ids = tuple(
        f"{chr(ord('a') + index)}-ocr"
        for index in range(len(behaviors))
    )
    capabilities = tuple(
        fx.capabilities(
            provider_id,
            fields=(
                "banknote_prefix",
                "certification_number",
                "country",
                "denomination",
                "mintmark",
                "monarch",
                "series_type",
                "silver_indicator",
                "variety_keyword",
                "year",
            ),
        )
        for provider_id in provider_ids
    )
    providers = tuple(
        fx.FakeProvider(provider_id, behavior)
        for provider_id, behavior in zip(
            provider_ids,
            behaviors,
            strict=True,
        )
    )
    return execute_selected_ocr_providers(
        fx.selection(*capabilities, fields=fields),
        fx.bindings(*zip(capabilities, providers, strict=True)),
        fx.request(),
    )


def successful_batch(
    values: tuple[tuple[str, ...], ...],
    *,
    fields: tuple[str, ...] = ("country",),
    confidences: tuple[float, ...] | None = None,
) -> OCRProviderExecutionBatch:
    reports = []
    for index, provider_values in enumerate(values):
        provider_id = f"{chr(ord('a') + index)}-ocr"
        confidence = (
            confidences[index]
            if confidences is not None
            else 50.0
        )
        candidates = tuple(
            fx.candidate(
                provider_id,
                value=value,
                confidence=confidence,
            )
            for value in provider_values
        )
        reports.append(fx.report(provider_id, *candidates))
    return execution_batch(*reports, fields=fields)


def finding(
    result: OCRProviderEnsembleResult,
    field_name: str,
) -> OCRProviderEnsembleFieldFinding:
    return next(item for item in result.fields if item.field_name == field_name)


class TestEnsemblePublicAPI(unittest.TestCase):
    def test_exact_public_api(self) -> None:
        from capture_import import workflow_ocr_ensemble as module

        self.assertEqual(set(module.__all__), PUBLIC_API)
        self.assertEqual(len(module.__all__), len(PUBLIC_API))

    def test_error_hierarchy(self) -> None:
        self.assertTrue(issubclass(OCRProviderEnsembleContractError, ValueError))
        self.assertTrue(
            issubclass(
                InvalidOCRProviderEnsembleContextError,
                OCRProviderEnsembleContractError,
            )
        )

    def test_no_ranking_calibration_selection_or_serialization_api(self) -> None:
        from capture_import import workflow_ocr_ensemble as module

        forbidden = {
            "selected_provider",
            "winner",
            "score",
            "weight",
            "calibrated_confidence",
            "to_dict",
            "from_dict",
            "serialize",
            "save",
            "load",
        }
        for name in module.__all__:
            self.assertTrue(forbidden.isdisjoint(dir(getattr(module, name))))


class TestFieldUniverse(unittest.TestCase):
    def test_required_field_is_present_when_every_provider_omits_it(self) -> None:
        result = compare_ocr_provider_outcomes(
            successful_batch(((), ()), fields=("country",))
        )

        self.assertEqual(result.field_names, ("country",))
        self.assertEqual(
            result.fields[0].status,
            OCRProviderEnsembleFieldStatus.NO_OBSERVATION,
        )

    def test_nonrequired_observed_fields_join_required_fields_lexically(
        self,
    ) -> None:
        a_report = fx.report(
            "a-ocr",
            fx.candidate("a-ocr", field_name="year", value="1967"),
        )
        b_report = fx.report(
            "b-ocr",
            fx.candidate("b-ocr", field_name="denomination", value="1 dollar"),
        )

        result = compare_ocr_provider_outcomes(
            execution_batch(
                a_report,
                b_report,
                fields=("country",),
            )
        )

        self.assertEqual(
            result.field_names,
            ("country", "denomination", "year"),
        )

    def test_empty_requirement_compares_observed_union(self) -> None:
        source_report = fx.report(
            "a-ocr",
            fx.candidate("a-ocr", field_name="year", value="1967"),
        )

        result = compare_ocr_provider_outcomes(
            execution_batch(source_report, fields=())
        )

        self.assertEqual(result.field_names, ("year",))

    def test_empty_requirement_and_no_observation_yields_empty_result(self) -> None:
        result = compare_ocr_provider_outcomes(
            execution_batch(fx.report("a-ocr"), fields=())
        )

        self.assertEqual(result.fields, ())


class TestSingleProviderSemantics(unittest.TestCase):
    def test_one_observed_value_is_single_source_never_consensus(self) -> None:
        source_candidate = fx.candidate("a-ocr", value="Canada")
        batch = execution_batch(
            fx.report("a-ocr", source_candidate)
        )

        result = compare_ocr_provider_outcomes(batch)
        field = result.fields[0]

        self.assertIs(result.batch, batch)
        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.SINGLE_SOURCE,
        )
        self.assertIsNone(field.consensus_value)
        self.assertIs(field.evidence[0].candidates[0], source_candidate)

    def test_missing_field_is_no_observation(self) -> None:
        field = compare_ocr_provider_outcomes(
            successful_batch(((),))
        ).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.NO_OBSERVATION,
        )
        self.assertEqual(
            field.evidence[0].status,
            OCRProviderFieldEvidenceStatus.MISSING,
        )

    def test_provider_failure_is_all_providers_failed(self) -> None:
        batch = execution_batch(
            OCRProviderExecutionError("a-ocr", "ENGINE_FAILED")
        )

        field = compare_ocr_provider_outcomes(batch).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.ALL_PROVIDERS_FAILED,
        )
        self.assertEqual(
            field.evidence[0].status,
            OCRProviderFieldEvidenceStatus.PROVIDER_FAILED,
        )
        self.assertEqual(
            field.evidence[0].failure_category,
            OCRProviderFailureCategory.EXECUTION,
        )
        self.assertEqual(
            field.evidence[0].diagnostic_code,
            "ENGINE_FAILED",
        )

    def test_one_provider_multiple_values_is_conflict(self) -> None:
        first = fx.candidate("a-ocr", value="Canada")
        second = fx.candidate("a-ocr", value="CANADA")
        field = compare_ocr_provider_outcomes(
            execution_batch(fx.report("a-ocr", first, second))
        ).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.CONFLICT,
        )
        self.assertEqual(
            tuple(group.value for group in field.value_groups),
            ("CANADA", "Canada"),
        )
        self.assertIsNone(field.consensus_value)


class TestTwoProviderSemantics(unittest.TestCase):
    def test_exact_agreement_is_consensus(self) -> None:
        result = compare_ocr_provider_outcomes(
            successful_batch((("Canada",), ("Canada",)))
        )
        field = result.fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.CONSENSUS,
        )
        self.assertEqual(field.consensus_value, "Canada")
        self.assertEqual(len(field.value_groups), 1)
        self.assertEqual(
            tuple(
                provider.provider_id
                for provider in field.value_groups[0].providers
            ),
            ("a-ocr", "b-ocr"),
        )

    def test_one_observes_and_one_omits_is_single_source(self) -> None:
        field = compare_ocr_provider_outcomes(
            successful_batch((("Canada",), ()))
        ).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.SINGLE_SOURCE,
        )
        self.assertEqual(
            tuple(item.status for item in field.evidence),
            (
                OCRProviderFieldEvidenceStatus.OBSERVED,
                OCRProviderFieldEvidenceStatus.MISSING,
            ),
        )

    def test_both_omit_is_no_observation(self) -> None:
        field = compare_ocr_provider_outcomes(
            successful_batch(((), ()))
        ).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.NO_OBSERVATION,
        )

    def test_exact_different_values_are_conflict_without_winner(self) -> None:
        field = compare_ocr_provider_outcomes(
            successful_batch((("Canada",), ("CANADA",)))
        ).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.CONFLICT,
        )
        self.assertIsNone(field.consensus_value)
        self.assertEqual(
            tuple(group.value for group in field.value_groups),
            ("Canada", "CANADA"),
        )

    def test_one_success_and_one_failure_is_single_source(self) -> None:
        batch = execution_batch(
            fx.report(
                "a-ocr",
                fx.candidate("a-ocr", value="Canada"),
            ),
            OCRProviderExecutionError("b-ocr", "ENGINE_FAILED"),
        )

        field = compare_ocr_provider_outcomes(batch).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.SINGLE_SOURCE,
        )
        self.assertEqual(
            field.evidence[1].status,
            OCRProviderFieldEvidenceStatus.PROVIDER_FAILED,
        )

    def test_both_fail_is_all_providers_failed(self) -> None:
        field = compare_ocr_provider_outcomes(
            execution_batch(
                OCRProviderExecutionError("a-ocr", "A_FAILED"),
                OCRProviderExecutionError("b-ocr", "B_FAILED"),
            )
        ).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.ALL_PROVIDERS_FAILED,
        )


class TestThreeProviderSemantics(unittest.TestCase):
    def test_all_agree_is_consensus(self) -> None:
        field = compare_ocr_provider_outcomes(
            successful_batch(
                (("Canada",), ("Canada",), ("Canada",))
            )
        ).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.CONSENSUS,
        )

    def test_two_agree_one_differs_remains_conflict(self) -> None:
        field = compare_ocr_provider_outcomes(
            successful_batch(
                (("Canada",), ("Canada",), ("CANADA",))
            )
        ).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.CONFLICT,
        )
        self.assertIsNone(field.consensus_value)
        self.assertEqual(
            tuple(len(group.providers) for group in field.value_groups),
            (2, 1),
        )

    def test_two_agree_one_fails_is_consensus(self) -> None:
        batch = execution_batch(
            fx.report("a-ocr", fx.candidate("a-ocr", value="Canada")),
            fx.report("b-ocr", fx.candidate("b-ocr", value="Canada")),
            OCRProviderExecutionError("c-ocr", "ENGINE_FAILED"),
        )

        field = compare_ocr_provider_outcomes(batch).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.CONSENSUS,
        )
        self.assertEqual(field.consensus_value, "Canada")

    def test_two_agree_one_omits_is_consensus(self) -> None:
        field = compare_ocr_provider_outcomes(
            successful_batch(
                (("Canada",), ("Canada",), ())
            )
        ).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.CONSENSUS,
        )

    def test_one_observes_one_missing_one_failed_is_single_source(self) -> None:
        batch = execution_batch(
            fx.report("a-ocr", fx.candidate("a-ocr", value="Canada")),
            fx.report("b-ocr"),
            OCRProviderExecutionError("c-ocr", "ENGINE_FAILED"),
        )

        field = compare_ocr_provider_outcomes(batch).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.SINGLE_SOURCE,
        )

    def test_three_distinct_values_are_conflict_in_provider_order(self) -> None:
        field = compare_ocr_provider_outcomes(
            successful_batch(
                (("Zulu",), ("Alpha",), ("Middle",))
            )
        ).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.CONFLICT,
        )
        self.assertEqual(
            tuple(group.value for group in field.value_groups),
            ("Zulu", "Alpha", "Middle"),
        )

    def test_all_omit_and_all_fail_are_distinct(self) -> None:
        omitted = compare_ocr_provider_outcomes(
            successful_batch(((), (), ()))
        ).fields[0]
        failed = compare_ocr_provider_outcomes(
            execution_batch(
                OCRProviderExecutionError("a-ocr", "A_FAILED"),
                OCRProviderExecutionError("b-ocr", "B_FAILED"),
                OCRProviderExecutionError("c-ocr", "C_FAILED"),
            )
        ).fields[0]

        self.assertEqual(
            omitted.status,
            OCRProviderEnsembleFieldStatus.NO_OBSERVATION,
        )
        self.assertEqual(
            failed.status,
            OCRProviderEnsembleFieldStatus.ALL_PROVIDERS_FAILED,
        )


class TestExactComparisonAndConfidence(unittest.TestCase):
    def test_exact_text_differences_are_conflicts(self) -> None:
        pairs = (
            ("Canada", "CANADA"),
            ("A", "A "),
            ("10", "10.00"),
            ("1920", "192O"),
            ("Cafe!", "Cafe?"),
        )
        for first, second in pairs:
            with self.subTest(first=first, second=second):
                field = compare_ocr_provider_outcomes(
                    successful_batch(((first,), (second,)))
                ).fields[0]
                self.assertEqual(
                    field.status,
                    OCRProviderEnsembleFieldStatus.CONFLICT,
                )

    def test_non_nfc_value_is_rejected_not_normalized(self) -> None:
        valid = unicodedata.normalize("NFC", "\u00e9")
        invalid = unicodedata.normalize("NFD", "\u00e9")
        batch = successful_batch(((valid,), (invalid,)))

        field = compare_ocr_provider_outcomes(batch).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.SINGLE_SOURCE,
        )
        self.assertEqual(
            field.evidence[1].status,
            OCRProviderFieldEvidenceStatus.PROVIDER_FAILED,
        )
        self.assertEqual(
            field.evidence[1].failure_category,
            OCRProviderFailureCategory.OUTPUT,
        )

    def test_confidence_does_not_change_consensus_or_candidate_identity(
        self,
    ) -> None:
        batch = successful_batch(
            (("Canada",), ("Canada",)),
            confidences=(1.0, 99.0),
        )
        original_candidates = tuple(
            outcome.report.candidates[0]
            for outcome in batch.outcomes
        )

        field = compare_ocr_provider_outcomes(batch).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.CONSENSUS,
        )
        self.assertEqual(
            tuple(
                candidate.confidence_score
                for candidate in field.value_groups[0].candidates
            ),
            (1.0, 99.0),
        )
        self.assertTrue(
            all(
                actual is expected
                for actual, expected in zip(
                    field.value_groups[0].candidates,
                    original_candidates,
                    strict=True,
                )
            )
        )

    def test_low_confidence_agreement_remains_consensus(self) -> None:
        field = compare_ocr_provider_outcomes(
            successful_batch(
                (("Canada",), ("Canada",)),
                confidences=(1.0, 2.0),
            )
        ).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.CONSENSUS,
        )

    def test_high_confidence_minority_never_wins(self) -> None:
        field = compare_ocr_provider_outcomes(
            successful_batch(
                (("Canada",), ("Canada",), ("CANADA",)),
                confidences=(10.0, 10.0, 100.0),
            )
        ).fields[0]

        self.assertEqual(
            field.status,
            OCRProviderEnsembleFieldStatus.CONFLICT,
        )
        self.assertIsNone(field.consensus_value)


class TestEvidenceAndValueGroupContracts(unittest.TestCase):
    def setUp(self) -> None:
        self.cap = fx.capabilities("a-ocr")
        self.source_candidate = fx.candidate("a-ocr")

    def test_observed_missing_and_failed_pairings_are_strict(self) -> None:
        valid = (
            OCRProviderFieldEvidence(
                self.cap,
                OCRProviderFieldEvidenceStatus.OBSERVED,
                (self.source_candidate,),
                None,
                None,
            ),
            OCRProviderFieldEvidence(
                self.cap,
                OCRProviderFieldEvidenceStatus.MISSING,
                (),
                None,
                None,
            ),
            OCRProviderFieldEvidence(
                self.cap,
                OCRProviderFieldEvidenceStatus.PROVIDER_FAILED,
                (),
                OCRProviderFailureCategory.EXECUTION,
                "ENGINE_FAILED",
            ),
        )
        self.assertEqual(
            tuple(item.status for item in valid),
            tuple(OCRProviderFieldEvidenceStatus),
        )
        invalid = (
            (
                OCRProviderFieldEvidenceStatus.OBSERVED,
                (),
                None,
                None,
            ),
            (
                OCRProviderFieldEvidenceStatus.MISSING,
                (self.source_candidate,),
                None,
                None,
            ),
            (
                OCRProviderFieldEvidenceStatus.PROVIDER_FAILED,
                (),
                None,
                None,
            ),
        )
        for status, candidates, category, code in invalid:
            with self.subTest(status=status):
                with self.assertRaises(
                    InvalidOCRProviderEnsembleContextError
                ):
                    OCRProviderFieldEvidence(
                        self.cap,
                        status,
                        candidates,
                        category,
                        code,
                    )

    def test_evidence_rejects_foreign_candidate_provider(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderEnsembleContextError,
            "does not match",
        ):
            OCRProviderFieldEvidence(
                self.cap,
                OCRProviderFieldEvidenceStatus.OBSERVED,
                (fx.candidate("b-ocr"),),
                None,
                None,
            )

    def test_evidence_wraps_malformed_nested_candidate(self) -> None:
        malformed = object.__new__(
            __import__(
                "capture_import.workflow_ocr_models",
                fromlist=["OCRFieldCandidate"],
            ).OCRFieldCandidate
        )

        with self.assertRaises(InvalidOCRProviderEnsembleContextError):
            OCRProviderFieldEvidence(
                self.cap,
                OCRProviderFieldEvidenceStatus.OBSERVED,
                (malformed,),
                None,
                None,
            )

    def test_value_group_requires_exact_provider_candidate_alignment(self) -> None:
        valid = OCRProviderEnsembleValueGroup(
            "Canada",
            (self.cap,),
            (self.source_candidate,),
        )
        self.assertIs(valid.providers[0], self.cap)
        self.assertIs(valid.candidates[0], self.source_candidate)

        for providers, candidates in (
            ((), ()),
            ((self.cap,), ()),
            ((self.cap, self.cap), (self.source_candidate, self.source_candidate)),
            ((self.cap,), (fx.candidate("a-ocr", value="CANADA"),)),
        ):
            with self.subTest(providers=providers, candidates=candidates):
                with self.assertRaises(
                    InvalidOCRProviderEnsembleContextError
                ):
                    OCRProviderEnsembleValueGroup(
                        "Canada",
                        providers,
                        candidates,
                    )

    def test_evidence_and_groups_are_frozen_and_slotted(self) -> None:
        evidence = OCRProviderFieldEvidence(
            self.cap,
            OCRProviderFieldEvidenceStatus.OBSERVED,
            (self.source_candidate,),
            None,
            None,
        )
        group = OCRProviderEnsembleValueGroup(
            "Canada",
            (self.cap,),
            (self.source_candidate,),
        )
        with self.assertRaises(FrozenInstanceError):
            evidence.candidates = ()  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            group.value = "CANADA"  # type: ignore[misc]
        self.assertFalse(hasattr(evidence, "__dict__"))
        self.assertFalse(hasattr(group, "__dict__"))


class TestFindingAndResultReconstruction(unittest.TestCase):
    def test_finding_rejects_wrong_status_consensus_and_groups(self) -> None:
        valid = compare_ocr_provider_outcomes(
            successful_batch((("Canada",), ("Canada",)))
        ).fields[0]
        invalid_values = (
            dict(status=OCRProviderEnsembleFieldStatus.CONFLICT),
            dict(consensus_value=None),
            dict(value_groups=()),
        )
        for changes in invalid_values:
            values = {
                "field_name": valid.field_name,
                "status": valid.status,
                "evidence": valid.evidence,
                "value_groups": valid.value_groups,
                "consensus_value": valid.consensus_value,
            }
            values.update(changes)
            with self.subTest(changes=changes):
                with self.assertRaises(
                    InvalidOCRProviderEnsembleContextError
                ):
                    OCRProviderEnsembleFieldFinding(**values)

    def test_finding_rejects_wrong_field_and_evidence_order(self) -> None:
        valid = compare_ocr_provider_outcomes(
            successful_batch((("Canada",), ("Canada",)))
        ).fields[0]
        with self.assertRaises(InvalidOCRProviderEnsembleContextError):
            OCRProviderEnsembleFieldFinding(
                "grade",
                valid.status,
                valid.evidence,
                valid.value_groups,
                valid.consensus_value,
            )
        with self.assertRaises(InvalidOCRProviderEnsembleContextError):
            OCRProviderEnsembleFieldFinding(
                valid.field_name,
                valid.status,
                tuple(reversed(valid.evidence)),
                valid.value_groups,
                valid.consensus_value,
            )

    def test_result_rejects_missing_reordered_and_foreign_findings(self) -> None:
        a_report = fx.report(
            "a-ocr",
            fx.candidate("a-ocr", field_name="country", value="Canada"),
            fx.candidate("a-ocr", field_name="year", value="1967"),
        )
        batch = execution_batch(a_report, fields=("country",))
        valid = compare_ocr_provider_outcomes(batch)
        self.assertEqual(valid.field_names, ("country", "year"))

        for fields in (
            (),
            valid.fields[:1],
            tuple(reversed(valid.fields)),
            (valid.fields[0], valid.fields[0]),
        ):
            with self.subTest(fields=fields):
                with self.assertRaises(
                    InvalidOCRProviderEnsembleContextError
                ):
                    OCRProviderEnsembleResult(batch, fields)

    def test_result_rejects_equal_but_distinct_candidate_identity(self) -> None:
        batch = successful_batch((("Canada",),))
        valid = compare_ocr_provider_outcomes(batch)
        source = valid.fields[0]
        copied_candidate = fx.candidate("a-ocr", value="Canada")
        copied_evidence = OCRProviderFieldEvidence(
            source.evidence[0].provider,
            OCRProviderFieldEvidenceStatus.OBSERVED,
            (copied_candidate,),
            None,
            None,
        )
        copied_group = OCRProviderEnsembleValueGroup(
            "Canada",
            (source.evidence[0].provider,),
            (copied_candidate,),
        )
        forged = OCRProviderEnsembleFieldFinding(
            "country",
            OCRProviderEnsembleFieldStatus.SINGLE_SOURCE,
            (copied_evidence,),
            (copied_group,),
            None,
        )

        with self.assertRaisesRegex(
            InvalidOCRProviderEnsembleContextError,
            "does not match",
        ):
            OCRProviderEnsembleResult(batch, (forged,))

    def test_result_is_frozen_slotted_and_exact_batch_identity(self) -> None:
        batch = successful_batch((("Canada",),))
        result = compare_ocr_provider_outcomes(batch)

        self.assertIs(result.batch, batch)
        with self.assertRaises(FrozenInstanceError):
            result.fields = ()  # type: ignore[misc]
        self.assertFalse(hasattr(result, "__dict__"))

    def test_wrong_batch_type_fails_with_typed_error(self) -> None:
        with self.assertRaises(InvalidOCRProviderEnsembleContextError):
            compare_ocr_provider_outcomes(object())  # type: ignore[arg-type]


class TestEnsembleSummaryProperties(unittest.TestCase):
    def test_summary_properties_are_derived_without_batch_status(self) -> None:
        a_report = fx.report(
            "a-ocr",
            fx.candidate("a-ocr", field_name="country", value="Canada"),
            fx.candidate("a-ocr", field_name="year", value="1967"),
        )
        b_report = fx.report(
            "b-ocr",
            fx.candidate("b-ocr", field_name="country", value="Canada"),
            fx.candidate("b-ocr", field_name="year", value="1968"),
        )
        result = compare_ocr_provider_outcomes(
            execution_batch(
                a_report,
                b_report,
                fields=("country", "denomination", "year"),
            )
        )

        self.assertEqual(
            tuple(item.field_name for item in result.consensus_fields),
            ("country",),
        )
        self.assertEqual(
            tuple(item.field_name for item in result.conflict_fields),
            ("year",),
        )
        self.assertEqual(result.single_source_fields, ())
        self.assertEqual(result.unavailable_fields, ())
        self.assertFalse(hasattr(result, "status"))
        self.assertEqual(
            finding(result, "denomination").status,
            OCRProviderEnsembleFieldStatus.NO_OBSERVATION,
        )


if __name__ == "__main__":
    unittest.main()
