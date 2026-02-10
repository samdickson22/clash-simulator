"""Tests for the Gymnasium environment."""
import pytest
import numpy as np


def test_env_creation():
    import clasher  # triggers registration
    import gymnasium as gym
    env = gym.make("ClashRoyale-v0")
    assert env is not None
    env.close()


def test_reset_returns_valid_obs():
    import clasher
    import gymnasium as gym
    env = gym.make("ClashRoyale-v0")
    obs, info = env.reset(seed=42)
    assert obs.shape == env.observation_space.shape
    assert env.observation_space.contains(obs)
    env.close()


def test_step_no_op():
    import clasher
    import gymnasium as gym
    env = gym.make("ClashRoyale-v0")
    obs, info = env.reset(seed=42)
    from clasher.gym_env import NO_OP
    obs2, reward, terminated, truncated, info2 = env.step(NO_OP)
    assert obs2.shape == env.observation_space.shape
    assert isinstance(reward, float)
    env.close()


def test_step_deploy_card():
    import clasher
    import gymnasium as gym
    env = gym.make("ClashRoyale-v0")
    obs, info = env.reset(seed=42)
    # Action: card 0 at grid position (9, 10)
    action = 0 * (18 * 32) + 9 * 32 + 10
    obs2, reward, terminated, truncated, info2 = env.step(action)
    assert obs2.shape == env.observation_space.shape
    env.close()


def test_full_episode():
    import clasher
    import gymnasium as gym
    env = gym.make("ClashRoyale-v0")
    obs, info = env.reset(seed=42)
    from clasher.gym_env import NO_OP
    
    steps = 0
    done = False
    while not done and steps < 2000:
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        steps += 1
    
    # Should complete within reasonable steps
    assert steps > 0
    env.close()
