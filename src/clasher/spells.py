from dataclasses import dataclass
from collections.abc import Iterator, Mapping
from threading import RLock
from typing import Dict, List, TYPE_CHECKING
from abc import ABC, abstractmethod

from .entities import Entity, Projectile, Troop, AreaEffect, SpawnProjectile, RollingProjectile, TimedExplosive, Graveyard
from .arena import Position
from .unit_traits import is_above_ground_surface, is_airborne_target
from .kinematics import (
    logic_speed_to_tiles_per_second,
    logic_units_to_tiles,
    normalized_vector_logic_units,
    tiles_to_logic_units,
    trunc_div,
)
from .logic_math import native_percent_damage, rotate_logic_vector

if TYPE_CHECKING:
    from .battle import BattleState


@dataclass
class Spell(ABC):
    """Base class for spell effects"""
    name: str
    mana_cost: int
    radius: float = 0.0
    damage: float = 0.0
    requires_territory: bool = False
    requires_walkable_target: bool = False
    
    @abstractmethod
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Cast the spell at target position"""
        pass

    def _get_launch_position(self, battle_state: 'BattleState', player_id: int) -> Position:
        """Return the owner-relative King Tower launch point for a spell payload."""
        tower_pos = (
            battle_state.arena.BLUE_KING_TOWER
            if player_id == 0
            else battle_state.arena.RED_KING_TOWER
        )
        return Position(tower_pos.x, tower_pos.y)
    
    def _hitbox_overlaps_with_area(self, entity: 'Entity', area_center: Position) -> bool:
        """Check if entity's hitbox overlaps with spell area using collision detection"""
        return entity.intersects_native_area(area_center, self.radius)


@dataclass
class DirectDamageSpell(Spell):
    """Spells that deal instant damage in an area"""
    stun_duration: float = 0.0
    slow_duration: float = 0.0  
    slow_multiplier: float = 1.0
    knockback_distance: float = 0.0
    knockback_ignores_mass: bool = False
    hits_air: bool = True
    hits_ground: bool = True
    affects_hidden: bool = False
    crown_tower_damage_multiplier: float = 1.0
    crown_tower_damage: float | None = None
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Deal damage to all enemies in radius"""
        targets: list[tuple[Entity, float]] = []
        for entity in list(battle_state.entities.values()):
            if (
                entity.player_id == player_id
                or not entity.is_alive
                or getattr(entity, "entity_kind", 4) in {2, 3}
            ):
                continue

            if self.hits_ground and not self.hits_air and is_above_ground_surface(entity):
                continue

            is_air = is_airborne_target(entity)
            if is_air and not self.hits_air:
                continue
            if (not is_air) and not self.hits_ground:
                continue
            
            # Use hitbox-based collision detection for more accurate damage
            if self._hitbox_overlaps_with_area(entity, target_pos):
                if not entity.can_receive_area_damage(
                    self.name,
                    affects_hidden=self.affects_hidden,
                ):
                    continue
                damage = self.damage
                if getattr(entity, "entity_kind", 4) == 1:
                    name = getattr(getattr(entity, "card_stats", None), "name", None)
                    if name in {"Tower", "KingTower"}:
                        damage = (
                            self.crown_tower_damage
                            if self.crown_tower_damage is not None
                            else native_percent_damage(
                                damage,
                                self.crown_tower_damage_multiplier,
                            )
                        )
                targets.append((entity, damage))

        # Native area resolution performs its complete damage/knockback pass
        # before a fresh status pass. Death-spawn children created by lethal
        # damage are therefore eligible for the following stun/slow scan, but
        # never for another copy of the same damage.
        for entity, damage in targets:
            entity.take_damage(
                damage,
                source_kind=self.name,
                affects_hidden=self.affects_hidden,
            )
            if self.knockback_distance > 0 and getattr(entity, "entity_kind", 4) != 1:
                from .mechanics.shared.knockback import apply_radial_knockback

                apply_radial_knockback(
                    entity,
                    battle_state,
                    target_pos,
                    self.knockback_distance,
                    source_kind=self.name,
                    ignores_mass=self.knockback_ignores_mass,
                )

        status_targets = []
        if self.stun_duration > 0 or self.slow_duration > 0:
            for entity in list(battle_state.entities.values()):
                if (
                    entity.player_id == player_id
                    or not entity.is_alive
                    or getattr(entity, "entity_kind", 4) in {2, 3}
                ):
                    continue
                if self.hits_ground and not self.hits_air and is_above_ground_surface(entity):
                    continue
                is_air = is_airborne_target(entity)
                if (is_air and not self.hits_air) or ((not is_air) and not self.hits_ground):
                    continue
                if (
                    not self._hitbox_overlaps_with_area(entity, target_pos)
                    or not entity.can_receive_effect(
                        self.name,
                        affects_hidden=self.affects_hidden,
                    )
                ):
                    continue
                status_targets.append(entity)

        for entity in status_targets:
            if self.stun_duration > 0:
                entity.apply_stun(
                    self.stun_duration,
                    source_kind=self.name,
                    affects_hidden=self.affects_hidden,
                )
            if self.slow_duration > 0:
                entity.apply_slow(
                    self.slow_duration,
                    self.slow_multiplier,
                    source_kind=self.name,
                    affects_hidden=self.affects_hidden,
                )

        return bool(targets or status_targets)


@dataclass  
class ProjectileSpell(Spell):
    """Spells that fire projectiles"""
    travel_speed: float = 500.0
    stun_duration: float = 0.0
    slow_duration: float = 0.0
    slow_multiplier: float = 1.0
    knockback_distance: float = 0.0
    knockback_ignores_mass: bool = False
    hits_air: bool = True
    hits_ground: bool = True
    crown_tower_damage_multiplier: float = 1.0
    crown_tower_damage: float | None = None
    damage_waves: int = 1
    damage_wave_interval: float = 0.0
    multiple_projectiles: int = 1
    spread_radius: float = 0.0
    projectile_pattern: str = "native_radial"
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Fire a projectile toward target position"""
        launch_pos = self._get_launch_position(battle_state, player_id)

        projectile_count = max(1, int(self.multiple_projectiles))
        wave_count = max(1, int(self.damage_waves))
        if projectile_count == 1:
            wave_count = 1

        for wave_index in range(wave_count):
            impact_positions = self._projectile_positions(
                battle_state,
                player_id,
                target_pos,
                projectile_count,
            )
            # Native linked projectile groups share their already-hit set.
            # Overlapping circles in one volley therefore damage an object
            # once, while the next wave gets a fresh group.
            damage_group = set() if projectile_count > 1 else None
            for impact_position in impact_positions:
                projectile = Projectile(
                    id=battle_state.next_entity_id,
                    position=Position(launch_pos.x, launch_pos.y),
                    player_id=player_id,
                    card_stats=None,
                    hitpoints=1,
                    max_hitpoints=1,
                    damage=self.damage,
                    range=0,
                    sight_range=0,
                    target_position=impact_position,
                    travel_speed=self.travel_speed,
                    splash_radius=self.radius,
                    stun_duration=self.stun_duration,
                    slow_duration=self.slow_duration,
                    slow_multiplier=self.slow_multiplier,
                    knockback_distance=self.knockback_distance,
                    knockback_ignores_mass=self.knockback_ignores_mass,
                    hits_air=self.hits_air,
                    hits_ground=self.hits_ground,
                    crown_tower_damage_multiplier=self.crown_tower_damage_multiplier,
                    crown_tower_damage=self.crown_tower_damage,
                    damage_waves=(
                        self.damage_waves
                        if projectile_count == 1
                        else 1
                    ),
                    damage_wave_interval=self.damage_wave_interval,
                    launch_delay=wave_index * self.damage_wave_interval,
                    damage_group_hit_entity_ids=damage_group,
                )
                projectile.spell_name = self.name
                battle_state.entities[projectile.id] = projectile
                battle_state.next_entity_id += 1
        return True

    def _projectile_positions(
        self,
        battle_state: 'BattleState',
        player_id: int,
        target_pos: Position,
        projectile_count: int,
    ) -> list[Position]:
        """Generate native multiple-projectile spell destinations."""
        if projectile_count <= 1:
            return [Position(target_pos.x, target_pos.y)]
        if self.projectile_pattern == "grouped_ring":
            positions = self._grouped_ring_positions(
                battle_state,
                target_pos,
                projectile_count,
            )
        else:
            positions = self._native_radial_positions(
                battle_state,
                target_pos,
                projectile_count,
            )
        if player_id == 0:
            return positions
        # Spell summoning works in owner-relative logic coordinates. Convert
        # the generated offsets back to world space for the upper player.
        return [
            Position(
                target_pos.x - (position.x - target_pos.x),
                target_pos.y - (position.y - target_pos.y),
            )
            for position in positions
        ]

    def _native_radial_positions(
        self,
        battle_state: 'BattleState',
        target_pos: Position,
        projectile_count: int,
    ) -> list[Position]:
        """Generic spell spread: center plus random radii on fixed spokes."""
        radius_units = max(0, tiles_to_logic_units(self.spread_radius))
        inner_units = radius_units >> 2
        span_units = max(0, radius_units - inner_units)
        angle_step = trunc_div(360, projectile_count)
        positions = [Position(target_pos.x, target_pos.y)]
        for index in range(1, projectile_count):
            radial_units = (
                battle_state.rng.randrange(span_units) + inner_units
                if span_units > 0
                else 0
            )
            positions.append(
                self._offset_position(
                    target_pos,
                    radial_units,
                    angle_step * index,
                )
            )
        return positions

    def _grouped_ring_positions(
        self,
        battle_state: 'BattleState',
        target_pos: Position,
        projectile_count: int,
    ) -> list[Position]:
        """Linked center-and-ring spread used by grouped arrow volleys."""
        radius_units = max(0, tiles_to_logic_units(self.spread_radius))
        projectile_radius_units = max(0, tiles_to_logic_units(self.radius))
        jitter_units = trunc_div(projectile_radius_units * 60, 100)
        ring_units = max(0, radius_units - jitter_units)
        clamp_units = trunc_div(radius_units * 90, 100)
        angle_step = trunc_div(360, projectile_count - 1)
        positions: list[Position] = []

        for index in range(projectile_count):
            if index == 0:
                base_x_units = 0
                base_y_units = 0
            else:
                base_x_units, base_y_units = self._rotated_vector_units(
                    ring_units,
                    0,
                    angle_step * (index - 1),
                )

            # The client rotates a (0, 60%-of-projectile-radius) vector by
            # rand(359) for every member of every wave, then clamps the
            # resulting destination to 90% of the enclosing spell radius.
            jitter_angle = battle_state.rng.randrange(359)
            jitter_x_units, jitter_y_units = self._rotated_vector_units(
                0,
                jitter_units,
                jitter_angle,
            )
            offset_x_units = base_x_units + jitter_x_units
            offset_y_units = base_y_units + jitter_y_units
            distance_squared = (
                offset_x_units * offset_x_units
                + offset_y_units * offset_y_units
            )
            if (
                clamp_units > 0
                and distance_squared > clamp_units * clamp_units
            ):
                offset_x_units, offset_y_units = normalized_vector_logic_units(
                    offset_x_units,
                    offset_y_units,
                    clamp_units,
                )
            positions.append(
                Position(
                    target_pos.x + logic_units_to_tiles(offset_x_units),
                    target_pos.y + logic_units_to_tiles(offset_y_units),
                )
            )
        return positions

    @staticmethod
    def _rotated_vector_units(
        x_units: int,
        y_units: int,
        angle_degrees: int,
    ) -> tuple[int, int]:
        return rotate_logic_vector(x_units, y_units, angle_degrees)

    @classmethod
    def _offset_position(
        cls,
        origin: Position,
        radial_units: int,
        angle_degrees: int,
    ) -> Position:
        offset_x_units, offset_y_units = cls._rotated_vector_units(
            radial_units,
            0,
            angle_degrees,
        )
        return Position(
            origin.x + logic_units_to_tiles(offset_x_units),
            origin.y + logic_units_to_tiles(offset_y_units),
        )

@dataclass
class AreaEffectSpell(Spell):
    """Spells that create area effects on the ground with duration"""
    duration: float = 4.0  # seconds
    freeze_effect: bool = False
    speed_multiplier: float = 1.0
    hits_air: bool = True
    hits_ground: bool = True
    affects_hidden: bool = False
    crown_tower_damage_multiplier: float = 1.0
    building_damage_multiplier: float = 1.0
    crown_tower_damage: float | None = None
    building_damage: float | None = None
    damage_tick_interval: float = 0.0
    initial_damage_delay: float | None = None
    max_damage_ticks: int = 0
    damage_on_spawn: bool = False
    slows_attack_speed: bool = True
    slows_spawn_speed: bool = True
    slow_refresh_duration: float = 0.25
    effect_tick_interval: float = 0.05
    cap_buff_time_to_effect: bool = False
    target_local_damage: bool = False
    periodic_damage_buff_duration: float = 0.0
    periodic_damage_controlled_by_parent: bool = False
    
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
            speed_multiplier=self.speed_multiplier,
            radius=self.radius,
            hits_air=self.hits_air,
            hits_ground=self.hits_ground,
            affects_hidden=self.affects_hidden,
            crown_tower_damage_multiplier=self.crown_tower_damage_multiplier,
            building_damage_multiplier=self.building_damage_multiplier,
            crown_tower_damage=self.crown_tower_damage,
            building_damage=self.building_damage,
            damage_tick_interval=self.damage_tick_interval,
            initial_damage_delay=self.initial_damage_delay,
            max_damage_ticks=self.max_damage_ticks,
            damage_on_spawn=self.damage_on_spawn,
            slows_attack_speed=self.slows_attack_speed,
            slows_spawn_speed=self.slows_spawn_speed,
            slow_refresh_duration=self.slow_refresh_duration,
            effect_tick_interval=self.effect_tick_interval,
            cap_buff_time_to_effect=self.cap_buff_time_to_effect,
            target_local_damage=self.target_local_damage,
            periodic_damage_buff_duration=self.periodic_damage_buff_duration,
            periodic_damage_controlled_by_parent=(
                self.periodic_damage_controlled_by_parent
            ),
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
    spawn_radius: float | None = None
    spawn_deploy_delay: float | None = None
    spawn_const_priority: bool = False
    
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
            spawn_character_data=self.spawn_character_data,
            spawn_radius=self.spawn_radius,
            spawn_deploy_delay_override=self.spawn_deploy_delay,
            spawn_const_priority=self.spawn_const_priority,
            crown_tower_damage_multiplier=self.crown_tower_damage_multiplier,
            crown_tower_damage=self.crown_tower_damage,
        )
        
        # Add spell name for visualization
        projectile.spell_name = self.name
        
        battle_state.entities[battle_state.next_entity_id] = projectile
        battle_state.next_entity_id += 1
        return True


@dataclass
class RoyalDeliverySpell(Spell):
    """Delayed impact spell that deals area damage and spawns a recruit."""
    impact_delay: float = 2.0
    travel_speed: float = logic_speed_to_tiles_per_second(5000.0)
    spawn_count: int = 1
    spawn_character: str = "DeliveryRecruit"
    spawn_character_data: dict = None
    spawn_deploy_delay: float = 0.25
    crown_tower_damage_multiplier: float = 1.0
    crown_tower_damage: float | None = None
    ignore_buildings: bool = False

    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        projectile = SpawnProjectile(
            id=battle_state.next_entity_id,
            position=Position(target_pos.x, target_pos.y),
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
            spawn_character_data=self.spawn_character_data,
            spawn_radius=0.0,
            activation_delay=self.impact_delay,
            spawn_deploy_delay_override=self.spawn_deploy_delay,
            hits_air=True,
            hits_ground=True,
            crown_tower_damage_multiplier=self.crown_tower_damage_multiplier,
            crown_tower_damage=self.crown_tower_damage,
            ignore_buildings=self.ignore_buildings,
        )
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
        
        for entity in list(battle_state.entities.values()):
            if entity.player_id != player_id or not entity.is_alive:
                continue
            
            distance = entity.position.distance_to(target_pos)
            if distance <= self.radius + 1e-9:
                # Apply buff effects
                if hasattr(entity, 'speed'):
                    entity.speed *= self.speed_multiplier
                if hasattr(entity, 'damage'):
                    entity.damage *= self.damage_multiplier
                entity.attack_speed_buff_multiplier = max(
                    getattr(entity, "attack_speed_buff_multiplier", 1.0),
                    self.speed_multiplier,
                )
                targets_hit += 1
        
        return targets_hit > 0


@dataclass
class FreezeSpell(Spell):
    """Spells that freeze enemies"""
    freeze_duration: float = 3.0  # seconds
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Freeze enemies in radius"""
        targets_hit = 0
        
        for entity in list(battle_state.entities.values()):
            if entity.player_id == player_id or not entity.is_alive:
                continue
            
            distance = entity.position.distance_to(target_pos)
            if distance <= self.radius + 1e-9:
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
        for entity in list(battle_state.entities.values()):
            if entity.player_id != player_id or not entity.is_alive:
                continue
            
            distance = entity.position.distance_to(target_pos)
            if distance <= self.radius + 1e-9:
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
        
        for entity in list(battle_state.entities.values()):
            if entity.player_id != player_id or not entity.is_alive:
                continue
            
            distance = entity.position.distance_to(target_pos)
            if distance <= self.radius + 1e-9:
                # Heal the unit
                current_hp = entity.hitpoints
                max_hp = entity.max_hitpoints
                entity.hitpoints = min(current_hp + self.heal_amount, max_hp)
                if entity.hitpoints != current_hp:
                    battle_state.mark_win_conditions_dirty_if_crown(entity)
                targets_hit += 1
        
        return targets_hit > 0


@dataclass
class RollingProjectileSpell(Spell):
    """Spells that spawn at location and roll forward (Log, Barbarian Barrel)"""
    casting_speed: float = 6.0  # tiles per second before the rolling payload appears
    casting_min_distance: float = 0.0
    travel_speed: float = 200.0
    projectile_range: float = 10.0  # tiles
    spawn_character: str = None  # For Barbarian Barrel
    spawn_character_data: dict = None
    spawn_deploy_delay: float | None = None
    radius_y: float = 0.6  # Height of rolling hitbox
    knockback_distance: float = 1.5
    knockback_ignores_mass: bool = False
    crown_tower_damage_multiplier: float = 1.0
    crown_tower_damage: float | None = None
    
    def cast(self, battle_state: 'BattleState', player_id: int, target_pos: Position) -> bool:
        """Spawn rolling projectile at target position"""
        launch_pos = self._get_launch_position(battle_state, player_id)
        casting_distance = max(
            launch_pos.distance_to(target_pos),
            self.casting_min_distance,
        )
        casting_delay = casting_distance / max(
            self.casting_speed,
            1e-9,
        )
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
            spawn_delay=casting_delay,
            spawn_character=self.spawn_character,
            spawn_character_data=self.spawn_character_data,
            spawn_deploy_delay_override=self.spawn_deploy_delay,
            radius_y=self.radius_y,
            knockback_distance=self.knockback_distance,
            knockback_ignores_mass=self.knockback_ignores_mass,
            crown_tower_damage_multiplier=self.crown_tower_damage_multiplier,
            crown_tower_damage=self.crown_tower_damage,
        )
        
        # Add spell name for visualization
        rolling_projectile.spell_name = self.name
        
        battle_state.entities[battle_state.next_entity_id] = rolling_projectile
        battle_state.next_entity_id += 1
        return True


@dataclass
class TornadoSpell(Spell):
    """Spell that pulls enemies towards center and deals damage over time"""
    attract_percentage: float = 360.0
    push_speed_factor: float = 100.0
    damage_per_hit: float = 35.0
    duration: float = 3.0
    hits_air: bool = True
    hits_ground: bool = True
    affects_hidden: bool = False
    crown_tower_damage_multiplier: float = 1.0
    crown_tower_damage: float | None = None
    damage_tick_interval: float = 0.55
    initial_damage_delay: float = 0.6
    max_damage_ticks: int = 1
    effect_tick_interval: float = 0.05
    buff_duration: float = 0.5
    controlled_by_parent: bool = True
    
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
            damage=self.damage_per_hit,
            range=self.radius,
            sight_range=self.radius,
            duration=self.duration,
            freeze_effect=False,
            radius=self.radius,
            hits_air=self.hits_air,
            hits_ground=self.hits_ground,
            affects_hidden=self.affects_hidden,
            crown_tower_damage_multiplier=self.crown_tower_damage_multiplier,
            crown_tower_damage=self.crown_tower_damage,
            damage_tick_interval=self.damage_tick_interval,
            initial_damage_delay=self.initial_damage_delay,
            max_damage_ticks=0,
            damage_on_spawn=False,
            effect_tick_interval=self.effect_tick_interval,
            target_local_damage=True,
            periodic_damage_buff_duration=self.buff_duration,
            periodic_damage_controlled_by_parent=self.controlled_by_parent,
        )
        
        # Add tornado-specific properties
        tornado.spell_name = self.name
        tornado.attract_percentage = self.attract_percentage
        tornado.push_speed_factor = self.push_speed_factor
        tornado.is_tornado = True
        
        battle_state.entities[battle_state.next_entity_id] = tornado
        battle_state.next_entity_id += 1
        return True


@dataclass
class GraveyardSpell(Spell):
    """Spell that spawns skeletons periodically in an area"""
    spawn_interval: float = 0.5
    initial_spawn_delay: float = 1.2
    spawn_deadlines: tuple[float, ...] = ()
    max_skeletons: int = 12
    duration: float = 9.0
    spawn_offsets: tuple[tuple[float, float], ...] = ()
    mirror_pattern_x_at_center: bool = False
    orient_pattern_y_by_player: bool = False
    spawn_deploy_delay_override: float | None = 0.5
    spawn_character: str = "Skeleton"
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
            initial_spawn_delay=self.initial_spawn_delay,
            spawn_deadlines=self.spawn_deadlines,
            max_skeletons=self.max_skeletons,
            spawn_radius=self.radius,
            duration=self.duration,
            spawn_offsets=self.spawn_offsets,
            mirror_pattern_x_at_center=self.mirror_pattern_x_at_center,
            orient_pattern_y_by_player=self.orient_pattern_y_by_player,
            spawn_deploy_delay_override=self.spawn_deploy_delay_override,
            spawn_character=self.spawn_character,
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
FIREBALL = ProjectileSpell("Fireball", 4, radius=250.0, damage=572, travel_speed=logic_speed_to_tiles_per_second(600.0))
ZAP = DirectDamageSpell("Zap", 2, radius=250.0, damage=159, stun_duration=0.5)
LIGHTNING = DirectDamageSpell("Lightning", 6, radius=350.0, damage=864, stun_duration=0.5)

# Projectile spell speeds are serialized distance per 50 ms logic tick.
ROCKET = ProjectileSpell("Rocket", 6, radius=2000.0/1000.0, damage=580, travel_speed=logic_speed_to_tiles_per_second(350.0))
GOBLIN_BARREL = SpawnProjectileSpell(
    "GoblinBarrel", 3, 
    radius=1500.0/1000.0, 
    damage=0, 
    travel_speed=logic_speed_to_tiles_per_second(400.0),
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
    },
    spawn_deploy_delay=1.1,
    spawn_const_priority=True,
)

# Area effect spells that stay on ground
FREEZE = AreaEffectSpell("Freeze", 4, radius=3000.0/1000.0, damage=45, duration=4.0, freeze_effect=True)
RAGE = BuffSpell("Rage", 2, radius=3000.0, damage=0, buff_duration=6.0, speed_multiplier=1.5, damage_multiplier=1.4)
MIRROR = DirectDamageSpell("Mirror", 3, radius=0.0, damage=0)  # Special case - handled in battle logic
POISON = DirectDamageSpell("Poison", 4, radius=3000.0, damage=78)  # Damage over time
GRAVEYARD = GraveyardSpell("Graveyard", 5, radius=2.5, damage=0, spawn_interval=0.5, max_skeletons=20, duration=10.0)
LOG = ProjectileSpell("Log", 2, radius=250.0, damage=240, travel_speed=logic_speed_to_tiles_per_second(1200.0))
TORNADO = TornadoSpell(
    "Tornado",
    3,
    radius=5.5,
    damage=0,
    attract_percentage=360.0,
    push_speed_factor=100.0,
    damage_per_hit=84.0,
    duration=1.05,
    crown_tower_damage=25.0,
)
EARTHQUAKE = DirectDamageSpell("Earthquake", 3, radius=3000.0/1000.0, damage=332, slow_duration=3.0, slow_multiplier=0.5)
BARB_LOG = ProjectileSpell("BarbLog", 2, radius=250.0/1000.0, damage=240, travel_speed=logic_speed_to_tiles_per_second(1200.0))
HEAL = HealSpell("Heal", 3, radius=3000.0/1000.0, damage=0, heal_amount=400.0)
SNOWBALL = DirectDamageSpell("Snowball", 2, radius=250.0/1000.0, damage=0, slow_duration=2.5, slow_multiplier=0.65)
ROYAL_DELIVERY = RoyalDeliverySpell("RoyalDelivery", 3, radius=3.0, damage=171)
GLOBAL_CLONE = DirectDamageSpell("GlobalClone", 3, radius=0.0, damage=0)  # Special case
GOBLIN_PARTY_ROCKET = ProjectileSpell("GoblinPartyRocket", 4, radius=250.0, damage=0, travel_speed=logic_speed_to_tiles_per_second(1000.0))
WARM_SPELL = DirectDamageSpell("WarmSpell", 0, radius=0.0, damage=0)  # Special case
GLOBAL_LIGHTNING = DirectDamageSpell("GlobalLightning", 6, radius=3000.0, damage=1440)
DARK_MAGIC = DirectDamageSpell("DarkMagic", 4, radius=3000.0, damage=0)  # Special effect
GOBLIN_CURSE = DirectDamageSpell("GoblinCurse", 3, radius=3000.0, damage=0)  # Special effect
MERGE_MAIDEN = DirectDamageSpell("MergeMaiden", 4, radius=0.0, damage=0)  # Special case

# Load spells dynamically from JSON
def _load_dynamic_spell_registry() -> Dict[str, Spell]:
    """Load spells dynamically from gamedata.json."""
    try:
        from .dynamic_spells import load_dynamic_spells
        registry = load_dynamic_spells()
        from .card_aliases import CARD_NAME_ALIASES
        for alias, target in CARD_NAME_ALIASES.items():
            if alias in registry:
                continue
            if target in registry:
                registry[alias] = registry[target]
        return registry
    except Exception as e:
        raise RuntimeError("Could not load serialized spell registry") from e


class _LazySpellRegistry(Mapping[str, Spell]):
    """Read-only spell registry that is independent of module import order.

    ``dynamic_spells`` builds concrete ``Spell`` subclasses declared in this
    module, so eagerly loading it while ``spells`` itself imports creates a
    cycle when callers import ``dynamic_spells`` first. Delaying only the data
    load keeps the type definitions available in either order and still
    exposes an ordinary mapping to every runtime caller.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, Spell] | None = None
        self._lock = RLock()

    def _get_registry(self) -> Dict[str, Spell]:
        if self._registry is None:
            with self._lock:
                if self._registry is None:
                    self._registry = _load_dynamic_spell_registry()
        return self._registry

    def __getitem__(self, key: str) -> Spell:
        return self._get_registry()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._get_registry())

    def __len__(self) -> int:
        return len(self._get_registry())


SPELL_REGISTRY: Mapping[str, Spell] = _LazySpellRegistry()
