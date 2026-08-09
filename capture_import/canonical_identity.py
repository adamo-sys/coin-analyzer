"""Provider-neutral canonical identity representation.

The functions in this module normalize only controlled, semantically
equivalent representations.  They preserve the provider's raw value and
return an explicit unmapped result for unknown or ambiguous input.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
import re
from typing import Generic, TypeVar
import unicodedata


class CanonicalizationStatus(str, Enum):
    MAPPED = "MAPPED"
    UNMAPPED = "UNMAPPED"


@dataclass(frozen=True, slots=True)
class CanonicalJurisdiction:
    canonical_id: str
    display_name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "canonical_id": self.canonical_id,
            "display_name": self.display_name,
        }


@dataclass(frozen=True, slots=True)
class CanonicalDenomination:
    numeric_value: Fraction
    unit_id: str
    display_name: str

    def to_dict(self) -> dict[str, object]:
        return {
            "numeric_value": {
                "numerator": self.numeric_value.numerator,
                "denominator": self.numeric_value.denominator,
            },
            "unit_id": self.unit_id,
            "display_name": self.display_name,
        }


CanonicalValue = TypeVar("CanonicalValue")


@dataclass(frozen=True, slots=True)
class CanonicalizedField(Generic[CanonicalValue]):
    raw_value: str | None
    canonical_value: CanonicalValue | None
    normalization_rules: tuple[str, ...]
    status: CanonicalizationStatus

    @property
    def is_mapped(self) -> bool:
        return self.status is CanonicalizationStatus.MAPPED

    def to_dict(self) -> dict[str, object]:
        canonical = self.canonical_value
        serialized = canonical.to_dict() if canonical is not None else None
        return {
            "raw_value": self.raw_value,
            "canonical_value": serialized,
            "normalization_rules": list(self.normalization_rules),
            "status": self.status.value,
        }


_JURISDICTIONS: dict[str, CanonicalJurisdiction] = {
    "US": CanonicalJurisdiction("US", "United States"),
    "PH": CanonicalJurisdiction("PH", "Philippines"),
}

_JURISDICTION_ALIASES: dict[str, tuple[str, str]] = {
    "united states": ("US", "jurisdiction.canonical-name"),
    "united states of america": ("US", "jurisdiction.official-long-name"),
    "usa": ("US", "jurisdiction.abbreviation"),
    "u s a": ("US", "jurisdiction.abbreviation"),
    "philippines": ("PH", "jurisdiction.canonical-name"),
}

_NUMBER_WORDS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

_UNIT_ALIASES: dict[str, tuple[str, str]] = {
    "rupee": ("rupee", "rupee"),
    "rupees": ("rupee", "rupees"),
    "cent": ("cent", "cent"),
    "cents": ("cent", "cents"),
    "dollar": ("dollar", "dollar"),
    "dollars": ("dollar", "dollars"),
    "penny": ("pence", "penny"),
    "pence": ("pence", "pence"),
    "franc": ("franc", "franc"),
    "francs": ("franc", "francs"),
    "centime": ("centime", "centime"),
    "centimes": ("centime", "centimes"),
    "peso": ("peso", "peso"),
    "pesos": ("peso", "pesos"),
}

_DISPLAY_UNITS: dict[str, tuple[str, str]] = {
    "rupee": ("rupee", "rupees"),
    "cent": ("cent", "cents"),
    "dollar": ("dollar", "dollars"),
    "pence": ("pence", "pence"),
    "franc": ("franc", "francs"),
    "centime": ("centime", "centimes"),
    "peso": ("peso", "pesos"),
}

_NUMERIC_RE = re.compile(r"^(?:\d+(?:\.\d+)?|\d+/\d+)$")


def canonicalize_jurisdiction(
    raw_value: str | None,
) -> CanonicalizedField[CanonicalJurisdiction]:
    """Map an exact controlled jurisdiction alias, never a historical relation."""

    if not isinstance(raw_value, str) or not raw_value.strip():
        return _unmapped(raw_value)
    key = _normalized_words(raw_value)
    alias = _JURISDICTION_ALIASES.get(key)
    if alias is None:
        return _unmapped(raw_value)
    canonical_id, rule = alias
    return CanonicalizedField(
        raw_value=raw_value,
        canonical_value=_JURISDICTIONS[canonical_id],
        normalization_rules=("text.unicode-case-space-punctuation", rule),
        status=CanonicalizationStatus.MAPPED,
    )


def canonicalize_denomination(
    raw_value: str | None,
    *,
    jurisdiction_id: str | None = None,
) -> CanonicalizedField[CanonicalDenomination]:
    """Normalize an anchored numeric-value/unit expression.

    Language-specific unit aliases are accepted only with the required
    canonical jurisdiction context.  Unknown input remains explicitly
    unmapped.
    """

    if not isinstance(raw_value, str) or not raw_value.strip():
        return _unmapped(raw_value)
    text = _normalized_denomination_text(raw_value)
    rules: list[str] = ["text.unicode-case-space-punctuation"]

    if text == "sixpence":
        amount = Fraction(6)
        unit_id = "pence"
        rules.append("denomination.compound.sixpence")
    else:
        pieces = text.split()
        if len(pieces) != 2:
            return _unmapped(raw_value)
        amount = _parse_amount(pieces[0], rules)
        if amount is None:
            return _unmapped(raw_value)
        unit_text = pieces[1]
        if unit_text == "piso":
            if jurisdiction_id != "PH":
                return _unmapped(raw_value)
            unit_id = "peso"
            rules.append("denomination.unit-alias.ph-piso-peso")
        else:
            unit = _UNIT_ALIASES.get(unit_text)
            if unit is None:
                return _unmapped(raw_value)
            unit_id, canonical_spelling = unit
            rules.append(
                "denomination.unit-canonical"
                if unit_text == canonical_spelling
                else "denomination.unit-inflection"
            )

    canonical = CanonicalDenomination(
        numeric_value=amount,
        unit_id=unit_id,
        display_name=_denomination_display(amount, unit_id),
    )
    return CanonicalizedField(
        raw_value=raw_value,
        canonical_value=canonical,
        normalization_rules=tuple(rules),
        status=CanonicalizationStatus.MAPPED,
    )


def _unmapped(raw_value: str | None) -> CanonicalizedField:
    return CanonicalizedField(
        raw_value=raw_value,
        canonical_value=None,
        normalization_rules=(),
        status=CanonicalizationStatus.UNMAPPED,
    )


def _normalized_words(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    text = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in text
    )
    return " ".join(text.split())


def _normalized_denomination_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold().replace("⁄", "/")
    text = "".join(
        character
        if character == "/" or character == "." or not unicodedata.category(character).startswith("P")
        else " "
        for character in text
    )
    return " ".join(text.split())


def _parse_amount(text: str, rules: list[str]) -> Fraction | None:
    if text == "half":
        rules.append("denomination.fraction-word.half")
        return Fraction(1, 2)
    word_value = _NUMBER_WORDS.get(text)
    if word_value is not None:
        rules.append("denomination.number-word")
        return Fraction(word_value)
    if not _NUMERIC_RE.fullmatch(text):
        return None
    try:
        amount = Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None
    if amount < 0:
        return None
    rules.append(
        "denomination.fraction-numeric" if "/" in text else "denomination.numeric"
    )
    return amount


def _denomination_display(amount: Fraction, unit_id: str) -> str:
    singular, plural = _DISPLAY_UNITS[unit_id]
    if amount.denominator == 1:
        number = str(amount.numerator)
    else:
        number = f"{amount.numerator}/{amount.denominator}"
    unit = singular if amount <= 1 else plural
    return f"{number} {unit}"
