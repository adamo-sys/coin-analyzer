"""Frozen, representation-only identity policy for desktop acceptance v1."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Mapping
import unicodedata


POLICY_SCHEMA = "coin-analyzer-desktop-acceptance-canonicalization-policy"
POLICY_ID = "coin-analyzer-desktop-acceptance-canonicalization"
POLICY_VERSION = "1.0.0"
DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parent.parent
    / "benchmarks"
    / "real-world-desktop-v1"
    / "canonicalization-policy-v1.json"
)
_NORMALIZATION = (
    "unicode_nfkc",
    "trim_surrounding_whitespace",
    "collapse_internal_whitespace",
    "casefold",
    "preserve_punctuation",
)
_ASCII_YEAR = re.compile(r"^[0-9]{4}$", flags=re.ASCII)
_EXPECTED_JURISDICTIONS = {
    "can": "CAN",
    "canada": "CAN",
}
_EXPECTED_DENOMINATIONS = {
    ("CAN", "$1"): "1 dollar",
    ("CAN", "$2"): "2 dollars",
    ("CAN", "1 cent"): "1 cent",
    ("CAN", "1 cents"): "1 cent",
    ("CAN", "1 dollar"): "1 dollar",
    ("CAN", "10 cent"): "10 cents",
    ("CAN", "10 cents"): "10 cents",
    ("CAN", "2 dollar"): "2 dollars",
    ("CAN", "2 dollars"): "2 dollars",
    ("CAN", "25 cent"): "25 cents",
    ("CAN", "25 cents"): "25 cents",
    ("CAN", "5 cent"): "5 cents",
    ("CAN", "5 cents"): "5 cents",
    ("CAN", "50 cent"): "50 cents",
    ("CAN", "50 cents"): "50 cents",
    ("CAN", "cent"): "1 cent",
    ("CAN", "dime"): "10 cents",
    ("CAN", "half dollar"): "50 cents",
    ("CAN", "loonie"): "1 dollar",
    ("CAN", "nickel"): "5 cents",
    ("CAN", "quarter"): "25 cents",
    ("CAN", "toonie"): "2 dollars",
}


class DesktopAcceptanceCanonicalizationError(ValueError):
    """The versioned acceptance policy artifact is malformed or unsupported."""


@dataclass(frozen=True, slots=True)
class DesktopAcceptanceCanonicalizationPolicy:
    jurisdiction_aliases: Mapping[str, str]
    denomination_aliases: Mapping[tuple[str, str], str]
    path: Path
    policy_id: str = POLICY_ID
    version: str = POLICY_VERSION


@dataclass(frozen=True, slots=True)
class CanonicalAcceptanceIdentity:
    country: str
    denomination: str
    year: str

    def to_dict(self) -> dict[str, str]:
        return {
            "country": self.country,
            "denomination": self.denomination,
            "year": self.year,
        }


def load_desktop_acceptance_canonicalization_policy(
    path: str | Path = DEFAULT_POLICY_PATH,
) -> DesktopAcceptanceCanonicalizationPolicy:
    policy_path = Path(path).resolve()
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DesktopAcceptanceCanonicalizationError(
            f"cannot read canonicalization policy: {error}"
        ) from error
    required = {
        "schema", "policy_id", "version", "diagnostic_normalization",
        "jurisdiction_aliases", "denomination_aliases", "year_policy",
    }
    if not isinstance(payload, Mapping) or set(payload) != required:
        raise DesktopAcceptanceCanonicalizationError("policy fields do not match schema.")
    if (payload["schema"] != POLICY_SCHEMA or payload["policy_id"] != POLICY_ID
            or payload["version"] != POLICY_VERSION):
        raise DesktopAcceptanceCanonicalizationError("policy identity/version is unsupported.")
    if tuple(payload["diagnostic_normalization"]) != _NORMALIZATION:
        raise DesktopAcceptanceCanonicalizationError("diagnostic normalization is unsupported.")
    year = payload["year_policy"]
    if year != {"calendar": "proleptic-gregorian", "format": "four-character-ascii",
                "minimum": "0001", "maximum": "9999"}:
        raise DesktopAcceptanceCanonicalizationError("year policy is unsupported.")
    jurisdictions = _alias_map(
        payload["jurisdiction_aliases"], ("normalized",), "jurisdiction_aliases"
    )
    denominations = _alias_map(
        payload["denomination_aliases"], ("jurisdiction", "normalized"),
        "denomination_aliases",
    )
    if jurisdictions != _EXPECTED_JURISDICTIONS:
        raise DesktopAcceptanceCanonicalizationError(
            "v1 jurisdiction mapping does not match the frozen policy."
        )
    if denominations != _EXPECTED_DENOMINATIONS:
        raise DesktopAcceptanceCanonicalizationError(
            "v1 denomination mapping does not match the frozen policy."
        )
    return DesktopAcceptanceCanonicalizationPolicy(
        jurisdiction_aliases=jurisdictions,
        denomination_aliases=denominations,
        path=policy_path,
    )


def diagnostic_normalize(value: object) -> str | None:
    """Normalize representation only; punctuation is deliberately retained."""
    if not isinstance(value, str):
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split()).casefold()
    return normalized or None


def canonicalize_country(
    value: object, policy: DesktopAcceptanceCanonicalizationPolicy,
) -> str | None:
    normalized = diagnostic_normalize(value)
    return None if normalized is None else policy.jurisdiction_aliases.get(normalized)


def canonicalize_denomination(
    value: object, *, canonical_country: str | None,
    policy: DesktopAcceptanceCanonicalizationPolicy,
) -> str | None:
    normalized = diagnostic_normalize(value)
    if normalized is None or canonical_country is None:
        return None
    return policy.denomination_aliases.get((canonical_country, normalized))


def canonicalize_year(value: object) -> str | None:
    normalized = diagnostic_normalize(value)
    if normalized is None or _ASCII_YEAR.fullmatch(normalized) is None or normalized == "0000":
        return None
    return normalized


def canonicalize_complete_identity(
    identity: object,
    policy: DesktopAcceptanceCanonicalizationPolicy,
) -> CanonicalAcceptanceIdentity | None:
    if not isinstance(identity, Mapping) or set(identity) != {"country", "denomination", "year"}:
        return None
    country = canonicalize_country(identity["country"], policy)
    denomination = canonicalize_denomination(
        identity["denomination"], canonical_country=country, policy=policy
    )
    year = canonicalize_year(identity["year"])
    if country is None or denomination is None or year is None:
        return None
    return CanonicalAcceptanceIdentity(country, denomination, year)


def complete_identities_equivalent(
    expected: object,
    proposed: object,
    policy: DesktopAcceptanceCanonicalizationPolicy,
) -> bool:
    expected_canonical = canonicalize_complete_identity(expected, policy)
    proposed_canonical = canonicalize_complete_identity(proposed, policy)
    return (
        expected_canonical is not None
        and proposed_canonical is not None
        and expected_canonical == proposed_canonical
    )


def diagnostic_exact_identity_match(expected: object, proposed: object) -> bool:
    """Return the non-authoritative normalized exact-string diagnostic."""
    if not isinstance(expected, Mapping) or not isinstance(proposed, Mapping):
        return False
    fields = ("country", "denomination", "year")
    if set(expected) != set(fields) or set(proposed) != set(fields):
        return False
    normalized = [
        (diagnostic_normalize(expected[field]), diagnostic_normalize(proposed[field]))
        for field in fields
    ]
    return all(left is not None and left == right for left, right in normalized)


def _alias_map(raw: object, keys: tuple[str, ...], name: str) -> dict:
    if not isinstance(raw, list):
        raise DesktopAcceptanceCanonicalizationError(f"{name} must be an array.")
    result = {}
    serialized_keys = []
    for item in raw:
        required = set(keys) | {"canonical"}
        if not isinstance(item, Mapping) or set(item) != required:
            raise DesktopAcceptanceCanonicalizationError(f"{name} entry fields are invalid.")
        key_values = tuple(item[key] for key in keys)
        if any(not isinstance(value, str) or not value for value in (*key_values, item["canonical"])):
            raise DesktopAcceptanceCanonicalizationError(f"{name} entries require text.")
        key = key_values[0] if len(key_values) == 1 else key_values
        if key in result:
            raise DesktopAcceptanceCanonicalizationError(f"{name} aliases must be unique.")
        result[key] = item["canonical"]
        serialized_keys.append(key_values)
    if serialized_keys != sorted(serialized_keys):
        raise DesktopAcceptanceCanonicalizationError(f"{name} must be sorted.")
    return result
