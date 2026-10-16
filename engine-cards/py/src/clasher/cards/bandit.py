from dataclasses import dataclass, field
import math

from ..mechanics.mechanic_base import BaseMechanic
from ..kinematics import (
    logic_time_milliseconds,
    logic_units_to_tiles,
    tiles_to_logic_units,
    trunc_div,
)


def dash_half_step(p, goal, length):
    """Ported from RoyaleSim (MIT), move16402.rs `dash_half_step`/`tunnel_step`: at most ``length`` toward
    ``goal`` through the walk's 1/256 direction and truncated step, no snap; ``arrived`` tests the pre-step
    distance."""
    dx, dy = goal[0] - p[0], goal[1] - p[1]
    dist = max(1, math.isqrt(dx * dx + dy * dy))
    arrived = math.isqrt(dx * dx + dy * dy) <= length
    step = min(max(0, length), dist)
    sx = trunc_div(trunc_div(dx * 256, dist) * step, 256)
    sy = trunc_div(trunc_div(dy * 256, dist) * step, 256)
    return (p[0] + sx, p[1] + sy), arrived


@dataclass
class BanditDash(BaseMechanic):
    """Mechanic for Bandit's dash attack with invincibility frames"""
    dash_distance: float = 500.0  # Legacy value (5 tiles in runtime coordinate space)
    dash_min_range: float = 3.5  # Minimum range to initiate dash (tiles)
    dash_max_range: float = 6.0  # Maximum range to initiate dash (tiles)
    # The displayed ``Dash Time`` is the interruptible wind-up before motion.
    # Once launched, movement uses the separately serialized jump speed.
    dash_duration_ms: int = 800
    invincibility_duration_ms: int = 800  # Legacy public field; motion is speed-based.
    post_dash_immunity_ms: int = 100
    jump_speed: float = 500.0
    dash_damage: float = 0.0

    # Internal state
    is_dashing: bool = field(init=False, default=False)
    last_dash_time: int = field(init=False, default=0)

    def on_attach(self, entity) -> None:
        """Initialize dash state"""
        entity._bandit_dashing = False
        entity._bandit_charging = False
        entity._bandit_invulnerable_until = 0
        entity._bandit_state = "idle"
        entity._bandit_wait = 0
        entity._bandit_seen_target = None
        entity._bandit_blocked = False
        entity._bandit_goal = None
        entity._special_move_active = False
        raw = getattr(getattr(entity, "card_stats", None), "_raw_entry", {}) or {}
        char_data = raw.get("summonCharacterData", {}) or {}
        self.dash_min_range = float(char_data.get("dashMinRange", self.dash_min_range * 1000)) / 1000.0
        self.dash_max_range = float(char_data.get("dashMaxRange", self.dash_max_range * 1000)) / 1000.0
        self.dash_duration_ms = int(
            char_data.get("dashCooldown", self.dash_duration_ms) or 0
        )
        self.jump_speed = float(char_data.get("jumpSpeed", self.jump_speed))
        self.dash_damage = float(char_data.get("dashDamage", self.dash_damage or 0.0))
        self.post_dash_immunity_ms = int(
            char_data.get(
                "dashImmuneToDamageTime",
                self.post_dash_immunity_ms,
            )
            or 0
        )

    # Batch C1: the Bandit-family dash, ported from RoyaleSim (MIT), state.rs `phase_path16402_for` (dash
    # branch), `dash_goal_native`, `end_dashes` and move16402.rs `dash_half_step`, all in the movement component
    # after this frame's combat targeting:
    #   idle -> standing on first sight of a target inside DashMaxRange+target radius (blocked for that
    #   target's whole sight if first seen inside DashMinRange+both radii) -> travel DashCooldown/50-1 ticks
    #   later (the entry tick is still) -> two JumpSpeed/2 half-steps a tick toward a frozen 500-cell goal,
    #   each followed by the Range+both-radii test against the target's current point -> blow and end.
    # Python keeps its non-interrupting Freeze contract: a frozen stand neither counts down nor cancels.

    def on_tick(self, entity, dt_ms: int) -> None:
        """Combat component: dash travel owns the frame (``_special_move_active``)."""
        return

    def on_movement_tick(self, entity, dt_ms: int) -> None:
        battle = getattr(entity, "battle_state", None)
        if battle is None:
            return
        state = entity._bandit_state
        if state == "travel":
            self._update_dash(entity, battle)
            return
        is_stunned = getattr(entity, "is_stunned", lambda: False)
        if is_stunned():
            return
        target = battle.entities.get(entity.target_id)
        if target is not None and not target.is_alive:
            target = None
        if state == "idle":
            walking = (
                target is not None
                and not entity._attack_windup_active
                and not entity._attack_finish_elapsed_ms
            )
            if walking:
                d2 = self._centre_d2(entity, target)
                radius_t = tiles_to_logic_units(target.get_collision_radius())
                near = (
                    tiles_to_logic_units(self.dash_min_range)
                    + tiles_to_logic_units(entity.get_collision_radius())
                    + radius_t
                )
                reach = tiles_to_logic_units(self.dash_max_range) + radius_t
                within = d2 <= reach * reach
                if entity._bandit_seen_target != target.id:
                    entity._bandit_seen_target = target.id
                    entity._bandit_blocked = d2 < near * near
                if within and not entity._bandit_blocked:
                    entity._bandit_state = state = "standing"
                    entity._bandit_wait = max(1, self.dash_duration_ms // 50) - 1
                    entity._bandit_charging = True
                    entity._special_move_consumed_tick = True
                    return
        elif state == "standing" and (
            target is None
            or target.id != entity._bandit_seen_target
            or entity._attack_windup_active
            or entity._attack_finish_elapsed_ms
        ):
            self._cancel_charge(entity)
            state = "idle"
        if state != "standing":
            return
        entity._bandit_wait -= 1
        if entity._bandit_wait <= 0:
            self._launch_dash(entity, target)
        # The stand (and the still entry tick) consumes this movement frame.
        entity._special_move_consumed_tick = True

    @staticmethod
    def _centre_d2(entity, target) -> int:
        dx = tiles_to_logic_units(target.position.x) - tiles_to_logic_units(entity.position.x)
        dy = tiles_to_logic_units(target.position.y) - tiles_to_logic_units(entity.position.y)
        return dx * dx + dy * dy

    def _target_edge_distance(self, entity, target) -> float | None:
        """Return target-edge distance when the native dash band accepts it."""
        return entity.native_dash_range_edge_distance(
            target,
            self.dash_min_range,
            self.dash_max_range,
        )

    def _launch_dash(self, entity, target) -> None:
        """Entry: freeze the 500-cell goal (RoyaleSim `dash_goal_native`); travel immunity starts."""
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
        entity._bandit_goal = ((px // 500) * 500 + 250, (py // 500) * 500 + 250)
        entity._bandit_state = "travel"
        entity._bandit_charging = False
        entity._bandit_dashing = True
        entity._bandit_wait = 0
        entity._special_move_active = True

    def _update_dash(self, entity, battle) -> None:
        """Two JumpSpeed/2 half-steps toward the goal, each followed by the range test."""
        target = battle.entities.get(entity._bandit_seen_target)
        if target is None or not target.is_alive:
            self._end_dash(entity, battle)
            return
        length = round(self.jump_speed) // 2
        reach = (
            tiles_to_logic_units(float(getattr(entity, "range", 0.75) or 0.75))
            + tiles_to_logic_units(entity.get_collision_radius())
            + tiles_to_logic_units(target.get_collision_radius())
        )
        gx, gy = entity._bandit_goal
        x = tiles_to_logic_units(entity.position.x)
        y = tiles_to_logic_units(entity.position.y)
        hit = False
        for _ in range(2):
            (x, y), arrived = dash_half_step((x, y), (gx, gy), length)
            entity.position.x = logic_units_to_tiles(x)
            entity.position.y = logic_units_to_tiles(y)
            ex = tiles_to_logic_units(target.position.x) - x
            ey = tiles_to_logic_units(target.position.y) - y
            if ex * ex + ey * ey <= reach * reach:
                hit = True
                break
            if arrived:
                break
        else:
            return
        if hit:
            scaler = getattr(entity.card_stats, "get_scaled_stat", None)
            dash_damage = (
                float(scaler(self.dash_damage))
                if self.dash_damage > 0 and callable(scaler)
                else self.dash_damage
                if self.dash_damage > 0
                else entity.damage * 2.0
            )
            entity._deal_attack_damage(
                target,
                dash_damage,
                battle,
                exclude_hit_mechanic=self,
            )
            entity.attack_cooldown = entity.get_base_attack_interval_seconds()
        self._end_dash(entity, battle)

    def _end_dash(self, entity, battle) -> None:
        from ..native_tilemap import recover_native_ground_position

        x, y = recover_native_ground_position(
            tiles_to_logic_units(entity.position.x),
            tiles_to_logic_units(entity.position.y),
        )
        entity.position.x = logic_units_to_tiles(x)
        entity.position.y = logic_units_to_tiles(y)
        entity._bandit_state = "idle"
        entity._bandit_dashing = False
        entity._bandit_charging = False
        entity._bandit_seen_target = None
        entity._bandit_blocked = False
        entity._bandit_goal = None
        entity._bandit_wait = 0
        entity._special_move_active = False
        entity._special_move_consumed_tick = True
        # Travel immunity ends here; DashImmuneToDamageTime keeps damage off for the tail. It also
        # covers projectiles that tick in the object phase after this movement component.
        entity._bandit_invulnerable_until = (
            logic_time_milliseconds(battle.time) + self.post_dash_immunity_ms
        )

    def _cancel_charge(self, entity) -> None:
        """A stand ends without a dash; the seen target and its block are kept."""
        entity._bandit_state = "idle"
        entity._bandit_charging = False
        entity._bandit_wait = 0

    def handle_stun(self, entity) -> None:
        # An interrupting stun ends the stand; travel is filtered by blocks_status_effect before this hook.
        if entity._bandit_state == "standing":
            self._cancel_charge(entity)

    def take_damage_during_dash(self, entity, damage: float) -> bool:
        """Check if entity should take damage during dash"""
        # The dash state blocks damage throughout travel. Character data also
        # supplies a damage-only tail after landing.
        return not self._is_damage_invulnerable(entity)

    def allows_effect(
        self,
        entity,
        source_kind: str | None,
        *,
        affects_hidden: bool = False,
    ) -> bool:
        """Block damage, status, and forced movement during actual travel."""
        del affects_hidden
        return not self._is_travel_invulnerable(entity)

    def blocks_status_effect(self, entity) -> bool:
        return self._is_travel_invulnerable(entity)

    def blocks_targeting(self, entity) -> bool:
        return False

    def blocks_ground_collision(self, entity) -> bool:
        return getattr(entity, "_bandit_dashing", False)

    def allows_forced_movement(
        self,
        entity,
        source_kind: str | None,
        movement_kind: str,
    ) -> bool | None:
        # Hook drag is the native exception to Bandit's travel immunity. It
        # can catch and cancel her dash; ordinary pushes remain ineffective.
        if source_kind == "Fisherman" and movement_kind == "hook":
            return True
        return None

    def on_forced_movement(
        self,
        entity,
        source_kind: str | None,
        movement_kind: str,
    ) -> None:
        # Any displacement that actually reaches the unit ends the stand. Once travel begins, ordinary
        # pushes are rejected by the dash's effect guard before this hook; Fisherman's hook is the
        # explicit exception that catches the dash. A hook resets the whole dash state.
        hook = source_kind == "Fisherman" and movement_kind == "hook"
        if entity._bandit_state == "standing":
            self._cancel_charge(entity)
        elif entity._bandit_state != "travel" or not hook:
            return
        if hook:
            entity._bandit_state = "idle"
            entity._bandit_dashing = False
            entity._bandit_charging = False
            entity._bandit_seen_target = None
            entity._bandit_blocked = False
            entity._bandit_goal = None
            entity._bandit_wait = 0
            entity._bandit_invulnerable_until = 0
            entity._special_move_active = False

    @staticmethod
    def _is_travel_invulnerable(entity) -> bool:
        return bool(getattr(entity, "_bandit_dashing", False))

    @classmethod
    def _is_damage_invulnerable(cls, entity) -> bool:
        if cls._is_travel_invulnerable(entity):
            return True
        battle = getattr(entity, "battle_state", None)
        if battle is None:
            return False
        return logic_time_milliseconds(battle.time) < int(
            getattr(entity, "_bandit_invulnerable_until", 0) or 0
        )
