"""Pure, explained duplicate detection for capture-package previews."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from itertools import islice
from typing import Iterable, Iterator, TypeVar
import unicodedata

from coin_collection import CoinItem

from .audit import AuditCoin, AuditSession
from .enums import (
    DuplicateCategory,
    DuplicateConfidence,
    ImageRole,
    ImportPhase,
)
from .errors import InvalidManifest, PackageTooLarge
from .limits import (
    MAX_DUPLICATE_AUDITS,
    MAX_DUPLICATE_EXISTING_ITEMS,
    MAX_DUPLICATE_MATCHED_IDS,
    MAX_DUPLICATE_REASONS,
)
from .models import PackageCoin
from .package import ValidatedCapturePackage

_CONFIDENCE_ORDER = {
    DuplicateConfidence.EXACT: 0,
    DuplicateConfidence.HIGH: 1,
    DuplicateConfidence.MEDIUM: 2,
    DuplicateConfidence.WEAK: 3,
}
_ROLE_ORDER = {ImageRole.FRONT: 0, ImageRole.REVERSE: 1, ImageRole.EDGE: 2}
_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class DuplicateCandidate:
    """One bounded, immutable duplicate signal for a proposed coin."""

    source_coin_id: str
    category: DuplicateCategory
    confidence: DuplicateConfidence
    matched_desktop_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    total_matches: int

    def validate(self) -> None:
        if not _is_safe_identifier(self.source_coin_id):
            raise ValueError("source_coin_id must be a display-safe identifier.")
        if not isinstance(self.category, DuplicateCategory):
            raise ValueError("category must be a DuplicateCategory.")
        if not isinstance(self.confidence, DuplicateConfidence):
            raise ValueError("confidence must be a DuplicateConfidence.")
        if (
            not isinstance(self.matched_desktop_ids, tuple)
            or len(self.matched_desktop_ids) > MAX_DUPLICATE_MATCHED_IDS
            or any(not _is_safe_identifier(value) for value in self.matched_desktop_ids)
        ):
            raise ValueError("matched_desktop_ids must contain bounded safe identifiers.")
        if self.matched_desktop_ids != tuple(sorted(set(self.matched_desktop_ids))):
            raise ValueError("matched_desktop_ids must be unique and sorted.")
        if (
            not isinstance(self.reasons, tuple)
            or not self.reasons
            or len(self.reasons) > MAX_DUPLICATE_REASONS
            or any(
                not isinstance(reason, str)
                or not reason.strip()
                or len(reason) > 500
                or any(ord(character) < 32 for character in reason)
                for reason in self.reasons
            )
        ):
            raise ValueError("reasons must contain bounded display-safe text.")
        if self.reasons != tuple(sorted(set(self.reasons))):
            raise ValueError("reasons must be unique and sorted.")
        if (
            isinstance(self.total_matches, bool)
            or not isinstance(self.total_matches, int)
            or self.total_matches < 1
        ):
            raise ValueError("total_matches must be a positive integer.")


@dataclass(slots=True)
class _EvidenceAccumulator:
    source_coin_id: str
    category: DuplicateCategory
    confidence: DuplicateConfidence
    matched_ids: set[str] = field(default_factory=set)
    reasons: set[str] = field(default_factory=set)
    total_matches: int = 0

    def add(self, candidate: DuplicateCandidate) -> None:
        self.matched_ids.update(candidate.matched_desktop_ids)
        self.reasons.update(candidate.reasons)
        self.total_matches += candidate.total_matches

    def build(self) -> DuplicateCandidate:
        result = DuplicateCandidate(
            source_coin_id=self.source_coin_id,
            category=self.category,
            confidence=self.confidence,
            matched_desktop_ids=tuple(sorted(self.matched_ids))[
                :MAX_DUPLICATE_MATCHED_IDS
            ],
            reasons=tuple(sorted(self.reasons))[:MAX_DUPLICATE_REASONS],
            total_matches=self.total_matches,
        )
        result.validate()
        return result


class PackageDuplicateDetectionService:
    """Produce deterministic bounded duplicate evidence without choosing an action."""

    def detect(
        self,
        package: ValidatedCapturePackage,
        existing_items: Iterable[CoinItem] = (),
        completed_audits: Iterable[AuditSession] = (),
    ) -> tuple[DuplicateCandidate, ...]:
        if not isinstance(package, ValidatedCapturePackage):
            raise ValueError("package must be a ValidatedCapturePackage.")
        package.manifest.validate()
        for coin in package.manifest.coins:
            require_safe_source_identifier(coin.id)
        items = _bounded_tuple(existing_items, MAX_DUPLICATE_EXISTING_ITEMS)
        audits = _bounded_tuple(completed_audits, MAX_DUPLICATE_AUDITS)
        if any(not isinstance(item, CoinItem) for item in items):
            raise ValueError("existing_items must contain CoinItem values.")
        for audit in audits:
            if not isinstance(audit, AuditSession):
                raise ValueError("completed_audits must contain AuditSession values.")
            audit.validate()
        successful = tuple(
            sorted(
                (audit for audit in audits if audit.phase is ImportPhase.SUCCEEDED),
                key=lambda audit: (audit.completed_at, audit.import_id),
            )
        )
        hashes = _package_role_hashes(package)
        existing_ids = {item.id for item in items if _is_safe_identifier(item.id)}
        aggregates: dict[
            tuple[str, DuplicateCategory, DuplicateConfidence], _EvidenceAccumulator
        ] = {}
        for coin in sorted(package.manifest.coins, key=lambda value: value.position):
            coin_hashes = hashes[coin.id]
            evidence = self._audit_candidates(
                package, coin, coin_hashes, successful, existing_ids
            )
            evidence = (*evidence, *self._collection_candidates(coin, items))
            for candidate in evidence:
                key = (
                    candidate.source_coin_id,
                    candidate.category,
                    candidate.confidence,
                )
                accumulator = aggregates.setdefault(
                    key,
                    _EvidenceAccumulator(
                        candidate.source_coin_id,
                        candidate.category,
                        candidate.confidence,
                    ),
                )
                accumulator.add(candidate)
        result = tuple(
            sorted(
                (accumulator.build() for accumulator in aggregates.values()),
                key=duplicate_candidate_sort_key,
            )
        )
        return result

    def _audit_candidates(
        self,
        package: ValidatedCapturePackage,
        coin: PackageCoin,
        coin_hashes: dict[ImageRole, str],
        audits: tuple[AuditSession, ...],
        existing_ids: set[str],
    ) -> Iterator[DuplicateCandidate]:
        for audit in audits:
            prior_coin = next(
                (
                    value
                    for value in audit.coin_provenance
                    if value.source_coin_id == coin.id
                ),
                None,
            )
            if audit.package_sha256 == package.package_sha256:
                yield _candidate(
                    coin.id,
                    DuplicateCategory.PACKAGE_REPLAY,
                    DuplicateConfidence.EXACT,
                    _safe_desktop_ids((prior_coin,) if prior_coin else ()),
                    (
                        "This package was successfully imported at "
                        f"{audit.completed_at} ({audit.imported_count} imported, "
                        f"{audit.skipped_count} skipped).",
                    ),
                )
            if prior_coin is None:
                continue
            prior_hashes = dict(prior_coin.image_role_hashes)
            both_match = _front_reverse_match(coin_hashes, prior_hashes)
            if (
                audit.package_sha256 != package.package_sha256
                and audit.created_by == package.manifest.created_by
                and audit.session_id == package.manifest.session.id
                and both_match
            ):
                yield _candidate(
                    coin.id,
                    DuplicateCategory.SOURCE_AND_MEDIA,
                    DuplicateConfidence.HIGH,
                    _safe_desktop_ids((prior_coin,)),
                    (
                        "Producer, capture session, source coin ID, and front/reverse image hashes match a prior successful import.",
                    ),
                )
            desktop_id = prior_coin.desktop_item_id
            if not desktop_id or desktop_id not in existing_ids:
                continue
            if both_match:
                yield _candidate(
                    coin.id,
                    DuplicateCategory.MEDIA_HASHES,
                    DuplicateConfidence.HIGH,
                    (desktop_id,),
                    ("Front and reverse image hashes match an existing imported record.",),
                )
            elif _matching_hash_roles(coin_hashes, prior_hashes):
                yield _candidate(
                    coin.id,
                    DuplicateCategory.PARTIAL_MEDIA,
                    DuplicateConfidence.WEAK,
                    (desktop_id,),
                    ("One image hash matches an existing imported record.",),
                )

    def _collection_candidates(
        self, coin: PackageCoin, items: tuple[CoinItem, ...]
    ) -> Iterator[DuplicateCandidate]:
        for item in sorted(items, key=lambda value: _text_key(value.id)):
            matched_ids = (item.id,) if _is_safe_identifier(item.id) else ()
            identity_match = _identity_key(coin) == _item_identity_key(item)
            matching_details, conflicting_details = _acquisition_comparison(coin, item)
            if identity_match and len(matching_details) >= 2 and not conflicting_details:
                yield _candidate(
                    coin.id,
                    DuplicateCategory.IDENTITY_AND_ACQUISITION,
                    DuplicateConfidence.MEDIUM,
                    matched_ids,
                    (
                        "Country, denomination, year, and compatible acquisition details match an existing record.",
                    ),
                )
            elif identity_match:
                reason = "Country, denomination, and year match an existing record."
                if matching_details:
                    reason = (
                        reason[:-1]
                        + "; matching acquisition fields: "
                        + ", ".join(matching_details)
                        + "."
                    )
                yield _candidate(
                    coin.id,
                    DuplicateCategory.IDENTITY,
                    DuplicateConfidence.WEAK,
                    matched_ids,
                    (reason,),
                )
            elif matching_details:
                yield _candidate(
                    coin.id,
                    DuplicateCategory.ACQUISITION_DETAILS,
                    DuplicateConfidence.WEAK,
                    matched_ids,
                    (
                        "Acquisition fields match an existing record: "
                        + ", ".join(matching_details)
                        + ".",
                    ),
                )


def require_safe_source_identifier(value: object) -> str:
    """Reject path-like or display-control-bearing mobile identifiers."""

    if not _is_safe_identifier(value):
        raise InvalidManifest()
    return value


def duplicate_candidate_sort_key(candidate: DuplicateCandidate) -> tuple[object, ...]:
    """Return the one canonical duplicate-evidence ordering key."""

    return (
        candidate.source_coin_id,
        _CONFIDENCE_ORDER[candidate.confidence],
        candidate.category.value,
        candidate.matched_desktop_ids,
        candidate.reasons,
        candidate.total_matches,
    )


def _candidate(
    source_coin_id: str,
    category: DuplicateCategory,
    confidence: DuplicateConfidence,
    matched_ids: tuple[str, ...],
    reasons: tuple[str, ...],
) -> DuplicateCandidate:
    candidate = DuplicateCandidate(
        source_coin_id=source_coin_id,
        category=category,
        confidence=confidence,
        matched_desktop_ids=tuple(sorted(set(matched_ids))),
        reasons=tuple(sorted(set(reasons))),
        total_matches=1,
    )
    candidate.validate()
    return candidate


def _package_role_hashes(
    package: ValidatedCapturePackage,
) -> dict[str, dict[ImageRole, str]]:
    result: dict[str, dict[ImageRole, str]] = {
        coin.id: {} for coin in package.manifest.coins
    }
    for media in package.media:
        if media.coin_id not in result or media.role in result[media.coin_id]:
            raise ValueError("Validated media does not match the package manifest.")
        result[media.coin_id][media.role] = media.sha256
    for coin in package.manifest.coins:
        expected = {photo.role for photo in coin.photos}
        if set(result[coin.id]) != expected:
            raise ValueError("Validated media is incomplete for a package coin.")
    return result


def _front_reverse_match(
    current: dict[ImageRole, str], prior: dict[ImageRole, str]
) -> bool:
    return all(
        role in current and current[role] == prior.get(role)
        for role in (ImageRole.FRONT, ImageRole.REVERSE)
    )


def _matching_hash_roles(
    current: dict[ImageRole, str], prior: dict[ImageRole, str]
) -> tuple[ImageRole, ...]:
    return tuple(
        sorted(
            (role for role, digest in current.items() if prior.get(role) == digest),
            key=lambda role: _ROLE_ORDER[role],
        )
    )


def _safe_desktop_ids(coins: Iterable[AuditCoin]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                coin.desktop_item_id
                for coin in coins
                if coin.desktop_item_id and _is_safe_identifier(coin.desktop_item_id)
            }
        )
    )


def _identity_key(coin: PackageCoin) -> tuple[str, str, str]:
    return (_text_key(coin.country), _text_key(coin.denomination), _text_key(coin.year))


def _item_identity_key(item: CoinItem) -> tuple[str, str, str]:
    return (_text_key(item.country), _text_key(item.denomination), _text_key(item.year))


def _acquisition_comparison(
    coin: PackageCoin, item: CoinItem
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    matches: list[str] = []
    conflicts: list[str] = []
    if coin.purchase_price is not None and item.purchase_price is not None:
        currency_matches = (
            not coin.purchase_currency
            or not item.purchase_currency
            or _text_key(coin.purchase_currency) == _text_key(item.purchase_currency)
        )
        if _decimal_key(coin.purchase_price) == _decimal_key(item.purchase_price) and currency_matches:
            matches.append("price")
        else:
            conflicts.append("price")
    for label, proposed, existing in (
        ("seller", coin.seller, item.purchase_source),
        ("date", coin.purchase_date, item.acquisition_date),
        ("notes", coin.notes, item.notes),
    ):
        if proposed in (None, "") or existing in (None, ""):
            continue
        if _text_key(proposed) == _text_key(existing):
            matches.append(label)
        else:
            conflicts.append(label)
    return tuple(matches), tuple(conflicts)


def _decimal_key(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _text_key(value: object) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    return " ".join(text.split()).casefold()


def _is_safe_identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value == value.strip()
        and len(value) <= 256
        and not any(character in value for character in ("/", "\\", ":"))
        and ".." not in value
        and not any(
            unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"}
            for character in value
        )
    )


def _bounded_tuple(values: Iterable[_T], limit: int) -> tuple[_T, ...]:
    """Consume at most one value beyond a comparison limit."""

    result = tuple(islice(values, limit + 1))
    if len(result) > limit:
        raise PackageTooLarge()
    return result
