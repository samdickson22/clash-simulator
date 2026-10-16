from dataclasses import dataclass
from typing import TYPE_CHECKING
import math

from ..mechanics.mechanic_base import BaseMechanic
from ..unit_traits import is_above_ground_surface, is_airborne_target
from ..kinematics import (
    logic_units_to_tiles,
    tiles_to_logic_units,
    trunc_div,
)

if TYPE_CHECKING:
    from ..entities import Entity


DASH_BLOW_TO_END_MS = 4 * 50


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
        # Batch C1: the raw DashLandingTime (300) is kept for reference, but the combat recovery after
        # the blow is the measured four ticks (RoyaleSim (MIT) state.rs DASH_BLOW_TO_END_TICKS = 4:
        # the timed dash ends four ticks after its blow and the normal load restarts there).
        self.landing_raw_ms = int(
            char_data.get("dashLandingTime", self.landing_duration_ms) or 0
        )
        self.landing_duration_ms = DASH_BLOW_TO_END_MS if self.landing_raw_ms > 0 else 0
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
        entity._mk_seen_target = None
        entity._mk_blocked = False
        entity._mk_wait = 0
        entity._mk_goal = None
        entity._mk_mark = 0
        entity._special_move_active = False

    def on_spawn(self, entity: 'Entity') -> None:
        self._slam(
            entity,
            self.spawn_radius,
            self._scaled_damage(entity, self.spawn_damage),
            knockback=self.spawn_knockback,
        )

    # Batch C1: the timed dash, ported from RoyaleSim (MIT), state.rs `phase_path16402_for` (dash branch with
    # DashConstantTime), `dash_goal_native` and move16402.rs `dash_half_step`, all in the movement component:
    # first sight inside DashMaxRange+target radius (blocked for that sight if first seen inside DashMinRange+
    # both radii) -> stand DashCooldown/50-1 ticks -> entry (moves on its entry tick) -> JumpSpeed a tick toward
    # the frozen 500-cell goal, holding where the arrival step ends -> blow DashConstantTime/50 ticks after the
    # entry (motion stops there, ground repaired) -> the dash ends DASH_BLOW_TO_END_TICKS after the blow.
    # Phases: None (idle), "charging" (the stand), "airborne" (entry..blow), "landing" (blow..end).

    def on_tick(self, entity: 'Entity', dt_ms: int) -> None:
        return

    def on_movement_tick(self, entity: 'Entity', dt_ms: int) -> None:
        battle = getattr(entity, "battle_state", None)
        if battle is None:
            return
        phase = entity._mk_leap_phase
        if phase == "airborne":
            self._update_airborne(entity, battle)
            return
        if phase == "landing":
            if battle.tick >= entity._mk_mark + self.airborne_duration_ms // 50 + DASH_BLOW_TO_END_MS // 50:
                self._finish_leap(entity)
            return
        if entity.is_stunned():
            return
        target = battle.entities.get(entity.target_id)
        if target is not None and not target.is_alive:
            target = None
        if phase is None:
            walking = (
                target is not None
                and not entity._attack_windup_active
                and not entity._attack_finish_elapsed_ms
            )
            if walking:
                dx = tiles_to_logic_units(target.position.x) - tiles_to_logic_units(entity.position.x)
                dy = tiles_to_logic_units(target.position.y) - tiles_to_logic_units(entity.position.y)
                d2 = dx * dx + dy * dy
                radius_t = tiles_to_logic_units(target.get_collision_radius())
                near = (
                    tiles_to_logic_units(self.jump_min_range)
                    + tiles_to_logic_units(entity.get_collision_radius())
                    + radius_t
                )
                reach = tiles_to_logic_units(self.jump_max_range) + radius_t
                if entity._mk_seen_target != target.id:
                    entity._mk_seen_target = target.id
                    entity._mk_blocked = d2 < near * near
                if d2 <= reach * reach and not entity._mk_blocked:
                    entity._mk_leap_phase = "charging"
                    entity._mk_leap_target_id = target.id
                    entity._mk_wait = max(1, self.leap_duration_ms // 50) - 1
                    entity._special_move_consumed_tick = True
                    return
        elif phase == "charging" and (
            target is None
            or target.id != entity._mk_seen_target
            or entity._attack_windup_active
            or entity._attack_finish_elapsed_ms
        ):
            self._cancel_charge(entity)
            phase = None
        if phase != "charging":
            return
        entity._mk_wait -= 1
        if entity._mk_wait > 0:
            entity._special_move_consumed_tick = True
            return
        self._launch_leap(entity, target, battle)
        self._update_airborne(entity, battle)

    def _update_airborne(self, entity: 'Entity', battle) -> None:
        from .bandit import dash_half_step

        x = tiles_to_logic_units(entity.position.x)
        y = tiles_to_logic_units(entity.position.y)
        (x, y), arrived = dash_half_step((x, y), entity._mk_goal, round(self.jump_speed))
        if arrived:
            entity._mk_goal = (x, y)
        entity.position.x = logic_units_to_tiles(x)
        entity.position.y = logic_units_to_tiles(y)
        if battle.tick != entity._mk_mark + self.airborne_duration_ms // 50:
            return
        target = battle.entities.get(entity._mk_leap_target_id)
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
        from ..native_tilemap import recover_native_ground_position

        x, y = recover_native_ground_position(x, y)
        entity.position.x = logic_units_to_tiles(x)
        entity.position.y = logic_units_to_tiles(y)
        entity._mk_goal = (x, y)
        entity._mk_leap_phase = "landing"

    def _target_edge_distance(self, entity: 'Entity', target: 'Entity') -> float | None:
        return entity.native_dash_range_edge_distance(
            target,
            self.jump_min_range,
            self.jump_max_range,
        )

    def _finish_leap(self, entity: 'Entity') -> None:
        entity._mk_leap_target = None
        entity._mk_leap_target_id = None
        entity._mk_leap_phase = None
        entity._mk_leap_progress = 0.0
        entity._mk_leap_travel_duration_ms = 0.0
        entity._mk_seen_target = None
        entity._mk_blocked = False
        entity._mk_wait = 0
        entity._mk_goal = None
        entity._special_move_active = False
        entity._special_move_consumed_tick = True

    def _launch_leap(self, entity: 'Entity', target: 'Entity', battle) -> None:
        """Entry: freeze the 500-cell goal (RoyaleSim `dash_goal_native`)."""
        ax = tiles_to_logic_units(entity.position.x)
        ay = tiles_to_logic_units(entity.position.y)
        tx = tiles_to_logic_units(target.position.x)
        ty = tiles_to_logic_units(target.position.y)
        rr = tiles_to_logic_units(entity.get_collision_radius()) + tiles_to_logic_units(
            target.get_collision_radius()
        )
        dx, dy = ax - tx, ay - ty
        n = math.isqrt(dx * dx + dy * dy)
        px, py = (tx, ty) if n == 0 else (tx + trunc_div(dx * rr, n), ty + trunc_div(dy * rr, n))
        entity._mk_goal = ((px // 500) * 500 + 250, (py // 500) * 500 + 250)
        entity._mk_mark = battle.tick
        entity._mk_wait = 0
        entity._mk_leap_target_id = target.id
        entity._mk_leap_phase = "airborne"
        entity._special_move_active = True

    def _cancel_charge(self, entity: 'Entity') -> None:
        """A stand ends without a leap; the seen target and its block are kept."""
        entity._mk_leap_phase = None
        entity._mk_leap_target_id = None
        entity._mk_wait = 0

    def _cancel_leap(self, entity: 'Entity') -> None:
        """Fisherman's hook resets the whole leap state."""
        entity._mk_leap_target = None
        entity._mk_leap_target_id = None
        entity._mk_leap_phase = None
        entity._mk_leap_progress = 0.0
        entity._mk_leap_travel_duration_ms = 0.0
        entity._mk_seen_target = None
        entity._mk_blocked = False
        entity._mk_wait = 0
        entity._mk_goal = None
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
        hook = source_kind == "Fisherman" and movement_kind == "hook"
        if getattr(entity, "_mk_leap_phase", None) == "charging":
            self._cancel_charge(entity)
            if hook:
                self._cancel_leap(entity)
            return

        # Once airborne, the leap is committed. Fisherman's hook is the
        # explicit exception that can drag Mega Knight out of the leap.
        if hook:
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
