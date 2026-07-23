"""Exact normalized-image duplicate signals for the import workflow.

Sprint 8 Unit 6 is strictly read-only.  The stage hashes canonical normalized
JPEG artifacts, compares them within the package and against an injected
bounded collection-descriptor source, and emits ephemeral duplicate evidence.
It never loads ``CoinItem`` objects, opens collection storage, or chooses an
import decision.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
from itertools import combinations, islice
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable

from PIL import Image

from .enums import DuplicateCategory, DuplicateConfidence, ImageRole
from .errors import CaptureImportError
from .limits import (
    MAX_DUPLICATE_EXISTING_ITEMS,
    MAX_DUPLICATE_MATCHED_IDS,
    MAX_DUPLICATE_REASONS,
    MAX_JSON_BYTES,
)
from .manifest import CapturePackageManifestParser
from .image_validation import require_complete_jpeg
from .models import PackageManifest
from .workflow_models import JsonValue, StageArtifact, StageInput, StageResult
from .workflow_obverse_reverse_pairing import (
    _decode_bounded_image,
    _read_bounded_artifact,
)
from .workflow_pipeline import StageContractError, StageExecutionError

IMAGE_DUPLICATE_DETECTION_STAGE_ID = "image-duplicate-detection"
PREPARED_MANIFEST_ARTIFACT = "prepared-manifest"
PREPARED_MANIFEST_NAME = "prepared-manifest.json"

_NORMALIZED_PREFIX = "normalized-"
_SAFE_COIN_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_REQUIRED_ROLES = (ImageRole.FRONT, ImageRole.REVERSE)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CONFIDENCE_ORDER = {
    DuplicateConfidence.EXACT: 0,
    DuplicateConfidence.HIGH: 1,
    DuplicateConfidence.MEDIUM: 2,
    DuplicateConfidence.WEAK: 3,
}


@dataclass(frozen=True, slots=True)
class DuplicateCandidate:
    """Collection-neutral duplicate evidence matching the preview DTO shape."""

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
            or any(
                not _is_safe_identifier(value)
                for value in self.matched_desktop_ids
            )
            or self.matched_desktop_ids
            != tuple(sorted(set(self.matched_desktop_ids)))
        ):
            raise ValueError(
                "matched_desktop_ids must contain bounded safe identifiers."
            )
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
            or self.reasons != tuple(sorted(set(self.reasons)))
        ):
            raise ValueError("reasons must contain bounded display-safe text.")
        if (
            isinstance(self.total_matches, bool)
            or not isinstance(self.total_matches, int)
            or self.total_matches < 1
        ):
            raise ValueError("total_matches must be a positive integer.")


@dataclass(frozen=True, slots=True)
class CollectionImageDescriptor:
    """Read-only image-hash projection for one durable collection item."""

    desktop_id: str
    role_hashes: tuple[tuple[ImageRole, str], ...]

    def validate(self) -> None:
        if not _is_safe_identifier(self.desktop_id):
            raise ValueError("desktop_id must be a display-safe identifier.")
        if not isinstance(self.role_hashes, tuple) or not self.role_hashes:
            raise ValueError("role_hashes must be a non-empty immutable tuple.")
        roles: list[ImageRole] = []
        for value in self.role_hashes:
            if (
                not isinstance(value, tuple)
                or len(value) != 2
                or not isinstance(value[0], ImageRole)
                or value[0] not in _REQUIRED_ROLES
                or not isinstance(value[1], str)
                or _SHA256.fullmatch(value[1]) is None
            ):
                raise ValueError(
                    "role_hashes must contain front/reverse SHA-256 pairs."
                )
            roles.append(value[0])
        if len(set(roles)) != len(roles):
            raise ValueError("role_hashes must contain unique roles.")
        if self.role_hashes != tuple(
            sorted(self.role_hashes, key=lambda item: item[0].value)
        ):
            raise ValueError("role_hashes must use canonical role ordering.")


@runtime_checkable
class CollectionImageDescriptorSource(Protocol):
    """Bounded read-only seam for durable collection image descriptors."""

    def iter_descriptors(self) -> Iterable[CollectionImageDescriptor]:
        """Return projections without mutating or materializing collection items."""
        ...


@dataclass(slots=True)
class _CandidateAccumulator:
    source_coin_id: str
    confidence: DuplicateConfidence
    matched_desktop_ids: set[str] = field(default_factory=set)
    reasons: set[str] = field(default_factory=set)
    total_matches: int = 0

    def add(
        self,
        *,
        matched_desktop_id: str | None,
        reason: str,
    ) -> None:
        if matched_desktop_id is not None:
            self.matched_desktop_ids.add(matched_desktop_id)
        self.reasons.add(reason)
        self.total_matches += 1

    def build(self) -> DuplicateCandidate:
        candidate = DuplicateCandidate(
            source_coin_id=self.source_coin_id,
            category=DuplicateCategory.NORMALIZED_MEDIA_HASHES,
            confidence=self.confidence,
            matched_desktop_ids=tuple(sorted(self.matched_desktop_ids))[
                :MAX_DUPLICATE_MATCHED_IDS
            ],
            reasons=tuple(sorted(self.reasons))[:MAX_DUPLICATE_REASONS],
            total_matches=self.total_matches,
        )
        candidate.validate()
        return candidate


class ImageDuplicateDetectionStage:
    """Emit deterministic exact-hash duplicate evidence without choosing actions."""

    def __init__(
        self,
        *,
        descriptor_source: CollectionImageDescriptorSource | None = None,
        manifest_parser: CapturePackageManifestParser | None = None,
    ) -> None:
        self._descriptor_source = descriptor_source
        self._manifest_parser = manifest_parser or CapturePackageManifestParser()

    @property
    def stage_id(self) -> str:
        return IMAGE_DUPLICATE_DETECTION_STAGE_ID

    def execute(self, stage_input: StageInput) -> StageResult:
        manifest = self._read_manifest(stage_input)
        package_hashes = self._hash_normalized_artifacts(stage_input, manifest)
        descriptors = self._read_collection_descriptors()
        candidates = self._detect(package_hashes, descriptors)
        return StageResult(
            artifacts={},
            metadata={
                "image_duplicate_candidate_count": len(candidates),
                "image_duplicate_candidates": [
                    _candidate_to_dict(candidate) for candidate in candidates
                ],
            },
        )

    def _read_manifest(self, stage_input: StageInput) -> PackageManifest:
        artifact = stage_input.artifacts.get(PREPARED_MANIFEST_ARTIFACT)
        if artifact is None:
            raise StageContractError(
                self.stage_id,
                f"requires upstream artifact {PREPARED_MANIFEST_ARTIFACT!r}.",
            )
        if (
            artifact.relative_path != PREPARED_MANIFEST_NAME
            or artifact.content_type != "application/json"
        ):
            raise StageContractError(
                self.stage_id,
                "prepared manifest artifact does not match its canonical contract.",
            )
        payload = _read_bounded_artifact(
            stage_input.workspace,
            Path(artifact.relative_path),
            stage_id=self.stage_id,
            label="prepared manifest",
            max_bytes=MAX_JSON_BYTES,
        )
        try:
            return self._manifest_parser.parse(payload)
        except CaptureImportError as exc:
            raise StageContractError(
                self.stage_id,
                "prepared manifest artifact is invalid.",
            ) from exc

    def _hash_normalized_artifacts(
        self,
        stage_input: StageInput,
        manifest: PackageManifest,
    ) -> dict[str, dict[ImageRole, str]]:
        expected: dict[tuple[str, ImageRole], StageArtifact] = {}
        manifest_roles: set[tuple[str, ImageRole]] = set()
        for coin in manifest.coins:
            if _SAFE_COIN_ID.fullmatch(coin.id) is None:
                raise StageContractError(
                    self.stage_id,
                    "manifest contains an unsafe source coin identifier.",
                )
            manifest_roles.update((coin.id, photo.role) for photo in coin.photos)
            for role in _REQUIRED_ROLES:
                key = f"{_NORMALIZED_PREFIX}{coin.id}-{role.value}"
                artifact = stage_input.artifacts.get(key)
                if artifact is None:
                    raise StageContractError(
                        self.stage_id,
                        f"missing normalized {role.value} artifact for coin {coin.id!r}.",
                    )
                expected[(coin.id, role)] = artifact

        for key in stage_input.artifacts:
            if not key.startswith(_NORMALIZED_PREFIX):
                continue
            parsed = _parse_normalized_key(key)
            if parsed is None or parsed not in manifest_roles:
                raise StageContractError(
                    self.stage_id,
                    "normalized artifact set does not match the prepared manifest.",
                )

        result: dict[str, dict[ImageRole, str]] = {}
        for (coin_id, role), artifact in sorted(
            expected.items(),
            key=lambda item: (item[0][0], item[0][1].value),
        ):
            canonical_path = f"normalized/{coin_id}/{role.value}.jpg"
            if (
                artifact.relative_path != canonical_path
                or artifact.content_type != "image/jpeg"
            ):
                raise StageContractError(
                    self.stage_id,
                    "normalized artifact does not match its canonical JPEG contract.",
                )
            payload = _read_bounded_artifact(
                stage_input.workspace,
                Path(artifact.relative_path),
                stage_id=self.stage_id,
                label=f"normalized {role.value} artifact",
            )
            _decode_bounded_image(
                payload,
                artifact,
                stage_id=self.stage_id,
                label=f"normalized {role.value} artifact",
            )
            _require_canonical_normalized_jpeg(payload, stage_id=self.stage_id)
            result.setdefault(coin_id, {})[role] = sha256(payload).hexdigest()
        return result

    def _read_collection_descriptors(
        self,
    ) -> tuple[CollectionImageDescriptor, ...]:
        if self._descriptor_source is None:
            return ()
        try:
            iterator = iter(self._descriptor_source.iter_descriptors())
            descriptors = tuple(
                islice(iterator, MAX_DUPLICATE_EXISTING_ITEMS + 1)
            )
        except Exception as exc:
            raise StageExecutionError(self.stage_id, exc) from exc
        if len(descriptors) > MAX_DUPLICATE_EXISTING_ITEMS:
            raise StageContractError(
                self.stage_id,
                "collection image descriptor limit exceeded.",
            )
        desktop_ids: set[str] = set()
        for descriptor in descriptors:
            if not isinstance(descriptor, CollectionImageDescriptor):
                raise StageContractError(
                    self.stage_id,
                    "collection lookup returned an invalid descriptor.",
                )
            try:
                descriptor.validate()
            except ValueError as exc:
                raise StageContractError(
                    self.stage_id,
                    "collection lookup returned an invalid descriptor.",
                ) from exc
            if descriptor.desktop_id in desktop_ids:
                raise StageContractError(
                    self.stage_id,
                    "collection lookup returned duplicate desktop identifiers.",
                )
            desktop_ids.add(descriptor.desktop_id)
        return tuple(sorted(descriptors, key=lambda item: item.desktop_id))

    def _detect(
        self,
        package_hashes: dict[str, dict[ImageRole, str]],
        descriptors: tuple[CollectionImageDescriptor, ...],
    ) -> tuple[DuplicateCandidate, ...]:
        accumulators: dict[
            tuple[str, DuplicateConfidence], _CandidateAccumulator
        ] = {}

        for left_id, right_id in combinations(sorted(package_hashes), 2):
            matching_roles = _matching_roles(
                package_hashes[left_id],
                package_hashes[right_id],
            )
            if not matching_roles:
                continue
            confidence, reason = _evidence_for_roles(
                matching_roles,
                within_package=True,
            )
            for source_coin_id in (left_id, right_id):
                _accumulator(accumulators, source_coin_id, confidence).add(
                    matched_desktop_id=None,
                    reason=reason,
                )

        for source_coin_id in sorted(package_hashes):
            source_hashes = package_hashes[source_coin_id]
            for descriptor in descriptors:
                matching_roles = _matching_roles(
                    source_hashes,
                    dict(descriptor.role_hashes),
                )
                if not matching_roles:
                    continue
                confidence, reason = _evidence_for_roles(
                    matching_roles,
                    within_package=False,
                )
                _accumulator(accumulators, source_coin_id, confidence).add(
                    matched_desktop_id=descriptor.desktop_id,
                    reason=reason,
                )

        return tuple(
            sorted(
                (accumulator.build() for accumulator in accumulators.values()),
                key=_duplicate_candidate_sort_key,
            )
        )


def _parse_normalized_key(key: str) -> tuple[str, ImageRole] | None:
    if not key.startswith(_NORMALIZED_PREFIX):
        return None
    parts = key[len(_NORMALIZED_PREFIX) :].rsplit("-", 1)
    if len(parts) != 2 or _SAFE_COIN_ID.fullmatch(parts[0]) is None:
        return None
    try:
        return parts[0], ImageRole(parts[1])
    except ValueError:
        return None


def _matching_roles(
    left: dict[ImageRole, str],
    right: dict[ImageRole, str],
) -> tuple[ImageRole, ...]:
    return tuple(
        role
        for role in _REQUIRED_ROLES
        if role in left and left[role] == right.get(role)
    )


def _evidence_for_roles(
    matching_roles: tuple[ImageRole, ...],
    *,
    within_package: bool,
) -> tuple[DuplicateConfidence, str]:
    if matching_roles == _REQUIRED_ROLES:
        scope = "another package item" if within_package else "an existing item"
        return (
            DuplicateConfidence.EXACT,
            f"Front and reverse normalized image hashes match {scope}.",
        )
    role = matching_roles[0].value
    scope = "another package item" if within_package else "an existing item"
    return (
        DuplicateConfidence.MEDIUM,
        f"The normalized {role} image hash matches {scope}.",
    )


def _accumulator(
    values: dict[tuple[str, DuplicateConfidence], _CandidateAccumulator],
    source_coin_id: str,
    confidence: DuplicateConfidence,
) -> _CandidateAccumulator:
    return values.setdefault(
        (source_coin_id, confidence),
        _CandidateAccumulator(source_coin_id, confidence),
    )


def _candidate_to_dict(candidate: DuplicateCandidate) -> dict[str, JsonValue]:
    return {
        "source_coin_id": candidate.source_coin_id,
        "category": candidate.category.value,
        "confidence": candidate.confidence.value,
        "matched_desktop_ids": list(candidate.matched_desktop_ids),
        "reasons": list(candidate.reasons),
        "total_matches": candidate.total_matches,
    }


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


def _duplicate_candidate_sort_key(
    candidate: DuplicateCandidate,
) -> tuple[object, ...]:
    return (
        candidate.source_coin_id,
        _CONFIDENCE_ORDER[candidate.confidence],
        candidate.category.value,
        candidate.matched_desktop_ids,
        candidate.reasons,
        candidate.total_matches,
    )


def _require_canonical_normalized_jpeg(
    payload: bytes,
    *,
    stage_id: str,
) -> None:
    """Require the exact baseline, metadata-free JPEG emitted by normalization."""

    try:
        require_complete_jpeg(payload)
    except ValueError as exc:
        raise StageContractError(
            stage_id,
            "normalized artifact is not a canonical JPEG.",
        ) from exc
    except Exception as exc:
        raise StageExecutionError(stage_id, exc) from exc

    try:
        with Image.open(BytesIO(payload)) as image:
            is_noncanonical = (
                image.format != "JPEG"
                or image.mode != "RGB"
                or image.info.get("progressive")
                or image.info.get("progression")
                or image.info.get("exif")
                or image.info.get("icc_profile")
            )
    except Exception as exc:
        raise StageExecutionError(stage_id, exc) from exc
    if is_noncanonical:
        raise StageContractError(
            stage_id,
            "normalized artifact is not a canonical JPEG.",
        )
