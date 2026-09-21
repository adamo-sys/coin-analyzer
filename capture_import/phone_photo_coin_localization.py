"""Deterministic Hough-circle localization for phone-photo coin images."""

from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np


LOCALIZATION_MAX_DIMENSION = 1200
LOCALIZATION_PADDING_RATIO = 0.10
HOUGH_DP = 1.2
HOUGH_MIN_DISTANCE_RATIO = 0.20
HOUGH_PARAM1 = 120
HOUGH_PARAM2 = 45
HOUGH_MIN_RADIUS_RATIO = 0.08
HOUGH_MAX_RADIUS_RATIO = 0.48


@dataclass(frozen=True, slots=True)
class CoinCircleLocalization:
    """One selected coin circle mapped to original-image coordinates."""

    center_x: int
    center_y: int
    radius: int
    score: float
    radius_ratio: float
    center_distance: float
    outside_ratio: float
    crop_x: int
    crop_y: int
    crop_width: int
    crop_height: int
    source_width: int
    source_height: int

    def __post_init__(self) -> None:
        if self.source_width <= 0 or self.source_height <= 0:
            raise ValueError("source dimensions must be positive.")
        if self.radius <= 0:
            raise ValueError("radius must be positive.")
        if not (0 <= self.center_x < self.source_width):
            raise ValueError("center_x must be inside the source image.")
        if not (0 <= self.center_y < self.source_height):
            raise ValueError("center_y must be inside the source image.")
        if self.crop_width <= 0 or self.crop_height <= 0:
            raise ValueError("crop dimensions must be positive.")
        if self.crop_x < 0 or self.crop_y < 0:
            raise ValueError("crop origin must be non-negative.")
        if self.crop_x + self.crop_width > self.source_width:
            raise ValueError("crop exceeds source width.")
        if self.crop_y + self.crop_height > self.source_height:
            raise ValueError("crop exceeds source height.")
        for name in ("score", "radius_ratio", "center_distance", "outside_ratio"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite.")


def localize_coin_circle(image: np.ndarray) -> CoinCircleLocalization | None:
    """Return the highest-ranked Hough circle, or None when none is found."""

    if not isinstance(image, np.ndarray) or image.ndim not in {2, 3}:
        raise ValueError("image must be a 2D or 3D numpy array.")
    source_h, source_w = image.shape[:2]
    if source_w <= 0 or source_h <= 0:
        raise ValueError("image dimensions must be positive.")

    scale = min(1.0, LOCALIZATION_MAX_DIMENSION / max(source_w, source_h))
    detect_w = max(1, int(round(source_w * scale)))
    detect_h = max(1, int(round(source_h * scale)))
    if scale < 1.0:
        detection = cv2.resize(
            image, (detect_w, detect_h), interpolation=cv2.INTER_AREA
        )
    else:
        detection = image

    if detection.ndim == 3:
        gray = cv2.cvtColor(detection, cv2.COLOR_BGR2GRAY)
    else:
        gray = detection
    gray = cv2.medianBlur(gray, 9)

    minimum_dimension = min(detect_w, detect_h)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=HOUGH_DP,
        minDist=max(1.0, HOUGH_MIN_DISTANCE_RATIO * minimum_dimension),
        param1=HOUGH_PARAM1,
        param2=HOUGH_PARAM2,
        minRadius=max(1, int(HOUGH_MIN_RADIUS_RATIO * minimum_dimension)),
        maxRadius=max(2, int(HOUGH_MAX_RADIUS_RATIO * minimum_dimension)),
    )
    if circles is None or circles.size == 0:
        return None

    candidates: list[tuple[float, float, float, float, float, float, float]] = []
    for raw_x, raw_y, raw_radius in circles[0]:
        x = float(raw_x)
        y = float(raw_y)
        radius = float(raw_radius)
        radius_ratio = radius / minimum_dimension
        center_distance = _normalized_center_distance(
            x, y, width=detect_w, height=detect_h
        )
        outside_ratio = _circle_outside_ratio(
            x, y, radius, width=detect_w, height=detect_h
        )
        score = 3.0 * radius_ratio - 1.5 * center_distance - 4.0 * outside_ratio
        candidates.append(
            (score, radius_ratio, center_distance, outside_ratio, x, y, radius)
        )

    candidates.sort(
        key=lambda item: (-item[0], -item[1], item[2], item[3], item[5], item[4])
    )
    score, radius_ratio, center_distance, outside_ratio, x, y, radius = candidates[0]

    inverse_scale = 1.0 / scale
    source_x = int(round(x * inverse_scale))
    source_y = int(round(y * inverse_scale))
    source_radius = max(1, int(round(radius * inverse_scale)))
    source_x = min(max(source_x, 0), source_w - 1)
    source_y = min(max(source_y, 0), source_h - 1)

    crop_x, crop_y, crop_w, crop_h = _padded_square(
        source_x,
        source_y,
        source_radius,
        source_width=source_w,
        source_height=source_h,
    )
    return CoinCircleLocalization(
        center_x=source_x,
        center_y=source_y,
        radius=source_radius,
        score=round(score, 6),
        radius_ratio=round(radius_ratio, 6),
        center_distance=round(center_distance, 6),
        outside_ratio=round(outside_ratio, 6),
        crop_x=crop_x,
        crop_y=crop_y,
        crop_width=crop_w,
        crop_height=crop_h,
        source_width=source_w,
        source_height=source_h,
    )


def crop_localized_coin(
    image: np.ndarray, localization: CoinCircleLocalization
) -> np.ndarray:
    """Return a copy of the localization's padded crop rectangle."""

    if not isinstance(image, np.ndarray) or image.ndim not in {2, 3}:
        raise ValueError("image must be a 2D or 3D numpy array.")
    height, width = image.shape[:2]
    if (width, height) != (localization.source_width, localization.source_height):
        raise ValueError("image dimensions do not match localization source.")
    x, y = localization.crop_x, localization.crop_y
    return image[
        y : y + localization.crop_height,
        x : x + localization.crop_width,
    ].copy()


def build_coin_evidence_views(
    image: np.ndarray, localization: CoinCircleLocalization
) -> tuple[tuple[str, np.ndarray], ...]:
    """Build deterministic full-face and rim-emphasis views for observation.

    The rim view masks the central disk rather than inventing pixels or rotating
    the coin. It is intended only to make peripheral inscriptions more salient.
    """

    full_face = crop_localized_coin(image, localization)
    crop_center_x = localization.center_x - localization.crop_x
    crop_center_y = localization.center_y - localization.crop_y
    rim = full_face.copy()
    inner_radius = max(1, int(round(localization.radius * 0.58)))
    cv2.circle(
        rim,
        (crop_center_x, crop_center_y),
        inner_radius,
        _neutral_fill_value(rim),
        thickness=-1,
    )
    return (("full_face", full_face), ("rim", rim))


def _neutral_fill_value(image: np.ndarray):
    """Return a deterministic neutral fill compatible with grayscale/BGR crops."""

    if image.ndim == 2:
        return int(np.median(image))
    median = np.median(image.reshape(-1, image.shape[2]), axis=0)
    return tuple(int(value) for value in median)


def _normalized_center_distance(
    x: float, y: float, *, width: int, height: int
) -> float:
    dx = x - width / 2.0
    dy = y - height / 2.0
    diagonal_half = math.hypot(width / 2.0, height / 2.0)
    return math.hypot(dx, dy) / diagonal_half if diagonal_half else 0.0


def _circle_outside_ratio(
    x: float, y: float, radius: float, *, width: int, height: int
) -> float:
    if radius <= 0:
        return 1.0
    overflow = (
        max(0.0, radius - x)
        + max(0.0, x + radius - width)
        + max(0.0, radius - y)
        + max(0.0, y + radius - height)
    )
    return min(1.0, overflow / (4.0 * radius))


def _padded_square(
    center_x: int,
    center_y: int,
    radius: int,
    *,
    source_width: int,
    source_height: int,
) -> tuple[int, int, int, int]:
    padded_radius = max(
        radius, int(math.ceil(radius * (1.0 + LOCALIZATION_PADDING_RATIO)))
    )
    left = max(0, center_x - padded_radius)
    top = max(0, center_y - padded_radius)
    right = min(source_width, center_x + padded_radius)
    bottom = min(source_height, center_y + padded_radius)
    return left, top, right - left, bottom - top
