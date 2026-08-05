import copy
from collections import deque

import numpy as np
import pytest

import gymnasium as gym

import clasher.rl.gym_env as gym_env_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from scripts.audit_enabled_mirror import (
    _assert_failed_env_actions_are_joint_conflicts,
    run_env_parity,
)


def test_gym_registration_is_explicitly_idempotent(monkeypatch):
    attempted = []

    def unexpected_register(**kwargs):
        attempted.append(kwargs)

    monkeypatch.setattr(gym_env_module, "register", unexpected_register)
    gym_env_module.register_gym_envs()

    assert attempted == []
    assert gym.spec("clasher-selfplay-v0").entry_point == (
        "clasher.rl.gym_env:ClasherSelfPlayGymEnv"
    )
    assert gym.spec("clasher-selfplay-xyz-v0").kwargs == {
        "action_mode": "xyz",
    }


def test_gym_env_reset_and_step_shapes_flat_dict():
    env = gym.make(
        "clasher-selfplay-v0",
        seed=3,
        decks_path="decks.json",
        decision_interval_ticks=8,
        max_ticks=256,
    )
    obs, info = env.reset(seed=11)

    assert "board" in obs and "hud" in obs
    assert obs["board"].shape == (33, 32, 18)
    assert obs["board"].dtype == np.float32
    assert obs["hud"].dtype == np.float32
    assert info["action_mask"].shape[0] == env.action_space.n
    assert info["action_mask_flat"].shape[0] == env.action_space.n

    legal = np.flatnonzero(info["action_mask"])
    assert legal.size > 0

    action = int(legal[0])
    next_obs, reward, terminated, truncated, next_info = env.step(action)
    assert next_obs["board"].shape == (33, 32, 18)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert next_info["action_mask"].shape[0] == env.action_space.n
    assert isinstance(next_info["agent_action_valid"], bool)
    assert isinstance(next_info["agent_action_flat"], int)

    env.close()


def test_gym_env_xyz_mode_dict_obs():
    env = gym.make(
        "clasher-selfplay-xyz-v0",
        seed=5,
        decks_path="decks.json",
        decision_interval_ticks=8,
        max_ticks=256,
    )
    obs, info = env.reset(seed=19)
    assert "board" in obs and "hud" in obs
    assert obs["board"].shape == (33, 32, 18)
    assert info["action_mask"].shape == (18, 32, 6)

    # explicit no-op in xyz format: slot=4
    action = np.array([0, 0, 4], dtype=np.int64)
    next_obs, reward, terminated, truncated, next_info = env.step(action)
    assert next_obs["board"].shape == (33, 32, 18)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert next_info["action_mask_flat"].ndim == 1

    env.close()


def test_reset_seed_replays_decks_and_initial_observation():
    env = gym.make("clasher-selfplay-v0", seed=2, decks_path="decks.json")
    first_obs, _ = env.reset(seed=101)
    # Advance both the opponent RNG and the simulator RNG before reseeding.
    for _ in range(3):
        env.step(env.unwrapped._env.action_space.no_op_action)
    second_obs, _ = env.reset(seed=101)

    np.testing.assert_array_equal(first_obs["board"], second_obs["board"])
    np.testing.assert_array_equal(first_obs["hud"], second_obs["hud"])
    env.close()


def test_enabled_legal_rollout_matches_both_production_engine_paths():
    run_env_parity(
        start_seed=701,
        seeds=1,
        decisions=16,
        decision_interval=4,
        max_ticks=128,
        mirror_match=False,
    )


def test_env_parity_verifier_allows_only_reproducible_joint_action_conflicts():
    battle = BattleState()
    red_left = next(
        entity
        for entity in battle.entities.values()
        if (
            entity.player_id == 1
            and getattr(entity, "_crown_tower_slot", None) == "left"
        )
    )
    red_left.take_damage(red_left.hitpoints)
    battle._update_tower_hp()
    for player in battle.players:
        player.elixir = 10.0
        player.hand = ["Cannon"]
        player.deck = ["Cannon"]
        player.cycle_queue = deque()

    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    actions = {
        player_id: action_space.encode_action(
            0,
            6,
            18,
            player_id,
        )
        for player_id in (0, 1)
    }
    execution = copy.deepcopy(battle)
    action_success = {
        1: action_space.apply_action(execution, 1, actions[1]),
        0: action_space.apply_action(execution, 0, actions[0]),
    }

    assert action_success == {1: True, 0: False}
    _assert_failed_env_actions_are_joint_conflicts(
        battle,
        action_space,
        actions,
        action_success,
        "joint placement",
    )

    invalid_actions = {
        0: action_space.encode_action(0, 3, 6, 0),
        1: action_space.no_op_action,
    }
    with pytest.raises(AssertionError, match="failed in isolation"):
        _assert_failed_env_actions_are_joint_conflicts(
            battle,
            action_space,
            invalid_actions,
            {0: False, 1: True},
            "stale mask",
        )
