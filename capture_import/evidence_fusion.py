"""Deterministic, provider-neutral visual and OCR evidence comparison."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from .canonical_identity import (
    canonicalize_denomination,
    canonicalize_jurisdiction,
)


REQUIRED_FUSION_FIELDS = ("country", "denomination", "year")


class FusionFieldStatus(str, Enum):
    AGREED = "AGREED"
    VISUAL_ONLY = "VISUAL_ONLY"
    OCR_ONLY = "OCR_ONLY"
    CONFLICT = "CONFLICT"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class FusedEvidenceValue:
    field_name: str
    source: str
    raw_value: str
    comparable_value: str
    provider_id: str
    model_id: str | None = None
    rank: int | None = None
    image_role: str | None = None
    artifact_key: str | None = None
    confidence_score: float | None = None
    normalization_rules: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "field_name": self.field_name,
            "source": self.source,
            "raw_value": self.raw_value,
            "comparable_value": self.comparable_value,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "rank": self.rank,
            "image_role": self.image_role,
            "artifact_key": self.artifact_key,
            "confidence_score": self.confidence_score,
            "normalization_rules": list(self.normalization_rules),
        }


@dataclass(frozen=True, slots=True)
class FusedFieldEvidence:
    field_name: str
    status: FusionFieldStatus
    visual_values: tuple[FusedEvidenceValue, ...]
    ocr_values: tuple[FusedEvidenceValue, ...]
    selected_value: str | None
    selected_comparable_value: str | None
    lower_rank_visual_agreements: tuple[int, ...]
    ambiguous: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "field_name": self.field_name,
            "status": self.status.value,
            "visual_values": [item.to_dict() for item in self.visual_values],
            "ocr_values": [item.to_dict() for item in self.ocr_values],
            "selected_value": self.selected_value,
            "selected_comparable_value": self.selected_comparable_value,
            "lower_rank_visual_agreements": list(self.lower_rank_visual_agreements),
            "ambiguous": self.ambiguous,
        }


@dataclass(frozen=True, slots=True)
class FusedIdentityEvidence:
    fields: tuple[FusedFieldEvidence, ...]
    unresolved: bool
    conflict: bool
    review_required: bool

    def field(self, name: str) -> FusedFieldEvidence:
        return next(item for item in self.fields if item.field_name == name)

    def to_dict(self) -> dict[str, object]:
        return {
            "fields": [item.to_dict() for item in self.fields],
            "unresolved": self.unresolved,
            "conflict": self.conflict,
            "review_required": self.review_required,
        }


def fuse_identity_evidence(
    *,
    visual_candidates: Sequence[Mapping[str, object]],
    ocr_candidates: Sequence[Mapping[str, object]],
    ocr_conflicts: Sequence[Mapping[str, object]] = (),
) -> FusedIdentityEvidence:
    """Compare evidence without selecting across any disagreement."""

    visual = _visual_evidence(visual_candidates)
    ocr = _ocr_evidence(ocr_candidates)
    explicit_conflicts = {
        str(item.get("field_name"))
        for item in ocr_conflicts
        if isinstance(item, Mapping)
        and item.get("field_name") in REQUIRED_FUSION_FIELDS
    }
    fields = tuple(
        _fuse_field(
            field,
            visual.get(field, ()),
            ocr.get(field, ()),
            explicit_ocr_conflict=field in explicit_conflicts,
        )
        for field in REQUIRED_FUSION_FIELDS
    )
    unresolved = any(item.selected_comparable_value is None for item in fields)
    conflict = any(item.status is FusionFieldStatus.CONFLICT for item in fields)
    review_required = conflict or any(
        item.status in {FusionFieldStatus.OCR_ONLY, FusionFieldStatus.UNRESOLVED}
        for item in fields
    )
    return FusedIdentityEvidence(
        fields=fields,
        unresolved=unresolved,
        conflict=conflict,
        review_required=review_required,
    )


def comparable_identity_value(
    field_name: str,
    raw_value: object,
    *,
    country_raw: object = None,
) -> tuple[str | None, tuple[str, ...]]:
    """Return one exact-or-canonical comparison key and applied rule provenance."""

    if not isinstance(raw_value, str) or not raw_value.strip():
        return None, ()
    normalized = _normalized(raw_value)
    if field_name == "country":
        result = canonicalize_jurisdiction(raw_value)
        if result.is_mapped:
            return (
                f"jurisdiction:{result.canonical_value.canonical_id}",
                result.normalization_rules,
            )
        return f"raw:{normalized}", ()
    if field_name == "denomination":
        country = canonicalize_jurisdiction(
            country_raw if isinstance(country_raw, str) else None
        )
        result = canonicalize_denomination(
            raw_value,
            jurisdiction_id=(
                country.canonical_value.canonical_id if country.is_mapped else None
            ),
        )
        if result.is_mapped:
            value = result.canonical_value.numeric_value
            return (
                f"denomination:{value.numerator}/{value.denominator}:{result.canonical_value.unit_id}",
                result.normalization_rules,
            )
        return f"raw:{normalized}", ()
    if field_name == "year":
        return f"year:{normalized}", ()
    raise ValueError(f"unsupported fusion field: {field_name}")


def _visual_evidence(
    candidates: Sequence[Mapping[str, object]],
) -> dict[str, tuple[FusedEvidenceValue, ...]]:
    by_field: dict[str, list[FusedEvidenceValue]] = {
        field: [] for field in REQUIRED_FUSION_FIELDS
    }
    ordered = sorted(
        (item for item in candidates if isinstance(item, Mapping)),
        key=lambda item: int(item.get("rank", 0)),
    )
    for candidate in ordered:
        rank = candidate.get("rank")
        country_raw = candidate.get("country")
        for field in REQUIRED_FUSION_FIELDS:
            raw = candidate.get(field)
            comparable, rules = comparable_identity_value(
                field, raw, country_raw=country_raw
            )
            if comparable is None:
                continue
            by_field[field].append(
                FusedEvidenceValue(
                    field_name=field,
                    source="VISUAL",
                    raw_value=str(raw).strip(),
                    comparable_value=comparable,
                    provider_id=str(candidate.get("provider_id") or "visual"),
                    model_id=_optional_text(candidate.get("model_id")),
                    rank=(
                        rank
                        if isinstance(rank, int) and not isinstance(rank, bool)
                        else None
                    ),
                    confidence_score=_optional_number(candidate.get("confidence")),
                    normalization_rules=rules,
                )
            )
    return {field: tuple(values) for field, values in by_field.items()}


def _ocr_evidence(
    candidates: Sequence[Mapping[str, object]],
) -> dict[str, tuple[FusedEvidenceValue, ...]]:
    rows = [item for item in candidates if isinstance(item, Mapping)]
    country_values = {
        str(item.get("normalized_value")).strip()
        for item in rows
        if item.get("field_name") == "country"
        and isinstance(item.get("normalized_value"), str)
        and str(item.get("normalized_value")).strip()
    }
    country_context = next(iter(country_values)) if len(country_values) == 1 else None
    by_field: dict[str, list[FusedEvidenceValue]] = {
        field: [] for field in REQUIRED_FUSION_FIELDS
    }
    seen: set[tuple[object, ...]] = set()
    for candidate in rows:
        field = candidate.get("field_name")
        if field not in REQUIRED_FUSION_FIELDS:
            continue
        raw = candidate.get("normalized_value")
        comparable, rules = comparable_identity_value(
            str(field), raw, country_raw=country_context
        )
        if comparable is None:
            continue
        item = FusedEvidenceValue(
            field_name=str(field),
            source="OCR",
            raw_value=str(raw).strip(),
            comparable_value=comparable,
            provider_id=str(candidate.get("provider_id") or "ocr"),
            image_role=_optional_text(candidate.get("image_role")),
            artifact_key=_optional_text(candidate.get("artifact_key")),
            confidence_score=_optional_number(candidate.get("confidence_score")),
            normalization_rules=rules,
        )
        identity = (
            item.field_name,
            item.comparable_value,
            item.provider_id,
            item.image_role,
            item.artifact_key,
        )
        if identity not in seen:
            seen.add(identity)
            by_field[str(field)].append(item)
    return {
        field: tuple(
            sorted(
                values,
                key=lambda item: (
                    item.comparable_value,
                    item.provider_id,
                    item.image_role or "",
                    item.artifact_key or "",
                ),
            )
        )
        for field, values in by_field.items()
    }


def _fuse_field(
    field_name: str,
    visual_values: tuple[FusedEvidenceValue, ...],
    ocr_values: tuple[FusedEvidenceValue, ...],
    *,
    explicit_ocr_conflict: bool,
) -> FusedFieldEvidence:
    top = next((item for item in visual_values if item.rank == 1), None)
    ocr_keys = {item.comparable_value for item in ocr_values}
    lower_agreements = tuple(
        sorted(
            {
                item.rank
                for item in visual_values
                if item.rank is not None
                and item.rank > 1
                and item.comparable_value in ocr_keys
            }
        )
    )
    selected: FusedEvidenceValue | None = None
    if top is not None and ocr_values:
        if (
            not explicit_ocr_conflict
            and len(ocr_keys) == 1
            and top.comparable_value in ocr_keys
        ):
            status = FusionFieldStatus.AGREED
            selected = top
        else:
            status = FusionFieldStatus.CONFLICT
    elif top is not None:
        status = FusionFieldStatus.VISUAL_ONLY
        selected = top
    elif ocr_values:
        if not explicit_ocr_conflict and len(ocr_keys) == 1:
            status = FusionFieldStatus.OCR_ONLY
            selected = ocr_values[0]
        else:
            status = FusionFieldStatus.CONFLICT
    else:
        status = FusionFieldStatus.UNRESOLVED
    return FusedFieldEvidence(
        field_name=field_name,
        status=status,
        visual_values=visual_values,
        ocr_values=ocr_values,
        selected_value=None if selected is None else selected.raw_value,
        selected_comparable_value=(
            None if selected is None else selected.comparable_value
        ),
        lower_rank_visual_agreements=lower_agreements,
        ambiguous=status in {FusionFieldStatus.CONFLICT, FusionFieldStatus.UNRESOLVED},
    )


def _normalized(value: object) -> str:
    return " ".join(str(value).strip().casefold().split())


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None
