import time
from typing import Dict, Any, Optional, Callable
import json

from .battle import BattleState
from .arena import Position


class BattleEngine:
    """Main engine for running Clash Royale battles"""
    
    def __init__(self, data_file: str = "gamedata.json"):
        self.data_file = data_file
        self.battle: Optional[BattleState] = None
        
    def create_battle(self) -> BattleState:
        """Create a new battle instance"""
        self.battle = BattleState()
        self.battle.card_loader.data_file = self.data_file
        self.battle.card_loader.load_cards()
        return self.battle
    
    def run_battle(self, 
                   max_ticks: int = 9090,  # ~5 minutes at 30 FPS
                   speed_factor: float = 1.0,
                   on_tick: Optional[Callable[[BattleState], None]] = None) -> Dict[str, Any]:
        """Run a complete battle to completion"""
        
        if not self.battle:
            self.create_battle()
        
        start_time = time.time()
        
        for _ in range(max_ticks):
            if self.battle.game_over:
                break
                
            self.battle.step(speed_factor)
            
            if on_tick:
                on_tick(self.battle)
        
        end_time = time.time()
        
        return {
            "result": self.battle.get_state_summary(),
            "duration_seconds": end_time - start_time,
            "ticks_per_second": self.battle.tick / (end_time - start_time) if end_time > start_time else 0
        }
    
    def run_headless(self, speed_factor: float = 10.0) -> Dict[str, Any]:
        """Run battle in headless mode for maximum speed"""
        return self.run_battle(speed_factor=speed_factor)
    
    def simulate_action(self, player_id: int, card_name: str, x: float, y: float) -> bool:
        """Simulate a player action (card deployment)"""
        if not self.battle:
            return False
        
        position = Position(x, y)
        return self.battle.deploy_card(player_id, card_name, position)
    
    def get_battle_state(self) -> Optional[Dict[str, Any]]:
        """Get current battle state as dict"""
        if not self.battle:
            return None
        
        return {
            "time": self.battle.time,
            "tick": self.battle.tick,
            "entities": {
                eid: {
                    "id": entity.id,
                    "type": entity.__class__.__name__,
                    "position": {"x": entity.position.x, "y": entity.position.y},
                    "player_id": entity.player_id,
                    "hitpoints": entity.hitpoints,
                    "max_hitpoints": entity.max_hitpoints,
                    "is_alive": entity.is_alive
                }
                for eid, entity in self.battle.entities.items()
            },
            "players": [
                {
                    "player_id": p.player_id,
                    "elixir": p.elixir,
                    "hand": p.hand,
                    "king_tower_hp": p.king_tower_hp,
                    "left_tower_hp": p.left_tower_hp,
                    "right_tower_hp": p.right_tower_hp,
                    "crowns": p.get_crown_count()
                }
                for p in self.battle.players
            ],
            "game_over": self.battle.game_over,
            "winner": self.battle.winner,
            "double_elixir": self.battle.double_elixir,
            "triple_elixir": self.battle.triple_elixir,
            "overtime": self.battle.overtime
        }
    
    def save_replay(self, filename: str) -> None:
        """Save battle replay to JSON file"""
        state = self.get_battle_state()
        if state:
            with open(filename, 'w') as f:
                json.dump(state, f, indent=2)