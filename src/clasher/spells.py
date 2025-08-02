from dataclasses import dataclass
from typing import Dict, List, TYPE_CHECKING
from abc import ABC, abstractmethod

from .entities import Entity, Projectile, Troop
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
            tower_pos = battle_state.arena.BLUE_KING_TOWER
            return Position(tower_pos.x, tower_pos.y)
        else:
            tower_pos = battle_state.arena.RED_KING_TOWER
            return Position(tower_pos.x, tower_pos.y)


@dataclass
class BuffSpell(Spell):
    """Spells that buff friendly units"""
    buff_duration: float = 3.0  # seconds
    speed_multiplier: float = 1.5
    damage_multiplier: float = 1.4
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Apply buff to friendly units in radius"""
        targets_hit = 0
        
        for entity in battle_state.entities.values():
            if entity.player_id != player_id or not entity.is_alive:
                continue
            
            distance = entity.position.distance_to(target_pos)
            if distance <= self.radius:
                # Apply buff effects
                if hasattr(entity, 'speed'):
                    entity.speed *= self.speed_multiplier
                if hasattr(entity, 'damage'):
                    entity.damage *= self.damage_multiplier
                targets_hit += 1
        
        return targets_hit > 0


@dataclass
class FreezeSpell(Spell):
    """Spells that freeze enemies"""
    freeze_duration: float = 3.0  # seconds
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Freeze enemies in radius"""
        targets_hit = 0
        
        for entity in battle_state.entities.values():
            if entity.player_id == player_id or not entity.is_alive:
                continue
            
            distance = entity.position.distance_to(target_pos)
            if distance <= self.radius:
                # Freeze the unit (stop movement and attacks)
                if hasattr(entity, 'speed'):
                    entity.speed = 0
                if hasattr(entity, 'is_frozen'):
                    entity.is_frozen = True
                targets_hit += 1
        
        return targets_hit > 0


@dataclass
class CloneSpell(Spell):
    """Spells that clone existing troops"""
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Clone friendly troops in radius"""
        targets_hit = 0
        
        # Find friendly troops in radius
        troops_to_clone = []
        for entity in battle_state.entities.values():
            if entity.player_id != player_id or not entity.is_alive:
                continue
            
            distance = entity.position.distance_to(target_pos)
            if distance <= self.radius:
                # Only clone troops, not buildings
                if hasattr(entity, 'speed') and hasattr(entity, 'card_stats'):
                    troops_to_clone.append(entity)
                    targets_hit += 1
        
        # Create clones
        for troop in troops_to_clone:
            clone = Troop(
                id=battle_state.next_entity_id,
                position=Position(troop.position.x, troop.position.y),
                player_id=player_id,
                card_stats=troop.card_stats,
                hitpoints=troop.hitpoints,
                max_hitpoints=troop.max_hitpoints,
                damage=troop.damage,
                range=troop.range,
                sight_range=troop.sight_range,
                speed=troop.speed,
                is_air_unit=troop.is_air_unit
            )
            # Mark as clone after creation
            clone.is_clone = True
            battle_state.entities[battle_state.next_entity_id] = clone
            battle_state.next_entity_id += 1
        
        return targets_hit > 0


@dataclass
class HealSpell(Spell):
    """Spells that heal friendly units"""
    heal_amount: float = 400.0
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Heal friendly units in radius"""
        targets_hit = 0
        
        for entity in battle_state.entities.values():
            if entity.player_id != player_id or not entity.is_alive:
                continue
            
            distance = entity.position.distance_to(target_pos)
            if distance <= self.radius:
                # Heal the unit
                current_hp = entity.hitpoints
                max_hp = entity.max_hitpoints
                entity.hitpoints = min(current_hp + self.heal_amount, max_hp)
                targets_hit += 1
        
        return targets_hit > 0


# Predefined spells
ARROWS = DirectDamageSpell("Arrows", 3, radius=400.0, damage=144)
FIREBALL = ProjectileSpell("Fireball", 4, radius=250.0, damage=572, travel_speed=600.0) 
ZAP = DirectDamageSpell("Zap", 2, radius=250.0, damage=159)
LIGHTNING = DirectDamageSpell("Lightning", 6, radius=350.0, damage=864)

# Missing spells implementation
RAGE = BuffSpell("Rage", 2, radius=3000.0, damage=0, buff_duration=6.0, speed_multiplier=1.5, damage_multiplier=1.4)
ROCKET = ProjectileSpell("Rocket", 5, radius=250.0, damage=1056, travel_speed=1000.0)
GOBLIN_BARREL = ProjectileSpell("GoblinBarrel", 3, radius=200.0, damage=0, travel_speed=800.0)
FREEZE = FreezeSpell("Freeze", 4, radius=3000.0, damage=0, freeze_duration=3.0)
MIRROR = DirectDamageSpell("Mirror", 3, radius=0.0, damage=0)  # Special case - handled in battle logic
POISON = DirectDamageSpell("Poison", 4, radius=3000.0, damage=78)  # Damage over time
GRAVEYARD = DirectDamageSpell("Graveyard", 5, radius=3000.0, damage=0)  # Summons skeletons
LOG = ProjectileSpell("Log", 2, radius=250.0, damage=240, travel_speed=1200.0)
TORNADO = DirectDamageSpell("Tornado", 3, radius=3000.0, damage=0)  # Pulls enemies
EARTHQUAKE = DirectDamageSpell("Earthquake", 3, radius=3000.0, damage=332)  # Damages buildings
BARB_LOG = ProjectileSpell("BarbLog", 2, radius=250.0, damage=240, travel_speed=1200.0)
HEAL = HealSpell("Heal", 3, radius=3000.0, damage=0, heal_amount=400.0)
SNOWBALL = DirectDamageSpell("Snowball", 2, radius=250.0, damage=0)  # Freezes single target
ROYAL_DELIVERY = DirectDamageSpell("RoyalDelivery", 4, radius=0.0, damage=0)  # Special case
GLOBAL_CLONE = DirectDamageSpell("GlobalClone", 3, radius=0.0, damage=0)  # Special case
GOBLIN_PARTY_ROCKET = ProjectileSpell("GoblinPartyRocket", 4, radius=250.0, damage=0, travel_speed=1000.0)
WARM_SPELL = DirectDamageSpell("WarmSpell", 0, radius=0.0, damage=0)  # Special case
GLOBAL_LIGHTNING = DirectDamageSpell("GlobalLightning", 6, radius=3000.0, damage=1440)
DARK_MAGIC = DirectDamageSpell("DarkMagic", 4, radius=3000.0, damage=0)  # Special effect
GOBLIN_CURSE = DirectDamageSpell("GoblinCurse", 3, radius=3000.0, damage=0)  # Special effect
MERGE_MAIDEN = DirectDamageSpell("MergeMaiden", 4, radius=0.0, damage=0)  # Special case

SPELL_REGISTRY = {
    "Arrows": ARROWS,
    "Fireball": FIREBALL, 
    "Zap": ZAP,
    "Lightning": LIGHTNING,
    "Rage": RAGE,
    "Rocket": ROCKET,
    "GoblinBarrel": GOBLIN_BARREL,
    "Freeze": FREEZE,
    "Mirror": MIRROR,
    "Poison": POISON,
    "Graveyard": GRAVEYARD,
    "Log": LOG,
    "Tornado": TORNADO,
    "Earthquake": EARTHQUAKE,
    "BarbLog": BARB_LOG,
    "Heal": HEAL,
    "Snowball": SNOWBALL,
    "RoyalDelivery": ROYAL_DELIVERY,
    "Clone": CloneSpell("Clone", 3, radius=3000.0, damage=0),
    "GlobalClone": GLOBAL_CLONE,
    "GoblinPartyRocket": GOBLIN_PARTY_ROCKET,
    "WarmSpell": WARM_SPELL,
    "GlobalLightning": GLOBAL_LIGHTNING,
    "DarkMagic": DARK_MAGIC,
    "GoblinCurse": GOBLIN_CURSE,
    "MergeMaiden": MERGE_MAIDEN
}
