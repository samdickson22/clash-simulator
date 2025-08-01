"""
Optimized Battle Engine for RL Training

Combines the best patterns from C++ reference implementation with Python ML ecosystem:
- Fixed-timestep loop with configurable speed multiplier
- Efficient entity management with spatial indexing
- Lane-based combat system for strategic gameplay
- Headless mode for maximum training speed
- State serialization for replay analysis
"""

import time
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum
import json
from collections import defaultdict

from .arena import Position, TileGrid
from .data import CardDataLoader, CardStats


class Lane(Enum):
    LEFT = 0
    CENTER = 1 
    RIGHT = 2


class EntityType(Enum):
    KING_TOWER = "king_tower"
    QUEEN_TOWER = "queen_tower"
    TROOP = "troop"
    BUILDING = "building"
    PROJECTILE = "projectile"


@dataclass
class OptimizedEntity:
    """Lightweight entity optimized for high-speed simulation"""
    id: int
    entity_type: EntityType
    player_id: int
    lane: Lane
    
    # Position and movement
    x: float
    y: float
    speed: float = 0.0
    
    # Combat stats
    hitpoints: float
    max_hitpoints: float
    damage: float
    attack_range: float
    attack_speed: float  # attacks per second
    
    # State tracking
    target_id: Optional[int] = None
    attack_timer: float = 0.0
    is_alive: bool = True
    is_flying: bool = False
    can_attack_air: bool = True
    
    # Behavioral flags
    prioritize_buildings: bool = False
    
    def __post_init__(self):
        if self.max_hitpoints == 0:
            self.max_hitpoints = self.hitpoints
    
    def take_damage(self, damage: float) -> None:
        """Apply damage with efficiency optimizations"""
        self.hitpoints = max(0, self.hitpoints - damage)
        if self.hitpoints <= 0:
            self.is_alive = False
    
    def can_attack(self) -> bool:
        """Check if entity can attack (cooldown completed)"""
        return self.attack_timer <= 0 and self.is_alive
    
    def reset_attack_timer(self) -> None:
        """Reset attack cooldown"""
        self.attack_timer = 1.0 / self.attack_speed if self.attack_speed > 0 else 0
    
    def get_position(self) -> Position:
        """Get position as Position object (cached for performance)"""
        return Position(self.x, self.y)


@dataclass
class PlayerState:
    """Optimized player state for RL environments"""
    player_id: int
    elixir: float = 5.0
    max_elixir: float = 10.0
    
    # Tower health tracking
    king_tower_hp: float = 2534
    left_tower_hp: float = 1400  
    right_tower_hp: float = 1400
    
    # Card system (simplified for performance)
    hand: List[str] = field(default_factory=lambda: ["knight", "archers", "fireball", "giant"])
    deck: List[str] = field(default_factory=lambda: ["knight", "archers", "fireball", "giant"] * 2)
    next_card_idx: int = 4
    
    def regenerate_elixir(self, dt: float, base_rate: float = 2.8) -> None:
        """Efficient elixir regeneration"""
        if self.elixir < self.max_elixir:
            self.elixir = min(self.max_elixir, self.elixir + dt / base_rate)
    
    def get_crown_count(self) -> int:
        """Count destroyed towers"""
        count = 0
        if self.left_tower_hp <= 0:
            count += 1
        if self.right_tower_hp <= 0:
            count += 1
        if self.king_tower_hp <= 0:
            count += 3  # King tower counts as winning
        return count


class SpatialIndex:
    """Efficient spatial indexing for fast target acquisition"""
    
    def __init__(self, width: int = 32, height: int = 18):
        self.width = width
        self.height = height
        self.cell_size = 2  # 2x2 tile cells for indexing
        self.grid_width = width // self.cell_size
        self.grid_height = height // self.cell_size
        self.clear()
    
    def clear(self):
        """Clear spatial index"""
        self.cells: Dict[Tuple[int, int], Set[int]] = defaultdict(set)
        self.entity_positions: Dict[int, Tuple[int, int]] = {}
    
    def _get_cell(self, x: float, y: float) -> Tuple[int, int]:
        """Get grid cell for position"""
        cell_x = max(0, min(self.grid_width - 1, int(x // self.cell_size)))
        cell_y = max(0, min(self.grid_height - 1, int(y // self.cell_size)))
        return (cell_x, cell_y)
    
    def update_entity(self, entity_id: int, x: float, y: float):
        """Update entity position in spatial index"""
        new_cell = self._get_cell(x, y)
        
        # Remove from old cell
        if entity_id in self.entity_positions:
            old_cell = self.entity_positions[entity_id]
            self.cells[old_cell].discard(entity_id)
        
        # Add to new cell
        self.cells[new_cell].add(entity_id)
        self.entity_positions[entity_id] = new_cell
    
    def remove_entity(self, entity_id: int):
        """Remove entity from spatial index"""
        if entity_id in self.entity_positions:
            cell = self.entity_positions[entity_id]
            self.cells[cell].discard(entity_id)
            del self.entity_positions[entity_id]
    
    def get_nearby_entities(self, x: float, y: float, radius: float = 4.0) -> Set[int]:
        """Get entity IDs within radius"""
        nearby = set()
        center_cell = self._get_cell(x, y)
        search_radius = int(radius // self.cell_size) + 1
        
        for dx in range(-search_radius, search_radius + 1):
            for dy in range(-search_radius, search_radius + 1):
                cell_x = center_cell[0] + dx
                cell_y = center_cell[1] + dy
                if 0 <= cell_x < self.grid_width and 0 <= cell_y < self.grid_height:
                    nearby.update(self.cells[(cell_x, cell_y)])
        
        return nearby


@dataclass
class OptimizedBattleState:
    """High-performance battle state for RL training"""
    
    # Core state
    entities: Dict[int, OptimizedEntity] = field(default_factory=dict)
    players: List[PlayerState] = field(default_factory=lambda: [PlayerState(0), PlayerState(1)])
    spatial_index: SpatialIndex = field(default_factory=SpatialIndex)
    
    # Timing (optimized for speed)
    time: float = 0.0
    tick: int = 0
    dt: float = 0.033  # Base timestep
    
    # Game state flags
    double_elixir: bool = False
    triple_elixir: bool = False
    overtime: bool = False
    game_over: bool = False
    winner: Optional[int] = None
    
    # Performance tracking
    next_entity_id: int = 1
    headless: bool = True  # Default to headless for RL
    
    # Static tower positions (from C++ implementation)
    TOWER_POSITIONS = {
        # Player 0 towers (bottom)
        'p0_king': (19, 27),
        'p0_left': (6, 25), 
        'p0_right': (31, 25),
        # Player 1 towers (top)
        'p1_king': (19, 3),
        'p1_left': (6, 5),
        'p1_right': (31, 5)
    }
    
    def __post_init__(self):
        """Initialize optimized battle state"""
        self._create_towers()
    
    def _create_towers(self):
        """Create tower entities with fixed positions"""
        tower_stats = {
            'king': {'hp': 2534, 'damage': 109, 'range': 7.0, 'attack_speed': 0.8},
            'queen': {'hp': 1400, 'damage': 109, 'range': 7.0, 'attack_speed': 0.8}
        }
        
        positions = [
            ('p0_king', EntityType.KING_TOWER, 0, Lane.CENTER),
            ('p0_left', EntityType.QUEEN_TOWER, 0, Lane.LEFT),
            ('p0_right', EntityType.QUEEN_TOWER, 0, Lane.RIGHT),
            ('p1_king', EntityType.KING_TOWER, 1, Lane.CENTER),
            ('p1_left', EntityType.QUEEN_TOWER, 1, Lane.LEFT),
            ('p1_right', EntityType.QUEEN_TOWER, 1, Lane.RIGHT)
        ]
        
        for pos_key, entity_type, player_id, lane in positions:
            x, y = self.TOWER_POSITIONS[pos_key]
            stats = tower_stats['king' if entity_type == EntityType.KING_TOWER else 'queen']
            
            tower = OptimizedEntity(
                id=self.next_entity_id,
                entity_type=entity_type,
                player_id=player_id,
                lane=lane,
                x=float(x),
                y=float(y),
                hitpoints=stats['hp'],
                max_hitpoints=stats['hp'],
                damage=stats['damage'],
                attack_range=stats['range'],
                attack_speed=stats['attack_speed']
            )
            
            self.entities[tower.id] = tower
            self.spatial_index.update_entity(tower.id, tower.x, tower.y)
            self.next_entity_id += 1
    
    def step(self, speed_factor: float = 1.0) -> None:
        """Optimized battle step with configurable speed"""
        if self.game_over:
            return
        
        effective_dt = self.dt * speed_factor
        self.time += effective_dt
        self.tick += 1
        
        # Update elixir modes
        if self.time >= 120.0 and not self.double_elixir:
            self.double_elixir = True
        
        # Regenerate elixir efficiently
        elixir_rate = 0.9 if self.triple_elixir else (1.4 if self.double_elixir else 2.8)
        for player in self.players:
            player.regenerate_elixir(effective_dt, elixir_rate)
        
        # Update entities with spatial optimization
        dead_entities = []
        for entity in self.entities.values():
            if not entity.is_alive:
                dead_entities.append(entity.id)
                continue
            
            # Update attack timer
            if entity.attack_timer > 0:
                entity.attack_timer -= effective_dt
            
            # Combat logic (simplified for performance)
            if entity.can_attack():
                target = self._find_target_optimized(entity)
                if target:
                    self._execute_attack(entity, target)
        
        # Cleanup dead entities
        for entity_id in dead_entities:
            self._remove_entity(entity_id)
        
        # Check win conditions
        self._check_win_condition()
    
    def _find_target_optimized(self, attacker: OptimizedEntity) -> Optional[OptimizedEntity]:
        """Efficient target finding using spatial index"""
        nearby_ids = self.spatial_index.get_nearby_entities(
            attacker.x, attacker.y, attacker.attack_range + 2
        )
        
        best_target = None
        min_distance = float('inf')
        building_targets = []
        troop_targets = []
        
        for entity_id in nearby_ids:
            if entity_id not in self.entities:
                continue
            
            target = self.entities[entity_id]
            if (not target.is_alive or 
                target.player_id == attacker.player_id or
                (target.is_flying and not attacker.can_attack_air)):
                continue
            
            # Calculate distance efficiently
            dx = attacker.x - target.x
            dy = attacker.y - target.y
            distance = (dx * dx + dy * dy) ** 0.5
            
            if distance > attacker.attack_range:
                continue
            
            # Prioritize buildings for certain units (from C++ implementation)
            if (target.entity_type in [EntityType.KING_TOWER, EntityType.QUEEN_TOWER, EntityType.BUILDING]):
                building_targets.append((target, distance))
            else:
                troop_targets.append((target, distance))
        
        # Choose target based on priority
        targets = building_targets if (building_targets and attacker.prioritize_buildings) else (building_targets + troop_targets)
        
        for target, distance in targets:
            if distance < min_distance:
                min_distance = distance
                best_target = target
        
        return best_target
    
    def _execute_attack(self, attacker: OptimizedEntity, target: OptimizedEntity):
        """Execute attack with damage calculation"""
        base_damage = attacker.damage
        
        # Simple damage modifiers (can be expanded)
        multiplier = 1.0
        if (target.entity_type in [EntityType.KING_TOWER, EntityType.QUEEN_TOWER] and 
            attacker.entity_type == EntityType.TROOP):
            multiplier = 1.2  # Troops deal bonus damage to towers
        
        final_damage = base_damage * multiplier
        target.take_damage(final_damage)
        attacker.reset_attack_timer()
    
    def _remove_entity(self, entity_id: int):
        """Remove entity from battle state"""
        if entity_id in self.entities:
            self.spatial_index.remove_entity(entity_id)
            del self.entities[entity_id]
    
    def _check_win_condition(self):
        """Check for game end conditions"""
        if self.game_over:
            return
        
        # Check king tower destruction
        for player_id in [0, 1]:
            if self.players[player_id].king_tower_hp <= 0:
                self.game_over = True
                self.winner = 1 - player_id
                return
        
        # Timeout after 5 minutes
        if self.time >= 300.0:
            p0_health = sum([self.players[0].king_tower_hp, self.players[0].left_tower_hp, self.players[0].right_tower_hp])
            p1_health = sum([self.players[1].king_tower_hp, self.players[1].left_tower_hp, self.players[1].right_tower_hp])
            
            if p0_health > p1_health:
                self.winner = 0
            elif p1_health > p0_health:
                self.winner = 1
            else:
                self.winner = None  # Draw
            
            self.game_over = True
    
    def deploy_card(self, player_id: int, card_name: str, position: Position, lane: Lane = Lane.CENTER) -> bool:
        """Deploy a card with lane-based positioning"""
        player = self.players[player_id]
        
        # Simple card cost check (can be expanded)
        card_cost = 4  # Simplified for now
        if player.elixir < card_cost:
            return False
        
        # Create entity based on card
        entity = self._create_card_entity(card_name, player_id, position, lane)
        if entity:
            self.entities[entity.id] = entity
            self.spatial_index.update_entity(entity.id, entity.x, entity.y)
            player.elixir -= card_cost
            return True
        
        return False
    
    def _create_card_entity(self, card_name: str, player_id: int, position: Position, lane: Lane) -> Optional[OptimizedEntity]:
        """Create entity from card name"""
        # Simplified card creation (can be expanded with actual card data)
        card_stats = {
            'knight': {'hp': 1344, 'damage': 104, 'speed': 1.0, 'range': 1.0, 'attack_speed': 1.2},
            'archers': {'hp': 304, 'damage': 89, 'speed': 1.0, 'range': 5.0, 'attack_speed': 1.2},
            'giant': {'hp': 3275, 'damage': 211, 'speed': 0.5, 'range': 1.0, 'attack_speed': 1.5},
        }
        
        if card_name not in card_stats:
            return None
        
        stats = card_stats[card_name]
        entity = OptimizedEntity(
            id=self.next_entity_id,
            entity_type=EntityType.TROOP,
            player_id=player_id,
            lane=lane,
            x=position.x,
            y=position.y,
            speed=stats['speed'],
            hitpoints=stats['hp'],
            max_hitpoints=stats['hp'],
            damage=stats['damage'],
            attack_range=stats['range'],
            attack_speed=stats['attack_speed'],
            prioritize_buildings=(card_name == 'giant')
        )
        
        self.next_entity_id += 1
        return entity
    
    def get_state_dict(self) -> Dict:
        """Get serializable state for replay/analysis"""
        return {
            'time': self.time,
            'tick': self.tick,
            'entities': {
                eid: {
                    'id': e.id,
                    'type': e.entity_type.value,
                    'player_id': e.player_id,
                    'x': e.x,
                    'y': e.y,
                    'hp': e.hitpoints,
                    'max_hp': e.max_hitpoints,
                    'is_alive': e.is_alive
                }
                for eid, e in self.entities.items()
            },
            'players': [
                {
                    'player_id': p.player_id,
                    'elixir': p.elixir,
                    'king_tower_hp': p.king_tower_hp,
                    'left_tower_hp': p.left_tower_hp,
                    'right_tower_hp': p.right_tower_hp,
                    'crowns': p.get_crown_count()
                }
                for p in self.players
            ],
            'game_over': self.game_over,
            'winner': self.winner,
            'double_elixir': self.double_elixir
        }


class OptimizedBattleEngine:
    """High-performance battle engine for RL training"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.battle: Optional[OptimizedBattleState] = None
    
    def create_battle(self) -> OptimizedBattleState:
        """Create new battle instance"""
        self.battle = OptimizedBattleState()
        self.battle.headless = self.headless
        return self.battle
    
    def run_battle_fast(self, 
                       max_ticks: int = 9090, 
                       speed_factor: float = 10.0,
                       early_stop: bool = True) -> Dict:
        """Run battle at maximum speed for RL training"""
        if not self.battle:
            self.create_battle()
        
        start_time = time.perf_counter()
        
        for tick in range(max_ticks):
            if self.battle.game_over and early_stop:
                break
            
            self.battle.step(speed_factor)
            
            # Periodic cleanup for long battles
            if tick % 1000 == 0:
                self._cleanup_memory()
        
        end_time = time.perf_counter()
        
        return {
            'result': self.battle.get_state_dict(),
            'duration_seconds': end_time - start_time,
            'ticks_executed': self.battle.tick,
            'ticks_per_second': self.battle.tick / (end_time - start_time) if end_time > start_time else 0,
            'game_time': self.battle.time
        }
    
    def _cleanup_memory(self):
        """Periodic memory cleanup for long-running simulations"""
        if self.battle:
            # Clear spatial index of dead entities
            dead_ids = [eid for eid, e in self.battle.entities.items() if not e.is_alive]
            for eid in dead_ids:
                self.battle._remove_entity(eid)
    
    def get_battle_state(self) -> Optional[OptimizedBattleState]:
        """Get current battle state"""
        return self.battle
    
    def save_replay(self, filename: str):
        """Save battle replay"""
        if self.battle:
            with open(filename, 'w') as f:
                json.dump(self.battle.get_state_dict(), f, indent=2)


# Performance comparison function
def benchmark_engines(iterations: int = 100) -> Dict:
    """Benchmark optimized vs original engine"""
    from .engine import BattleEngine
    
    # Test optimized engine
    start = time.perf_counter()
    optimized_engine = OptimizedBattleEngine(headless=True)
    
    for _ in range(iterations):
        battle = optimized_engine.create_battle()
        optimized_engine.run_battle_fast(max_ticks=1000, speed_factor=10.0)
    
    optimized_time = time.perf_counter() - start
    
    # Test original engine  
    start = time.perf_counter()
    original_engine = BattleEngine()
    
    for _ in range(iterations):
        battle = original_engine.create_battle()
        original_engine.run_headless(speed_factor=10.0)
    
    original_time = time.perf_counter() - start
    
    return {
        'optimized_time': optimized_time,
        'original_time': original_time,
        'speedup': original_time / optimized_time,
        'optimized_battles_per_second': iterations / optimized_time,
        'original_battles_per_second': iterations / original_time
    }