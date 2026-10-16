from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from clasher.arena import TileGrid

from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .public_observation import (
    ConfidenceAwareActorObservation,
    validate_real_play_feature_contract,
)
from .structured_obs import (
    ACTOR_GLOBAL_SIZE,
    ENTITY_FEATURE_SIZE,
    ActorObservation,
    StructuredObservationBuilder,
)
from .tv_royale_public_state import (
    associate_health_to_entities,
    associate_motion_between_frames,
)

IMAGE_WIDTH = 428
IMAGE_HEIGHT = 683
Y_OFFSET_TOP = 62
Y_OFFSET_BOTTOM = 7
SOURCE_ARENA_MIDDLE_Y = Y_OFFSET_TOP + (
    IMAGE_HEIGHT - Y_OFFSET_TOP - Y_OFFSET_BOTTOM
) / 2.0

_SOURCE_ALIASES = {
    "barbbarrel": "BarbarianBarrel",
    "ewiz": "ElectroWizard",
    "ghost": "RoyalGhost",
    "skelebarrel": "SkeletonBarrel",
    "snowball": "GiantSnowball",
    "teslacoil": "Tesla",
    "valk": "Valkyrie",
}
_UNIT_ALIASES = {
    "cannoneertower": "Tower",
    "daggerduchesstower": "Tower",
    "golembig": "Golem",
    "golemmid": "Golemite",
    "golemsmall": "Golemite",
    "hog": "RoyalHog",
    "kingtower": "KingTower",
    "queentower": "Tower",
    "skeletonevolution": "Skeleton",
    "skeletonsevolution": "Skeleton",
    "thelog": "LogProjectileRolling",
}
_SKIPPED_VISUAL_CLASSES = {
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


def _normalized_name(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


@dataclass(frozen=True)
class TVRoyaleDetection:
    class_name: str
    belonging: int
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class ConvertedTVRoyalePlacement:
    entity_ids: np.ndarray
    entity_features: np.ndarray
    entity_mask: np.ndarray
    hand_ids: np.ndarray
    global_features: np.ndarray
    action_mask: np.ndarray
    expert_action: int
    target_card: str
    target_slot: int


@dataclass(frozen=True)
class RecoveredTVRoyaleLocation:
    x: float
    y: float
    confidence: float
    support: int


def recover_deployment_clock(
    before: list[TVRoyaleDetection],
    after: list[TVRoyaleDetection],
    *,
    minimum_confidence: float = 0.75,
    existing_match_distance: float = 24.0,
    cluster_distance: float = 18.0,
) -> RecoveredTVRoyaleLocation | None:
    """Recover one lower-player deployment marker from a before/after pair.

    KataCR's ``clock`` class is the in-arena deployment countdown. The larger
    TV Royale shard stores one frame before and one after a labeled card play
    but omits coordinates. We accept only one newly appearing clock cluster;
    pre-existing markers and ambiguous multi-placement frames fail closed.
    """

    if not 0.0 < minimum_confidence <= 1.0:
        raise ValueError("minimum clock confidence must be in (0, 1]")
    if existing_match_distance < 0.0 or cluster_distance < 0.0:
        raise ValueError("clock distances must be non-negative")

    def clocks(detections: list[TVRoyaleDetection]) -> list[tuple[float, float, float]]:
        return [
            (
                (detection.x1 + detection.x2) * 0.5,
                (detection.y1 + detection.y2) * 0.5,
                detection.confidence,
            )
            for detection in detections
            if detection.belonging == 0
            and _normalized_name(detection.class_name) == "clock"
            and detection.confidence >= minimum_confidence
        ]

    before_clocks = clocks(before)
    novel = []
    for x, y, confidence in clocks(after):
        if any(
            math.hypot(x - old_x, y - old_y) <= existing_match_distance
            for old_x, old_y, _ in before_clocks
        ):
            continue
        novel.append((x, y, confidence))
    if not novel:
        return None

    clusters: list[list[tuple[float, float, float]]] = []
    for point in sorted(novel, key=lambda item: item[2], reverse=True):
        for cluster in clusters:
            weight = sum(item[2] for item in cluster)
            center_x = sum(item[0] * item[2] for item in cluster) / weight
            center_y = sum(item[1] * item[2] for item in cluster) / weight
            if math.hypot(point[0] - center_x, point[1] - center_y) <= cluster_distance:
                cluster.append(point)
                break
        else:
            clusters.append([point])
    if len(clusters) != 1:
        return None
    cluster = clusters[0]
    weight = sum(item[2] for item in cluster)
    return RecoveredTVRoyaleLocation(
        x=sum(item[0] * item[2] for item in cluster) / weight,
        y=sum(item[1] * item[2] for item in cluster) / weight,
        confidence=max(item[2] for item in cluster),
        support=len(cluster),
    )


def recover_deployment_cost_bubble(
    before: list[TVRoyaleDetection],
    after: list[TVRoyaleDetection],
    *,
    minimum_confidence: float = 0.75,
    existing_match_distance: float = 24.0,
    cluster_distance: float = 18.0,
    vertical_bias_cells: float = 0.2,
) -> RecoveredTVRoyaleLocation | None:
    """Recover one new lower-player floating deployment-cost bubble.

    KataCR's arena ``elixir`` class is the public number bubble rendered at a
    deployment, not the player's HUD counter.  Its bottom-centre is a better
    placement anchor than a troop sprite centre.  The small upward bias matches
    the public grid convention used by the upstream action builder.
    """

    if not 0.0 < minimum_confidence <= 1.0:
        raise ValueError("minimum cost-bubble confidence must be in (0, 1]")
    if existing_match_distance < 0.0 or cluster_distance < 0.0:
        raise ValueError("cost-bubble distances must be non-negative")
    if not 0.0 <= vertical_bias_cells <= 1.0:
        raise ValueError("cost-bubble vertical bias must be in [0, 1]")
    grid_height = IMAGE_HEIGHT - Y_OFFSET_TOP - Y_OFFSET_BOTTOM
    vertical_bias = vertical_bias_cells * grid_height / BOARD_HEIGHT

    def bubbles(
        detections: list[TVRoyaleDetection],
    ) -> list[tuple[float, float, float]]:
        return [
            (
                (detection.x1 + detection.x2) * 0.5,
                detection.y2 - vertical_bias,
                detection.confidence,
            )
            for detection in detections
            if detection.belonging == 0
            and _normalized_name(detection.class_name) == "elixir"
            and detection.confidence >= minimum_confidence
        ]

    before_bubbles = bubbles(before)
    novel = []
    for x, y, confidence in bubbles(after):
        if any(
            math.hypot(x - old_x, y - old_y) <= existing_match_distance
            for old_x, old_y, _ in before_bubbles
        ):
            continue
        novel.append((x, y, confidence))
    if not novel:
        return None

    clusters: list[list[tuple[float, float, float]]] = []
    for point in sorted(novel, key=lambda item: item[2], reverse=True):
        for cluster in clusters:
            weight = sum(item[2] for item in cluster)
            center_x = sum(item[0] * item[2] for item in cluster) / weight
            center_y = sum(item[1] * item[2] for item in cluster) / weight
            if math.hypot(point[0] - center_x, point[1] - center_y) <= cluster_distance:
                cluster.append(point)
                break
        else:
            clusters.append([point])
    if len(clusters) != 1:
        return None
    cluster = clusters[0]
    weight = sum(item[2] for item in cluster)
    return RecoveredTVRoyaleLocation(
        x=sum(item[0] * item[2] for item in cluster) / weight,
        y=sum(item[1] * item[2] for item in cluster) / weight,
        confidence=max(item[2] for item in cluster),
        support=len(cluster),
    )


class TVRoyalePlacementConverter:
    """Convert public TV Royale action frames into actor-only placement labels.

    The source records the lower player's public hand, elixir, chosen card,
    placement coordinate, and a screenshot at the action. Detector ownership 0
    is therefore the acting player. Clasher's canonical perspective is the
    source frame rotated by 180 degrees.

    These rows intentionally contain placements only. They are suitable for
    the PPO trainer's location-only rehearsal objective, which conditions on
    the expert card slot without modifying the policy's card/no-op choice.
    """

    def __init__(
        self,
        *,
        decks_path: str = "decks.json",
        max_entities: int = 128,
        token_names: tuple[str, ...] | None = None,
        source_frame_hz: float = 10.0,
    ) -> None:
        if source_frame_hz <= 0.0 or not math.isfinite(source_frame_hz):
            raise ValueError("source_frame_hz must be finite and positive")
        self.builder = StructuredObservationBuilder(
            decks_path=decks_path,
            max_entities=max_entities,
            token_names=token_names,
        )
        self.max_entities = max_entities
        self.source_frame_hz = float(source_frame_hz)
        self.noop_action = NUM_HAND_SLOTS * NUM_TILES
        self.action_count = self.noop_action + 2
        self._token_by_normalized = {
            _normalized_name(name): name
            for name in self.builder.token_names
            if not name.startswith("<")
        }

    def source_card_name(self, raw_name: Any) -> str | None:
        if not isinstance(raw_name, str) or not raw_name:
            return None
        name = raw_name
        if name.startswith("gray_"):
            name = name.removeprefix("gray_")
        if name.startswith("evo_"):
            name = name.removeprefix("evo_")
        normalized = _normalized_name(name)
        aliased = _SOURCE_ALIASES.get(normalized)
        if aliased is not None:
            return aliased if aliased in self.builder.token_names else None
        return self._token_by_normalized.get(normalized)

    def source_card_type(self, raw_name: Any) -> str | None:
        card_name = self.source_card_name(raw_name)
        if card_name is None:
            return None
        stats = self.builder.loader.get_card(card_name)
        return str(getattr(stats, "card_type", "") or "").lower()

    def source_card_cost(self, raw_name: Any) -> int | None:
        """Return authoritative public cost for one recognized source card."""

        card_name = self.source_card_name(raw_name)
        if card_name is None:
            return None
        stats = self.builder.loader.get_card(card_name)
        if stats is None:
            return None
        raw_cost = getattr(stats, "mana_cost", None)
        if isinstance(raw_cost, bool) or not isinstance(raw_cost, (int, float)):
            return None
        cost = int(raw_cost)
        if cost != raw_cost or not 0 < cost <= 10:
            return None
        return cost

    def is_location_training_candidate(
        self,
        *,
        raw_card: Any,
        raw_hand: Any,
        elixir: float,
        x: int,
        y: int,
    ) -> tuple[bool, str | None]:
        """Apply the upstream location model's conservative source filters."""

        values = list(raw_hand) if isinstance(raw_hand, (list, tuple)) else []
        if len(values) != NUM_HAND_SLOTS:
            return False, "incomplete_hand"
        if any(self.source_card_name(value) is None for value in values):
            return False, "outside_enabled_vocabulary"
        target = self.source_card_name(raw_card)
        if target is None:
            return False, "outside_enabled_vocabulary"
        if target not in [self.source_card_name(value) for value in values]:
            return False, "target_not_in_hand"
        if self.source_card_type(raw_card) == "spell":
            return False, "spell_location_label"
        if x < 0 or y < 0:
            return False, "missing_location"
        if y <= SOURCE_ARENA_MIDDLE_Y:
            return False, "non_lower_side"
        if not self.is_legal_source_placement(
            raw_card=raw_card,
            raw_hand=values,
            elixir=elixir,
            x=x,
            y=y,
        ):
            return False, "illegal_source_placement"
        return True, None

    def is_spell_location_training_candidate(
        self,
        *,
        raw_card: Any,
        raw_hand: Any,
        elixir: float,
        x: int,
        y: int,
    ) -> tuple[bool, str | None]:
        """Validate an independently recovered lower-player spell center."""

        values = list(raw_hand) if isinstance(raw_hand, (list, tuple)) else []
        if len(values) != NUM_HAND_SLOTS:
            return False, "incomplete_hand"
        if any(self.source_card_name(value) is None for value in values):
            return False, "outside_enabled_vocabulary"
        target = self.source_card_name(raw_card)
        if target is None:
            return False, "outside_enabled_vocabulary"
        if target not in [self.source_card_name(value) for value in values]:
            return False, "target_not_in_hand"
        if self.source_card_type(raw_card) != "spell":
            return False, "not_spell_location_label"
        if x < 0 or y < Y_OFFSET_TOP or x >= IMAGE_WIDTH or y >= IMAGE_HEIGHT - Y_OFFSET_BOTTOM:
            return False, "missing_location"
        if not self.is_legal_source_placement(
            raw_card=raw_card,
            raw_hand=values,
            elixir=elixir,
            x=x,
            y=y,
        ):
            return False, "illegal_source_placement"
        return True, None

    def is_noop_training_candidate(
        self,
        *,
        raw_card: Any,
        raw_hand: Any,
    ) -> tuple[bool, str | None]:
        """Accept only explicit no-play rows with a complete enabled hand."""

        if not isinstance(raw_card, str) or raw_card.strip().lower() != "none":
            return False, "not_explicit_noop"
        values = list(raw_hand) if isinstance(raw_hand, (list, tuple)) else []
        if len(values) != NUM_HAND_SLOTS:
            return False, "incomplete_hand"
        if any(self.source_card_name(value) is None for value in values):
            return False, "outside_enabled_vocabulary"
        return True, None

    def unit_token(self, raw_name: str) -> tuple[int, str] | None:
        normalized = _normalized_name(raw_name)
        if normalized in _SKIPPED_VISUAL_CLASSES or normalized.endswith("symbol"):
            return None
        if normalized.endswith("evolution"):
            normalized = normalized.removesuffix("evolution")
        aliased = _UNIT_ALIASES.get(normalized)
        token_name = (
            aliased
            if aliased in self.builder.token_names
            else self._token_by_normalized.get(normalized)
        )
        if token_name is None:
            return self.builder.token_id(None), self.builder.UNKNOWN_TOKEN
        return self.builder.token_id(token_name), token_name

    @staticmethod
    def source_pixel_to_canonical_tile(x: int, y: int) -> int:
        grid_height = IMAGE_HEIGHT - Y_OFFSET_TOP - Y_OFFSET_BOTTOM
        tile_x = int(x / (IMAGE_WIDTH / BOARD_WIDTH))
        tile_y = int((y - Y_OFFSET_TOP) / (grid_height / BOARD_HEIGHT))
        tile_x = max(0, min(tile_x, BOARD_WIDTH - 1))
        tile_y = max(0, min(tile_y, BOARD_HEIGHT - 1))
        canonical_x = BOARD_WIDTH - 1 - tile_x
        canonical_y = BOARD_HEIGHT - 1 - tile_y
        return canonical_y * BOARD_WIDTH + canonical_x

    @staticmethod
    def _entity_kind(token_name: str, builder: StructuredObservationBuilder) -> int:
        if token_name in {"Tower", "KingTower"}:
            return 1
        stats = builder.loader.get_card(token_name)
        kind = str(getattr(stats, "card_type", "") or "").lower()
        if kind == "building":
            return 1
        if kind == "spell":
            return 3
        return 0

    def is_supported_public_body_class(self, class_name: str) -> bool:
        """Return whether a detector class is an enabled troop/building body."""

        mapped = self.unit_token(class_name)
        if mapped is None:
            return False
        _, token_name = mapped
        return token_name != self.builder.UNKNOWN_TOKEN and self._entity_kind(
            token_name, self.builder
        ) in {0, 1}

    def is_supported_public_entity_class(self, class_name: str) -> bool:
        """Return whether a detector class has a causal actor representation."""

        mapped = self.unit_token(class_name)
        if mapped is None:
            return False
        _, token_name = mapped
        return token_name != self.builder.UNKNOWN_TOKEN and self._entity_kind(
            token_name, self.builder
        ) in {0, 1, 2, 3}

    def _entities(
        self, detections: list[TVRoyaleDetection]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        rows: list[tuple[tuple[Any, ...], int, np.ndarray]] = []
        grid_height = IMAGE_HEIGHT - Y_OFFSET_TOP - Y_OFFSET_BOTTOM
        for detection in detections:
            if detection.confidence <= 0.0:
                continue
            mapped = self.unit_token(detection.class_name)
            if mapped is None:
                continue
            token_id, token_name = mapped
            center_x = (detection.x1 + detection.x2) * 0.5
            center_y = (detection.y1 + detection.y2) * 0.5
            source_x = center_x / IMAGE_WIDTH * BOARD_WIDTH
            source_y = (center_y - Y_OFFSET_TOP) / grid_height * BOARD_HEIGHT
            canonical_x = float(np.clip(BOARD_WIDTH - source_x, 0.0, BOARD_WIDTH))
            canonical_y = float(np.clip(BOARD_HEIGHT - source_y, 0.0, BOARD_HEIGHT))
            row = np.zeros((ENTITY_FEATURE_SIZE,), dtype=np.float32)
            row[0] = canonical_x / BOARD_WIDTH
            row[1] = canonical_y / BOARD_HEIGHT
            own = int(detection.belonging) == 0
            row[2] = float(own)
            row[3] = float(not own)
            kind = self._entity_kind(token_name, self.builder)
            row[4 + kind] = 1.0
            # Health crops are unavailable in this source. Neutral full health
            # matches the established KataCR importer and avoids inventing HP.
            row[9] = 1.0
            static = self.builder.card_stat_features[token_id]
            stats = self.builder.loader.get_card(token_name)
            speed = float(getattr(stats, "speed", 0.0) or 0.0)
            row[23] = float(np.clip(math.log1p(abs(speed)) / math.log1p(1000.0), 0.0, 1.0))
            row[24] = static[7]
            row[25] = static[8]
            row[26] = static[12]
            if kind == 0:
                # Orientation is not visually decoded. The public lane prior
                # is a closer match to a newly deployed live troop than the
                # impossible all-zero facing vector.
                row[28] = 1.0 if own else -1.0
            row[30] = static[6]
            row[31] = float(token_name in {"Tower", "KingTower"})
            sort_key = (
                kind,
                int(not own),
                token_id,
                round(float(row[1]), 5),
                round(float(row[0]), 5),
            )
            rows.append((sort_key, token_id, row))
        rows.sort(key=lambda item: item[0])
        if len(rows) > self.max_entities:
            raise ValueError(
                f"TV Royale frame has {len(rows)} entities, exceeding "
                f"max_entities={self.max_entities}"
            )
        entity_ids = np.zeros((self.max_entities,), dtype=np.int64)
        entity_features = np.zeros(
            (self.max_entities, ENTITY_FEATURE_SIZE), dtype=np.float16
        )
        entity_mask = np.zeros((self.max_entities,), dtype=np.bool_)
        for index, (_, token_id, row) in enumerate(rows):
            entity_ids[index] = token_id
            entity_features[index] = row
            entity_mask[index] = True
        return entity_ids, entity_features, entity_mask

    def _public_entities(
        self,
        image_bgr: np.ndarray,
        detections: list[TVRoyaleDetection],
        *,
        previous_detections: list[TVRoyaleDetection] | None = None,
        frame_delta: int = 1,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Build schema-v2 entities without inventing unavailable dynamics."""

        def visible_body(class_name: str) -> bool:
            return self.is_supported_public_body_class(class_name)

        health_by_detection = {
            observation.entity_index: observation
            for observation in associate_health_to_entities(
                image_bgr,
                detections,
                body_class_predicate=visible_body,
            )
        }

        def body_identity(class_name: str) -> str | None:
            if not self.is_supported_public_body_class(class_name):
                return None
            mapped = self.unit_token(class_name)
            assert mapped is not None
            return mapped[1]

        motion_by_detection = (
            {
                observation.entity_index: observation
                for observation in associate_motion_between_frames(
                    previous_detections,
                    detections,
                    body_identity=body_identity,
                    frame_delta=frame_delta,
                )
            }
            if previous_detections is not None
            else {}
        )
        rows: list[tuple[tuple[Any, ...], int, np.ndarray, np.ndarray, float]] = []
        grid_height = IMAGE_HEIGHT - Y_OFFSET_TOP - Y_OFFSET_BOTTOM
        for detection_index, detection in enumerate(detections):
            if detection.confidence <= 0.0:
                continue
            if not self.is_supported_public_entity_class(detection.class_name):
                continue
            mapped = self.unit_token(detection.class_name)
            if mapped is None:
                continue
            token_id, token_name = mapped
            if token_name == self.builder.UNKNOWN_TOKEN:
                continue
            detection_confidence = float(np.clip(detection.confidence, 0.0, 1.0))
            center_x = (detection.x1 + detection.x2) * 0.5
            center_y = (detection.y1 + detection.y2) * 0.5
            source_x = center_x / IMAGE_WIDTH * BOARD_WIDTH
            source_y = (center_y - Y_OFFSET_TOP) / grid_height * BOARD_HEIGHT
            canonical_x = float(np.clip(BOARD_WIDTH - source_x, 0.0, BOARD_WIDTH))
            canonical_y = float(np.clip(BOARD_HEIGHT - source_y, 0.0, BOARD_HEIGHT))

            row = np.zeros((ENTITY_FEATURE_SIZE,), dtype=np.float32)
            confidence = np.zeros((ENTITY_FEATURE_SIZE,), dtype=np.float32)
            row[0] = canonical_x / BOARD_WIDTH
            row[1] = canonical_y / BOARD_HEIGHT
            confidence[0:2] = detection_confidence
            own = int(detection.belonging) == 0
            row[2] = float(own)
            row[3] = float(not own)
            confidence[2:4] = detection_confidence
            kind = self._entity_kind(token_name, self.builder)
            row[4 + kind] = 1.0
            confidence[4:9] = detection_confidence

            health = health_by_detection.get(detection_index)
            if health is not None:
                row[9] = float(np.clip(health.fill_fraction, 0.0, 1.0))
                confidence[9] = min(detection_confidence, health.confidence)

            known_identity = token_name != self.builder.UNKNOWN_TOKEN
            if known_identity:
                static = self.builder.card_stat_features[token_id]
                stats = self.builder.loader.get_card(token_name)
                speed = float(getattr(stats, "speed", 0.0) or 0.0)
                row[23] = float(
                    np.clip(math.log1p(abs(speed)) / math.log1p(1000.0), 0.0, 1.0)
                )
                row[24] = static[7]
                row[25] = static[8]
                row[26] = static[12]
                row[30] = static[6]
                confidence[[23, 24, 25, 26, 30]] = detection_confidence

            motion = motion_by_detection.get(detection_index)
            if motion is not None:
                # The source shows the lower player; canonical observation is
                # rotated 180 degrees, so both vector components change sign.
                canonical_delta_x = -motion.delta_x
                canonical_delta_y = -motion.delta_y
                magnitude = math.hypot(canonical_delta_x, canonical_delta_y)
                if magnitude >= 0.5:
                    row[27] = float(canonical_delta_x / magnitude)
                    row[28] = float(canonical_delta_y / magnitude)
                    confidence[27:29] = min(
                        detection_confidence, motion.confidence
                    )

            sort_key = (
                kind,
                int(not own),
                token_id,
                round(float(row[1]), 5),
                round(float(row[0]), 5),
            )
            rows.append((sort_key, token_id, row, confidence, detection_confidence))

        rows.sort(key=lambda item: item[0])
        if len(rows) > self.max_entities:
            raise ValueError(
                f"TV Royale frame has {len(rows)} entities, exceeding "
                f"max_entities={self.max_entities}"
            )
        entity_ids = np.zeros((self.max_entities,), dtype=np.int64)
        entity_features = np.zeros(
            (self.max_entities, ENTITY_FEATURE_SIZE), dtype=np.float16
        )
        entity_mask = np.zeros((self.max_entities,), dtype=np.bool_)
        entity_id_confidence = np.zeros((self.max_entities,), dtype=np.float32)
        entity_feature_confidence = np.zeros(
            (self.max_entities, ENTITY_FEATURE_SIZE), dtype=np.float32
        )
        for index, (_, token_id, row, confidence, identity_confidence) in enumerate(
            rows
        ):
            entity_ids[index] = token_id
            entity_features[index] = row
            entity_mask[index] = True
            entity_id_confidence[index] = identity_confidence
            entity_feature_confidence[index] = confidence
        return (
            entity_ids,
            entity_features,
            entity_mask,
            entity_id_confidence,
            entity_feature_confidence,
        )

    def _public_globals(
        self,
        *,
        frame: int,
        elixir: float,
        detections: list[TVRoyaleDetection],
        image_bgr: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        values = np.zeros((ACTOR_GLOBAL_SIZE,), dtype=np.float32)
        confidence = np.zeros((ACTOR_GLOBAL_SIZE,), dtype=np.float32)
        legacy = self._global_features(frame=frame, elixir=elixir)
        values[0:5] = legacy[0:5]
        confidence[0:5] = 1.0
        if math.isfinite(elixir) and elixir >= 0.0:
            values[5] = legacy[5]
            confidence[5] = 1.0

        def visible_body(class_name: str) -> bool:
            return self.is_supported_public_body_class(class_name)

        for observation in associate_health_to_entities(
            image_bgr,
            detections,
            body_class_predicate=visible_body,
        ):
            normalized = _normalized_name(observation.entity_class)
            own = observation.belonging == 0
            if normalized == "kingtower":
                feature = 10 if own else 13
                if not own:
                    values[17] = 1.0
                    confidence[17] = max(
                        confidence[17],
                        float(np.clip(detections[observation.entity_index].confidence, 0, 1)),
                    )
            elif normalized in {"queentower", "cannoneertower", "daggerduchesstower"}:
                canonical_x = 1.0 - observation.center_x / IMAGE_WIDTH
                canonical_left = canonical_x < 0.5
                if own:
                    feature = 8 if canonical_left else 9
                else:
                    feature = 11 if canonical_left else 12
            else:
                continue
            if observation.confidence >= confidence[feature]:
                values[feature] = float(np.clip(observation.fill_fraction, 0.0, 1.0))
                confidence[feature] = float(np.clip(observation.confidence, 0.0, 1.0))
        return values, confidence

    def public_observation(
        self,
        *,
        image_bgr: np.ndarray,
        raw_hand: Any,
        elixir: float,
        frame: int,
        detections: list[TVRoyaleDetection],
        previous_detections: list[TVRoyaleDetection] | None = None,
        previous_frame: int | None = None,
        raw_next_card: Any = None,
    ) -> ConfidenceAwareActorObservation:
        """Convert one replay frame into confidence-aware public schema v2."""

        (
            entity_ids,
            entity_features,
            entity_mask,
            entity_id_confidence,
            entity_feature_confidence,
        ) = self._public_entities(
            image_bgr,
            detections,
            previous_detections=previous_detections,
            frame_delta=(frame - previous_frame) if previous_frame is not None else 1,
        )
        hand_ids, hand_names = self._hand(raw_hand, raw_next_card=raw_next_card)
        hand_id_confidence = np.asarray(
            [1.0 if name is not None else 0.0 for name in hand_names],
            dtype=np.float32,
        )
        global_features, global_feature_confidence = self._public_globals(
            frame=frame,
            elixir=elixir,
            detections=detections,
            image_bgr=image_bgr,
        )
        history_slots = self.builder.spec.public_history_slots
        seen_slots = self.builder.spec.public_seen_card_slots
        observation = ActorObservation(
            entity_ids=entity_ids,
            entity_features=entity_features,
            entity_mask=entity_mask,
            hand_ids=hand_ids,
            global_features=global_features,
            opponent_history_ids=np.zeros((history_slots,), dtype=np.int64),
            opponent_history_ages=np.zeros((history_slots,), dtype=np.float32),
            opponent_seen_card_ids=np.zeros((seen_slots,), dtype=np.int64),
        )
        result = ConfidenceAwareActorObservation(
            observation=observation,
            entity_id_confidence=entity_id_confidence,
            entity_feature_confidence=entity_feature_confidence,
            hand_id_confidence=hand_id_confidence,
            global_feature_confidence=global_feature_confidence,
            opponent_history_confidence=np.zeros(
                (history_slots,), dtype=np.float32
            ),
            opponent_seen_card_confidence=np.zeros(
                (seen_slots,), dtype=np.float32
            ),
        )
        validate_real_play_feature_contract(result)
        return result

    def _hand(
        self,
        raw_hand: Any,
        *,
        raw_next_card: Any = None,
    ) -> tuple[np.ndarray, list[str | None]]:
        values = list(raw_hand) if isinstance(raw_hand, (list, tuple)) else []
        values = values[:NUM_HAND_SLOTS]
        values.extend([None] * (NUM_HAND_SLOTS - len(values)))
        names = [self.source_card_name(value) for value in values]
        # The local player's Next icon is public. Older corpora did not decode
        # it and continue to pass ``None``; live/current-frame extractors may
        # supply a directly observed identity without exposing future cards.
        names.append(self.source_card_name(raw_next_card))
        hand_ids = np.asarray(
            [0 if name is None else self.builder.token_id(name) for name in names],
            dtype=np.int64,
        )
        return hand_ids, names

    def _global_features(self, *, frame: int, elixir: float) -> np.ndarray:
        seconds = max(0.0, float(frame)) / self.source_frame_hz
        progress = float(np.clip(seconds / 300.0, 0.0, 1.0))
        result = np.zeros((ACTOR_GLOBAL_SIZE,), dtype=np.float32)
        result[0] = progress
        result[1] = 1.0 - progress
        result[2] = float(seconds >= 120.0)
        result[3] = float(seconds >= 240.0)
        result[4] = float(seconds >= 180.0)
        result[5] = float(np.clip(float(elixir) / 10.0, 0.0, 1.0))
        # Crown counts and exact tower HP are not decoded from the source. The
        # entity table still exposes public tower presence and position.
        result[8:14] = 1.0
        result[17] = 1.0
        return result

    def _action_mask(
        self,
        hand_names: list[str | None],
        *,
        elixir: float,
    ) -> np.ndarray:
        mask = np.zeros((self.action_count,), dtype=np.bool_)
        blocked = set(TileGrid.BLOCKED_TILES)
        own_tile_count = BOARD_WIDTH * (BOARD_HEIGHT // 2)
        for slot, card_name in enumerate(hand_names[:NUM_HAND_SLOTS]):
            if card_name is None:
                continue
            stats = self.builder.loader.get_card(card_name)
            cost = float(getattr(stats, "mana_cost", 0.0) or 0.0)
            if not math.isfinite(elixir) or elixir < 0.0 or cost > elixir + 1e-6:
                continue
            kind = str(getattr(stats, "card_type", "") or "").lower()
            can_deploy_enemy_side = bool(
                kind == "spell"
                or getattr(stats, "can_deploy_on_enemy_side", False)
            )
            tile_range = (
                range(NUM_TILES) if can_deploy_enemy_side else range(own_tile_count)
            )
            for tile in tile_range:
                if kind == "spell" or tile not in blocked:
                    mask[slot * NUM_TILES + tile] = True
        mask[self.noop_action] = True
        return mask

    def is_legal_source_placement(
        self,
        *,
        raw_card: Any,
        raw_hand: Any,
        elixir: float,
        x: int,
        y: int,
    ) -> bool:
        """Return whether a source placement is legal for its observed hand.

        The TV Royale shards contain some opponent-side or otherwise mismatched
        card/location rows. Those are not detector jitter and must not be made
        legal by mutating the action mask used for imitation.
        """

        target_card = self.source_card_name(raw_card)
        if target_card is None or x < 0 or y < 0:
            return False
        _, hand_names = self._hand(raw_hand)
        try:
            target_slot = hand_names[:NUM_HAND_SLOTS].index(target_card)
        except ValueError:
            return False
        target_tile = self.source_pixel_to_canonical_tile(x, y)
        expert_action = target_slot * NUM_TILES + target_tile
        return bool(self._action_mask(hand_names, elixir=elixir)[expert_action])

    def convert(
        self,
        *,
        raw_card: str,
        raw_hand: Any,
        elixir: float,
        frame: int,
        x: int,
        y: int,
        detections: list[TVRoyaleDetection],
    ) -> ConvertedTVRoyalePlacement | None:
        target_card = self.source_card_name(raw_card)
        if target_card is None or x < 0 or y < 0:
            return None
        hand_ids, hand_names = self._hand(raw_hand)
        try:
            target_slot = hand_names[:NUM_HAND_SLOTS].index(target_card)
        except ValueError:
            return None
        target_tile = self.source_pixel_to_canonical_tile(x, y)
        expert_action = target_slot * NUM_TILES + target_tile
        action_mask = self._action_mask(hand_names, elixir=elixir)
        if not action_mask[expert_action]:
            return None
        entity_ids, entity_features, entity_mask = self._entities(detections)
        return ConvertedTVRoyalePlacement(
            entity_ids=entity_ids,
            entity_features=entity_features,
            entity_mask=entity_mask,
            hand_ids=hand_ids,
            global_features=self._global_features(frame=frame, elixir=elixir),
            action_mask=action_mask,
            expert_action=expert_action,
            target_card=target_card,
            target_slot=target_slot,
        )

    def convert_type_only(
        self,
        *,
        raw_card: str,
        raw_hand: Any,
        elixir: float,
        frame: int,
        detections: list[TVRoyaleDetection],
    ) -> ConvertedTVRoyalePlacement | None:
        """Encode a played-card label without claiming a deployment location.

        The returned placement action uses the first legal tile only as a
        carrier for the hand-slot identity. It is valid exclusively with the
        ``type-head-v1`` objective, whose location coefficient is forced to
        zero. Production manifests label these rows explicitly as type-only.
        """

        target_card = self.source_card_name(raw_card)
        if target_card is None:
            return None
        hand_ids, hand_names = self._hand(raw_hand)
        try:
            target_slot = hand_names[:NUM_HAND_SLOTS].index(target_card)
        except ValueError:
            return None
        action_mask = self._action_mask(hand_names, elixir=elixir)
        legal_tiles = np.flatnonzero(
            action_mask[
                target_slot * NUM_TILES : (target_slot + 1) * NUM_TILES
            ]
        )
        if legal_tiles.size == 0:
            return None
        expert_action = target_slot * NUM_TILES + int(legal_tiles[0])
        entity_ids, entity_features, entity_mask = self._entities(detections)
        return ConvertedTVRoyalePlacement(
            entity_ids=entity_ids,
            entity_features=entity_features,
            entity_mask=entity_mask,
            hand_ids=hand_ids,
            global_features=self._global_features(frame=frame, elixir=elixir),
            action_mask=action_mask,
            expert_action=expert_action,
            target_card=target_card,
            target_slot=target_slot,
        )

    def convert_noop(
        self,
        *,
        raw_card: str,
        raw_hand: Any,
        elixir: float,
        frame: int,
        detections: list[TVRoyaleDetection],
    ) -> ConvertedTVRoyalePlacement | None:
        """Convert a source-authored no-card-play frame into a legal no-op."""

        accepted, _ = self.is_noop_training_candidate(
            raw_card=raw_card,
            raw_hand=raw_hand,
        )
        if not accepted:
            return None
        hand_ids, hand_names = self._hand(raw_hand)
        entity_ids, entity_features, entity_mask = self._entities(detections)
        action_mask = self._action_mask(hand_names, elixir=elixir)
        if not action_mask[self.noop_action]:
            return None
        return ConvertedTVRoyalePlacement(
            entity_ids=entity_ids,
            entity_features=entity_features,
            entity_mask=entity_mask,
            hand_ids=hand_ids,
            global_features=self._global_features(frame=frame, elixir=elixir),
            action_mask=action_mask,
            expert_action=self.noop_action,
            target_card="<noop>",
            target_slot=-1,
        )
