from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import msgspec
import json
from pathlib import Path

from .battle import BattleState
from .arena import Position


@dataclass
class TickSnapshot:
    """Snapshot of battle state at a specific tick"""
    tick: int
    time: float
    entities: Dict[int, Dict[str, Any]]
    players: List[Dict[str, Any]]
    events: List[str]


class ReplayRecorder:
    """Records battle states for replay/analysis"""
    
    def __init__(self):
        self.snapshots: List[TickSnapshot] = []
        self.events: List[str] = []
        
    def record_tick(self, battle_state: BattleState) -> None:
        """Record current battle state"""
        entities_data = {}
        for eid, entity in battle_state.entities.items():
            entities_data[eid] = {
                "type": entity.__class__.__name__,
                "position": {"x": entity.position.x, "y": entity.position.y},
                "player_id": entity.player_id,
                "hitpoints": entity.hitpoints,
                "max_hitpoints": entity.max_hitpoints,
                "is_alive": entity.is_alive,
                "damage": entity.damage,
                "range": entity.range
            }
        
        players_data = []
        for player in battle_state.players:
            players_data.append({
                "elixir": player.elixir,
                "hand": player.hand.copy(),
                "king_tower_hp": player.king_tower_hp,
                "left_tower_hp": player.left_tower_hp,
                "right_tower_hp": player.right_tower_hp,
                "crowns": player.get_crown_count()
            })
        
        snapshot = TickSnapshot(
            tick=battle_state.tick,
            time=battle_state.time,
            entities=entities_data,
            players=players_data,
            events=self.events.copy()
        )
        
        self.snapshots.append(snapshot)
        self.events.clear()
    
    def record_event(self, event: str) -> None:
        """Record a battle event"""
        self.events.append(event)
    
    def save_msgspec(self, filename: str) -> None:
        """Save replay using msgspec for speed"""
        data = [asdict(snapshot) for snapshot in self.snapshots]
        encoded = msgspec.json.encode(data)
        
        with open(filename, 'wb') as f:
            f.write(encoded)
    
    def save_json(self, filename: str) -> None:
        """Save replay as readable JSON"""
        data = [asdict(snapshot) for snapshot in self.snapshots]
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_msgspec(self, filename: str) -> List[TickSnapshot]:
        """Load replay from msgspec file"""
        with open(filename, 'rb') as f:
            data = msgspec.json.decode(f.read())
        
        self.snapshots = [
            TickSnapshot(**snapshot) for snapshot in data
        ]
        return self.snapshots
    
    def get_stats(self) -> Dict[str, Any]:
        """Get replay statistics"""
        if not self.snapshots:
            return {}
        
        final_snapshot = self.snapshots[-1]
        
        return {
            "total_ticks": len(self.snapshots),
            "duration_seconds": final_snapshot.time,
            "final_state": {
                "entities": len(final_snapshot.entities),
                "player0_crowns": final_snapshot.players[0]["crowns"],
                "player1_crowns": final_snapshot.players[1]["crowns"],
                "winner": None  # TODO: Determine from crown count
            }
        }


class TurboEngine:
    """High-performance battle engine for mass simulation"""
    
    def __init__(self, data_file: str = "gamedata.json"):
        self.data_file = data_file
        self.recorder: Optional[ReplayRecorder] = None
        
    def run_batch(self, 
                  num_battles: int, 
                  speed_factor: float = 100.0,
                  record_replays: bool = False) -> List[Dict[str, Any]]:
        """Run multiple battles in sequence"""
        results = []
        
        for i in range(num_battles):
            if record_replays:
                self.recorder = ReplayRecorder()
            
            from .engine import BattleEngine
            engine = BattleEngine(self.data_file)
            result = engine.run_headless(speed_factor)
            
            if self.recorder:
                # Save replay
                replay_file = f"replay_{i:04d}.msgpack"
                self.recorder.save_msgspec(replay_file)
                result["replay_file"] = replay_file
            
            results.append(result)
        
        return results
    
    def benchmark(self, duration_seconds: int = 10) -> Dict[str, float]:
        """Benchmark engine performance"""
        import time
        from .engine import BattleEngine
        
        battles_completed = 0
        total_ticks = 0
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            engine = BattleEngine(self.data_file)
            result = engine.run_headless(speed_factor=1000.0)
            
            battles_completed += 1
            # Estimate ticks from duration and tick rate
            total_ticks += int(result["result"]["time"] / 0.033)
        
        elapsed = time.time() - start_time
        
        return {
            "battles_per_second": battles_completed / elapsed,
            "ticks_per_second": total_ticks / elapsed,
            "total_battles": battles_completed,
            "elapsed_seconds": elapsed
        }