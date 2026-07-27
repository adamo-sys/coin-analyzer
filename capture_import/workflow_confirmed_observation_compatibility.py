"""Pure compatibility checks across confirmed observation fields.

Only explicit, repository-supported incompatibilities are enforced.  Unknown
values and domains backed only by heuristics remain not evaluated.  The module
never mutates observations, maps collection fields, performs external lookups,
or invokes mapping/canonicalization automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from .workflow_confirmed_observation_models import (
    ConfirmedFieldObservation,
    ConfirmedObservationSet,
)
from .workflow_confirmed_observation_validators import (
    validate_confirmed_observation_set,
)


_MONARCH_YEAR_RULE_ID = "monarch_year"
_MONARCH_YEAR_FIELDS = ("monarch", "year")

# Inclusive ranges deliberately overlap at accession years.  This avoids
# rejecting boundary-year issues that may legitimately bear either monarch.
_MONARCH_YEAR_RANGES = MappingProxyType(
    {
        "Victoria": (1837, 1901),
        "Edward VII": (1901, 1910),
        "George V": (1910, 1936),
        "Edward VIII": (1936, 1936),
        "George VI": (1936, 1952),
        "Elizabeth II": (1952, 2022),
        "Charles III": (2022, 2999),
    }
)


class ConfirmedObservationCompatibilityStatus(str, Enum):
    """Bounded outcome for one compatibility rule."""

    COMPATIBLE = "COMPATIBLE"
    NOT_EVALUATED = "NOT_EVALUATED"


class ConfirmedObservationCompatibilityError(ValueError):
    """Base error for confirmed-observation compatibility failures."""


class IncompatibleConfirmedObservationError(
    ConfirmedObservationCompatibilityError
):
    """A known, deterministic cross-field incompatibility was found."""

    def __init__(
        self,
        *,
        rule_id: str,
        field_values: tuple[tuple[str, str], ...],
        message: str,
    ) -> None:
        self.rule_id = rule_id
        self.field_names = tuple(name for name, _ in field_values)
        self.field_values = field_values
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ConfirmedObservationCompatibilityResult:
    """Immutable JSON-safe outcome for one deterministic rule."""

    rule_id: str
    fields: tuple[str, ...]
    status: ConfirmedObservationCompatibilityStatus
    message: str

    @property
    def is_compatible(self) -> bool:
        return self.status is ConfirmedObservationCompatibilityStatus.COMPATIBLE

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "fields": list(self.fields),
            "status": self.status.value,
            "message": self.message,
        }


class ConfirmedObservationCompatibilityValidator:
    """Stateless validator for the bounded strong-rule set."""

    __slots__ = ()

    def validate(
        self,
        observation_set: ConfirmedObservationSet,
    ) -> tuple[ConfirmedObservationCompatibilityResult, ...]:
        validate_confirmed_observation_set(observation_set)
        observations = {
            observation.field_name: observation
            for observation in observation_set.observations
        }
        result = self._validate_monarch_year(observations)
        return (result,)

    @staticmethod
    def _validate_monarch_year(
        observations: dict[str, ConfirmedFieldObservation],
    ) -> ConfirmedObservationCompatibilityResult:
        monarch_observation = observations.get("monarch")
        year_observation = observations.get("year")
        if monarch_observation is None or year_observation is None:
            return ConfirmedObservationCompatibilityResult(
                rule_id=_MONARCH_YEAR_RULE_ID,
                fields=_MONARCH_YEAR_FIELDS,
                status=(
                    ConfirmedObservationCompatibilityStatus.NOT_EVALUATED
                ),
                message=(
                    "Monarch/year compatibility requires both confirmed "
                    "fields."
                ),
            )

        monarch = monarch_observation.submitted_value
        year_text = year_observation.submitted_value
        bounds = _MONARCH_YEAR_RANGES.get(monarch)
        if bounds is None:
            return ConfirmedObservationCompatibilityResult(
                rule_id=_MONARCH_YEAR_RULE_ID,
                fields=_MONARCH_YEAR_FIELDS,
                status=(
                    ConfirmedObservationCompatibilityStatus.NOT_EVALUATED
                ),
                message=(
                    "Monarch/year compatibility is not defined for the "
                    "exact submitted monarch."
                ),
            )

        year = int(year_text)
        minimum, maximum = bounds
        if not minimum <= year <= maximum:
            raise IncompatibleConfirmedObservationError(
                rule_id=_MONARCH_YEAR_RULE_ID,
                field_values=(
                    ("monarch", monarch),
                    ("year", year_text),
                ),
                message=(
                    f"Monarch {monarch!r} is incompatible with year "
                    f"{year_text!r} under the bounded reign rule."
                ),
            )

        return ConfirmedObservationCompatibilityResult(
            rule_id=_MONARCH_YEAR_RULE_ID,
            fields=_MONARCH_YEAR_FIELDS,
            status=ConfirmedObservationCompatibilityStatus.COMPATIBLE,
            message=(
                "Monarch and year satisfy the inclusive bounded reign rule."
            ),
        )


def validate_confirmed_observation_compatibility(
    observation_set: ConfirmedObservationSet,
) -> tuple[ConfirmedObservationCompatibilityResult, ...]:
    """Validate compatibility without retaining state or changing the set."""

    return ConfirmedObservationCompatibilityValidator().validate(
        observation_set
    )
