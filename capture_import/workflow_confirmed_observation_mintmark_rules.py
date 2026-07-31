"""Immutable caller-supplied contracts for mintmark assertions.

This module defines exact mintmark scopes and exact mintmark strings. It
contains no evaluator, default catalog, persistence, runtime integration,
readiness authority, or historical lookup behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


__all__ = [
    "MintmarkRuleContractError",
    "InvalidMintmarkRuleContextError",
    "DuplicateMintmarkRuleError",
    "AmbiguousMintmarkRuleError",
    "MintmarkRule",
    "MintmarkRuleCatalog",
]


_RULE_ID = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_MIN_YEAR = 1000
_MAX_YEAR = 2999
_MAX_SCOPE_TEXT_CHARS = 128
_MAX_MINTMARK_CHARS = 128


class MintmarkRuleContractError(ValueError):
    """A mintmark rule or catalog contract is malformed."""

    __slots__ = ()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Mintmark rule contract errors are immutable.")


class InvalidMintmarkRuleContextError(MintmarkRuleContractError):
    """A rule or catalog contains malformed local contract data."""


class DuplicateMintmarkRuleError(MintmarkRuleContractError):
    """A catalog repeats a rule ID or exact mintmark scope."""


class AmbiguousMintmarkRuleError(MintmarkRuleContractError):
    """A catalog mixes generic and specific mintmark scopes for one issue family."""


@dataclass(frozen=True, slots=True)
class MintmarkRule:
    """One exact, transient caller-supplied mintmark assertion."""

    rule_id: str
    country: str
    denomination: str
    series_type: str | None
    year: int | None
    monarch: str | None
    mintmark: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate exact scope values and deterministic mintmark identity."""

        _validate_rule_id(self.rule_id)
        _validate_scope_text(self.country, "country")
        _validate_scope_text(self.denomination, "denomination")
        if self.series_type is not None:
            _validate_scope_text(self.series_type, "series_type")
        if self.year is not None:
            _validate_year(self.year)
        if self.monarch is not None:
            _validate_scope_text(self.monarch, "monarch")
        _validate_mintmark(self.mintmark)


@dataclass(frozen=True, slots=True)
class MintmarkRuleCatalog:
    """Canonical immutable set of caller-supplied mintmark rules.

    An empty catalog means only that the caller supplied no mintmark coverage.
    Rules must be ordered lexically by ``rule_id``.  For one exact
    country/denomination pair, a catalog may contain either one generic rule
    or one or more distinct specific rules, never both.
    """

    rules: tuple[MintmarkRule, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate nested rules, uniqueness, ambiguity, and lexical order."""

        if not isinstance(self.rules, tuple):
            raise InvalidMintmarkRuleContextError(
                "rules must be an immutable tuple."
            )
        if any(not isinstance(rule, MintmarkRule) for rule in self.rules):
            raise InvalidMintmarkRuleContextError(
                "rules must contain MintmarkRule values."
            )

        rule_ids: set[str] = set()
        scopes: set[tuple[str, str, str | None, int | None, str | None]] = set()
        generic_pairs: set[tuple[str, str]] = set()
        specific_pairs: set[tuple[str, str]] = set()
        for rule in self.rules:
            rule.validate()
            if rule.rule_id in rule_ids:
                raise DuplicateMintmarkRuleError(
                    "rules must not contain duplicate rule IDs."
                )
            rule_ids.add(rule.rule_id)

            scope = _scope_key(rule)
            if scope in scopes:
                raise DuplicateMintmarkRuleError(
                    "rules must not contain duplicate exact scopes."
                )
            scopes.add(scope)

            pair = (rule.country, rule.denomination)
            if _is_generic(rule):
                generic_pairs.add(pair)
            else:
                specific_pairs.add(pair)

        if generic_pairs.intersection(specific_pairs):
            raise AmbiguousMintmarkRuleError(
                "generic and specific mintmark rules must not coexist for "
                "one country and denomination."
            )

        expected_order = tuple(
            sorted(self.rules, key=lambda rule: rule.rule_id)
        )
        if self.rules != expected_order:
            raise InvalidMintmarkRuleContextError(
                "rules must use lexical rule_id order."
            )

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """Return caller-supplied rule IDs in validated catalog order."""

        return tuple(rule.rule_id for rule in self.rules)


def _validate_rule_id(value: object) -> str:
    if not isinstance(value, str) or _RULE_ID.fullmatch(value) is None:
        raise InvalidMintmarkRuleContextError(
            "rule_id must match [a-z][a-z0-9._-]{0,127}."
        )
    return value


def _validate_scope_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise InvalidMintmarkRuleContextError(f"{name} must be a string.")
    if not value or not value.strip():
        raise InvalidMintmarkRuleContextError(
            f"{name} must not be blank."
        )
    if value != value.strip():
        raise InvalidMintmarkRuleContextError(
            f"{name} must not contain leading or trailing whitespace."
        )
    if len(value) > _MAX_SCOPE_TEXT_CHARS:
        raise InvalidMintmarkRuleContextError(
            f"{name} exceeds its 128-character limit."
        )
    if unicodedata.normalize("NFC", value) != value:
        raise InvalidMintmarkRuleContextError(
            f"{name} must already be NFC-normalized."
        )
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise InvalidMintmarkRuleContextError(
            f"{name} must not contain control characters."
        )
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise InvalidMintmarkRuleContextError(
            f"{name} must not contain surrogate code points."
        )
    return value


def _validate_year(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidMintmarkRuleContextError(
            "year must be an exact integer."
        )
    if not _MIN_YEAR <= value <= _MAX_YEAR:
        raise InvalidMintmarkRuleContextError(
            "year must be between 1000 and 2999."
        )
    return value


def _validate_mintmark(value: object) -> str:
    if not isinstance(value, str):
        raise InvalidMintmarkRuleContextError("mintmark must be a string.")
    if not value or not value.strip():
        raise InvalidMintmarkRuleContextError(
            "mintmark must not be blank."
        )
    if value != value.strip():
        raise InvalidMintmarkRuleContextError(
            "mintmark must not contain leading or trailing whitespace."
        )
    if len(value) > _MAX_MINTMARK_CHARS:
        raise InvalidMintmarkRuleContextError(
            "mintmark exceeds its 128-character limit."
        )
    if unicodedata.normalize("NFC", value) != value:
        raise InvalidMintmarkRuleContextError(
            "mintmark must already be NFC-normalized."
        )
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise InvalidMintmarkRuleContextError(
            "mintmark must not contain control characters."
        )
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise InvalidMintmarkRuleContextError(
            "mintmark must not contain surrogate code points."
        )
    if value.casefold() in {"none", "no mintmark"}:
        raise InvalidMintmarkRuleContextError(
            "mintmark must be an exact mintmark token, not an empty-marker alias."
        )
    return value


def _is_generic(rule: MintmarkRule) -> bool:
    return rule.series_type is None and rule.year is None and rule.monarch is None


def _scope_key(
    rule: MintmarkRule,
) -> tuple[str, str, str | None, int | None, str | None]:
    return (
        rule.country,
        rule.denomination,
        rule.series_type,
        rule.year,
        rule.monarch,
    )
