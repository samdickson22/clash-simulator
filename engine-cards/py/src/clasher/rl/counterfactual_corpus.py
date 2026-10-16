from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .common import NUM_HAND_SLOTS, NUM_TILES

PLACEMENT_KIND = 0
NO_OP_KIND = 1
ABILITY_KIND = 2
INVALID_KIND = -1


@dataclass(frozen=True)
class CandidateContext:
    valid: np.ndarray
    kinds: np.ndarray
    card_ids: np.ndarray
    card_features: np.ndarray
    tile_features: np.ndarray
    policy_logits: np.ndarray
    policy_log_probabilities: np.ndarray
    policy_type_log_probabilities: np.ndarray


def terminal_candidate_order(
    outcome: float,
    crowns: int,
    tower_damage: float,
) -> tuple[float, int, float]:
    """Canonical terminal preference: result, crowns, then tower damage."""
    if not np.isfinite(outcome) or not np.isfinite(tower_damage):
        raise ValueError("terminal candidate ordering requires finite values")
    return float(outcome), int(crowns), float(tower_damage)


def action_type_index(action: int, *, no_op_action: int) -> int:
    """Map a flat action to its four placement slots, no-op, or ability."""
    if action < 0:
        return INVALID_KIND
    if action < NUM_HAND_SLOTS * NUM_TILES:
        return action // NUM_TILES
    if action == no_op_action:
        return NUM_HAND_SLOTS
    if action == no_op_action + 1:
        return NUM_HAND_SLOTS + 1
    raise ValueError(f"action {action} is outside the canonical action space")


def top_policy_candidates(
    *,
    base_action: int,
    joint_logits: np.ndarray,
    action_mask: np.ndarray,
    no_op_action: int,
    max_candidates: int,
) -> np.ndarray:
    """Take the strongest legal action from every type before truncation."""
    if max_candidates <= 0:
        raise ValueError("max_candidates must be positive")
    logits = np.asarray(joint_logits, dtype=np.float32)
    mask = np.asarray(action_mask, dtype=np.bool_)
    if logits.shape != mask.shape or logits.ndim != 1:
        raise ValueError("joint logits and action mask have invalid shape")
    if no_op_action + 2 != logits.shape[0]:
        raise ValueError("joint action space does not end with no-op and ability")
    if not 0 <= base_action < len(mask) or not mask[base_action]:
        raise ValueError("base action must be legal")
    primary: list[tuple[float, int]] = []
    for slot in range(NUM_HAND_SLOTS):
        start = slot * NUM_TILES
        legal_tiles = np.flatnonzero(mask[start : start + NUM_TILES])
        if not len(legal_tiles):
            continue
        slot_logits = logits[start : start + NUM_TILES]
        tile = min(
            legal_tiles.tolist(),
            key=lambda value: (-float(slot_logits[value]), int(value)),
        )
        action = start + int(tile)
        primary.append((float(logits[action]), action))
    for action in (no_op_action, no_op_action + 1):
        if mask[action]:
            primary.append((float(logits[action]), action))
    primary.sort(key=lambda row: (-row[0], row[1]))
    result = [base_action]
    result.extend(action for _logit, action in primary if action != base_action)
    return np.asarray(result[:max_candidates], dtype=np.int64)


def should_query_counterfactual(
    *,
    decision_index: int,
    last_query_decision: int | None,
    tick: int,
    collected: int,
    states_per_game: int,
    minimum_tick: int,
    query_stride: int,
    can_play: bool,
) -> bool:
    """Return whether this exact policy decision is an intervention root."""
    if query_stride <= 0:
        raise ValueError("query_stride must be positive")
    return bool(
        collected < states_per_game
        and tick >= minimum_tick
        and (
            last_query_decision is None
            or decision_index - last_query_decision >= query_stride
        )
        and can_play
    )


def _masked_log_softmax(logits: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if logits.ndim != 1 or mask.shape != logits.shape:
        raise ValueError("logits and mask must be equally shaped rank-one arrays")
    if not np.any(mask):
        raise ValueError("at least one action must be legal")
    legal = logits[mask].astype(np.float64, copy=False)
    maximum = float(np.max(legal))
    normalizer = maximum + float(np.log(np.exp(legal - maximum).sum()))
    result = np.full(logits.shape, -np.inf, dtype=np.float32)
    result[mask] = (legal - normalizer).astype(np.float32)
    return result


def build_candidate_context(
    *,
    candidate_actions: np.ndarray,
    hand_ids: np.ndarray,
    card_stat_features: np.ndarray,
    canonical_tile_features: np.ndarray,
    joint_logits: np.ndarray,
    action_mask: np.ndarray,
    no_op_action: int,
) -> CandidateContext:
    """Encode action-conditioned public semantics without card-name branches."""
    actions = np.asarray(candidate_actions, dtype=np.int64)
    hand = np.asarray(hand_ids, dtype=np.int64)
    card_stats = np.asarray(card_stat_features, dtype=np.float32)
    tile_stats = np.asarray(canonical_tile_features, dtype=np.float32)
    logits = np.asarray(joint_logits, dtype=np.float32)
    mask = np.asarray(action_mask, dtype=np.bool_)
    if actions.ndim != 1:
        raise ValueError("candidate actions must be rank one")
    if hand.shape != (NUM_HAND_SLOTS,):
        raise ValueError("hand_ids must contain exactly four slots")
    if card_stats.ndim != 2 or np.any(hand < 0) or np.any(hand >= len(card_stats)):
        raise ValueError("hand_ids are outside the card feature table")
    if tile_stats.shape[0] != NUM_TILES or tile_stats.ndim != 2:
        raise ValueError("canonical tile feature table has invalid shape")
    if logits.shape != mask.shape or logits.ndim != 1:
        raise ValueError("joint logits and action mask have invalid shape")
    if no_op_action + 2 != logits.shape[0]:
        raise ValueError("joint action space does not end with no-op and ability")

    valid = actions >= 0
    kinds = np.full(actions.shape, INVALID_KIND, dtype=np.int8)
    card_ids = np.zeros(actions.shape, dtype=np.int64)
    candidate_card_features = np.zeros(
        (*actions.shape, card_stats.shape[1]),
        dtype=np.float32,
    )
    candidate_tile_features = np.zeros(
        (*actions.shape, tile_stats.shape[1]),
        dtype=np.float32,
    )
    policy_logits = np.full(actions.shape, -np.inf, dtype=np.float32)
    policy_log_probabilities = np.full(actions.shape, -np.inf, dtype=np.float32)
    policy_type_log_probabilities = np.full(
        actions.shape,
        -np.inf,
        dtype=np.float32,
    )
    action_log_probabilities = _masked_log_softmax(logits, mask)
    type_log_masses = np.full(NUM_HAND_SLOTS + 2, -np.inf, dtype=np.float32)
    for action_type in range(NUM_HAND_SLOTS + 2):
        if action_type < NUM_HAND_SLOTS:
            start = action_type * NUM_TILES
            stop = start + NUM_TILES
        else:
            start = no_op_action + action_type - NUM_HAND_SLOTS
            stop = start + 1
        legal = mask[start:stop]
        if not np.any(legal):
            continue
        type_logs = action_log_probabilities[start:stop][legal].astype(
            np.float64,
            copy=False,
        )
        maximum = float(np.max(type_logs))
        type_log_masses[action_type] = np.float32(
            maximum + float(np.log(np.exp(type_logs - maximum).sum()))
        )

    for index, action_value in enumerate(actions.tolist()):
        if action_value < 0:
            continue
        if action_value >= logits.shape[0]:
            raise ValueError(f"candidate action {action_value} is out of range")
        if not mask[action_value]:
            raise ValueError(f"candidate action {action_value} is not legal")
        action_type = action_type_index(action_value, no_op_action=no_op_action)
        kinds[index] = (
            PLACEMENT_KIND
            if action_type < NUM_HAND_SLOTS
            else NO_OP_KIND
            if action_type == NUM_HAND_SLOTS
            else ABILITY_KIND
        )
        policy_logits[index] = logits[action_value]
        policy_log_probabilities[index] = action_log_probabilities[action_value]
        policy_type_log_probabilities[index] = type_log_masses[action_type]
        if action_type >= NUM_HAND_SLOTS:
            continue
        card_id = int(hand[action_type])
        tile = action_value % NUM_TILES
        card_ids[index] = card_id
        candidate_card_features[index] = card_stats[card_id]
        candidate_tile_features[index] = tile_stats[tile]

    return CandidateContext(
        valid=valid,
        kinds=kinds,
        card_ids=card_ids,
        card_features=candidate_card_features,
        tile_features=candidate_tile_features,
        policy_logits=policy_logits,
        policy_log_probabilities=policy_log_probabilities,
        policy_type_log_probabilities=policy_type_log_probabilities,
    )
