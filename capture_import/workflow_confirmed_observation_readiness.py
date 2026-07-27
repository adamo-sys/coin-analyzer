"""Pure readiness composition for confirmed observation sets.

Readiness means safe under the currently implemented Sprint 13 rules: Unit 1C
field validation succeeds, Unit 1D applies every explicit canonical value, and
Unit 1E finds no known incompatibility.  It does not mean historically complete
or collection-ready.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .workflow_confirmed_observation_canonicalization import (
    apply_canonical_values,
)
from .workflow_confirmed_observation_compatibility import (
    ConfirmedObservationCompatibilityResult,
    validate_confirmed_observation_compatibility,
)
from .workflow_confirmed_observation_models import ConfirmedObservationSet


class ConfirmedObservationReadinessStatus(str, Enum):
    """Bounded successful readiness outcome."""

    READY = "READY"


@dataclass(frozen=True, slots=True)
class ConfirmedObservationReadinessResult:
    """Immutable evidence that all implemented readiness stages succeeded."""

    source_coin_id: str
    status: ConfirmedObservationReadinessStatus
    canonicalized_observation_set: ConfirmedObservationSet
    compatibility_results: tuple[
        ConfirmedObservationCompatibilityResult,
        ...,
    ]

    @property
    def is_ready(self) -> bool:
        return self.status is ConfirmedObservationReadinessStatus.READY

    def to_dict(self) -> dict[str, object]:
        return {
            "source_coin_id": self.source_coin_id,
            "status": self.status.value,
            "canonicalized_observation_set": (
                self.canonicalized_observation_set.to_dict()
            ),
            "compatibility_results": [
                result.to_dict()
                for result in self.compatibility_results
            ],
        }


class ConfirmedObservationReadinessAssessor:
    """Stateless composition of Unit 1D and Unit 1E public boundaries."""

    __slots__ = ()

    def assess(
        self,
        observation_set: ConfirmedObservationSet,
    ) -> ConfirmedObservationReadinessResult:
        # Unit 1D performs Unit 1C validation before immutable application.
        canonicalized = apply_canonical_values(observation_set)
        compatibility = validate_confirmed_observation_compatibility(
            canonicalized
        )
        return ConfirmedObservationReadinessResult(
            source_coin_id=canonicalized.source_coin_id,
            status=ConfirmedObservationReadinessStatus.READY,
            canonicalized_observation_set=canonicalized,
            compatibility_results=compatibility,
        )

    def require(
        self,
        observation_set: ConfirmedObservationSet,
    ) -> ConfirmedObservationSet:
        return self.assess(observation_set).canonicalized_observation_set


def assess_confirmed_observation_readiness(
    observation_set: ConfirmedObservationSet,
) -> ConfirmedObservationReadinessResult:
    """Return READY evidence or propagate the authoritative typed failure."""

    return ConfirmedObservationReadinessAssessor().assess(observation_set)


def require_confirmed_observation_readiness(
    observation_set: ConfirmedObservationSet,
) -> ConfirmedObservationSet:
    """Return the canonicalized ready set or propagate the typed failure."""

    return ConfirmedObservationReadinessAssessor().require(observation_set)
