from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from capture_import.enums import ImageRole
from capture_import.workflow_ocr_models import (
    OCRConflict,
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRObservation,
)
from capture_import.workflow_ocr_provider_contracts import (
    OCRProviderAvailability,
    OCRProviderCapabilities,
    OCRProviderCleanupError,
    OCRProviderExecutionError,
    OCRProviderFieldSupportMode,
    OCRProviderInputError,
    OCRProviderOutputError,
    OCRProviderUnavailableError,
)
from capture_import.workflow_ocr_provider_execution import (
    InvalidOCRProviderExecutionContextError,
    MismatchedOCRProviderBindingError,
    MissingOCRProviderBindingError,
    NoSelectedOCRProvidersError,
    OCRProviderBatchError,
    OCRProviderExecutionBatch,
    OCRProviderExecutionBinding,
    OCRProviderExecutionBindings,
    OCRProviderExecutionContractError,
    OCRProviderExecutionOutcome,
    OCRProviderExecutionRequest,
    OCRProviderExecutionStatus,
    OCRProviderFailureCategory,
    execute_selected_ocr_providers,
)
from capture_import.workflow_ocr_provider_selection import (
    OCRProviderAvailabilityPolicy,
    OCRProviderRegistry,
    OCRProviderSelectionCriteria,
    select_ocr_providers,
)


PUBLIC_API = {
    "OCRProviderExecutionContractError",
    "InvalidOCRProviderExecutionContextError",
    "OCRProviderBatchError",
    "NoSelectedOCRProvidersError",
    "MissingOCRProviderBindingError",
    "MismatchedOCRProviderBindingError",
    "OCRProviderExecutionStatus",
    "OCRProviderFailureCategory",
    "OCRProviderExecutionBinding",
    "OCRProviderExecutionBindings",
    "OCRProviderExecutionRequest",
    "OCRProviderExecutionOutcome",
    "OCRProviderExecutionBatch",
    "execute_selected_ocr_providers",
}


def capabilities(
    provider_id: str,
    *,
    availability: OCRProviderAvailability = OCRProviderAvailability.AVAILABLE,
    field_mode: OCRProviderFieldSupportMode = (
        OCRProviderFieldSupportMode.DECLARED
    ),
    fields: tuple[str, ...] = ("country", "year"),
) -> OCRProviderCapabilities:
    return OCRProviderCapabilities(
        provider_id=provider_id,
        availability=availability,
        supported_image_roles=(ImageRole.FRONT,),
        supported_media_types=("image/jpeg",),
        field_support_mode=field_mode,
        supported_fields=fields,
    )


def selection(
    *items: OCRProviderCapabilities,
    fields: tuple[str, ...] = ("country",),
):
    return select_ocr_providers(
        OCRProviderRegistry(tuple(items)),
        OCRProviderSelectionCriteria(
            required_image_role=ImageRole.FRONT,
            required_media_type="image/jpeg",
            required_fields=fields,
            availability_policy=(
                OCRProviderAvailabilityPolicy.REQUIRE_AVAILABLE
            ),
        ),
    )


def request(**changes: object) -> OCRProviderExecutionRequest:
    values: dict[str, object] = {
        "source_coin_id": "coin-1",
        "image_role": ImageRole.FRONT,
        "artifact_key": "cropped-coin-1-front",
        "media_type": "image/jpeg",
        "image_bytes": b"immutable-image",
    }
    values.update(changes)
    return OCRProviderExecutionRequest(**values)  # type: ignore[arg-type]


def candidate(
    provider_id: str,
    field_name: str = "country",
    value: str = "Canada",
    *,
    confidence: float = 50.0,
    source_coin_id: str = "coin-1",
    image_role: str = "front",
    artifact_key: str = "cropped-coin-1-front",
) -> OCRFieldCandidate:
    return OCRFieldCandidate(
        source_coin_id=source_coin_id,
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id=provider_id,
        field_name=field_name,
        raw_text=value,
        normalized_value=value,
        confidence_score=confidence,
    )


def report(
    provider_id: str,
    *candidates: OCRFieldCandidate,
    source_coin_id: str = "coin-1",
    image_role: str = "front",
    artifact_key: str = "cropped-coin-1-front",
    available: bool = True,
) -> OCRMetadataReport:
    if not available:
        return OCRMetadataReport(
            provider_available=False,
            review_status=__import__(
                "capture_import.workflow_ocr_models",
                fromlist=["OCRReviewStatus"],
            ).OCRReviewStatus.UNAVAILABLE,
        )
    observation = OCRObservation(
        source_coin_id=source_coin_id,
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id=provider_id,
        raw_text="raw",
        confidence_score=50.0,
    )
    ordered = tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.source_coin_id,
                item.field_name,
                item.image_role,
                item.normalized_value,
                item.provider_id,
                item.artifact_key,
            ),
        )
    )
    conflicts = []
    for field_name in sorted({item.field_name for item in ordered}):
        values = tuple(
            item.normalized_value
            for item in ordered
            if item.field_name == field_name
        )
        if len(values) > 1:
            conflicts.append(
                OCRConflict(
                    source_coin_id=source_coin_id,
                    field_name=field_name,
                    candidate_values=values,
                    reason="provider supplied multiple values",
                )
            )
    return OCRMetadataReport(
        provider_available=True,
        observations=(observation,),
        candidates=ordered,
        conflicts=tuple(conflicts),
        review_status=(
            __import__(
                "capture_import.workflow_ocr_models",
                fromlist=["OCRReviewStatus"],
            ).OCRReviewStatus.CONFLICT
            if conflicts
            else __import__(
                "capture_import.workflow_ocr_models",
                fromlist=["OCRReviewStatus"],
            ).OCRReviewStatus.REVIEW_REQUIRED
        ),
    )


class FakeProvider:
    def __init__(
        self,
        provider_id: str,
        behavior: object,
        *,
        order: list[str] | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.behavior = behavior
        self.calls: list[dict[str, object]] = []
        self.order = order

    def analyze(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.order is not None:
            self.order.append(self.provider_id)
        if isinstance(self.behavior, BaseException):
            raise self.behavior
        if callable(self.behavior):
            return self.behavior(**kwargs)
        return self.behavior


def bindings(
    *pairs: tuple[OCRProviderCapabilities, FakeProvider],
) -> OCRProviderExecutionBindings:
    return OCRProviderExecutionBindings(
        tuple(
            OCRProviderExecutionBinding(capability, provider)
            for capability, provider in pairs
        )
    )


class TestExecutionPublicAPI(unittest.TestCase):
    def test_exact_public_api(self) -> None:
        from capture_import import workflow_ocr_provider_execution as module

        self.assertEqual(set(module.__all__), PUBLIC_API)
        self.assertEqual(len(module.__all__), len(PUBLIC_API))

    def test_error_hierarchy_is_distinct_from_unit_1a_execution_error(
        self,
    ) -> None:
        self.assertTrue(issubclass(OCRProviderExecutionContractError, ValueError))
        self.assertTrue(
            issubclass(
                InvalidOCRProviderExecutionContextError,
                OCRProviderExecutionContractError,
            )
        )
        self.assertTrue(issubclass(OCRProviderBatchError, Exception))
        self.assertFalse(issubclass(OCRProviderBatchError, OCRProviderExecutionError))
        with self.assertRaisesRegex(TypeError, "cannot be constructed directly"):
            OCRProviderBatchError("caller-controlled message")

    def test_no_serialization_ranking_retry_or_async_api(self) -> None:
        from capture_import import workflow_ocr_provider_execution as module

        forbidden = {
            "to_dict",
            "from_dict",
            "serialize",
            "save",
            "load",
            "rank",
            "score",
            "retry",
            "fallback",
            "timeout",
            "execute_async",
        }
        for name in module.__all__:
            value = getattr(module, name)
            self.assertTrue(forbidden.isdisjoint(dir(value)))


class TestExecutionBindingContracts(unittest.TestCase):
    def test_binding_preserves_exact_capability_and_provider_identity(self) -> None:
        cap = capabilities("alpha-ocr")
        provider = FakeProvider("alpha-ocr", report("alpha-ocr"))

        value = OCRProviderExecutionBinding(cap, provider)

        self.assertIs(value.capabilities, cap)
        self.assertIs(value.provider, provider)
        self.assertEqual(value.provider_id, "alpha-ocr")

    def test_binding_is_frozen_slotted_and_identity_based(self) -> None:
        cap = capabilities("alpha-ocr")
        provider = FakeProvider("alpha-ocr", report("alpha-ocr"))
        value = OCRProviderExecutionBinding(cap, provider)

        with self.assertRaises(FrozenInstanceError):
            value.provider = provider  # type: ignore[misc]
        self.assertFalse(hasattr(value, "__dict__"))
        self.assertNotEqual(value, OCRProviderExecutionBinding(cap, provider))

    def test_binding_rejects_wrong_capability_and_provider(self) -> None:
        with self.assertRaises(InvalidOCRProviderExecutionContextError):
            OCRProviderExecutionBinding(  # type: ignore[arg-type]
                object(),
                FakeProvider("alpha-ocr", object()),
            )
        with self.assertRaises(InvalidOCRProviderExecutionContextError):
            OCRProviderExecutionBinding(  # type: ignore[arg-type]
                capabilities("alpha-ocr"),
                object(),
            )

    def test_binding_wraps_malformed_nested_capability(self) -> None:
        malformed = object.__new__(OCRProviderCapabilities)

        with self.assertRaises(InvalidOCRProviderExecutionContextError):
            OCRProviderExecutionBinding(
                malformed,
                FakeProvider("alpha-ocr", object()),
            )

    def test_binding_rejects_provider_id_mismatch(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderExecutionContextError,
            "exactly match",
        ):
            OCRProviderExecutionBinding(
                capabilities("alpha-ocr"),
                FakeProvider("beta-ocr", object()),
            )

    def test_binding_rejects_unreadable_provider_id(self) -> None:
        class BrokenID:
            @property
            def provider_id(self):
                raise RuntimeError("secret")

            def analyze(self, **kwargs):
                return kwargs

        with self.assertRaisesRegex(
            InvalidOCRProviderExecutionContextError,
            "could not be read",
        ):
            OCRProviderExecutionBinding(
                capabilities("alpha-ocr"),
                BrokenID(),
            )

    def test_binding_registry_is_canonical_and_identity_preserving(self) -> None:
        alpha = capabilities("alpha-ocr")
        beta = capabilities("beta-ocr")
        alpha_provider = FakeProvider("alpha-ocr", report("alpha-ocr"))
        beta_provider = FakeProvider("beta-ocr", report("beta-ocr"))

        registry = bindings(
            (alpha, alpha_provider),
            (beta, beta_provider),
        )

        self.assertEqual(registry.provider_ids, ("alpha-ocr", "beta-ocr"))
        self.assertIs(registry.bindings[0].capabilities, alpha)

    def test_binding_registry_rejects_empty_list_and_wrong_items(self) -> None:
        for value in ((), [], (object(),)):
            with self.subTest(value=value):
                with self.assertRaises(
                    InvalidOCRProviderExecutionContextError
                ):
                    OCRProviderExecutionBindings(value)  # type: ignore[arg-type]

    def test_binding_registry_rejects_duplicate_and_reversed_ids(self) -> None:
        alpha = capabilities("alpha-ocr")
        beta = capabilities("beta-ocr")
        first = OCRProviderExecutionBinding(
            alpha,
            FakeProvider("alpha-ocr", object()),
        )
        duplicate = OCRProviderExecutionBinding(
            alpha,
            FakeProvider("alpha-ocr", object()),
        )
        second = OCRProviderExecutionBinding(
            beta,
            FakeProvider("beta-ocr", object()),
        )
        for value in ((first, duplicate), (second, first)):
            with self.subTest(value=value):
                with self.assertRaises(
                    InvalidOCRProviderExecutionContextError
                ):
                    OCRProviderExecutionBindings(value)


class TestExecutionRequestContract(unittest.TestCase):
    def test_request_preserves_exact_values_and_is_immutable(self) -> None:
        value = request()

        self.assertIs(value.image_role, ImageRole.FRONT)
        self.assertEqual(value.image_bytes, b"immutable-image")
        with self.assertRaises(FrozenInstanceError):
            value.media_type = "image/png"  # type: ignore[misc]
        self.assertFalse(hasattr(value, "__dict__"))

    def test_request_rejects_wrong_role_media_bytes_and_artifact_path(self) -> None:
        cases = (
            {"image_role": "front"},
            {"media_type": "Image/JPEG"},
            {"media_type": "image/*"},
            {"image_bytes": bytearray(b"x")},
            {"image_bytes": b""},
            {"artifact_key": "../front.jpg"},
            {"source_coin_id": ""},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(
                    InvalidOCRProviderExecutionContextError
                ):
                    request(**changes)


class TestExecutionPreconditions(unittest.TestCase):
    def test_zero_eligible_rejected_before_provider_invocation(self) -> None:
        cap = capabilities(
            "alpha-ocr",
            availability=OCRProviderAvailability.UNAVAILABLE,
        )
        selected = selection(cap)
        provider = FakeProvider("alpha-ocr", report("alpha-ocr"))

        with self.assertRaises(NoSelectedOCRProvidersError):
            execute_selected_ocr_providers(
                selected,
                bindings((cap, provider)),
                request(),
            )

        self.assertEqual(provider.calls, [])

    def test_missing_binding_rejected_before_any_invocation(self) -> None:
        alpha = capabilities("alpha-ocr")
        beta = capabilities("beta-ocr")
        selected = selection(alpha, beta)
        alpha_provider = FakeProvider("alpha-ocr", report("alpha-ocr"))

        with self.assertRaises(MissingOCRProviderBindingError) as caught:
            execute_selected_ocr_providers(
                selected,
                bindings((alpha, alpha_provider)),
                request(),
            )

        self.assertEqual(caught.exception.provider_id, "beta-ocr")
        self.assertEqual(alpha_provider.calls, [])

    def test_equal_but_distinct_capability_binding_fails_identity(self) -> None:
        selected_capability = capabilities("alpha-ocr")
        equal_capability = capabilities("alpha-ocr")
        selected = selection(selected_capability)
        provider = FakeProvider("alpha-ocr", report("alpha-ocr"))

        with self.assertRaises(MismatchedOCRProviderBindingError):
            execute_selected_ocr_providers(
                selected,
                bindings((equal_capability, provider)),
                request(),
            )

        self.assertEqual(provider.calls, [])

    def test_provider_id_change_after_binding_fails_before_invocation(self) -> None:
        cap = capabilities("alpha-ocr")
        provider = FakeProvider("alpha-ocr", report("alpha-ocr"))
        registry = bindings((cap, provider))
        provider.provider_id = "beta-ocr"

        with self.assertRaises(InvalidOCRProviderExecutionContextError):
            execute_selected_ocr_providers(selection(cap), registry, request())

        self.assertEqual(provider.calls, [])

    def test_extra_binding_is_allowed_and_not_invoked(self) -> None:
        alpha = capabilities("alpha-ocr")
        beta = capabilities("beta-ocr")
        alpha_provider = FakeProvider("alpha-ocr", report("alpha-ocr"))
        beta_provider = FakeProvider("beta-ocr", report("beta-ocr"))

        batch = execute_selected_ocr_providers(
            selection(alpha),
            bindings(
                (alpha, alpha_provider),
                (beta, beta_provider),
            ),
            request(),
        )

        self.assertEqual(batch.provider_ids, ("alpha-ocr",))
        self.assertEqual(len(alpha_provider.calls), 1)
        self.assertEqual(beta_provider.calls, [])

    def test_role_and_media_mismatch_fail_before_invocation(self) -> None:
        cap = capabilities("alpha-ocr")
        provider = FakeProvider("alpha-ocr", report("alpha-ocr"))
        selected = selection(cap)
        for bad_request in (
            request(image_role=ImageRole.REVERSE),
            request(media_type="image/png"),
        ):
            with self.subTest(request=bad_request):
                with self.assertRaises(
                    InvalidOCRProviderExecutionContextError
                ):
                    execute_selected_ocr_providers(
                        selected,
                        bindings((cap, provider)),
                        bad_request,
                    )
        self.assertEqual(provider.calls, [])


class TestProviderExecution(unittest.TestCase):
    def test_invokes_all_providers_once_in_selection_order(self) -> None:
        order: list[str] = []
        caps = tuple(
            capabilities(provider_id)
            for provider_id in ("alpha-ocr", "beta-ocr", "legacy-ocr")
        )
        providers = tuple(
            FakeProvider(
                cap.provider_id,
                report(cap.provider_id),
                order=order,
            )
            for cap in caps
        )

        batch = execute_selected_ocr_providers(
            selection(*caps),
            bindings(*zip(caps, providers, strict=True)),
            request(),
        )

        self.assertEqual(order, ["alpha-ocr", "beta-ocr", "legacy-ocr"])
        self.assertEqual(batch.provider_ids, tuple(cap.provider_id for cap in caps))
        self.assertTrue(
            all(len(provider.calls) == 1 for provider in providers)
        )

    def test_success_retains_exact_capability_report_and_request(self) -> None:
        cap = capabilities("alpha-ocr")
        source_report = report(
            "alpha-ocr",
            candidate("alpha-ocr"),
        )
        provider = FakeProvider("alpha-ocr", source_report)
        execution_request = request()
        selected = selection(cap)

        batch = execute_selected_ocr_providers(
            selected,
            bindings((cap, provider)),
            execution_request,
        )

        outcome = batch.outcomes[0]
        self.assertIs(batch.selection, selected)
        self.assertIs(batch.request, execution_request)
        self.assertIs(outcome.capabilities, cap)
        self.assertIs(outcome.report, source_report)
        self.assertEqual(outcome.status, OCRProviderExecutionStatus.SUCCEEDED)
        self.assertEqual(
            provider.calls[0],
            {
                "source_coin_id": "coin-1",
                "image_role": "front",
                "artifact_key": "cropped-coin-1-front",
                "image_bytes": b"immutable-image",
            },
        )

    def test_typed_provider_failures_are_sanitized_and_do_not_short_circuit(
        self,
    ) -> None:
        error_cases = (
            (
                OCRProviderUnavailableError,
                OCRProviderFailureCategory.UNAVAILABLE,
            ),
            (OCRProviderInputError, OCRProviderFailureCategory.INPUT),
            (OCRProviderExecutionError, OCRProviderFailureCategory.EXECUTION),
            (OCRProviderOutputError, OCRProviderFailureCategory.OUTPUT),
            (OCRProviderCleanupError, OCRProviderFailureCategory.CLEANUP),
        )
        for error_type, category in error_cases:
            with self.subTest(error_type=error_type):
                alpha = capabilities("alpha-ocr")
                beta = capabilities("beta-ocr")
                first = FakeProvider(
                    "alpha-ocr",
                    error_type("alpha-ocr", "PROVIDER_FAILED"),
                )
                second_report = report("beta-ocr")
                second = FakeProvider("beta-ocr", second_report)

                batch = execute_selected_ocr_providers(
                    selection(alpha, beta),
                    bindings((alpha, first), (beta, second)),
                    request(),
                )

                failed, succeeded = batch.outcomes
                self.assertEqual(failed.failure_category, category)
                self.assertEqual(failed.diagnostic_code, "PROVIDER_FAILED")
                self.assertIsNone(failed.report)
                self.assertIs(succeeded.report, second_report)
                self.assertEqual(len(second.calls), 1)
                self.assertNotIn(
                    str(first.behavior),
                    failed.diagnostic_code,
                )

    def test_unexpected_failure_uses_fixed_code_and_continues(self) -> None:
        alpha = capabilities("alpha-ocr")
        beta = capabilities("beta-ocr")
        first = FakeProvider("alpha-ocr", RuntimeError("secret path C:\\x"))
        second = FakeProvider("beta-ocr", report("beta-ocr"))

        batch = execute_selected_ocr_providers(
            selection(alpha, beta),
            bindings((alpha, first), (beta, second)),
            request(),
        )

        self.assertEqual(
            batch.outcomes[0].failure_category,
            OCRProviderFailureCategory.UNEXPECTED,
        )
        self.assertEqual(
            batch.outcomes[0].diagnostic_code,
            "UNEXPECTED_PROVIDER_FAILURE",
        )
        self.assertEqual(len(second.calls), 1)

    def test_mismatched_typed_error_id_is_output_failure(self) -> None:
        cap = capabilities("alpha-ocr")
        provider = FakeProvider(
            "alpha-ocr",
            OCRProviderExecutionError("beta-ocr", "ENGINE_FAILED"),
        )

        outcome = execute_selected_ocr_providers(
            selection(cap),
            bindings((cap, provider)),
            request(),
        ).outcomes[0]

        self.assertEqual(
            outcome.failure_category,
            OCRProviderFailureCategory.OUTPUT,
        )
        self.assertEqual(
            outcome.diagnostic_code,
            "MISMATCHED_PROVIDER_ERROR_ID",
        )

    def test_keyboard_interrupt_and_system_exit_propagate(self) -> None:
        for error in (KeyboardInterrupt(), SystemExit(3)):
            cap = capabilities("alpha-ocr")
            provider = FakeProvider("alpha-ocr", error)
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)):
                    execute_selected_ocr_providers(
                        selection(cap),
                        bindings((cap, provider)),
                        request(),
                    )

    def test_reported_unavailable_becomes_unavailable_failure(self) -> None:
        cap = capabilities("alpha-ocr")
        provider = FakeProvider(
            "alpha-ocr",
            report("alpha-ocr", available=False),
        )

        outcome = execute_selected_ocr_providers(
            selection(cap),
            bindings((cap, provider)),
            request(),
        ).outcomes[0]

        self.assertEqual(
            outcome.failure_category,
            OCRProviderFailureCategory.UNAVAILABLE,
        )
        self.assertEqual(
            outcome.diagnostic_code,
            "PROVIDER_REPORTED_UNAVAILABLE",
        )

    def test_malformed_outputs_are_isolated_and_later_provider_runs(self) -> None:
        malformed_reports = (
            object(),
            report(
                "wrong-ocr",
                candidate("wrong-ocr"),
            ),
            report(
                "alpha-ocr",
                candidate("alpha-ocr", source_coin_id="other"),
                source_coin_id="other",
            ),
            report(
                "alpha-ocr",
                candidate("alpha-ocr", field_name="year", value="1967"),
            ),
        )
        for malformed in malformed_reports:
            with self.subTest(malformed=type(malformed).__name__):
                alpha = capabilities("alpha-ocr", fields=("country",))
                beta = capabilities("beta-ocr")
                first = FakeProvider("alpha-ocr", malformed)
                second = FakeProvider("beta-ocr", report("beta-ocr"))

                batch = execute_selected_ocr_providers(
                    selection(alpha, beta, fields=()),
                    bindings((alpha, first), (beta, second)),
                    request(),
                )

                self.assertEqual(
                    batch.outcomes[0].failure_category,
                    OCRProviderFailureCategory.OUTPUT,
                )
                self.assertEqual(
                    batch.outcomes[0].diagnostic_code,
                    "INVALID_PROVIDER_OUTPUT",
                )
                self.assertEqual(len(second.calls), 1)

    def test_unknown_field_support_may_emit_canonical_fields(self) -> None:
        cap = capabilities(
            "unknown-ocr",
            field_mode=OCRProviderFieldSupportMode.UNKNOWN,
            fields=(),
        )
        source_report = report(
            "unknown-ocr",
            candidate("unknown-ocr", field_name="variety_keyword", value="Wide"),
        )

        outcome = execute_selected_ocr_providers(
            selection(cap, fields=()),
            bindings((cap, FakeProvider("unknown-ocr", source_report))),
            request(),
        ).outcomes[0]

        self.assertIs(outcome.report, source_report)

    def test_multiple_provider_candidates_are_preserved_when_conflict_exact(
        self,
    ) -> None:
        cap = capabilities("alpha-ocr")
        first = candidate("alpha-ocr", value="Canada")
        second = candidate("alpha-ocr", value="CANADA")
        source_report = report("alpha-ocr", first, second)

        outcome = execute_selected_ocr_providers(
            selection(cap),
            bindings((cap, FakeProvider("alpha-ocr", source_report))),
            request(),
        ).outcomes[0]

        self.assertIs(outcome.report, source_report)
        self.assertIs(outcome.report.candidates[0], second)
        self.assertIs(outcome.report.candidates[1], first)

    def test_legacy_like_analyze_provider_uses_unchanged_signature(self) -> None:
        cap = capabilities(
            "legacy-ocr",
            fields=(
                "banknote_prefix",
                "certification_number",
                "country",
                "denomination",
                "year",
            ),
        )
        legacy_report = report(
            "legacy-ocr",
            candidate("legacy-ocr", field_name="year", value="1967"),
        )
        provider = FakeProvider("legacy-ocr", legacy_report)

        batch = execute_selected_ocr_providers(
            selection(cap, fields=("year",)),
            bindings((cap, provider)),
            request(),
        )

        self.assertIs(batch.outcomes[0].report, legacy_report)
        self.assertEqual(len(provider.calls), 1)


class TestExecutionOutcomeAndBatchContracts(unittest.TestCase):
    def test_success_and_failure_pairing_is_strict(self) -> None:
        cap = capabilities("alpha-ocr")
        source_report = report("alpha-ocr")
        invalid = (
            dict(
                status=OCRProviderExecutionStatus.SUCCEEDED,
                report=None,
                failure_category=None,
                diagnostic_code=None,
            ),
            dict(
                status=OCRProviderExecutionStatus.SUCCEEDED,
                report=source_report,
                failure_category=OCRProviderFailureCategory.OUTPUT,
                diagnostic_code="BAD",
            ),
            dict(
                status=OCRProviderExecutionStatus.FAILED,
                report=source_report,
                failure_category=OCRProviderFailureCategory.OUTPUT,
                diagnostic_code="BAD",
            ),
            dict(
                status=OCRProviderExecutionStatus.FAILED,
                report=None,
                failure_category=None,
                diagnostic_code=None,
            ),
        )
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises(
                    InvalidOCRProviderExecutionContextError
                ):
                    OCRProviderExecutionOutcome(capabilities=cap, **values)

    def test_outcome_and_batch_are_frozen_and_slotted(self) -> None:
        cap = capabilities("alpha-ocr")
        batch = execute_selected_ocr_providers(
            selection(cap),
            bindings((cap, FakeProvider("alpha-ocr", report("alpha-ocr")))),
            request(),
        )

        with self.assertRaises(FrozenInstanceError):
            batch.outcomes = ()  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            batch.outcomes[0].report = None  # type: ignore[misc]
        self.assertFalse(hasattr(batch, "__dict__"))
        self.assertFalse(hasattr(batch.outcomes[0], "__dict__"))

    def test_batch_rejects_missing_foreign_and_reordered_outcomes(self) -> None:
        alpha = capabilities("alpha-ocr")
        beta = capabilities("beta-ocr")
        selected = selection(alpha, beta)
        execution_request = request()
        alpha_outcome = OCRProviderExecutionOutcome(
            alpha,
            OCRProviderExecutionStatus.SUCCEEDED,
            report("alpha-ocr"),
            None,
            None,
        )
        beta_outcome = OCRProviderExecutionOutcome(
            beta,
            OCRProviderExecutionStatus.SUCCEEDED,
            report("beta-ocr"),
            None,
            None,
        )
        invalid = (
            (),
            (alpha_outcome,),
            (beta_outcome, alpha_outcome),
            (alpha_outcome, alpha_outcome),
        )
        for outcomes in invalid:
            with self.subTest(outcomes=outcomes):
                with self.assertRaises(
                    InvalidOCRProviderExecutionContextError
                ):
                    OCRProviderExecutionBatch(
                        selected,
                        execution_request,
                        outcomes,
                    )

    def test_batch_supports_partial_and_all_failure(self) -> None:
        alpha = capabilities("alpha-ocr")
        beta = capabilities("beta-ocr")
        partial = execute_selected_ocr_providers(
            selection(alpha, beta),
            bindings(
                (
                    alpha,
                    FakeProvider(
                        "alpha-ocr",
                        OCRProviderInputError("alpha-ocr", "BAD_INPUT"),
                    ),
                ),
                (beta, FakeProvider("beta-ocr", report("beta-ocr"))),
            ),
            request(),
        )
        all_failed = execute_selected_ocr_providers(
            selection(alpha, beta),
            bindings(
                (
                    alpha,
                    FakeProvider(
                        "alpha-ocr",
                        OCRProviderInputError("alpha-ocr", "BAD_INPUT"),
                    ),
                ),
                (
                    beta,
                    FakeProvider(
                        "beta-ocr",
                        OCRProviderOutputError("beta-ocr", "BAD_OUTPUT"),
                    ),
                ),
            ),
            request(),
        )

        self.assertEqual(len(partial.failed_outcomes), 1)
        self.assertEqual(len(partial.successful_outcomes), 1)
        self.assertEqual(len(all_failed.failed_outcomes), 2)
        self.assertEqual(all_failed.successful_outcomes, ())

    def test_batch_errors_have_immutable_bounded_attributes(self) -> None:
        for error in (
            MissingOCRProviderBindingError("alpha-ocr"),
            MismatchedOCRProviderBindingError("alpha-ocr"),
        ):
            with self.subTest(error=type(error).__name__):
                self.assertEqual(error.provider_id, "alpha-ocr")
                self.assertEqual(vars(error), {})
                with self.assertRaisesRegex(AttributeError, "immutable"):
                    error.provider_id = "beta-ocr"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
