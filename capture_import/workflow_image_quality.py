"""Image quality scoring stage for the import workflow (Sprint 8 Unit 3).

Scores every normalized image artifact produced by the upstream
``image-normalization`` stage.  This is a metadata-only stage: it reads
workspace artifacts and emits JSON-safe quality metadata.

All metrics are deterministic: fixed OpenCV parameters, integer-rounded
scores.  The stage does not fail on poor-quality images; it records their
scores and continues.  Missing or unreadable artifacts raise
``StageContractError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .workflow_models import JsonValue, StageArtifact, StageInput, StageResult
from .workflow_pipeline import StageContractError, StageExecutionError

IMAGE_QUALITY_SCORING_STAGE_ID = "image-quality-scoring"

# Thresholds adapted from image_assessment.py Level A metrics.
_MIN_TINY_DIMENSION = 300
_MIN_GOOD_DIMENSION = 800
_VERY_LOW_SHARPNESS = 20.0
_MODERATE_BLUR_SHARPNESS = 80.0
_LOW_CONTRAST = 20.0
_UNDEREXPOSED_BRIGHTNESS = 45.0
_OVEREXPOSED_BRIGHTNESS = 215.0
_BLOWN_HIGHLIGHT_RATIO = 0.12

# Normalized artifact prefix from Unit 2.
_NORMALIZED_PREFIX = "normalized-"


class ReadinessDecision(str, Enum):
    """Downstream readiness derived from quality metrics."""

    READY = "READY"
    MAYBE = "MAYBE"
    NOT_READY = "NOT_READY"


class QualityConfidence(str, Enum):
    """Confidence in the quality assessment."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True, slots=True)
class PhotoQualityRecord:
    """Immutable quality record for one normalized image."""

    coin_id: str
    role: str
    width: int
    height: int
    sharpness: int
    contrast: int
    brightness: int
    resolution: int
    blown_highlight_ratio: float
    readiness_score: int
    decision: str
    confidence: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "coin_id": self.coin_id,
            "role": self.role,
            "width": self.width,
            "height": self.height,
            "sharpness": self.sharpness,
            "contrast": self.contrast,
            "brightness": self.brightness,
            "resolution": self.resolution,
            "blown_highlight_ratio": self.blown_highlight_ratio,
            "readiness_score": self.readiness_score,
            "decision": self.decision,
            "confidence": self.confidence,
        }


def _parse_normalized_key(key: str) -> tuple[str, str] | None:
    """Parse a normalized artifact key into (coin_id, role).

    Unit 2 artifact keys follow ``normalized-{coin_id}-{role}``,
    e.g. ``normalized-coin-1-front``.
    """
    if not key.startswith(_NORMALIZED_PREFIX):
        return None
    tail = key[len(_NORMALIZED_PREFIX) :]
    parts = tail.rsplit("-", 1)
    if len(parts) != 2:
        return None
    coin_id, role = parts
    return coin_id, role


def _compute_metrics(image_path: Path) -> dict[str, Any]:
    """Read an image and compute deterministic Level A metrics.

    Returns a dict with ``width``, ``height``, ``sharpness`` (int),
    ``contrast`` (int), ``brightness`` (int), ``resolution`` (int),
    ``blown_highlight_ratio`` (float rounded to 5 decimals).

    Raises ``StageExecutionError`` on decode failure.
    """
    try:
        image = cv2.imread(str(image_path))
        if image is None:
            raise StageExecutionError(
                IMAGE_QUALITY_SCORING_STAGE_ID,
                ValueError(f"image could not be decoded: {image_path}"),
            )
    except (OSError, ValueError) as exc:
        raise StageExecutionError(
            IMAGE_QUALITY_SCORING_STAGE_ID,
            exc,
        ) from exc

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Deterministic fixed-parameter metrics.
    sharpness = int(np.var(cv2.Laplacian(gray, cv2.CV_64F)))
    contrast = int(np.std(gray))
    brightness = int(np.mean(gray))
    blown = float(np.mean(gray >= 245))

    return {
        "width": int(width),
        "height": int(height),
        "sharpness": sharpness,
        "contrast": contrast,
        "brightness": brightness,
        "resolution": min(int(width), int(height)),
        "blown_highlight_ratio": round(blown, 5),
    }


def _score_and_decide(
    metrics: dict[str, Any],
) -> tuple[int, ReadinessDecision, QualityConfidence]:
    """Score metrics and derive decision and confidence.

    Scoring formula (adapted from image_assessment.py):
    - Start at 100.
    - Resolution: <300 → -35, <800 → -15.
    - Sharpness: <20 → -30, <80 → -15.
    - Contrast: <20 → -15.
    - Brightness: <45 → -20, >215 → -20.
    - Blown highlights: >0.12 → -15.
    - Clamp to 0-100.

    Decision:
    - <50 → NOT_READY
    - ≥80 → READY
    - otherwise → MAYBE

    Confidence:
    - 3+ issue categories → LOW
    - 1-2 issue categories → MEDIUM
    - no issues → HIGH
    """
    score = 100
    issues = []

    resolution = metrics["resolution"]
    if resolution < _MIN_TINY_DIMENSION:
        score -= 35
        issues.append("resolution")
    elif resolution < _MIN_GOOD_DIMENSION:
        score -= 15
        issues.append("resolution")

    sharpness = metrics["sharpness"]
    if sharpness < _VERY_LOW_SHARPNESS:
        score -= 30
        issues.append("sharpness")
    elif sharpness < _MODERATE_BLUR_SHARPNESS:
        score -= 15
        issues.append("sharpness")

    contrast = metrics["contrast"]
    if contrast < _LOW_CONTRAST:
        score -= 15
        issues.append("contrast")

    brightness = metrics["brightness"]
    if brightness < _UNDEREXPOSED_BRIGHTNESS:
        score -= 20
        issues.append("brightness")
    elif brightness > _OVEREXPOSED_BRIGHTNESS:
        score -= 20
        issues.append("brightness")

    if metrics["blown_highlight_ratio"] > _BLOWN_HIGHLIGHT_RATIO:
        score -= 15
        issues.append("blown_highlight")

    score = max(0, min(100, score))

    if score < 50:
        decision = ReadinessDecision.NOT_READY
    elif score >= 80:
        decision = ReadinessDecision.READY
    else:
        decision = ReadinessDecision.MAYBE

    issue_count = len(issues)
    if issue_count >= 3:
        confidence = QualityConfidence.LOW
    elif issue_count >= 1:
        confidence = QualityConfidence.MEDIUM
    else:
        confidence = QualityConfidence.HIGH

    return score, decision, confidence


class ImageQualityScoringStage:
    """Score normalized images with deterministic Level A quality metrics.

    Consumes the normalized-artifact mapping from the upstream
    ``ImageNormalizationStage`` and produces a quality record for
    every image.  This is a metadata-only stage.
    """

    @property
    def stage_id(self) -> str:
        return IMAGE_QUALITY_SCORING_STAGE_ID

    def execute(self, stage_input: StageInput) -> StageResult:
        # Discover normalized artifacts from Unit 2.
        normalized: list[tuple[str, str, StageArtifact]] = []
        for key, artifact in stage_input.artifacts.items():
            parsed = _parse_normalized_key(key)
            if parsed is not None:
                normalized.append((parsed[0], parsed[1], artifact))

        if not normalized:
            raise StageContractError(
                self.stage_id,
                "no normalized image artifacts found in upstream pipeline.",
            )

        quality_records: list[JsonValue] = []

        for coin_id, role, artifact in normalized:
            image_path = stage_input.workspace / artifact.relative_path
            if not image_path.exists():
                raise StageContractError(
                    self.stage_id,
                    f"normalized artifact not found in workspace: "
                    f"{artifact.relative_path!r}.",
                )

            metrics = _compute_metrics(image_path)
            score, decision, confidence = _score_and_decide(metrics)

            record = PhotoQualityRecord(
                coin_id=coin_id,
                role=role,
                width=metrics["width"],
                height=metrics["height"],
                sharpness=metrics["sharpness"],
                contrast=metrics["contrast"],
                brightness=metrics["brightness"],
                resolution=metrics["resolution"],
                blown_highlight_ratio=metrics["blown_highlight_ratio"],
                readiness_score=score,
                decision=decision.value,
                confidence=confidence.value,
            )
            quality_records.append(record.to_dict())

        return StageResult(
            artifacts={},
            metadata={
                "quality_scored_image_count": len(quality_records),
                "quality_records": quality_records,
            },
        )
