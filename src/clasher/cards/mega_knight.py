from dataclasses import dataclass
from typing import TYPE_CHECKING
import math

from ..mechanics.mechanic_base import BaseMechanic
from ..unit_traits import is_above_ground_surface, is_airborne_target
from ..kinematics import (
    logic_speed_to_tiles_per_second,
    logic_units_to_tiles,
    normalized_vector_logic_units,
    tiles_to_logic_units,
    trunc_div,
)

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class MegaKnightSlam(BaseMechanic):
    """Applies Mega Knight's spawn slam and ground shockwaves."""
    spawn_radius: float = 2.2
    spawn_damage: float = 0.0
    spawn_knockback: float = 1.0
    slam_radius: float = 1.3
    jump_damage: float = 0.0
    jump_min_range: float = 3.5
    jump_max_range: float = 5.0
    jump_speed: float = 250.0
    # DashCooldown is the interruptible charge before takeoff. Current game
    # data gives Mega Knight a fixed airborne duration and a separate landing
    # recovery; JumpSpeed is the fallback for characters without that field.
    leap_duration_ms: int = 900
    airborne_duration_ms: int = 800
    landing_duration_ms: int = 300
    jump_knockback: float = 1.0

    def on_attach(self, entity: 'Entity') -> None:
        raw = getattr(entity.card_stats, "_raw_entry", {}) or {}
        char_data = raw.get("summonCharacterData", {}) or {}
        deploy_projectile = raw.get("projectileData", {}) or {}
        self.spawn_radius = float(deploy_projectile.get("radius", self.spawn_radius * 1000)) / 1000.0
        self.spawn_damage = float(deploy_projectile.get("damage", self.spawn_damage or 0.0))
        self.spawn_knockback = float(deploy_projectile.get("pushback", self.spawn_knockback * 1000)) / 1000.0
        # ``areaDamageRadius`` is the 1.3-tile radius of Mega Knight's normal
        # mace swing. His spawn and jump landing use the wider serialized
        # shockwave projectile instead.
        self.slam_radius = self.spawn_radius
        self.jump_damage = float(char_data.get("dashDamage", self.jump_damage or 0.0))
        self.jump_min_range = float(char_data.get("dashMinRange", self.jump_min_range * 1000)) / 1000.0
        self.jump_max_range = float(char_data.get("dashMaxRange", self.jump_max_range * 1000)) / 1000.0
        self.jump_speed = float(char_data.get("jumpSpeed", self.jump_speed))
        self.leap_duration_ms = int(
            char_data.get("dashCooldown", self.leap_duration_ms) or 0
        )
        self.airborne_duration_ms = int(
            char_data.get("dashConstantTime", self.airborne_duration_ms) or 0
        )
        self.landing_duration_ms = int(
            char_data.get("dashLandingTime", self.landing_duration_ms) or 0
        )
        self.jump_knockback = float(
            char_data.get("dashPushBack", self.jump_knockback * 1000) or 0
        ) / 1000.0
        self.slam_radius = float(
            char_data.get("dashRadius", self.slam_radius * 1000)
            or self.slam_radius * 1000
        ) / 1000.0
        entity._mk_leap_target_id = None
        entity._mk_leap_target = None
        entity._mk_leap_phase = None
        entity._mk_leap_progress = 0.0
        entity._mk_leap_travel_duration_ms = 0.0
        entity._special_move_active = False

    def on_spawn(self, entity: 'Entity') -> None:
        self._slam(
            entity,
            self.spawn_radius,
            self._scaled_damage(entity, self.spawn_damage),
            knockback=self.spawn_knockback,
        )

    def on_tick(self, entity: 'Entity', dt_ms: int) -> None:
        phase = getattr(entity, "_mk_leap_phase", None)
        if phase is None:
            target = None
            if (
                hasattr(entity, "battle_state")
                and getattr(entity, "target_id", None) is not None
            ):
                target = entity.battle_state.entities.get(entity.target_id)
            if target is not None and target.is_alive and not entity.is_stunned():
                if self._target_edge_distance(entity, target) is not None:
                    self._start_charge(entity, target)
            return
        if phase == "charging":
            self._update_charge(entity, dt_ms)
            return

    def on_movement_tick(self, entity: 'Entity', dt_ms: int) -> None:
        """Advance the committed leap and landing in component type 1."""
        phase = getattr(entity, "_mk_leap_phase", None)
        if phase == "airborne":
            self._update_airborne(entity, dt_ms)
        elif phase == "landing":
            self._update_landing(entity, dt_ms)

    def _current_charge_target(self, entity: 'Entity'):
        battle = getattr(entity, "battle_state", None)
        if battle is None:
            return None
        current = battle.entities.get(getattr(entity, "target_id", None))
        if current is None or not entity._is_valid_target(current):
            current = None
        best = entity.get_nearest_target(battle.entities)
        if best is not None and (
            current is None or entity._should_switch_target(current, best)
        ):
            current = best
            entity.target_id = best.id
        return current

    def _update_charge(self, entity: 'Entity', dt_ms: int) -> None:
        # Stun does not cancel Mega Knight's initiated jump, but it still
        # freezes the anticipation animation. Preserve the accumulated
        # wind-up so he can resume immediately when the stun expires.
        if entity.is_stunned():
            return
        target = self._current_charge_target(entity)
        if target is None:
            self._cancel_leap(entity)
            return
        distance = entity.position.distance_to(target.position)
        if self._target_edge_distance(entity, target) is None:
            self._cancel_leap(entity)
            return
        entity._mk_leap_target_id = target.id
        entity._mk_leap_progress += dt_ms * entity.get_attack_rate_multiplier()
        if entity._mk_leap_progress + 1e-9 < self.leap_duration_ms:
            return
        self._launch_leap(entity, target, distance)

    def _target_edge_distance(self, entity: 'Entity', target: 'Entity') -> float | None:
        return entity.native_dash_range_edge_distance(
            target,
            self.jump_min_range,
            self.jump_max_range,
        )

    def _update_airborne(self, entity: 'Entity', dt_ms: int) -> None:
        entity._mk_leap_progress += dt_ms
        duration = max(1.0, entity._mk_leap_travel_duration_ms)
        progress = min(1.0, entity._mk_leap_progress / duration)
        start_x, start_y = entity._mk_leap_origin
        target_x, target_y = entity._mk_leap_target
        elapsed_ms = min(round(duration), round(entity._mk_leap_progress))
        duration_ms = max(1, round(duration))
        start_x_units = tiles_to_logic_units(start_x)
        start_y_units = tiles_to_logic_units(start_y)
        entity.position.x = logic_units_to_tiles(
            start_x_units
            + trunc_div(
                (tiles_to_logic_units(target_x) - start_x_units) * elapsed_ms,
                duration_ms,
            )
        )
        entity.position.y = logic_units_to_tiles(
            start_y_units
            + trunc_div(
                (tiles_to_logic_units(target_y) - start_y_units) * elapsed_ms,
                duration_ms,
            )
        )
        if progress >= 1.0:
            target = entity.battle_state.entities.get(entity._mk_leap_target_id)
            self._slam(
                entity,
                self.slam_radius,
                self._scaled_damage(entity, self.jump_damage),
                knockback=self.jump_knockback,
            )
            if target is not None and target.is_alive:
                for mechanic in entity.mechanics:
                    if mechanic is not self:
                        mechanic.on_attack_hit(entity, target)
            entity.attack_cooldown = entity.get_base_attack_interval_seconds()
            entity._mk_leap_progress = 0.0
            entity._mk_leap_travel_duration_ms = 0.0
            if self.landing_duration_ms > 0:
                entity._mk_leap_phase = "landing"
            else:
                self._finish_leap(entity)

    def _update_landing(self, entity: 'Entity', dt_ms: int) -> None:
        entity._mk_leap_progress += dt_ms
        if entity._mk_leap_progress + 1e-9 < self.landing_duration_ms:
            return
        self._finish_leap(entity)

    def _finish_leap(self, entity: 'Entity') -> None:
        entity._mk_leap_target = None
        entity._mk_leap_target_id = None
        entity._mk_leap_phase = None
        entity._mk_leap_progress = 0.0
        entity._mk_leap_travel_duration_ms = 0.0
        entity._special_move_active = False
        entity._special_move_consumed_tick = True

    def _start_charge(self, entity: 'Entity', target: 'Entity') -> None:
        entity._mk_leap_phase = "charging"
        entity._mk_leap_progress = 0.0
        entity._mk_leap_target_id = target.id
        entity._special_move_active = True

    def _launch_leap(self, entity: 'Entity', target: 'Entity', _distance: float) -> None:
        # Leap landing is governed by the target hitbox and its splash impact,
        # rather than the normal melee edge-to-edge reach calculation.
        origin_x_units = tiles_to_logic_units(entity.position.x)
        origin_y_units = tiles_to_logic_units(entity.position.y)
        dx_units = tiles_to_logic_units(target.position.x) - origin_x_units
        dy_units = tiles_to_logic_units(target.position.y) - origin_y_units
        distance_units = math.isqrt(dx_units * dx_units + dy_units * dy_units)
        stop_distance_units = tiles_to_logic_units(
            entity.range + target.get_collision_radius()
        )
        travel_units = max(0, distance_units - stop_distance_units)
        travel_x_units, travel_y_units = normalized_vector_logic_units(
            dx_units,
            dy_units,
            travel_units,
        )
        entity._mk_leap_progress = 0.0
        entity._mk_leap_origin = (entity.position.x, entity.position.y)
        entity._mk_leap_target = (
            logic_units_to_tiles(origin_x_units + travel_x_units),
            logic_units_to_tiles(origin_y_units + travel_y_units),
        )
        entity._mk_leap_target_id = target.id
        entity._mk_leap_phase = "airborne"
        if self.airborne_duration_ms > 0:
            entity._mk_leap_travel_duration_ms = float(self.airborne_duration_ms)
        else:
            speed_tiles_per_second = max(
                1e-9,
                logic_speed_to_tiles_per_second(self.jump_speed),
            )
            entity._mk_leap_travel_duration_ms = max(
                1.0,
                logic_units_to_tiles(travel_units)
                / speed_tiles_per_second
                * 1000.0,
            )
        entity._special_move_active = True

    def _cancel_leap(self, entity: 'Entity') -> None:
        entity._mk_leap_target = None
        entity._mk_leap_target_id = None
        entity._mk_leap_phase = None
        entity._mk_leap_progress = 0.0
        entity._mk_leap_travel_duration_ms = 0.0
        entity._special_move_active = False
        entity._special_move_consumed_tick = True

    def blocks_ground_collision(self, entity: 'Entity') -> bool:
        return getattr(entity, "_mk_leap_phase", None) == "airborne"

    def on_forced_movement(
        self,
        entity: 'Entity',
        source_kind: str | None,
        movement_kind: str,
    ) -> None:
        # Any displacement that actually reaches Mega Knight interrupts the
        # pre-jump anticipation. Ordinary mass-limited knockback is rejected
        # before this hook because Mega Knight is heavyweight, while
        # pushback-all payloads such as The Log legitimately reach it.
        if getattr(entity, "_mk_leap_phase", None) == "charging":
            self._cancel_leap(entity)
            return

        # Once airborne, the leap is committed. Fisherman's hook is the
        # explicit exception that can drag Mega Knight out of the leap.
        if source_kind == "Fisherman" and movement_kind == "hook":
            self._cancel_leap(entity)

    def _scaled_damage(self, entity: 'Entity', base_damage: float) -> float:
        scaler = getattr(entity.card_stats, "get_scaled_stat", None)
        if callable(scaler):
            return float(scaler(base_damage))
        return float(base_damage)

    def _slam(self, entity: 'Entity', radius: float, damage: float, knockback: float = 0.0) -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        impact_position = type(entity.position)(entity.position.x, entity.position.y)
        targets = []
        for other in list(battle_state.entities.values()):
            if other.player_id == entity.player_id or not other.is_alive:
                continue
            if (
                is_airborne_target(other)
                or is_above_ground_surface(other)
                or getattr(other, "entity_kind", 4) in {2, 3}
            ):
                continue
            if other.intersects_native_area(impact_position, radius):
                if not other.can_receive_area_damage(
                    "mega-knight-slam",
                    source_entity=entity,
                ):
                    continue
                targets.append(other)

        for other in targets:
            other.take_damage(damage, source_kind="mega-knight-slam")
            if (
                other.is_alive
                and knockback > 0
                and getattr(other, "entity_kind", 4) != 1
            ):
                from ..mechanics.shared.knockback import apply_radial_knockback

                apply_radial_knockback(
                    other,
                    battle_state,
                    impact_position,
                    knockback,
                    source_kind="mega-knight-slam",
                )
