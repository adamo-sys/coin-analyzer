from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal
import ast
from pathlib import Path
import unittest

from capture_import.workflow_ocr_confidence_calibration import (
    InvalidOCRConfidenceCalibrationContextError,
    OCRCalibratedCandidateConfidence,
    OCRCalibratedExecutionConfidence,
    OCRConfidenceCalibrationContractError,
    OCRConfidenceCalibrationCoverageError,
    OCRConfidenceCalibrationError,
    OCRConfidenceCalibrationInputError,
    OCRConfidenceCalibrationPoint,
    OCRConfidenceCalibrationProfile,
    OCRConfidenceCalibrationProfileNotFoundError,
    OCRConfidenceCalibrationRegistry,
    calibrate_ocr_confidence_value,
    calibrate_ocr_execution_confidence,
    resolve_ocr_confidence_calibration_profile,
)
from capture_import.workflow_ocr_ensemble import (
    OCRProviderEnsembleFieldStatus,
    compare_ocr_provider_outcomes,
)
from capture_import.workflow_ocr_models import OCRFieldCandidate
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
    "OCRConfidenceCalibrationContractError",
    "InvalidOCRConfidenceCalibrationContextError",
    "OCRConfidenceCalibrationError",
    "OCRConfidenceCalibrationProfileNotFoundError",
    "OCRConfidenceCalibrationCoverageError",
    "OCRConfidenceCalibrationInputError",
    "OCRConfidenceCalibrationPoint",
    "OCRConfidenceCalibrationProfile",
    "OCRConfidenceCalibrationRegistry",
    "OCRCalibratedCandidateConfidence",
    "OCRCalibratedExecutionConfidence",
    "resolve_ocr_confidence_calibration_profile",
    "calibrate_ocr_confidence_value",
    "calibrate_ocr_execution_confidence",
}


def point(raw: int, calibrated: int) -> OCRConfidenceCalibrationPoint:
    return OCRConfidenceCalibrationPoint(
        raw_confidence_bps=raw,
        calibrated_confidence_bps=calibrated,
    )


def profile(
    profile_id: str = "alpha-ocr-default-v1",
    provider_id: str = "alpha-ocr",
    field_name: str | None = None,
    points: tuple[OCRConfidenceCalibrationPoint, ...] = (
        OCRConfidenceCalibrationPoint(0, 0),
        OCRConfidenceCalibrationPoint(10_000, 10_000),
    ),
) -> OCRConfidenceCalibrationProfile:
    return OCRConfidenceCalibrationProfile(
        profile_id=profile_id,
        provider_id=provider_id,
        field_name=field_name,
        points=points,
    )


def registry(
    *profiles: OCRConfidenceCalibrationProfile,
) -> OCRConfidenceCalibrationRegistry:
    return OCRConfidenceCalibrationRegistry(tuple(profiles))


def make_batch(
    *provider_candidates: tuple[
        str,
        tuple[tuple[str, str, float], ...] | BaseException,
    ],
    required_fields: tuple[str, ...] = (),
) -> OCRProviderExecutionBatch:
    capabilities = tuple(
        fx.capabilities(provider_id)
        for provider_id, _ in provider_candidates
    )
    providers = []
    for capability, (_, values) in zip(
        capabilities,
        provider_candidates,
        strict=True,
    ):
        if isinstance(values, BaseException):
            behavior: object = values
        else:
            candidates = tuple(
                fx.candidate(
                    capability.provider_id,
                    field_name,
                    value,
                    confidence=confidence,
                )
                for field_name, value, confidence in values
            )
            behavior = fx.report(capability.provider_id, *candidates)
        providers.append(
            fx.FakeProvider(capability.provider_id, behavior)
        )
    return execute_selected_ocr_providers(
        fx.selection(*capabilities, fields=required_fields),
        fx.bindings(
            *tuple(zip(capabilities, providers, strict=True))
        ),
        fx.request(),
    )


def one_candidate_batch(
    *,
    confidence: float = 50.0,
    field_name: str = "country",
    provider_id: str = "alpha-ocr",
) -> OCRProviderExecutionBatch:
    return make_batch(
        (
            provider_id,
            ((field_name, "Canada", confidence),),
        )
    )


class TestPublicAPIAndArchitecture(unittest.TestCase):
    def test_exact_public_api(self) -> None:
        from capture_import import workflow_ocr_confidence_calibration as module

        self.assertEqual(set(module.__all__), PUBLIC_API)
        self.assertEqual(len(module.__all__), len(PUBLIC_API))

    def test_error_hierarchy(self) -> None:
        self.assertTrue(
            issubclass(OCRConfidenceCalibrationContractError, ValueError)
        )
        self.assertTrue(
            issubclass(
                InvalidOCRConfidenceCalibrationContextError,
                OCRConfidenceCalibrationContractError,
            )
        )
        for error_type in (
            OCRConfidenceCalibrationProfileNotFoundError,
            OCRConfidenceCalibrationCoverageError,
            OCRConfidenceCalibrationInputError,
        ):
            self.assertTrue(issubclass(error_type, OCRConfidenceCalibrationError))
        with self.assertRaisesRegex(TypeError, "cannot be constructed directly"):
            OCRConfidenceCalibrationError("caller-controlled message")

    def test_no_serialization_ranking_threshold_or_runtime_api(self) -> None:
        from capture_import import workflow_ocr_confidence_calibration as module

        forbidden = {
            "to_dict",
            "from_dict",
            "serialize",
            "save",
            "load",
            "rank",
            "winner",
            "threshold",
            "train",
            "fit",
            "refresh",
        }
        for name in module.__all__:
            with self.subTest(name=name):
                self.assertTrue(forbidden.isdisjoint(dir(getattr(module, name))))

    def test_import_boundary_is_pure(self) -> None:
        path = Path(
            "capture_import/workflow_ocr_confidence_calibration.py"
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_from = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        disallowed = {
            "os",
            "pathlib",
            "datetime",
            "uuid",
            "random",
            "logging",
            "asyncio",
            "numpy",
            "pandas",
            "sklearn",
            "scipy",
            "collection_management",
        }
        self.assertTrue(disallowed.isdisjoint(imports))
        self.assertFalse(
            any(
                any(token in module for token in disallowed)
                for module in imported_from
            )
        )
        self.assertFalse(
            any(
                token in (path.read_text(encoding="utf-8"))
                for token in (
                    "workflow_ocr_runtime",
                    "workflow_ocr_composition",
                    "legacy_ocr",
                    "desktop",
                )
            )
        )


class TestCalibrationPoint(unittest.TestCase):
    def test_valid_boundaries_and_immutability(self) -> None:
        value = point(0, 10_000)

        self.assertEqual(value.raw_confidence_bps, 0)
        self.assertEqual(value.calibrated_confidence_bps, 10_000)
        self.assertFalse(hasattr(value, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            value.raw_confidence_bps = 1  # type: ignore[misc]

    def test_rejects_wrong_and_out_of_range_values(self) -> None:
        for raw, calibrated in (
            (True, 0),
            (0.0, 0),
            (-1, 0),
            (10_001, 0),
            (0, True),
            (0, 1.0),
            (0, -1),
            (0, 10_001),
        ):
            with self.subTest(raw=raw, calibrated=calibrated):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    point(raw, calibrated)  # type: ignore[arg-type]


class TestCalibrationProfile(unittest.TestCase):
    def test_provider_fallback_and_field_scope_are_exact(self) -> None:
        fallback = profile()
        field = profile(
            "alpha-ocr-country-v1",
            field_name="country",
        )

        self.assertEqual(fallback.scope_key, ("alpha-ocr", None))
        self.assertEqual(field.scope_key, ("alpha-ocr", "country"))

    def test_identifier_boundaries(self) -> None:
        shortest = profile("a")
        longest = profile("a" + "1" * 127)

        self.assertEqual(shortest.profile_id, "a")
        self.assertEqual(len(longest.profile_id), 128)

    def test_rejects_malformed_profile_ids(self) -> None:
        invalid_values = (
            "",
            "Alpha",
            "1alpha",
            "../alpha",
            "https://alpha",
            "a" * 129,
            None,
            1,
        )
        for invalid in invalid_values:
            with self.subTest(invalid=invalid):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    profile(invalid)  # type: ignore[arg-type]

    def test_rejects_malformed_provider_and_field_scope(self) -> None:
        for provider_id, field_name in (
            ("Alpha", None),
            ("../alpha", None),
            ("alpha-ocr", "*"),
            ("alpha-ocr", "Country"),
            ("alpha-ocr", ""),
        ):
            with self.subTest(provider_id=provider_id, field_name=field_name):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    profile(
                        provider_id=provider_id,
                        field_name=field_name,
                    )

    def test_identity_and_nonlinear_profiles_are_valid(self) -> None:
        identity = profile()
        nonlinear = profile(
            points=(
                point(0, 0),
                point(5_000, 2_500),
                point(10_000, 10_000),
            )
        )

        self.assertEqual(calibrate_ocr_confidence_value(50, identity), 5_000)
        self.assertEqual(
            calibrate_ocr_confidence_value(50, nonlinear),
            2_500,
        )

    def test_completely_flat_profile_is_explicitly_allowed(self) -> None:
        flat = profile(
            points=(point(0, 4_000), point(10_000, 4_000))
        )

        self.assertEqual(calibrate_ocr_confidence_value(0, flat), 4_000)
        self.assertEqual(calibrate_ocr_confidence_value(50, flat), 4_000)
        self.assertEqual(calibrate_ocr_confidence_value(100, flat), 4_000)

    def test_points_must_be_tuple_with_two_values(self) -> None:
        for invalid in (
            [],
            (),
            (point(0, 0),),
            (object(), point(10_000, 10_000)),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    profile(points=invalid)  # type: ignore[arg-type]

    def test_points_must_cover_complete_raw_scale(self) -> None:
        for points in (
            (point(1, 0), point(10_000, 10_000)),
            (point(0, 0), point(9_999, 10_000)),
        ):
            with self.subTest(points=points):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    profile(points=points)

    def test_raw_points_must_be_strictly_increasing(self) -> None:
        for points in (
            (point(0, 0), point(5_000, 5_000), point(5_000, 6_000), point(10_000, 10_000)),
            (point(0, 0), point(7_000, 7_000), point(5_000, 8_000), point(10_000, 10_000)),
        ):
            with self.subTest(points=points):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    profile(points=points)

    def test_calibrated_points_must_be_nondecreasing(self) -> None:
        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            profile(
                points=(
                    point(0, 0),
                    point(5_000, 8_000),
                    point(10_000, 7_000),
                )
            )

    def test_profile_is_frozen_slotted_and_tuple_backed(self) -> None:
        value = profile()

        self.assertIsInstance(value.points, tuple)
        self.assertFalse(hasattr(value, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            value.profile_id = "other-v1"  # type: ignore[misc]


class TestCalibrationRegistry(unittest.TestCase):
    def test_canonical_order_field_profiles_before_fallback(self) -> None:
        country = profile(
            "alpha-country-v1",
            field_name="country",
        )
        year = profile(
            "alpha-year-v1",
            field_name="year",
        )
        fallback = profile()
        beta = profile(
            "beta-default-v1",
            provider_id="beta-ocr",
        )

        value = registry(country, year, fallback, beta)

        self.assertEqual(
            tuple(item.profile_id for item in value.profiles),
            (
                "alpha-country-v1",
                "alpha-year-v1",
                "alpha-ocr-default-v1",
                "beta-default-v1",
            ),
        )

    def test_registry_rejects_empty_non_tuple_and_wrong_items(self) -> None:
        for invalid in ((), [], (object(),)):
            with self.subTest(invalid=invalid):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    OCRConfidenceCalibrationRegistry(
                        invalid  # type: ignore[arg-type]
                    )

    def test_registry_rejects_duplicate_profile_id(self) -> None:
        first = profile()
        duplicate = profile(
            first.profile_id,
            provider_id="beta-ocr",
        )

        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            registry(first, duplicate)

    def test_registry_rejects_duplicate_scope_in_final_position(self) -> None:
        first = profile()
        beta = profile(
            "beta-default-v1",
            provider_id="beta-ocr",
        )
        duplicate = profile("alpha-other-v1")

        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            registry(first, beta, duplicate)

    def test_registry_rejects_reversed_order_without_sorting(self) -> None:
        alpha = profile()
        beta = profile(
            "beta-default-v1",
            provider_id="beta-ocr",
        )

        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            registry(beta, alpha)

    def test_registry_rejects_reversed_fields_and_misplaced_fallback(self) -> None:
        country = profile("alpha-country-v1", field_name="country")
        year = profile("alpha-year-v1", field_name="year")
        fallback = profile()
        for profiles in (
            (year, country, fallback),
            (fallback, country, year),
        ):
            with self.subTest(profiles=profiles):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    registry(*profiles)

    def test_registry_rejects_final_position_duplicate_profile_id(self) -> None:
        alpha = profile()
        beta = profile(
            "beta-default-v1",
            provider_id="beta-ocr",
        )
        duplicate_id = profile(
            alpha.profile_id,
            provider_id="charlie-ocr",
        )

        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            registry(alpha, beta, duplicate_id)

    def test_registry_wraps_malformed_nested_profile(self) -> None:
        malformed = profile()
        object.__setattr__(malformed, "profile_id", "INVALID")

        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            registry(malformed)

    def test_registry_is_frozen_slotted_and_identity_preserving(self) -> None:
        item = profile()
        value = registry(item)

        self.assertIs(value.profiles[0], item)
        self.assertFalse(hasattr(value, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            value.profiles = ()  # type: ignore[misc]


class TestProfileLookup(unittest.TestCase):
    def setUp(self) -> None:
        self.country = profile(
            "alpha-country-v1",
            field_name="country",
        )
        self.fallback = profile()
        self.registry = registry(self.country, self.fallback)

    def test_field_profile_precedes_provider_fallback(self) -> None:
        actual = resolve_ocr_confidence_calibration_profile(
            self.registry,
            "alpha-ocr",
            "country",
        )

        self.assertIs(actual, self.country)

    def test_provider_fallback_is_exact_identity(self) -> None:
        actual = resolve_ocr_confidence_calibration_profile(
            self.registry,
            "alpha-ocr",
            "year",
        )

        self.assertIs(actual, self.fallback)

    def test_unknown_provider_and_missing_field_fail_typed(self) -> None:
        only_field = registry(self.country)
        for source, provider_id, field_name in (
            (self.registry, "beta-ocr", "country"),
            (only_field, "alpha-ocr", "year"),
        ):
            with self.subTest(provider_id=provider_id, field_name=field_name):
                with self.assertRaises(
                    OCRConfidenceCalibrationProfileNotFoundError
                ) as caught:
                    resolve_ocr_confidence_calibration_profile(
                        source,
                        provider_id,
                        field_name,
                    )
                self.assertEqual(caught.exception.provider_id, provider_id)
                self.assertEqual(caught.exception.field_name, field_name)
                self.assertEqual(vars(caught.exception), {})
                with self.assertRaisesRegex(AttributeError, "immutable"):
                    caught.exception.provider_id = "other-ocr"  # type: ignore[misc]

    def test_lookup_is_case_sensitive_and_has_no_global_fallback(self) -> None:
        for provider_id, field_name in (
            ("Alpha-ocr", "country"),
            ("alpha-ocr", "Country"),
            ("*", "country"),
        ):
            with self.subTest(provider_id=provider_id, field_name=field_name):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    resolve_ocr_confidence_calibration_profile(
                        self.registry,
                        provider_id,
                        field_name,
                    )

    def test_lookup_rejects_wrong_registry_type(self) -> None:
        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            resolve_ocr_confidence_calibration_profile(
                object(),  # type: ignore[arg-type]
                "alpha-ocr",
                "country",
            )


class TestInterpolation(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = profile()
        self.nonlinear = profile(
            points=(
                point(0, 0),
                point(2_500, 1_000),
                point(5_000, 4_000),
                point(10_000, 10_000),
            )
        )

    def test_identity_boundaries_midpoint_and_fraction(self) -> None:
        cases = (
            (0, 0),
            (100, 10_000),
            (50, 5_000),
            (87.25, 8_725),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(
                    calibrate_ocr_confidence_value(raw, self.identity),
                    expected,
                )

    def test_authoritative_decimal_conversion_boundaries(self) -> None:
        cases = (
            (0.01, 1),
            (0.005, 1),
            (0.1, 10),
            (0.29, 29),
            (12.345, 1_235),
            (99.994, 9_999),
            (99.995, 10_000),
            (5e-324, 0),
            (99.99999999999999, 10_000),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(
                    calibrate_ocr_confidence_value(raw, self.identity),
                    expected,
                )

    def test_raw_conversion_rounds_half_up_to_source_basis_point(self) -> None:
        self.assertEqual(
            calibrate_ocr_confidence_value(1.234, self.identity),
            123,
        )
        self.assertEqual(
            calibrate_ocr_confidence_value(1.235, self.identity),
            124,
        )

    def test_piecewise_exact_points_and_multiple_segments(self) -> None:
        cases = (
            (0, 0),
            (25, 1_000),
            (50, 4_000),
            (100, 10_000),
            (37.5, 2_500),
            (75, 7_000),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(
                    calibrate_ocr_confidence_value(raw, self.nonlinear),
                    expected,
                )

    def test_interpolation_rounds_non_even_division_half_up(self) -> None:
        unusual = profile(
            points=(
                point(0, 0),
                point(3, 2),
                point(10_000, 10_000),
            )
        )

        self.assertEqual(
            calibrate_ocr_confidence_value(0.01, unusual),
            1,
        )
        self.assertEqual(
            calibrate_ocr_confidence_value(0.02, unusual),
            1,
        )

    def test_large_integer_products_are_exact_and_deterministic(self) -> None:
        mapping = profile(
            points=(
                point(0, 0),
                point(9_999, 9_998),
                point(10_000, 10_000),
            )
        )

        results = tuple(
            calibrate_ocr_confidence_value(99.98, mapping)
            for _ in range(20)
        )

        self.assertEqual(len(set(results)), 1)
        self.assertEqual(results[0], 9_997)

    def test_invalid_raw_inputs_raise_typed_input_error(self) -> None:
        invalid_values = (
            True,
            -1,
            101,
            float("nan"),
            float("inf"),
            float("-inf"),
            Decimal("50"),
            "50",
            None,
        )
        for invalid in invalid_values:
            with self.subTest(invalid=invalid):
                with self.assertRaises(OCRConfidenceCalibrationInputError):
                    calibrate_ocr_confidence_value(invalid, self.identity)

    def test_input_error_has_bounded_immutable_attributes(self) -> None:
        with self.assertRaises(OCRConfidenceCalibrationInputError) as caught:
            calibrate_ocr_confidence_value(None, self.identity)

        error = caught.exception
        self.assertEqual(error.provider_id, "alpha-ocr")
        self.assertIsNone(error.field_name)
        self.assertEqual(error.profile_id, "alpha-ocr-default-v1")
        self.assertEqual(vars(error), {})
        with self.assertRaisesRegex(AttributeError, "immutable"):
            error.profile_id = "other-v1"  # type: ignore[misc]


class TestCandidateCalibration(unittest.TestCase):
    def setUp(self) -> None:
        self.batch = one_candidate_batch(confidence=87.25)
        self.profile = profile()
        self.registry = registry(self.profile)
        self.result = calibrate_ocr_execution_confidence(
            self.batch,
            self.registry,
        )
        self.evidence = self.result.candidates[0]

    def test_exact_source_and_profile_identities_are_retained(self) -> None:
        outcome = self.batch.outcomes[0]
        candidate = outcome.report.candidates[0]

        self.assertIs(self.evidence.provider, outcome.capabilities)
        self.assertIs(self.evidence.report, outcome.report)
        self.assertIs(self.evidence.candidate, candidate)
        self.assertIs(self.evidence.profile, self.profile)
        self.assertEqual(self.evidence.raw_confidence, 87.25)
        self.assertEqual(self.evidence.calibrated_confidence_bps, 8_725)

    def test_raw_integer_and_float_types_are_preserved_exactly(self) -> None:
        integer_result = calibrate_ocr_execution_confidence(
            one_candidate_batch(confidence=50),  # type: ignore[arg-type]
            self.registry,
        )
        float_result = calibrate_ocr_execution_confidence(
            one_candidate_batch(confidence=50.0),
            self.registry,
        )

        self.assertIs(type(integer_result.candidates[0].raw_confidence), int)
        self.assertIs(type(float_result.candidates[0].raw_confidence), float)
        self.assertEqual(
            integer_result.candidates[0].calibrated_confidence_bps,
            float_result.candidates[0].calibrated_confidence_bps,
        )

    def test_derived_identifiers_are_exact(self) -> None:
        self.assertEqual(self.evidence.provider_id, "alpha-ocr")
        self.assertEqual(self.evidence.field_name, "country")
        self.assertEqual(
            self.evidence.profile_id,
            "alpha-ocr-default-v1",
        )

    def test_candidate_evidence_is_frozen_and_slotted(self) -> None:
        self.assertFalse(hasattr(self.evidence, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            self.evidence.calibrated_confidence_bps = 0  # type: ignore[misc]

    def test_field_specific_profile_overrides_fallback(self) -> None:
        field_profile = profile(
            "alpha-country-v1",
            field_name="country",
            points=(point(0, 0), point(10_000, 5_000)),
        )
        source = registry(field_profile, self.profile)

        result = calibrate_ocr_execution_confidence(self.batch, source)

        self.assertIs(result.candidates[0].profile, field_profile)
        self.assertEqual(
            result.candidates[0].calibrated_confidence_bps,
            4_363,
        )

    def test_direct_reconstruction_rejects_foreign_provider(self) -> None:
        foreign = fx.capabilities("beta-ocr")

        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            OCRCalibratedCandidateConfidence(
                provider=foreign,
                report=self.evidence.report,
                candidate=self.evidence.candidate,
                profile=self.evidence.profile,
                raw_confidence=self.evidence.raw_confidence,
                calibrated_confidence_bps=(
                    self.evidence.calibrated_confidence_bps
                ),
            )

    def test_direct_reconstruction_rejects_foreign_report(self) -> None:
        foreign_report = fx.report(
            "alpha-ocr",
            fx.candidate(
                "alpha-ocr",
                confidence=87.25,
            ),
        )

        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            OCRCalibratedCandidateConfidence(
                provider=self.evidence.provider,
                report=foreign_report,
                candidate=self.evidence.candidate,
                profile=self.evidence.profile,
                raw_confidence=self.evidence.raw_confidence,
                calibrated_confidence_bps=(
                    self.evidence.calibrated_confidence_bps
                ),
            )

    def test_direct_reconstruction_rejects_equal_distinct_candidate(self) -> None:
        original = self.evidence.candidate
        duplicate = OCRFieldCandidate(
            source_coin_id=original.source_coin_id,
            image_role=original.image_role,
            artifact_key=original.artifact_key,
            provider_id=original.provider_id,
            field_name=original.field_name,
            raw_text=original.raw_text,
            normalized_value=original.normalized_value,
            confidence_score=original.confidence_score,
            evidence=original.evidence,
            review_status=original.review_status,
        )

        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            OCRCalibratedCandidateConfidence(
                provider=self.evidence.provider,
                report=self.evidence.report,
                candidate=duplicate,
                profile=self.evidence.profile,
                raw_confidence=self.evidence.raw_confidence,
                calibrated_confidence_bps=(
                    self.evidence.calibrated_confidence_bps
                ),
            )

    def test_direct_reconstruction_rejects_wrong_profile_scope(self) -> None:
        wrong_provider = profile(
            "beta-default-v1",
            provider_id="beta-ocr",
        )
        wrong_field = profile(
            "alpha-year-v1",
            field_name="year",
        )
        for invalid in (wrong_provider, wrong_field):
            with self.subTest(profile=invalid.profile_id):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    OCRCalibratedCandidateConfidence(
                        provider=self.evidence.provider,
                        report=self.evidence.report,
                        candidate=self.evidence.candidate,
                        profile=invalid,
                        raw_confidence=self.evidence.raw_confidence,
                        calibrated_confidence_bps=(
                            self.evidence.calibrated_confidence_bps
                        ),
                    )

    def test_direct_reconstruction_rejects_wrong_raw_and_calibrated_values(
        self,
    ) -> None:
        cases = (
            (87, 8_725),
            (87.25, 8_724),
            (87.25, True),
            (87.25, 10_001),
        )
        for raw, calibrated in cases:
            with self.subTest(raw=raw, calibrated=calibrated):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    OCRCalibratedCandidateConfidence(
                        provider=self.evidence.provider,
                        report=self.evidence.report,
                        candidate=self.evidence.candidate,
                        profile=self.evidence.profile,
                        raw_confidence=raw,
                        calibrated_confidence_bps=calibrated,
                    )


class TestBatchCalibration(unittest.TestCase):
    def test_multiple_providers_and_candidates_preserve_evidence_order(self) -> None:
        batch = make_batch(
            (
                "alpha-ocr",
                (
                    ("country", "Canada", 20.0),
                    ("year", "1967", 80.0),
                ),
            ),
            (
                "beta-ocr",
                (("country", "Canada", 60.0),),
            ),
        )
        source = registry(
            profile(),
            profile("beta-default-v1", provider_id="beta-ocr"),
        )

        result = calibrate_ocr_execution_confidence(batch, source)

        self.assertEqual(
            tuple(item.provider_id for item in result.candidates),
            ("alpha-ocr", "alpha-ocr", "beta-ocr"),
        )
        self.assertEqual(
            tuple(item.field_name for item in result.candidates),
            ("country", "year", "country"),
        )
        expected_candidates = tuple(
            candidate
            for outcome in batch.successful_outcomes
            for candidate in outcome.report.candidates
        )
        self.assertTrue(
            all(
                actual.candidate is expected
                for actual, expected in zip(
                    result.candidates,
                    expected_candidates,
                    strict=True,
                )
            )
        )

    def test_failed_outcomes_are_omitted_without_profile(self) -> None:
        batch = make_batch(
            (
                "alpha-ocr",
                (("country", "Canada", 50.0),),
            ),
            (
                "beta-ocr",
                OCRProviderExecutionError("beta-ocr", "ENGINE_FAILED"),
            ),
        )

        result = calibrate_ocr_execution_confidence(
            batch,
            registry(profile()),
        )

        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].provider_id, "alpha-ocr")

    def test_all_failed_providers_yield_empty_calibration(self) -> None:
        batch = make_batch(
            (
                "alpha-ocr",
                OCRProviderExecutionError("alpha-ocr", "ENGINE_FAILED"),
            ),
            (
                "beta-ocr",
                OCRProviderExecutionError("beta-ocr", "ENGINE_FAILED"),
            ),
        )

        result = calibrate_ocr_execution_confidence(
            batch,
            registry(profile()),
        )

        self.assertEqual(result.candidates, ())

    def test_successful_empty_report_yields_empty_calibration(self) -> None:
        batch = make_batch(("alpha-ocr", ()))

        result = calibrate_ocr_execution_confidence(
            batch,
            registry(profile()),
        )

        self.assertEqual(result.candidates, ())

    def test_missing_profile_fails_complete_coverage(self) -> None:
        batch = make_batch(
            (
                "alpha-ocr",
                (
                    ("country", "Canada", 50.0),
                    ("year", "1967", 50.0),
                ),
            )
        )
        source = registry(
            profile(
                "alpha-country-v1",
                field_name="country",
            )
        )

        with self.assertRaises(
            OCRConfidenceCalibrationCoverageError
        ) as caught:
            calibrate_ocr_execution_confidence(batch, source)

        self.assertEqual(caught.exception.provider_id, "alpha-ocr")
        self.assertEqual(caught.exception.field_name, "year")
        self.assertEqual(vars(caught.exception), {})
        with self.assertRaisesRegex(AttributeError, "immutable"):
            caught.exception.field_name = "country"  # type: ignore[misc]

    def test_second_provider_missing_profile_fails_atomically(self) -> None:
        batch = make_batch(
            (
                "alpha-ocr",
                (("country", "Canada", 50.0),),
            ),
            (
                "beta-ocr",
                (("country", "Canada", 50.0),),
            ),
        )

        with self.assertRaises(OCRConfidenceCalibrationCoverageError):
            calibrate_ocr_execution_confidence(
                batch,
                registry(profile()),
            )

        self.assertEqual(
            tuple(
                candidate.confidence_score
                for outcome in batch.successful_outcomes
                for candidate in outcome.report.candidates
            ),
            (50.0, 50.0),
        )

    def test_field_specific_and_fallback_coverage_combines(self) -> None:
        batch = make_batch(
            (
                "alpha-ocr",
                (
                    ("country", "Canada", 50.0),
                    ("year", "1967", 50.0),
                ),
            )
        )
        country = profile(
            "alpha-country-v1",
            field_name="country",
            points=(point(0, 0), point(10_000, 5_000)),
        )
        fallback = profile()

        result = calibrate_ocr_execution_confidence(
            batch,
            registry(country, fallback),
        )

        self.assertEqual(
            tuple(item.profile_id for item in result.candidates),
            ("alpha-country-v1", "alpha-ocr-default-v1"),
        )

    def test_batch_and_registry_identity_are_retained(self) -> None:
        batch = one_candidate_batch()
        source = registry(profile())

        result = calibrate_ocr_execution_confidence(batch, source)

        self.assertIs(result.batch, batch)
        self.assertIs(result.registry, source)
        self.assertFalse(hasattr(result, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            result.candidates = ()  # type: ignore[misc]

    def test_wrong_batch_or_registry_type_fails_typed(self) -> None:
        batch = one_candidate_batch()
        for invalid_batch, invalid_registry in (
            (object(), registry(profile())),
            (batch, object()),
        ):
            with self.subTest(
                batch=type(invalid_batch).__name__,
                registry=type(invalid_registry).__name__,
            ):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    calibrate_ocr_execution_confidence(
                        invalid_batch,  # type: ignore[arg-type]
                        invalid_registry,  # type: ignore[arg-type]
                    )

    def test_result_rejects_non_tuple_missing_and_extra_candidates(self) -> None:
        batch = one_candidate_batch()
        source = registry(profile())
        valid = calibrate_ocr_execution_confidence(batch, source)
        for candidates in (
            [],
            (),
            valid.candidates + valid.candidates,
        ):
            with self.subTest(candidates=candidates):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    OCRCalibratedExecutionConfidence(
                        batch=batch,
                        registry=source,
                        candidates=candidates,  # type: ignore[arg-type]
                    )

    def test_result_rejects_wrong_order_and_foreign_candidate(self) -> None:
        batch = make_batch(
            (
                "alpha-ocr",
                (
                    ("country", "Canada", 20.0),
                    ("year", "1967", 80.0),
                ),
            )
        )
        source = registry(profile())
        valid = calibrate_ocr_execution_confidence(batch, source)
        foreign = calibrate_ocr_execution_confidence(
            one_candidate_batch(confidence=20.0),
            registry(profile()),
        ).candidates[0]
        for candidates in (
            tuple(reversed(valid.candidates)),
            (foreign, valid.candidates[1]),
        ):
            with self.subTest(candidates=candidates):
                with self.assertRaises(
                    InvalidOCRConfidenceCalibrationContextError
                ):
                    OCRCalibratedExecutionConfidence(
                        batch=batch,
                        registry=source,
                        candidates=candidates,
                    )

    def test_result_rejects_equal_distinct_profile_from_registry(self) -> None:
        batch = one_candidate_batch()
        registered = profile()
        source = registry(registered)
        valid = calibrate_ocr_execution_confidence(batch, source)
        duplicate = profile()
        forged = OCRCalibratedCandidateConfidence(
            provider=valid.candidates[0].provider,
            report=valid.candidates[0].report,
            candidate=valid.candidates[0].candidate,
            profile=duplicate,
            raw_confidence=valid.candidates[0].raw_confidence,
            calibrated_confidence_bps=(
                valid.candidates[0].calibrated_confidence_bps
            ),
        )

        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            OCRCalibratedExecutionConfidence(
                batch=batch,
                registry=source,
                candidates=(forged,),
            )

    def test_result_rejects_equal_distinct_capability(self) -> None:
        batch = one_candidate_batch()
        source = registry(profile())
        valid = calibrate_ocr_execution_confidence(batch, source)
        forged_provider = fx.capabilities("alpha-ocr")
        forged = OCRCalibratedCandidateConfidence(
            provider=forged_provider,
            report=valid.candidates[0].report,
            candidate=valid.candidates[0].candidate,
            profile=valid.candidates[0].profile,
            raw_confidence=valid.candidates[0].raw_confidence,
            calibrated_confidence_bps=(
                valid.candidates[0].calibrated_confidence_bps
            ),
        )

        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            OCRCalibratedExecutionConfidence(
                batch=batch,
                registry=source,
                candidates=(forged,),
            )

    def test_repeated_calibration_is_equal_and_identity_preserving(self) -> None:
        batch = one_candidate_batch(confidence=12.345)
        source = registry(profile())

        first = calibrate_ocr_execution_confidence(batch, source)
        second = calibrate_ocr_execution_confidence(batch, source)

        self.assertEqual(first, second)
        self.assertIs(first.batch, second.batch)
        self.assertIs(first.registry, second.registry)
        self.assertIs(
            first.candidates[0].candidate,
            second.candidates[0].candidate,
        )
        self.assertIs(
            first.candidates[0].profile,
            second.candidates[0].profile,
        )


class TestConfidenceEnsembleIsolation(unittest.TestCase):
    def test_two_low_confidence_equal_values_remain_consensus(self) -> None:
        batch = make_batch(
            (
                "alpha-ocr",
                (("country", "Canada", 1.0),),
            ),
            (
                "beta-ocr",
                (("country", "Canada", 2.0),),
            ),
        )
        ensemble = compare_ocr_provider_outcomes(batch)
        source = registry(
            profile(),
            profile("beta-default-v1", provider_id="beta-ocr"),
        )

        calibrated = calibrate_ocr_execution_confidence(batch, source)

        self.assertEqual(
            ensemble.fields[0].status,
            OCRProviderEnsembleFieldStatus.CONSENSUS,
        )
        self.assertIs(calibrated.batch, ensemble.batch)
        self.assertIs(
            ensemble.fields[0].evidence[0].candidates[0],
            calibrated.candidates[0].candidate,
        )

    def test_high_confidence_different_value_remains_conflict(self) -> None:
        batch = make_batch(
            (
                "alpha-ocr",
                (("country", "Canada", 1.0),),
            ),
            (
                "beta-ocr",
                (("country", "CANADA", 99.0),),
            ),
        )
        ensemble = compare_ocr_provider_outcomes(batch)
        source = registry(
            profile(),
            profile("beta-default-v1", provider_id="beta-ocr"),
        )

        calibrate_ocr_execution_confidence(batch, source)

        self.assertEqual(
            ensemble.fields[0].status,
            OCRProviderEnsembleFieldStatus.CONFLICT,
        )
        self.assertIsNone(ensemble.fields[0].consensus_value)

    def test_low_agreement_plus_high_difference_remains_conflict(self) -> None:
        batch = make_batch(
            ("alpha-ocr", (("country", "Canada", 1.0),)),
            ("beta-ocr", (("country", "Canada", 2.0),)),
            ("charlie-ocr", (("country", "CANADA", 99.0),)),
        )
        ensemble = compare_ocr_provider_outcomes(batch)

        calibrate_ocr_execution_confidence(
            batch,
            registry(
                profile(),
                profile("beta-default-v1", provider_id="beta-ocr"),
                profile(
                    "charlie-default-v1",
                    provider_id="charlie-ocr",
                ),
            ),
        )

        self.assertEqual(
            ensemble.fields[0].status,
            OCRProviderEnsembleFieldStatus.CONFLICT,
        )

    def test_high_confidence_single_source_remains_single_source(self) -> None:
        batch = make_batch(
            ("alpha-ocr", (("country", "Canada", 99.0),)),
            ("beta-ocr", ()),
        )
        ensemble = compare_ocr_provider_outcomes(batch)

        calibrate_ocr_execution_confidence(
            batch,
            registry(
                profile(),
                profile("beta-default-v1", provider_id="beta-ocr"),
            ),
        )

        self.assertEqual(
            ensemble.fields[0].status,
            OCRProviderEnsembleFieldStatus.SINGLE_SOURCE,
        )

    def test_low_confidence_single_source_remains_single_source(self) -> None:
        batch = make_batch(
            (
                "alpha-ocr",
                (("country", "Canada", 1.0),),
            ),
            ("beta-ocr", ()),
        )
        ensemble = compare_ocr_provider_outcomes(batch)

        calibrate_ocr_execution_confidence(
            batch,
            registry(
                profile(),
                profile("beta-default-v1", provider_id="beta-ocr"),
            ),
        )

        self.assertEqual(
            ensemble.fields[0].status,
            OCRProviderEnsembleFieldStatus.SINGLE_SOURCE,
        )

    def test_calibration_does_not_filter_values_or_select_winner(self) -> None:
        batch = make_batch(
            (
                "alpha-ocr",
                (("country", "Canada", 1.0),),
            ),
            (
                "beta-ocr",
                (("country", "CANADA", 99.0),),
            ),
        )
        source = registry(
            profile(
                points=(point(0, 0), point(10_000, 1_000))
            ),
            profile(
                "beta-default-v1",
                provider_id="beta-ocr",
                points=(point(0, 9_000), point(10_000, 10_000)),
            ),
        )

        result = calibrate_ocr_execution_confidence(batch, source)

        self.assertEqual(len(result.candidates), 2)
        self.assertEqual(
            tuple(
                item.candidate.normalized_value
                for item in result.candidates
            ),
            ("Canada", "CANADA"),
        )
        self.assertFalse(
            any(
                hasattr(result, name)
                for name in (
                    "winner",
                    "selected_candidate",
                    "threshold",
                    "rank",
                )
            )
        )

    def test_no_observation_and_all_failed_statuses_remain_unchanged(self) -> None:
        no_observation_batch = make_batch(
            ("alpha-ocr", ()),
            required_fields=("country",),
        )
        all_failed_batch = make_batch(
            (
                "alpha-ocr",
                OCRProviderExecutionError("alpha-ocr", "ENGINE_FAILED"),
            ),
            required_fields=("country",),
        )
        no_observation = compare_ocr_provider_outcomes(no_observation_batch)
        all_failed = compare_ocr_provider_outcomes(all_failed_batch)
        source = registry(profile())

        calibrate_ocr_execution_confidence(no_observation_batch, source)
        calibrate_ocr_execution_confidence(all_failed_batch, source)

        self.assertEqual(
            no_observation.fields[0].status,
            OCRProviderEnsembleFieldStatus.NO_OBSERVATION,
        )
        self.assertEqual(
            all_failed.fields[0].status,
            OCRProviderEnsembleFieldStatus.ALL_PROVIDERS_FAILED,
        )


class TestMalformedBatchReconstruction(unittest.TestCase):
    def test_malformed_nested_batch_is_wrapped(self) -> None:
        batch = one_candidate_batch()
        object.__setattr__(batch, "outcomes", ())

        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            calibrate_ocr_execution_confidence(
                batch,
                registry(profile()),
            )

    def test_invalid_candidate_confidence_is_wrapped_by_batch_boundary(self) -> None:
        batch = one_candidate_batch()
        candidate = batch.outcomes[0].report.candidates[0]
        object.__setattr__(candidate, "confidence_score", float("nan"))

        with self.assertRaises(
            InvalidOCRConfidenceCalibrationContextError
        ):
            calibrate_ocr_execution_confidence(
                batch,
                registry(profile()),
            )

    def test_failed_outcome_cannot_be_forged_into_successful_calibration(
        self,
    ) -> None:
        batch = one_candidate_batch()
        outcome = batch.outcomes[0]
        forged = OCRProviderExecutionOutcome(
            capabilities=outcome.capabilities,
            status=OCRProviderExecutionStatus.FAILED,
            report=None,
            failure_category=OCRProviderFailureCategory.EXECUTION,
            diagnostic_code="ENGINE_FAILED",
        )
        malformed = OCRProviderExecutionBatch(
            selection=batch.selection,
            request=batch.request,
            outcomes=(forged,),
        )

        result = calibrate_ocr_execution_confidence(
            malformed,
            registry(profile()),
        )

        self.assertEqual(result.candidates, ())


if __name__ == "__main__":
    unittest.main()
