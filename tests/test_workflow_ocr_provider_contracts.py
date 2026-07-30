"""Focused tests for Sprint 16 Unit 1A OCR provider contracts."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import inspect
import unittest

from capture_import.enums import ImageRole
from capture_import.workflow_ocr_models import ALLOWED_OCR_FIELDS
import capture_import.workflow_ocr_provider_contracts as contracts
from capture_import.workflow_ocr_provider_contracts import (
    InvalidOCRProviderContractError,
    OCRProviderAvailability,
    OCRProviderCapabilities,
    OCRProviderCleanupError,
    OCRProviderContractError,
    OCRProviderError,
    OCRProviderExecutionError,
    OCRProviderFieldSupportMode,
    OCRProviderInputError,
    OCRProviderOutputError,
    OCRProviderUnavailableError,
)


PUBLIC_API = [
    "OCRProviderContractError",
    "InvalidOCRProviderContractError",
    "OCRProviderError",
    "OCRProviderUnavailableError",
    "OCRProviderInputError",
    "OCRProviderExecutionError",
    "OCRProviderOutputError",
    "OCRProviderCleanupError",
    "OCRProviderAvailability",
    "OCRProviderFieldSupportMode",
    "OCRProviderCapabilities",
]

LEGACY_FIELDS = (
    "banknote_prefix",
    "certification_number",
    "country",
    "denomination",
    "year",
)


def _capabilities(
    *,
    provider_id: object = "legacy-ocr",
    availability: object = OCRProviderAvailability.AVAILABLE,
    roles: object = (
        ImageRole.FRONT,
        ImageRole.REVERSE,
        ImageRole.EDGE,
    ),
    media_types: object = ("image/jpeg",),
    field_mode: object = OCRProviderFieldSupportMode.DECLARED,
    fields: object = LEGACY_FIELDS,
) -> OCRProviderCapabilities:
    return OCRProviderCapabilities(
        provider_id=provider_id,  # type: ignore[arg-type]
        availability=availability,  # type: ignore[arg-type]
        supported_image_roles=roles,  # type: ignore[arg-type]
        supported_media_types=media_types,  # type: ignore[arg-type]
        field_support_mode=field_mode,  # type: ignore[arg-type]
        supported_fields=fields,  # type: ignore[arg-type]
    )


class PublicAPIAndHierarchyTests(unittest.TestCase):
    def test_exact_public_api(self) -> None:
        self.assertEqual(contracts.__all__, PUBLIC_API)
        for name in PUBLIC_API:
            self.assertTrue(hasattr(contracts, name), name)

    def test_contract_error_hierarchy_is_separate_from_runtime_errors(
        self,
    ) -> None:
        self.assertTrue(issubclass(OCRProviderContractError, ValueError))
        self.assertTrue(
            issubclass(
                InvalidOCRProviderContractError,
                OCRProviderContractError,
            )
        )
        self.assertFalse(issubclass(OCRProviderContractError, OCRProviderError))
        self.assertFalse(issubclass(OCRProviderError, ValueError))

    def test_runtime_error_hierarchy_is_exact(self) -> None:
        expected = (
            OCRProviderUnavailableError,
            OCRProviderInputError,
            OCRProviderExecutionError,
            OCRProviderOutputError,
            OCRProviderCleanupError,
        )
        for error_type in expected:
            with self.subTest(error_type=error_type.__name__):
                self.assertIs(error_type.__base__, OCRProviderError)

    def test_no_registry_selection_ensemble_or_calibration_api(self) -> None:
        forbidden_fragments = (
            "Registry",
            "Selection",
            "Ensemble",
            "Calibration",
            "Priority",
            "Reporter",
        )
        self.assertFalse(
            any(
                fragment in name
                for name in contracts.__all__
                for fragment in forbidden_fragments
            )
        )

    def test_contracts_have_no_serialization_or_refresh_api(self) -> None:
        capabilities = _capabilities()
        for name in (
            "to_dict",
            "from_dict",
            "serialize",
            "deserialize",
            "save",
            "load",
            "refresh",
        ):
            self.assertFalse(hasattr(capabilities, name), name)

class ProviderIdentityTests(unittest.TestCase):
    def test_valid_provider_ids(self) -> None:
        for provider_id in (
            "a",
            "legacy-ocr",
            "provider_1",
            "provider.family",
            "provider-v2.1",
            "a" + ("0" * 127),
        ):
            with self.subTest(provider_id=provider_id):
                self.assertEqual(
                    _capabilities(provider_id=provider_id).provider_id,
                    provider_id,
                )

    def test_invalid_provider_id_types(self) -> None:
        for value in (None, 1, True, b"legacy-ocr", object()):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(provider_id=value)

    def test_empty_whitespace_and_uppercase_provider_ids_fail(self) -> None:
        for value in ("", " ", "legacy ocr", "Legacy-ocr", "LEGACY"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(provider_id=value)

    def test_path_url_and_invalid_punctuation_provider_ids_fail(self) -> None:
        for value in (
            "/legacy-ocr",
            r"legacy\ocr",
            "https://ocr",
            "legacy:ocr",
            "legacy@ocr",
            ".legacy",
            "-legacy",
        ):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(provider_id=value)

    def test_overlong_provider_id_fails(self) -> None:
        with self.assertRaises(InvalidOCRProviderContractError):
            _capabilities(provider_id="a" * 129)

class DiagnosticCodeAndRuntimeErrorTests(unittest.TestCase):
    ERROR_TYPES = (
        OCRProviderError,
        OCRProviderUnavailableError,
        OCRProviderInputError,
        OCRProviderExecutionError,
        OCRProviderOutputError,
        OCRProviderCleanupError,
    )

    def test_valid_diagnostic_codes(self) -> None:
        for code in (
            "A",
            "ENGINE_FAILURE",
            "UNSUPPORTED_MEDIA_TYPE",
            "A" + ("0" * 63),
        ):
            with self.subTest(code=code):
                error = OCRProviderExecutionError("legacy-ocr", code)
                self.assertEqual(error.diagnostic_code, code)

    def test_invalid_diagnostic_code_types(self) -> None:
        for value in (None, 1, True, b"FAIL", object()):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    OCRProviderExecutionError(
                        "legacy-ocr",
                        value,  # type: ignore[arg-type]
                    )

    def test_invalid_diagnostic_code_text_fails(self) -> None:
        for value in (
            "",
            " ",
            "engine_failure",
            "ENGINE FAILURE",
            "ENGINE-FAILURE",
            "_ENGINE_FAILURE",
            "A" * 65,
        ):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    OCRProviderExecutionError("legacy-ocr", value)

    def test_all_runtime_errors_retain_only_bounded_identity(self) -> None:
        for error_type in self.ERROR_TYPES:
            with self.subTest(error_type=error_type.__name__):
                error = error_type("legacy-ocr", "ENGINE_FAILURE")
                self.assertEqual(error.provider_id, "legacy-ocr")
                self.assertEqual(error.diagnostic_code, "ENGINE_FAILURE")
                self.assertEqual(
                    set(vars(error)),
                    set(),
                )

    def test_runtime_error_attributes_are_immutable(self) -> None:
        error = OCRProviderExecutionError("legacy-ocr", "ENGINE_FAILURE")
        for name, value in (
            ("provider_id", "changed"),
            ("diagnostic_code", "CHANGED"),
            ("metadata", {"secret": "value"}),
            ("args", ("changed",)),
        ):
            with self.subTest(name=name):
                with self.assertRaises(AttributeError):
                    setattr(error, name, value)

    def test_error_messages_are_deterministic_and_sanitized(self) -> None:
        cases = (
            (
                OCRProviderUnavailableError,
                "OCR provider 'legacy-ocr' is unavailable "
                "(DEPENDENCY_UNAVAILABLE).",
            ),
            (
                OCRProviderInputError,
                "OCR provider 'legacy-ocr' rejected its input "
                "(UNSUPPORTED_MEDIA_TYPE).",
            ),
            (
                OCRProviderExecutionError,
                "OCR provider 'legacy-ocr' failed during execution "
                "(ENGINE_FAILURE).",
            ),
            (
                OCRProviderOutputError,
                "OCR provider 'legacy-ocr' returned invalid output "
                "(INVALID_PROVIDER_OUTPUT).",
            ),
            (
                OCRProviderCleanupError,
                "OCR provider 'legacy-ocr' failed during cleanup "
                "(CLEANUP_FAILED).",
            ),
        )
        for error_type, expected in cases:
            code = expected.rsplit("(", 1)[1][:-2]
            with self.subTest(error_type=error_type.__name__):
                error = error_type("legacy-ocr", code)
                self.assertEqual(str(error), expected)
                self.assertNotIn("\\", str(error))
                self.assertNotIn("/", str(error))
                self.assertNotIn("api", str(error).lower())

    def test_error_contract_accepts_no_arbitrary_message_or_cause(self) -> None:
        signature = inspect.signature(OCRProviderExecutionError)
        self.assertEqual(
            tuple(signature.parameters),
            ("provider_id", "diagnostic_code"),
        )

    def test_invalid_provider_identity_uses_contract_error(self) -> None:
        with self.assertRaises(InvalidOCRProviderContractError):
            OCRProviderUnavailableError("Legacy OCR", "UNAVAILABLE")


class CapabilityShapeAndImmutabilityTests(unittest.TestCase):
    def test_valid_capabilities_preserve_exact_values(self) -> None:
        value = _capabilities()
        self.assertEqual(value.provider_id, "legacy-ocr")
        self.assertIs(value.availability, OCRProviderAvailability.AVAILABLE)
        self.assertEqual(
            value.supported_image_roles,
            (ImageRole.FRONT, ImageRole.REVERSE, ImageRole.EDGE),
        )
        self.assertEqual(value.supported_media_types, ("image/jpeg",))
        self.assertIs(
            value.field_support_mode,
            OCRProviderFieldSupportMode.DECLARED,
        )
        self.assertEqual(value.supported_fields, LEGACY_FIELDS)

    def test_capabilities_are_frozen_and_slotted(self) -> None:
        value = _capabilities()
        self.assertFalse(hasattr(value, "__dict__"))
        for name in (
            "provider_id",
            "availability",
            "supported_image_roles",
            "supported_media_types",
            "field_support_mode",
            "supported_fields",
        ):
            with self.subTest(name=name):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, name, getattr(value, name))

    def test_wrong_availability_type_fails_closed(self) -> None:
        for value in ("AVAILABLE", None, 1):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(availability=value)

    def test_wrong_field_support_mode_type_fails_closed(self) -> None:
        for value in ("DECLARED", None, 1):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(field_mode=value)

    def test_repeated_construction_is_equal_and_hashable(self) -> None:
        first = _capabilities()
        second = _capabilities()
        self.assertEqual(first, second)
        self.assertEqual(hash(first), hash(second))

class ImageRoleValidationTests(unittest.TestCase):
    def test_role_collection_must_be_tuple(self) -> None:
        for value in (
            [ImageRole.FRONT],
            {ImageRole.FRONT},
            "front",
            None,
        ):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(roles=value)

    def test_role_values_must_be_exact_enum_members(self) -> None:
        for value in (("front",), (object(),), (None,)):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(roles=value)

    def test_empty_duplicate_and_noncanonical_roles_fail(self) -> None:
        cases = (
            (),
            (ImageRole.FRONT, ImageRole.FRONT),
            (ImageRole.REVERSE, ImageRole.FRONT),
            (ImageRole.FRONT, ImageRole.EDGE, ImageRole.REVERSE),
        )
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(roles=value)


class MediaTypeValidationTests(unittest.TestCase):
    def test_valid_media_types_use_exact_mime_grammar(self) -> None:
        for value in (
            ("image/jpeg",),
            ("image/jpeg", "image/png"),
            ("application/vnd.ocr+json", "image/jpeg"),
        ):
            with self.subTest(value=value):
                self.assertEqual(
                    _capabilities(media_types=value).supported_media_types,
                    value,
                )

    def test_media_types_must_be_nonempty_tuple(self) -> None:
        for value in ((), ["image/jpeg"], {"image/jpeg"}, "image/jpeg", None):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(media_types=value)

    def test_malformed_media_types_fail(self) -> None:
        for item in (
            "IMAGE/JPEG",
            "image/JPEG",
            "image/jpeg; quality=90",
            "image/*",
            "*.jpg",
            ".jpg",
            "jpeg",
            "/image/jpeg",
            "image/",
            "",
        ):
            with self.subTest(item=item):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(media_types=(item,))

    def test_duplicate_and_noncanonical_media_types_fail(self) -> None:
        for value in (
            ("image/jpeg", "image/jpeg"),
            ("image/png", "image/jpeg"),
            ("image/jpeg", "image/png", "image/png"),
        ):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(media_types=value)

class FieldSupportValidationTests(unittest.TestCase):
    def test_declared_fields_must_be_known_nonempty_and_lexical(self) -> None:
        self.assertEqual(
            _capabilities(fields=tuple(sorted(ALLOWED_OCR_FIELDS))).supported_fields,
            tuple(sorted(ALLOWED_OCR_FIELDS)),
        )

    def test_unknown_support_requires_empty_field_tuple(self) -> None:
        value = _capabilities(
            field_mode=OCRProviderFieldSupportMode.UNKNOWN,
            fields=(),
        )
        self.assertIs(
            value.field_support_mode,
            OCRProviderFieldSupportMode.UNKNOWN,
        )
        self.assertEqual(value.supported_fields, ())

    def test_unknown_support_does_not_accept_declared_fields(self) -> None:
        with self.assertRaises(InvalidOCRProviderContractError):
            _capabilities(
                field_mode=OCRProviderFieldSupportMode.UNKNOWN,
                fields=("year",),
            )

    def test_declared_support_cannot_be_empty(self) -> None:
        with self.assertRaises(InvalidOCRProviderContractError):
            _capabilities(fields=())

    def test_field_collection_must_be_tuple(self) -> None:
        for value in (["year"], {"year"}, "year", None):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(fields=value)

    def test_unknown_and_non_string_fields_fail(self) -> None:
        for value in (
            ("grade",),
            ("future_field",),
            (None,),
            (1,),
            (object(),),
        ):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(fields=value)

    def test_duplicate_and_noncanonical_fields_fail(self) -> None:
        for value in (
            ("country", "country"),
            ("year", "country"),
            ("country", "year", "year"),
        ):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(fields=value)


class LegacyTruthfulnessTests(unittest.TestCase):
    def test_legacy_provider_capabilities_are_representable(self) -> None:
        capabilities = _capabilities(
            availability=OCRProviderAvailability.UNKNOWN,
        )
        self.assertEqual(capabilities.provider_id, "legacy-ocr")
        self.assertEqual(
            capabilities.supported_image_roles,
            (ImageRole.FRONT, ImageRole.REVERSE, ImageRole.EDGE),
        )
        self.assertEqual(capabilities.supported_media_types, ("image/jpeg",))
        self.assertEqual(capabilities.supported_fields, LEGACY_FIELDS)

    def test_legacy_runtime_unavailability_is_representable(self) -> None:
        capabilities = _capabilities(
            availability=OCRProviderAvailability.UNAVAILABLE,
        )
        self.assertIs(
            capabilities.availability,
            OCRProviderAvailability.UNAVAILABLE,
        )
        error = OCRProviderUnavailableError(
            "legacy-ocr",
            "DEPENDENCY_UNAVAILABLE",
        )
        self.assertEqual(error.provider_id, capabilities.provider_id)

    def test_cleanup_failure_category_is_representable_without_policy(self) -> None:
        error = OCRProviderCleanupError("legacy-ocr", "CLEANUP_FAILED")
        self.assertEqual(error.diagnostic_code, "CLEANUP_FAILED")
        self.assertFalse(hasattr(error, "fatal"))
        self.assertFalse(hasattr(error, "retryable"))


class ReconstructionAndEnumDriftTests(unittest.TestCase):
    def test_malformed_nested_values_raise_typed_contract_error(self) -> None:
        cases = (
            {"roles": (object(),)},
            {"media_types": (object(),)},
            {"fields": (object(),)},
            {"availability": object()},
            {"field_mode": object()},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(InvalidOCRProviderContractError):
                    _capabilities(**changes)

    def test_exact_availability_vocabulary(self) -> None:
        self.assertEqual(
            tuple(item.value for item in OCRProviderAvailability),
            ("AVAILABLE", "UNAVAILABLE", "UNKNOWN"),
        )

    def test_exact_field_support_vocabulary(self) -> None:
        self.assertEqual(
            tuple(item.value for item in OCRProviderFieldSupportMode),
            ("DECLARED", "UNKNOWN"),
        )

    def test_unknown_enum_strings_fail_instead_of_defaulting(self) -> None:
        with self.assertRaises(InvalidOCRProviderContractError):
            _capabilities(availability="FUTURE")
        with self.assertRaises(InvalidOCRProviderContractError):
            _capabilities(field_mode="FUTURE")


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_production_imports_are_narrow_and_runtime_free(self) -> None:
        source = inspect.getsource(contracts)
        tree = ast.parse(source)
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])

        self.assertEqual(
            imported_roots,
            {
                "__future__",
                "dataclasses",
                "enum",
                "re",
                "enums",
                "workflow_ocr_models",
            },
        )

    def test_production_source_excludes_forbidden_boundaries(self) -> None:
        source = inspect.getsource(contracts)
        forbidden = (
            "tkinter",
            "desktop_",
            "collection_management",
            "mutation",
            "persistence",
            "legacy_ocr",
            "ocr_experiment",
            "pathlib",
            "filesystem",
            "os.environ",
            "network",
            "datetime",
            "uuid",
            "random",
            "logging",
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, source.lower())

    def test_no_runtime_provider_invocation_contract(self) -> None:
        source = inspect.getsource(contracts)
        tree = ast.parse(source)
        public_functions = tuple(
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        )
        self.assertEqual(public_functions, ())

if __name__ == "__main__":
    unittest.main()
