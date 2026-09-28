from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

from .public_observation import (
    ConfidenceAwareActorObservation,
    validate_real_play_feature_contract,
)
from .structured_obs import ActorObservation


class PublicVisualDetection(Protocol):
    """Structural type for one detector result from the current camera frame."""

    class_name: str
    belonging: int
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class VisibleBattleClock:
    """One OCR reading of the game timer that is visibly rendered this frame."""

    seconds_remaining: int
    overtime: bool
    confidence: float
    raw_text: str

    def validate(self) -> None:
        if self.seconds_remaining < 0 or self.seconds_remaining > 300:
            raise ValueError("visible clock seconds must be in [0, 300]")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("visible clock confidence must be in [0, 1]")


@dataclass(frozen=True)
class CurrentFrameDeploymentCue:
    """A visible in-arena deployment marker, not a gameplay hitbox.

    The normalized point is the marker centre. ``visual_extent_*`` describes
    detector evidence only and must never be interpreted as a collision or
    placement footprint. A marker may remain visible for multiple frames;
    deduplication belongs to model-owned recurrent state.
    """

    player_id: int
    x: float
    y: float
    confidence: float
    support: int
    visual_extent_x: float
    visual_extent_y: float
    evidence: Literal["deployment-marker"] = "deployment-marker"

    def validate(self) -> None:
        if self.player_id not in {0, 1}:
            raise ValueError("deployment cue player_id must be zero or one")
        for name in ("x", "y", "confidence", "visual_extent_x", "visual_extent_y"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"deployment cue {name} must be in [0, 1]")
        if self.support < 1:
            raise ValueError("deployment cue support must be positive")


@dataclass(frozen=True)
class CurrentFrameCardPlayCue:
    """A fail-closed card identity associated with a current visual marker."""

    player_id: int
    card_token_id: int
    x: float
    y: float
    identity_confidence: float
    placement_confidence: float
    event_confidence: float
    marker_support: int
    evidence: Literal["marker-plus-colocated-identity"] = (
        "marker-plus-colocated-identity"
    )

    def validate(self) -> None:
        if self.player_id not in {0, 1}:
            raise ValueError("card-play cue player_id must be zero or one")
        if self.card_token_id <= 0:
            raise ValueError("card-play cue requires a known positive token id")
        for name in (
            "x",
            "y",
            "identity_confidence",
            "placement_confidence",
            "event_confidence",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"card-play cue {name} must be in [0, 1]")
        if self.marker_support < 1:
            raise ValueError("card-play cue marker support must be positive")


@dataclass(frozen=True)
class CurrentFrameCombatCue:
    """A visible combat/effect cue without an invented remaining timer."""

    entity_index: int
    kind: Literal[
        "attack",
        "charge",
        "damage",
        "freeze",
        "haste",
        "heal",
        "shield",
        "slow",
        "stealth",
        "stun",
    ]
    confidence: float

    def validate(self) -> None:
        if self.entity_index < 0:
            raise ValueError("combat cue entity index must be non-negative")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("combat cue confidence must be in [0, 1]")


@dataclass(frozen=True)
class CurrentFramePublicSignals:
    """Strict inference payload containing only evidence from the current frame.

    This object deliberately has no previous-frame fields or match history. The
    policy may recurrently remember these signals, but the camera adapter may
    not precompute card cycle, opponent elixir, status durations, or attack
    clocks outside the model.
    """

    observation: ConfidenceAwareActorObservation
    clock: VisibleBattleClock | None = None
    deployment_cues: tuple[CurrentFrameDeploymentCue, ...] = ()
    card_play_cues: tuple[CurrentFrameCardPlayCue, ...] = ()
    combat_cues: tuple[CurrentFrameCombatCue, ...] = ()

    def validate(self) -> None:
        validate_real_play_feature_contract(self.observation)
        actor = self.observation.observation
        if (
            np.any(actor.opponent_history_ids)
            or np.any(actor.opponent_history_ages)
            or np.any(actor.opponent_seen_card_ids)
            or np.any(self.observation.opponent_history_confidence)
            or np.any(self.observation.opponent_seen_card_confidence)
        ):
            raise ValueError(
                "current-frame signals cannot contain externally accumulated "
                "opponent history"
            )
        if np.any(self.observation.entity_feature_confidence[..., 27:29] > 0.0):
            raise ValueError(
                "current-frame signals cannot contain externally tracked motion"
            )
        if self.clock is not None:
            self.clock.validate()
        for deployment_cue in self.deployment_cues:
            deployment_cue.validate()
        for card_play_cue in self.card_play_cues:
            card_play_cue.validate()
        for combat_cue in self.combat_cues:
            combat_cue.validate()


_CLOCK_PATTERN = re.compile(
    r"^(?:(?P<overtime>OT|OVERTIME)\s*)?(?P<minutes>\d{1,2}):(?P<seconds>\d{2})$",
    re.IGNORECASE,
)


def parse_visible_battle_clock(
    text: str,
    *,
    confidence: float,
) -> VisibleBattleClock | None:
    """Parse OCR text without guessing malformed or low-confidence readings."""

    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("visible clock confidence must be in [0, 1]")
    normalized = " ".join(text.strip().upper().split())
    match = _CLOCK_PATTERN.fullmatch(normalized)
    if match is None:
        return None
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    if seconds >= 60:
        return None
    total = minutes * 60 + seconds
    if total > 300:
        return None
    result = VisibleBattleClock(
        seconds_remaining=total,
        overtime=match.group("overtime") is not None,
        confidence=float(confidence),
        raw_text=text,
    )
    result.validate()
    return result


def current_frame_deployment_cues(
    detections: Sequence[PublicVisualDetection],
    *,
    image_width: int,
    image_height: int,
    minimum_confidence: float = 0.75,
    cluster_distance_pixels: float = 18.0,
) -> tuple[CurrentFrameDeploymentCue, ...]:
    """Cluster current deployment-marker boxes without temporal novelty claims."""

    if image_width <= 0 or image_height <= 0:
        raise ValueError("deployment cue image dimensions must be positive")
    if not 0.0 <= minimum_confidence <= 1.0:
        raise ValueError("deployment cue minimum confidence must be in [0, 1]")
    if cluster_distance_pixels < 0.0:
        raise ValueError("deployment cue cluster distance must be non-negative")

    points: list[tuple[int, float, float, float, float, float]] = []
    for detection in detections:
        normalized_name = "".join(
            character for character in detection.class_name.lower() if character.isalnum()
        )
        if (
            normalized_name != "clock"
            or detection.belonging not in {0, 1}
            or detection.confidence < minimum_confidence
        ):
            continue
        points.append(
            (
                int(detection.belonging),
                (float(detection.x1) + float(detection.x2)) * 0.5,
                (float(detection.y1) + float(detection.y2)) * 0.5,
                float(detection.confidence),
                abs(float(detection.x2) - float(detection.x1)),
                abs(float(detection.y2) - float(detection.y1)),
            )
        )

    clusters: list[list[tuple[int, float, float, float, float, float]]] = []
    for point in sorted(points, key=lambda item: (item[0], -item[3], item[2], item[1])):
        for cluster in clusters:
            if cluster[0][0] != point[0]:
                continue
            weight = sum(item[3] for item in cluster)
            center_x = sum(item[1] * item[3] for item in cluster) / weight
            center_y = sum(item[2] * item[3] for item in cluster) / weight
            if math.hypot(point[1] - center_x, point[2] - center_y) <= cluster_distance_pixels:
                cluster.append(point)
                break
        else:
            clusters.append([point])

    result: list[CurrentFrameDeploymentCue] = []
    for cluster in clusters:
        weight = sum(item[3] for item in cluster)
        cue = CurrentFrameDeploymentCue(
            player_id=cluster[0][0],
            x=float(
                np.clip(
                    sum(item[1] * item[3] for item in cluster) / weight / image_width,
                    0.0,
                    1.0,
                )
            ),
            y=float(
                np.clip(
                    sum(item[2] * item[3] for item in cluster) / weight / image_height,
                    0.0,
                    1.0,
                )
            ),
            confidence=max(item[3] for item in cluster),
            support=len(cluster),
            visual_extent_x=float(
                np.clip(max(item[4] for item in cluster) / image_width, 0.0, 1.0)
            ),
            visual_extent_y=float(
                np.clip(max(item[5] for item in cluster) / image_height, 0.0, 1.0)
            ),
        )
        cue.validate()
        result.append(cue)
    return tuple(sorted(result, key=lambda cue: (cue.player_id, cue.y, cue.x)))


def current_frame_card_play_cues(
    detections: Sequence[PublicVisualDetection],
    deployment_cues: Sequence[CurrentFrameDeploymentCue],
    *,
    image_width: int,
    image_height: int,
    card_token: Callable[[str], int | None],
    maximum_distance_fraction: float = 0.12,
) -> tuple[CurrentFrameCardPlayCue, ...]:
    """Associate a marker with one unambiguous co-located visual identity.

    This is intentionally conservative. It emits no identity when multiple
    distinct card tokens are near a marker, and it does not turn spawned bodies
    into match history. Repeated cues remain repeated current-frame evidence for
    the model-owned state to deduplicate.
    """

    if image_width <= 0 or image_height <= 0:
        raise ValueError("card-play cue image dimensions must be positive")
    if maximum_distance_fraction <= 0.0:
        raise ValueError("card-play cue maximum distance must be positive")
    diagonal = math.hypot(image_width, image_height)
    candidates: list[tuple[int, int, float, float, float]] = []
    for detection in detections:
        if detection.belonging not in {0, 1} or detection.confidence <= 0.0:
            continue
        token = card_token(detection.class_name)
        if token is None or token <= 0:
            continue
        candidates.append(
            (
                int(detection.belonging),
                int(token),
                (float(detection.x1) + float(detection.x2)) * 0.5 / image_width,
                (float(detection.y1) + float(detection.y2)) * 0.5 / image_height,
                float(np.clip(detection.confidence, 0.0, 1.0)),
            )
        )

    output: list[CurrentFrameCardPlayCue] = []
    for marker in deployment_cues:
        marker.validate()
        nearby = [
            candidate
            for candidate in candidates
            if candidate[0] == marker.player_id
            and math.hypot(
                (candidate[2] - marker.x) * image_width,
                (candidate[3] - marker.y) * image_height,
            )
            / diagonal
            <= maximum_distance_fraction
        ]
        tokens = {candidate[1] for candidate in nearby}
        if len(tokens) != 1:
            continue
        token = next(iter(tokens))
        identity_confidence = max(
            candidate[4] for candidate in nearby if candidate[1] == token
        )
        cue = CurrentFrameCardPlayCue(
            player_id=marker.player_id,
            card_token_id=token,
            x=marker.x,
            y=marker.y,
            identity_confidence=identity_confidence,
            placement_confidence=marker.confidence,
            event_confidence=min(identity_confidence, marker.confidence),
            marker_support=marker.support,
        )
        cue.validate()
        output.append(cue)
    return tuple(output)


@dataclass
class _EntityTrack:
    track_id: int
    token_id: int
    row: np.ndarray
    confidence: np.ndarray
    identity_confidence: float
    last_frame: int
    last_observed_frame: int
    velocity: np.ndarray
    observations: int

    @property
    def team(self) -> int:
        return 0 if self.row[2] >= self.row[3] else 1


class CausalVisionTracker:
    """Causally stabilize frame-level public observations for real play.

    The tracker never receives simulator objects or future frames. It associates
    bodies by public identity, team, and predicted image-plane position; carries
    short HP/hand/tower gaps with decaying confidence; and derives motion from
    observed displacement. Unsupported status and combat-clock fields remain
    zero-confidence by construction.
    """

    _CARRIED_GLOBALS = (8, 9, 10, 11, 12, 13, 17)

    def __init__(
        self,
        *,
        max_gap_frames: int = 6,
        confidence_decay: float = 0.82,
        maximum_distance_per_frame: float = 0.025,
        maximum_distance: float = 0.20,
        minimum_motion: float = 1e-4,
        minimum_effect_observations: int = 2,
    ) -> None:
        if max_gap_frames < 0:
            raise ValueError("max_gap_frames must be non-negative")
        if not 0.0 < confidence_decay <= 1.0:
            raise ValueError("confidence_decay must be in (0, 1]")
        if maximum_distance_per_frame <= 0.0 or maximum_distance <= 0.0:
            raise ValueError("tracking distances must be positive")
        if minimum_motion < 0.0:
            raise ValueError("minimum_motion must be non-negative")
        if minimum_effect_observations < 1:
            raise ValueError("minimum_effect_observations must be positive")
        self.max_gap_frames = int(max_gap_frames)
        self.confidence_decay = float(confidence_decay)
        self.maximum_distance_per_frame = float(maximum_distance_per_frame)
        self.maximum_distance = float(maximum_distance)
        self.minimum_motion = float(minimum_motion)
        self.minimum_effect_observations = int(minimum_effect_observations)
        self._tracks: dict[int, _EntityTrack] = {}
        self._next_track_id = 1
        self._last_frame: int | None = None
        self._last_hand_ids: np.ndarray | None = None
        self._last_hand_confidence: np.ndarray | None = None
        self._last_global_values: np.ndarray | None = None
        self._last_global_confidence: np.ndarray | None = None

    def reset(self) -> None:
        self._tracks.clear()
        self._next_track_id = 1
        self._last_frame = None
        self._last_hand_ids = None
        self._last_hand_confidence = None
        self._last_global_values = None
        self._last_global_confidence = None

    @staticmethod
    def _team(row: np.ndarray) -> int:
        return 0 if row[2] >= row[3] else 1

    def _association_candidates(
        self,
        source: ConfidenceAwareActorObservation,
        current_indices: list[int],
        frame: int,
    ) -> list[tuple[float, int, int]]:
        candidates: list[tuple[float, int, int]] = []
        observation = source.observation
        for track_id, track in self._tracks.items():
            gap = frame - track.last_observed_frame
            if gap <= 0 or gap > self.max_gap_frames + 1:
                continue
            predicted = np.clip(track.row[0:2] + track.velocity * gap, 0.0, 1.0)
            limit = min(
                self.maximum_distance,
                self.maximum_distance_per_frame * max(1, gap),
            )
            for index in current_indices:
                if int(observation.entity_ids[index]) != track.token_id:
                    continue
                if self._team(observation.entity_features[index]) != track.team:
                    continue
                distance = float(
                    np.linalg.norm(observation.entity_features[index, 0:2] - predicted)
                )
                if distance <= limit:
                    candidates.append((distance, track_id, index))
        return sorted(candidates, key=lambda item: (item[0], item[1], item[2]))

    def _update_tracks(
        self,
        source: ConfidenceAwareActorObservation,
        frame: int,
    ) -> list[tuple[bool, _EntityTrack]]:
        observation = source.observation
        current_indices = np.flatnonzero(observation.entity_mask).tolist()
        assigned_tracks: set[int] = set()
        assigned_indices: set[int] = set()
        output: list[tuple[bool, _EntityTrack]] = []

        for _, track_id, index in self._association_candidates(
            source, current_indices, frame
        ):
            if track_id in assigned_tracks or index in assigned_indices:
                continue
            assigned_tracks.add(track_id)
            assigned_indices.add(index)
            track = self._tracks[track_id]
            gap = max(1, frame - track.last_observed_frame)
            row = observation.entity_features[index].astype(np.float32, copy=True)
            confidence: np.ndarray = source.entity_feature_confidence[index].astype(
                np.float32, copy=True
            )
            displacement = row[0:2] - track.row[0:2]
            velocity = displacement / gap
            magnitude = float(np.linalg.norm(displacement))
            if magnitude >= self.minimum_motion:
                motion_confidence = min(
                    float(source.entity_id_confidence[index]),
                    float(np.min(source.entity_feature_confidence[index, 0:2])),
                    track.identity_confidence * self.confidence_decay**gap,
                )
                if motion_confidence > 0.0:
                    row[27:29] = displacement / magnitude
                    confidence[27:29] = motion_confidence
                else:
                    row[27:29] = 0.0
                    confidence[27:29] = 0.0
            elif track.confidence[27] > 0.0 or track.confidence[28] > 0.0:
                row[27:29] = track.row[27:29]
                confidence[27:29] = (
                    track.confidence[27:29] * self.confidence_decay**gap
                )

            # Health bars flicker under effects. Carry the last actual public
            # measurement briefly instead of substituting simulator HP.
            if confidence[9] <= 0.0 and track.confidence[9] > 0.0:
                row[9] = track.row[9]
                confidence[9] = track.confidence[9] * self.confidence_decay**gap

            track.row = row
            track.confidence = confidence
            track.identity_confidence = float(source.entity_id_confidence[index])
            track.last_frame = frame
            track.last_observed_frame = frame
            track.velocity = velocity
            track.observations += 1
            output.append((True, track))

        for index in current_indices:
            if index in assigned_indices:
                continue
            track = _EntityTrack(
                track_id=self._next_track_id,
                token_id=int(observation.entity_ids[index]),
                row=observation.entity_features[index].astype(np.float32, copy=True),
                confidence=source.entity_feature_confidence[index].astype(
                    np.float32, copy=True
                ),
                identity_confidence=float(source.entity_id_confidence[index]),
                last_frame=frame,
                last_observed_frame=frame,
                velocity=np.zeros((2,), dtype=np.float32),
                observations=1,
            )
            self._tracks[track.track_id] = track
            self._next_track_id += 1
            output.append((True, track))

        stale: list[int] = []
        for track_id, track in self._tracks.items():
            if track_id in assigned_tracks or track.last_observed_frame == frame:
                continue
            gap = frame - track.last_observed_frame
            if gap > self.max_gap_frames:
                stale.append(track_id)
                continue
            step = frame - track.last_frame
            if step > 0:
                track.row[0:2] = np.clip(
                    track.row[0:2] + track.velocity * step, 0.0, 1.0
                )
                decay = self.confidence_decay**step
                track.confidence *= decay
                track.identity_confidence *= decay
                track.last_frame = frame
            output.append((False, track))
        for track_id in stale:
            del self._tracks[track_id]
        return output

    def _pack_entities(
        self,
        source: ConfidenceAwareActorObservation,
        tracks: list[tuple[bool, _EntityTrack]],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        observation = source.observation
        max_entities = observation.entity_ids.shape[0]
        confirmed = [
            item
            for item in tracks
            if item[1].row[7] <= 0.5
            or item[1].observations >= self.minimum_effect_observations
        ]
        ranked = sorted(
            confirmed,
            key=lambda item: (
                not item[0],
                -item[1].identity_confidence,
                self._team(item[1].row),
                item[1].token_id,
                round(float(item[1].row[1]), 5),
                round(float(item[1].row[0]), 5),
                item[1].track_id,
            ),
        )[:max_entities]
        ids = np.zeros_like(observation.entity_ids)
        features = np.zeros_like(observation.entity_features, dtype=np.float32)
        mask = np.zeros_like(observation.entity_mask)
        id_confidence = np.zeros_like(source.entity_id_confidence, dtype=np.float32)
        feature_confidence = np.zeros_like(
            source.entity_feature_confidence, dtype=np.float32
        )
        for index, (_, track) in enumerate(ranked):
            ids[index] = track.token_id
            visible_row = track.row.copy()
            visible_row[track.confidence <= 0.0] = 0.0
            features[index] = visible_row
            mask[index] = True
            id_confidence[index] = track.identity_confidence
            feature_confidence[index] = track.confidence
        return ids, features, mask, id_confidence, feature_confidence

    def _carry_hud(
        self,
        source: ConfidenceAwareActorObservation,
        frame_delta: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        observation = source.observation
        hand_ids = observation.hand_ids.copy()
        hand_confidence: np.ndarray = source.hand_id_confidence.astype(
            np.float32, copy=True
        )
        globals_ = observation.global_features.astype(np.float32, copy=True)
        global_confidence: np.ndarray = source.global_feature_confidence.astype(
            np.float32, copy=True
        )
        decay = self.confidence_decay**max(1, frame_delta)

        if self._last_hand_ids is not None and self._last_hand_confidence is not None:
            missing = hand_confidence <= 0.0
            hand_ids[missing] = self._last_hand_ids[missing]
            hand_confidence[missing] = self._last_hand_confidence[missing] * decay
        if (
            self._last_global_values is not None
            and self._last_global_confidence is not None
        ):
            for index in self._CARRIED_GLOBALS:
                if global_confidence[index] > 0.0:
                    continue
                globals_[index] = self._last_global_values[index]
                global_confidence[index] = (
                    self._last_global_confidence[index] * decay
                )

        self._last_hand_ids = hand_ids.copy()
        self._last_hand_confidence = hand_confidence.copy()
        self._last_global_values = globals_.copy()
        self._last_global_confidence = global_confidence.copy()
        return hand_ids, hand_confidence, globals_, global_confidence

    def update(
        self,
        source: ConfidenceAwareActorObservation,
        *,
        frame: int,
    ) -> ConfidenceAwareActorObservation:
        """Advance with one chronological frame and return tracked public state."""

        validate_real_play_feature_contract(source)
        if frame < 0:
            raise ValueError("frame must be non-negative")
        if self._last_frame is not None and frame <= self._last_frame:
            raise ValueError("vision tracker frames must be strictly increasing")
        frame_delta = 1 if self._last_frame is None else frame - self._last_frame
        tracks = self._update_tracks(source, frame)
        (
            entity_ids,
            entity_features,
            entity_mask,
            entity_id_confidence,
            entity_feature_confidence,
        ) = self._pack_entities(source, tracks)
        hand_ids, hand_confidence, globals_, global_confidence = self._carry_hud(
            source, frame_delta
        )
        observation = source.observation
        tracked = ConfidenceAwareActorObservation(
            observation=ActorObservation(
                entity_ids=entity_ids,
                entity_features=entity_features,
                entity_mask=entity_mask,
                hand_ids=hand_ids,
                global_features=globals_,
                opponent_history_ids=observation.opponent_history_ids.copy(),
                opponent_history_ages=observation.opponent_history_ages.copy(),
                opponent_seen_card_ids=observation.opponent_seen_card_ids.copy(),
            ),
            entity_id_confidence=entity_id_confidence,
            entity_feature_confidence=entity_feature_confidence,
            hand_id_confidence=hand_confidence,
            global_feature_confidence=global_confidence,
            opponent_history_confidence=source.opponent_history_confidence.copy(),
            opponent_seen_card_confidence=source.opponent_seen_card_confidence.copy(),
            schema_version=source.schema_version,
        )
        validate_real_play_feature_contract(tracked)
        self._last_frame = frame
        return tracked


def normalized_motion_angle(x: float, y: float) -> float | None:
    """Small diagnostic helper used by visual audit renderers."""

    if not math.isfinite(x) or not math.isfinite(y):
        return None
    if math.hypot(x, y) <= 1e-8:
        return None
    return math.atan2(y, x)
