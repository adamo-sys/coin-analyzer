"""Pure application of validator-produced canonical observation values.

The service validates through Sprint 13 Unit 1C and returns new immutable Unit
1A contracts.  It does not infer canonical values, mutate inputs, map collection
fields, persist state, or invoke the OCR mapper automatically.
"""

from __future__ import annotations

from dataclasses import replace

from .workflow_confirmed_observation_models import (
    ConfirmedFieldObservation,
    ConfirmedObservationSet,
)
from .workflow_confirmed_observation_validators import (
    ConfirmedObservationValidationResult,
    validate_confirmed_observation,
    validate_confirmed_observation_set,
)


class ConfirmedObservationCanonicalizationError(ValueError):
    """Base error for applying an explicit canonical-value result."""


class ConflictingCanonicalValueError(
    ConfirmedObservationCanonicalizationError
):
    """An existing canonical value cannot be verified by Unit 1C."""

    def __init__(
        self,
        *,
        field_name: str,
        existing_value: str,
        validator_value: str | None,
    ) -> None:
        self.field_name = field_name
        self.existing_value = existing_value
        self.validator_value = validator_value
        expected = (
            "no canonical value"
            if validator_value is None
            else repr(validator_value)
        )
        super().__init__(
            f"Existing canonical value for {field_name!r} conflicts with "
            f"validator output {expected}."
        )


class ConfirmedObservationCanonicalizer:
    """Stateless fail-closed canonical-value application service."""

    __slots__ = ()

    def apply_to_observation(
        self,
        observation: ConfirmedFieldObservation,
    ) -> ConfirmedFieldObservation:
        validation = validate_confirmed_observation(observation)
        return self._apply_validation(observation, validation)

    def apply_to_set(
        self,
        observation_set: ConfirmedObservationSet,
    ) -> ConfirmedObservationSet:
        validations = validate_confirmed_observation_set(observation_set)
        observations = tuple(
            self._apply_validation(observation, validation)
            for observation, validation in zip(
                observation_set.observations,
                validations,
                strict=True,
            )
        )
        result = replace(
            observation_set,
            observations=observations,
        )
        result.validate()
        return result

    @staticmethod
    def _apply_validation(
        observation: ConfirmedFieldObservation,
        validation: ConfirmedObservationValidationResult,
    ) -> ConfirmedFieldObservation:
        canonical_value = validation.canonical_value
        existing_value = observation.canonical_value
        if existing_value is not None and existing_value != canonical_value:
            raise ConflictingCanonicalValueError(
                field_name=observation.field_name,
                existing_value=existing_value,
                validator_value=canonical_value,
            )

        result = replace(
            observation,
            canonical_value=canonical_value,
        )
        result.validate()
        return result


def apply_canonical_value(
    observation: ConfirmedFieldObservation,
) -> ConfirmedFieldObservation:
    """Validate and canonicalize one observation without retaining state."""

    return ConfirmedObservationCanonicalizer().apply_to_observation(
        observation
    )


def apply_canonical_values(
    observation_set: ConfirmedObservationSet,
) -> ConfirmedObservationSet:
    """Validate and atomically canonicalize one immutable observation set."""

    return ConfirmedObservationCanonicalizer().apply_to_set(observation_set)
