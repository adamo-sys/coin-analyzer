from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

from capture_import.enums import ImageRole
from capture_import.workflow_ocr_provider_contracts import (
    OCRProviderAvailability,
    OCRProviderCapabilities,
    OCRProviderFieldSupportMode,
)
from capture_import.workflow_ocr_provider_execution import (
    OCRProviderExecutionBinding,
    OCRProviderExecutionBindings,
    execute_selected_ocr_providers,
)
from capture_import.workflow_ocr_provider_integration import (
    InvalidOCRProviderIntegrationContextError,
    OCRProviderIntegration,
    OCRProviderIntegrationContractError,
    build_legacy_ocr_provider_integration,
    build_ocr_provider_integration,
    create_legacy_ocr_provider_capabilities,
)
from capture_import.workflow_ocr_provider_selection import (
    OCRProviderAvailabilityPolicy,
    OCRProviderRegistry,
    OCRProviderSelectionCriteria,
    select_ocr_providers,
)
from tests import test_workflow_ocr_provider_execution as fx


PUBLIC_API = {
    "OCRProviderIntegrationContractError",
    "InvalidOCRProviderIntegrationContextError",
    "OCRProviderIntegration",
    "build_ocr_provider_integration",
    "create_legacy_ocr_provider_capabilities",
    "build_legacy_ocr_provider_integration",
}


def capability(
    provider_id: str,
    availability: OCRProviderAvailability,
) -> OCRProviderCapabilities:
    return OCRProviderCapabilities(
        provider_id=provider_id,
        availability=availability,
        supported_image_roles=(ImageRole.FRONT,),
        supported_media_types=("image/jpeg",),
        field_support_mode=OCRProviderFieldSupportMode.DECLARED,
        supported_fields=("country",),
    )


class ProviderSpy(fx.FakeProvider):
    def __init__(self, provider_id: str) -> None:
        super().__init__(
            provider_id,
            fx.report(
                provider_id,
                fx.candidate(provider_id),
            ),
        )


class TestProviderIntegrationPublicAPI(unittest.TestCase):
    def test_exact_public_api(self) -> None:
        from capture_import import workflow_ocr_provider_integration as module

        self.assertEqual(set(module.__all__), PUBLIC_API)
        self.assertEqual(len(module.__all__), len(PUBLIC_API))

    def test_error_hierarchy(self) -> None:
        self.assertTrue(
            issubclass(OCRProviderIntegrationContractError, ValueError)
        )
        self.assertTrue(
            issubclass(
                InvalidOCRProviderIntegrationContextError,
                OCRProviderIntegrationContractError,
            )
        )

    def test_no_discovery_loader_default_or_persistence_api(self) -> None:
        from capture_import import workflow_ocr_provider_integration as module

        forbidden = {
            "discover",
            "load",
            "refresh",
            "default_provider",
            "save",
            "to_dict",
            "from_dict",
            "select",
            "execute",
        }
        self.assertTrue(forbidden.isdisjoint(module.__all__))

    def test_module_does_not_import_legacy_provider(self) -> None:
        module_path = (
            Path(__file__).parents[1]
            / "capture_import"
            / "workflow_ocr_provider_integration.py"
        )
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_names.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        self.assertNotIn("legacy_ocr_workflow_provider", imported_names)


class TestIntegrationAggregate(unittest.TestCase):
    def test_valid_registry_and_bindings_preserve_exact_identity(self) -> None:
        alpha = capability(
            "alpha-ocr",
            OCRProviderAvailability.AVAILABLE,
        )
        beta = capability(
            "beta-ocr",
            OCRProviderAvailability.UNKNOWN,
        )
        registry = OCRProviderRegistry((alpha, beta))
        alpha_provider = ProviderSpy("alpha-ocr")
        beta_provider = ProviderSpy("beta-ocr")
        bindings = OCRProviderExecutionBindings(
            (
                OCRProviderExecutionBinding(alpha, alpha_provider),
                OCRProviderExecutionBinding(beta, beta_provider),
            )
        )
        integration = build_ocr_provider_integration(
            registry=registry,
            bindings=bindings,
        )

        self.assertIs(integration.registry, registry)
        self.assertIs(integration.bindings, bindings)
        self.assertIs(
            integration.registry.capabilities[0],
            integration.bindings.bindings[0].capabilities,
        )
        self.assertIs(
            integration.registry.capabilities[1],
            integration.bindings.bindings[1].capabilities,
        )
        self.assertEqual(alpha_provider.calls, [])
        self.assertEqual(beta_provider.calls, [])

    def test_capability_only_unknown_and_unavailable_are_valid(self) -> None:
        for availability in (
            OCRProviderAvailability.UNKNOWN,
            OCRProviderAvailability.UNAVAILABLE,
        ):
            with self.subTest(availability=availability):
                integration = OCRProviderIntegration(
                    OCRProviderRegistry(
                        (capability("alpha-ocr", availability),)
                    ),
                    None,
                )
                self.assertIsNone(integration.bindings)

    def test_available_requires_binding(self) -> None:
        with self.assertRaises(
            InvalidOCRProviderIntegrationContextError
        ):
            OCRProviderIntegration(
                OCRProviderRegistry(
                    (
                        capability(
                            "alpha-ocr",
                            OCRProviderAvailability.AVAILABLE,
                        ),
                    )
                ),
                None,
            )

    def test_unavailable_rejects_binding(self) -> None:
        alpha = capability(
            "alpha-ocr",
            OCRProviderAvailability.UNAVAILABLE,
        )
        with self.assertRaises(
            InvalidOCRProviderIntegrationContextError
        ):
            OCRProviderIntegration(
                OCRProviderRegistry((alpha,)),
                OCRProviderExecutionBindings(
                    (
                        OCRProviderExecutionBinding(
                            alpha,
                            ProviderSpy("alpha-ocr"),
                        ),
                    )
                ),
            )

    def test_foreign_and_equal_distinct_binding_capability_are_rejected(self) -> None:
        alpha = capability(
            "alpha-ocr",
            OCRProviderAvailability.AVAILABLE,
        )
        for bound_capability in (
            capability("beta-ocr", OCRProviderAvailability.AVAILABLE),
            capability("alpha-ocr", OCRProviderAvailability.AVAILABLE),
        ):
            with self.subTest(
                provider_id=bound_capability.provider_id
            ), self.assertRaises(
                InvalidOCRProviderIntegrationContextError
            ):
                OCRProviderIntegration(
                    OCRProviderRegistry((alpha,)),
                    OCRProviderExecutionBindings(
                        (
                            OCRProviderExecutionBinding(
                                bound_capability,
                                ProviderSpy(
                                    bound_capability.provider_id
                                ),
                            ),
                        )
                    ),
                )

    def test_wrong_registry_and_bindings_types_are_typed_errors(self) -> None:
        unknown = capability(
            "alpha-ocr",
            OCRProviderAvailability.UNKNOWN,
        )
        for registry, bindings in (
            (object(), None),
            (OCRProviderRegistry((unknown,)), object()),
        ):
            with self.subTest(), self.assertRaises(
                InvalidOCRProviderIntegrationContextError
            ):
                OCRProviderIntegration(  # type: ignore[arg-type]
                    registry,
                    bindings,
                )

    def test_aggregate_is_frozen_and_slotted(self) -> None:
        integration = OCRProviderIntegration(
            OCRProviderRegistry(
                (
                    capability(
                        "alpha-ocr",
                        OCRProviderAvailability.UNKNOWN,
                    ),
                )
            ),
            None,
        )
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            integration.bindings = None  # type: ignore[misc]
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            integration.extra = object()  # type: ignore[attr-defined]


class TestLegacyIntegration(unittest.TestCase):
    def test_truthful_capability_snapshot(self) -> None:
        item = create_legacy_ocr_provider_capabilities(
            OCRProviderAvailability.UNKNOWN
        )
        self.assertEqual(item.provider_id, "legacy-ocr")
        self.assertIs(
            item.availability,
            OCRProviderAvailability.UNKNOWN,
        )
        self.assertEqual(
            item.supported_image_roles,
            (ImageRole.FRONT, ImageRole.REVERSE, ImageRole.EDGE),
        )
        self.assertEqual(item.supported_media_types, ("image/jpeg",))
        self.assertIs(
            item.field_support_mode,
            OCRProviderFieldSupportMode.DECLARED,
        )
        self.assertEqual(
            item.supported_fields,
            (
                "banknote_prefix",
                "certification_number",
                "country",
                "denomination",
                "year",
            ),
        )

    def test_available_and_unknown_retain_exact_provider_without_invoking(self) -> None:
        for availability in (
            OCRProviderAvailability.AVAILABLE,
            OCRProviderAvailability.UNKNOWN,
        ):
            provider = ProviderSpy("legacy-ocr")
            integration = build_legacy_ocr_provider_integration(
                availability=availability,
                provider=provider,
            )
            self.assertIs(
                integration.bindings.bindings[0].provider,
                provider,
            )
            self.assertIs(
                integration.registry.capabilities[0],
                integration.bindings.bindings[0].capabilities,
            )
            self.assertEqual(provider.calls, [])

    def test_unknown_and_unavailable_can_be_unbound(self) -> None:
        for availability in (
            OCRProviderAvailability.UNKNOWN,
            OCRProviderAvailability.UNAVAILABLE,
        ):
            integration = build_legacy_ocr_provider_integration(
                availability=availability
            )
            self.assertIsNone(integration.bindings)

    def test_available_cannot_overclaim_without_provider(self) -> None:
        with self.assertRaises(
            InvalidOCRProviderIntegrationContextError
        ):
            build_legacy_ocr_provider_integration(
                availability=OCRProviderAvailability.AVAILABLE
            )

    def test_unavailable_cannot_bind_provider(self) -> None:
        with self.assertRaises(
            InvalidOCRProviderIntegrationContextError
        ):
            build_legacy_ocr_provider_integration(
                availability=OCRProviderAvailability.UNAVAILABLE,
                provider=ProviderSpy("legacy-ocr"),
            )

    def test_invalid_availability_provider_and_provider_id_are_typed(self) -> None:
        with self.assertRaises(
            InvalidOCRProviderIntegrationContextError
        ):
            create_legacy_ocr_provider_capabilities("UNKNOWN")  # type: ignore[arg-type]
        with self.assertRaises(
            InvalidOCRProviderIntegrationContextError
        ):
            build_legacy_ocr_provider_integration(
                availability=OCRProviderAvailability.UNKNOWN,
                provider=object(),  # type: ignore[arg-type]
            )
        with self.assertRaises(
            InvalidOCRProviderIntegrationContextError
        ):
            build_legacy_ocr_provider_integration(
                availability=OCRProviderAvailability.UNKNOWN,
                provider=ProviderSpy("other-ocr"),
            )


class TestExplicitMultiProviderPath(unittest.TestCase):
    def test_multiple_explicit_providers_compose_and_execute_lexically(self) -> None:
        order: list[str] = []
        alpha = capability(
            "alpha-ocr",
            OCRProviderAvailability.AVAILABLE,
        )
        beta = capability(
            "beta-ocr",
            OCRProviderAvailability.AVAILABLE,
        )
        alpha_provider = fx.FakeProvider(
            "alpha-ocr",
            fx.report("alpha-ocr", fx.candidate("alpha-ocr")),
            order=order,
        )
        beta_provider = fx.FakeProvider(
            "beta-ocr",
            fx.report("beta-ocr", fx.candidate("beta-ocr")),
            order=order,
        )
        integration = OCRProviderIntegration(
            OCRProviderRegistry((alpha, beta)),
            OCRProviderExecutionBindings(
                (
                    OCRProviderExecutionBinding(alpha, alpha_provider),
                    OCRProviderExecutionBinding(beta, beta_provider),
                )
            ),
        )
        self.assertEqual(order, [])

        selection = select_ocr_providers(
            integration.registry,
            OCRProviderSelectionCriteria(
                required_image_role=ImageRole.FRONT,
                required_media_type="image/jpeg",
                required_fields=("country",),
                availability_policy=(
                    OCRProviderAvailabilityPolicy.REQUIRE_AVAILABLE
                ),
            ),
        )
        batch = execute_selected_ocr_providers(
            selection,
            integration.bindings,
            fx.request(),
        )
        self.assertEqual(order, ["alpha-ocr", "beta-ocr"])
        self.assertEqual(batch.provider_ids, ("alpha-ocr", "beta-ocr"))

    def test_unknown_binding_obeys_existing_selection_policy(self) -> None:
        unknown = capability(
            "alpha-ocr",
            OCRProviderAvailability.UNKNOWN,
        )
        integration = OCRProviderIntegration(
            OCRProviderRegistry((unknown,)),
            OCRProviderExecutionBindings(
                (
                    OCRProviderExecutionBinding(
                        unknown,
                        ProviderSpy("alpha-ocr"),
                    ),
                )
            ),
        )
        require_available = select_ocr_providers(
            integration.registry,
            OCRProviderSelectionCriteria(
                required_image_role=ImageRole.FRONT,
                required_media_type="image/jpeg",
                required_fields=("country",),
                availability_policy=(
                    OCRProviderAvailabilityPolicy.REQUIRE_AVAILABLE
                ),
            ),
        )
        allow_unknown = select_ocr_providers(
            integration.registry,
            OCRProviderSelectionCriteria(
                required_image_role=ImageRole.FRONT,
                required_media_type="image/jpeg",
                required_fields=("country",),
                availability_policy=(
                    OCRProviderAvailabilityPolicy.ALLOW_UNKNOWN
                ),
            ),
        )
        self.assertEqual(require_available.eligible_providers, ())
        self.assertIs(allow_unknown.eligible_providers[0], unknown)

    def test_default_pipeline_is_still_ocr_free(self) -> None:
        from capture_import.workflow_stages import build_image_processing_pipeline

        pipeline = build_image_processing_pipeline()
        self.assertNotIn("ocr-metadata-extraction", pipeline.stage_ids)


if __name__ == "__main__":
    unittest.main()
