#!/usr/bin/env python3
"""Pinned retrieval backend recovered from historical commit 36766dd.

Do not tune this module for the adversarial benchmark. The numerical constants and
scoring logic below intentionally reproduce the original reference-image retrieval
backend used by the 8-case pilot:

- 320x320 centre-square preprocessing
- four reference rotations
- ORB(nfeatures=1200, fastThreshold=8)
- BFMatcher(NORM_HAMMING, crossCheck=True)
- good-match distance <= 55
- ORB score = 0.70*density + 0.30*quality
- HSV H/S histogram 24x24 bins
- image score = 0.78*ORB + 0.22*histogram
- two-side score = geometric mean(obverse, reverse)

Source of truth: capture_import/reference_image_retrieval_benchmark_cli.py at
commit 36766dd (feat: add reference image retrieval benchmark).
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

BACKEND_SOURCE_COMMIT = "36766dd"
BACKEND_NAME = "opencv-orb-plus-hsv-histogram-rotation-invariant"


def _read(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"cannot decode image: {path}")
    return image


def _prepare(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    size = min(h, w)
    y = max(0, (h - size) // 2)
    x = max(0, (w - size) // 2)
    square = image[y:y + size, x:x + size]
    return cv2.resize(square, (320, 320), interpolation=cv2.INTER_AREA)


def _rotations(image: np.ndarray) -> tuple[np.ndarray, ...]:
    return (
        image,
        cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(image, cv2.ROTATE_180),
        cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE),
    )


def _orb_score(a: np.ndarray, b: np.ndarray) -> float:
    gray_a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=1200, fastThreshold=8)
    key_a, desc_a = orb.detectAndCompute(gray_a, None)
    key_b, desc_b = orb.detectAndCompute(gray_b, None)
    if desc_a is None or desc_b is None or not key_a or not key_b:
        return 0.0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(desc_a, desc_b)
    if not matches:
        return 0.0
    good = [m for m in matches if m.distance <= 55]
    denominator = max(1, min(len(key_a), len(key_b), 180))
    density = min(1.0, len(good) / denominator)
    if not good:
        return 0.0
    quality = 1.0 - min(1.0, float(np.mean([m.distance for m in good])) / 80.0)
    return 0.70 * density + 0.30 * quality


def _hist_score(a: np.ndarray, b: np.ndarray) -> float:
    hsv_a = cv2.cvtColor(a, cv2.COLOR_BGR2HSV)
    hsv_b = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
    hist_a = cv2.calcHist([hsv_a], [0, 1], None, [24, 24], [0, 180, 0, 256])
    hist_b = cv2.calcHist([hsv_b], [0, 1], None, [24, 24], [0, 180, 0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    correlation = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
    return max(0.0, min(1.0, (correlation + 1.0) / 2.0))


def image_similarity(query_path: Path, reference_path: Path) -> tuple[float, dict[str, float]]:
    query = _prepare(_read(query_path))
    reference = _prepare(_read(reference_path))
    best_orb = 0.0
    best_hist = 0.0
    best = 0.0
    for rotated in _rotations(reference):
        orb = _orb_score(query, rotated)
        hist = _hist_score(query, rotated)
        score = 0.78 * orb + 0.22 * hist
        if score > best:
            best, best_orb, best_hist = score, orb, hist
    return best, {"orb": best_orb, "histogram": best_hist}


def two_side_similarity(
    query_obverse: Path,
    query_reverse: Path,
    reference_obverse: Path,
    reference_reverse: Path,
) -> tuple[float, dict[str, object]]:
    obv, obv_detail = image_similarity(query_obverse, reference_obverse)
    rev, rev_detail = image_similarity(query_reverse, reference_reverse)
    combined = math.sqrt(max(0.0, obv) * max(0.0, rev))
    return combined, {
        "obverse": obv,
        "reverse": rev,
        "obverse_detail": obv_detail,
        "reverse_detail": rev_detail,
    }
