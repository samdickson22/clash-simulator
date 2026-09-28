from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

import cv2
import numpy as np

if TYPE_CHECKING:
    from .tv_royale_replay import TVRoyaleDetection

HEALTH_BAR_CLASSES = frozenset({"bar", "tower-bar", "king-tower-bar"})


@dataclass(frozen=True)
class TVRoyaleHealthObservation:
    """A visible health-bar measurement, not an inferred simulator truth."""

    bar_class: str
    belonging: int
    fill_fraction: float
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class TVRoyaleEntityHealthObservation:
    """A health measurement associated with one visible body detection."""

    entity_index: int
    entity_class: str
    belonging: int
    center_x: float
    center_y: float
    fill_fraction: float
    confidence: float
    bar: TVRoyaleHealthObservation
    sensor_origin: Literal["current-frame-body-bar"] = "current-frame-body-bar"
    label_only: bool = False
    uses_future_frames: bool = False


@dataclass(frozen=True)
class TVRoyaleEntityMotionObservation:
    """A causal body-centre displacement between two observed frames."""

    entity_index: int
    entity_class: str
    belonging: int
    delta_x: float
    delta_y: float
    confidence: float


_NON_BODY_CLASSES = frozenset(
    {
        "bar",
        "barlevel",
        "clock",
        "daggerduchesstowerbar",
        "elixir",
        "emote",
        "kingtowerbar",
        "paddingbelong",
        "selected",
        "text",
        "towerbar",
    }
)
_KING_TOWER_CLASSES = frozenset({"kingtower"})
_PRINCESS_TOWER_CLASSES = frozenset(
    {"queentower", "cannoneertower", "daggerduchesstower"}
)


def _normalized_name(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _clip_box(
    image: np.ndarray, detection: TVRoyaleDetection
) -> tuple[int, int, int, int] | None:
    height, width = image.shape[:2]
    x1 = max(0, min(width, round(detection.x1)))
    y1 = max(0, min(height, round(detection.y1)))
    x2 = max(0, min(width, round(detection.x2)))
    y2 = max(0, min(height, round(detection.y2)))
    if x2 - x1 < 4 or y2 - y1 < 3:
        return None
    return x1, y1, x2, y2


def _team_fill_mask(patch_bgr: np.ndarray, belonging: int) -> np.ndarray:
    """Return bright team-color pixels, excluding the dark empty-bar color."""

    blue, green, red = np.moveaxis(patch_bgr.astype(np.int16), -1, 0)
    if belonging == 0:
        return cast(
            np.ndarray,
            (blue >= 145)
            & (green >= 125)
            & (blue - red >= 30)
            & (green - red >= 20),
        )
    if belonging == 1:
        return cast(
            np.ndarray,
            ((red >= 135) & (red - green >= 35) & (red >= blue))
            | ((red >= 180) & (green >= 100) & (red - green >= 15) & (red >= blue - 10)),
        )
    raise ValueError(f"health-bar belonging must be 0 or 1, got {belonging}")


def _measurement_strip(
    patch: np.ndarray, *, bar_class: str, belonging: int
) -> np.ndarray:
    """Select pixels that carry fill while avoiding level icons and HP digits."""

    height, width = patch.shape[:2]
    if bar_class == "bar":
        return patch[1 : max(2, height - 1), 1 : max(2, width - 1)]

    if bar_class == "tower-bar":
        x_start = round(width * 0.26)
        if belonging == 0:
            y_start, y_end = round(height * 0.22), round(height * 0.38)
        else:
            # Enemy Princess Tower numbers are above the colored strip; own
            # numbers are below it in the canonical TV Royale orientation.
            y_start, y_end = round(height * 0.52), round(height * 0.72)
    elif bar_class == "king-tower-bar":
        x_start = round(width * 0.26)
        y_start, y_end = round(height * 0.46), round(height * 0.68)
    else:
        raise ValueError(f"unsupported health bar class: {bar_class}")

    x_start = min(max(0, x_start), width - 1)
    y_start = min(max(0, y_start), height - 1)
    y_end = min(max(y_start + 1, y_end), height)
    return patch[y_start:y_end, x_start : max(x_start + 1, width - 1)]


def _prefix_fill_fraction(column_scores: np.ndarray) -> tuple[float, float]:
    """Measure the left-to-right fill and return (fraction, profile quality)."""

    if column_scores.size == 0:
        return 0.0, 0.0
    active = column_scores >= 0.45
    leading_window = min(4, active.size)
    leading = np.flatnonzero(active[:leading_window])
    if leading.size == 0:
        # A detected bar with no bright team-color interior is a useful zero-HP
        # observation, but less certain than a positive fill measurement.
        return 0.0, 0.65

    start = int(leading[0])
    last_active = start
    gap = 0
    for index in range(start, active.size):
        if active[index]:
            last_active = index
            gap = 0
        else:
            gap += 1
            if gap > 1:
                break

    fill_end = last_active + 1
    fraction = float(np.clip(fill_end / max(1, active.size), 0.0, 1.0))
    trailing_active = int(np.count_nonzero(active[fill_end:]))
    trailing_width = max(1, active.size - fill_end)
    continuity = 1.0 - min(1.0, trailing_active / trailing_width)
    color_strength = min(1.0, float(np.max(column_scores)) / 0.75)
    leading_quality = 1.0 - 0.12 * start
    quality = float(np.clip(continuity * color_strength * leading_quality, 0.0, 1.0))
    return fraction, quality


def measure_health_bar(
    image_bgr: np.ndarray, detection: TVRoyaleDetection
) -> TVRoyaleHealthObservation | None:
    """Measure a detector-localized visible health bar.

    The result is deliberately a noisy public observation. It must not be
    treated as an exact simulator HP value, and low-confidence rows should be
    masked rather than silently filled with a fabricated default.
    """

    if detection.class_name not in HEALTH_BAR_CLASSES:
        return None
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ValueError("health-bar input must be a BGR image with three channels")
    clipped = _clip_box(image_bgr, detection)
    if clipped is None:
        return None
    x1, y1, x2, y2 = clipped
    patch = image_bgr[y1:y2, x1:x2]
    strip = _measurement_strip(
        patch,
        bar_class=detection.class_name,
        belonging=detection.belonging,
    )
    if strip.size == 0:
        return None
    scores = _team_fill_mask(strip, detection.belonging).mean(axis=0)
    fraction, profile_quality = _prefix_fill_fraction(scores)
    confidence = float(
        np.clip(float(detection.confidence) * profile_quality, 0.0, 1.0)
    )
    return TVRoyaleHealthObservation(
        bar_class=detection.class_name,
        belonging=detection.belonging,
        fill_fraction=fraction,
        confidence=confidence,
        x1=float(x1),
        y1=float(y1),
        x2=float(x2),
        y2=float(y2),
    )


def measure_health_bars(
    image_bgr: np.ndarray, detections: Iterable[TVRoyaleDetection]
) -> list[TVRoyaleHealthObservation]:
    observations: list[TVRoyaleHealthObservation] = []
    for detection in detections:
        observation = measure_health_bar(image_bgr, detection)
        if observation is not None:
            observations.append(observation)
    return observations


def associate_health_to_entities(
    image_bgr: np.ndarray,
    detections: list[TVRoyaleDetection],
    *,
    body_class_predicate: Callable[[str], bool] | None = None,
) -> list[TVRoyaleEntityHealthObservation]:
    """Associate visible bars to bodies with a one-to-one geometry match."""

    bars: list[tuple[int, TVRoyaleHealthObservation]] = []
    bodies: list[tuple[int, TVRoyaleDetection, str]] = []
    for index, detection in enumerate(detections):
        measured = measure_health_bar(image_bgr, detection)
        if measured is not None:
            bars.append((index, measured))
            continue
        normalized = _normalized_name(detection.class_name)
        eligible_class = (
            body_class_predicate is None
            or body_class_predicate(detection.class_name)
        )
        if (
            normalized not in _NON_BODY_CLASSES
            and detection.belonging in {0, 1}
            and eligible_class
        ):
            bodies.append((index, detection, normalized))

    candidate_pairs: list[
        tuple[
            float,
            float,
            int,
            TVRoyaleDetection,
            int,
            TVRoyaleHealthObservation,
        ]
    ] = []
    for entity_index, body, normalized in bodies:
        body_center_x = (body.x1 + body.x2) * 0.5
        if normalized in _KING_TOWER_CLASSES:
            wanted_bar = "king-tower-bar"
            body_anchor_y = (body.y1 + body.y2) * 0.5
            maximum_distance = 130.0
        elif normalized in _PRINCESS_TOWER_CLASSES:
            wanted_bar = "tower-bar"
            body_anchor_y = (body.y1 + body.y2) * 0.5
            maximum_distance = 100.0
        else:
            wanted_bar = "bar"
            body_anchor_y = body.y1
            maximum_distance = 45.0
        for bar_index, bar in bars:
            if bar.bar_class != wanted_bar or bar.belonging != body.belonging:
                continue
            bar_center_x = (bar.x1 + bar.x2) * 0.5
            bar_anchor_y = (bar.y1 + bar.y2) * 0.5 if wanted_bar != "bar" else bar.y2
            distance = math.hypot(
                body_center_x - bar_center_x,
                body_anchor_y - bar_anchor_y,
            )
            if distance > maximum_distance:
                continue
            candidate_pairs.append(
                (
                    distance,
                    maximum_distance,
                    entity_index,
                    body,
                    bar_index,
                    bar,
                )
            )

    used_entities: set[int] = set()
    used_bars: set[int] = set()
    result: list[TVRoyaleEntityHealthObservation] = []
    for distance, maximum_distance, entity_index, body, bar_index, bar in sorted(
        candidate_pairs, key=lambda row: row[0]
    ):
        if entity_index in used_entities or bar_index in used_bars:
            continue
        used_entities.add(entity_index)
        used_bars.add(bar_index)
        geometry_confidence = max(0.0, 1.0 - 0.5 * distance / maximum_distance)
        confidence = float(
            np.clip(
                bar.confidence * float(body.confidence) * geometry_confidence,
                0.0,
                1.0,
            )
        )
        result.append(
            TVRoyaleEntityHealthObservation(
                entity_index=entity_index,
                entity_class=body.class_name,
                belonging=body.belonging,
                center_x=(body.x1 + body.x2) * 0.5,
                center_y=(body.y1 + body.y2) * 0.5,
                fill_fraction=bar.fill_fraction,
                confidence=confidence,
                bar=bar,
            )
        )
    result.sort(key=lambda row: row.entity_index)
    return result


def associate_motion_between_frames(
    before: list[TVRoyaleDetection],
    after: list[TVRoyaleDetection],
    *,
    body_identity: Callable[[str], str | None],
    frame_delta: int = 1,
    maximum_distance_per_frame: float = 24.0,
) -> list[TVRoyaleEntityMotionObservation]:
    """Match enabled public bodies causally by identity, team, and proximity.

    This intentionally accepts only short frame gaps. Long-gap nearest-neighbour
    matching through deaths, spawns, and crowds would fabricate trajectories.
    """

    if frame_delta <= 0:
        raise ValueError("motion frame_delta must be positive")
    if maximum_distance_per_frame <= 0.0:
        raise ValueError("motion maximum distance must be positive")
    maximum_distance = maximum_distance_per_frame * frame_delta

    previous: list[tuple[int, TVRoyaleDetection, str, float, float]] = []
    current: list[tuple[int, TVRoyaleDetection, str, float, float]] = []
    for collection, detections in ((previous, before), (current, after)):
        for index, detection in enumerate(detections):
            identity = body_identity(detection.class_name)
            if identity is None or detection.belonging not in {0, 1}:
                continue
            collection.append(
                (
                    index,
                    detection,
                    identity,
                    (detection.x1 + detection.x2) * 0.5,
                    (detection.y1 + detection.y2) * 0.5,
                )
            )

    candidates: list[
        tuple[
            float,
            int,
            int,
            TVRoyaleDetection,
            TVRoyaleDetection,
            float,
            float,
            float,
            float,
        ]
    ] = []
    for previous_index, old, old_identity, old_x, old_y in previous:
        for current_index, new, new_identity, new_x, new_y in current:
            if old_identity != new_identity or old.belonging != new.belonging:
                continue
            distance = math.hypot(new_x - old_x, new_y - old_y)
            if distance <= maximum_distance:
                candidates.append(
                    (
                        distance,
                        previous_index,
                        current_index,
                        old,
                        new,
                        old_x,
                        old_y,
                        new_x,
                        new_y,
                    )
                )

    used_previous: set[int] = set()
    used_current: set[int] = set()
    observations: list[TVRoyaleEntityMotionObservation] = []
    for candidate in sorted(candidates, key=lambda item: (item[0], item[2], item[1])):
        (
            distance,
            previous_index,
            current_index,
            old,
            new,
            old_x,
            old_y,
            new_x,
            new_y,
        ) = candidate
        if previous_index in used_previous or current_index in used_current:
            continue
        used_previous.add(previous_index)
        used_current.add(current_index)
        distance_quality = max(0.0, 1.0 - distance / maximum_distance)
        confidence = float(
            np.clip(
                min(old.confidence, new.confidence) * distance_quality,
                0.0,
                1.0,
            )
        )
        observations.append(
            TVRoyaleEntityMotionObservation(
                entity_index=current_index,
                entity_class=new.class_name,
                belonging=new.belonging,
                delta_x=new_x - old_x,
                delta_y=new_y - old_y,
                confidence=confidence,
            )
        )
    return sorted(observations, key=lambda observation: observation.entity_index)


def render_health_observations(
    image_bgr: np.ndarray,
    observations: Iterable[TVRoyaleHealthObservation],
) -> np.ndarray:
    """Render auditable bar boxes and measured fractions on an arena crop."""

    output = image_bgr.copy()
    for observation in observations:
        color = (255, 210, 70) if observation.belonging == 0 else (80, 80, 255)
        x1, y1, x2, y2 = (
            round(observation.x1),
            round(observation.y1),
            round(observation.x2),
            round(observation.y2),
        )
        cv2.rectangle(output, (x1, y1), (x2, y2), color, 1)
        label = (
            f"{observation.bar_class} hp~{observation.fill_fraction:.2f} "
            f"c={observation.confidence:.2f}"
        )
        cv2.putText(
            output,
            label,
            (max(0, x1), max(12, y1 - 3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.34,
            color,
            1,
            cv2.LINE_AA,
        )
    return cast(np.ndarray, output)


def render_entity_health_observations(
    image_bgr: np.ndarray,
    observations: Iterable[TVRoyaleEntityHealthObservation],
) -> np.ndarray:
    """Render body centers, bar associations, and HP fractions for visual QA."""

    output = image_bgr.copy()
    for observation in observations:
        color = (255, 210, 70) if observation.belonging == 0 else (80, 80, 255)
        bar_center = (
            round((observation.bar.x1 + observation.bar.x2) * 0.5),
            round((observation.bar.y1 + observation.bar.y2) * 0.5),
        )
        body_center = (round(observation.center_x), round(observation.center_y))
        cv2.rectangle(
            output,
            (round(observation.bar.x1), round(observation.bar.y1)),
            (round(observation.bar.x2), round(observation.bar.y2)),
            color,
            1,
        )
        cv2.line(output, bar_center, body_center, color, 1, cv2.LINE_AA)
        cv2.circle(output, body_center, 3, color, -1, cv2.LINE_AA)
        label = (
            f"{observation.entity_class} hp~{observation.fill_fraction:.2f} "
            f"c={observation.confidence:.2f}"
        )
        cv2.putText(
            output,
            label,
            (max(0, round(observation.bar.x1)), max(12, round(observation.bar.y1) - 3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.34,
            color,
            1,
            cv2.LINE_AA,
        )
    return cast(np.ndarray, output)
