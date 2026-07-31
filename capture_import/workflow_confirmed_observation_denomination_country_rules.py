"""Immutable caller-supplied contracts for denomination-country compatibility.

This module defines exact denomination-country scopes and exact compatibility
outcomes. It contains no evaluator, default catalog, storage, runtime
integration, readiness authority, or lookup behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata


__all__ = [
    "DenominationCountryRuleContractError",
    "InvalidDenominationCountryRuleContextError",
    "DuplicateDenominationCountryRuleError",
    "DenominationCountryCompatibility",
    "DenominationCountryRule",
    "DenominationCountryRuleCatalog",
]


_RULE_ID = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_MAX_SCOPE_TEXT_CHARS = 128


class DenominationCountryRuleContractError(ValueError):
    """A denomination-country rule or catalog contract is malformed."""

    __slots__ = ()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            "Denomination-country rule contract errors are immutable."
        )


class InvalidDenominationCountryRuleContextError(
    DenominationCountryRuleContractError
):
    """A rule or catalog contains malformed local contract data."""


class DuplicateDenominationCountryRuleError(
    DenominationCountryRuleContractError
):
    """A catalog repeats a rule ID or exact country/denomination scope."""


class DenominationCountryCompatibility(str, Enum):
    """Deterministic compatibility outcome for one country/denomination rule."""

    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"


@dataclass(frozen=True, slots=True)
class DenominationCountryRule:
    """One exact, transient caller-supplied denomination-country rule."""

    rule_id: str
    country: str
    denomination: str
    compatibility: DenominationCountryCompatibility

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate exact scope values and deterministic compatibility state."""

        _validate_rule_id(self.rule_id)
        _validate_scope_text(self.country, "country")
        _validate_scope_text(self.denomination, "denomination")
        _validate_compatibility(self.compatibility)


@dataclass(frozen=True, slots=True)
class DenominationCountryRuleCatalog:
    """Canonical immutable set of caller-supplied compatibility rules.

    An empty catalog means only that the caller supplied no denomination-country
    coverage. Rules must be ordered lexically by ``rule_id``.
    """

    rules: tuple[DenominationCountryRule, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate nested rules, uniqueness, and lexical order."""

        if not isinstance(self.rules, tuple):
            raise InvalidDenominationCountryRuleContextError(
                "rules must be an immutable tuple."
            )
        if any(
            not isinstance(rule, DenominationCountryRule)
            for rule in self.rules
        ):
            raise InvalidDenominationCountryRuleContextError(
                "rules must contain DenominationCountryRule values."
            )

        rule_ids: set[str] = set()
        scopes: set[tuple[str, str]] = set()
        for rule in self.rules:
            rule.validate()
            if rule.rule_id in rule_ids:
                raise DuplicateDenominationCountryRuleError(
                    "rules must not contain duplicate rule IDs."
                )
            rule_ids.add(rule.rule_id)

            scope = _scope_key(rule)
            if scope in scopes:
                raise DuplicateDenominationCountryRuleError(
                    "rules must not contain duplicate exact scopes."
                )
            scopes.add(scope)

        expected_order = tuple(
            sorted(self.rules, key=lambda rule: rule.rule_id)
        )
        if self.rules != expected_order:
            raise InvalidDenominationCountryRuleContextError(
                "rules must use lexical rule_id order."
            )

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """Return caller-supplied rule IDs in validated catalog order."""

        return tuple(rule.rule_id for rule in self.rules)


def _validate_rule_id(value: object) -> str:
    if not isinstance(value, str) or _RULE_ID.fullmatch(value) is None:
        raise InvalidDenominationCountryRuleContextError(
            "rule_id must match [a-z][a-z0-9._-]{0,127}."
        )
    return value


def _validate_scope_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise InvalidDenominationCountryRuleContextError(
            f"{name} must be a string."
        )
    if not value or not value.strip():
        raise InvalidDenominationCountryRuleContextError(
            f"{name} must not be blank."
        )
    if value != value.strip():
        raise InvalidDenominationCountryRuleContextError(
            f"{name} must not contain leading or trailing whitespace."
        )
    if len(value) > _MAX_SCOPE_TEXT_CHARS:
        raise InvalidDenominationCountryRuleContextError(
            f"{name} exceeds its 128-character limit."
        )
    if unicodedata.normalize("NFC", value) != value:
        raise InvalidDenominationCountryRuleContextError(
            f"{name} must already be NFC-normalized."
        )
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise InvalidDenominationCountryRuleContextError(
            f"{name} must not contain control characters."
        )
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise InvalidDenominationCountryRuleContextError(
            f"{name} must not contain surrogate code points."
        )
    return value


def _validate_compatibility(value: object) -> DenominationCountryCompatibility:
    if isinstance(value, bool) or not isinstance(
        value, DenominationCountryCompatibility
    ):
        raise InvalidDenominationCountryRuleContextError(
            "compatibility must be a DenominationCountryCompatibility value."
        )
    return value


def _scope_key(rule: DenominationCountryRule) -> tuple[str, str]:
    return (rule.country, rule.denomination)
