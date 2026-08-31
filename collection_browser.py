"""Pure, immutable projections for browsing a mixed numismatic collection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Iterable, Sequence

from coin_collection import (
    CoinItem,
    Disposition,
    IdentificationStatus,
    ItemType,
    validate_utc_rfc3339,
)


ABSENCE_MARKER = "—"
ALL = "ALL"


class CollectionBrowserSort(str, Enum):
    """Closed sort vocabulary for collection browser projections."""

    COLLECTION_ORDER = "COLLECTION_ORDER"
    RECENTLY_UPDATED = "RECENTLY_UPDATED"
    ISSUER_COUNTRY = "ISSUER_COUNTRY"
    DENOMINATION = "DENOMINATION"
    DATE_SERIES = "DATE_SERIES"


def _optional_enum_filter(enum_type, value, field_name: str):
    if value is None or value == ALL:
        return None
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be ALL or a supported value")
    try:
        return enum_type(value)
    except ValueError:
        raise ValueError(f"{field_name} has an unsupported value") from None


@dataclass(frozen=True, slots=True)
class CollectionBrowserCriteria:
    """Validated, immutable criteria for one ephemeral browser projection."""

    search_text: str = ""
    item_type: ItemType | str | None = None
    disposition: Disposition | str | None = None
    identification_status: IdentificationStatus | str | None = None
    issuer_or_country: str = ""
    sort_order: CollectionBrowserSort | str = CollectionBrowserSort.COLLECTION_ORDER

    def __post_init__(self) -> None:
        if not isinstance(self.search_text, str):
            raise ValueError("search_text must be a string")
        if not isinstance(self.issuer_or_country, str):
            raise ValueError("issuer_or_country must be a string")

        object.__setattr__(self, "search_text", self.search_text.strip())
        issuer_or_country = self.issuer_or_country.strip()
        object.__setattr__(
            self,
            "issuer_or_country",
            "" if issuer_or_country == ALL else issuer_or_country,
        )
        object.__setattr__(
            self,
            "item_type",
            _optional_enum_filter(ItemType, self.item_type, "item_type"),
        )
        object.__setattr__(
            self,
            "disposition",
            _optional_enum_filter(Disposition, self.disposition, "disposition"),
        )
        object.__setattr__(
            self,
            "identification_status",
            _optional_enum_filter(
                IdentificationStatus,
                self.identification_status,
                "identification_status",
            ),
        )
        sort_order = self.sort_order
        if not isinstance(sort_order, CollectionBrowserSort):
            if not isinstance(sort_order, str):
                raise ValueError("sort_order must be a supported value")
            try:
                sort_order = CollectionBrowserSort(sort_order)
            except ValueError:
                raise ValueError("sort_order has an unsupported value") from None
        object.__setattr__(self, "sort_order", sort_order)


@dataclass(frozen=True, slots=True)
class CollectionBrowserRow:
    """Detached presentation data keyed solely by a stable collection item ID."""

    item_id: str
    thumbnail_path: str
    item_type: str
    issuer_country: str
    denomination: str
    date_series: str
    grade: str
    acquisition: str
    disposition: str
    identification_status: str


def _factual_text(value) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _display(value) -> str:
    return _factual_text(value) or ABSENCE_MARKER


def _issuer_country_text(item: CoinItem) -> str:
    issuer = _factual_text(item.issuer)
    country = _factual_text(item.country)
    if issuer and country and issuer.casefold() != country.casefold():
        return f"{issuer} / {country}"
    return issuer or country or ABSENCE_MARKER


def _search_values(item: CoinItem) -> tuple[str, ...]:
    return tuple(
        _factual_text(value)
        for value in (
            item.id,
            item.country,
            item.issuer,
            item.denomination,
            item.year,
            item.title,
            item.reference,
            item.notes,
            item.grade,
            item.numista_n,
        )
    )


def _matches(item: CoinItem, criteria: CollectionBrowserCriteria) -> bool:
    if criteria.search_text:
        needle = criteria.search_text.casefold()
        if not any(needle in value.casefold() for value in _search_values(item)):
            return False
    if criteria.item_type is not None and item.item_type is not criteria.item_type:
        return False
    if criteria.disposition is not None and item.disposition is not criteria.disposition:
        return False
    if (
        criteria.identification_status is not None
        and item.identification_status is not criteria.identification_status
    ):
        return False
    if criteria.issuer_or_country:
        expected = criteria.issuer_or_country.casefold()
        if expected not in {
            _factual_text(item.issuer).casefold(),
            _factual_text(item.country).casefold(),
        }:
            return False
    return True


def _valid_timestamp(item: CoinItem) -> datetime | None:
    try:
        value = validate_utc_rfc3339(item.updated_at)
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except (TypeError, ValueError):
        return None


def _sparse_text_key(value: str, original_index: int) -> tuple:
    text = "" if value == ABSENCE_MARKER else value
    return (not bool(text), text.casefold(), original_index)


def _sort_indexed(
    indexed: list[tuple[int, CoinItem]], sort_order: CollectionBrowserSort
) -> list[tuple[int, CoinItem]]:
    if sort_order is CollectionBrowserSort.COLLECTION_ORDER:
        return indexed
    if sort_order is CollectionBrowserSort.RECENTLY_UPDATED:
        valid = []
        invalid = []
        for index, item in indexed:
            timestamp = _valid_timestamp(item)
            (valid if timestamp is not None else invalid).append(
                (index, item, timestamp)
            )
        valid.sort(key=lambda row: row[2], reverse=True)
        return [(index, item) for index, item, _ in valid + invalid]

    def text_value(item: CoinItem) -> str:
        if sort_order is CollectionBrowserSort.ISSUER_COUNTRY:
            return _issuer_country_text(item)
        if sort_order is CollectionBrowserSort.DENOMINATION:
            return _display(item.denomination)
        return _display(item.year)

    return sorted(
        indexed,
        key=lambda pair: _sparse_text_key(text_value(pair[1]), pair[0]),
    )


def _acquisition_text(item: CoinItem) -> str:
    parts: list[str] = []
    price = item.purchase_price
    if isinstance(price, Decimal) and price.is_finite() and price >= 0:
        amount = format(price, "f")
        currency = _factual_text(item.purchase_currency)
        parts.append(f"{currency} {amount}" if currency else amount)
    acquisition_date = _factual_text(item.acquisition_date)
    source = _factual_text(item.purchase_source)
    if acquisition_date:
        parts.append(acquisition_date)
    if source:
        parts.append(source)
    return " · ".join(parts) or ABSENCE_MARKER


def _primary_photo_path(item: CoinItem) -> str:
    photos = []
    try:
        for original_index, photo in enumerate(tuple(item.photos or ())):
            path = _factual_text(getattr(photo, "path", ""))
            if path:
                try:
                    display_order = int(getattr(photo, "display_order", original_index))
                except (TypeError, ValueError):
                    display_order = original_index
                photos.append(
                    (
                        display_order,
                        original_index,
                        bool(getattr(photo, "is_primary", False)),
                        path,
                    )
                )
    except (TypeError, AttributeError):
        photos = []
    if photos:
        photos.sort(key=lambda row: (row[0], row[1]))
        primary = next((row for row in photos if row[2]), photos[0])
        return primary[3]
    return _factual_text(item.image_path)


def _row(item: CoinItem) -> CollectionBrowserRow:
    return CollectionBrowserRow(
        item_id=item.id,
        thumbnail_path=_primary_photo_path(item),
        item_type=item.item_type.value,
        issuer_country=_issuer_country_text(item),
        denomination=_display(item.denomination),
        date_series=_display(item.year),
        grade=_display(item.grade),
        acquisition=_acquisition_text(item),
        disposition=item.disposition.value,
        identification_status=item.identification_status.value,
    )


def project_collection(
    items: Sequence[CoinItem] | Iterable[CoinItem],
    criteria: CollectionBrowserCriteria | None = None,
) -> tuple[CollectionBrowserRow, ...]:
    """Return a detached projection without mutating items or their source sequence."""

    if criteria is None:
        criteria = CollectionBrowserCriteria()
    if not isinstance(criteria, CollectionBrowserCriteria):
        raise ValueError("criteria must be CollectionBrowserCriteria")
    source = tuple(items)
    if any(not isinstance(item, CoinItem) for item in source):
        raise ValueError("items must contain only CoinItem values")
    indexed = [
        (index, item)
        for index, item in enumerate(source)
        if _matches(item, criteria)
    ]
    return tuple(_row(item) for _, item in _sort_indexed(indexed, criteria.sort_order))


def issuer_country_filter_options(
    items: Sequence[CoinItem] | Iterable[CoinItem],
) -> tuple[str, ...]:
    """Return a deterministic case-insensitive union of factual issuer/country values."""

    variants: dict[str, set[str]] = {}
    for item in tuple(items):
        if not isinstance(item, CoinItem):
            raise ValueError("items must contain only CoinItem values")
        for value in (item.issuer, item.country):
            text = _factual_text(value)
            if text:
                variants.setdefault(text.casefold(), set()).add(text)
    representatives = [min(values) for values in variants.values()]
    return tuple(sorted(representatives, key=lambda value: (value.casefold(), value)))


__all__ = [
    "ABSENCE_MARKER",
    "ALL",
    "CollectionBrowserCriteria",
    "CollectionBrowserRow",
    "CollectionBrowserSort",
    "issuer_country_filter_options",
    "project_collection",
]
