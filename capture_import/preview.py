"""Immutable, read-only capture-package preview construction."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from hashlib import sha256
import json
from typing import Iterable

from coin_collection import CoinItem, PhotoRole

from .audit import AuditSession
from .duplicates import (
    DuplicateCandidate,
    PackageDuplicateDetectionService,
    duplicate_candidate_sort_key,
    require_safe_source_identifier,
)
from .enums import DuplicateCategory, DuplicateDecision, ImageRole
from .limits import MAX_COINS_PER_PACKAGE, MAX_PACKAGE_SIZE
from .models import (
    CollectionBaseline,
    ImportDecision,
    PackageCoin,
    _validate_basename,
    _validate_relative_path,
    _validate_sha256,
)
from .package import ValidatedCapturePackage

_ROLE_ORDER = {ImageRole.FRONT: 0, ImageRole.REVERSE: 1, ImageRole.EDGE: 2}
_DESKTOP_ROLES = {
    ImageRole.FRONT: PhotoRole.FRONT,
    ImageRole.REVERSE: PhotoRole.BACK,
    ImageRole.EDGE: PhotoRole.EDGE,
}
_UNMAPPED_ORDER = {"mint": 0, "composition": 1, "is_bullion": 2, "asw_troy_ounces": 3}


@dataclass(frozen=True, slots=True)
class PreviewImage:
    """Display-safe image metadata with no source or managed filesystem path."""

    source_role: ImageRole
    desktop_role: PhotoRole
    archive_path: str
    mime_type: str
    byte_length: int
    width: int
    height: int
    sha256: str
    is_primary: bool

    def validate(self) -> None:
        if not isinstance(self.source_role, ImageRole):
            raise ValueError("source_role must be an ImageRole.")
        if self.desktop_role is not _DESKTOP_ROLES[self.source_role]:
            raise ValueError("desktop_role does not match source_role.")
        _validate_relative_path(self.archive_path, "archive_path")
        if self.mime_type not in {"image/jpeg", "image/png"}:
            raise ValueError("mime_type is not supported.")
        for name, value in (
            ("byte_length", self.byte_length),
            ("width", self.width),
            ("height", self.height),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer.")
        _validate_sha256(self.sha256, "image sha256")
        if not isinstance(self.is_primary, bool):
            raise ValueError("is_primary must be a boolean.")
        if self.is_primary is not (self.source_role is ImageRole.FRONT):
            raise ValueError("Only the front image may be primary during preview.")


@dataclass(frozen=True, slots=True)
class UnmappedFact:
    """One mobile fact retained for audit but not mapped to CoinItem."""

    field: str
    label: str
    value: str

    def validate(self) -> None:
        if self.field not in _UNMAPPED_ORDER:
            raise ValueError("field is not an approved unmapped mobile field.")
        for name, value in (("label", self.label), ("value", self.value)):
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > 500
                or any(ord(character) < 32 for character in value)
            ):
                raise ValueError(f"{name} must be bounded display-safe text.")


@dataclass(frozen=True, slots=True)
class ProposedCoin:
    """Immutable mapped desktop proposal with no allocated desktop resources."""

    source_coin_id: str
    position: int
    country: str
    denomination: str
    year: str
    notes: str
    acquisition_date: str | None
    purchase_price: Decimal
    purchase_currency: str
    purchase_source: str | None
    quantity: int
    photos: tuple[PreviewImage, ...]
    unmapped_facts: tuple[UnmappedFact, ...]
    warnings: tuple[str, ...]
    duplicate_reasons: tuple[str, ...] = ()
    grade: str = ""
    reference: str = ""
    numista_number: str = ""
    estimate_cad: float = 0.0

    @property
    def total_cost(self) -> Decimal:
        """Return the exact derived acquisition cost without persisting it."""

        return self.purchase_price

    def validate(self) -> None:
        for name, value in (
            ("source_coin_id", self.source_coin_id),
            ("country", self.country),
            ("denomination", self.denomination),
            ("year", self.year),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")
        if isinstance(self.position, bool) or not isinstance(self.position, int) or self.position < 0:
            raise ValueError("position must be a non-negative integer.")
        if not isinstance(self.notes, str):
            raise ValueError("notes must be a string.")
        if self.acquisition_date is not None and not isinstance(self.acquisition_date, str):
            raise ValueError("acquisition_date must be a string or null.")
        if (
            not isinstance(self.purchase_price, Decimal)
            or not self.purchase_price.is_finite()
            or self.purchase_price < 0
        ):
            raise ValueError("purchase_price must be a finite non-negative Decimal.")
        if (
            not isinstance(self.purchase_currency, str)
            or len(self.purchase_currency) != 3
            or not self.purchase_currency.isalpha()
            or self.purchase_currency != self.purchase_currency.upper()
        ):
            raise ValueError("purchase_currency must be three uppercase letters.")
        if self.purchase_source is not None and not isinstance(self.purchase_source, str):
            raise ValueError("purchase_source must be a string or null.")
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int) or self.quantity < 1:
            raise ValueError("quantity must be a positive integer.")
        if not isinstance(self.photos, tuple):
            raise ValueError("photos must be an immutable tuple.")
        for photo in self.photos:
            if not isinstance(photo, PreviewImage):
                raise ValueError("photos must contain PreviewImage values.")
            photo.validate()
        roles = tuple(photo.source_role for photo in self.photos)
        if roles != tuple(sorted(roles, key=lambda role: _ROLE_ORDER[role])):
            raise ValueError("photos must use deterministic role ordering.")
        if len(set(roles)) != len(roles) or not {
            ImageRole.FRONT,
            ImageRole.REVERSE,
        }.issubset(roles):
            raise ValueError("photos must contain unique front and reverse roles.")
        if not isinstance(self.unmapped_facts, tuple):
            raise ValueError("unmapped_facts must be an immutable tuple.")
        for fact in self.unmapped_facts:
            if not isinstance(fact, UnmappedFact):
                raise ValueError("unmapped_facts must contain UnmappedFact values.")
            fact.validate()
        fact_fields = tuple(fact.field for fact in self.unmapped_facts)
        if fact_fields != tuple(sorted(fact_fields, key=_UNMAPPED_ORDER.__getitem__)):
            raise ValueError("unmapped_facts must use deterministic field ordering.")
        _validate_string_tuple(self.warnings, "warnings")
        _validate_string_tuple(self.duplicate_reasons, "duplicate_reasons")
        if any((self.grade, self.reference, self.numista_number)) or self.estimate_cad != 0.0:
            raise ValueError("Unsupported desktop fields must remain blank/default.")


@dataclass(frozen=True, slots=True)
class PreviewDecisionSet:
    """Decisions cryptographically bound to one exact immutable preview."""

    preview_fingerprint: str
    decisions: tuple[ImportDecision, ...]

    def __len__(self) -> int:
        return len(self.decisions)

    def __iter__(self):
        return iter(self.decisions)

    def __getitem__(self, index: int) -> ImportDecision:
        return self.decisions[index]

    def validate(self) -> None:
        _validate_sha256(self.preview_fingerprint, "preview_fingerprint")
        if not isinstance(self.decisions, tuple):
            raise ValueError("decisions must be an immutable tuple.")
        for decision in self.decisions:
            if not isinstance(decision, ImportDecision):
                raise ValueError("decisions must contain ImportDecision values.")
            decision.validate()
        ids = tuple(decision.source_coin_id for decision in self.decisions)
        if len(set(ids)) != len(ids):
            raise ValueError("decisions must have unique source IDs.")


@dataclass(frozen=True, slots=True)
class PackageImportPreview:
    """Canonical read-only preview bound to package and collection identities."""

    package_basename: str
    package_sha256: str
    package_byte_length: int
    collection_baseline: CollectionBaseline
    schema: str
    package_version: str
    created_by: str
    created_with: str
    exported_at: str
    session_id: str
    session_name: str
    session_description: str
    session_date: str | None
    proposals: tuple[ProposedCoin, ...]
    duplicate_candidates: tuple[DuplicateCandidate, ...]
    decisions: PreviewDecisionSet

    @property
    def duplicate_count(self) -> int:
        return len({candidate.source_coin_id for candidate in self.duplicate_candidates})

    @property
    def new_count(self) -> int:
        return len(self.proposals) - self.duplicate_count

    @property
    def default_skipped_count(self) -> int:
        return sum(
            decision.decision is DuplicateDecision.SKIP for decision in self.decisions
        )

    def validate(self) -> None:
        basename = _validate_basename(self.package_basename, "package_basename")
        if not basename.lower().endswith(".ca-package"):
            raise ValueError("package_basename must end with .ca-package.")
        _validate_sha256(self.package_sha256, "package_sha256")
        if (
            isinstance(self.package_byte_length, bool)
            or not isinstance(self.package_byte_length, int)
            or not 1 <= self.package_byte_length <= MAX_PACKAGE_SIZE
        ):
            raise ValueError("package_byte_length is outside the supported range.")
        if not isinstance(self.collection_baseline, CollectionBaseline):
            raise ValueError("collection_baseline must be a CollectionBaseline.")
        self.collection_baseline.validate()
        for name, value in (
            ("schema", self.schema),
            ("package_version", self.package_version),
            ("created_by", self.created_by),
            ("created_with", self.created_with),
            ("exported_at", self.exported_at),
            ("session_id", self.session_id),
            ("session_name", self.session_name),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")
        if not isinstance(self.session_description, str):
            raise ValueError("session_description must be a string.")
        if self.session_date is not None and not isinstance(self.session_date, str):
            raise ValueError("session_date must be a string or null.")
        if not isinstance(self.proposals, tuple) or not 1 <= len(self.proposals) <= MAX_COINS_PER_PACKAGE:
            raise ValueError("proposals must be a bounded immutable tuple.")
        for proposal in self.proposals:
            if not isinstance(proposal, ProposedCoin):
                raise ValueError("proposals must contain ProposedCoin values.")
            proposal.validate()
        source_ids = tuple(proposal.source_coin_id for proposal in self.proposals)
        positions = tuple(proposal.position for proposal in self.proposals)
        if len(set(source_ids)) != len(source_ids) or positions != tuple(range(len(self.proposals))):
            raise ValueError("proposals must have unique IDs and contiguous positions.")
        if not isinstance(self.duplicate_candidates, tuple):
            raise ValueError("duplicate_candidates must be an immutable tuple.")
        for candidate in self.duplicate_candidates:
            if not isinstance(candidate, DuplicateCandidate):
                raise ValueError("duplicate_candidates must contain DuplicateCandidate values.")
            candidate.validate()
            if candidate.source_coin_id not in source_ids:
                raise ValueError("duplicate candidate refers to an unknown source coin.")
        if len(set(self.duplicate_candidates)) != len(self.duplicate_candidates):
            raise ValueError("duplicate_candidates must be unique.")
        if self.duplicate_candidates != tuple(
            sorted(self.duplicate_candidates, key=duplicate_candidate_sort_key)
        ):
            raise ValueError("duplicate_candidates must use canonical ordering.")
        if not isinstance(self.decisions, PreviewDecisionSet):
            raise ValueError("decisions must be a PreviewDecisionSet.")
        self.decisions.validate()
        defaults = _default_decisions(self.proposals, self.duplicate_candidates)
        if self.decisions.decisions != defaults:
            raise ValueError("preview decisions must contain canonical defaults.")
        if tuple(decision.source_coin_id for decision in self.decisions) != source_ids:
            raise ValueError("decisions must match proposals exactly and in order.")
        expected_fingerprint = _preview_fingerprint(
            self.package_basename,
            self.package_sha256,
            self.package_byte_length,
            self.collection_baseline,
            self.proposals,
            self.duplicate_candidates,
            defaults,
        )
        if self.decisions.preview_fingerprint != expected_fingerprint:
            raise ValueError("decisions are not bound to this preview.")


class PackageImportPreviewBuilder:
    """Map a validated package to a deterministic preview without mutation."""

    def __init__(
        self, duplicate_service: PackageDuplicateDetectionService | None = None
    ) -> None:
        self.duplicate_service = duplicate_service or PackageDuplicateDetectionService()

    def build(
        self,
        package: ValidatedCapturePackage,
        collection_baseline: CollectionBaseline,
        *,
        existing_items: Iterable[CoinItem] = (),
        completed_audits: Iterable[AuditSession] = (),
    ) -> PackageImportPreview:
        if not isinstance(package, ValidatedCapturePackage):
            raise ValueError("package must be a ValidatedCapturePackage.")
        package.manifest.validate()
        if not isinstance(collection_baseline, CollectionBaseline):
            raise ValueError("collection_baseline must be a CollectionBaseline.")
        collection_baseline.validate()
        media_by_key = {(media.coin_id, media.role): media for media in package.media}
        if len(media_by_key) != len(package.media):
            raise ValueError("Validated media contains duplicate coin/role records.")
        proposals = tuple(
            self._map_coin(coin, media_by_key)
            for coin in sorted(package.manifest.coins, key=lambda value: value.position)
        )
        candidates = self.duplicate_service.detect(
            package, existing_items, completed_audits
        )
        reasons_by_coin: dict[str, list[str]] = {proposal.source_coin_id: [] for proposal in proposals}
        for candidate in candidates:
            reasons_by_coin[candidate.source_coin_id].extend(candidate.reasons)
        proposals = tuple(
            replace(
                proposal,
                duplicate_reasons=tuple(sorted(set(reasons_by_coin[proposal.source_coin_id]))),
            )
            for proposal in proposals
        )
        default_decisions = _default_decisions(proposals, candidates)
        fingerprint = _preview_fingerprint(
            package.package_basename,
            package.package_sha256,
            package.package_byte_length,
            collection_baseline,
            proposals,
            candidates,
            default_decisions,
        )
        manifest = package.manifest
        preview = PackageImportPreview(
            package_basename=package.package_basename,
            package_sha256=package.package_sha256,
            package_byte_length=package.package_byte_length,
            collection_baseline=collection_baseline,
            schema=manifest.schema,
            package_version=manifest.package_version,
            created_by=manifest.created_by,
            created_with=manifest.created_with,
            exported_at=manifest.exported_at,
            session_id=manifest.session.id,
            session_name=manifest.session.name,
            session_description=manifest.session.description,
            session_date=manifest.session.session_date,
            proposals=proposals,
            duplicate_candidates=candidates,
            decisions=PreviewDecisionSet(fingerprint, default_decisions),
        )
        preview.validate()
        return preview

    @staticmethod
    def _map_coin(coin: PackageCoin, media_by_key: dict[tuple[str, ImageRole], object]) -> ProposedCoin:
        require_safe_source_identifier(coin.id)
        images: list[PreviewImage] = []
        for photo in sorted(coin.photos, key=lambda value: _ROLE_ORDER[value.role]):
            media = media_by_key.get((coin.id, photo.role))
            if media is None:
                raise ValueError("Validated media is incomplete for a package coin.")
            if (
                media.archive_path != photo.path
                or media.mime_type != photo.mime_type
                or media.byte_length != photo.byte_length
                or media.width != photo.width
                or media.height != photo.height
            ):
                raise ValueError("Validated media does not match manifest image metadata.")
            images.append(
                PreviewImage(
                    source_role=photo.role,
                    desktop_role=_DESKTOP_ROLES[photo.role],
                    archive_path=media.archive_path,
                    mime_type=media.mime_type,
                    byte_length=media.byte_length,
                    width=media.width,
                    height=media.height,
                    sha256=media.sha256,
                    is_primary=photo.role is ImageRole.FRONT,
                )
            )
        facts = _unmapped_facts(coin)
        proposal = ProposedCoin(
            source_coin_id=coin.id,
            position=coin.position,
            country=coin.country,
            denomination=coin.denomination,
            year=coin.year,
            notes=coin.notes,
            acquisition_date=coin.purchase_date,
            purchase_price=coin.purchase_price,
            purchase_currency=coin.purchase_currency,
            purchase_source=coin.seller or None,
            quantity=coin.quantity,
            photos=tuple(images),
            unmapped_facts=facts,
            warnings=tuple(
                sorted(
                    f"{fact.label} is retained for audit only and is not mapped to CoinItem."
                    for fact in facts
                )
            ),
        )
        proposal.validate()
        return proposal


def _unmapped_facts(coin: PackageCoin) -> tuple[UnmappedFact, ...]:
    values: list[UnmappedFact] = []
    if coin.mint:
        values.append(UnmappedFact("mint", "Mint", coin.mint))
    values.append(UnmappedFact("composition", "Composition", coin.composition.value))
    values.append(UnmappedFact("is_bullion", "Bullion item", "Yes" if coin.is_bullion else "No"))
    if coin.asw_troy_ounces is not None:
        values.append(
            UnmappedFact(
                "asw_troy_ounces",
                "Actual silver weight (troy oz)",
                format(coin.asw_troy_ounces, "f"),
            )
        )
    result = tuple(sorted(values, key=lambda fact: _UNMAPPED_ORDER[fact.field]))
    for fact in result:
        fact.validate()
    return result


def _validate_string_tuple(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple) or any(
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 500
        or any(ord(character) < 32 for character in value)
        for value in values
    ):
        raise ValueError(f"{field_name} must contain bounded display-safe strings.")
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{field_name} must be unique and sorted.")


def _default_decisions(
    proposals: tuple[ProposedCoin, ...],
    candidates: tuple[DuplicateCandidate, ...],
) -> tuple[ImportDecision, ...]:
    exact_ids = {
        candidate.source_coin_id
        for candidate in candidates
        if candidate.category is DuplicateCategory.PACKAGE_REPLAY
    }
    return tuple(
        ImportDecision(
            proposal.source_coin_id,
            DuplicateDecision.SKIP
            if proposal.source_coin_id in exact_ids
            else DuplicateDecision.IMPORT_AS_NEW,
        )
        for proposal in proposals
    )


def _preview_fingerprint(
    package_basename: str,
    package_sha256: str,
    package_byte_length: int,
    collection_baseline: CollectionBaseline,
    proposals: tuple[ProposedCoin, ...],
    candidates: tuple[DuplicateCandidate, ...],
    defaults: tuple[ImportDecision, ...],
) -> str:
    payload = {
        "package_basename": package_basename,
        "package_sha256": package_sha256,
        "package_byte_length": package_byte_length,
        "collection_baseline": collection_baseline.to_dict(),
        "proposals": [
            {"source_coin_id": proposal.source_coin_id, "position": proposal.position}
            for proposal in proposals
        ],
        "duplicate_candidates": [
            {
                "source_coin_id": candidate.source_coin_id,
                "category": candidate.category.value,
                "confidence": candidate.confidence.value,
                "matched_desktop_ids": list(candidate.matched_desktop_ids),
                "reasons": list(candidate.reasons),
                "total_matches": candidate.total_matches,
            }
            for candidate in candidates
        ],
        "default_decisions": [decision.to_dict() for decision in defaults],
    }
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
