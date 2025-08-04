from dataclasses import dataclass
from typing import Dict, List, TYPE_CHECKING
from abc import ABC, abstractmethod

from .entities import Entity, Projectile, Troop, AreaEffect, SpawnProjectile, RollingProjectile, TimedExplosive, Graveyard
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
    
    def _hitbox_overlaps_with_area(self, entity: 'Entity', area_center: Position) -> bool:
        """Check if entity's hitbox overlaps with spell area using collision detection"""
        # Get entity collision radius (default to 0.5 tiles if not specified or None)
        if entity.card_stats and hasattr(entity.card_stats, 'collision_radius') and entity.card_stats.collision_radius is not None:
            entity_radius = entity.card_stats.collision_radius
        else:
            entity_radius = 0.5
        
        # Calculate distance between area center and entity center
        distance = entity.position.distance_to(area_center)
        
        # Check if spell area overlaps with entity hitbox
        return distance <= (self.radius + entity_radius)


@dataclass
class DirectDamageSpell(Spell):
    """Spells that deal instant damage in an area"""
    stun_duration: float = 0.0
    slow_duration: float = 0.0  
    slow_multiplier: float = 1.0
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Deal damage to all enemies in radius"""
        targets_hit = 0
        
        for entity in battle_state.entities.values():
            if entity.player_id == player_id or not entity.is_alive:
                continue
            
            # Use hitbox-based collision detection for more accurate damage
            if self._hitbox_overlaps_with_area(entity, target_pos):
                entity.take_damage(self.damage)
                
                # Apply status effects
                if self.stun_duration > 0:
                    entity.apply_stun(self.stun_duration)
                if self.slow_duration > 0:
                    entity.apply_slow(self.slow_duration, self.slow_multiplier)
                
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
        
        # Add spell name for visualization
        projectile.spell_name = self.name
        
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
class AreaEffectSpell(Spell):
    """Spells that create area effects on the ground with duration"""
    duration: float = 4.0  # seconds
    freeze_effect: bool = False
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Create area effect at target position"""
        # Create area effect entity
        area_effect = AreaEffect(
            id=battle_state.next_entity_id,
            position=Position(target_pos.x, target_pos.y),
            player_id=player_id,
            card_stats=None,
            hitpoints=1,
            max_hitpoints=1,
            damage=self.damage,
            range=self.radius,
            sight_range=self.radius,
            duration=self.duration,
            freeze_effect=self.freeze_effect,
            radius=self.radius
        )
        
        # Add spell name for visualization
        area_effect.spell_name = self.name
        
        battle_state.entities[battle_state.next_entity_id] = area_effect
        battle_state.next_entity_id += 1
        return True


@dataclass
class SpawnProjectileSpell(ProjectileSpell):
    """Projectile spells that spawn units when they land"""
    spawn_count: int = 3
    spawn_character: str = "Goblin"
    spawn_character_data: dict = None
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Fire a projectile that spawns units on impact"""
        launch_pos = self._get_launch_position(battle_state, player_id)
        
        projectile = SpawnProjectile(
            id=battle_state.next_entity_id,
            position=launch_pos,
            player_id=player_id,
            card_stats=None,
            hitpoints=1,
            max_hitpoints=1,
            damage=self.damage,
            range=0,
            sight_range=0,
            target_position=Position(target_pos.x, target_pos.y),
            travel_speed=self.travel_speed,
            splash_radius=self.radius,
            spawn_count=self.spawn_count,
            spawn_character=self.spawn_character,
            spawn_character_data=self.spawn_character_data
        )
        
        # Add spell name for visualization
        projectile.spell_name = self.name
        
        battle_state.entities[battle_state.next_entity_id] = projectile
        battle_state.next_entity_id += 1
        return True


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


@dataclass
class RollingProjectileSpell(Spell):
    """Spells that spawn at location and roll forward (Log, Barbarian Barrel)"""
    travel_speed: float = 200.0
    projectile_range: float = 10.0  # tiles
    spawn_delay: float = 0.65  # seconds
    spawn_character: str = None  # For Barbarian Barrel
    spawn_character_data: dict = None
    radius_y: float = 0.6  # Height of rolling hitbox
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Spawn rolling projectile at target position"""
        # Create rolling projectile entity
        rolling_projectile = RollingProjectile(
            id=battle_state.next_entity_id,
            position=Position(target_pos.x, target_pos.y),
            player_id=player_id,
            card_stats=None,
            hitpoints=1,
            max_hitpoints=1,
            damage=self.damage,
            range=self.radius,  # Use radius as range for rolling width
            sight_range=0,
            travel_speed=self.travel_speed,
            projectile_range=self.projectile_range,
            spawn_delay=self.spawn_delay,
            spawn_character=self.spawn_character,
            spawn_character_data=self.spawn_character_data,
            radius_y=self.radius_y
        )
        
        # Add spell name for visualization
        rolling_projectile.spell_name = self.name
        
        battle_state.entities[battle_state.next_entity_id] = rolling_projectile
        battle_state.next_entity_id += 1
        return True


@dataclass
class TornadoSpell(Spell):
    """Spell that pulls enemies towards center and deals damage over time"""
    pull_force: float = 3.0  # tiles per second
    damage_per_second: float = 35.0
    duration: float = 3.0
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Create tornado effect that pulls enemies and deals damage"""
        # Create area effect with pull mechanics
        tornado = AreaEffect(
            id=battle_state.next_entity_id,
            position=Position(target_pos.x, target_pos.y),
            player_id=player_id,
            card_stats=None,
            hitpoints=1,
            max_hitpoints=1,
            damage=self.damage_per_second,
            range=self.radius,
            sight_range=self.radius,
            duration=self.duration,
            freeze_effect=False,
            radius=self.radius
        )
        
        # Add tornado-specific properties
        tornado.spell_name = self.name
        tornado.pull_force = self.pull_force
        tornado.is_tornado = True
        
        battle_state.entities[battle_state.next_entity_id] = tornado
        battle_state.next_entity_id += 1
        return True


@dataclass
class GraveyardSpell(Spell):
    """Spell that spawns skeletons periodically in an area"""
    spawn_interval: float = 0.5
    max_skeletons: int = 20
    duration: float = 10.0
    skeleton_data: dict = None
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Create graveyard that spawns skeletons"""
        graveyard = Graveyard(
            id=battle_state.next_entity_id,
            position=Position(target_pos.x, target_pos.y),
            player_id=player_id,
            card_stats=None,
            hitpoints=1,
            max_hitpoints=1,
            damage=0,
            range=self.radius,
            sight_range=self.radius,
            spawn_interval=self.spawn_interval,
            max_skeletons=self.max_skeletons,
            spawn_radius=self.radius,
            duration=self.duration,
            skeleton_data=self.skeleton_data or {
                "hitpoints": 67,
                "damage": 67,
                "speed": 60,
                "range": 500,
                "sightRange": 5500,
                "hitSpeed": 1000,
                "deployTime": 1000,
                "loadTime": 1000,
                "collisionRadius": 300,
                "attacksGround": True,
                "tidTarget": "TID_TARGETS_GROUND"
            }
        )
        
        # Add spell name for visualization
        graveyard.spell_name = self.name
        
        battle_state.entities[battle_state.next_entity_id] = graveyard
        battle_state.next_entity_id += 1
        return True


# Predefined spells based on JSON schemas
ARROWS = DirectDamageSpell("Arrows", 3, radius=400.0, damage=144)
FIREBALL = ProjectileSpell("Fireball", 4, radius=250.0, damage=572, travel_speed=600.0/60.0) 
ZAP = DirectDamageSpell("Zap", 2, radius=250.0, damage=159, stun_duration=0.5)
LIGHTNING = DirectDamageSpell("Lightning", 6, radius=350.0, damage=864, stun_duration=0.5)

# Projectile spells that travel across arena (speeds converted from tiles/min to tiles/sec)
ROCKET = ProjectileSpell("Rocket", 6, radius=2000.0/1000.0, damage=580, travel_speed=350.0/60.0)
GOBLIN_BARREL = SpawnProjectileSpell(
    "GoblinBarrel", 3, 
    radius=1500.0/1000.0, 
    damage=0, 
    travel_speed=400.0/60.0,
    spawn_count=3,
    spawn_character="Goblin",
    spawn_character_data={
        "hitpoints": 79,
        "damage": 47,
        "speed": 120,
        "range": 500,
        "sightRange": 5500,
        "hitSpeed": 1100,
        "loadTime": 700,
        "deployTime": 1000,
        "collisionRadius": 500,
        "attacksGround": True,
        "tidTarget": "TID_TARGETS_GROUND"
    }
)

# Area effect spells that stay on ground
FREEZE = AreaEffectSpell("Freeze", 4, radius=3000.0/1000.0, damage=45, duration=4.0, freeze_effect=True)
RAGE = BuffSpell("Rage", 2, radius=3000.0, damage=0, buff_duration=6.0, speed_multiplier=1.5, damage_multiplier=1.4)
MIRROR = DirectDamageSpell("Mirror", 3, radius=0.0, damage=0)  # Special case - handled in battle logic
POISON = DirectDamageSpell("Poison", 4, radius=3000.0, damage=78)  # Damage over time
GRAVEYARD = GraveyardSpell("Graveyard", 5, radius=2.5, damage=0, spawn_interval=0.5, max_skeletons=20, duration=10.0)
LOG = ProjectileSpell("Log", 2, radius=250.0, damage=240, travel_speed=1200.0/60.0)
TORNADO = TornadoSpell("Tornado", 3, radius=3000.0/1000.0, damage=0, pull_force=3.0, damage_per_second=35.0, duration=3.0)
EARTHQUAKE = DirectDamageSpell("Earthquake", 3, radius=3000.0/1000.0, damage=332, slow_duration=3.0, slow_multiplier=0.5)
BARB_LOG = ProjectileSpell("BarbLog", 2, radius=250.0/1000.0, damage=240, travel_speed=1200.0/60.0)
HEAL = HealSpell("Heal", 3, radius=3000.0/1000.0, damage=0, heal_amount=400.0)
SNOWBALL = DirectDamageSpell("Snowball", 2, radius=250.0/1000.0, damage=0, slow_duration=2.5, slow_multiplier=0.65)
ROYAL_DELIVERY = DirectDamageSpell("RoyalDelivery", 4, radius=0.0, damage=0)  # Special case
GLOBAL_CLONE = DirectDamageSpell("GlobalClone", 3, radius=0.0, damage=0)  # Special case
GOBLIN_PARTY_ROCKET = ProjectileSpell("GoblinPartyRocket", 4, radius=250.0, damage=0, travel_speed=1000.0/60.0)
WARM_SPELL = DirectDamageSpell("WarmSpell", 0, radius=0.0, damage=0)  # Special case
GLOBAL_LIGHTNING = DirectDamageSpell("GlobalLightning", 6, radius=3000.0, damage=1440)
DARK_MAGIC = DirectDamageSpell("DarkMagic", 4, radius=3000.0, damage=0)  # Special effect
GOBLIN_CURSE = DirectDamageSpell("GoblinCurse", 3, radius=3000.0, damage=0)  # Special effect
MERGE_MAIDEN = DirectDamageSpell("MergeMaiden", 4, radius=0.0, damage=0)  # Special case

# Load spells dynamically from JSON
def _load_dynamic_spell_registry():
    """Load spells dynamically from gamedata.json."""
    try:
        from .dynamic_spells import load_dynamic_spells
        return load_dynamic_spells()
    except Exception as e:
        print(f"Warning: Could not load dynamic spells: {e}")
        # Fallback to static spells
        return {
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

SPELL_REGISTRY = _load_dynamic_spell_registry()
