"""Crop detection stage for the import workflow (Sprint 8 Unit 4).

Detects the coin region in normalized images using a rule-based contour
heuristic (Otsu thresholding with both polarities, circularity filtering).
Produces cropped image artifacts and deterministic crop-rectangle metadata.
Images where no confident crop is found fall back to a byte-for-byte copy
of the normalized source so downstream stages always have a ``cropped-*``
artifact to read.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .limits import MAX_IMAGE_DIMENSION, MAX_IMAGE_PIXELS
from .workflow_models import JsonValue, StageArtifact, StageInput, StageResult
from .workflow_pipeline import StageContractError, StageExecutionError

CROP_DETECTION_STAGE_ID = "crop-detection"

_CROP_SUBDIR = "cropped"
_JPEG_QUALITY = 95

# Normalized artifact prefix from upstream Unit 2.
_NORMALIZED_PREFIX = "normalized-"

# Defensive coin_id validation (same convention as Unit 2/3).
_SAFE_COIN_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# ---------------------------------------------------------------------------
# Contour qualification thresholds
# ---------------------------------------------------------------------------
MIN_AREA_RATIO = 0.08
MAX_AREA_RATIO = 0.98
MIN_ASPECT_RATIO = 0.75
MAX_ASPECT_RATIO = 1.25
MIN_CIRCULARITY = 0.82

# ---------------------------------------------------------------------------
# Confidence formula
# ---------------------------------------------------------------------------
TARGET_AREA_RATIO = 0.5
MIN_CROP_CONFIDENCE = 0.65

# ---------------------------------------------------------------------------
# Crop padding
# ---------------------------------------------------------------------------
CROP_PADDING_RATIO = 0.03


@dataclass(frozen=True, slots=True)
class CropRecord:
    """Immutable crop record for one normalized image."""

    coin_id: str
    role: str
    x: int
    y: int
    width: int
    height: int
    crop_confidence: float
    crop_applied: bool
    source_normalized_key: str
    source_width: int
    source_height: int

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "coin_id": self.coin_id,
            "role": self.role,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "crop_confidence": self.crop_confidence,
            "crop_applied": self.crop_applied,
            "source_normalized_key": self.source_normalized_key,
            "source_width": self.source_width,
            "source_height": self.source_height,
        }


def _require_contained(path: Path, base: Path, *, stage_id: str, label: str) -> None:
    """Raise StageContractError if *path* is not inside *base*.

    *path* must be a relative path; absolute paths are rejected.
    Parent traversal (``..``) is rejected regardless of the final resolved
    location so that the check cannot be bypassed by path normalization.
    """
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


def _parse_normalized_key(key: str) -> tuple[str, str] | None:
    """Parse a normalized artifact key into (coin_id, role).

    Keys follow ``normalized-{coin_id}-{role}``,
    e.g. ``normalized-coin-1-front``.
    """
    if not key.startswith(_NORMALIZED_PREFIX):
        return None
    tail = key[len(_NORMALIZED_PREFIX) :]
    parts = tail.rsplit("-", 1)
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def _qualify_contour(
    area: float,
    perimeter: float,
    bbox: tuple[int, int, int, int],
    image_area: float,
) -> tuple[float, float, float] | None:
    """Check whether a contour satisfies coin-region criteria.

    Returns ``(area_ratio, aspect_ratio, circularity)`` when the contour
    qualifies, or ``None`` otherwise.
    """
    if image_area <= 0 or perimeter <= 0:
        return None

    area_ratio = area / image_area
    if not (MIN_AREA_RATIO <= area_ratio <= MAX_AREA_RATIO):
        return None

    _, _, w, h = bbox
    if w <= 0 or h <= 0:
        return None

    aspect_ratio = min(w, h) / max(w, h)
    if not (MIN_ASPECT_RATIO <= aspect_ratio <= MAX_ASPECT_RATIO):
        return None

    circularity = 4.0 * math.pi * area / (perimeter * perimeter)
    if circularity < MIN_CIRCULARITY:
        return None

    return area_ratio, aspect_ratio, circularity


def _compute_confidence(
    area_ratio: float,
    aspect_ratio: float,
    circularity: float,
) -> float:
    """Compute a deterministic confidence score in [0.0, 1.0].

    Weights: circularity 40%, aspect 35%, area 25%.
    """
    circularity_score = min(1.0, circularity)
    aspect_score = max(0.0, 1.0 - abs(1.0 - aspect_ratio))
    area_score = max(0.0, 1.0 - abs(area_ratio - TARGET_AREA_RATIO) / TARGET_AREA_RATIO)

    return round(
        0.40 * circularity_score + 0.35 * aspect_score + 0.25 * area_score,
        4,
    )


def _apply_padding(
    x: int,
    y: int,
    w: int,
    h: int,
    source_w: int,
    source_h: int,
) -> tuple[int, int, int, int]:
    """Expand the crop rectangle by a fixed proportional margin.

    Clamps the result to image bounds.  Returns ``(x, y, width, height)``.
    """
    pad = max(1, int(min(w, h) * CROP_PADDING_RATIO))

    new_x = max(0, x - pad)
    new_y = max(0, y - pad)
    new_right = min(source_w, x + w + pad)
    new_bottom = min(source_h, y + h + pad)

    return new_x, new_y, new_right - new_x, new_bottom - new_y


def _find_best_crop(image: np.ndarray) -> tuple[int, int, int, int, float] | None:
    """Find the best coin contour and return ``(x, y, w, h, confidence)``.

    Uses Otsu thresholding with both polarities, filters contours by area
    ratio, aspect ratio, and circularity, and returns the highest-confidence
    padded crop rectangle.  Returns ``None`` when no qualifying contour is
    found.
    """
    height, width = image.shape[:2]
    image_area = float(height * width)
    if image_area <= 0:
        return None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    candidates: list[tuple[float, float, int, int, int, int, int, int]] = []

    # Evaluate both threshold polarities.
    for flags in (
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    ):
        _, mask = cv2.threshold(blurred, 0, 255, flags)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            if area <= 0 or perimeter <= 0:
                continue

            from typing import cast

            bbox = cast(tuple[int, int, int, int], cv2.boundingRect(contour))
            qualified = _qualify_contour(area, perimeter, bbox, image_area)
            if qualified is None:
                continue

            area_ratio, aspect_ratio, circularity = qualified
            confidence = _compute_confidence(area_ratio, aspect_ratio, circularity)

            bx, by, bw, bh = bbox
            candidates.append((confidence, int(area), by, bx, bw, bh, width, height))

    if not candidates:
        return None

    # Deterministic tie-breaker: highest confidence, then largest area,
    # then top-most, then left-most, then smallest dimensions.
    candidates.sort(key=lambda c: (-c[0], -c[1], c[2], c[3], c[4], c[5]))
    best = candidates[0]
    confidence, _, by, bx, bw, bh, source_w, source_h = best

    x, y, w, h = _apply_padding(bx, by, bw, bh, source_w, source_h)
    return x, y, w, h, confidence


class CropDetectionStage:
    """Detect coin regions in normalized images with deterministic contours.

    Consumes the normalized-artifact mapping from the upstream
    ``ImageNormalizationStage`` and produces a cropped artifact for
    every image.  This is a workspace-writing stage.
    """

    @property
    def stage_id(self) -> str:
        return CROP_DETECTION_STAGE_ID

    def execute(self, stage_input: StageInput) -> StageResult:
        # Discover normalized artifacts from Unit 2.
        normalized: list[tuple[str, str, str, StageArtifact]] = []
        for key, artifact in stage_input.artifacts.items():
            parsed = _parse_normalized_key(key)
            if parsed is None:
                continue
            coin_id, role = parsed
            normalized.append((key, coin_id, role, artifact))

        if not normalized:
            raise StageContractError(
                self.stage_id,
                "no normalized image artifacts found in upstream pipeline.",
            )

        crop_records: list[CropRecord] = []
        crop_applied_count = 0
        seen_identities: set[tuple[str, str]] = set()

        for source_key, coin_id, role, artifact in sorted(
            normalized, key=lambda t: (t[1], t[2], t[0])
        ):
            if not _SAFE_COIN_ID.match(coin_id):
                raise StageContractError(
                    self.stage_id,
                    f"invalid coin_id in artifact key: {coin_id!r}.",
                )

            identity = (coin_id, role)
            if identity in seen_identities:
                raise StageContractError(
                    self.stage_id,
                    f"duplicate (coin_id, role) pair: {identity!r}.",
                )
            seen_identities.add(identity)

            image_path = stage_input.workspace / artifact.relative_path

            # Verify source path stays inside workspace BEFORE existence.
            # An outside path must fail as containment regardless of whether
            # the external target exists.
            _require_contained(
                Path(artifact.relative_path),
                stage_input.workspace,
                stage_id=self.stage_id,
                label="normalized input",
            )

            if not image_path.exists():
                raise StageContractError(
                    self.stage_id,
                    f"normalized artifact not found in workspace: "
                    f"{artifact.relative_path!r}.",
                )

            # Prepare crop output directory and verify containment.
            crop_dir = stage_input.workspace / _CROP_SUBDIR / coin_id
            crop_dir.mkdir(parents=True, exist_ok=True)
            cropped_path = crop_dir / f"{role}.jpg"
            _require_contained(
                Path(_CROP_SUBDIR) / coin_id / f"{role}.jpg",
                stage_input.workspace,
                stage_id=self.stage_id,
                label="cropped output",
            )

            # Read and validate source dimensions.
            try:
                image = cv2.imread(str(image_path))
                if image is None:
                    raise StageExecutionError(
                        CROP_DETECTION_STAGE_ID,
                        ValueError(f"image could not be decoded: {image_path}"),
                    )
            except OSError as exc:
                raise StageExecutionError(
                    CROP_DETECTION_STAGE_ID,
                    exc,
                ) from exc

            source_h, source_w = image.shape[:2]
            source_pixels = source_w * source_h
            if source_pixels > MAX_IMAGE_PIXELS:
                raise StageContractError(
                    self.stage_id,
                    f"normalized image exceeds MAX_IMAGE_PIXELS: " f"{source_pixels}.",
                )
            if source_w > MAX_IMAGE_DIMENSION or source_h > MAX_IMAGE_DIMENSION:
                raise StageContractError(
                    self.stage_id,
                    f"normalized image exceeds MAX_IMAGE_DIMENSION: "
                    f"{source_w}x{source_h}",
                )

            crop_result = _find_best_crop(image)

            if crop_result is not None and crop_result[4] >= MIN_CROP_CONFIDENCE:
                x, y, w, h, confidence = crop_result
                crop_applied = True
                crop_applied_count += 1

                # Validate crop dimensions.
                if w <= 0 or h <= 0:
                    raise StageExecutionError(
                        self.stage_id,
                        RuntimeError(f"computed empty crop rectangle: {w}x{h}"),
                    )
                if w > MAX_IMAGE_DIMENSION or h > MAX_IMAGE_DIMENSION:
                    raise StageExecutionError(
                        self.stage_id,
                        RuntimeError(
                            f"computed crop exceeds MAX_IMAGE_DIMENSION: " f"{w}x{h}"
                        ),
                    )

                # Encode cropped region as JPEG.
                crop_region = image[y : y + h, x : x + w]
                try:
                    pil_crop = Image.fromarray(
                        cv2.cvtColor(crop_region, cv2.COLOR_BGR2RGB)
                    )
                    pil_crop.save(
                        str(cropped_path),
                        format="JPEG",
                        quality=_JPEG_QUALITY,
                    )
                except (OSError, ValueError) as exc:
                    raise StageExecutionError(
                        CROP_DETECTION_STAGE_ID,
                        exc,
                    ) from exc
            else:
                # Fallback: byte-for-byte copy of normalized source.
                crop_applied = False
                confidence = 0.0
                x, y, w, h = 0, 0, source_w, source_h
                try:
                    cropped_path.write_bytes(image_path.read_bytes())
                except OSError as exc:
                    raise StageExecutionError(
                        CROP_DETECTION_STAGE_ID,
                        exc,
                    ) from exc

            record = CropRecord(
                coin_id=coin_id,
                role=role,
                x=x,
                y=y,
                width=w,
                height=h,
                crop_confidence=confidence,
                crop_applied=crop_applied,
                source_normalized_key=source_key,
                source_width=source_w,
                source_height=source_h,
            )
            crop_records.append(record)

        # Sort for deterministic serialized order.
        crop_records.sort(key=lambda r: (r.coin_id, r.role, r.source_normalized_key))

        return StageResult(
            artifacts={
                f"cropped-{r.coin_id}-{r.role}": StageArtifact(
                    relative_path=f"cropped/{r.coin_id}/{r.role}.jpg",
                    content_type="image/jpeg",
                )
                for r in crop_records
            },
            metadata={
                "crop_applied_image_count": crop_applied_count,
                "crop_records": [r.to_dict() for r in crop_records],
            },
        )
