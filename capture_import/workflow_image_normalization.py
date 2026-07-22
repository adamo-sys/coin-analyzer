"""Image normalization stage for the import workflow (Sprint 8 Unit 2).

Converts every validated capture-package JPEG/PNG into a canonical normalized
JPEG artifact inside the workspace.  The stage reads the upstream
``prepared-manifest`` artifact and the original archive at
``request.source``; it writes only beneath ``StageInput.workspace``.
"""

from __future__ import annotations

import json
import re
import warnings
import zipfile
from io import BytesIO
from typing import Any

from PIL import Image

from .enums import ImageRole
from .limits import MAX_IMAGE_DIMENSION
from .workflow_models import StageArtifact, StageInput, StageResult
from .workflow_pipeline import StageContractError, StageExecutionError

IMAGE_NORMALIZATION_STAGE_ID = "image-normalization"

PREPARED_MANIFEST_ARTIFACT = "prepared-manifest"
PREPARED_MANIFEST_NAME = "prepared-manifest.json"

_NORMALIZED_SUBDIR = "normalized"
_JPEG_QUALITY = 92
_JPEG_MIME = "image/jpeg"

# Defensive: reject coin_id values that could escape the workspace or
# create ambiguous paths.  The upstream manifest validator is expected
# to enforce this, but the stage re-validates because it constructs
# filesystem paths from the identifier.
_SAFE_COIN_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_ROLE_TO_FILENAME = {
    ImageRole.FRONT: "front",
    ImageRole.REVERSE: "reverse",
    ImageRole.EDGE: "edge",
}


def _role_filename(role_name: str) -> str:
    """Map a manifest role string to the normalized output filename stem."""
    try:
        role = ImageRole(role_name)
        return _ROLE_TO_FILENAME[role]
    except (ValueError, KeyError):
        # Defensive: fall back to the raw role name for unknown roles.
        return role_name


def _validate_coin_id(coin_id: str, *, stage_id: str) -> None:
    """Raise StageContractError if coin_id is unsafe for path construction."""
    if not _SAFE_COIN_ID.fullmatch(coin_id):
        raise StageContractError(
            stage_id,
            f"coin_id {coin_id!r} contains unsafe characters for path "
            f"construction.",
        )


class ImageNormalizationStage:
    """Normalize capture-package images to canonical JPEG artifacts.

    Reads the upstream ``prepared-manifest`` artifact to discover images,
    reads each image from the source archive, and writes a normalized JPEG
    into the workspace.
    """

    def __init__(
        self,
        *,
        max_dimension: int = MAX_IMAGE_DIMENSION,
        quality: int = _JPEG_QUALITY,
    ) -> None:
        self._max_dimension = max_dimension
        self._quality = quality

    @property
    def stage_id(self) -> str:
        return IMAGE_NORMALIZATION_STAGE_ID

    def execute(self, stage_input: StageInput) -> StageResult:
        manifest = self._read_manifest(stage_input)
        archive_path = stage_input.request.source

        try:
            archive = zipfile.ZipFile(archive_path, mode="r")
        except (OSError, zipfile.BadZipFile) as exc:
            raise StageExecutionError(self.stage_id, exc) from exc

        artifacts: dict[str, StageArtifact] = {}
        dimensions: dict[str, Any] = {}
        normalized_count = 0

        try:
            for coin in manifest.get("coins", []):
                coin_id = coin.get("id")
                if not coin_id or not isinstance(coin_id, str):
                    raise StageContractError(
                        self.stage_id,
                        "manifest coin missing valid id.",
                    )
                # Defensive path validation: coin_id is used to construct
                # filesystem paths, so it must be path-safe even if the
                # upstream manifest validator already enforces this.
                _validate_coin_id(coin_id, stage_id=self.stage_id)

                photos = coin.get("photos", {})
                if not isinstance(photos, dict):
                    raise StageContractError(
                        self.stage_id,
                        f"manifest coin {coin_id!r} has invalid photos.",
                    )
                for role_name, photo in photos.items():
                    if not isinstance(photo, dict):
                        continue
                    image_path = photo.get("path")
                    if not image_path or not isinstance(image_path, str):
                        raise StageContractError(
                            self.stage_id,
                            f"manifest coin {coin_id!r} photo {role_name!r} "
                            f"missing path.",
                        )

                    image_bytes = self._read_archive_image(
                        archive, image_path, coin_id, role_name
                    )
                    normalized_bytes, width, height = self._normalize_image(image_bytes)

                    role_file = _role_filename(role_name)
                    relative_path = f"{_NORMALIZED_SUBDIR}/{coin_id}/{role_file}.jpg"
                    output_path = stage_input.workspace / relative_path

                    # Ensure parent directory exists within workspace.
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(normalized_bytes)

                    artifact_key = f"normalized-{coin_id}-{role_file}"
                    artifacts[artifact_key] = StageArtifact(
                        relative_path=relative_path,
                        content_type=_JPEG_MIME,
                    )
                    dimensions[f"{coin_id}/{role_file}"] = {
                        "width": width,
                        "height": height,
                    }
                    normalized_count += 1
        finally:
            archive.close()

        return StageResult(
            artifacts=artifacts,
            metadata={
                "normalized_image_count": normalized_count,
                "normalized_dimensions": dimensions,
            },
        )

    def _read_manifest(self, stage_input: StageInput) -> dict:
        """Read and parse the upstream ``prepared-manifest`` artifact."""
        artifact = stage_input.artifacts.get(PREPARED_MANIFEST_ARTIFACT)
        if artifact is None:
            raise StageContractError(
                self.stage_id,
                f"requires upstream artifact {PREPARED_MANIFEST_ARTIFACT!r}.",
            )
        manifest_path = stage_input.workspace / artifact.relative_path
        try:
            payload = manifest_path.read_bytes()
        except OSError as exc:
            raise StageContractError(
                self.stage_id,
                f"declared artifact is not readable in the workspace: "
                f"{artifact.relative_path!r}.",
            ) from exc
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise StageContractError(
                self.stage_id,
                f"upstream manifest is not valid JSON: {exc}",
            ) from exc
        if not isinstance(data, dict):
            raise StageContractError(
                self.stage_id,
                "upstream manifest is not a JSON object.",
            )
        return data

    def _read_archive_image(
        self,
        archive: zipfile.ZipFile,
        image_path: str,
        coin_id: str,
        role_name: str,
    ) -> bytes:
        """Read one image payload from the archive with bounded size.

        The size bound is a coarse upper limit for an uncompressed RGBA
        image at ``MAX_IMAGE_DIMENSION``.  It does not protect against
        all pathological compressed images (e.g., a tiny ZIP entry that
        expands to billions of pixels), but it catches the common case
        of an archive entry that is already too large.  The subsequent
        ``_normalize_image`` call handles decompression-bomb protection
        via Pillow's own limits.
        """
        try:
            info = archive.getinfo(image_path)
        except KeyError as exc:
            raise StageExecutionError(
                self.stage_id,
                ValueError(
                    f"image path {image_path!r} not found in archive "
                    f"for coin {coin_id!r} role {role_name!r}."
                ),
            ) from exc

        # Coarse bound: uncompressed RGBA at max dimension.
        if info.file_size > MAX_IMAGE_DIMENSION * MAX_IMAGE_DIMENSION * 4:
            raise StageExecutionError(
                self.stage_id,
                ValueError(
                    f"image {image_path!r} exceeds size safety bound "
                    f"for coin {coin_id!r} role {role_name!r}."
                ),
            )

        try:
            payload = archive.read(image_path)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            raise StageExecutionError(
                self.stage_id,
                exc,
            ) from exc

        return payload

    def _normalize_image(self, payload: bytes) -> tuple[bytes, int, int]:
        """Decode, resize, convert to sRGB, strip metadata, save as JPEG.

        Returns ``(jpeg_bytes, width, height)``.

        Design notes:

        - ``DecompressionBombWarning`` is suppressed because this stage
          is intentionally designed to resize oversized images.  The
          warning would fire for images that exceed Pillow's default
          pixel-count limit but are still within our ``max_dimension``
          bound.  The ``DecompressionBombError`` (which occurs at a
          much higher hard limit) is still caught as a fatal error.

        - ``Image.verify()`` is intentionally omitted.  Pillow's
          ``Image.open()`` already performs basic header validation,
          and ``verify()`` is format-specific (not supported for all
          formats, and may behave differently across Pillow versions).
          Corrupt images are caught by the ``OSError`` / ``ValueError``
          handlers during ``open()``, ``convert()``, or ``save()``.
        """
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", Image.DecompressionBombWarning)
                with Image.open(BytesIO(payload)) as image:
                    # Explicit load to catch decode errors early.
                    image.load()

                    # Convert to RGB (sRGB).  Discard alpha and palette.
                    if image.mode != "RGB":
                        image = image.convert("RGB")  # type: ignore[assignment]

                    # Resize if the larger dimension exceeds the cap.
                    width, height = image.size
                    max_dim = max(width, height)
                    if max_dim > self._max_dimension:
                        ratio = self._max_dimension / max_dim
                        new_width = int(width * ratio)
                        new_height = int(height * ratio)
                        image = image.resize(  # type: ignore[assignment]
                            (new_width, new_height),
                            Image.LANCZOS,  # type: ignore[attr-defined]
                        )
                        width, height = image.size

                    # Save as baseline JPEG, quality 92, no EXIF, no progressive.
                    output = BytesIO()
                    image.save(
                        output,
                        format="JPEG",
                        quality=self._quality,
                        progressive=False,
                        optimize=False,
                    )
                    return output.getvalue(), width, height
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise StageExecutionError(
                self.stage_id,
                exc,
            ) from exc
