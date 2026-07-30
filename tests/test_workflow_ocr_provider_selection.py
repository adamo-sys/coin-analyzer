from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from capture_import.enums import ImageRole
from capture_import.workflow_ocr_provider_contracts import (
    OCRProviderAvailability,
    OCRProviderCapabilities,
    OCRProviderFieldSupportMode,
)
from capture_import.workflow_ocr_provider_selection import (
    AmbiguousOCRProviderSelectionError,
    InvalidOCRProviderSelectionContextError,
    NoEligibleOCRProviderError,
    OCRProviderAvailabilityPolicy,
    OCRProviderRegistry,
    OCRProviderSelectionCriteria,
    OCRProviderSelectionFinding,
    OCRProviderSelectionReason,
    OCRProviderSelectionResult,
    OCRProviderSelectionStatus,
    UnknownOCRProviderSelectionReferenceError,
    require_registered_ocr_provider,
    require_single_selected_ocr_provider,
    select_ocr_providers,
)


def capability(
    provider_id: str = "alpha",
    *,
    availability: OCRProviderAvailability = OCRProviderAvailability.AVAILABLE,
    roles: tuple[ImageRole, ...] = (ImageRole.FRONT,),
    media: tuple[str, ...] = ("image/jpeg",),
    field_mode: OCRProviderFieldSupportMode = (
        OCRProviderFieldSupportMode.DECLARED
    ),
    fields: tuple[str, ...] = ("country", "year"),
) -> OCRProviderCapabilities:
    return OCRProviderCapabilities(
        provider_id=provider_id,
        availability=availability,
        supported_image_roles=roles,
        supported_media_types=media,
        field_support_mode=field_mode,
        supported_fields=fields,
    )


def criteria(
    *,
    role: ImageRole = ImageRole.FRONT,
    media: str = "image/jpeg",
    fields: tuple[str, ...] = ("country",),
    availability: OCRProviderAvailabilityPolicy = (
        OCRProviderAvailabilityPolicy.REQUIRE_AVAILABLE
    ),
    allowed: tuple[str, ...] | None = None,
) -> OCRProviderSelectionCriteria:
    return OCRProviderSelectionCriteria(
        required_image_role=role,
        required_media_type=media,
        required_fields=fields,
        availability_policy=availability,
        allowed_provider_ids=allowed,
    )


class TestOCRProviderRegistry(unittest.TestCase):
    def test_accepts_canonical_capability_tuple(self) -> None:
        alpha = capability("alpha")
        beta = capability("beta")

        registry = OCRProviderRegistry((alpha, beta))

        self.assertEqual(registry.provider_ids, ("alpha", "beta"))
        self.assertIs(registry.capabilities[0], alpha)
        self.assertIs(registry.capabilities[1], beta)

    def test_is_frozen_and_slotted(self) -> None:
        registry = OCRProviderRegistry((capability(),))

        with self.assertRaises(FrozenInstanceError):
            registry.capabilities = ()  # type: ignore[misc]
        self.assertFalse(hasattr(registry, "__dict__"))

    def test_rejects_non_tuple(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "immutable tuple",
        ):
            OCRProviderRegistry([capability()])  # type: ignore[arg-type]

    def test_rejects_empty_registry(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "must not be empty",
        ):
            OCRProviderRegistry(())

    def test_rejects_wrong_entry_type(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "OCRProviderCapabilities",
        ):
            OCRProviderRegistry(("alpha",))  # type: ignore[arg-type]

    def test_rejects_duplicate_provider_ids(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "duplicate provider IDs",
        ):
            OCRProviderRegistry((capability(), capability()))

    def test_rejects_noncanonical_order_without_sorting(self) -> None:
        beta = capability("beta")
        alpha = capability("alpha")

        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "lexical provider-ID order",
        ):
            OCRProviderRegistry((beta, alpha))

    def test_validate_detects_invalid_reconstruction(self) -> None:
        malformed = object.__new__(OCRProviderRegistry)
        object.__setattr__(malformed, "capabilities", ())

        with self.assertRaises(InvalidOCRProviderSelectionContextError):
            malformed.validate()


class TestOCRProviderSelectionCriteria(unittest.TestCase):
    def test_accepts_complete_exact_criteria(self) -> None:
        value = criteria(
            role=ImageRole.REVERSE,
            media="image/png",
            fields=("country", "denomination"),
            availability=OCRProviderAvailabilityPolicy.ALLOW_UNKNOWN,
            allowed=("alpha", "beta"),
        )

        self.assertIs(value.required_image_role, ImageRole.REVERSE)
        self.assertEqual(value.required_media_type, "image/png")
        self.assertEqual(value.required_fields, ("country", "denomination"))
        self.assertEqual(value.allowed_provider_ids, ("alpha", "beta"))

    def test_accepts_empty_required_fields(self) -> None:
        self.assertEqual(criteria(fields=()).required_fields, ())

    def test_none_allowlist_means_unrestricted(self) -> None:
        self.assertIsNone(criteria(allowed=None).allowed_provider_ids)

    def test_rejects_empty_explicit_allowlist(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "must not be empty",
        ):
            criteria(allowed=())

    def test_rejects_non_tuple_allowlist(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "immutable tuple",
        ):
            criteria(allowed=["alpha"])  # type: ignore[arg-type]

    def test_rejects_duplicate_allowlist(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "duplicates",
        ):
            criteria(allowed=("alpha", "alpha"))

    def test_rejects_noncanonical_allowlist_order(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "lexical provider-ID order",
        ):
            criteria(allowed=("beta", "alpha"))

    def test_rejects_malformed_allowlist_provider_id(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "provider-ID contract",
        ):
            criteria(allowed=("Alpha",))

    def test_rejects_wrong_role_type(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "ImageRole",
        ):
            criteria(role="front")  # type: ignore[arg-type]

    def test_rejects_parameterized_media_type(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "normalized MIME",
        ):
            criteria(media="image/jpeg; charset=binary")

    def test_rejects_uppercase_media_type(self) -> None:
        with self.assertRaises(InvalidOCRProviderSelectionContextError):
            criteria(media="Image/JPEG")

    def test_rejects_non_tuple_required_fields(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "immutable tuple",
        ):
            criteria(fields=["country"])  # type: ignore[arg-type]

    def test_rejects_unknown_required_field(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "unknown OCR field",
        ):
            criteria(fields=("grade",))

    def test_rejects_duplicate_required_fields(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "duplicates",
        ):
            criteria(fields=("country", "country"))

    def test_rejects_noncanonical_required_field_order(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "lexical order",
        ):
            criteria(fields=("year", "country"))

    def test_rejects_wrong_availability_policy_type(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "OCRProviderAvailabilityPolicy",
        ):
            criteria(availability="REQUIRE_AVAILABLE")  # type: ignore[arg-type]

    def test_is_frozen_and_slotted(self) -> None:
        value = criteria()

        with self.assertRaises(FrozenInstanceError):
            value.required_media_type = "image/png"  # type: ignore[misc]
        self.assertFalse(hasattr(value, "__dict__"))


class TestRegisteredProviderLookup(unittest.TestCase):
    def setUp(self) -> None:
        self.alpha = capability("alpha")
        self.beta = capability("beta")
        self.registry = OCRProviderRegistry((self.alpha, self.beta))

    def test_returns_exact_registered_capability(self) -> None:
        found = require_registered_ocr_provider(self.registry, "beta")

        self.assertIs(found, self.beta)

    def test_unknown_id_raises_typed_bounded_error(self) -> None:
        with self.assertRaises(
            UnknownOCRProviderSelectionReferenceError
        ) as caught:
            require_registered_ocr_provider(self.registry, "gamma")

        self.assertEqual(caught.exception.provider_id, "gamma")
        self.assertNotIn(repr(self.registry), str(caught.exception))

    def test_unknown_reference_error_state_is_immutable(self) -> None:
        error = UnknownOCRProviderSelectionReferenceError("gamma")

        with self.assertRaisesRegex(AttributeError, "immutable"):
            error.provider_id = "other"  # type: ignore[misc]
        with self.assertRaisesRegex(AttributeError, "immutable"):
            error.args = ("changed",)

    def test_unknown_reference_error_rejects_malformed_id(self) -> None:
        with self.assertRaises(InvalidOCRProviderSelectionContextError):
            UnknownOCRProviderSelectionReferenceError("../gamma")

    def test_malformed_id_is_contract_error_not_membership_error(self) -> None:
        with self.assertRaises(InvalidOCRProviderSelectionContextError):
            require_registered_ocr_provider(self.registry, "../alpha")

    def test_rejects_wrong_registry_type(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "OCRProviderRegistry",
        ):
            require_registered_ocr_provider(object(), "alpha")  # type: ignore[arg-type]


class TestOCRProviderSelection(unittest.TestCase):
    def test_exact_match_is_eligible(self) -> None:
        item = capability()
        registry = OCRProviderRegistry((item,))

        result = select_ocr_providers(registry, criteria())

        self.assertIs(result.registry, registry)
        self.assertEqual(result.eligible_providers, (item,))
        self.assertIs(result.eligible_providers[0], item)
        self.assertEqual(
            result.findings[0].status,
            OCRProviderSelectionStatus.ELIGIBLE,
        )
        self.assertEqual(
            result.findings[0].reason,
            OCRProviderSelectionReason.MATCHED,
        )

    def test_allowlist_exclusion_has_first_precedence(self) -> None:
        item = capability(
            "alpha",
            availability=OCRProviderAvailability.UNAVAILABLE,
            roles=(ImageRole.REVERSE,),
            media=("image/png",),
        )
        allowed = capability("other")
        registry = OCRProviderRegistry((item, allowed))

        result = select_ocr_providers(
            registry,
            criteria(allowed=("other",)),
        )

        self.assertEqual(
            result.findings[0].reason,
            OCRProviderSelectionReason.PROVIDER_NOT_ALLOWED,
        )

    def test_unavailable_is_excluded_even_when_unknown_allowed(self) -> None:
        item = capability(availability=OCRProviderAvailability.UNAVAILABLE)

        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(
                availability=OCRProviderAvailabilityPolicy.ALLOW_UNKNOWN
            ),
        )

        self.assertEqual(
            result.findings[0].reason,
            OCRProviderSelectionReason.PROVIDER_UNAVAILABLE,
        )

    def test_unknown_availability_fails_closed_by_default(self) -> None:
        item = capability(availability=OCRProviderAvailability.UNKNOWN)

        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(),
        )

        self.assertEqual(
            result.findings[0].reason,
            OCRProviderSelectionReason.PROVIDER_AVAILABILITY_UNKNOWN,
        )

    def test_unknown_availability_can_be_explicitly_allowed(self) -> None:
        item = capability(availability=OCRProviderAvailability.UNKNOWN)

        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(
                availability=OCRProviderAvailabilityPolicy.ALLOW_UNKNOWN
            ),
        )

        self.assertEqual(result.eligible_providers, (item,))

    def test_unsupported_role_is_excluded(self) -> None:
        item = capability(roles=(ImageRole.REVERSE,))

        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(),
        )

        self.assertEqual(
            result.findings[0].reason,
            OCRProviderSelectionReason.IMAGE_ROLE_UNSUPPORTED,
        )

    def test_unsupported_media_type_is_excluded(self) -> None:
        item = capability(media=("image/png",))

        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(),
        )

        self.assertEqual(
            result.findings[0].reason,
            OCRProviderSelectionReason.MEDIA_TYPE_UNSUPPORTED,
        )

    def test_unknown_field_support_cannot_satisfy_required_fields(self) -> None:
        item = capability(
            field_mode=OCRProviderFieldSupportMode.UNKNOWN,
            fields=(),
        )

        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(),
        )

        self.assertEqual(
            result.findings[0].reason,
            OCRProviderSelectionReason.FIELD_SUPPORT_UNKNOWN,
        )

    def test_unknown_field_support_can_satisfy_empty_field_requirement(self) -> None:
        item = capability(
            field_mode=OCRProviderFieldSupportMode.UNKNOWN,
            fields=(),
        )

        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(fields=()),
        )

        self.assertEqual(result.eligible_providers, (item,))

    def test_missing_declared_field_is_excluded(self) -> None:
        item = capability(fields=("year",))

        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(fields=("country",)),
        )

        self.assertEqual(
            result.findings[0].reason,
            OCRProviderSelectionReason.REQUIRED_FIELDS_UNSUPPORTED,
        )

    def test_declared_field_superset_is_eligible(self) -> None:
        item = capability(fields=("country", "denomination", "year"))

        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(fields=("country", "year")),
        )

        self.assertEqual(result.eligible_providers, (item,))

    def test_all_findings_preserve_canonical_registry_order(self) -> None:
        alpha = capability("alpha")
        beta = capability("beta", media=("image/png",))
        gamma = capability("gamma")
        registry = OCRProviderRegistry((alpha, beta, gamma))

        result = select_ocr_providers(registry, criteria())

        self.assertEqual(
            tuple(item.capability.provider_id for item in result.findings),
            ("alpha", "beta", "gamma"),
        )
        self.assertEqual(
            tuple(item.provider_id for item in result.eligible_providers),
            ("alpha", "gamma"),
        )

    def test_selection_does_not_reorder_by_allowlist(self) -> None:
        alpha = capability("alpha")
        beta = capability("beta")
        registry = OCRProviderRegistry((alpha, beta))

        result = select_ocr_providers(
            registry,
            criteria(allowed=("alpha", "beta")),
        )

        self.assertEqual(
            tuple(item.provider_id for item in result.eligible_providers),
            ("alpha", "beta"),
        )

    def test_unknown_allowlist_member_raises_before_selection(self) -> None:
        registry = OCRProviderRegistry((capability("alpha"),))

        with self.assertRaises(
            UnknownOCRProviderSelectionReferenceError
        ) as caught:
            select_ocr_providers(
                registry,
                criteria(allowed=("alpha", "beta")),
            )

        self.assertEqual(caught.exception.provider_id, "beta")

    def test_zero_matches_is_valid_diagnostic_result(self) -> None:
        item = capability(media=("image/png",))

        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(),
        )

        self.assertEqual(result.eligible_providers, ())
        self.assertEqual(len(result.findings), 1)

    def test_repeated_selection_is_equal_and_identity_stable(self) -> None:
        item = capability()
        registry = OCRProviderRegistry((item,))
        request = criteria()

        first = select_ocr_providers(registry, request)
        second = select_ocr_providers(registry, request)

        self.assertEqual(first, second)
        self.assertIs(first.registry, second.registry)
        self.assertIs(first.criteria, second.criteria)
        self.assertIs(first.eligible_providers[0], item)
        self.assertIs(second.eligible_providers[0], item)

    def test_rejects_wrong_registry_input(self) -> None:
        with self.assertRaises(InvalidOCRProviderSelectionContextError):
            select_ocr_providers(object(), criteria())  # type: ignore[arg-type]

    def test_rejects_wrong_criteria_input(self) -> None:
        with self.assertRaises(InvalidOCRProviderSelectionContextError):
            select_ocr_providers(
                OCRProviderRegistry((capability(),)),
                object(),  # type: ignore[arg-type]
            )


class TestOCRProviderSelectionFinding(unittest.TestCase):
    def test_is_frozen_slotted_and_retains_identity(self) -> None:
        item = capability()
        finding = OCRProviderSelectionFinding(
            capability=item,
            status=OCRProviderSelectionStatus.ELIGIBLE,
            reason=OCRProviderSelectionReason.MATCHED,
        )

        self.assertIs(finding.capability, item)
        with self.assertRaises(FrozenInstanceError):
            finding.reason = (  # type: ignore[misc]
                OCRProviderSelectionReason.PROVIDER_UNAVAILABLE
            )
        self.assertFalse(hasattr(finding, "__dict__"))

    def test_rejects_eligible_with_nonmatched_reason(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "pair exactly",
        ):
            OCRProviderSelectionFinding(
                capability=capability(),
                status=OCRProviderSelectionStatus.ELIGIBLE,
                reason=OCRProviderSelectionReason.PROVIDER_UNAVAILABLE,
            )

    def test_rejects_excluded_with_matched_reason(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "pair exactly",
        ):
            OCRProviderSelectionFinding(
                capability=capability(),
                status=OCRProviderSelectionStatus.EXCLUDED,
                reason=OCRProviderSelectionReason.MATCHED,
            )

    def test_rejects_wrong_capability_type(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "OCRProviderCapabilities",
        ):
            OCRProviderSelectionFinding(
                capability=object(),  # type: ignore[arg-type]
                status=OCRProviderSelectionStatus.EXCLUDED,
                reason=OCRProviderSelectionReason.PROVIDER_UNAVAILABLE,
            )


class TestOCRProviderSelectionResult(unittest.TestCase):
    def setUp(self) -> None:
        self.item = capability()
        self.registry = OCRProviderRegistry((self.item,))
        self.criteria = criteria()
        self.finding = OCRProviderSelectionFinding(
            capability=self.item,
            status=OCRProviderSelectionStatus.ELIGIBLE,
            reason=OCRProviderSelectionReason.MATCHED,
        )

    def test_accepts_exact_complete_reconstruction(self) -> None:
        result = OCRProviderSelectionResult(
            registry=self.registry,
            criteria=self.criteria,
            findings=(self.finding,),
            eligible_providers=(self.item,),
        )

        self.assertIs(result.findings[0].capability, self.item)
        self.assertIs(result.eligible_providers[0], self.item)

    def test_is_frozen_and_slotted(self) -> None:
        result = select_ocr_providers(self.registry, self.criteria)

        with self.assertRaises(FrozenInstanceError):
            result.findings = ()  # type: ignore[misc]
        self.assertFalse(hasattr(result, "__dict__"))

    def test_rejects_non_tuple_findings(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "immutable tuple",
        ):
            OCRProviderSelectionResult(
                registry=self.registry,
                criteria=self.criteria,
                findings=[self.finding],  # type: ignore[arg-type]
                eligible_providers=(self.item,),
            )

    def test_rejects_incomplete_findings(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "cover every registry",
        ):
            OCRProviderSelectionResult(
                registry=self.registry,
                criteria=self.criteria,
                findings=(),
                eligible_providers=(),
            )

    def test_rejects_equal_but_nonidentical_finding_capability(self) -> None:
        duplicate = capability()
        other_finding = OCRProviderSelectionFinding(
            capability=duplicate,
            status=OCRProviderSelectionStatus.ELIGIBLE,
            reason=OCRProviderSelectionReason.MATCHED,
        )

        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "preserve registry capability identity",
        ):
            OCRProviderSelectionResult(
                registry=self.registry,
                criteria=self.criteria,
                findings=(other_finding,),
                eligible_providers=(duplicate,),
            )

    def test_rejects_non_tuple_eligible_providers(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "immutable tuple",
        ):
            OCRProviderSelectionResult(
                registry=self.registry,
                criteria=self.criteria,
                findings=(self.finding,),
                eligible_providers=[self.item],  # type: ignore[arg-type]
            )

    def test_rejects_forged_finding_for_criteria(self) -> None:
        unavailable = capability(
            availability=OCRProviderAvailability.UNAVAILABLE
        )
        registry = OCRProviderRegistry((unavailable,))
        forged = OCRProviderSelectionFinding(
            capability=unavailable,
            status=OCRProviderSelectionStatus.ELIGIBLE,
            reason=OCRProviderSelectionReason.MATCHED,
        )

        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "match the supplied registry and criteria",
        ):
            OCRProviderSelectionResult(
                registry=registry,
                criteria=self.criteria,
                findings=(forged,),
                eligible_providers=(unavailable,),
            )

    def test_rejects_unregistered_criteria_allowlist(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "unregistered provider",
        ):
            OCRProviderSelectionResult(
                registry=self.registry,
                criteria=criteria(allowed=("beta",)),
                findings=(self.finding,),
                eligible_providers=(self.item,),
            )

    def test_rejects_missing_eligible_provider(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "exactly match",
        ):
            OCRProviderSelectionResult(
                registry=self.registry,
                criteria=self.criteria,
                findings=(self.finding,),
                eligible_providers=(),
            )

    def test_rejects_extra_eligible_provider(self) -> None:
        unavailable = capability(
            availability=OCRProviderAvailability.UNAVAILABLE
        )
        registry = OCRProviderRegistry((unavailable,))
        excluded = OCRProviderSelectionFinding(
            capability=unavailable,
            status=OCRProviderSelectionStatus.EXCLUDED,
            reason=OCRProviderSelectionReason.PROVIDER_UNAVAILABLE,
        )

        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "exactly match",
        ):
            OCRProviderSelectionResult(
                registry=registry,
                criteria=self.criteria,
                findings=(excluded,),
                eligible_providers=(unavailable,),
            )


class TestStrictSingleSelection(unittest.TestCase):
    def test_returns_exact_single_capability(self) -> None:
        item = capability()
        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(),
        )

        selected = require_single_selected_ocr_provider(result)

        self.assertIs(selected, item)

    def test_zero_eligible_raises_typed_error(self) -> None:
        item = capability(media=("image/png",))
        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(),
        )

        with self.assertRaisesRegex(
            NoEligibleOCRProviderError,
            "No OCR provider",
        ):
            require_single_selected_ocr_provider(result)

    def test_multiple_eligible_raises_typed_bounded_error(self) -> None:
        alpha = capability("alpha")
        beta = capability("beta")
        result = select_ocr_providers(
            OCRProviderRegistry((alpha, beta)),
            criteria(),
        )

        with self.assertRaises(
            AmbiguousOCRProviderSelectionError
        ) as caught:
            require_single_selected_ocr_provider(result)

        self.assertEqual(caught.exception.provider_ids, ("alpha", "beta"))
        self.assertNotIn(repr(result), str(caught.exception))

    def test_ambiguity_error_state_is_immutable(self) -> None:
        error = AmbiguousOCRProviderSelectionError(("alpha", "beta"))

        with self.assertRaisesRegex(AttributeError, "immutable"):
            error.provider_ids = ("other", "third")  # type: ignore[misc]
        with self.assertRaisesRegex(AttributeError, "immutable"):
            error.args = ("changed",)

    def test_ambiguity_error_requires_canonical_multiple_ids(self) -> None:
        invalid_values = (
            (),
            ("alpha",),
            ("beta", "alpha"),
            ("alpha", "alpha"),
            ("Alpha", "beta"),
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(
                    InvalidOCRProviderSelectionContextError
                ):
                    AmbiguousOCRProviderSelectionError(value)

    def test_rejects_wrong_result_type(self) -> None:
        with self.assertRaisesRegex(
            InvalidOCRProviderSelectionContextError,
            "OCRProviderSelectionResult",
        ):
            require_single_selected_ocr_provider(object())  # type: ignore[arg-type]


class TestSelectionArchitecture(unittest.TestCase):
    def test_no_provider_invocation_is_needed(self) -> None:
        class ExplodingProvider:
            def observe(self, *args: object, **kwargs: object) -> object:
                raise AssertionError("selection must not invoke providers")

            def analyze(self, *args: object, **kwargs: object) -> object:
                raise AssertionError("selection must not invoke providers")

        provider = ExplodingProvider()
        item = capability()

        result = select_ocr_providers(
            OCRProviderRegistry((item,)),
            criteria(),
        )

        self.assertEqual(result.eligible_providers, (item,))
        self.assertIsNotNone(provider)

    def test_errors_do_not_capture_capability_payloads(self) -> None:
        result = select_ocr_providers(
            OCRProviderRegistry(
                (capability("alpha"), capability("beta"))
            ),
            criteria(),
        )

        with self.assertRaises(
            AmbiguousOCRProviderSelectionError
        ) as caught:
            require_single_selected_ocr_provider(result)

        self.assertEqual(vars(caught.exception), {})
        self.assertEqual(caught.exception.provider_ids, ("alpha", "beta"))


if __name__ == "__main__":
    unittest.main()
