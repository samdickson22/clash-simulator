import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..mechanic_base import BaseMechanic
from ...unit_traits import is_above_ground_surface, is_airborne_target
from ...logic_math import spawn_target_distance_discount_sq_units

if TYPE_CHECKING:
    from ...battle import BattleState


@dataclass
class DeathDamage(BaseMechanic):
    """Mechanic that deals area damage when entity dies"""
    radius_tiles: float
    damage: int
    knockback_distance: float = 0.0
    hits_air: bool = True
    hits_ground: bool = True
    scaled_damage: float = field(init=False, default=0.0)

    def on_attach(self, entity) -> None:
        scaler = getattr(getattr(entity, "card_stats", None), "get_scaled_stat", None)
        self.scaled_damage = float(scaler(self.damage) if callable(scaler) else self.damage)

    def on_death(self, entity) -> None:
        """Deal area damage at death position"""
        if not hasattr(entity, 'battle_state'):
            return

        battle_state = entity.battle_state
        source_kind = getattr(getattr(entity, "card_stats", None), "name", None)

        if getattr(battle_state, "debug_logs", False):
            print(
                f"[Mechanic] DeathDamage triggered by {getattr(entity.card_stats, 'name', 'Unknown')} "
                f"at ({entity.position.x:.1f},{entity.position.y:.1f}) radius={self.radius_tiles} dmg={self.scaled_damage}"
            )

        # Commit the whole nova before resolving any victim's death effects.
        from ...arena import Position

        impact_position = Position(entity.position.x, entity.position.y)
        targets = []
        for target in list(battle_state.entities.values()):
            if target.player_id == entity.player_id or not target.is_alive:
                continue
            if getattr(target, "entity_kind", 4) in {2, 3}:
                continue
            if self.hits_ground and not self.hits_air and is_above_ground_surface(target):
                continue
            is_air = is_airborne_target(target)
            if (is_air and not self.hits_air) or ((not is_air) and not self.hits_ground):
                continue

            if target.intersects_native_area(
                impact_position,
                self.radius_tiles,
            ):
                if not target.can_receive_area_damage(
                    source_kind,
                    source_entity=entity,
                ):
                    continue
                targets.append(target)

        for target in targets:
            target.take_damage(self.scaled_damage, source_kind=source_kind)
            if target.is_alive and self.knockback_distance > 0:
                from .knockback import apply_radial_knockback

                apply_radial_knockback(
                    target,
                    battle_state,
                    impact_position,
                    self.knockback_distance,
                    source_kind=source_kind,
                )


@dataclass
class DeathSpawn(BaseMechanic):
    """Mechanic that spawns units when entity dies"""
    unit_name: str
    count: int
    radius_tiles: float = 0.0
    min_radius_tiles: float = 0.0
    radial_pushback: bool = False
    spawn_const_priority: bool = False
    deploy_time_ms: int = 0
    unit_data: dict | None = None

    def on_death(self, entity) -> None:
        """Spawn units around death position"""
        if not hasattr(entity, 'battle_state'):
            return

        battle_state = entity.battle_state
        inherited_freeze_remaining = max(
            0.0,
            float(getattr(entity, "freeze_expiry_time", 0.0) or 0.0)
            - battle_state.time,
        )

        if getattr(battle_state, "debug_logs", False):
            print(
                f"[Mechanic] DeathSpawn triggered by {getattr(entity.card_stats, 'name', 'Unknown')} "
                f"-> {self.count}x {self.unit_name}"
            )

        from ...arena import Position
        from ...entities import TimedExplosive
        from ...factory.dynamic_factory import troop_from_character_data

        # Bomb-style death spawns (e.g., BalloonBomb, BombTowerBomb) become timed explosives.
        if self.unit_data and self.unit_data.get("deathDamage") is not None and not self.unit_data.get("hitpoints"):
            raw_explosion_damage = self.unit_data.get("deathDamage", 0)
            scaler = getattr(getattr(entity, "card_stats", None), "get_scaled_stat", None)
            explosion_damage = float(
                scaler(raw_explosion_damage) if callable(scaler) else raw_explosion_damage
            )
            explosion_timer = max(0.1, (self.unit_data.get("deployTime", 1000) or 1000) / 1000.0)
            raw_explosion_radius = (
                self.unit_data.get("deathDamageRadius")
                or self.unit_data.get("deathRadius")
                or 2000
            )
            explosion_radius = float(raw_explosion_radius) / 1000.0
            spawn_data = self.unit_data.get("deathSpawnCharacterData") or {}
            spawn_name = spawn_data.get("name") or self.unit_data.get("deathSpawnCharacter")
            spawn_count = int(self.unit_data.get("deathSpawnCount", 0) or 0)
            for _ in range(self.count):
                explosive = TimedExplosive(
                    id=battle_state.next_entity_id,
                    is_clone=getattr(entity, "is_clone", False),
                    position=Position(entity.position.x, entity.position.y),
                    player_id=entity.player_id,
                    card_stats=entity.card_stats,
                    hitpoints=1,
                    max_hitpoints=1,
                    damage=0,
                    range=0,
                    sight_range=0,
                    explosion_timer=explosion_timer,
                    explosion_radius=explosion_radius,
                    explosion_damage=explosion_damage,
                    knockback_distance=float(
                        self.unit_data.get("deathPushback", 0) or 0
                    ) / 1000.0,
                    death_spawn_name=spawn_name,
                    death_spawn_count=spawn_count,
                    death_spawn_data=spawn_data or None,
                    death_spawn_radius=float(
                        self.unit_data.get("deathSpawnRadius", 700) or 700
                    ) / 1000.0,
                    death_spawn_deploy_time=max(
                        0.0,
                        float(self.unit_data.get("deathSpawnDeployTime", 0) or 0)
                        / 1000.0,
                    ),
                    death_spawn_pushback=bool(
                        self.unit_data.get("deathSpawnPushback", False)
                    ),
                    spawn_const_priority=bool(
                        self.unit_data.get("spawnConstPriority", False)
                    ),
                    deployment_collision_radius=float(
                        self.unit_data.get("collisionRadius", 500) or 500
                    ) / 1000.0,
                    # A falling container that will release troops remains
                    # movable by arena-wide pulls. Stationary death bombs do
                    # not expose that capability.
                    area_displaceable=bool(spawn_name and spawn_count > 0),
                    is_air_unit=bool(spawn_name and spawn_count > 0),
                    _facing_x_units=entity._facing_x_units,
                    _facing_y_units=entity._facing_y_units,
                )
                if (
                    inherited_freeze_remaining > 1e-9
                    and explosive.carries_freeze_to_children
                ):
                    # The falling/opening payload carries the parent's
                    # absolute Freeze expiry without pausing its own timer.
                    explosive.freeze_expiry_time = max(
                        explosive.freeze_expiry_time,
                        battle_state.time + inherited_freeze_remaining,
                    )
                battle_state.entities[explosive.id] = explosive
                battle_state.next_entity_id += 1
            return

        death_spawn_stats = None
        if self.unit_data:
            death_spawn_stats = troop_from_character_data(
                self.unit_name,
                self.unit_data,
                elixir=0,
                raw_overrides={"level": getattr(entity.card_stats, "level", 11)},
                rarity=self.unit_data.get("rarity", "Common"),
            )
        if not death_spawn_stats:
            # Fall back to canonical card loader entry when raw spawn data is unavailable.
            death_spawn_stats = battle_state.card_loader.get_card(self.unit_name)
            if death_spawn_stats is not None:
                death_spawn_stats = copy.copy(death_spawn_stats)
                death_spawn_stats.level = getattr(entity.card_stats, "level", 11)
        if not death_spawn_stats:
            raise ValueError(
                f"Missing death-spawn character data for {self.unit_name}"
            )

        from ...formations import native_radial_spawn_offset

        facing_x_units, facing_y_units = entity.native_facing_units()
        angle_shift = float(
            getattr(entity.card_stats, "spawn_angle_shift", 0) or 0
        )
        radius = max(0.0, float(self.radius_tiles))
        min_radius = max(0.0, float(self.min_radius_tiles))
        if radius > 0.0 and 0.0 < min_radius < radius:
            from ...kinematics import logic_units_to_tiles, tiles_to_logic_units

            minimum_units = tiles_to_logic_units(min_radius)
            radius_units = tiles_to_logic_units(radius)
            radius = logic_units_to_tiles(
                minimum_units
                + battle_state.rng.randrange(radius_units - minimum_units)
            )

        for index in range(self.count):
            if radius > 0.0:
                offset_x, offset_y = native_radial_spawn_offset(
                    index,
                    self.count,
                    radius,
                    angle_shift,
                    facing_x_units=facing_x_units,
                    facing_y_units=facing_y_units,
                    flip_x=(
                        self.spawn_const_priority
                        and battle_state.arena.native_path_id_at(
                            entity.position
                        )
                        == 1
                    ),
                    flip_y=self.spawn_const_priority and entity.player_id == 1,
                )
                spawn_position = Position(
                    entity.position.x + offset_x,
                    entity.position.y + offset_y,
                )
            else:
                spawn_position = battle_state._native_child_position_without_radius(
                    entity,
                    death_spawn_stats,
                    direct=self.count == 1,
                )

            spawned_id = battle_state.next_entity_id
            battle_state._spawn_unit_at_position(
                spawn_position,
                entity.player_id,
                death_spawn_stats,
                deploy_delay_override=max(0.0, self.deploy_time_ms / 1000.0),
                snap_to_valid=False,
                death_spawn=True,
                is_clone=getattr(entity, "is_clone", False),
                death_spawn_travel_origin=(
                    entity.position
                    if self.radial_pushback and radius > 0.0
                    else None
                ),
            )
            spawned = battle_state.entities.get(spawned_id)
            if spawned is not None and self.spawn_const_priority:
                spawned._native_target_distance_discount_sq_units = (
                    spawn_target_distance_discount_sq_units(index)
                )
            if spawned is not None and (
                (self.radial_pushback and radius > 0.0)
                or self.spawn_const_priority
            ):
                battle_state.sync_fast_target_entity(spawned)
            # Native Freeze inheritance is limited to immediate death
            # payloads.  A non-zero DeathSpawnDeployTime puts each child into
            # the staggered deployment path, so it is not yet present to
            # inherit the dying parent's status (for example, Battle Ram's
            # Barbarians).  Key this off the serialized timing field so the
            # same rule applies to every current and future death payload.
            if (
                inherited_freeze_remaining > 1e-9
                and self.deploy_time_ms <= 0
            ):
                if spawned is not None:
                    # The child is born after Freeze took its one-time target
                    # snapshot, so copy the parent's absolute expiry instead
                    # of trying to reapply the area effect.
                    spawned.inherit_freeze_until(
                        entity.freeze_expiry_time,
                        battle_state.time,
                    )
