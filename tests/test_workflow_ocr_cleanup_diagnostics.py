from __future__ import annotations

from dataclasses import FrozenInstanceError
from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image

from capture_import.workflow_ocr_cleanup_diagnostics import (
    InvalidOCRProviderCleanupDiagnosticContextError,
    OCRProviderCleanupDiagnostic,
    OCRProviderCleanupDiagnosticContractError,
    OCRProviderCleanupDiagnosticSeverity,
    OCRProviderExecutionWithCleanup,
)
from capture_import.workflow_ocr_confidence_calibration import (
    OCRConfidenceCalibrationPoint,
    OCRConfidenceCalibrationProfile,
    OCRConfidenceCalibrationRegistry,
    calibrate_ocr_execution_confidence,
)
from capture_import.workflow_ocr_ensemble import (
    OCRProviderEnsembleFieldStatus,
    compare_ocr_provider_outcomes,
)
from capture_import.workflow_ocr_provider_contracts import (
    OCRProviderCleanupError,
)
from capture_import.workflow_ocr_provider_execution import (
    OCRProviderExecutionStatus,
    OCRProviderFailureCategory,
    execute_selected_ocr_providers,
)
from tests import test_workflow_ocr_provider_execution as fx
from legacy_ocr_workflow_provider import LegacyOCRWorkflowProvider
from ocr_experiment import OCRExperiment


PUBLIC_API = {
    "OCRProviderCleanupDiagnosticContractError",
    "InvalidOCRProviderCleanupDiagnosticContextError",
    "OCRProviderCleanupDiagnosticSeverity",
    "OCRProviderCleanupDiagnostic",
    "OCRProviderExecutionWithCleanup",
}


def successful_batch(
    *provider_values: tuple[str, str],
    confidence: float = 50.0,
):
    capabilities = tuple(
        fx.capabilities(provider_id)
        for provider_id, _value in provider_values
    )
    providers = tuple(
        fx.FakeProvider(
            provider_id,
            fx.report(
                provider_id,
                fx.candidate(
                    provider_id,
                    value=value,
                    confidence=confidence,
                ),
            ),
        )
        for provider_id, value in provider_values
    )
    return execute_selected_ocr_providers(
        fx.selection(*capabilities),
        fx.bindings(*zip(capabilities, providers, strict=True)),
        fx.request(),
    )


def warning(batch, index: int = 0, **changes: object):
    values = {
        "provider": batch.outcomes[index].capabilities,
        "severity": OCRProviderCleanupDiagnosticSeverity.WARNING,
        "diagnostic_code": "TEMPORARY_ARTIFACT_RETAINED",
        "artifact_key": batch.request.artifact_key,
    }
    values.update(changes)
    return OCRProviderCleanupDiagnostic(**values)


def jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 12), (100, 100, 100)).save(
        output,
        format="JPEG",
    )
    return output.getvalue()


class DeterministicExperiment(OCRExperiment):
    def __init__(self) -> None:
        super().__init__()
        self.temporary_path = ""

    def run(self, image_path="", raw_text=None, engine="pytesseract"):
        self.temporary_path = image_path
        return super().run(
            image_path="",
            raw_text="CANADA 1967",
            engine=engine,
        )


class TestCleanupPublicAPI(unittest.TestCase):
    def test_exact_public_api(self) -> None:
        from capture_import import workflow_ocr_cleanup_diagnostics as module

        self.assertEqual(set(module.__all__), PUBLIC_API)
        self.assertEqual(len(module.__all__), len(PUBLIC_API))

    def test_error_hierarchy_and_severity_vocabulary(self) -> None:
        self.assertTrue(
            issubclass(OCRProviderCleanupDiagnosticContractError, ValueError)
        )
        self.assertTrue(
            issubclass(
                InvalidOCRProviderCleanupDiagnosticContextError,
                OCRProviderCleanupDiagnosticContractError,
            )
        )
        self.assertEqual(
            tuple(item.value for item in OCRProviderCleanupDiagnosticSeverity),
            ("WARNING", "FAILURE"),
        )

    def test_no_execution_persistence_or_serialization_api(self) -> None:
        from capture_import import workflow_ocr_cleanup_diagnostics as module

        forbidden = {
            "execute_cleanup",
            "retry_cleanup",
            "save",
            "load",
            "to_dict",
            "from_dict",
            "serialize",
            "logger",
        }
        self.assertTrue(forbidden.isdisjoint(module.__all__))


class TestCleanupDiagnosticContract(unittest.TestCase):
    def setUp(self) -> None:
        self.batch = successful_batch(("alpha-ocr", "Canada"))
        self.provider = self.batch.outcomes[0].capabilities

    def test_warning_and_failure_values_are_representable(self) -> None:
        for severity in OCRProviderCleanupDiagnosticSeverity:
            item = OCRProviderCleanupDiagnostic(
                provider=self.provider,
                severity=severity,
                diagnostic_code="CLEANUP_FAILED",
                artifact_key=None,
            )
            self.assertIs(item.provider, self.provider)
            self.assertIs(item.severity, severity)

    def test_raw_severity_and_wrong_provider_are_rejected(self) -> None:
        with self.assertRaises(
            InvalidOCRProviderCleanupDiagnosticContextError
        ):
            OCRProviderCleanupDiagnostic(
                provider=self.provider,
                severity="WARNING",  # type: ignore[arg-type]
                diagnostic_code="CLEANUP_FAILED",
            )
        with self.assertRaises(
            InvalidOCRProviderCleanupDiagnosticContextError
        ):
            OCRProviderCleanupDiagnostic(
                provider=object(),  # type: ignore[arg-type]
                severity=OCRProviderCleanupDiagnosticSeverity.WARNING,
                diagnostic_code="CLEANUP_FAILED",
            )

    def test_diagnostic_code_uses_bounded_unit_1a_grammar(self) -> None:
        for value in ("", "lowercase", "HAS-DASH", "A" * 65, 123):
            with self.subTest(value=value), self.assertRaises(
                InvalidOCRProviderCleanupDiagnosticContextError
            ):
                OCRProviderCleanupDiagnostic(
                    provider=self.provider,
                    severity=OCRProviderCleanupDiagnosticSeverity.WARNING,
                    diagnostic_code=value,  # type: ignore[arg-type]
                )

    def test_artifact_key_is_optional_bounded_and_not_a_path(self) -> None:
        for value in ("", " ", " x", "x ", "a/b", r"a\b", "a" * 256, 1):
            with self.subTest(value=value), self.assertRaises(
                InvalidOCRProviderCleanupDiagnosticContextError
            ):
                OCRProviderCleanupDiagnostic(
                    provider=self.provider,
                    severity=OCRProviderCleanupDiagnosticSeverity.WARNING,
                    diagnostic_code="CLEANUP_FAILED",
                    artifact_key=value,  # type: ignore[arg-type]
                )

    def test_contract_has_no_message_path_exception_or_metadata_field(self) -> None:
        self.assertEqual(
            OCRProviderCleanupDiagnostic.__slots__,
            ("provider", "severity", "diagnostic_code", "artifact_key"),
        )

    def test_diagnostic_is_frozen_and_slotted(self) -> None:
        item = warning(self.batch)
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            item.diagnostic_code = "CHANGED"  # type: ignore[misc]
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            item.extra = object()  # type: ignore[attr-defined]


class TestCleanupWrapper(unittest.TestCase):
    def test_success_with_diagnostic_preserves_exact_batch_report_candidate(self) -> None:
        batch = successful_batch(("alpha-ocr", "Canada"))
        item = warning(batch)
        wrapped = OCRProviderExecutionWithCleanup(batch, (item,))

        self.assertIs(wrapped.batch, batch)
        self.assertIs(wrapped.diagnostics[0], item)
        self.assertIs(
            wrapped.batch.outcomes[0].status,
            OCRProviderExecutionStatus.SUCCEEDED,
        )
        self.assertIs(
            wrapped.batch.outcomes[0].report,
            batch.outcomes[0].report,
        )
        self.assertIs(
            wrapped.batch.outcomes[0].report.candidates[0],
            batch.outcomes[0].report.candidates[0],
        )

    def test_empty_diagnostics_is_valid(self) -> None:
        batch = successful_batch(("alpha-ocr", "Canada"))
        self.assertEqual(
            OCRProviderExecutionWithCleanup(batch, ()).diagnostics,
            (),
        )

    def test_non_tuple_wrong_item_and_wrong_batch_are_rejected(self) -> None:
        batch = successful_batch(("alpha-ocr", "Canada"))
        for bad_batch, diagnostics in (
            (object(), ()),
            (batch, [warning(batch)]),
            (batch, (object(),)),
        ):
            with self.subTest(), self.assertRaises(
                InvalidOCRProviderCleanupDiagnosticContextError
            ):
                OCRProviderExecutionWithCleanup(  # type: ignore[arg-type]
                    bad_batch,
                    diagnostics,
                )

    def test_foreign_and_equal_distinct_capabilities_are_rejected(self) -> None:
        batch = successful_batch(("alpha-ocr", "Canada"))
        foreign = fx.capabilities("foreign-ocr")
        equal_distinct = fx.capabilities("alpha-ocr")
        for provider in (foreign, equal_distinct):
            diagnostic = OCRProviderCleanupDiagnostic(
                provider=provider,
                severity=OCRProviderCleanupDiagnosticSeverity.WARNING,
                diagnostic_code="CLEANUP_FAILED",
            )
            with self.subTest(provider=provider.provider_id), self.assertRaises(
                InvalidOCRProviderCleanupDiagnosticContextError
            ):
                OCRProviderExecutionWithCleanup(batch, (diagnostic,))

    def test_duplicate_and_provider_order_are_rejected(self) -> None:
        batch = successful_batch(
            ("alpha-ocr", "Canada"),
            ("beta-ocr", "Canada"),
        )
        first = warning(batch, 0)
        second = warning(batch, 1)
        for diagnostics in ((first, first), (second, first)):
            with self.subTest(), self.assertRaises(
                InvalidOCRProviderCleanupDiagnosticContextError
            ):
                OCRProviderExecutionWithCleanup(batch, diagnostics)

    def test_wrong_artifact_key_is_rejected(self) -> None:
        batch = successful_batch(("alpha-ocr", "Canada"))
        with self.assertRaises(
            InvalidOCRProviderCleanupDiagnosticContextError
        ):
            OCRProviderExecutionWithCleanup(
                batch,
                (warning(batch, artifact_key="other-artifact"),),
            )

    def test_fatal_cleanup_stays_failed_without_duplicate_diagnostic(self) -> None:
        alpha = fx.capabilities("alpha-ocr")
        beta = fx.capabilities("beta-ocr")
        calls: list[str] = []
        batch = execute_selected_ocr_providers(
            fx.selection(alpha, beta),
            fx.bindings(
                (
                    alpha,
                    fx.FakeProvider(
                        "alpha-ocr",
                        OCRProviderCleanupError(
                            "alpha-ocr",
                            "CLEANUP_FAILED",
                        ),
                        order=calls,
                    ),
                ),
                (
                    beta,
                    fx.FakeProvider(
                        "beta-ocr",
                        fx.report(
                            "beta-ocr",
                            fx.candidate("beta-ocr"),
                        ),
                        order=calls,
                    ),
                ),
            ),
            fx.request(),
        )
        wrapped = OCRProviderExecutionWithCleanup(batch, ())

        self.assertEqual(calls, ["alpha-ocr", "beta-ocr"])
        self.assertIs(
            wrapped.batch.outcomes[0].failure_category,
            OCRProviderFailureCategory.CLEANUP,
        )
        self.assertIs(
            wrapped.batch.outcomes[1].status,
            OCRProviderExecutionStatus.SUCCEEDED,
        )
        failure = OCRProviderCleanupDiagnostic(
            provider=alpha,
            severity=OCRProviderCleanupDiagnosticSeverity.FAILURE,
            diagnostic_code="CLEANUP_FAILED",
        )
        with self.assertRaises(
            InvalidOCRProviderCleanupDiagnosticContextError
        ):
            OCRProviderExecutionWithCleanup(batch, (failure,))

    def test_warning_cannot_attach_to_failed_provider(self) -> None:
        alpha = fx.capabilities("alpha-ocr")
        batch = execute_selected_ocr_providers(
            fx.selection(alpha),
            fx.bindings(
                (
                    alpha,
                    fx.FakeProvider(
                        "alpha-ocr",
                        OCRProviderCleanupError(
                            "alpha-ocr",
                            "CLEANUP_FAILED",
                        ),
                    ),
                )
            ),
            fx.request(),
        )
        with self.assertRaises(
            InvalidOCRProviderCleanupDiagnosticContextError
        ):
            OCRProviderExecutionWithCleanup(batch, (warning(batch),))

    def test_wrapper_is_frozen_slotted_and_tuple_backed(self) -> None:
        batch = successful_batch(("alpha-ocr", "Canada"))
        wrapped = OCRProviderExecutionWithCleanup(batch, (warning(batch),))
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            wrapped.batch = batch  # type: ignore[misc]
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            wrapped.extra = object()  # type: ignore[attr-defined]


class TestCleanupCrossUnitPreservation(unittest.TestCase):
    def test_legacy_provider_emits_sanitized_warning_and_retains_report(self) -> None:
        capabilities = fx.capabilities("legacy-ocr")
        diagnostics: list[OCRProviderCleanupDiagnostic] = []
        experiment = DeterministicExperiment()
        provider = LegacyOCRWorkflowProvider(
            experiment=experiment,
            cleanup_capabilities=capabilities,
            cleanup_diagnostic_sink=diagnostics.append,
        )

        with patch.object(
            Path,
            "unlink",
            side_effect=OSError("sensitive path text"),
        ):
            report = provider.analyze(
                source_coin_id="coin-1",
                image_role="front",
                artifact_key="cropped-coin-1-front",
                image_bytes=jpeg(),
            )

        Path(experiment.temporary_path).unlink(missing_ok=True)
        self.assertTrue(report.provider_available)
        self.assertEqual(len(diagnostics), 1)
        item = diagnostics[0]
        self.assertIs(item.provider, capabilities)
        self.assertIs(
            item.severity,
            OCRProviderCleanupDiagnosticSeverity.WARNING,
        )
        self.assertEqual(
            item.diagnostic_code,
            "TEMPORARY_IMAGE_DELETE_FAILED",
        )
        self.assertNotIn("sensitive", item.diagnostic_code)
        self.assertFalse(hasattr(item, "path"))
        self.assertFalse(hasattr(item, "exception"))

    def test_successful_cleanup_does_not_call_sink(self) -> None:
        capabilities = fx.capabilities("legacy-ocr")
        diagnostics: list[OCRProviderCleanupDiagnostic] = []
        experiment = DeterministicExperiment()
        provider = LegacyOCRWorkflowProvider(
            experiment=experiment,
            cleanup_capabilities=capabilities,
            cleanup_diagnostic_sink=diagnostics.append,
        )

        report = provider.analyze(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            image_bytes=jpeg(),
        )

        self.assertTrue(report.provider_available)
        self.assertEqual(diagnostics, [])
        self.assertFalse(Path(experiment.temporary_path).exists())

    def test_sink_exception_cannot_destroy_valid_report_or_escape_text(self) -> None:
        capabilities = fx.capabilities("legacy-ocr")
        experiment = DeterministicExperiment()

        def failing_sink(_diagnostic: OCRProviderCleanupDiagnostic) -> None:
            raise RuntimeError("caller-controlled sensitive exception")

        provider = LegacyOCRWorkflowProvider(
            experiment=experiment,
            cleanup_capabilities=capabilities,
            cleanup_diagnostic_sink=failing_sink,
        )

        with patch.object(
            Path,
            "unlink",
            side_effect=OSError("sensitive path text"),
        ):
            report = provider.analyze(
                source_coin_id="coin-1",
                image_role="front",
                artifact_key="cropped-coin-1-front",
                image_bytes=jpeg(),
            )

        Path(experiment.temporary_path).unlink(missing_ok=True)
        self.assertTrue(report.provider_available)
        self.assertTrue(report.observations)

    def test_sink_return_value_is_ignored_and_each_failure_emits_once(self) -> None:
        capabilities = fx.capabilities("legacy-ocr")
        diagnostics: list[OCRProviderCleanupDiagnostic] = []
        paths: list[str] = []

        def sink(item: OCRProviderCleanupDiagnostic) -> object:
            diagnostics.append(item)
            return object()

        experiment = DeterministicExperiment()
        provider = LegacyOCRWorkflowProvider(
            experiment=experiment,
            cleanup_capabilities=capabilities,
            cleanup_diagnostic_sink=sink,
        )

        for artifact_key in ("first-front", "second-front"):
            with patch.object(
                Path,
                "unlink",
                side_effect=OSError("delete failed"),
            ):
                report = provider.analyze(
                    source_coin_id="coin-1",
                    image_role="front",
                    artifact_key=artifact_key,
                    image_bytes=jpeg(),
                )
            paths.append(experiment.temporary_path)
            self.assertTrue(report.provider_available)

        for temporary_path in paths:
            Path(temporary_path).unlink(missing_ok=True)
        self.assertEqual(
            tuple(item.artifact_key for item in diagnostics),
            ("first-front", "second-front"),
        )

    def test_legacy_cleanup_sink_is_strictly_explicit(self) -> None:
        capabilities = fx.capabilities("legacy-ocr")
        with self.assertRaises(ValueError):
            LegacyOCRWorkflowProvider(
                cleanup_capabilities=capabilities,
            )
        with self.assertRaises(ValueError):
            LegacyOCRWorkflowProvider(
                cleanup_diagnostic_sink=lambda _item: None,
            )

    def test_warning_does_not_change_consensus(self) -> None:
        batch = successful_batch(
            ("alpha-ocr", "Canada"),
            ("beta-ocr", "Canada"),
        )
        before = compare_ocr_provider_outcomes(batch)
        wrapped = OCRProviderExecutionWithCleanup(
            batch,
            (warning(batch, 1),),
        )
        after = compare_ocr_provider_outcomes(wrapped.batch)
        self.assertEqual(before, after)
        self.assertIs(
            after.fields[0].status,
            OCRProviderEnsembleFieldStatus.CONSENSUS,
        )

    def test_warning_does_not_change_conflict(self) -> None:
        batch = successful_batch(
            ("alpha-ocr", "Canada"),
            ("beta-ocr", "France"),
        )
        wrapped = OCRProviderExecutionWithCleanup(
            batch,
            (warning(batch),),
        )
        result = compare_ocr_provider_outcomes(wrapped.batch)
        self.assertIs(
            result.fields[0].status,
            OCRProviderEnsembleFieldStatus.CONFLICT,
        )

    def test_warning_does_not_change_calibrated_candidate(self) -> None:
        batch = successful_batch(("alpha-ocr", "Canada"), confidence=50.0)
        registry = OCRConfidenceCalibrationRegistry(
            (
                OCRConfidenceCalibrationProfile(
                    profile_id="alpha-default-v1",
                    provider_id="alpha-ocr",
                    field_name=None,
                    points=(
                        OCRConfidenceCalibrationPoint(0, 0),
                        OCRConfidenceCalibrationPoint(10_000, 8_000),
                    ),
                ),
            )
        )
        before = calibrate_ocr_execution_confidence(batch, registry)
        wrapped = OCRProviderExecutionWithCleanup(
            batch,
            (warning(batch),),
        )
        after = calibrate_ocr_execution_confidence(wrapped.batch, registry)
        self.assertEqual(before, after)
        self.assertIs(after.batch, batch)
        self.assertIs(
            after.candidates[0].candidate,
            batch.outcomes[0].report.candidates[0],
        )


if __name__ == "__main__":
    unittest.main()
