"""Obverse/reverse pairing stage for the import workflow (Sprint 8 Unit 5).

Confirms that the front and reverse images for each coin plausibly depict
opposite sides of the same object.  This is a heuristic sanity check, not
identification.  The stage is metadata-only: it consumes image artifacts and
emits pairing records with a bounded consistency score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .limits import MAX_IMAGE_DIMENSION, MAX_IMAGE_PIXELS
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
_WEIGHT_DIM = 0.30
_WEIGHT_ASPECT = 0.25
_WEIGHT_BRIGHTNESS = 0.25
_WEIGHT_CONTRAST = 0.20


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
) -> tuple[float, float, float, float, float]:
    """Compute deterministic pairing scores.

    Returns ``(consistency_score, dim_score, aspect_score,
    brightness_score, contrast_score)``.
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

    consistency = (
        _WEIGHT_DIM * dim_score
        + _WEIGHT_ASPECT * aspect_score
        + _WEIGHT_BRIGHTNESS * brightness_score
        + _WEIGHT_CONTRAST * contrast_score
    )

    return (
        round(min(1.0, max(0.0, consistency)), 4),
        round(dim_score, 4),
        round(aspect_score, 4),
        round(brightness_score, 4),
        round(contrast_score, 4),
    )


def _build_explanation(
    paired: bool,
    dim_score: float,
    aspect_score: float,
    brightness_score: float,
    contrast_score: float,
) -> str:
    """Produce a human-readable explanation of the pairing decision."""
    parts: list[str] = []
    if paired:
        parts.append("Images plausibly depict opposite sides of the same object.")
    else:
        parts.append("Images may not depict opposite sides of the same object.")
    parts.append(
        f"dimension={dim_score:.2f} aspect={aspect_score:.2f} "
        f"brightness={brightness_score:.2f} contrast={contrast_score:.2f}"
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

            front_path = stage_input.workspace / front_artifact.relative_path
            reverse_path = stage_input.workspace / reverse_artifact.relative_path

            for path, label in (
                (front_path, f"front ({front_key})"),
                (reverse_path, f"reverse ({reverse_key})"),
            ):
                _require_contained(
                    Path(
                        front_artifact.relative_path
                        if "front" in label
                        else reverse_artifact.relative_path
                    ),
                    stage_input.workspace,
                    stage_id=self.stage_id,
                    label=label,
                )
                if not path.exists():
                    raise StageContractError(
                        self.stage_id,
                        f"artifact not found in workspace: {path.name!r}.",
                    )

            # Load images and validate bounds.
            try:
                front_image = cv2.imread(str(front_path))
                if front_image is None:
                    raise StageExecutionError(
                        self.stage_id,
                        ValueError(f"front image could not be decoded: {front_path}"),
                    )
                reverse_image = cv2.imread(str(reverse_path))
                if reverse_image is None:
                    raise StageExecutionError(
                        self.stage_id,
                        ValueError(
                            f"reverse image could not be decoded: {reverse_path}"
                        ),
                    )
            except OSError as exc:
                raise StageExecutionError(self.stage_id, exc) from exc

            for image, label in ((front_image, "front"), (reverse_image, "reverse")):
                h, w = image.shape[:2]
                pixels = w * h
                if pixels > MAX_IMAGE_PIXELS:
                    raise StageContractError(
                        self.stage_id,
                        f"{label} image exceeds MAX_IMAGE_PIXELS: {pixels}.",
                    )
                if w > MAX_IMAGE_DIMENSION or h > MAX_IMAGE_DIMENSION:
                    raise StageContractError(
                        self.stage_id,
                        f"{label} image exceeds MAX_IMAGE_DIMENSION: {w}x{h}",
                    )

            (
                consistency_score,
                dim_score,
                aspect_score,
                brightness_score,
                contrast_score,
            ) = _compute_pairing_score(front_image, reverse_image)

            paired = consistency_score >= PAIRING_THRESHOLD

            record = PairingRecord(
                coin_id=coin_id,
                paired=paired,
                consistency_score=consistency_score,
                explanation=_build_explanation(
                    paired, dim_score, aspect_score, brightness_score, contrast_score
                ),
                front_width=front_image.shape[1],
                front_height=front_image.shape[0],
                reverse_width=reverse_image.shape[1],
                reverse_height=reverse_image.shape[0],
                dim_score=dim_score,
                aspect_score=aspect_score,
                brightness_score=brightness_score,
                contrast_score=contrast_score,
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
