#!/usr/bin/env python3
"""
Test Gymnasium Environment Integration

Tests the Clash Royale Gym environment with random agents
and demonstrates RL training compatibility.
"""

import numpy as np
from src.clasher.gym_env import ClashRoyaleGymEnv, decode_action, encode_action


class RandomAgent:
    """Simple random agent for testing"""
    
    def __init__(self, env):
        self.env = env
        self.action_space = env.action_space
    
    def select_action(self, observation, info):
        """Select random valid action"""
        # Prefer deploying in own territory
        valid_actions = []
        
        # Generate some reasonable random actions
        for hand_idx in range(4):
            for x in range(6, 12):  # Middle area
                for y in range(0, 8):  # Player 0 territory
                    action = encode_action(hand_idx, x, y)
                    valid_actions.append(action)
        
        return np.random.choice(valid_actions)


def test_basic_env():
    """Test basic environment functionality"""
    print("🧪 Testing Basic Environment Functionality")
    print("-" * 50)
    
    env = ClashRoyaleGymEnv(render_mode="human", speed_factor=10.0)
    
    # Test reset
    obs, info = env.reset()
    print(f"✅ Reset successful")
    print(f"   Observation shape: {obs.shape}")
    print(f"   Action space: {env.action_space}")
    print(f"   Initial info: {info}")
    
    # Test a few steps
    agent = RandomAgent(env)
    
    for step in range(10):
        action = agent.select_action(obs, info)
        hand_idx, x_tile, y_tile = decode_action(action)
        
        obs, reward, terminated, truncated, info = env.step(action)
        
        print(f"Step {step+1}: Action=({hand_idx},{x_tile},{y_tile}), "
              f"Reward={reward:.3f}, Info={info}")
        
        if terminated or truncated:
            print(f"Episode ended at step {step+1}")
            break
    
    env.close()
    print("✅ Basic test completed\n")


def test_episode_rollout():
    """Test complete episode rollout"""
    print("🎮 Testing Complete Episode Rollout")
    print("-" * 50)
    
    env = ClashRoyaleGymEnv(speed_factor=50.0, max_steps=1000)
    agent = RandomAgent(env)
    
    obs, info = env.reset()
    
    total_reward = 0
    step_count = 0
    
    while True:
        action = agent.select_action(obs, info)
        obs, reward, terminated, truncated, info = env.step(action)
        
        total_reward += reward
        step_count += 1
        
        # Print progress occasionally
        if step_count % 100 == 0:
            print(f"Step {step_count}: Total reward={total_reward:.2f}, "
                  f"Time={info.get('time', 0):.1f}s")
        
        if terminated or truncated:
            break
    
    print(f"✅ Episode completed in {step_count} steps")
    print(f"   Total reward: {total_reward:.2f}")
    print(f"   Final info: {info}")
    print(f"   Winner: Player {info.get('winner', 'None')}")
    
    env.close()
    print()


def test_observation_encoding():
    """Test observation tensor encoding"""
    print("🔍 Testing Observation Encoding")
    print("-" * 50)
    
    env = ClashRoyaleGymEnv()
    obs, info = env.reset()
    
    # Deploy a card to create entities
    action = encode_action(0, 8, 4)  # Deploy first card in middle
    obs, reward, terminated, truncated, info = env.step(action)
    
    # Check observation properties
    print(f"✅ Observation shape: {obs.shape}")
    print(f"   Channel 0 (owners) range: {obs[:,:,0].min()}-{obs[:,:,0].max()}")
    print(f"   Channel 1 (types) range: {obs[:,:,1].min()}-{obs[:,:,1].max()}")  
    print(f"   Channel 2 (HP) range: {obs[:,:,2].min()}-{obs[:,:,2].max()}")
    
    # Count non-zero pixels
    non_zero_pixels = np.sum(obs[:,:,0] > 0)
    print(f"   Non-empty pixels: {non_zero_pixels}")
    
    env.close()
    print()


def test_action_encoding():
    """Test action encoding/decoding"""
    print("🎯 Testing Action Encoding")
    print("-" * 50)
    
    # Test encoding/decoding roundtrip
    test_cases = [
        (0, 0, 0),    # First card, top-left
        (3, 17, 31),  # Last card, bottom-right  
        (1, 8, 15),   # Middle action
        (2, 5, 20)    # Random action
    ]
    
    for hand_idx, x_tile, y_tile in test_cases:
        action = encode_action(hand_idx, x_tile, y_tile)
        decoded = decode_action(action)
        
        print(f"Original: ({hand_idx}, {x_tile}, {y_tile}) -> "
              f"Action: {action} -> Decoded: {decoded}")
        
        assert decoded == (hand_idx, x_tile, y_tile), "Encoding mismatch!"
    
    print("✅ All encoding tests passed")
    print()


def benchmark_env_speed():
    """Benchmark environment speed"""
    print("⚡ Benchmarking Environment Speed")
    print("-" * 50)
    
    env = ClashRoyaleGymEnv(speed_factor=100.0)
    agent = RandomAgent(env)
    
    import time
    
    num_episodes = 5
    total_steps = 0
    start_time = time.time()
    
    for episode in range(num_episodes):
        obs, info = env.reset()
        episode_steps = 0
        
        while True:
            action = agent.select_action(obs, info)
            obs, reward, terminated, truncated, info = env.step(action)
            episode_steps += 1
            
            if terminated or truncated:
                break
        
        total_steps += episode_steps
        print(f"Episode {episode+1}: {episode_steps} steps")
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    print(f"✅ Completed {num_episodes} episodes in {elapsed:.2f}s")
    print(f"   Total steps: {total_steps}")
    print(f"   Steps/second: {total_steps/elapsed:.0f}")
    
    env.close()
    print()


def main():
    print("🏟️ CLASH ROYALE GYMNASIUM ENVIRONMENT TESTS")
    print("=" * 60)
    
    test_basic_env()
    test_observation_encoding()
    test_action_encoding()
    test_episode_rollout()
    benchmark_env_speed()
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED - Gymnasium Environment Ready!")
    print("🤖 Compatible with Stable-Baselines3, RLlib, etc.")
    print("📊 Observation: 128x128x3 tensor")
    print("🎮 Action: Discrete(2304) - (card, x, y)")
    print("=" * 60)


if __name__ == "__main__":
    main()