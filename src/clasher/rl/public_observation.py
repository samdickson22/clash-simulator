from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .own_card_history import AcceptedOwnPlay
from .structured_obs import VISIBLE_CARD_SLOTS, ActorObservation

PUBLIC_OBSERVATION_SCHEMA_VERSION = 4

# The legacy 32/18 feature widths are shared with exact simulator corpora.  A
# width match is therefore not evidence that an observation can be produced by
# the deployed camera.  Keep an explicit, named sensor contract and validate it
# before using a corpus or rollout as real-play actor input.
ENTITY_FEATURE_NAMES = (
    "x",
    "y",
    "own_team",
    "enemy_team",
    "troop_kind",
    "building_kind",
    "projectile_kind",
    "area_effect_kind",
    "other_kind",
    "hp_fraction",
    "shield_fraction",
    "airborne",
    "deployment_pending",
    "deployment_remaining_fraction",
    "stun_remaining",
    "slow_remaining",
    "haste_remaining",
    "special_move_active",
    "stealth_active",
    "hidden_building",
    "forced_movement",
    "attack_windup",
    "charging",
    "base_speed",
    "attack_range",
    "sight_range",
    "collision_radius",
    "motion_x",
    "motion_y",
    "effect_progress",
    "base_damage",
    "tower_active",
)
GLOBAL_FEATURE_NAMES = (
    "battle_progress",
    "battle_remaining",
    "double_elixir",
    "triple_elixir",
    "overtime",
    "own_elixir",
    "own_crowns",
    "enemy_crowns",
    "own_left_tower_hp",
    "own_right_tower_hp",
    "own_king_tower_hp",
    "enemy_left_tower_hp",
    "enemy_right_tower_hp",
    "enemy_king_tower_hp",
    "champion_cooldown",
    "champion_duration",
    "next_card_refill",
    "enemy_king_alive",
)

# These are the fields implemented by the current frame/temporal extractor.
# Static lookup fields are permitted only after the detector has identified the
# body, because the real client can perform the same public card-data lookup.
REAL_PLAY_ENTITY_FEATURE_INDICES = frozenset(
    {
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        23,
        24,
        25,
        26,
        27,
        28,
        30,
    }
)
REAL_PLAY_GLOBAL_FEATURE_INDICES = frozenset(
    {
        0,
        1,
        2,
        3,
        4,
        5,
        8,
        9,
        10,
        11,
        12,
        13,
        17,
    }
)
REAL_PLAY_FEATURE_CONTRACT_VERSION = 2

if len(ENTITY_FEATURE_NAMES) != 32 or len(GLOBAL_FEATURE_NAMES) != 18:
    raise AssertionError("real-play feature names must match the actor schema")


@dataclass(frozen=True)
class PublicObservationDegradationProfile:
    """Provisional public-sensor coverage used to degrade simulator state.

    Coverage values are explicit configuration, not claims about detector
    recall. They must be recalibrated from a labelled multi-arena set before a
    production imitation/RL run.
    """

    entity_keep_probability: float = 1.0
    identity_confidence: float = 0.85
    position_confidence: float = 0.85
    static_feature_confidence: float = 0.85
    hp_keep_probability: float = 0.66
    hp_confidence: float = 0.69
    motion_keep_probability: float = 0.36
    motion_confidence: float = 0.60
    tower_hp_keep_probability: float = 0.66
    tower_hp_confidence: float = 0.69
    position_noise_std: float = 0.0
    hp_noise_std: float = 0.0

    def validate(self) -> None:
        for name in (
            "entity_keep_probability",
            "identity_confidence",
            "position_confidence",
            "static_feature_confidence",
            "hp_keep_probability",
            "hp_confidence",
            "motion_keep_probability",
            "motion_confidence",
            "tower_hp_keep_probability",
            "tower_hp_confidence",
        ):
            value = getattr(self, name)
            if not np.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1]")
        for name in ("position_noise_std", "hp_noise_std"):
            value = getattr(self, name)
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")


TV_ROYALE_PILOT_DEGRADATION = PublicObservationDegradationProfile()


def _finite_unit_interval(name: str, value: np.ndarray) -> None:
    if not np.issubdtype(value.dtype, np.number):
        raise TypeError(f"{name} must be numeric")
    if not np.all(np.isfinite(value)):
        raise ValueError(f"{name} contains non-finite values")
    if np.any(value < 0.0) or np.any(value > 1.0):
        raise ValueError(f"{name} must stay in [0, 1]")


def _missing_values_are_zero(
    name: str,
    values: np.ndarray,
    confidence: np.ndarray,
) -> None:
    missing = confidence <= 0.0
    if np.any(values[missing] != 0):
        invalid = np.argwhere(missing & (values != 0))
        first = tuple(int(index) for index in invalid[0])
        raise ValueError(
            f"{name} fabricates values where confidence is zero at {first}: "
            f"value={values[first]!r} confidence={confidence[first]!r}"
        )


@dataclass(frozen=True)
class ConfidenceAwareActorObservation:
    """Actor-visible values paired with explicit observation confidence.

    A confidence of one means the value is directly known in the source
    observation domain. Zero means missing, and the corresponding value must be
    the neutral zero placeholder. Intermediate values represent noisy public
    measurements such as detector-localized health bars. They are not
    probabilities that the underlying game state exists.

    The confidence arrays deliberately remain separate from the legacy
    32-feature policy input. This prevents old corpora/checkpoints from silently
    changing semantics; schema v3 also carries explicit match lifecycle outside those tensors.
    """

    observation: ActorObservation
    entity_id_confidence: np.ndarray
    entity_feature_confidence: np.ndarray
    hand_id_confidence: np.ndarray
    global_feature_confidence: np.ndarray
    opponent_history_confidence: np.ndarray
    opponent_seen_card_confidence: np.ndarray
    schema_version: int = PUBLIC_OBSERVATION_SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != PUBLIC_OBSERVATION_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported public observation schema {self.schema_version}"
            )
        observation = self.observation
        if observation.board_rotated is not None and type(observation.board_rotated) is not bool:
            raise ValueError("board rotation must be bool or unknown")
        if observation.terminal is not None and type(observation.terminal) is not bool:
            raise ValueError("terminal status must be bool or unknown")
        levels, level_confidence = observation.entity_levels, observation.entity_level_confidence
        if (levels is None) != (level_confidence is None):
            raise ValueError('incomplete public entity level fields')
        if levels is not None:
            if levels.dtype != np.int64 or level_confidence.dtype != np.float32 or levels.shape != observation.entity_ids.shape or level_confidence.shape != levels.shape:
                raise ValueError('invalid public entity level shape or dtype')
            _finite_unit_interval('entity level confidence', level_confidence)
            if (((levels < 0) | (levels > 127)).any()
                or ((levels == 0) != (level_confidence == 0)).any()
                or ((~observation.entity_mask) & ((levels != 0) | (level_confidence != 0))).any()):
                raise ValueError('invalid public entity levels or confidence')
        expected_shapes = {
            "entity_id_confidence": observation.entity_ids.shape,
            "entity_feature_confidence": observation.entity_features.shape,
            "hand_id_confidence": observation.hand_ids.shape,
            "global_feature_confidence": observation.global_features.shape,
            "opponent_history_confidence": observation.opponent_history_ids.shape,
            "opponent_seen_card_confidence": observation.opponent_seen_card_ids.shape,
        }
        for name, expected in expected_shapes.items():
            value = getattr(self, name)
            if value.shape != expected:
                raise ValueError(f"{name} shape {value.shape} != {expected}")
            _finite_unit_interval(name, value)

        if observation.opponent_history_ages.shape != observation.opponent_history_ids.shape:
            raise ValueError("opponent history ages do not match history ids")
        if observation.entity_mask.shape != observation.entity_ids.shape:
            raise ValueError("entity mask does not match entity ids")
        if observation.entity_features.shape[:-1] != observation.entity_ids.shape:
            raise ValueError("entity features do not match entity ids")

        padded = ~observation.entity_mask.astype(np.bool_, copy=False)
        if np.any(self.entity_id_confidence[padded] != 0.0):
            raise ValueError("padded entities have identity confidence")
        if np.any(self.entity_feature_confidence[padded] != 0.0):
            raise ValueError("padded entities have feature confidence")
        if np.any(observation.entity_ids[padded] != 0):
            raise ValueError("padded entity ids must be zero")
        if np.any(observation.entity_features[padded] != 0.0):
            raise ValueError("padded entity features must be zero")

        _missing_values_are_zero(
            "entity ids", observation.entity_ids, self.entity_id_confidence
        )
        _missing_values_are_zero(
            "entity features",
            observation.entity_features,
            self.entity_feature_confidence,
        )
        _missing_values_are_zero(
            "hand ids", observation.hand_ids, self.hand_id_confidence
        )
        _missing_values_are_zero(
            "global features",
            observation.global_features,
            self.global_feature_confidence,
        )
        _missing_values_are_zero(
            "opponent history ids",
            observation.opponent_history_ids,
            self.opponent_history_confidence,
        )
        _missing_values_are_zero(
            "opponent history ages",
            observation.opponent_history_ages,
            self.opponent_history_confidence,
        )
        _missing_values_are_zero(
            "opponent seen-card ids",
            observation.opponent_seen_card_ids,
            self.opponent_seen_card_confidence,
        )


def validate_real_play_feature_contract(
    observation: ConfidenceAwareActorObservation,
) -> None:
    """Reject actor values unavailable from the current causal vision stack.

    Exact simulator observations intentionally fail this check when they expose
    status timers, attack windups, card-refill clocks, or other values for which
    the deployed extractor has no estimator.  Such truth remains valid for an
    asymmetric critic or oracle, but not for the real-play actor.
    """

    observation.validate()
    entity_confidence = observation.entity_feature_confidence
    global_confidence = observation.global_feature_confidence
    forbidden_entity = sorted(
        set(range(entity_confidence.shape[-1]))
        - REAL_PLAY_ENTITY_FEATURE_INDICES
    )
    forbidden_global = sorted(
        set(range(global_confidence.shape[-1]))
        - REAL_PLAY_GLOBAL_FEATURE_INDICES
    )
    leaked_entities = [
        ENTITY_FEATURE_NAMES[index]
        for index in forbidden_entity
        if np.any(entity_confidence[..., index] > 0.0)
    ]
    leaked_globals = [
        GLOBAL_FEATURE_NAMES[index]
        for index in forbidden_global
        if np.any(global_confidence[..., index] > 0.0)
    ]
    if leaked_entities or leaked_globals:
        raise ValueError(
            "observation exceeds real-play feature contract: "
            f"entity={leaked_entities}, global={leaked_globals}"
        )
    if observation.observation.hand_ids.shape[-1] > VISIBLE_CARD_SLOTS and (
        np.any(observation.observation.hand_ids[..., VISIBLE_CARD_SLOTS:] != 0)
        or np.any(observation.hand_id_confidence[..., VISIBLE_CARD_SLOTS:] > 0.0)
    ):
        raise ValueError("observation exposes cards beyond hand plus public next card")


def exact_public_observation(
    observation: ActorObservation,
) -> ConfidenceAwareActorObservation:
    """Wrap exact simulator public state with confidence and match lifecycle."""

    entity_known = observation.entity_mask.astype(np.float32, copy=True)
    result = ConfidenceAwareActorObservation(
        observation=observation,
        entity_id_confidence=entity_known,
        entity_feature_confidence=np.broadcast_to(
            entity_known[..., None], observation.entity_features.shape
        ).astype(np.float32, copy=True),
        hand_id_confidence=np.ones(observation.hand_ids.shape, dtype=np.float32),
        global_feature_confidence=np.ones(
            observation.global_features.shape, dtype=np.float32
        ),
        opponent_history_confidence=np.ones(
            observation.opponent_history_ids.shape, dtype=np.float32
        ),
        opponent_seen_card_confidence=np.ones(
            observation.opponent_seen_card_ids.shape, dtype=np.float32
        ),
    )
    result.validate()
    return result


def reference_public_observation(
    observation: ActorObservation,
) -> ConfidenceAwareActorObservation:
    """Project simulator state to the pinned reference observer's coverage.

    Retain exact visible geometry, body HP/levels, own hand/elixir and Crown
    HP. Effect timers and shield state stay unknown, as in the native public
    adapter. This is a reference comparison projection, not a camera model.
    """
    source = exact_public_observation(observation)
    features = observation.entity_features.copy()
    confidence = source.entity_feature_confidence.copy()
    features[:, 10:] = 0
    confidence[:, 10:] = 0
    bodies = observation.entity_mask & ((features[:, 4] + features[:, 5]) > 0.5)
    features[~bodies, 9] = 0
    confidence[~bodies, 9] = 0
    globals_ = np.zeros_like(observation.global_features)
    global_confidence = np.zeros_like(source.global_feature_confidence)
    for column in (5, 8, 9, 10, 11, 12, 13):
        globals_[column] = observation.global_features[column]
        global_confidence[column] = source.global_feature_confidence[column]
    projected = replace(
        source,
        observation=replace(
            observation, entity_features=features, global_features=globals_,
            opponent_history_ids=np.zeros_like(observation.opponent_history_ids),
            opponent_history_ages=np.zeros_like(observation.opponent_history_ages),
            opponent_seen_card_ids=np.zeros_like(observation.opponent_seen_card_ids),
        ),
        entity_feature_confidence=confidence,
        global_feature_confidence=global_confidence,
        opponent_history_confidence=np.zeros_like(source.opponent_history_confidence),
        opponent_seen_card_confidence=np.zeros_like(source.opponent_seen_card_confidence),
    )
    projected.validate()
    return projected


def degrade_simulator_public_observation(
    observation: ActorObservation,
    *,
    profile: PublicObservationDegradationProfile,
    rng: np.random.Generator,
    accepted_own_play: AcceptedOwnPlay | None = None,
) -> ConfidenceAwareActorObservation:
    """Project visual state; own command history needs a separate public receipt.

    The default drops simulator control metadata because replay images cannot
    establish acceptance. A controller may supply its confirmed own-play record.
    """

    profile.validate()
    exact_public_observation(observation)
    source_entities = observation.entity_features
    entity_ids = np.zeros_like(observation.entity_ids)
    entity_features = np.zeros_like(source_entities)
    entity_mask = np.zeros_like(observation.entity_mask)
    entity_id_confidence = np.zeros(observation.entity_ids.shape, dtype=np.float32)
    entity_feature_confidence = np.zeros(source_entities.shape, dtype=np.float32)

    for index in np.flatnonzero(observation.entity_mask).tolist():
        source = source_entities[index]
        # The detector exposes enabled bodies plus visible projectile/area
        # effects. Engine-only containers remain unavailable.
        visible_kind = bool(np.any(source[4:8] > 0.5))
        if not visible_kind:
            continue
        if rng.random() > profile.entity_keep_probability:
            continue
        entity_mask[index] = True
        entity_ids[index] = observation.entity_ids[index]
        entity_id_confidence[index] = profile.identity_confidence

        entity_features[index, 0:2] = source[0:2]
        if profile.position_noise_std > 0.0:
            entity_features[index, 0:2] = np.clip(
                entity_features[index, 0:2]
                + rng.normal(0.0, profile.position_noise_std, size=2),
                0.0,
                1.0,
            )
        entity_feature_confidence[index, 0:2] = profile.position_confidence

        entity_features[index, 2:9] = source[2:9]
        entity_feature_confidence[index, 2:9] = profile.identity_confidence
        for feature in (23, 24, 25, 26, 30):
            entity_features[index, feature] = source[feature]
            entity_feature_confidence[index, feature] = (
                profile.static_feature_confidence
            )

        is_body = source[4] > 0.5 or source[5] > 0.5
        if is_body and rng.random() <= profile.hp_keep_probability:
            hp = float(source[9])
            if profile.hp_noise_std > 0.0:
                hp += float(rng.normal(0.0, profile.hp_noise_std))
            entity_features[index, 9] = np.clip(hp, 0.0, 1.0)
            entity_feature_confidence[index, 9] = profile.hp_confidence

        facing = source[27:29]
        if (
            float(np.linalg.norm(facing)) > 1e-6
            and rng.random() <= profile.motion_keep_probability
        ):
            entity_features[index, 27:29] = facing
            entity_feature_confidence[index, 27:29] = profile.motion_confidence

    hand_ids = np.zeros_like(observation.hand_ids)
    hand_id_confidence = np.zeros(observation.hand_ids.shape, dtype=np.float32)
    public_hand_slots = min(VISIBLE_CARD_SLOTS, observation.hand_ids.size)
    hand_ids[:public_hand_slots] = observation.hand_ids[:public_hand_slots]
    hand_id_confidence[:public_hand_slots] = 1.0

    global_features = np.zeros_like(observation.global_features)
    global_feature_confidence = np.zeros(
        observation.global_features.shape, dtype=np.float32
    )
    directly_visible_globals = min(6, observation.global_features.size)
    global_features[:directly_visible_globals] = observation.global_features[
        :directly_visible_globals
    ]
    global_feature_confidence[:directly_visible_globals] = 1.0
    for feature in range(8, min(14, observation.global_features.size)):
        if rng.random() > profile.tower_hp_keep_probability:
            continue
        hp = float(observation.global_features[feature])
        if profile.hp_noise_std > 0.0:
            hp += float(rng.normal(0.0, profile.hp_noise_std))
        global_features[feature] = np.clip(hp, 0.0, 1.0)
        global_feature_confidence[feature] = profile.tower_hp_confidence

    projected = ActorObservation(
        # The current visual extractor has no calibrated level-label reader.
        entity_levels=None if observation.entity_levels is None else np.zeros_like(observation.entity_levels),
        entity_level_confidence=None if observation.entity_level_confidence is None else np.zeros_like(observation.entity_level_confidence),
        terminal=observation.terminal,
        board_rotated=observation.board_rotated,
        own_last_play=accepted_own_play,
        entity_ids=entity_ids,
        entity_features=entity_features,
        entity_mask=entity_mask,
        hand_ids=hand_ids,
        global_features=global_features,
        opponent_history_ids=np.zeros_like(observation.opponent_history_ids),
        opponent_history_ages=np.zeros_like(observation.opponent_history_ages),
        opponent_seen_card_ids=np.zeros_like(observation.opponent_seen_card_ids),
    )
    result = ConfidenceAwareActorObservation(
        observation=projected,
        entity_id_confidence=entity_id_confidence,
        entity_feature_confidence=entity_feature_confidence,
        hand_id_confidence=hand_id_confidence,
        global_feature_confidence=global_feature_confidence,
        opponent_history_confidence=np.zeros(
            observation.opponent_history_ids.shape, dtype=np.float32
        ),
        opponent_seen_card_confidence=np.zeros(
            observation.opponent_seen_card_ids.shape, dtype=np.float32
        ),
    )
    result.validate()
    validate_real_play_feature_contract(result)
    return result
