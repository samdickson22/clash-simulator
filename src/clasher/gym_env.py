"""
Gymnasium Environment for Clash Royale Battle Engine

Following plan.md Phase 8 specifications:
- Observation: 128x128x3 tensor (owner mask, troop type, HP)
- Action: (hand_idx, x_tile, y_tile) encoded as Discrete(2304)
- Compatible with Stable-Baselines and RLlib
"""

from typing import Dict, Any, Optional, Tuple
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from .engine import BattleEngine
from .arena import Position
from .battle import BattleState


class ClashRoyaleGymEnv(gym.Env):
    """Gymnasium environment for Clash Royale battles"""
    
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 30}
    
    def __init__(self, 
                 render_mode: Optional[str] = None,
                 data_file: str = "gamedata.json",
                 max_steps: int = 9090,  # ~5 minutes
                 speed_factor: float = 1.0):
        
        super().__init__()
        
        self.render_mode = render_mode
        self.data_file = data_file
        self.max_steps = max_steps
        self.speed_factor = speed_factor
        
        # Observation space: 128x128x3 grid
        # Channel 0: Owner mask (0=empty, 1=player0, 2=player1)  
        # Channel 1: Troop type ID (0=empty, 1-100=troop types)
        # Channel 2: HP percentage (0-255)
        self.observation_space = spaces.Box(
            low=0, high=255, 
            shape=(128, 128, 3), 
            dtype=np.uint8
        )
        
        # Action space: Discrete(2304) = 4 cards * 18 x * 32 y  
        # Encoding: action = hand_idx * (18 * 32) + x_tile * 32 + y_tile
        self.action_space = spaces.Discrete(4 * 18 * 32)  # 2304 total actions
        
        # Internal state
        self.engine: Optional[BattleEngine] = None
        self.battle: Optional[BattleState] = None
        self.step_count = 0
        self.done = False
        
        # Card type mappings for observations
        self.card_type_ids = {
            "Knight": 1, "Archers": 2, "Arrows": 3, "Fireball": 4,
            "Giant": 5, "Musketeer": 6, "Mini_P.E.K.K.A": 7, "Wizard": 8,
            "Tower": 10, "KingTower": 11
        }
    
    def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
        """Reset environment to initial state"""
        super().reset(seed=seed)
        
        # Create new battle
        self.engine = BattleEngine(self.data_file)
        self.battle = self.engine.create_battle()
        self.step_count = 0
        self.done = False
        
        observation = self._get_observation()
        info = self._get_info()
        
        return observation, info
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Execute one environment step"""
        if self.done:
            raise RuntimeError("Environment is done, call reset()")
        
        # Decode action for 18x32 arena: action = hand_idx * (18 * 32) + x_tile * 32 + y_tile  
        hand_idx = action // (18 * 32)
        remainder = action % (18 * 32)
        x_tile = remainder // 32
        y_tile = remainder % 32
        
        # Clamp to valid ranges for 18x32 arena
        hand_idx = min(hand_idx, 3)
        x_tile = min(x_tile, 17)  # 0-17 for 18 tiles wide
        y_tile = min(y_tile, 31)  # 0-31 for 32 tiles tall
        
        # Execute action for player 0
        reward = 0.0
        if hand_idx < len(self.battle.players[0].hand):
            card_name = self.battle.players[0].hand[hand_idx]
            
            # Convert tile coordinates to world position
            world_pos = self.battle.arena.tile_to_world(x_tile, y_tile)
            
            # Try to deploy card
            if self.battle.deploy_card(0, card_name, world_pos):
                reward += 0.1  # Small reward for valid deployment
        
        # Step battle simulation
        self.battle.step(self.speed_factor)
        self.step_count += 1
        
        # Calculate reward
        reward += self._calculate_reward()
        
        # Check if done
        terminated = self.battle.game_over
        truncated = self.step_count >= self.max_steps
        self.done = terminated or truncated
        
        observation = self._get_observation()
        info = self._get_info()
        
        return observation, reward, terminated, truncated, info
    
    def _get_observation(self) -> np.ndarray:
        """Get current observation as 128x128x3 tensor"""
        obs = np.zeros((128, 128, 3), dtype=np.uint8)
        
        if not self.battle:
            return obs
        
        # Scale factor from world coordinates to observation grid for 18x32 arena
        scale_x = 128 / (self.battle.arena.width * self.battle.arena.tile_size)  # 18 tiles wide
        scale_y = 128 / (self.battle.arena.height * self.battle.arena.tile_size) # 32 tiles tall
        
        for entity in self.battle.entities.values():
            if not entity.is_alive:
                continue
            
            # Convert world position to observation coordinates
            obs_x = int(entity.position.x * scale_x)
            obs_y = int(entity.position.y * scale_y)
            
            # Clamp to valid range
            obs_x = np.clip(obs_x, 0, 127)
            obs_y = np.clip(obs_y, 0, 127)
            
            # Set observation values
            obs[obs_y, obs_x, 0] = entity.player_id + 1  # Owner (1 or 2)
            
            # Get troop type ID
            card_name = entity.card_stats.name
            type_id = self.card_type_ids.get(card_name, 99)  # Unknown = 99
            obs[obs_y, obs_x, 1] = min(type_id, 255)
            
            # HP percentage (0-255)
            hp_pct = entity.hitpoints / max(entity.max_hitpoints, 1)
            obs[obs_y, obs_x, 2] = int(hp_pct * 255)
        
        return obs
    
    def _calculate_reward(self) -> float:
        """Calculate reward based on battle state"""
        if not self.battle:
            return 0.0
        
        reward = 0.0
        
        # Reward for crown count difference
        p0_crowns = self.battle.players[0].get_crown_count()
        p1_crowns = self.battle.players[1].get_crown_count()
        crown_diff = p0_crowns - p1_crowns
        reward += crown_diff * 10.0  # 10 points per crown advantage
        
        # Large reward for winning
        if self.battle.game_over:
            if self.battle.winner == 0:
                reward += 100.0  # Win bonus
            elif self.battle.winner == 1:
                reward -= 100.0  # Loss penalty
            # Draw = 0 additional reward
        
        # Small reward for tower damage
        p0_tower_hp = (self.battle.players[0].king_tower_hp + 
                      self.battle.players[0].left_tower_hp + 
                      self.battle.players[0].right_tower_hp)
        p1_tower_hp = (self.battle.players[1].king_tower_hp + 
                      self.battle.players[1].left_tower_hp + 
                      self.battle.players[1].right_tower_hp)
        
        # Reward for enemy damage, penalty for own damage
        max_hp = 4008 + 1400 + 1400  # King + 2 princess towers
        damage_to_enemy = max_hp - p1_tower_hp
        damage_to_self = max_hp - p0_tower_hp
        
        reward += (damage_to_enemy - damage_to_self) * 0.001  # Small scaling
        
        return reward
    
    def _get_info(self) -> Dict[str, Any]:
        """Get info dictionary"""
        info = {"step": self.step_count}
        
        if self.battle:
            info.update({
                "time": self.battle.time,
                "elixir": self.battle.players[0].elixir,
                "entities": len(self.battle.entities),
                "p0_crowns": self.battle.players[0].get_crown_count(),
                "p1_crowns": self.battle.players[1].get_crown_count(),
                "game_over": self.battle.game_over,
                "winner": self.battle.winner
            })
        
        return info
    
    def render(self) -> Optional[np.ndarray]:
        """Render environment (basic implementation)"""
        if self.render_mode == "rgb_array":
            return self._get_observation()
        elif self.render_mode == "human":
            print(f"Step {self.step_count}: {self._get_info()}")
        return None
    
    def close(self):
        """Clean up environment"""
        self.engine = None
        self.battle = None


def decode_action(action: int) -> Tuple[int, int, int]:
    """Decode action integer to (hand_idx, x_tile, y_tile) for 18x32 arena"""
    hand_idx = action // (18 * 32)
    remainder = action % (18 * 32)
    x_tile = remainder // 32
    y_tile = remainder % 32
    return hand_idx, x_tile, y_tile


def encode_action(hand_idx: int, x_tile: int, y_tile: int) -> int:
    """Encode (hand_idx, x_tile, y_tile) to action integer for 18x32 arena"""
    return hand_idx * (18 * 32) + x_tile * 32 + y_tile