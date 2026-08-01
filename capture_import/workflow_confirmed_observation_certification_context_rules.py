"""Immutable caller-supplied contracts for certification-context evaluation.

These contracts define exact certification-context scopes and caller-supplied
fallback evaluation context. They contain no evaluator, default catalog,
persistence, runtime integration, readiness authority, or historical/issuer
knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


__all__ = [
    "CertificationContextRuleContractError",
    "InvalidCertificationContextRuleContextError",
    "DuplicateCertificationContextRuleError",
    "AmbiguousCertificationContextRuleError",
    "CertificationContextRule",
    "CertificationContextRuleCatalog",
    "CertificationEvaluationContext",
]


_RULE_ID = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_MAX_SCOPE_TEXT_CHARS = 128


class CertificationContextRuleContractError(ValueError):
    """A certification-context rule or catalog contract is malformed."""

    __slots__ = ()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            "Certification-context rule contract errors are immutable."
        )


class InvalidCertificationContextRuleContextError(
    CertificationContextRuleContractError
):
    """A rule, catalog, or evaluation context contains malformed data."""


class DuplicateCertificationContextRuleError(
    CertificationContextRuleContractError
):
    """A catalog repeats a rule ID or exact certification-context scope."""


class AmbiguousCertificationContextRuleError(
    CertificationContextRuleContractError
):
    """A catalog mixes generic and specific rules for one issue family."""


@dataclass(frozen=True, slots=True)
class CertificationContextRule:
    """One exact, transient caller-supplied certification-context rule."""

    rule_id: str
    grading_company: str
    country: str
    denomination: str
    series_type: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate exact scope values and deterministic rule identity."""

        _validate_rule_id(self.rule_id)
        _validate_scope_text(self.grading_company, "grading_company")
        _validate_scope_text(self.country, "country")
        _validate_scope_text(self.denomination, "denomination")
        if self.series_type is not None:
            _validate_scope_text(self.series_type, "series_type")


@dataclass(frozen=True, slots=True)
class CertificationContextRuleCatalog:
    """Canonical immutable collection of caller-supplied certification rules.

    An empty catalog means only that the caller supplied no certification-context
    coverage. Rules must be ordered lexically by ``rule_id``. For one exact
    country/denomination pair, a catalog may contain either one generic rule or
    one or more distinct series-specific rules, never both.
    """

    rules: tuple[CertificationContextRule, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate nested rules, uniqueness, ambiguity, and lexical order."""

        if not isinstance(self.rules, tuple):
            raise InvalidCertificationContextRuleContextError(
                "rules must be an immutable tuple."
            )
        if any(
            not isinstance(rule, CertificationContextRule)
            for rule in self.rules
        ):
            raise InvalidCertificationContextRuleContextError(
                "rules must contain CertificationContextRule values."
            )

        rule_ids: set[str] = set()
        scopes: set[tuple[str, str, str, str | None]] = set()
        generic_pairs: set[tuple[str, str]] = set()
        specific_pairs: set[tuple[str, str]] = set()
        for rule in self.rules:
            rule.validate()
            if rule.rule_id in rule_ids:
                raise DuplicateCertificationContextRuleError(
                    "rules must not contain duplicate rule IDs."
                )
            rule_ids.add(rule.rule_id)

            scope = _scope_key(rule)
            if scope in scopes:
                raise DuplicateCertificationContextRuleError(
                    "rules must not contain duplicate exact scopes."
                )
            scopes.add(scope)

            pair = (rule.country, rule.denomination)
            if rule.series_type is None:
                generic_pairs.add(pair)
            else:
                specific_pairs.add(pair)

        if generic_pairs.intersection(specific_pairs):
            raise AmbiguousCertificationContextRuleError(
                "generic and series-specific certification-context rules must "
                "not coexist for one country and denomination."
            )

        expected_order = tuple(
            sorted(self.rules, key=lambda rule: rule.rule_id)
        )
        if self.rules != expected_order:
            raise InvalidCertificationContextRuleContextError(
                "rules must use lexical rule_id order."
            )

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """Return caller-supplied rule IDs in validated catalog order."""

        return tuple(rule.rule_id for rule in self.rules)


@dataclass(frozen=True, slots=True)
class CertificationEvaluationContext:
    """Optional caller-supplied evaluation context for certification rules.

    This is not evidence and is not part of a confirmed-observation set. It is
    an explicit advisory evaluation input supplied by the caller.
    """

    grading_company: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate optional caller-supplied context values."""

        if self.grading_company is not None:
            _validate_scope_text(self.grading_company, "grading_company")


def _validate_rule_id(value: object) -> str:
    if not isinstance(value, str) or _RULE_ID.fullmatch(value) is None:
        raise InvalidCertificationContextRuleContextError(
            "rule_id must match [a-z][a-z0-9._-]{0,127}."
        )
    return value


def _validate_scope_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise InvalidCertificationContextRuleContextError(
            f"{name} must be a string."
        )
    if not value or not value.strip():
        raise InvalidCertificationContextRuleContextError(
            f"{name} must not be blank."
        )
    if value != value.strip():
        raise InvalidCertificationContextRuleContextError(
            f"{name} must not contain leading or trailing whitespace."
        )
    if len(value) > _MAX_SCOPE_TEXT_CHARS:
        raise InvalidCertificationContextRuleContextError(
            f"{name} exceeds its 128-character limit."
        )
    if unicodedata.normalize("NFC", value) != value:
        raise InvalidCertificationContextRuleContextError(
            f"{name} must already be NFC-normalized."
        )
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise InvalidCertificationContextRuleContextError(
            f"{name} must not contain control characters."
        )
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise InvalidCertificationContextRuleContextError(
            f"{name} must not contain surrogate code points."
        )
    return value


def _scope_key(rule: CertificationContextRule) -> tuple[str, str, str, str | None]:
    return (
        rule.grading_company,
        rule.country,
        rule.denomination,
        rule.series_type,
    )
