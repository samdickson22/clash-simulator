"""
Advanced Mechanics for Phase 9

Implements:
- Knockback effects
- Stun mechanics  
- Death spawns
- King activation triggers
- Tile snapping and bridge logic refinements
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

from .entities import Entity, Troop
from .arena import Position
from .battle import BattleState


class EffectType(Enum):
    KNOCKBACK = "knockback"
    STUN = "stun"
    DEATH_SPAWN = "death_spawn"
    KING_ACTIVATE = "king_activate"


@dataclass
class Effect:
    """Base effect class"""
    effect_type: EffectType
    duration: float = 0.0
    strength: float = 0.0
    remaining_time: float = 0.0
    
    def __post_init__(self):
        if self.remaining_time == 0.0:
            self.remaining_time = self.duration


@dataclass
class KnockbackEffect(Effect):
    """Knockback effect that pushes units away"""
    direction_x: float = 0.0
    direction_y: float = 0.0
    
    def __post_init__(self):
        super().__post_init__()
        self.effect_type = EffectType.KNOCKBACK


@dataclass
class StunEffect(Effect):
    """Stun effect that prevents actions"""
    
    def __post_init__(self):
        super().__post_init__()
        self.effect_type = EffectType.STUN


class AdvancedTroop(Troop):
    """Enhanced troop with advanced mechanics"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.effects: List[Effect] = []
        self.death_spawn_card: Optional[str] = None
        self.knockback_on_hit: bool = False
        self.king_activation_range: float = 0.0
        
    def update(self, dt: float, battle_state: BattleState) -> None:
        """Update with advanced mechanics"""
        # Update effects
        self.update_effects(dt)
        
        # Check if stunned
        if self.is_stunned():
            return  # Skip normal update
        
        # Normal troop update
        super().update(dt, battle_state)
        
        # Check king activation
        self.check_king_activation(battle_state)
    
    def update_effects(self, dt: float) -> None:
        """Update all active effects"""
        active_effects = []
        
        for effect in self.effects:
            effect.remaining_time -= dt
            
            if effect.remaining_time > 0:
                self.apply_effect(effect, dt)
                active_effects.append(effect) 
            else:
                self.remove_effect(effect)
        
        self.effects = active_effects
    
    def apply_effect(self, effect: Effect, dt: float) -> None:
        """Apply an active effect"""
        if effect.effect_type == EffectType.KNOCKBACK:
            knockback = effect
            # Apply knockback movement
            self.position.x += knockback.direction_x * knockback.strength * dt
            self.position.y += knockback.direction_y * knockback.strength * dt
            
        elif effect.effect_type == EffectType.STUN:
            # Stun prevents actions (handled in is_stunned())
            pass
    
    def remove_effect(self, effect: Effect) -> None:
        """Clean up when effect expires"""
        pass
    
    def add_effect(self, effect: Effect) -> None:
        """Add a new effect"""
        self.effects.append(effect)
    
    def is_stunned(self) -> bool:
        """Check if unit is currently stunned"""
        return any(e.effect_type == EffectType.STUN for e in self.effects)
    
    def apply_knockback(self, direction_x: float, direction_y: float, 
                       strength: float, duration: float = 0.5) -> None:
        """Apply knockback effect"""
        knockback = KnockbackEffect(
            effect_type=EffectType.KNOCKBACK,
            direction_x=direction_x,
            direction_y=direction_y,
            strength=strength,
            duration=duration
        )
        self.add_effect(knockback)
    
    def apply_stun(self, duration: float) -> None:
        """Apply stun effect"""
        stun = StunEffect(
            effect_type=EffectType.STUN,
            duration=duration
        )
        self.add_effect(stun)
    
    def check_king_activation(self, battle_state: BattleState) -> None:
        """Check if this unit activates enemy king tower"""
        if self.king_activation_range <= 0:
            return
        
        enemy_player_id = 1 - self.player_id
        
        # Get enemy king tower position
        if enemy_player_id == 0:
            king_pos = battle_state.arena.BLUE_KING_TOWER
        else:
            king_pos = battle_state.arena.RED_KING_TOWER
        
        # Check distance to king tower
        distance = self.position.distance_to(king_pos)
        if distance <= self.king_activation_range:
            self.activate_king_tower(battle_state, enemy_player_id)
    
    def activate_king_tower(self, battle_state: BattleState, player_id: int) -> None:
        """Activate king tower (make it target this unit)"""
        for entity in battle_state.entities.values():
            if (entity.player_id == player_id and 
                entity.card_stats.name == "KingTower"):
                # Force king tower to target this unit
                entity.target_id = self.id
                break
    
    def on_death(self, battle_state: BattleState) -> None:
        """Handle death spawns and other death effects"""
        if self.death_spawn_card:
            self.spawn_on_death(battle_state)
    
    def spawn_on_death(self, battle_state: BattleState) -> None:
        """Spawn units when this unit dies"""
        card_stats = battle_state.card_loader.get_card(self.death_spawn_card)
        if not card_stats:
            return
        
        # Spawn at death location
        spawn_positions = [
            Position(self.position.x - 50, self.position.y),
            Position(self.position.x + 50, self.position.y),
            Position(self.position.x, self.position.y - 50),
            Position(self.position.x, self.position.y + 50)
        ]
        
        for pos in spawn_positions[:card_stats.count or 1]:
            if battle_state.arena.is_valid_position(pos):
                new_troop = AdvancedTroop(
                    id=battle_state.next_entity_id,
                    position=pos,
                    player_id=self.player_id,
                    card_stats=card_stats,
                    hitpoints=card_stats.hitpoints or 100,
                    max_hitpoints=card_stats.hitpoints or 100,
                    damage=card_stats.damage or 10,
                    range=card_stats.range or 100,
                    sight_range=card_stats.sight_range or 500,
                    speed=1.0
                )
                
                battle_state.entities[battle_state.next_entity_id] = new_troop
                battle_state.next_entity_id += 1


class TileSnapping:
    """Improved tile snapping and positioning"""
    
    @staticmethod
    def snap_to_tile(position: Position, tile_size: float = 100.0) -> Position:
        """Snap position to nearest tile center"""
        tile_x = round(position.x / tile_size)
        tile_y = round(position.y / tile_size)
        
        return Position(
            tile_x * tile_size + tile_size / 2,
            tile_y * tile_size + tile_size / 2
        )
    
    @staticmethod
    def get_bridge_path(start: Position, end: Position, 
                       arena_width: int = 32, river_y: float = 9.0) -> List[Position]:
        """Get optimal path considering bridges"""
        # Simple pathfinding - move to nearest bridge if crossing river
        start_side = 0 if start.y < river_y else 1
        end_side = 0 if end.y < river_y else 1
        
        if start_side == end_side:
            # Same side - direct path
            return [start, end]
        
        # Need to cross river - find best bridge
        left_bridge = Position(6.0, river_y)
        right_bridge = Position(26.0, river_y)
        
        # Choose closest bridge
        dist_to_left = start.distance_to(left_bridge) + left_bridge.distance_to(end)
        dist_to_right = start.distance_to(right_bridge) + right_bridge.distance_to(end)
        
        if dist_to_left < dist_to_right:
            return [start, left_bridge, end]
        else:
            return [start, right_bridge, end]


class AdvancedCombat:
    """Enhanced combat mechanics"""
    
    @staticmethod
    def apply_attack_effects(attacker: Entity, target: Entity, 
                           battle_state: BattleState) -> None:
        """Apply special attack effects"""
        # Knockback effects
        if hasattr(attacker, 'knockback_on_hit') and attacker.knockback_on_hit:
            # Calculate knockback direction
            dx = target.position.x - attacker.position.x
            dy = target.position.y - attacker.position.y
            distance = (dx * dx + dy * dy) ** 0.5
            
            if distance > 0 and isinstance(target, AdvancedTroop):
                target.apply_knockback(
                    direction_x=dx / distance,
                    direction_y=dy / distance,
                    strength=200.0,  # Knockback strength
                    duration=0.3
                )
        
        # Stun effects (example: some units stun on hit)
        if (hasattr(attacker, 'stun_on_hit') and attacker.stun_on_hit and
            isinstance(target, AdvancedTroop)):
            target.apply_stun(1.0)  # 1 second stun


# Predefined advanced units
def create_advanced_knight(entity_id: int, position: Position, 
                          player_id: int, card_stats) -> AdvancedTroop:
    """Create Knight with advanced mechanics"""
    knight = AdvancedTroop(
        id=entity_id,
        position=position,
        player_id=player_id,
        card_stats=card_stats,
        hitpoints=card_stats.hitpoints or 690,
        max_hitpoints=card_stats.hitpoints or 690,
        damage=card_stats.damage or 79,
        range=card_stats.range or 120,
        sight_range=card_stats.sight_range or 550,
        speed=1.0
    )
    
    # Knights can activate king towers when close
    knight.king_activation_range = 300.0
    return knight


def create_advanced_giant(entity_id: int, position: Position,
                         player_id: int, card_stats) -> AdvancedTroop:
    """Create Giant with knockback on hit"""
    giant = AdvancedTroop(
        id=entity_id,
        position=position,
        player_id=player_id,
        card_stats=card_stats,
        hitpoints=card_stats.hitpoints or 1598,
        max_hitpoints=card_stats.hitpoints or 1598,
        damage=card_stats.damage or 99,
        range=card_stats.range or 120,
        sight_range=card_stats.sight_range or 700,
        speed=0.7  # Slow
    )
    
    # Giants knockback smaller units
    giant.knockback_on_hit = True
    return giant