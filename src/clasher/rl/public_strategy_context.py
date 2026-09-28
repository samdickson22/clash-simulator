from __future__ import annotations

from typing import Protocol

import numpy as np

from .structured_obs import ACTOR_GLOBAL_SIZE, ENTITY_FEATURE_SIZE

PUBLIC_STRATEGIC_CONTEXT_VERSION = 1

_TEAM_NAMES = ("own", "enemy")
_LANE_NAMES = ("left", "right")
_LANE_FEATURE_NAMES = (
    "combat_count",
    "deployed_elixir",
    "surviving_elixir",
    "air_surviving_elixir",
    "forward_pressure",
    "ranged_pressure",
)

PUBLIC_STRATEGIC_CONTEXT_NAMES = (
    "match_progress",
    "match_remaining",
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
    "own_champion_cooldown",
    "own_champion_duration",
    "own_next_card_refill",
    "enemy_king_active",
    *(
        f"{team}_{lane}_{feature}"
        for team in _TEAM_NAMES
        for lane in _LANE_NAMES
        for feature in _LANE_FEATURE_NAMES
    ),
)
PUBLIC_STRATEGIC_CONTEXT_SIZE = len(PUBLIC_STRATEGIC_CONTEXT_NAMES)


class PublicObservation(Protocol):
    entity_ids: np.ndarray
    entity_features: np.ndarray
    entity_mask: np.ndarray
    global_features: np.ndarray


def canonicalize_public_globals(
    global_features: np.ndarray,
    *,
    perspective_player: int,
) -> np.ndarray:
    """Return public globals in the same 180-degree canonical frame as entities.

    The legacy actor observation rotates player-1 entity coordinates, but its
    tower HP slots retain world-space left/right ordering. Correct that mismatch
    locally without changing the inputs consumed by existing checkpoints.
    """

    if perspective_player not in {0, 1}:
        raise ValueError("perspective_player must be 0 or 1")
    result: np.ndarray = np.asarray(global_features, dtype=np.float32).copy()
    if result.shape != (ACTOR_GLOBAL_SIZE,):
        raise ValueError(
            "public global feature shape mismatch: "
            f"expected {(ACTOR_GLOBAL_SIZE,)}, got {result.shape}"
        )
    if perspective_player == 1:
        result[[8, 9]] = result[[9, 8]]
        result[[11, 12]] = result[[12, 11]]
    return result


def build_public_strategic_context(
    observation: PublicObservation,
    card_stat_features: np.ndarray,
    *,
    perspective_player: int,
) -> np.ndarray:
    """Summarize public tower state and visible lane pressure without card rules.

    The summary consumes only actor-visible tensors and the same public static
    card features already supplied to the policy. It contains no opponent hand,
    cycle, elixir, private target ID, or card-name branch.
    """

    entity_ids = np.asarray(observation.entity_ids)
    entity_features = np.asarray(observation.entity_features, dtype=np.float32)
    entity_mask = np.asarray(observation.entity_mask, dtype=np.bool_)
    card_stats = np.asarray(card_stat_features, dtype=np.float32)
    if entity_ids.ndim != 1 or entity_mask.shape != entity_ids.shape:
        raise ValueError("public entity IDs and mask must be aligned vectors")
    if entity_features.shape != (len(entity_ids), ENTITY_FEATURE_SIZE):
        raise ValueError("public entity feature table has an unexpected shape")
    if card_stats.ndim != 2 or card_stats.shape[1] < 8:
        raise ValueError("public card stat table must contain base card features")
    if entity_ids.size and (
        int(entity_ids.min(initial=0)) < 0
        or int(entity_ids.max(initial=0)) >= len(card_stats)
    ):
        raise ValueError("public entity token is outside the card stat table")

    result = np.zeros((PUBLIC_STRATEGIC_CONTEXT_SIZE,), dtype=np.float32)
    result[:ACTOR_GLOBAL_SIZE] = canonicalize_public_globals(
        observation.global_features,
        perspective_player=perspective_player,
    )

    # Each lane block is accumulated in interpretable physical units and then
    # normalized. Static feature 0 is elixir / 10; feature 7 is attack range / 12.
    lane_blocks = result[ACTOR_GLOBAL_SIZE:].reshape(2, 2, len(_LANE_FEATURE_NAMES))
    for token_id, features, valid in zip(
        entity_ids,
        entity_features,
        entity_mask,
        strict=True,
    ):
        if not valid:
            continue
        own = bool(features[2] > 0.5)
        enemy = bool(features[3] > 0.5)
        # Summarize deployable combat bodies only. This excludes spells,
        # projectiles, effects, and zero-cost Crown Towers without naming them.
        combat_body = bool(features[4] > 0.5 or features[5] > 0.5)
        elixir_over_ten = float(card_stats[int(token_id), 0])
        if own == enemy or not combat_body or elixir_over_ten <= 0.0:
            continue

        team = 0 if own else 1
        lane = 0 if float(features[0]) < 0.5 else 1
        hp_fraction = float(np.clip(features[9], 0.0, 1.0))
        progress = float(features[1]) if own else 1.0 - float(features[1])
        progress = float(np.clip(progress, 0.0, 1.0))
        surviving_value = elixir_over_ten * hp_fraction
        block = lane_blocks[team, lane]
        block[0] += 1.0
        block[1] += elixir_over_ten
        block[2] += surviving_value
        block[3] += surviving_value * float(features[11] > 0.5)
        block[4] += surviving_value * progress
        block[5] += surviving_value * float(np.clip(card_stats[int(token_id), 7], 0.0, 1.0))

    # 16 bodies and 40 deployed elixir are deliberately generous saturation
    # points for a lane. Clipping keeps the feature contract bounded under swarms.
    lane_blocks[..., 0] = np.clip(lane_blocks[..., 0] / 16.0, 0.0, 1.0)
    lane_blocks[..., 1:] = np.clip(lane_blocks[..., 1:] / 4.0, 0.0, 1.0)
    return result
