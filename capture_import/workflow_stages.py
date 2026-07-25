"""Reference preprocessing stages for the import workflow (Sprint 7 Unit 7).

This module adapts existing Sprint 5 validation/parsing services to the
internal ``ProcessingStage`` protocol.  It is strictly ephemeral:

- stages read the immutable request source and write only into the
  caller-owned workspace;
- no stage creates, opens, or names snapshots, journals, collections,
  transactions, rollback, or recovery — those remain reachable exclusively
  through the Unit 6 transaction delegate;
- no stage contacts ``PackageImportCoordinator``; the application-layer
  adapter lives in ``workflow_adapter.py``.

Source reads are race-aware (owner-mandated Unit 7 constraint):

- ``_open_source_readonly`` mirrors the frozen Sprint 5 verified-open
  pattern with ``O_RDONLY``: ``require_plain_regular_file`` fails closed on
  links/reparse points, ``O_NOFOLLOW`` rejects a final-component link where
  the platform provides it, and ``handle_matches_path`` binds the open
  handle to the verified path identity;
- digest and length are computed from that single open handle (policy-free
  I/O — every size and integrity policy stays inside the validator);
- identity is re-verified between the digest pass and the validator pass,
  so source replacement fails closed with ``PackageChanged``; in-place
  mutation fails closed inside ``validate_stream``'s own digest check.

Normalized manifest artifact policy (``prepared-manifest.json``):

- produced exclusively by the existing ``PackageManifest.to_dict()``
  serializer seam — no archive re-reading and no ad hoc field extraction;
- JSON object keys sorted at every level, compact separators (``,``/``:``),
  ``ensure_ascii=False``, non-finite numbers rejected (``allow_nan=False``);
- encoded UTF-8 without BOM and terminated by exactly one LF;
- consumed only by reparsing through ``CapturePackageManifestParser``.
"""

from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from ._filesystem import handle_matches_path, require_plain_regular_file
from .errors import PackageChanged
from .manifest import CapturePackageManifestParser
from .package import CapturePackageValidator
from .workflow_crop_detection import CropDetectionStage
from .workflow_image_duplicates import ImageDuplicateDetectionStage
from .workflow_image_normalization import ImageNormalizationStage
from .workflow_image_quality import ImageQualityScoringStage
from .workflow_models import StageArtifact, StageInput, StageResult
from .workflow_obverse_reverse_pairing import ObverseReversePairingStage
from .workflow_pipeline import ProcessingPipeline, StageContractError

if TYPE_CHECKING:
    from .models import PackageManifest

PACKAGE_VALIDATION_STAGE_ID = "package-validation"
MANIFEST_PREPARATION_STAGE_ID = "manifest-preparation"

PREPARED_MANIFEST_ARTIFACT = "prepared-manifest"
PREPARED_MANIFEST_NAME = "prepared-manifest.json"

_METADATA_BASENAME = "package_basename"
_METADATA_SHA256 = "package_sha256"
_METADATA_BYTE_LENGTH = "package_byte_length"
_METADATA_SCHEMA = "manifest_schema"
_METADATA_PACKAGE_VERSION = "manifest_package_version"
_METADATA_COIN_COUNT = "manifest_coin_count"

_READ_CHUNK = 1024 * 1024


def _open_source_readonly(path: Path) -> BinaryIO:
    """Open one source package read-only with link rejection and identity binding.

    Mirrors the frozen Sprint 5 verified-open pattern
    (``open_existing_binary_for_delete``) narrowed to ``O_RDONLY``.
    """
    require_plain_regular_file(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    handle = os.fdopen(descriptor, "rb")
    if not handle_matches_path(handle, path):
        handle.close()
        raise OSError("The source identity changed while it was opened.")
    return handle


def _digest_handle(handle: BinaryIO) -> tuple[str, int]:
    """Return ``(sha256 hex, byte length)`` computed from one open handle.

    Policy-free I/O: size limits and integrity verification remain with
    ``CapturePackageValidator.validate_stream``.
    """
    digest = sha256()
    length = 0
    while True:
        chunk = handle.read(_READ_CHUNK)
        if not chunk:
            break
        length += len(chunk)
        digest.update(chunk)
    return digest.hexdigest(), length


def _serialize_manifest_normalized(manifest: PackageManifest) -> bytes:
    """Serialize through the existing ``to_dict`` seam under the module policy."""
    text = json.dumps(
        manifest.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return (text + "\n").encode("utf-8")


class PackageValidationStage:
    """Validate the request source fail-fast and publish a normalized manifest.

    Calls the existing ``CapturePackageValidator`` wholesale (no validation
    logic is reimplemented here) against the request source — the only
    target reachable before ``PackageImportCoordinator.prepare()`` creates
    the authoritative snapshot.  The source is opened race-aware and is
    never written to.
    """

    def __init__(self, *, validator: CapturePackageValidator | None = None) -> None:
        self._validator = (
            validator if validator is not None else CapturePackageValidator()
        )

    @property
    def stage_id(self) -> str:
        return PACKAGE_VALIDATION_STAGE_ID

    def execute(self, stage_input: StageInput) -> StageResult:
        source = stage_input.request.source
        handle = _open_source_readonly(source)
        try:
            package_sha256, package_byte_length = _digest_handle(handle)
            if not handle_matches_path(handle, source):
                raise PackageChanged("source replaced during validation")
            validated = self._validator.validate_stream(
                handle,
                source.name,
                package_sha256=package_sha256,
                package_byte_length=package_byte_length,
            )
        finally:
            handle.close()
        artifact_path = stage_input.workspace / PREPARED_MANIFEST_NAME
        artifact_path.write_bytes(_serialize_manifest_normalized(validated.manifest))
        return StageResult(
            artifacts={
                PREPARED_MANIFEST_ARTIFACT: StageArtifact(
                    relative_path=PREPARED_MANIFEST_NAME,
                    content_type="application/json",
                )
            },
            metadata={
                _METADATA_BASENAME: validated.package_basename,
                _METADATA_SHA256: validated.package_sha256,
                _METADATA_BYTE_LENGTH: validated.package_byte_length,
            },
        )


class ManifestPreparationStage:
    """Assemble manifest facts for downstream stages from the normalized artifact.

    Reparses ``prepared-manifest.json`` through the existing
    ``CapturePackageManifestParser`` (no manifest validation logic is
    reimplemented) and emits curated JSON-safe metadata.
    """

    def __init__(self, *, parser: CapturePackageManifestParser | None = None) -> None:
        self._parser = (
            parser if parser is not None else CapturePackageManifestParser()
        )

    @property
    def stage_id(self) -> str:
        return MANIFEST_PREPARATION_STAGE_ID

    def execute(self, stage_input: StageInput) -> StageResult:
        artifact = stage_input.artifacts.get(PREPARED_MANIFEST_ARTIFACT)
        if artifact is None:
            raise StageContractError(
                self.stage_id,
                f"requires upstream artifact {PREPARED_MANIFEST_ARTIFACT!r}.",
            )
        try:
            payload = (stage_input.workspace / artifact.relative_path).read_bytes()
        except OSError as exc:
            raise StageContractError(
                self.stage_id,
                "declared artifact is not readable in the workspace: "
                f"{artifact.relative_path!r}.",
            ) from exc
        manifest = self._parser.parse(payload)
        return StageResult(
            artifacts={},
            metadata={
                _METADATA_SCHEMA: manifest.schema,
                _METADATA_PACKAGE_VERSION: manifest.package_version,
                _METADATA_COIN_COUNT: len(manifest.coins),
            },
        )


def build_reference_pipeline(
    *,
    validator: CapturePackageValidator | None = None,
    parser: CapturePackageManifestParser | None = None,
) -> ProcessingPipeline:
    """Build the deterministic reference pipeline.

    Stage order is an explicit fixed tuple (ADR-007); no discovery,
    registration timing, or mapping iteration is involved.
    """
    return ProcessingPipeline(
        stages=(
            PackageValidationStage(validator=validator),
            ManifestPreparationStage(parser=parser),
        )
    )


def build_image_processing_pipeline(
    *,
    validator: CapturePackageValidator | None = None,
    parser: CapturePackageManifestParser | None = None,
) -> ProcessingPipeline:
    """Build the deterministic Sprint 8 seven-stage processing pipeline."""

    return ProcessingPipeline(
        stages=(
            PackageValidationStage(validator=validator),
            ManifestPreparationStage(parser=parser),
            ImageNormalizationStage(),
            ImageQualityScoringStage(),
            CropDetectionStage(),
            ObverseReversePairingStage(),
            ImageDuplicateDetectionStage(),
        )
    )
