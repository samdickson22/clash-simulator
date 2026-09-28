from __future__ import annotations

from dataclasses import replace

import numpy as np
import torch

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.common import NUM_TILES
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import (
    PUBLIC_BELIEF_PARAMETER_PREFIXES,
    _stack_step_inputs,
)


def _first_legal_placement(
    battle: BattleState,
    action_space: DiscreteTileActionSpace,
    player_id: int,
) -> int:
    mask = action_space.legal_action_mask(battle, player_id)
    placements = np.flatnonzero(mask[: action_space.no_op_action])
    assert placements.size
    return int(placements[0])


def test_public_history_records_only_successful_plays_and_clones_independently():
    battle = BattleState(fast_path=True)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)

    assert not action_space.apply_action(battle, 1, -1)
    assert battle.public_card_play_history == {0: [], 1: []}
    action = _first_legal_placement(battle, action_space, 1)
    card_name = battle.players[1].hand[action // NUM_TILES]
    assert card_name is not None
    assert action_space.apply_action(battle, 1, action)
    assert battle.public_card_play_history[1] == [(0, card_name)]

    cloned = battle.clone()
    cloned.public_card_play_history[1].append((9, "Giant"))
    assert battle.public_card_play_history[1] == [(0, card_name)]


def test_public_history_observation_is_opponent_only_recent_first_with_age():
    battle = BattleState()
    battle.public_card_play_history[0] = [(0, "Knight")]
    battle.public_card_play_history[1] = [(0, "Giant"), (10, "Archer")]
    battle.tick = 30
    builder = StructuredObservationBuilder(public_history_slots=4)

    player0 = builder.build_actor(battle, 0)
    player1 = builder.build_actor(battle, 1)

    assert player0.opponent_history_ids.tolist() == [
        builder.token_id("Archer"),
        builder.token_id("Giant"),
        0,
        0,
    ]
    np.testing.assert_allclose(
        player0.opponent_history_ages[:2],
        np.asarray([20 * battle.dt / 60.0, 30 * battle.dt / 60.0]),
    )
    assert player1.opponent_history_ids.tolist() == [
        builder.token_id("Knight"),
        0,
        0,
        0,
    ]


def test_public_seen_cards_persist_in_first_discovery_order_without_duplicates():
    battle = BattleState()
    battle.public_card_play_history[0] = [(0, "Knight")]
    battle.public_card_play_history[1] = [
        (0, "Giant"),
        (10, "Archer"),
        (20, "Giant"),
        (30, "Zap"),
        (40, "MiniP.E.K.K.A"),
        (50, "Fireball"),
    ]
    builder = StructuredObservationBuilder(
        public_history_slots=4,
        public_seen_card_slots=8,
    )

    player0 = builder.build_actor(battle, 0)
    player1 = builder.build_actor(battle, 1)

    assert player0.opponent_history_ids.tolist() == [
        builder.token_id("Fireball"),
        builder.token_id("MiniP.E.K.K.A"),
        builder.token_id("Zap"),
        builder.token_id("Giant"),
    ]
    assert player0.opponent_seen_card_ids.tolist() == [
        builder.token_id("Giant"),
        builder.token_id("Archer"),
        builder.token_id("Zap"),
        builder.token_id("MiniP.E.K.K.A"),
        builder.token_id("Fireball"),
        0,
        0,
        0,
    ]
    assert player1.opponent_seen_card_ids.tolist() == [
        builder.token_id("Knight"),
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    ]


def test_zero_initialized_public_history_upgrade_preserves_checkpoint_outputs():
    checkpoint = torch.load(
        "checkpoints/tv_raw1000_spatial_value_rl_seed1044801/"
        "policy_v2_update_000040.pt",
        map_location="cpu",
        weights_only=False,
    )
    source_config = PolicyConfig.from_dict(checkpoint["model_config"])
    source_builder = StructuredObservationBuilder(
        token_names=checkpoint["token_names"],
        max_entities=source_config.max_entities,
        card_semantics_version=source_config.card_semantics_version,
    )
    source = ClasherPolicy(source_config, source_builder.card_stat_features).eval()
    source.load_state_dict(checkpoint["model_state_dict"])

    target_config = replace(
        source_config,
        public_history_slots=4,
        public_seen_card_slots=8,
    )
    target_builder = StructuredObservationBuilder(
        token_names=checkpoint["token_names"],
        max_entities=target_config.max_entities,
        card_semantics_version=target_config.card_semantics_version,
        public_history_slots=target_config.public_history_slots,
        public_seen_card_slots=target_config.public_seen_card_slots,
    )
    target = ClasherPolicy(target_config, target_builder.card_stat_features).eval()
    incompatible = target.load_state_dict(checkpoint["model_state_dict"], strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys
    assert all(
        key.startswith(PUBLIC_BELIEF_PARAMETER_PREFIXES)
        for key in incompatible.missing_keys
    )
    allowed_prefixes = (
        "public_history_",
        "public_seen_card_",
        "public_belief_",
    )
    assert all(key.startswith(allowed_prefixes) for key in incompatible.missing_keys)

    battle = BattleState(fast_path=True)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    assert action_space.apply_action(
        battle,
        1,
        _first_legal_placement(battle, action_space, 1),
    )
    action_mask = action_space.legal_action_mask(battle, 0)[None, :]
    common = (
        action_mask,
        np.asarray([action_space.no_op_action], dtype=np.int64),
        np.zeros((1,), dtype=np.float32),
        np.ones((1,), dtype=np.bool_),
        torch.device("cpu"),
    )
    source_inputs = _stack_step_inputs([source_builder.build(battle, 0)], *common)
    target_inputs = _stack_step_inputs([target_builder.build(battle, 0)], *common)
    with torch.no_grad():
        source_output = source(source_inputs)
        target_output = target(target_inputs)
    assert torch.equal(source_output.joint_logits, target_output.joint_logits)
    assert torch.equal(source_output.values, target_output.values)
    assert torch.equal(
        source_output.opponent_hand_logits,
        target_output.opponent_hand_logits,
    )
    assert torch.equal(source_output.opponent_elixir, target_output.opponent_elixir)
