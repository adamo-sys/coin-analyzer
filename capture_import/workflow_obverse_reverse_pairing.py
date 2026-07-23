"""Obverse/reverse pairing stage for the import workflow (Sprint 8 Unit 5).

Confirms that the front and reverse images for each coin plausibly depict
opposite sides of the same object.  This is a heuristic sanity check, not
identification.  The stage is metadata-only: it consumes image artifacts and
emits pairing records with a bounded consistency score.
"""

from __future__ import annotations

import os
import re
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import cv2
import numpy as np
from PIL import Image

from ._filesystem import (
    handle_matches_path,
    open_plain_directory_handle,
    require_plain_directory,
    require_plain_regular_file,
)
from .limits import (
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_SIZE,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_IMAGE_TYPES,
)
from .workflow_models import JsonValue, StageArtifact, StageInput, StageResult
from .workflow_pipeline import StageContractError, StageExecutionError

OBVERSE_REVERSE_PAIRING_STAGE_ID = "obverse-reverse-pairing"

# Artifact prefixes the stage recognises.
_CROPPED_PREFIX = "cropped-"
_NORMALIZED_PREFIX = "normalized-"

# Defensive coin_id validation (same convention as Units 2–4).
_SAFE_COIN_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Pairing decision threshold.
PAIRING_THRESHOLD = 0.6

# Metric weights for consistency score.
_WEIGHT_DIM = 0.15
_WEIGHT_ASPECT = 0.10
_WEIGHT_BRIGHTNESS = 0.15
_WEIGHT_CONTRAST = 0.15
_WEIGHT_HISTOGRAM = 0.45

_COLOR_HISTOGRAM_BINS = 8
_READ_CHUNK = 1024 * 1024


@dataclass(frozen=True, slots=True)
class PairingRecord:
    """Immutable pairing record for one coin."""

    coin_id: str
    paired: bool
    consistency_score: float
    explanation: str
    front_width: int
    front_height: int
    reverse_width: int
    reverse_height: int
    dim_score: float
    aspect_score: float
    brightness_score: float
    contrast_score: float
    color_histogram_score: float

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "coin_id": self.coin_id,
            "paired": self.paired,
            "consistency_score": self.consistency_score,
            "explanation": self.explanation,
            "front_width": self.front_width,
            "front_height": self.front_height,
            "reverse_width": self.reverse_width,
            "reverse_height": self.reverse_height,
            "dim_score": self.dim_score,
            "aspect_score": self.aspect_score,
            "brightness_score": self.brightness_score,
            "contrast_score": self.contrast_score,
            "color_histogram_score": self.color_histogram_score,
        }


def _parse_artifact_key(key: str) -> tuple[str, str, str] | None:
    """Parse an artifact key into (prefix, coin_id, role).

    Recognises ``cropped-{coin_id}-{role}`` and
    ``normalized-{coin_id}-{role}``.
    """
    for prefix in (_CROPPED_PREFIX, _NORMALIZED_PREFIX):
        if key.startswith(prefix):
            tail = key[len(prefix) :]
            parts = tail.rsplit("-", 1)
            if len(parts) == 2:
                return prefix[:-1], parts[0], parts[1]
    return None


def _require_contained(path: Path, base: Path, *, stage_id: str, label: str) -> None:
    """Raise StageContractError if *path* is not inside *base*."""
    if path.is_absolute():
        raise StageContractError(stage_id, f"{label} is absolute: {path!r}.")
    if ".." in path.parts:
        raise StageContractError(
            stage_id, f"{label} contains parent traversal: {path!r}."
        )
    base_resolved = base.resolve()
    joined = base_resolved / path
    try:
        joined.relative_to(base_resolved)
    except ValueError as exc:
        raise StageContractError(
            stage_id, f"{label} escapes workspace: {path!r}."
        ) from exc


def _ratio_similarity(a: float, b: float) -> float:
    """Return similarity in [0.0, 1.0] for two positive values."""
    if a <= 0 or b <= 0:
        return 0.0
    return min(a, b) / max(a, b)


def _open_artifact_readonly(path: Path) -> BinaryIO:
    """Open one plain artifact without following a substituted final component."""

    require_plain_regular_file(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    handle = os.fdopen(descriptor, "rb")
    if not handle_matches_path(handle, path):
        handle.close()
        raise OSError("The artifact identity changed while it was opened.")
    return handle


def _read_bounded_artifact(
    workspace: Path,
    relative_path: Path,
    *,
    stage_id: str,
    label: str,
    max_bytes: int | None = None,
) -> bytes:
    """Read one workspace artifact through held directory and file identities."""

    if max_bytes is None:
        max_bytes = MAX_IMAGE_SIZE
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise StageContractError(stage_id, f"{label} has an invalid read limit.")
    _require_contained(
        relative_path,
        workspace,
        stage_id=stage_id,
        label=label,
    )
    candidate = workspace / relative_path
    try:
        require_plain_directory(workspace)
        require_plain_directory(candidate.parent)
        with (
            open_plain_directory_handle(workspace) as workspace_handle,
            open_plain_directory_handle(candidate.parent) as parent_handle,
        ):
            handle = _open_artifact_readonly(candidate)
            try:
                before = os.fstat(handle.fileno())
                if before.st_size > max_bytes:
                    raise StageContractError(
                        stage_id,
                        f"{label} exceeds its byte limit.",
                    )
                chunks: list[bytes] = []
                total = 0
                while total <= max_bytes:
                    chunk = handle.read(min(_READ_CHUNK, max_bytes + 1 - total))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                if total > max_bytes:
                    raise StageContractError(
                        stage_id,
                        f"{label} exceeds its byte limit.",
                    )
                after = os.fstat(handle.fileno())
                if (
                    before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns
                    or before.st_ctime_ns != after.st_ctime_ns
                    or total != before.st_size
                ):
                    raise OSError("The artifact changed while it was read.")
                if (
                    not workspace_handle.verify_path()
                    or not parent_handle.verify_path()
                    or not handle_matches_path(handle, candidate)
                ):
                    raise OSError("The artifact path identity changed while it was read.")
                return b"".join(chunks)
            finally:
                handle.close()
    except StageContractError:
        raise
    except (FileNotFoundError, OSError) as exc:
        raise StageContractError(
            stage_id,
            f"{label} is not a stable plain file inside the workflow workspace.",
        ) from exc


def _decode_bounded_image(
    payload: bytes,
    artifact: StageArtifact,
    *,
    stage_id: str,
    label: str,
) -> np.ndarray:
    """Validate the encoded contract before performing one bounded OpenCV decode."""

    declared_type = artifact.content_type
    suffix = Path(artifact.relative_path).suffix.lower()
    if declared_type not in SUPPORTED_IMAGE_TYPES:
        raise StageContractError(
            stage_id,
            f"{label} has unsupported content type.",
        )
    if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
        raise StageContractError(
            stage_id,
            f"{label} has unsupported filename extension.",
        )

    if payload.startswith(b"\xff\xd8"):
        signature_format = "JPEG"
    elif payload.startswith(b"\x89PNG\r\n\x1a\n"):
        signature_format = "PNG"
    else:
        try:
            with Image.open(BytesIO(payload)) as unsupported_probe:
                unsupported_format = unsupported_probe.format
        except (OSError, SyntaxError, ValueError) as exc:
            raise StageExecutionError(
                stage_id,
                ValueError(f"{label} could not be validated as an image."),
            ) from exc
        raise StageContractError(
            stage_id,
            f"{label} uses unsupported encoded format {unsupported_format!r}.",
        )

    expected_format = "JPEG" if declared_type == "image/jpeg" else "PNG"
    expected_suffix = ".jpg" if expected_format == "JPEG" else ".png"
    if signature_format != expected_format or suffix != expected_suffix:
        raise StageContractError(
            stage_id,
            f"{label} bytes, content type, and extension disagree.",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as probe:
                width, height = probe.size
                if probe.format != expected_format or getattr(probe, "n_frames", 1) != 1:
                    raise StageContractError(
                        stage_id,
                        f"{label} does not match the accepted single-image format.",
                    )
                if width < 1 or height < 1:
                    raise StageContractError(stage_id, f"{label} has invalid dimensions.")
                if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                    raise StageContractError(
                        stage_id,
                        f"{label} exceeds MAX_IMAGE_DIMENSION.",
                    )
                if width * height > MAX_IMAGE_PIXELS:
                    raise StageContractError(
                        stage_id,
                        f"{label} exceeds MAX_IMAGE_PIXELS.",
                    )
                probe.verify()
    except StageContractError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        SyntaxError,
        ValueError,
    ) as exc:
        raise StageExecutionError(
            stage_id,
            ValueError(f"{label} could not be validated as an image."),
        ) from exc

    try:
        encoded = np.frombuffer(payload, dtype=np.uint8)
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    except (cv2.error, MemoryError, ValueError) as exc:
        raise StageExecutionError(stage_id, exc) from exc
    if decoded is None or decoded.shape[:2] != (height, width):
        raise StageExecutionError(
            stage_id,
            ValueError(f"{label} could not be decoded consistently."),
        )
    return decoded


def _compute_color_histogram(image: np.ndarray) -> np.ndarray:
    """Return a deterministic, normalized joint BGR color histogram."""

    pixel_count = image.shape[0] * image.shape[1]
    histogram = cv2.calcHist(
        [image],
        [0, 1, 2],
        None,
        [_COLOR_HISTOGRAM_BINS] * 3,
        [0, 256] * 3,
    ).reshape(-1)
    return histogram.astype(np.float64) / float(pixel_count)


def _color_histogram_similarity(front: np.ndarray, reverse: np.ndarray) -> float:
    """Return fixed-bin histogram intersection in the closed interval [0, 1]."""

    front_histogram = _compute_color_histogram(front)
    reverse_histogram = _compute_color_histogram(reverse)
    intersection = float(np.minimum(front_histogram, reverse_histogram).sum())
    return min(1.0, max(0.0, intersection))


def _compute_image_metrics(image: np.ndarray) -> tuple[float, float, float, float]:
    """Compute explainable metrics from an image.

    Returns ``(mean_brightness, contrast, aspect_ratio, pixel_count)``.
    """
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(gray.mean())
    contrast = float(gray.std())
    aspect_ratio = width / height if height > 0 else 0.0
    pixel_count = width * height
    return mean_brightness, contrast, aspect_ratio, pixel_count


def _compute_pairing_score(
    front: np.ndarray,
    reverse: np.ndarray,
) -> tuple[float, float, float, float, float, float]:
    """Compute deterministic pairing scores.

    Returns ``(consistency_score, dim_score, aspect_score,
    brightness_score, contrast_score, color_histogram_score)``.
    """
    f_mean, f_contrast, f_aspect, f_pixels = _compute_image_metrics(front)
    r_mean, r_contrast, r_aspect, r_pixels = _compute_image_metrics(reverse)

    f_h, f_w = front.shape[:2]
    r_h, r_w = reverse.shape[:2]

    dim_score = (
        _ratio_similarity(float(f_w), float(r_w))
        + _ratio_similarity(float(f_h), float(r_h))
    ) / 2.0

    aspect_score = _ratio_similarity(f_aspect, r_aspect)

    brightness_diff = abs(f_mean - r_mean)
    brightness_score = max(0.0, 1.0 - brightness_diff / 255.0)

    # Contrast can vary more than brightness; use a softer divisor.
    contrast_diff = abs(f_contrast - r_contrast)
    contrast_score = max(0.0, 1.0 - contrast_diff / 128.0)

    color_histogram_score = _color_histogram_similarity(front, reverse)

    consistency = (
        _WEIGHT_DIM * dim_score
        + _WEIGHT_ASPECT * aspect_score
        + _WEIGHT_BRIGHTNESS * brightness_score
        + _WEIGHT_CONTRAST * contrast_score
        + _WEIGHT_HISTOGRAM * color_histogram_score
    )

    return (
        round(min(1.0, max(0.0, consistency)), 4),
        round(dim_score, 4),
        round(aspect_score, 4),
        round(brightness_score, 4),
        round(contrast_score, 4),
        round(color_histogram_score, 4),
    )


def _build_explanation(
    paired: bool,
    dim_score: float,
    aspect_score: float,
    brightness_score: float,
    contrast_score: float,
    color_histogram_score: float,
) -> str:
    """Produce a human-readable explanation of the pairing decision."""
    parts: list[str] = []
    if paired:
        parts.append("Images plausibly depict opposite sides of the same object.")
    else:
        parts.append("Images may not depict opposite sides of the same object.")
    parts.append(
        f"dimension={dim_score:.2f} aspect={aspect_score:.2f} "
        f"brightness={brightness_score:.2f} contrast={contrast_score:.2f} "
        f"color_histogram={color_histogram_score:.2f}"
    )
    return " ".join(parts)


class ObverseReversePairingStage:
    """Heuristic consistency check between front and reverse images per coin.

    Consumes cropped artifacts (preferred) or normalized artifacts and emits
    a pairing record for every coin that has both front and reverse images.
    """

    @property
    def stage_id(self) -> str:
        return OBVERSE_REVERSE_PAIRING_STAGE_ID

    def execute(self, stage_input: StageInput) -> StageResult:
        # Collect eligible artifacts by coin_id and role.
        # Prefer cropped over normalized when both exist.
        by_coin: dict[str, dict[str, tuple[str, StageArtifact]]] = {}
        for key, artifact in stage_input.artifacts.items():
            parsed = _parse_artifact_key(key)
            if parsed is None:
                continue
            prefix, coin_id, role = parsed
            if role not in {"front", "reverse"}:
                continue
            if not _SAFE_COIN_ID.match(coin_id):
                raise StageContractError(
                    self.stage_id,
                    f"invalid coin_id in artifact key: {coin_id!r}.",
                )
            coin_map = by_coin.setdefault(coin_id, {})
            # Prefer cropped ("cropped" prefix) over normalized.
            existing = coin_map.get(role)
            if existing is None or prefix == "cropped":
                coin_map[role] = (key, artifact)

        if not by_coin:
            raise StageContractError(
                self.stage_id,
                "no eligible front/reverse image artifacts found in upstream pipeline.",
            )

        pairing_records: list[PairingRecord] = []

        for coin_id in sorted(by_coin):
            roles = by_coin[coin_id]
            if "front" not in roles or "reverse" not in roles:
                raise StageContractError(
                    self.stage_id,
                    f"coin {coin_id!r} is missing required front or reverse image.",
                )

            front_key, front_artifact = roles["front"]
            reverse_key, reverse_artifact = roles["reverse"]

            front_payload = _read_bounded_artifact(
                stage_input.workspace,
                Path(front_artifact.relative_path),
                stage_id=self.stage_id,
                label=f"front ({front_key})",
            )
            reverse_payload = _read_bounded_artifact(
                stage_input.workspace,
                Path(reverse_artifact.relative_path),
                stage_id=self.stage_id,
                label=f"reverse ({reverse_key})",
            )
            front_image = _decode_bounded_image(
                front_payload,
                front_artifact,
                stage_id=self.stage_id,
                label=f"front ({front_key})",
            )
            reverse_image = _decode_bounded_image(
                reverse_payload,
                reverse_artifact,
                stage_id=self.stage_id,
                label=f"reverse ({reverse_key})",
            )

            (
                consistency_score,
                dim_score,
                aspect_score,
                brightness_score,
                contrast_score,
                color_histogram_score,
            ) = _compute_pairing_score(front_image, reverse_image)

            paired = consistency_score >= PAIRING_THRESHOLD

            record = PairingRecord(
                coin_id=coin_id,
                paired=paired,
                consistency_score=consistency_score,
                explanation=_build_explanation(
                    paired,
                    dim_score,
                    aspect_score,
                    brightness_score,
                    contrast_score,
                    color_histogram_score,
                ),
                front_width=front_image.shape[1],
                front_height=front_image.shape[0],
                reverse_width=reverse_image.shape[1],
                reverse_height=reverse_image.shape[0],
                dim_score=dim_score,
                aspect_score=aspect_score,
                brightness_score=brightness_score,
                contrast_score=contrast_score,
                color_histogram_score=color_histogram_score,
            )
            pairing_records.append(record)

        return StageResult(
            artifacts={},
            metadata={
                "paired_coin_count": sum(1 for r in pairing_records if r.paired),
                "total_coin_count": len(pairing_records),
                "pairing_records": [r.to_dict() for r in pairing_records],
            },
        )
