from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .battle import BattleState

from .arena import Position
from .card_types import CardStatsCompat, Mechanic
from .factory.dynamic_factory import troop_from_character_data, troop_from_values


class EntityType(Enum):
    TROOP = "troop"
    BUILDING = "building"
    PROJECTILE = "projectile"
    AURA = "aura"


class TargetType(Enum):
    GROUND = "ground"
    AIR = "air" 
    BOTH = "both"


@dataclass
class Entity(ABC):
    id: int
    position: Position
    player_id: int
    card_stats: CardStatsCompat
    
    # Combat stats
    hitpoints: float
    max_hitpoints: float
    damage: float
    range: float
    sight_range: float
    
    # Timing
    attack_cooldown: float = 0.0
    load_time: float = 0.0
    deploy_delay_remaining: float = 0.0
    
    # State
    target_id: Optional[int] = None
    is_alive: bool = True
    is_air_unit: bool = False  # True for flying troops like Minions, Balloon, Dragon
    
    # Status effects
    stun_timer: float = 0.0
    slow_timer: float = 0.0
    slow_multiplier: float = 1.0
    original_speed: Optional[float] = None
    attack_speed_debuff_multiplier: float = 1.0
    attack_speed_buff_multiplier: float = 1.0
    last_attack_time: float = 0.0  # For visualization tracking

    # Mechanics system
    mechanics: List[Mechanic] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.max_hitpoints == 0:
            self.max_hitpoints = self.hitpoints
        # Call on_attach for all mechanics
        for mechanic in self.mechanics:
            mechanic.on_attach(self)
    
    @abstractmethod
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update entity state each tick"""
        pass
    
    def take_damage(self, amount: float) -> None:
        """Apply damage to entity"""
        for mechanic in getattr(self, "mechanics", []):
            guard = getattr(mechanic, "take_damage_during_dash", None)
            if callable(guard):
                should_take_damage = guard(self, amount)
                if not should_take_damage:
                    return

        # King tower activation when hit directly.
        if type(self).__name__ == "Building" and getattr(getattr(self, "card_stats", None), "name", None) == "KingTower":
            if amount > 0:
                self._tower_active = True
        self.hitpoints = max(0, self.hitpoints - amount)
        if self.hitpoints <= 0 and self.is_alive:
            self.is_alive = False
            self.on_death()  # Trigger death mechanics

    def on_spawn(self) -> None:
        """Called when entity is spawned in battle"""
        pass  # print(f"[Lifecycle] on_spawn {getattr(self.card_stats, 'name', 'Unknown')} id={self.id}")
        for mechanic in self.mechanics:
            mechanic.on_spawn(self)

    def on_death(self) -> None:
        """Called when entity dies"""
        pass  # print(f"[Lifecycle] on_death {getattr(self.card_stats, 'name', 'Unknown')} id={self.id}")
        for mechanic in self.mechanics:
            mechanic.on_death(self)
    
    def _deal_attack_damage(self, primary_target: 'Entity', damage: float, battle_state: 'BattleState') -> None:
        """Deal damage to target, with splash damage if applicable"""
        if not primary_target.is_alive:
            return
        
        # Record attack time for AoE visualization
        self.last_attack_time = battle_state.time
        
        # Get area damage radius from different possible sources
        area_damage_radius = None
        if hasattr(self.card_stats, 'area_damage_radius') and self.card_stats.area_damage_radius:
            area_damage_radius = self.card_stats.area_damage_radius / 1000.0
        elif hasattr(self.card_stats, 'projectile_splash_radius') and self.card_stats.projectile_splash_radius:
            area_damage_radius = self.card_stats.projectile_splash_radius / 1000.0
        
        # Deal damage to primary target
        primary_target.take_damage(damage)
        
        # Deal splash damage if this unit has area damage
        if area_damage_radius and area_damage_radius > 0:
            # Find all entities within splash radius
            for entity in list(battle_state.entities.values()):
                if entity == primary_target or entity.player_id == self.player_id:
                    continue
                
                # Check distance using hitbox overlap detection
                entity_distance = primary_target.position.distance_to(entity.position)
                
                # Calculate combined radius for overlap check
                primary_radius = getattr(primary_target.card_stats, 'collision_radius', 0.5) or 0.5
                entity_radius = getattr(entity.card_stats, 'collision_radius', 0.5) or 0.5
                
                # Check if splash radius overlaps with entity hitbox
                if entity_distance <= (area_damage_radius + entity_radius):
                    entity.take_damage(damage)
    
    def apply_stun(self, duration: float) -> None:
        """Apply stun effect for specified duration"""
        self.stun_timer = max(self.stun_timer, duration)
        # Stun resets/restarts attack timing for units already in the attack loop.
        hit_interval = self.get_attack_interval_seconds()
        if hit_interval > 0:
            self.attack_cooldown = max(self.attack_cooldown, hit_interval)

        # Allow card mechanics to react to stun (e.g., Sparky charge reset).
        for mechanic in getattr(self, "mechanics", []):
            handler = getattr(mechanic, "handle_stun", None)
            if callable(handler):
                handler(self)
        
    def apply_slow(self, duration: float, multiplier: float) -> None:
        """Apply slow effect for specified duration"""
        if hasattr(self, 'speed') and self.original_speed is None:
            self.original_speed = self.speed
        self.slow_timer = max(self.slow_timer, duration)
        self.slow_multiplier = min(self.slow_multiplier, multiplier)
        self.attack_speed_debuff_multiplier = min(self.attack_speed_debuff_multiplier, multiplier)
        if hasattr(self, 'speed'):
            self.speed = self.original_speed * self.slow_multiplier
    
    def update_status_effects(self, dt: float) -> None:
        """Update status effect timers"""
        # Update stun timer
        if self.stun_timer > 0:
            self.stun_timer -= dt
        
        # Update slow timer and restore speed when expired
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0:
                # Restore original speed
                if hasattr(self, 'speed') and self.original_speed is not None:
                    self.speed = self.original_speed
                    self.original_speed = None
                self.slow_multiplier = 1.0
                self.attack_speed_debuff_multiplier = 1.0

        # Handle temporary buffs that adjust speed/damage
        if getattr(self, '_buff_active', False):
            if hasattr(self, 'battle_state'):
                if self.battle_state.time >= getattr(self, '_buff_end_time', 0):
                    if hasattr(self, '_original_speed') and self._original_speed is not None:
                        if hasattr(self, 'speed'):
                            self.speed = self._original_speed
                        self._original_speed = None
                    if hasattr(self, '_original_damage') and self._original_damage is not None:
                        self.damage = self._original_damage
                        self._original_damage = None
                    self.attack_speed_buff_multiplier = 1.0
                    self._buff_active = False
                    self._buff_end_time = None

    def get_attack_rate_multiplier(self) -> float:
        """Effective attack-rate multiplier (<=1 slow, >1 buffs)."""
        multiplier = self.attack_speed_debuff_multiplier * self.attack_speed_buff_multiplier
        return max(0.0, multiplier)

    def get_attack_interval_seconds(self) -> float:
        """Current time between attacks after attack-speed modifiers."""
        hit_speed_ms = getattr(getattr(self, "card_stats", None), "hit_speed", None)
        if not hit_speed_ms:
            return 1.0
        rate_multiplier = max(0.05, self.get_attack_rate_multiplier())
        return (hit_speed_ms / 1000.0) / rate_multiplier
    
    def is_stunned(self) -> bool:
        """Check if entity is currently stunned"""
        return self.stun_timer > 0
    
    def can_attack_target(self, target: 'Entity') -> bool:
        """Check if this entity can attack the target"""
        if not self._is_valid_target(target):
            return False

        if target.is_air_unit and not self._can_attack_air():
            return False
        if (not target.is_air_unit) and not self._can_attack_ground():
            return False
        
        distance = self.position.distance_to(target.position)
        target_radius = getattr(target.card_stats, "collision_radius", 0.5) or 0.5
        return distance <= (self.range + target_radius)
    
    def _is_valid_target(self, entity: 'Entity') -> bool:
        """Check if entity can be targeted (excludes spell entities)"""
        # Spell entities cannot be targeted by troops
        spell_entity_types = {'Projectile', 'SpawnProjectile', 'RollingProjectile', 'AreaEffect', 'Graveyard', 'TimedExplosive'}
        if type(entity).__name__ in spell_entity_types:
            return False

        # Stealthed entities cannot be targeted until their cloak expires
        stealth_until = getattr(entity, '_stealth_until', 0)
        if stealth_until and hasattr(entity, 'battle_state'):
            current_ms = int(entity.battle_state.time * 1000)
            if stealth_until > current_ms:
                return False

        # Must be alive and enemy
        return entity.is_alive and entity.player_id != self.player_id
    
    def get_nearest_target(self, entities: Dict[int, 'Entity']) -> Optional['Entity']:
        """Find nearest valid target with priority rules"""
        nearest = None
        min_distance = float('inf')
        
        # Priority: Troops > Buildings (authentic Clash Royale behavior)
        building_targets = []
        troop_targets = []
        
        # Check if this unit can only target buildings
        targets_only_buildings = (hasattr(self, 'card_stats') and 
                                self.card_stats and 
                                getattr(self.card_stats, 'targets_only_buildings', False))
        
        # Check what this unit can attack
        can_attack_air = self._can_attack_air()
        can_attack_ground = self._can_attack_ground()
        
        for entity in entities.values():
            # Only check if entity is valid target (excludes spell entities)
            if not self._is_valid_target(entity):
                continue

            # Additional safety: never target spell entities explicitly by class types
            if isinstance(entity, (Projectile, SpawnProjectile, RollingProjectile, AreaEffect)):
                continue
                
            distance = self.position.distance_to(entity.position)
            
            # Check air targeting rules
            if entity.is_air_unit and not can_attack_air:
                continue  # Skip air units if we can't attack air
            if (not entity.is_air_unit) and not can_attack_ground:
                continue  # Skip ground units if we can't attack ground
            
            # Only consider targets within sight range for troops vs troops
            if isinstance(entity, Building):
                building_targets.append((entity, distance))
            else:
                # For troop targets, only consider if within sight range
                if distance <= self.sight_range:
                    # Skip troops if we only target buildings
                    if not targets_only_buildings:
                        troop_targets.append((entity, distance))
        
        # Choose targets based on targeting rules
        if targets_only_buildings:
            targets = building_targets  # Only consider buildings
        else:
            targets = troop_targets if troop_targets else building_targets  # Troops first, then buildings
        
        for entity, distance in targets:
            if distance < min_distance:
                min_distance = distance
                nearest = entity
        
        return nearest
    
    def _should_switch_target(self, current_target: 'Entity', new_target: 'Entity') -> bool:
        """Determine if we should switch from current target to new target"""
        if getattr(self.card_stats, 'targets_only_buildings', False) and not isinstance(new_target, Building):
            return False
        # Always switch to troops in sight range (higher priority than buildings)
        is_current_building = isinstance(current_target, Building)
        is_new_troop = not isinstance(new_target, Building)
        
        if is_new_troop and is_current_building:
            # Switch from building to troop if troop is in sight range
            distance_to_new = self.position.distance_to(new_target.position)
            if distance_to_new <= self.sight_range:
                return True
        
        # Don't switch if current target is closer and same type
        current_distance = self.position.distance_to(current_target.position)
        new_distance = self.position.distance_to(new_target.position)
        
        # If both are same type (both troops or both buildings), keep closer one
        if isinstance(current_target, Building) == isinstance(new_target, Building):
            return new_distance < current_distance
        
        return False

    def _can_attack_air(self) -> bool:
        """Return True if this entity can attack air units."""
        card_stats = getattr(self, "card_stats", None)
        if not card_stats:
            return True
        target_type = getattr(card_stats, "target_type", None)
        if target_type in {"TID_TARGETS_AIR", "TID_TARGETS_AIR_AND_GROUND"}:
            return True
        return bool(getattr(card_stats, "attacks_air", False))

    def _can_attack_ground(self) -> bool:
        """Return True if this entity can attack ground units."""
        card_stats = getattr(self, "card_stats", None)
        if not card_stats:
            return True
        target_type = getattr(card_stats, "target_type", None)
        if target_type in {
            "TID_TARGETS_GROUND",
            "TID_TARGETS_AIR_AND_GROUND",
            "TID_TARGETS_BUILDINGS",
            "TID_TARGETS_GROUND_AND_BUILDINGS",
            "TID_TARGETS_BUILDINGS_AND_GROUND",
        }:
            return True
        return bool(getattr(card_stats, "attacks_ground", True))


@dataclass
class Troop(Entity):
    speed: float = 1.0
    target_type: TargetType = TargetType.BOTH
    
    # Charging mechanics
    is_charging: bool = False
    has_charged: bool = False  # Track if first charge attack has been used
    charge_target_position: Optional[Position] = None
    distance_traveled: float = 0.0  # Track distance traveled for charging
    initial_position: Position = None  # Store initial position for distance calculation
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update troop - move and attack"""
        if not self.is_alive:
            return

        if self.deploy_delay_remaining > 0:
            self.deploy_delay_remaining = max(0.0, self.deploy_delay_remaining - dt)
            return
        
        # Update status effects first
        self.update_status_effects(dt)

        # Call on_tick for all mechanics
        for mechanic in self.mechanics:
            mechanic.on_tick(self, dt * 1000)  # Convert to ms

        # If stunned, can't move or attack
        if self.is_stunned():
            return
        
        # Store initial position for distance tracking
        if self.initial_position is None:
            self.initial_position = Position(self.position.x, self.position.y)
        
        # Update attack cooldown and track time for visualization
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt * self.get_attack_rate_multiplier()
        
        # Update last attack time for visualization tracking
        self.last_attack_time += dt
        
        # Handle charging mechanics based on distance traveled
        if getattr(self.card_stats, 'charge_range', None) and not self.has_charged:
            self._update_charging_state(battle_state)
        
        # Always re-evaluate targets every tick to switch to higher priority enemies
        current_target = None
        if self.target_id:
            current_target = battle_state.entities.get(self.target_id)
            if not current_target or not current_target.is_alive:
                self.target_id = None
                current_target = None
        
        # Always check for better targets (troops in FOV take priority over buildings)
        best_target = self.get_nearest_target(battle_state.entities)
        if best_target and (not current_target or self._should_switch_target(current_target, best_target)):
            current_target = best_target
            self.target_id = current_target.id
        
        if current_target:
            # Move towards target if out of range
            distance = self.position.distance_to(current_target.position)
            target_radius = getattr(current_target.card_stats, "collision_radius", 0.5) or 0.5
            if distance > (self.range + target_radius):
                self._move_towards_target(current_target, dt, battle_state)
            elif self.attack_cooldown <= 0:
                # Call on_attack_start for all mechanics
                for mechanic in self.mechanics:
                    mechanic.on_attack_start(self, current_target)

                # Check if this troop uses projectiles
                if self._uses_projectiles():
                    self._create_projectile(current_target, battle_state)
                else:
                    # Direct attack with special charging damage if applicable
                    attack_damage = self._get_attack_damage()
                    self._deal_attack_damage(current_target, attack_damage, battle_state)

                # Call on_attack_hit for all mechanics
                for mechanic in self.mechanics:
                    mechanic.on_attack_hit(self, current_target)

                self.attack_cooldown = self.get_attack_interval_seconds()
                self.last_attack_time = 0.0  # Reset for visualization
                self._on_attack()  # Handle post-attack mechanics
    
    def _get_attack_damage(self) -> float:
        """Get the appropriate damage value based on charging state"""
        if getattr(self.card_stats, 'charge_range', None) and not self.has_charged and self.is_charging:
            # Use special damage for first charge attack
            return float(
                (getattr(self.card_stats, 'scaled_damage_special', None)
                 or getattr(self.card_stats, 'damage_special', None)
                 or self.damage)
            )
        return float(self.damage)
    
    def _uses_projectiles(self) -> bool:
        """Check if this troop uses projectiles for attacks"""
        if getattr(self, '_force_melee_attack', False):
            return False
        return (self.card_stats and 
                hasattr(self.card_stats, 'projectile_data') and 
                self.card_stats.projectile_data is not None)
    
    def _create_projectile(self, target: 'Entity', battle_state: 'BattleState') -> None:
        """Create a projectile towards the target"""
        if not self.card_stats or not self.card_stats.projectile_data:
            # Fallback to direct attack if no projectile data
            attack_damage = self._get_attack_damage()
            target.take_damage(attack_damage)
            return
        
        # Get projectile properties
        projectile_data = self.card_stats.projectile_data
        projectile_damage = self.damage  # Use entity's scaled damage instead of base projectile damage
        projectile_speed = projectile_data.get('speed', 500) / 60.0  # Convert from per-minute to per-second
        splash_radius = projectile_data.get('radius', 0) / 1000.0 if projectile_data.get('radius') else 0.0
        target_buff_data = projectile_data.get("targetBuffData") or {}
        slow_duration = projectile_data.get("buffTime", 0) / 1000.0
        slow_multiplier = 1.0 + (target_buff_data.get("speedMultiplier", 0) / 100.0)
        stun_duration = 0.0
        if (
            target_buff_data.get("speedMultiplier") == -100
            and target_buff_data.get("hitSpeedMultiplier") == -100
            and slow_duration > 0
        ):
            stun_duration = slow_duration
            slow_duration = 0.0
            slow_multiplier = 1.0
        tid_target = projectile_data.get("tidTarget", "TID_TARGETS_AIR_AND_GROUND")
        hits_air = "AIR" in tid_target
        hits_ground = ("GROUND" in tid_target) or ("BUILDINGS" in tid_target)
        if tid_target == "TID_TARGETS_GROUND":
            hits_air = False
            hits_ground = True
        crown_tower_damage_multiplier = max(
            0.0, 1.0 + (projectile_data.get("crownTowerDamagePercent", 0) / 100.0)
        )
        
        # Use charging damage if applicable
        if self.is_charging and self.card_stats.damage_special:
            projectile_damage = (
                getattr(self.card_stats, "scaled_damage_special", None)
                or self.card_stats.damage_special
            )
        
        # Check if this is Bowler (create rolling projectile)
        if self.card_stats.name == "Bowler":
            # Calculate direction to target for angled throwing
            dx = target.position.x - self.position.x
            dy = target.position.y - self.position.y
            distance = (dx * dx + dy * dy) ** 0.5
            
            # Normalize direction and calculate end position
            if distance > 0:
                direction_x = dx / distance
                direction_y = dy / distance
                end_x = self.position.x + direction_x * 7.5  # Roll 7.5 tiles in target direction
                end_y = self.position.y + direction_y * 7.5
            else:
                # Fallback if target is at same position
                end_x = self.position.x
                end_y = self.position.y + 7.5  # Roll forward
            
            # Create rolling projectile (Bowler boulder) with target direction
            rolling_projectile = RollingProjectile(
                id=battle_state.next_entity_id,
                position=Position(self.position.x, self.position.y),
                player_id=self.player_id,
                card_stats=self.card_stats,
                hitpoints=1,
                max_hitpoints=1,
                damage=projectile_damage,
                range=splash_radius,  # Use splash radius as rolling width
                sight_range=0,
                travel_speed=projectile_speed * 60.0,  # Convert back to tiles/min for RollingProjectile
                projectile_range=7.5,  # 7500 game units = 7.5 tiles
                spawn_delay=0.0,  # No spawn delay for Bowler
                spawn_character=None,  # Bowler doesn't spawn units
                spawn_character_data=None,
                knockback_distance=projectile_data.get("pushback", 1000) / 1000.0,
                target_direction_x=direction_x if distance > 0 else 0.0,
                target_direction_y=direction_y if distance > 0 else 1.0
            )
            
            battle_state.entities[rolling_projectile.id] = rolling_projectile
        else:
            # Create regular projectile
            projectile = Projectile(
                id=battle_state.next_entity_id,
                position=Position(self.position.x, self.position.y),
                player_id=self.player_id,
                card_stats=self.card_stats,
                hitpoints=1,
                max_hitpoints=1,
                damage=projectile_damage,
                range=self.range,
                sight_range=1.0,
                target_position=Position(target.position.x, target.position.y),
                travel_speed=projectile_speed,
                splash_radius=splash_radius,
                source_name=self.card_stats.name if self.card_stats else "Unknown",
                stun_duration=stun_duration,
                slow_duration=slow_duration,
                slow_multiplier=max(0.0, slow_multiplier),
                knockback_distance=projectile_data.get("pushback", 0) / 1000.0,
                hits_air=hits_air,
                hits_ground=hits_ground,
                crown_tower_damage_multiplier=crown_tower_damage_multiplier,
            )
            
            battle_state.entities[projectile.id] = projectile
        
        battle_state.next_entity_id += 1
    
    def _on_attack(self) -> None:
        """Handle post-attack mechanics like charging state reset"""
        if self.card_stats.charge_range and not self.has_charged and self.is_charging:
            self.has_charged = True
            self.is_charging = False
            self.charge_target_position = None
            # Reset to normal speed if charge speed multiplier was applied
            if self.card_stats.charge_speed_multiplier:
                self.speed = self.card_stats.speed or 60.0
    
    def _update_charging_state(self, battle_state: 'BattleState') -> None:
        """Update charging state - check if troop should start charging based on distance traveled"""
        # Calculate distance traveled from initial position
        if self.initial_position:
            distance_traveled = self.position.distance_to(self.initial_position)
            charge_distance_tiles = self.card_stats.charge_range / 1000.0 if self.card_stats.charge_range else 0.0
            
            # Start charging after traveling the required distance
            if distance_traveled >= charge_distance_tiles and not self.is_charging and not self.has_charged:
                self.is_charging = True
                # Apply charge speed multiplier if available
                if self.card_stats.charge_speed_multiplier:
                    speed_multiplier = 1.0 + (self.card_stats.charge_speed_multiplier / 100.0)
                    self.speed = (self.card_stats.speed or 60.0) * speed_multiplier
    
    def _move_towards_target(self, target_entity: 'Entity', dt: float, battle_state=None) -> None:
        """Move towards target entity with simple obstacle avoidance"""
        # Air units fly directly to targets
        if self.is_air_unit:
            pathfind_target = target_entity.position
        else:
            # Ground units use bridge navigation if needed
            pathfind_target = self._get_pathfind_target(target_entity, battle_state)

        dx = pathfind_target.x - self.position.x
        dy = pathfind_target.y - self.position.y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance > 0:
            # Normalize and scale by speed
            speed_tiles_per_second = self.speed / 60.0  # Convert tiles/min to tiles/sec
            move_distance = speed_tiles_per_second * dt

            # Don't overshoot the target
            if move_distance > distance:
                move_distance = distance

            move_x = (dx / distance) * move_distance
            move_y = (dy / distance) * move_distance

            # Check if the new position would be walkable (for ground units)
            new_position = Position(self.position.x + move_x, self.position.y + move_y)

            # Air units ignore walkability checks, ground units must check
            if self.is_air_unit or (battle_state and battle_state.is_ground_position_walkable(new_position, self)):
                self.position.x += move_x
                self.position.y += move_y
            else:
                # If direct path is blocked, try to find a way around
                alternative_move = self._find_alternative_move(move_x, move_y, battle_state)
                if alternative_move:
                    alt_x, alt_y = alternative_move
                    self.position.x += alt_x
                    self.position.y += alt_y

    def _find_alternative_move(self, original_move_x: float, original_move_y: float, battle_state) -> Optional[tuple]:
        """Find an alternative movement direction when the direct path is blocked."""
        if not battle_state:
            return None

        # Try different angles around the blocked direction
        import math

        # Calculate the original angle
        original_angle = math.atan2(original_move_y, original_move_x)
        move_distance = math.sqrt(original_move_x * original_move_x + original_move_y * original_move_y)

        # Try angles offset by 45°, 90°, -45°, -90° from the original direction
        angle_offsets = [math.pi/4, math.pi/2, -math.pi/4, -math.pi/2]

        for angle_offset in angle_offsets:
            new_angle = original_angle + angle_offset
            new_move_x = math.cos(new_angle) * move_distance
            new_move_y = math.sin(new_angle) * move_distance

            # Check if this alternative direction is walkable
            alt_position = Position(self.position.x + new_move_x, self.position.y + new_move_y)

            if battle_state.is_ground_position_walkable(alt_position, self):
                return (new_move_x, new_move_y)

        return None

    def _get_pathfind_target(self, target_entity: 'Entity', battle_state=None) -> Position:
        """Get pathfinding target using priority system with advanced post-tower-destruction logic:
        Air units: 1) Targets in FOV, 2) Towers (fly directly over river)
        Ground units:
        - Before first tower destroyed: 1) Troops in sight range, 2) Bridge center, 3) Princess towers
        - After first tower destroyed: 1) Troops in FOV, 2) Center bridge, 3) Cross bridge if clear, 4) Target buildings
        """
        from .battle import BattleState

        final_target = target_entity.position

        # Air units bypass bridge pathfinding - they fly directly to targets
        if self.is_air_unit:
            distance_to_target = self.position.distance_to(final_target)
            is_troop = not isinstance(target_entity, Building)

            # Priority 1: If target is a troop within sight range, go directly
            if is_troop and distance_to_target <= self.sight_range:
                return final_target

            # Priority 2: Go directly to any target (towers, etc.) - air units ignore bridges
            return final_target

        # Ground units use bridge pathfinding
        # Check if we need to cross the river (river at y=16)
        current_side = 0 if self.position.y < 16.0 else 1
        target_side = 0 if final_target.y < 16.0 else 1
        need_to_cross = current_side != target_side

        # Priority 1: If target is a troop within sight range, go directly
        distance_to_target = self.position.distance_to(final_target)
        is_troop = not isinstance(target_entity, Building)

        # For troop targets within sight range, still check if we need bridge pathfinding
        if is_troop and distance_to_target <= self.sight_range:
            # If we don't need to cross the river, go directly
            if not need_to_cross:
                return final_target
            # If we need to cross, continue with bridge logic even for troops

        # If we don't need to cross, go directly to target
        if not need_to_cross:
            return final_target

        # Check if first tower has been destroyed to determine pathfinding mode
        first_tower_destroyed = self._is_first_tower_destroyed(battle_state)

        if first_tower_destroyed:
            return self._get_advanced_pathfind_target(target_entity)
        else:
            return self._get_basic_pathfind_target(target_entity)

    def _is_first_tower_destroyed(self, battle_state) -> bool:
        """Check if the first tower (any princess tower) has been destroyed"""
        if not battle_state:
            return False

        # Check if any princess towers are destroyed by looking at player tower HP
        total_princess_towers_alive = 0

        for player in battle_state.players:
            if player.left_tower_hp > 0:
                total_princess_towers_alive += 1
            if player.right_tower_hp > 0:
                total_princess_towers_alive += 1

        # If we have less than 4 princess towers alive, at least one has been destroyed
        return total_princess_towers_alive < 4

    def _get_basic_pathfind_target(self, target_entity: 'Entity') -> Position:
        """Original pathfinding logic before first tower is destroyed"""
        final_target = target_entity.position

        # We need to cross the river - use bridge logic
        # Determine which bridge to use (left at x=3.5, right at x=14.5)
        left_bridge_dist = abs(self.position.x - 3.5)
        right_bridge_dist = abs(self.position.x - 14.5)

        if left_bridge_dist < right_bridge_dist:
            bridge_x = 3.5  # Left bridge center of center tile
        else:
            bridge_x = 14.5  # Right bridge center of center tile

        # Bridge center is at the actual center of the bridge structure
        bridge_y = 16.0  # Dead center of the bridge spanning the river
        bridge_center = Position(bridge_x, bridge_y)

        # Check if we're on the bridge (within 1.5 tiles of bridge center)
        # Bridge is 3 tiles wide, pathfinder targets center of center tile
        on_bridge = (abs(self.position.x - bridge_x) <= 1.5 and
                    abs(self.position.y - 16.0) <= 1.0)

        if on_bridge:
            # Priority 3: On bridge - go to appropriate princess tower
            if self.player_id == 0:  # Blue player going to red side
                if bridge_x == 3.5:  # Left bridge -> left tower
                    return Position(3.5, 25.5)  # RED_LEFT_TOWER
                else:  # Right bridge -> right tower
                    return Position(14.5, 25.5)  # RED_RIGHT_TOWER
            else:  # Red player going to blue side
                if bridge_x == 3.5:  # Left bridge -> left tower
                    return Position(3.5, 6.5)  # BLUE_LEFT_TOWER
                else:  # Right bridge -> right tower
                    return Position(14.5, 6.5)  # BLUE_RIGHT_TOWER
        else:
            # Priority 2: Behind bridge - go to bridge center
            return bridge_center

    def _get_advanced_pathfind_target(self, target_entity: 'Entity') -> Position:
        """Advanced pathfinding logic after first tower is destroyed"""
        final_target = target_entity.position

        # Choose the nearest actual bridge (left at x=3.5 or right at x=14.5)
        left_bridge = Position(3.5, 16.0)
        right_bridge = Position(14.5, 16.0)

        # Determine which bridge is closer
        dist_to_left = self.position.distance_to(left_bridge)
        dist_to_right = self.position.distance_to(right_bridge)

        if dist_to_left <= dist_to_right:
            chosen_bridge = left_bridge
        else:
            chosen_bridge = right_bridge

        # Check if we're on either bridge
        on_left_bridge = (abs(self.position.x - 3.5) <= 1.5 and abs(self.position.y - 16.0) <= 1.0)
        on_right_bridge = (abs(self.position.x - 14.5) <= 1.5 and abs(self.position.y - 16.0) <= 1.0)
        on_bridge = on_left_bridge or on_right_bridge

        if on_bridge:
            # On center bridge - decide whether to cross or target what's visible

            # Check if target is a building (tower or other structure)
            is_building = isinstance(target_entity, Building)

            if is_building:
                # Check if we can see the building (it's in line of sight)
                distance_to_target = self.position.distance_to(final_target)
                if distance_to_target <= self.sight_range:
                    # Building is in line of sight - go directly to it
                    return final_target
                else:
                    # Building not in sight - cross the bridge and move forward
                    if self.player_id == 0:  # Blue player crossing to red side
                        # Move forward from bridge towards red side
                        if on_left_bridge:
                            return Position(3.5, 20.0)  # Forward from left bridge
                        else:
                            return Position(14.5, 20.0)  # Forward from right bridge
                    else:  # Red player crossing to blue side
                        # Move forward from bridge towards blue side
                        if on_left_bridge:
                            return Position(3.5, 12.0)  # Forward from left bridge
                        else:
                            return Position(14.5, 12.0)  # Forward from right bridge
            else:
                # Target is a troop - if in line of sight, go directly
                distance_to_target = self.position.distance_to(final_target)
                if distance_to_target <= self.sight_range:
                    return final_target
                else:
                    # Cross bridge to get closer to target
                    if self.player_id == 0:
                        if on_left_bridge:
                            return Position(3.5, 20.0)  # Move from left bridge towards red side
                        else:
                            return Position(14.5, 20.0)  # Move from right bridge towards red side
                    else:
                        if on_left_bridge:
                            return Position(3.5, 12.0)  # Move from left bridge towards blue side
                        else:
                            return Position(14.5, 12.0)  # Move from right bridge towards blue side
        else:
            # Not on bridge yet - check if we need to route around river
            # Direct path to bridge might cross river, so use intermediate waypoint

            # Check if we're on the same side as the chosen bridge
            if chosen_bridge.x == 3.5:  # Left bridge
                # For left bridge, approach from left side on land
                bridge_approach = Position(3.5, 14.0) if self.player_id == 0 else Position(3.5, 18.0)
            else:  # Right bridge
                # For right bridge, approach from right side on land
                bridge_approach = Position(14.5, 14.0) if self.player_id == 0 else Position(14.5, 18.0)

            # Check if we can reach the bridge approach position directly
            approach_distance = self.position.distance_to(bridge_approach)
            bridge_distance = self.position.distance_to(chosen_bridge)

            # Always use approach waypoint if we're not already close to the bridge
            # This prevents diagonal paths through the river
            if bridge_distance > 2.0:  # If more than 2 tiles away from bridge
                return bridge_approach
            else:
                return chosen_bridge
  

@dataclass
class Building(Entity):
    speed: float = 0.0  # Buildings don't move
    lifetime_elapsed: float = 0.0
    is_king_tower: bool = False  # King towers don't attack until activated
    king_tower_active: bool = False  # Set to True when king tower is activated
    
    def take_damage(self, amount: float) -> None:
        """Override to activate king tower when directly hit"""
        if self.is_king_tower and not self.king_tower_active and amount > 0:
            self.king_tower_active = True
        super().take_damage(amount)
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update building - only attack, no movement"""
        if not self.is_alive:
            return

        if self.deploy_delay_remaining > 0:
            self.deploy_delay_remaining = max(0.0, self.deploy_delay_remaining - dt)
            return

        if getattr(self, "_is_king_tower", False) and not getattr(self, "_tower_active", True):
            return

        # Update status effects
        self.update_status_effects(dt)

        # Call on_tick for all mechanics
        for mechanic in self.mechanics:
            mechanic.on_tick(self, dt * 1000)  # Convert to ms

        # Lifetime handling: decay HP proportional to elapsed time
        lifetime_ms = getattr(self.card_stats, 'lifetime_ms', None)
        if lifetime_ms and lifetime_ms > 0:
            decay = (self.max_hitpoints / float(lifetime_ms)) * (dt * 1000.0)
            if decay > 0:
                self.take_damage(decay)
                if not self.is_alive:
                    return

        # King towers don't attack until activated
        if self.is_king_tower and not self.king_tower_active:
            return

        # If stunned, can't attack
        if self.is_stunned():
            return
        
        # Update attack cooldown and track time for visualization
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt * self.get_attack_rate_multiplier()
        
        # Update last attack time for visualization tracking
        self.last_attack_time += dt
        
        # Find and attack target
        target = self.get_nearest_target(battle_state.entities)
        self.target_id = target.id if target else None
        if target and self.can_attack_target(target) and self.attack_cooldown <= 0:
            # Call on_attack_start for all mechanics
            for mechanic in self.mechanics:
                mechanic.on_attack_start(self, target)

            # Check if this building uses projectiles
            if self._uses_projectiles():
                self._create_projectile(target, battle_state)
            else:
                # Direct attack
                self._deal_attack_damage(target, self.damage, battle_state)

            # Call on_attack_hit for all mechanics
            for mechanic in self.mechanics:
                mechanic.on_attack_hit(self, target)

            self.attack_cooldown = self.get_attack_interval_seconds()
            self.last_attack_time = 0.0  # Reset for visualization
    
    def _uses_projectiles(self) -> bool:
        """Check if this building uses projectiles for attacks"""
        return (self.card_stats and 
                hasattr(self.card_stats, 'projectile_data') and 
                self.card_stats.projectile_data is not None)
    
    def _create_projectile(self, target: 'Entity', battle_state: 'BattleState') -> None:
        """Create a projectile towards the target"""
        if not self.card_stats or not self.card_stats.projectile_data:
            # Fallback to direct attack if no projectile data
            # Call on_attack_start for all mechanics
            for mechanic in self.mechanics:
                mechanic.on_attack_start(self, target)

            target.take_damage(self.damage)

            # Call on_attack_hit for all mechanics
            for mechanic in self.mechanics:
                mechanic.on_attack_hit(self, target)
            return
        
        # Get projectile properties
        projectile_data = self.card_stats.projectile_data
        projectile_damage = self.damage  # Use entity's scaled damage instead of base projectile damage
        projectile_speed = projectile_data.get('speed', 500) / 60.0  # Convert from per-minute to per-second
        splash_radius = projectile_data.get('radius', 0) / 1000.0 if projectile_data.get('radius') else 0.0
        target_buff_data = projectile_data.get("targetBuffData") or {}
        slow_duration = projectile_data.get("buffTime", 0) / 1000.0
        slow_multiplier = 1.0 + (target_buff_data.get("speedMultiplier", 0) / 100.0)
        stun_duration = 0.0
        if (
            target_buff_data.get("speedMultiplier") == -100
            and target_buff_data.get("hitSpeedMultiplier") == -100
            and slow_duration > 0
        ):
            stun_duration = slow_duration
            slow_duration = 0.0
            slow_multiplier = 1.0
        tid_target = projectile_data.get("tidTarget", "TID_TARGETS_AIR_AND_GROUND")
        hits_air = "AIR" in tid_target
        hits_ground = ("GROUND" in tid_target) or ("BUILDINGS" in tid_target)
        if tid_target == "TID_TARGETS_GROUND":
            hits_air = False
            hits_ground = True
        crown_tower_damage_multiplier = max(
            0.0, 1.0 + (projectile_data.get("crownTowerDamagePercent", 0) / 100.0)
        )
        
        # Create projectile entity
        projectile = Projectile(
            id=battle_state.next_entity_id,
            position=Position(self.position.x, self.position.y),
            player_id=self.player_id,
            card_stats=self.card_stats,
            hitpoints=1,
            max_hitpoints=1,
            damage=projectile_damage,
            range=self.range,
            sight_range=1.0,
            target_position=Position(target.position.x, target.position.y),
            travel_speed=projectile_speed,
            splash_radius=splash_radius,
            source_name=self.card_stats.name if self.card_stats else "Unknown",
            stun_duration=stun_duration,
            slow_duration=slow_duration,
            slow_multiplier=max(0.0, slow_multiplier),
            knockback_distance=projectile_data.get("pushback", 0) / 1000.0,
            hits_air=hits_air,
            hits_ground=hits_ground,
            crown_tower_damage_multiplier=crown_tower_damage_multiplier,
        )
        
        battle_state.entities[projectile.id] = projectile
        battle_state.next_entity_id += 1


@dataclass
class Projectile(Entity):
    target_position: Position = field(default_factory=lambda: Position(0, 0))
    travel_speed: float = 5.0
    splash_radius: float = 0.0
    source_name: str = "Unknown"  # Name of unit that fired this projectile
    stun_duration: float = 0.0
    slow_duration: float = 0.0
    slow_multiplier: float = 1.0
    knockback_distance: float = 0.0
    hits_air: bool = True
    hits_ground: bool = True
    crown_tower_damage_multiplier: float = 1.0
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update projectile - move towards target"""
        if not self.is_alive:
            return
        
        # Move towards target
        distance = self.position.distance_to(self.target_position)
        if distance <= self.travel_speed * dt:
            # Reached target - deal damage
            self._deal_splash_damage(battle_state)
            self.is_alive = False
        else:
            self._move_towards(self.target_position, dt)
    
    def _move_towards(self, target_pos: Position, dt: float) -> None:
        """Move towards target position"""
        dx = target_pos.x - self.position.x
        dy = target_pos.y - self.position.y
        distance = (dx * dx + dy * dy) ** 0.5
        
        if distance > 0:
            move_distance = self.travel_speed * dt
            move_x = (dx / distance) * move_distance
            move_y = (dy / distance) * move_distance
            
            self.position.x += move_x
            self.position.y += move_y
    
    def _deal_splash_damage(self, battle_state: 'BattleState') -> None:
        """Deal damage to entities in splash radius using hitbox overlap detection"""
        for entity in list(battle_state.entities.values()):
            if entity.player_id == self.player_id or not entity.is_alive:
                continue

            is_air = getattr(entity, 'is_air_unit', False)
            if is_air and not self.hits_air:
                continue
            if (not is_air) and not self.hits_ground:
                continue
            
            # Use hitbox-based collision detection for more accurate splash damage
            if self._hitbox_overlaps_with_splash(entity):
                damage = self.damage
                if isinstance(entity, Building) and getattr(entity.card_stats, 'name', None) in {"Tower", "KingTower"}:
                    damage *= self.crown_tower_damage_multiplier
                entity.take_damage(damage)
                if self.stun_duration > 0:
                    entity.apply_stun(self.stun_duration)
                if self.slow_duration > 0 and self.slow_multiplier < 1.0:
                    entity.apply_slow(self.slow_duration, self.slow_multiplier)
                if self.knockback_distance > 0 and not isinstance(entity, Building):
                    self._apply_knockback(entity, battle_state)

    def _apply_knockback(self, entity: 'Entity', battle_state: 'BattleState') -> None:
        """Push entity away from impact center."""
        dx = entity.position.x - self.target_position.x
        dy = entity.position.y - self.target_position.y
        distance = math.hypot(dx, dy)
        if distance == 0:
            return
        new_position = Position(
            entity.position.x + (dx / distance) * self.knockback_distance,
            entity.position.y + (dy / distance) * self.knockback_distance,
        )
        if getattr(entity, "is_air_unit", False) or battle_state.is_ground_position_walkable(new_position, entity):
            entity.position = new_position
    
    def _hitbox_overlaps_with_splash(self, entity: 'Entity') -> bool:
        """Check if entity's hitbox overlaps with splash damage radius"""
        # Get entity collision radius (default to 0.5 tiles if not specified or None)
        if entity.card_stats and hasattr(entity.card_stats, 'collision_radius') and entity.card_stats.collision_radius is not None:
            entity_radius = entity.card_stats.collision_radius
        else:
            entity_radius = 0.5
        
        # Calculate distance between projectile impact and entity center
        distance = entity.position.distance_to(self.target_position)
        
        # Check if splash radius overlaps with entity hitbox
        return distance <= (self.splash_radius + entity_radius)




@dataclass
class AreaEffect(Entity):
    """Area effect spells that stay on the ground for a duration"""
    duration: float = 4.0
    freeze_effect: bool = False
    speed_multiplier: float = 1.0
    radius: float = 3.0
    time_alive: float = 0.0
    hits_air: bool = True
    hits_ground: bool = True
    crown_tower_damage_multiplier: float = 1.0
    building_damage_multiplier: float = 1.0
    
    # Tornado-specific properties
    pull_force: float = 0.0
    is_tornado: bool = False
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update area effect - apply effects and check duration"""
        if not self.is_alive:
            return
        
        self.time_alive += dt
        
        # Check if duration expired
        if self.time_alive >= self.duration:
            self.is_alive = False
            return
        
        # Apply effects to entities in radius
        for entity in list(battle_state.entities.values()):
            if entity.player_id == self.player_id or not entity.is_alive or entity == self:
                continue

            is_air = getattr(entity, 'is_air_unit', False)
            if is_air and not self.hits_air:
                continue
            if (not is_air) and not self.hits_ground:
                continue
            
            # Use hitbox-based collision detection  
            if self._hitbox_overlaps_with_radius(entity):
                distance = entity.position.distance_to(self.position)
                
                # Apply tornado pull effect
                if self.is_tornado and self.pull_force > 0:
                    self._apply_tornado_pull(entity, distance, dt, battle_state)
                
                if self.freeze_effect:
                    entity.apply_stun(max(dt, 0.1))
                    entity.apply_slow(max(dt, 0.1), 0.0)
                elif self.speed_multiplier < 1.0:
                    entity.apply_slow(max(dt, 0.25), self.speed_multiplier)
                
                # Apply damage over time (small damage each tick)
                if self.damage > 0:
                    damage = self.damage * dt
                    if isinstance(entity, Building):
                        damage *= self.building_damage_multiplier
                        if getattr(entity.card_stats, 'name', None) in {"Tower", "KingTower"}:
                            damage *= self.crown_tower_damage_multiplier
                    entity.take_damage(damage)

    def _apply_tornado_pull(self, entity: 'Entity', distance: float, dt: float, battle_state: 'BattleState') -> None:
        """Pull entity towards tornado center"""
        if distance == 0:
            return
        
        # Calculate pull vector towards tornado center
        dx = self.position.x - entity.position.x
        dy = self.position.y - entity.position.y
        
        # Normalize and apply pull force
        pull_distance = self.pull_force * dt
        
        # Don't pull past the center
        if pull_distance > distance:
            pull_distance = distance * 0.9  # Stop just short of center
        
        pull_x = (dx / distance) * pull_distance
        pull_y = (dy / distance) * pull_distance
        
        # Apply pull movement (air units can be pulled anywhere, ground units need walkable space)
        new_position = Position(entity.position.x + pull_x, entity.position.y + pull_y)
        
        if getattr(entity, 'is_air_unit', False) or battle_state.is_ground_position_walkable(new_position, entity):
            entity.position.x += pull_x
            entity.position.y += pull_y
    
    def _hitbox_overlaps_with_radius(self, entity: 'Entity') -> bool:
        """Check if entity's hitbox overlaps with area effect radius"""
        # Get entity collision radius (default to 0.5 tiles if not specified or None)
        if entity.card_stats and hasattr(entity.card_stats, 'collision_radius') and entity.card_stats.collision_radius is not None:
            entity_radius = entity.card_stats.collision_radius
        else:
            entity_radius = 0.5
        
        # Calculate distance between area center and entity center
        distance = entity.position.distance_to(self.position)
        
        # Check if area radius overlaps with entity hitbox
        return distance <= (self.radius + entity_radius)


@dataclass
class SpawnProjectile(Projectile):
    """Projectile that spawns units when it reaches target"""
    spawn_count: int = 3
    spawn_character: str = "Goblin"
    spawn_character_data: dict = None
    activation_delay: float = 0.0
    time_alive: float = 0.0
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update projectile - move towards target and spawn units on impact"""
        if not self.is_alive:
            return

        self.time_alive += dt
        if self.time_alive < self.activation_delay:
            return
        
        # Move towards target
        distance = self.position.distance_to(self.target_position)
        if distance <= self.travel_speed * dt:
            # Reached target - spawn units and deal splash damage
            self._spawn_units(battle_state)
            self._deal_splash_damage(battle_state)
            self.is_alive = False
        else:
            self._move_towards(self.target_position, dt)
    
    def _spawn_units(self, battle_state: 'BattleState') -> None:
        """Spawn units at target position"""
        import math
        import random
        
        if not self.spawn_character_data:
            return
        
        spawn_stats = troop_from_character_data(
            self.spawn_character,
            self.spawn_character_data,
            elixir=0,
            rarity=self.spawn_character_data.get("rarity", "Common"),
        )
        
        # Spawn units in a small radius around target
        spawn_radius = 1.0  # tiles
        
        for _ in range(self.spawn_count):
            # Random position around the target location
            angle = random.random() * 2 * math.pi
            distance = random.random() * spawn_radius
            spawn_x = self.target_position.x + distance * math.cos(angle)
            spawn_y = self.target_position.y + distance * math.sin(angle)
            
            # Create and spawn the unit
            battle_state._spawn_troop(Position(spawn_x, spawn_y), self.player_id, spawn_stats)


@dataclass
class RollingProjectile(Entity):
    """Rolling projectiles that spawn at location and roll forward (Log, Barbarian Barrel)"""
    travel_speed: float = 200.0
    projectile_range: float = 10.0  # tiles
    spawn_delay: float = 0.65  # seconds
    spawn_character: str = None
    spawn_character_data: dict = None
    radius_y: float = 0.6  # Height of rolling hitbox
    knockback_distance: float = 1.5
    # Optional custom direction (unit vector); used by Bowler boulder
    target_direction_x: Optional[float] = None
    target_direction_y: Optional[float] = None
    
    def __post_init__(self):
        super().__post_init__()
        # Use range field from Entity as rolling radius
        self.rolling_radius = self.range
    
    # State tracking
    time_alive: float = 0.0
    distance_traveled: float = 0.0
    hit_entities: set = field(default_factory=set)  # Track entities hit (can only hit once)
    has_spawned_character: bool = False
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update rolling projectile - wait for spawn delay, then roll forward"""
        if not self.is_alive:
            return
        
        self.time_alive += dt
        
        # Wait for spawn delay before starting to roll
        if self.time_alive < self.spawn_delay:
            return
        
        # Roll forward at constant speed
        roll_distance = self.travel_speed / 60.0 * dt  # Convert tiles/min to tiles/sec
        self.distance_traveled += roll_distance
        
        # Determine roll direction
        if self.target_direction_x is not None and self.target_direction_y is not None:
            # Use custom direction (for Bowler)
            self.position.x += self.target_direction_x * roll_distance
            self.position.y += self.target_direction_y * roll_distance
        else:
            # Default direction (towards enemy side for Log/Barbarian Barrel)
            if self.player_id == 0:  # Blue player rolls towards red side (positive Y)
                self.position.y += roll_distance
            else:  # Red player rolls towards blue side (negative Y)
                self.position.y -= roll_distance
        
        # Check if reached max range
        if self.distance_traveled >= self.projectile_range:
            # Spawn character if applicable (Barbarian Barrel)
            if self.spawn_character and not self.has_spawned_character:
                self._spawn_character(battle_state)
            self.is_alive = False
            return
        
        # Deal damage to entities in rectangular hitbox
        self._deal_rolling_damage(battle_state)
    
    def _deal_rolling_damage(self, battle_state: 'BattleState') -> None:
        """Deal damage to ground units in rolling path (rectangular hitbox)"""
        # Create a copy of entities list to avoid RuntimeError when dictionary changes during iteration
        entities_copy = list(battle_state.entities.values())
        for entity in entities_copy:
            if (entity.player_id == self.player_id or 
                not entity.is_alive or 
                entity.id in self.hit_entities or
                entity == self):
                continue
            
            # Skip air units (Log only hits ground)
            if getattr(entity, 'is_air_unit', False):
                continue
            
            # Check if entity is in rectangular rolling hitbox with entity collision radius
            if self._hitbox_overlaps_with_rolling_path(entity):
                # Hit the entity
                entity.take_damage(self.damage)
                self.hit_entities.add(entity.id)
                
                # Apply knockback effect (Log pushes units backward)
                self._apply_knockback(entity, battle_state)

    def _apply_knockback(self, entity: 'Entity', battle_state: 'BattleState') -> None:
        """Apply knockback effect - pushes unit away from Log and resets attack"""
        # Buildings cannot be knocked back or stunned; they only take damage
        if isinstance(entity, Building):
            return

        # Reset attack cooldown (stunned briefly)
        if hasattr(entity, 'attack_cooldown'):
            entity.attack_cooldown = max(entity.attack_cooldown, 0.5)
        
        # Physical knockback - push unit away from Log's rolling direction
        knockback_distance = self.knockback_distance  # tiles
        
        # Determine knockback direction based on movement direction
        if self.target_direction_x is not None and self.target_direction_y is not None:
            # Push along projectile's travel vector (Bowler angled push)
            candidate_x = entity.position.x + self.target_direction_x * knockback_distance
            candidate_y = entity.position.y + self.target_direction_y * knockback_distance
        else:
            if self.player_id == 0:  # Blue player Log rolling toward red side
                # Push units further toward red side (positive Y)
                candidate_x = entity.position.x
                candidate_y = entity.position.y + knockback_distance
            else:  # Red player Log rolling toward blue side
                # Push units further toward blue side (negative Y)
                candidate_x = entity.position.x
                candidate_y = entity.position.y - knockback_distance
        
        # Slight random horizontal displacement for realism
        import random
        horizontal_variance = random.uniform(-0.3, 0.3)
        candidate_x += horizontal_variance

        # Keep within arena bounds
        candidate_x = max(0.5, min(17.5, candidate_x))
        candidate_y = max(0.5, min(31.5, candidate_y))
        candidate = Position(candidate_x, candidate_y)
        if battle_state.is_ground_position_walkable(candidate, entity):
            entity.position = candidate
    
    def _hitbox_overlaps_with_rolling_path(self, entity: 'Entity') -> bool:
        """Check if entity's hitbox overlaps with rolling projectile path"""
        # Get entity collision radius (default to 0.5 tiles if not specified or None)
        if entity.card_stats and hasattr(entity.card_stats, 'collision_radius') and entity.card_stats.collision_radius is not None:
            entity_radius = entity.card_stats.collision_radius
        else:
            entity_radius = 0.5
        
        # Calculate distance components
        dx = abs(entity.position.x - self.position.x)
        dy = abs(entity.position.y - self.position.y)
        
        # Check if entity hitbox overlaps with rectangular rolling area
        return dx <= (self.rolling_radius + entity_radius) and dy <= (self.radius_y + entity_radius)
    
    def _spawn_character(self, battle_state: 'BattleState') -> None:
        """Spawn character at end of roll (Barbarian Barrel)"""
        if not self.spawn_character_data and not self.spawn_character:
            return
        
        # If we have a character name but no data, create default stats
        if not self.spawn_character_data and self.spawn_character:
            from .data import CardStats as CS
            from .arena import Position as Pos
            spawn_stats = CS(
                name=self.spawn_character,
                id=0, mana_cost=0, rarity="Common",
                hitpoints=742, damage=120, speed=60.0,
                range=0.7, sight_range=5.5, hit_speed=1500,
                deploy_time=1000, load_time=1000, collision_radius=0.5,
                attacks_ground=True, attacks_air=False,
                targets_only_buildings=False, target_type="TID_TARGETS_GROUND"
            )
            battle_state._spawn_troop(Pos(self.position.x, self.position.y), self.player_id, spawn_stats)
            self.has_spawned_character = True
            return
        
        import math

        spawn_stats = troop_from_character_data(
            self.spawn_character,
            self.spawn_character_data,
            elixir=0,
            rarity=self.spawn_character_data.get("rarity", "Common"),
        )
        
        # Spawn character at current position
        battle_state._spawn_troop(Position(self.position.x, self.position.y), self.player_id, spawn_stats)
        self.has_spawned_character = True


@dataclass
class TimedExplosive(Entity):
    """Entity that explodes after a countdown timer (death bombs, balloon bombs)"""
    explosion_timer: float = 3.0
    explosion_radius: float = 1.5
    explosion_damage: float = 600.0
    death_spawn_name: Optional[str] = None
    death_spawn_count: int = 0
    death_spawn_data: Optional[dict] = None
    time_alive: float = 0.0
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update timed explosive - countdown and explode"""
        if not self.is_alive:
            return
            
        self.time_alive += dt
        
        # Check if timer expired
        if self.time_alive >= self.explosion_timer:
            self._explode(battle_state)
            self.is_alive = False
    
    def _explode(self, battle_state: 'BattleState') -> None:
        """Deal explosion damage to entities in radius using hitbox collision"""
        for entity in list(battle_state.entities.values()):
            if entity.player_id == self.player_id or not entity.is_alive or entity == self:
                continue
            
            # Use hitbox-based collision detection for explosion
            if self._hitbox_overlaps_with_explosion(entity):
                entity.take_damage(self.explosion_damage)

        # Optional chained death spawn (e.g. Skeleton Barrel container -> Skeletons).
        if self.death_spawn_name and self.death_spawn_count > 0:
            self._spawn_death_units(battle_state)

    def _spawn_death_units(self, battle_state: 'BattleState') -> None:
        """Spawn units around this explosive when configured."""
        import math
        import random

        from .factory.dynamic_factory import troop_from_character_data, troop_from_values

        spawn_stats = battle_state.card_loader.get_card(self.death_spawn_name)
        if not spawn_stats and self.death_spawn_data:
            spawn_stats = troop_from_character_data(
                self.death_spawn_name,
                self.death_spawn_data,
                elixir=0,
                rarity=self.death_spawn_data.get("rarity", "Common"),
            )
        if not spawn_stats:
            spawn_stats = troop_from_values(
                self.death_spawn_name,
                hitpoints=100,
                damage=25,
                speed_tiles_per_min=60.0,
                range_tiles=1.0,
                sight_range_tiles=5.0,
                hit_speed_ms=1000,
                collision_radius_tiles=0.5,
            )

        for _ in range(self.death_spawn_count):
            angle = random.random() * 2 * math.pi
            distance = random.random() * 0.7
            spawn_x = self.position.x + distance * math.cos(angle)
            spawn_y = self.position.y + distance * math.sin(angle)
            battle_state._spawn_troop(Position(spawn_x, spawn_y), self.player_id, spawn_stats)
    
    def _hitbox_overlaps_with_explosion(self, entity: 'Entity') -> bool:
        """Check if entity's hitbox overlaps with explosion radius"""
        # Get entity collision radius (default to 0.5 tiles if not specified or None)
        if entity.card_stats and hasattr(entity.card_stats, 'collision_radius') and entity.card_stats.collision_radius is not None:
            entity_radius = entity.card_stats.collision_radius
        else:
            entity_radius = 0.5
        
        # Calculate distance between explosion center and entity center
        distance = entity.position.distance_to(self.position)
        
        # Check if explosion radius overlaps with entity hitbox
        return distance <= (self.explosion_radius + entity_radius)


@dataclass
class Graveyard(Entity):
    """Entity that periodically spawns skeletons in an area"""
    spawn_interval: float = 0.5
    max_skeletons: int = 20
    spawn_radius: float = 2.5
    duration: float = 10.0
    skeleton_data: dict = None
    time_alive: float = 0.0
    time_since_spawn: float = 0.0
    skeletons_spawned: int = 0
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update graveyard - spawn skeletons periodically"""
        if not self.is_alive:
            return
            
        self.time_alive += dt
        self.time_since_spawn += dt
        
        # Check if duration expired
        if self.time_alive >= self.duration:
            self.is_alive = False
            return
        
        # Spawn skeleton if it's time and haven't reached max
        if (self.time_since_spawn >= self.spawn_interval and 
            self.skeletons_spawned < self.max_skeletons):
            self._spawn_skeleton(battle_state)
            self.time_since_spawn = 0.0
            self.skeletons_spawned += 1
    
    def _spawn_skeleton(self, battle_state: 'BattleState') -> None:
        """Spawn a skeleton at random position in radius"""
        import math
        import random
        
        if not self.skeleton_data:
            return
        
        # Create skeleton stats
        skeleton_stats = troop_from_character_data(
            "Skeleton",
            self.skeleton_data,
            elixir=0,
            rarity=self.skeleton_data.get("rarity", "Common"),
        )
        
        # Random position within spawn radius
        angle = random.random() * 2 * math.pi
        distance = random.random() * self.spawn_radius
        spawn_x = self.position.x + distance * math.cos(angle)
        spawn_y = self.position.y + distance * math.sin(angle)
        
        # Spawn the skeleton
        battle_state._spawn_troop(Position(spawn_x, spawn_y), self.player_id, skeleton_stats)
