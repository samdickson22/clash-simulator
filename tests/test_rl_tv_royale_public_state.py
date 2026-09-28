from __future__ import annotations

import cv2
import numpy as np
import pytest

from clasher.rl.tv_royale_public_state import (
    associate_health_to_entities,
    associate_motion_between_frames,
    measure_health_bar,
    render_entity_health_observations,
    render_health_observations,
)
from clasher.rl.tv_royale_replay import TVRoyaleDetection


def _detection(
    class_name: str, belonging: int, width: int, height: int
) -> TVRoyaleDetection:
    return TVRoyaleDetection(
        class_name=class_name,
        belonging=belonging,
        confidence=0.9,
        x1=0,
        y1=0,
        x2=width,
        y2=height,
    )


@pytest.mark.parametrize(
    ("belonging", "color"),
    ((0, (235, 190, 70)), (1, (80, 70, 220))),
)
def test_unit_health_bar_recovers_fill_fraction(
    belonging: int, color: tuple[int, int, int]
) -> None:
    image = np.full((10, 44, 3), (65, 65, 80), dtype=np.uint8)
    image[1:9, 1:14] = color
    observation = measure_health_bar(image, _detection("bar", belonging, 44, 10))

    assert observation is not None
    assert observation.fill_fraction == pytest.approx(13 / 42, abs=0.04)
    assert observation.confidence >= 0.75


def test_tower_health_bar_ignores_level_icon_and_number_colored_pixels() -> None:
    image = np.full((20, 80, 3), (70, 65, 80), dtype=np.uint8)
    # The actual own-team bar fill is the upper strip after the fixed level icon.
    image[4:8, 21:42] = (235, 190, 70)
    # Digit-like cyan noise exists lower in the box and must not extend the fill.
    image[9:17, 25:70] = (235, 190, 70)
    observation = measure_health_bar(image, _detection("tower-bar", 0, 80, 20))

    assert observation is not None
    assert observation.fill_fraction == pytest.approx(21 / 58, abs=0.04)


def test_empty_detected_health_bar_is_zero_with_explicit_lower_confidence() -> None:
    image = np.full((10, 44, 3), (65, 65, 80), dtype=np.uint8)
    observation = measure_health_bar(image, _detection("bar", 1, 44, 10))

    assert observation is not None
    assert observation.fill_fraction == 0.0
    assert 0.5 <= observation.confidence < 0.9


def test_pale_enemy_fill_remains_visible_under_bright_effect_overlay() -> None:
    image = np.full((10, 44, 3), (73, 50, 93), dtype=np.uint8)
    image[1:9, 1:21] = (255, 225, 255)
    observation = measure_health_bar(image, _detection("bar", 1, 44, 10))

    assert observation is not None
    assert observation.fill_fraction == pytest.approx(20 / 42, abs=0.04)


def test_non_bar_detection_is_ignored_and_renderer_preserves_shape() -> None:
    image = np.zeros((16, 32, 3), dtype=np.uint8)
    troop = _detection("hog-rider", 0, 20, 12)
    assert measure_health_bar(image, troop) is None

    bar_image = np.full((10, 32, 3), (65, 65, 80), dtype=np.uint8)
    bar_image[1:9, 1:16] = (235, 190, 70)
    observation = measure_health_bar(bar_image, _detection("bar", 0, 32, 10))
    assert observation is not None
    rendered = render_health_observations(bar_image, [observation])
    assert rendered.shape == bar_image.shape
    assert not np.array_equal(rendered, bar_image)
    assert cv2.countNonZero(cv2.cvtColor(rendered, cv2.COLOR_BGR2GRAY)) > 0


def test_bar_is_associated_once_with_nearest_same_team_body() -> None:
    image = np.full((80, 100, 3), (65, 65, 80), dtype=np.uint8)
    image[10:18, 21:40] = (235, 190, 70)
    detections = [
        TVRoyaleDetection("bar", 0, 0.95, 20, 9, 60, 19),
        TVRoyaleDetection("hog-rider", 0, 0.9, 25, 22, 63, 68),
        TVRoyaleDetection("knight", 0, 0.99, 70, 20, 98, 60),
        TVRoyaleDetection("hog-rider", 1, 0.99, 23, 21, 62, 67),
    ]

    associated = associate_health_to_entities(image, detections)
    assert len(associated) == 1
    assert associated[0].entity_index == 1
    assert associated[0].entity_class == "hog-rider"
    assert associated[0].fill_fraction == pytest.approx(18 / 38, abs=0.05)
    assert associated[0].sensor_origin == "current-frame-body-bar"
    assert not associated[0].label_only
    assert not associated[0].uses_future_frames
    rendered = render_entity_health_observations(image, associated)
    assert rendered.shape == image.shape


def test_tower_bars_match_tower_kind_and_side() -> None:
    image = np.full((160, 120, 3), (65, 65, 80), dtype=np.uint8)
    image[8:14, 31:78] = (80, 70, 220)
    image[82:86, 21:62] = (235, 190, 70)
    detections = [
        TVRoyaleDetection("king-tower-bar", 1, 0.95, 20, 0, 100, 28),
        TVRoyaleDetection("king-tower", 1, 0.97, 25, 30, 95, 90),
        TVRoyaleDetection("tower-bar", 0, 0.94, 10, 75, 90, 95),
        TVRoyaleDetection("queen-tower", 0, 0.96, 15, 96, 85, 150),
    ]

    associated = associate_health_to_entities(image, detections)
    assert [row.entity_class for row in associated] == ["king-tower", "queen-tower"]
    assert all(row.confidence > 0.4 for row in associated)


def test_data_derived_body_filter_prevents_effect_from_stealing_bar() -> None:
    image = np.full((80, 100, 3), (65, 65, 80), dtype=np.uint8)
    image[10:18, 21:40] = (235, 190, 70)
    detections = [
        TVRoyaleDetection("bar", 0, 0.95, 20, 9, 60, 19),
        TVRoyaleDetection("fireball", 0, 0.99, 26, 20, 62, 55),
        TVRoyaleDetection("hog-rider", 0, 0.9, 25, 24, 63, 68),
    ]

    associated = associate_health_to_entities(
        image,
        detections,
        body_class_predicate=lambda name: name != "fireball",
    )
    assert [row.entity_class for row in associated] == ["hog-rider"]


def test_motion_association_is_causal_identity_and_team_matched() -> None:
    before = [
        TVRoyaleDetection("hog-rider", 0, 0.90, 20, 20, 40, 60),
        TVRoyaleDetection("clone", 0, 0.99, 50, 20, 80, 60),
        TVRoyaleDetection("hog-rider", 1, 0.99, 20, 20, 40, 60),
    ]
    after = [
        TVRoyaleDetection("hog-rider", 0, 0.95, 26, 28, 46, 68),
        TVRoyaleDetection("clone", 0, 0.99, 56, 28, 86, 68),
    ]

    motion = associate_motion_between_frames(
        before,
        after,
        body_identity=lambda name: "HogRider" if name == "hog-rider" else None,
    )

    assert len(motion) == 1
    assert motion[0].entity_index == 0
    assert motion[0].delta_x == 6.0
    assert motion[0].delta_y == 8.0
    assert 0.5 < motion[0].confidence < 0.9

    with pytest.raises(ValueError, match="frame_delta"):
        associate_motion_between_frames(
            before,
            after,
            body_identity=lambda name: name,
            frame_delta=0,
        )
