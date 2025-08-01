from dataclasses import dataclass
from typing import Dict, List, TYPE_CHECKING
from abc import ABC, abstractmethod

from .entities import Entity, Projectile
from .arena import Position

if TYPE_CHECKING:
    from .battle import BattleState


@dataclass
class Spell(ABC):
    """Base class for spell effects"""
    name: str
    mana_cost: int
    radius: float = 0.0
    damage: float = 0.0
    
    @abstractmethod
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Cast the spell at target position"""
        pass


@dataclass
class DirectDamageSpell(Spell):
    """Spells that deal instant damage in an area"""
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Deal damage to all enemies in radius"""
        targets_hit = 0
        
        for entity in battle_state.entities.values():
            if entity.player_id == player_id or not entity.is_alive:
                continue
            
            distance = entity.position.distance_to(target_pos)
            if distance <= self.radius:
                entity.take_damage(self.damage)
                targets_hit += 1
        
        return targets_hit > 0


@dataclass  
class ProjectileSpell(Spell):
    """Spells that fire projectiles"""
    travel_speed: float = 500.0
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Fire a projectile toward target position"""
        # Find launch position (nearest tower or king tower)
        launch_pos = self._get_launch_position(battle_state, player_id)
        
        projectile = Projectile(
            id=battle_state.next_entity_id,
            position=launch_pos,
            player_id=player_id,
            card_stats=None,  # Spells don't have card stats
            hitpoints=1,
            max_hitpoints=1,
            damage=self.damage,
            range=0,
            sight_range=0,
            target_position=target_pos,
            travel_speed=self.travel_speed,
            splash_radius=self.radius
        )
        
        battle_state.entities[battle_state.next_entity_id] = projectile
        battle_state.next_entity_id += 1
        return True
    
    def _get_launch_position(self, battle_state: 'BattleState', player_id: int) -> Position:
        """Get launch position for projectile"""
        if player_id == 0:
            return battle_state.arena.BLUE_KING_TOWER
        else:
            return battle_state.arena.RED_KING_TOWER


# Predefined spells
ARROWS = DirectDamageSpell("Arrows", 3, radius=400.0, damage=144)
FIREBALL = ProjectileSpell("Fireball", 4, radius=250.0, damage=572, travel_speed=600.0) 
ZAP = DirectDamageSpell("Zap", 2, radius=250.0, damage=159)
LIGHTNING = DirectDamageSpell("Lightning", 6, radius=350.0, damage=864)

SPELL_REGISTRY = {
    "Arrows": ARROWS,
    "Fireball": FIREBALL, 
    "Zap": ZAP,
    "Lightning": LIGHTNING
}