from unittest.mock import patch

import cv2
import numpy as np
import pytest

from capture_import.phone_photo_coin_localization import (
    LOCALIZATION_PADDING_RATIO,
    CoinCircleLocalization,
    _circle_outside_ratio,
    _normalized_center_distance,
    _padded_square,
    build_coin_evidence_views,
    crop_localized_coin,
    localize_coin_circle,
)


def _circle_result(x=300.0, y=300.0, radius=200.0):
    return np.array([[[x, y, radius]]], dtype=np.float32)


def test_center_distance_is_zero_at_image_center():
    assert _normalized_center_distance(300, 200, width=600, height=400) == 0.0


def test_outside_ratio_penalizes_edge_overflow():
    assert _circle_outside_ratio(300, 300, 100, width=600, height=600) == 0.0
    assert _circle_outside_ratio(25, 300, 100, width=600, height=600) > 0.0


def test_padded_square_adds_ten_percent_and_clamps():
    x, y, w, h = _padded_square(
        300, 300, 100, source_width=600, source_height=600
    )
    padded = int(np.ceil(100 * (1.0 + LOCALIZATION_PADDING_RATIO)))
    assert (x, y, w, h) == (
        300 - padded,
        300 - padded,
        2 * padded,
        2 * padded,
    )

    x, y, w, h = _padded_square(
        20, 20, 100, source_width=600, source_height=600
    )
    assert x == 0
    assert y == 0
    assert x + w <= 600
    assert y + h <= 600


def test_no_hough_candidate_returns_none():
    image = np.zeros((600, 600, 3), dtype=np.uint8)
    with patch(
        "capture_import.phone_photo_coin_localization.cv2.HoughCircles",
        return_value=None,
    ):
        assert localize_coin_circle(image) is None


def test_selected_circle_maps_to_original_resolution_and_crop():
    image = np.zeros((2400, 3200, 3), dtype=np.uint8)
    with patch(
        "capture_import.phone_photo_coin_localization.cv2.HoughCircles",
        return_value=_circle_result(450.0, 300.0, 250.0),
    ):
        result = localize_coin_circle(image)

    assert result is not None
    # 3200 -> 1200 detection scale = 0.375.
    assert result.center_x == 1200
    assert result.center_y == 800
    assert result.radius == 667
    assert result.source_width == 3200
    assert result.source_height == 2400
    assert result.crop_width > result.radius * 2
    assert result.crop_height > result.radius * 2


def test_ranking_prefers_large_centered_circle_over_small_offcenter_circle():
    image = np.zeros((600, 600, 3), dtype=np.uint8)
    circles = np.array(
        [[[100.0, 100.0, 90.0], [300.0, 300.0, 200.0]]], dtype=np.float32
    )
    with patch(
        "capture_import.phone_photo_coin_localization.cv2.HoughCircles",
        return_value=circles,
    ):
        result = localize_coin_circle(image)

    assert result is not None
    assert (result.center_x, result.center_y, result.radius) == (300, 300, 200)


def test_ranking_penalizes_circle_outside_frame():
    image = np.zeros((600, 600, 3), dtype=np.uint8)
    circles = np.array(
        [[[25.0, 300.0, 220.0], [300.0, 300.0, 190.0]]], dtype=np.float32
    )
    with patch(
        "capture_import.phone_photo_coin_localization.cv2.HoughCircles",
        return_value=circles,
    ):
        result = localize_coin_circle(image)

    assert result is not None
    assert (result.center_x, result.center_y) == (300, 300)


def test_repeated_selection_is_deterministic():
    image = np.zeros((600, 600, 3), dtype=np.uint8)
    circles = np.array(
        [[[300.0, 300.0, 200.0], [300.0, 300.0, 200.0]]], dtype=np.float32
    )
    with patch(
        "capture_import.phone_photo_coin_localization.cv2.HoughCircles",
        return_value=circles,
    ):
        first = localize_coin_circle(image)
        second = localize_coin_circle(image)
    assert first == second


def test_crop_localized_coin_returns_expected_copy():
    image = np.arange(100 * 100, dtype=np.uint16).reshape(100, 100)
    localization = CoinCircleLocalization(
        center_x=50,
        center_y=50,
        radius=20,
        score=1.0,
        radius_ratio=0.2,
        center_distance=0.0,
        outside_ratio=0.0,
        crop_x=25,
        crop_y=25,
        crop_width=50,
        crop_height=50,
        source_width=100,
        source_height=100,
    )
    cropped = crop_localized_coin(image, localization)
    assert cropped.shape == (50, 50)
    assert np.array_equal(cropped, image[25:75, 25:75])
    assert cropped is not image


def test_crop_rejects_mismatched_source_dimensions():
    image = np.zeros((90, 100, 3), dtype=np.uint8)
    localization = CoinCircleLocalization(
        center_x=50,
        center_y=50,
        radius=20,
        score=1.0,
        radius_ratio=0.2,
        center_distance=0.0,
        outside_ratio=0.0,
        crop_x=25,
        crop_y=25,
        crop_width=50,
        crop_height=50,
        source_width=100,
        source_height=100,
    )
    with pytest.raises(ValueError, match="dimensions"):
        crop_localized_coin(image, localization)


@pytest.mark.parametrize(
    "image",
    [
        "not-an-image",
        np.array([1, 2, 3]),
    ],
)
def test_localizer_rejects_invalid_image(image):
    with pytest.raises(ValueError, match="numpy array"):
        localize_coin_circle(image)


def test_real_synthetic_circle_is_localized_without_mocking_hough():
    image = np.full((600, 600, 3), 230, dtype=np.uint8)
    cv2.circle(image, (300, 300), 200, (40, 40, 40), 6)
    cv2.circle(image, (300, 300), 196, (120, 120, 120), -1)

    result = localize_coin_circle(image)

    assert result is not None
    assert abs(result.center_x - 300) < 20
    assert abs(result.center_y - 300) < 20
    assert abs(result.radius - 200) < 20
    assert result.crop_x >= 0
    assert result.crop_y >= 0
    assert result.crop_x + result.crop_width <= 600
    assert result.crop_y + result.crop_height <= 600


def test_evidence_views_are_deterministic_and_preserve_full_face():
    image = np.full((100, 100, 3), 200, dtype=np.uint8)
    cv2.circle(image, (50, 50), 20, (50, 60, 70), -1)
    localization = CoinCircleLocalization(
        center_x=50,
        center_y=50,
        radius=20,
        score=1.0,
        radius_ratio=0.2,
        center_distance=0.0,
        outside_ratio=0.0,
        crop_x=25,
        crop_y=25,
        crop_width=50,
        crop_height=50,
        source_width=100,
        source_height=100,
    )

    first = build_coin_evidence_views(image, localization)
    second = build_coin_evidence_views(image, localization)

    assert tuple(name for name, _ in first) == ("full_face", "rim")
    assert np.array_equal(first[0][1], crop_localized_coin(image, localization))
    assert np.array_equal(first[0][1], second[0][1])
    assert np.array_equal(first[1][1], second[1][1])


def test_rim_view_masks_center_but_preserves_periphery():
    image = np.arange(100 * 100, dtype=np.uint16).reshape(100, 100)
    localization = CoinCircleLocalization(
        center_x=50,
        center_y=50,
        radius=20,
        score=1.0,
        radius_ratio=0.2,
        center_distance=0.0,
        outside_ratio=0.0,
        crop_x=25,
        crop_y=25,
        crop_width=50,
        crop_height=50,
        source_width=100,
        source_height=100,
    )

    views = dict(build_coin_evidence_views(image, localization))
    full_face = views["full_face"]
    rim = views["rim"]

    assert rim.shape == full_face.shape
    assert rim[25, 25] != full_face[25, 25]
    assert rim[0, 0] == full_face[0, 0]
