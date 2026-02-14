import numpy as np

import gymnasium as gym

import clasher.rl.gym_env  # noqa: F401 - triggers env registration


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
    assert obs["board"].shape == (15, 32, 18)
    assert obs["board"].dtype == np.float32
    assert obs["hud"].dtype == np.float32
    assert info["action_mask"].shape[0] == env.action_space.n
    assert info["action_mask_flat"].shape[0] == env.action_space.n

    legal = np.flatnonzero(info["action_mask"])
    assert legal.size > 0

    action = int(legal[0])
    next_obs, reward, terminated, truncated, next_info = env.step(action)
    assert next_obs["board"].shape == (15, 32, 18)
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
    assert obs["board"].shape == (15, 32, 18)
    assert info["action_mask"].shape == (18, 32, 5)

    # explicit no-op in xyz format: slot=4
    action = np.array([0, 0, 4], dtype=np.int64)
    next_obs, reward, terminated, truncated, next_info = env.step(action)
    assert next_obs["board"].shape == (15, 32, 18)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert next_info["action_mask_flat"].ndim == 1

    env.close()
