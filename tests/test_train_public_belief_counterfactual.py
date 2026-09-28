from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import torch

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.model import ClasherPolicy, PolicyOutput
from clasher.rl.strategy_bots import BALANCED, StrategyBot
from scripts.pretrain_public_cycle_belief import verify_policy_equivalence
from scripts.train_public_belief_counterfactual import (
    _single_actor_inputs,
    action_type,
    candidate_actions_from_output,
    counterfactual_action_scores,
    counterfactual_target_distribution,
    counterfactual_win_prob_p0,
)


def _battle_signature(battle: BattleState) -> tuple[object, ...]:
    return (
        battle.tick,
        battle.time,
        battle.game_over,
        battle.winner,
        battle.rng.getstate(),
        tuple(
            (
                player.elixir,
                tuple(player.hand),
                tuple(player.deck),
                tuple(player.cycle_queue),
                player.left_tower_hp,
                player.right_tower_hp,
                player.king_tower_hp,
            )
            for player in battle.players
        ),
        tuple(
            (
                entity.id,
                entity.player_id,
                entity.card_stats.name,
                entity.position.x,
                entity.position.y,
                entity.hitpoints,
                entity.is_alive,
            )
            for entity in battle.entities.values()
        ),
    )


def _policy_output(location_logits: torch.Tensor) -> PolicyOutput:
    return PolicyOutput(
        joint_logits=torch.zeros((1, 1, NUM_HAND_SLOTS * NUM_TILES + 2)),
        values=torch.zeros((1, 1)),
        opponent_hand_logits=torch.zeros((1, 1, 1)),
        opponent_elixir=torch.zeros((1, 1)),
        next_state=(torch.zeros((1, 1)), torch.zeros((1, 1))),
        action_type_logits=torch.zeros((1, 1, NUM_HAND_SLOTS + 2)),
        location_logits=location_logits,
    )


def test_candidate_actions_choose_one_best_legal_location_per_type() -> None:
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    mask = np.zeros(action_space.num_actions, dtype=np.bool_)
    mask[2] = True
    mask[7] = True
    mask[NUM_TILES + 4] = True
    mask[action_space.no_op_action] = True
    logits = torch.zeros((1, 1, NUM_HAND_SLOTS, NUM_TILES))
    logits[0, 0, 0, 2] = 1.0
    logits[0, 0, 0, 7] = 3.0
    logits[0, 0, 1, 4] = 2.0

    candidates = candidate_actions_from_output(
        _policy_output(logits),
        mask,
        action_space,
    )

    assert candidates == {
        0: 7,
        1: NUM_TILES + 4,
        NUM_HAND_SLOTS: action_space.no_op_action,
    }
    assert all(mask[action] for action in candidates.values())
    assert {
        target: action_type(action, action_space)
        for target, action in candidates.items()
    } == {target: target for target in candidates}


def test_counterfactual_scores_are_exact_and_do_not_mutate_root() -> None:
    battle = BattleState(fast_path=True)
    battle.rng.seed(901)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    before = _battle_signature(battle)
    mask = action_space.legal_action_mask(battle, 0, fast_path=True)
    placement = int(np.flatnonzero(mask[: action_space.no_op_action])[0])
    candidates = {
        action_type(placement, action_space): placement,
        NUM_HAND_SLOTS: action_space.no_op_action,
    }

    first = counterfactual_action_scores(
        battle,
        player_id=0,
        opponent_action=action_space.no_op_action,
        candidate_actions=candidates,
        action_space=action_space,
        horizon_ticks=8,
    )
    second = counterfactual_action_scores(
        battle,
        player_id=0,
        opponent_action=action_space.no_op_action,
        candidate_actions=candidates,
        action_space=action_space,
        horizon_ticks=8,
    )

    np.testing.assert_array_equal(first, second)
    assert np.isfinite(first[list(candidates)]).all()
    assert np.isnan(np.delete(first, list(candidates))).all()
    assert _battle_signature(battle) == before


def test_counterfactual_value_balances_deployed_material_with_spent_elixir() -> None:
    battle = BattleState(fast_path=True)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    mask = action_space.legal_action_mask(battle, 0, fast_path=True)
    placement = int(np.flatnonzero(mask[: action_space.no_op_action])[0])
    deployed = battle.clone()
    before = counterfactual_win_prob_p0(battle)

    assert action_space.apply_action(deployed, 0, placement)
    after = counterfactual_win_prob_p0(deployed)

    # Material appearing on board should not be treated as free value at the
    # root. Minor differences are permitted because card intrinsic value is an
    # intentionally smoothed estimate rather than a card-name table.
    assert abs(after - before) < 0.01


def test_soft_counterfactual_targets_ignore_invalid_candidates() -> None:
    scores = np.asarray(
        [[0.50, np.nan, 0.51, 0.49, np.nan, np.nan]],
        dtype=np.float64,
    )

    probabilities = counterfactual_target_distribution(
        scores,
        temperature=0.005,
        device=torch.device("cpu"),
    )

    torch.testing.assert_close(probabilities.sum(dim=-1), torch.ones(1))
    assert probabilities[0, 2] > probabilities[0, 0] > probabilities[0, 3]
    assert probabilities[0, 1] == 0.0


def test_counterfactual_scores_support_canonical_player_one_actions() -> None:
    battle = BattleState(fast_path=True)
    battle.rng.seed(902)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    mask = action_space.legal_action_mask(battle, 1, fast_path=True)
    placement = int(np.flatnonzero(mask[: action_space.no_op_action])[0])
    target = action_type(placement, action_space)

    scores = counterfactual_action_scores(
        battle,
        player_id=1,
        opponent_action=action_space.no_op_action,
        candidate_actions={target: placement},
        action_space=action_space,
        horizon_ticks=4,
    )

    assert np.isfinite(scores[target])


def test_closed_loop_counterfactual_is_deterministic_and_nonmutating() -> None:
    checkpoint = Path(
        "checkpoints/public_cycle_belief_relational_seed1049001/"
        "policy_v2_update_000040_belief.pt"
    )
    loaded = load_policy_checkpoint(
        checkpoint,
        device=torch.device("cpu"),
        decks_path=Path("decks.json"),
    )
    battle = BattleState(fast_path=True)
    battle.rng.seed(903)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    mask = action_space.legal_action_mask(battle, 0, fast_path=True)
    placement = int(np.flatnonzero(mask[: action_space.no_op_action])[0])
    candidates = {
        action_type(placement, action_space): placement,
        NUM_HAND_SLOTS: action_space.no_op_action,
    }
    inputs = _single_actor_inputs(
        loaded.builder.build_actor(battle, 0),
        mask,
        action_space.no_op_action,
        0.0,
        True,
        torch.device("cpu"),
    )
    with torch.no_grad():
        _, _, _, next_state, _ = loaded.model.act(
            inputs,
            loaded.model.initial_state(1),
            deterministic=True,
        )
    before = _battle_signature(battle)
    kwargs = {
        "player_id": 0,
        "opponent_action": action_space.no_op_action,
        "candidate_actions": candidates,
        "action_space": action_space,
        "horizon_ticks": 16,
        "continuation_model": loaded.model,
        "continuation_builder": loaded.builder,
        "continuation_state": next_state,
        "continuation_opponent": StrategyBot(BALANCED),
        "decision_interval_ticks": 8,
        "device": torch.device("cpu"),
    }

    first = counterfactual_action_scores(battle, **kwargs)
    second = counterfactual_action_scores(battle, **kwargs)

    np.testing.assert_array_equal(first, second)
    assert _battle_signature(battle) == before


def test_counterfactual_rejects_invalid_horizon_without_mutation() -> None:
    battle = BattleState(fast_path=True)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    before = _battle_signature(battle)

    with np.testing.assert_raises_regex(ValueError, "horizon"):
        counterfactual_action_scores(
            battle,
            player_id=0,
            opponent_action=action_space.no_op_action,
            candidate_actions={NUM_HAND_SLOTS: action_space.no_op_action},
            action_space=action_space,
            horizon_ticks=0,
        )

    assert _battle_signature(battle) == before


def test_zero_relational_heads_make_all_action_contexts_behavior_exact() -> None:
    checkpoint = Path(
        "checkpoints/public_cycle_belief_relational_seed1049001/"
        "policy_v2_update_000040_belief.pt"
    )
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    loaded = load_policy_checkpoint(
        checkpoint,
        device=torch.device("cpu"),
        decks_path=Path("decks.json"),
    )
    for context in ("belief-board-add", "belief-board-interaction"):
        config = replace(
            loaded.model.config,
            public_belief_action_context=context,
        )
        model = ClasherPolicy(config, loaded.builder.card_stat_features)
        model.load_state_dict(payload["model_state_dict"])
        result = verify_policy_equivalence(payload, model, loaded.builder)
        assert result["bit_exact"] is True


def test_tactical_gate_restores_parent_policy_without_enemy_pressure() -> None:
    parent_path = Path(
        "checkpoints/public_cycle_belief_relational_seed1049001/"
        "policy_v2_update_000040_belief.pt"
    )
    candidate_path = Path(
        "checkpoints/public_belief_cf_sweep_board-interaction_lr00005_seed1049101/"
        "policy_v2_update_000040_counterfactual.pt"
    )
    parent = load_policy_checkpoint(
        parent_path,
        device=torch.device("cpu"),
        decks_path=Path("decks.json"),
    )
    candidate_payload = torch.load(
        candidate_path,
        map_location="cpu",
        weights_only=False,
    )
    config = replace(
        parent.model.config,
        public_belief_action_context="belief-board-interaction",
        public_belief_enemy_y_gate=0.65,
    )
    candidate = ClasherPolicy(config, parent.builder.card_stat_features)
    candidate.load_state_dict(candidate_payload["model_state_dict"])
    battle = BattleState(fast_path=True)
    observation = parent.builder.build_actor(battle, 0)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    mask = action_space.legal_action_mask(battle, 0, fast_path=True)
    inputs = _single_actor_inputs(
        observation,
        mask,
        action_space.no_op_action,
        0.0,
        True,
        torch.device("cpu"),
    )
    with torch.no_grad():
        parent_output = parent.model(inputs, parent.model.initial_state(1))
        candidate_output = candidate(inputs, candidate.initial_state(1))
    torch.testing.assert_close(
        candidate_output.joint_logits,
        parent_output.joint_logits,
        rtol=0.0,
        atol=1e-5,
    )
    assert candidate_output.joint_logits.argmax().item() == (
        parent_output.joint_logits.argmax().item()
    )
