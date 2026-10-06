"""Conservative equivalence of current recorded issue descriptions, v1.

This pure boundary does not verify identity, authenticity, specimen sameness,
record duplication, ownership, or quantity. Callers must explicitly project
current operative fields and supply an already-resolved effective status.
There is no persistence adapter or legacy-status derivation here.
"""

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar


class ItemType(str, Enum):
    COIN = "COIN"
    BANKNOTE = "BANKNOTE"


class EffectiveStatus(str, Enum):
    IDENTIFIED = "IDENTIFIED"
    PARTIAL = "PARTIAL"
    UNIDENTIFIED = "UNIDENTIFIED"


class IssueDecision(str, Enum):
    SAME_ISSUE = "SAME_ISSUE"
    DIFFERENT_ISSUE = "DIFFERENT_ISSUE"
    ABSTAIN = "ABSTAIN"


class IssueReason(str, Enum):
    COMPLETE_OPERATIVE_IDENTITY = "COMPLETE_OPERATIVE_IDENTITY"
    INVALID_VALUE = "INVALID_VALUE"
    MISSING_ITEM_TYPE = "MISSING_ITEM_TYPE"
    ITEM_TYPE_CONFLICT = "ITEM_TYPE_CONFLICT"
    INELIGIBLE_STATUS = "INELIGIBLE_STATUS"
    MISSING_REQUIRED_IDENTITY = "MISSING_REQUIRED_IDENTITY"
    TYPE_DESIGN_CONFLICT = "TYPE_DESIGN_CONFLICT"
    ORDINARY_IDENTITY_CONFLICT = "ORDINARY_IDENTITY_CONFLICT"
    ISSUER_CONFLICT = "ISSUER_CONFLICT"
    QUALIFIER_MISSING = "QUALIFIER_MISSING"
    UNSCOPED_REFERENCE_DISAGREEMENT = "UNSCOPED_REFERENCE_DISAGREEMENT"
    NUMISTA_DISAGREEMENT = "NUMISTA_DISAGREEMENT"
    CONTRADICTORY_IDENTITY_EVIDENCE = "CONTRADICTORY_IDENTITY_EVIDENCE"


@dataclass(frozen=True, slots=True, kw_only=True)
class IssueIdentity:
    """Explicit current identity input; keys are opaque, unnormalized strings.

    Runtime admission requires exact IssueIdentity, declared local enum members,
    and built-in str values. Subclasses and instance-controlled class claims are
    rejected. Enum fields also accept their exact uppercase built-in str value.
    None/malformed status is invalid, never legacy absence. Text fields accept
    strings or None; malformed runtime values are rejected by the comparator.
    No item-type or effective-status default is supplied.
    """

    subject_key: str
    item_type: ItemType | str | None
    effective_status: EffectiveStatus | str | None
    country: str | None = None
    denomination: str | None = None
    year: str | None = None
    type_design: str | None = None
    issuer: str | None = None
    reference: str | None = None
    numista_n: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedIssueIdentity:
    """Normalized operative evidence only, without subject keys.

    Unavailable or invalid fields project to None. INVALID_VALUE distinguishes
    invalid evidence in the result; it always takes precedence over comparison.
    """

    item_type: ItemType | None
    effective_status: EffectiveStatus | None
    country: str | None
    denomination: str | None
    year: str | None
    type_design: str | None
    issuer: str | None
    reference: str | None
    numista_n: str | None


@dataclass(frozen=True, slots=True)
class IssueEquivalenceResult:
    """Decision and reasons from the first applicable precedence tier.

    compared_values is canonically sorted, independent of caller order.
    subject_keys alone retains caller order. An invalid input/key has a None
    key; a non-projection input yields no compared_values. Valid keys survive
    exactly. No confidence or implicit boolean decision is provided.
    """

    decision: IssueDecision
    reason_codes: tuple[IssueReason, ...]
    compared_values: tuple[NormalizedIssueIdentity, ...]
    subject_keys: tuple[str | None, str | None]

    def __bool__(self) -> bool:
        raise TypeError("Inspect IssueEquivalenceResult.decision explicitly")


_UNAVAILABLE = frozenset({
    "unknown", "n/a", "na", "none", "not applicable", "unidentified",
    "null", "nan", "<na>", "?", "-", "not known",
})
_TEXT_FIELDS = ("country", "denomination", "year", "type_design", "issuer", "reference")
_REQUIRED_FIELDS = ("country", "denomination", "year", "type_design")
_PROJECTION_FIELDS = ("item_type", "effective_status", *_TEXT_FIELDS, "numista_n")
_EnumValue = TypeVar("_EnumValue", bound=Enum)


def _enum_value(value: object, enum: type[_EnumValue]) -> _EnumValue | None:
    # type() ignores instance-controlled __class__; identity avoids equality.
    if type(value) is enum:
        for member in enum:
            if value is member:
                return member
        return None
    if type(value) is str:
        try:
            return enum(value)
        except ValueError:
            pass
    return None


def _text(value: object) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    if type(value) is not str:
        return None, True
    normalized = " ".join(unicodedata.normalize("NFC", value).split()).casefold()
    if not normalized or normalized in _UNAVAILABLE:
        return None, False
    return normalized, False


def _positive_ascii_decimal(value: str) -> bool:
    # Avoid numeric conversion (including interpreter-dependent digit limits).
    return re.fullmatch(r"[0-9]+", value) is not None and bool(value.lstrip("0"))


def _numista(value: object) -> tuple[str | None, bool]:
    normalized, invalid = _text(value)
    if normalized is None:
        return None, invalid
    assert type(value) is str
    exact = " ".join(unicodedata.normalize("NFC", value).split())
    digits = exact.removeprefix("N#")
    if not _positive_ascii_decimal(digits):
        return None, True
    return digits.lstrip("0"), False


def _project(value: IssueIdentity) -> tuple[NormalizedIssueIdentity, bool, bool]:
    item_type = _enum_value(value.item_type, ItemType)
    status = _enum_value(value.effective_status, EffectiveStatus)
    missing_type = value.item_type is None or (
        type(value.item_type) is str and value.item_type == ""
    )
    invalid = ((item_type is None and not missing_type) or status is None
               or type(value.subject_key) is not str)
    text_values: dict[str, str | None] = {}
    for field in _TEXT_FIELDS:
        text, bad = _text(getattr(value, field))
        if field == "year" and text is not None and not _positive_ascii_decimal(text):
            text, bad = None, True
        text_values[field] = text
        invalid = invalid or bad
    numista, bad = _numista(value.numista_n)
    invalid = invalid or bad
    return NormalizedIssueIdentity(
        item_type, status, text_values["country"], text_values["denomination"],
        text_values["year"], text_values["type_design"], text_values["issuer"],
        text_values["reference"], numista,
    ), invalid, missing_type


def _sort_key(value: NormalizedIssueIdentity) -> tuple[str, ...]:
    return tuple(getattr(value, field) or "" for field in _PROJECTION_FIELDS)


def _disagrees(left: str | None, right: str | None) -> bool:
    return left is not None and right is not None and left != right


def compare_issue_identity(left: IssueIdentity, right: IssueIdentity) -> IssueEquivalenceResult:
    """Compare descriptions under v1 precedence; never inspect arbitrary records.

    DIFFERENT_ISSUE says only that current recorded descriptions differ, without
    claiming either is correct. SAME_ISSUE has exactly one route: complete equal
    ordinary identity, IDENTIFIED statuses, and compatible optional qualifiers.
    """
    keys = tuple(
        value.subject_key if type(value) is IssueIdentity
        and type(value.subject_key) is str else None
        for value in (left, right)
    )
    subject_keys = (keys[0], keys[1])
    if type(left) is not IssueIdentity or type(right) is not IssueIdentity:
        return IssueEquivalenceResult(
            IssueDecision.ABSTAIN, (IssueReason.INVALID_VALUE,), (), subject_keys,
        )

    a, invalid_a, missing_type_a = _project(left)
    b, invalid_b, missing_type_b = _project(right)
    evidence = tuple(sorted((a, b), key=_sort_key))

    def result(decision: IssueDecision, *reasons: IssueReason) -> IssueEquivalenceResult:
        return IssueEquivalenceResult(decision, reasons, evidence, subject_keys)

    # 1. Invalid/unavailable type, status, or field representations.
    invalid_reasons = []
    if missing_type_a or missing_type_b:
        invalid_reasons.append(IssueReason.MISSING_ITEM_TYPE)
    if invalid_a or invalid_b:
        invalid_reasons.append(IssueReason.INVALID_VALUE)
    if invalid_reasons:
        return result(IssueDecision.ABSTAIN, *invalid_reasons)

    # 2. Supported item-type disagreement outranks all valid field evidence.
    if a.item_type != b.item_type:
        return result(IssueDecision.DIFFERENT_ISSUE, IssueReason.ITEM_TYPE_CONFLICT)

    same_numista = a.numista_n is not None and a.numista_n == b.numista_n
    # 3. Populated required ordinary conflicts, in fixed semantic reason order.
    ordinary_reasons = []
    if any(_disagrees(getattr(a, field), getattr(b, field))
           for field in ("country", "denomination", "year")):
        ordinary_reasons.append(IssueReason.ORDINARY_IDENTITY_CONFLICT)
    if _disagrees(a.type_design, b.type_design):
        ordinary_reasons.append(IssueReason.TYPE_DESIGN_CONFLICT)
    if ordinary_reasons:
        if same_numista:
            return result(IssueDecision.ABSTAIN,
                          IssueReason.CONTRADICTORY_IDENTITY_EVIDENCE, *ordinary_reasons)
        return result(IssueDecision.DIFFERENT_ISSUE, *ordinary_reasons)

    # 4. Populated issuer disagreement follows required ordinary conflicts.
    if _disagrees(a.issuer, b.issuer):
        if same_numista:
            return result(IssueDecision.ABSTAIN,
                          IssueReason.CONTRADICTORY_IDENTITY_EVIDENCE,
                          IssueReason.ISSUER_CONFLICT)
        return result(IssueDecision.DIFFERENT_ISSUE, IssueReason.ISSUER_CONFLICT)

    # 5. Optional qualifier disagreements/asymmetry cannot establish sameness.
    qualifier_reasons = []
    if _disagrees(a.numista_n, b.numista_n):
        qualifier_reasons.append(IssueReason.NUMISTA_DISAGREEMENT)
    if _disagrees(a.reference, b.reference):
        qualifier_reasons.append(IssueReason.UNSCOPED_REFERENCE_DISAGREEMENT)
    if any((getattr(a, field) is None) != (getattr(b, field) is None)
           for field in ("issuer", "reference", "numista_n")):
        qualifier_reasons.append(IssueReason.QUALIFIER_MISSING)
    if qualifier_reasons:
        return result(IssueDecision.ABSTAIN, *qualifier_reasons)

    # 6. Valid explicit statuses must both be IDENTIFIED.
    if (a.effective_status != EffectiveStatus.IDENTIFIED
            or b.effective_status != EffectiveStatus.IDENTIFIED):
        return result(IssueDecision.ABSTAIN, IssueReason.INELIGIBLE_STATUS)

    # 7. Missing required fields never count as agreement.
    if any(getattr(value, field) is None
           for value in (a, b) for field in _REQUIRED_FIELDS):
        return result(IssueDecision.ABSTAIN, IssueReason.MISSING_REQUIRED_IDENTITY)

    # 8. The single positive route.
    return result(IssueDecision.SAME_ISSUE, IssueReason.COMPLETE_OPERATIVE_IDENTITY)
