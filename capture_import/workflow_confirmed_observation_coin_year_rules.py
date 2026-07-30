"""Immutable caller-supplied contracts for coin-specific issue-year rules.

This module defines exact issue-family scopes and exact allowed-year sets.  It
contains no historical facts, evaluator, default catalog, persistence, runtime
integration, or readiness authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


__all__ = [
    "CoinYearRuleContractError",
    "InvalidCoinYearRuleContextError",
    "DuplicateCoinYearRuleError",
    "AmbiguousCoinYearRuleError",
    "CoinYearRule",
    "CoinYearRuleCatalog",
]


_RULE_ID = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_MIN_YEAR = 1000
_MAX_YEAR = 2999
_MAX_SCOPE_TEXT_CHARS = 128


class CoinYearRuleContractError(ValueError):
    """A coin-year rule or catalog contract is malformed."""

    __slots__ = ()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Coin-year rule contract errors are immutable.")


class InvalidCoinYearRuleContextError(CoinYearRuleContractError):
    """A rule or catalog contains malformed local contract data."""


class DuplicateCoinYearRuleError(CoinYearRuleContractError):
    """A catalog repeats a rule ID or exact issue-family scope."""


class AmbiguousCoinYearRuleError(CoinYearRuleContractError):
    """A catalog mixes generic and specific rules for one issue family."""


@dataclass(frozen=True, slots=True)
class CoinYearRule:
    """One exact, transient caller-supplied issue-year rule.

    ``series_type=None`` declares a generic country/denomination scope.  A
    string declares one exact series-specific scope.  Values are validated but
    never trimmed, normalized, case-folded, inferred, or reconstructed.
    """

    rule_id: str
    country: str
    denomination: str
    series_type: str | None
    allowed_years: tuple[int, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate exact scope text and deterministic year ordering."""

        _validate_rule_id(self.rule_id)
        _validate_scope_text(self.country, "country")
        _validate_scope_text(self.denomination, "denomination")
        if self.series_type is not None:
            _validate_scope_text(self.series_type, "series_type")
        _validate_allowed_years(self.allowed_years)


@dataclass(frozen=True, slots=True)
class CoinYearRuleCatalog:
    """Canonical immutable collection of caller-supplied coin-year rules.

    An empty catalog means only that the caller supplied no coin-year
    coverage.  Rules must be ordered lexically by ``rule_id``.  For one exact
    country/denomination pair, a catalog may contain either one generic rule
    or one or more distinct series-specific rules, never both.
    """

    rules: tuple[CoinYearRule, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate nested rules, uniqueness, ambiguity, and lexical order."""

        if not isinstance(self.rules, tuple):
            raise InvalidCoinYearRuleContextError(
                "rules must be an immutable tuple."
            )
        if any(not isinstance(rule, CoinYearRule) for rule in self.rules):
            raise InvalidCoinYearRuleContextError(
                "rules must contain CoinYearRule values."
            )

        rule_ids: set[str] = set()
        scopes: set[tuple[str, str, str | None]] = set()
        generic_pairs: set[tuple[str, str]] = set()
        specific_pairs: set[tuple[str, str]] = set()
        for rule in self.rules:
            rule.validate()
            if rule.rule_id in rule_ids:
                raise DuplicateCoinYearRuleError(
                    "rules must not contain duplicate rule IDs."
                )
            rule_ids.add(rule.rule_id)

            scope = _scope_key(rule)
            if scope in scopes:
                raise DuplicateCoinYearRuleError(
                    "rules must not contain duplicate exact scopes."
                )
            scopes.add(scope)

            pair = (rule.country, rule.denomination)
            if rule.series_type is None:
                generic_pairs.add(pair)
            else:
                specific_pairs.add(pair)

        if generic_pairs.intersection(specific_pairs):
            raise AmbiguousCoinYearRuleError(
                "generic and series-specific rules must not coexist for "
                "one country and denomination."
            )

        expected_order = tuple(
            sorted(self.rules, key=lambda rule: rule.rule_id)
        )
        if self.rules != expected_order:
            raise InvalidCoinYearRuleContextError(
                "rules must use lexical rule_id order."
            )

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """Return caller-supplied rule IDs in validated catalog order."""

        return tuple(rule.rule_id for rule in self.rules)


def _validate_rule_id(value: object) -> str:
    if not isinstance(value, str) or _RULE_ID.fullmatch(value) is None:
        raise InvalidCoinYearRuleContextError(
            "rule_id must match [a-z][a-z0-9._-]{0,127}."
        )
    return value


def _validate_scope_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise InvalidCoinYearRuleContextError(
            f"{name} must be a string."
        )
    if not value or not value.strip():
        raise InvalidCoinYearRuleContextError(
            f"{name} must not be blank."
        )
    if value != value.strip():
        raise InvalidCoinYearRuleContextError(
            f"{name} must not contain leading or trailing whitespace."
        )
    if len(value) > _MAX_SCOPE_TEXT_CHARS:
        raise InvalidCoinYearRuleContextError(
            f"{name} exceeds its 128-character limit."
        )
    if unicodedata.normalize("NFC", value) != value:
        raise InvalidCoinYearRuleContextError(
            f"{name} must already be NFC-normalized."
        )
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise InvalidCoinYearRuleContextError(
            f"{name} must not contain control characters."
        )
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise InvalidCoinYearRuleContextError(
            f"{name} must not contain surrogate code points."
        )
    return value


def _validate_allowed_years(value: object) -> None:
    if not isinstance(value, tuple):
        raise InvalidCoinYearRuleContextError(
            "allowed_years must be an immutable tuple."
        )
    if not value:
        raise InvalidCoinYearRuleContextError(
            "allowed_years must contain at least one year."
        )
    for year in value:
        if isinstance(year, bool) or not isinstance(year, int):
            raise InvalidCoinYearRuleContextError(
                "allowed_years must contain exact integers."
            )
        if not _MIN_YEAR <= year <= _MAX_YEAR:
            raise InvalidCoinYearRuleContextError(
                "allowed_years must be between 1000 and 2999."
            )
    if any(current >= following for current, following in zip(value, value[1:])):
        raise InvalidCoinYearRuleContextError(
            "allowed_years must be strictly increasing without duplicates."
        )


def _scope_key(rule: CoinYearRule) -> tuple[str, str, str | None]:
    return (rule.country, rule.denomination, rule.series_type)
