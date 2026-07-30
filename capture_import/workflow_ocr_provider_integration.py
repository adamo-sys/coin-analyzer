"""Explicit OCR capability and runtime-binding integration.

This module connects caller-supplied Unit 1A capability snapshots to the
existing Unit 1B registry and Unit 1C analyze-compatible execution bindings.
It performs no discovery, dependency probing, provider construction,
selection, execution, persistence, or default activation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import ImageRole as _ImageRole
from .workflow_ocr_provider_contracts import (
    OCRProviderAvailability,
    OCRProviderCapabilities,
    OCRProviderFieldSupportMode,
)
from .workflow_ocr_provider_execution import (
    OCRProviderExecutionBinding,
    OCRProviderExecutionBindings,
)
from .workflow_ocr_provider_selection import OCRProviderRegistry
from .workflow_ocr_stage import OCRMetadataProvider as _OCRMetadataProvider


__all__ = [
    "OCRProviderIntegrationContractError",
    "InvalidOCRProviderIntegrationContextError",
    "OCRProviderIntegration",
    "build_ocr_provider_integration",
    "create_legacy_ocr_provider_capabilities",
    "build_legacy_ocr_provider_integration",
]


_LEGACY_PROVIDER_ID = "legacy-ocr"
_LEGACY_SUPPORTED_FIELDS = (
    "banknote_prefix",
    "certification_number",
    "country",
    "denomination",
    "year",
)


class OCRProviderIntegrationContractError(ValueError):
    """An explicit provider integration violates Unit 1E invariants."""


class InvalidOCRProviderIntegrationContextError(
    OCRProviderIntegrationContractError
):
    """Registry, binding, capability, or provider context is invalid."""


@dataclass(frozen=True, slots=True, eq=False)
class OCRProviderIntegration:
    """Exact immutable pairing of a registry and executable bindings.

    ``bindings=None`` represents a capability-only registry.  It is useful
    for truthful ``UNKNOWN`` or ``UNAVAILABLE`` snapshots; execution remains
    an explicit later action.
    """

    registry: OCRProviderRegistry
    bindings: OCRProviderExecutionBindings | None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.registry, OCRProviderRegistry):
            raise InvalidOCRProviderIntegrationContextError(
                "registry must be an OCRProviderRegistry."
            )
        try:
            self.registry.validate()
        except Exception as error:
            raise InvalidOCRProviderIntegrationContextError(
                "registry must satisfy the Unit 1B contract."
            ) from error

        bindings_by_id: dict[str, OCRProviderExecutionBinding] = {}
        if self.bindings is not None:
            if not isinstance(
                self.bindings,
                OCRProviderExecutionBindings,
            ):
                raise InvalidOCRProviderIntegrationContextError(
                    "bindings must be OCRProviderExecutionBindings or None."
                )
            try:
                self.bindings.validate()
            except Exception as error:
                raise InvalidOCRProviderIntegrationContextError(
                    "bindings must satisfy the Unit 1C contract."
                ) from error
            bindings_by_id = {
                binding.provider_id: binding
                for binding in self.bindings.bindings
            }

        registry_ids = set(self.registry.provider_ids)
        foreign_ids = set(bindings_by_id).difference(registry_ids)
        if foreign_ids:
            raise InvalidOCRProviderIntegrationContextError(
                "every binding must belong to the supplied registry."
            )

        for capability in self.registry.capabilities:
            binding = bindings_by_id.get(capability.provider_id)
            if binding is not None and binding.capabilities is not capability:
                raise InvalidOCRProviderIntegrationContextError(
                    "bindings must preserve exact registry capability identity."
                )
            if capability.availability is OCRProviderAvailability.AVAILABLE:
                if binding is None:
                    raise InvalidOCRProviderIntegrationContextError(
                        "AVAILABLE capabilities require an execution binding."
                    )
            elif capability.availability is OCRProviderAvailability.UNAVAILABLE:
                if binding is not None:
                    raise InvalidOCRProviderIntegrationContextError(
                        "UNAVAILABLE capabilities cannot have an execution binding."
                    )


def build_ocr_provider_integration(
    *,
    registry: OCRProviderRegistry,
    bindings: OCRProviderExecutionBindings | None,
) -> OCRProviderIntegration:
    """Validate and retain caller-built registry and bindings exactly."""

    return OCRProviderIntegration(
        registry=registry,
        bindings=bindings,
    )


def create_legacy_ocr_provider_capabilities(
    availability: OCRProviderAvailability,
) -> OCRProviderCapabilities:
    """Create the truthful legacy-provider capability snapshot.

    Availability is an exact caller-supplied snapshot.  No optional dependency
    or runtime environment is inspected.
    """

    if not isinstance(availability, OCRProviderAvailability):
        raise InvalidOCRProviderIntegrationContextError(
            "availability must be an OCRProviderAvailability."
        )
    return OCRProviderCapabilities(
        provider_id=_LEGACY_PROVIDER_ID,
        availability=availability,
        supported_image_roles=(
            _ImageRole.FRONT,
            _ImageRole.REVERSE,
            _ImageRole.EDGE,
        ),
        supported_media_types=("image/jpeg",),
        field_support_mode=OCRProviderFieldSupportMode.DECLARED,
        supported_fields=_LEGACY_SUPPORTED_FIELDS,
    )


def build_legacy_ocr_provider_integration(
    *,
    availability: OCRProviderAvailability,
    provider: _OCRMetadataProvider | None = None,
) -> OCRProviderIntegration:
    """Compose one explicit legacy capability snapshot and optional binding.

    ``AVAILABLE`` requires an actual provider object, ``UNAVAILABLE`` forbids
    one, and ``UNKNOWN`` may retain one when invocation is possible but its
    availability has not been asserted.
    """

    capability = create_legacy_ocr_provider_capabilities(availability)
    registry = OCRProviderRegistry(capabilities=(capability,))

    if provider is None:
        bindings = None
    else:
        if not isinstance(provider, _OCRMetadataProvider):
            raise InvalidOCRProviderIntegrationContextError(
                "provider must satisfy OCRMetadataProvider."
            )
        if availability is OCRProviderAvailability.UNAVAILABLE:
            raise InvalidOCRProviderIntegrationContextError(
                "UNAVAILABLE legacy capabilities cannot bind a provider."
            )
        try:
            binding = OCRProviderExecutionBinding(
                capabilities=capability,
                provider=provider,
            )
            bindings = OCRProviderExecutionBindings(bindings=(binding,))
        except Exception as error:
            raise InvalidOCRProviderIntegrationContextError(
                "provider must match the legacy OCR capability identity."
            ) from error

    return OCRProviderIntegration(
        registry=registry,
        bindings=bindings,
    )
