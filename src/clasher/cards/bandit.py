from dataclasses import dataclass, field
from typing import TYPE_CHECKING
import math

from ..mechanics.mechanic_base import BaseMechanic
from ..kinematics import (
    LOGIC_TICK_SECONDS,
    logic_time_milliseconds,
    logic_units_to_tiles,
    normalized_vector_logic_units,
    speed_work_for_duration,
    tiles_to_logic_units,
    vector_towards_logic_units,
)

if TYPE_CHECKING:
    from ..entities import Troop


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
        entity._bandit_dash_timer = 0.0
        entity._bandit_dash_origin = None
        entity._bandit_dash_target = None
        entity._bandit_dash_target_id = None
        entity._bandit_dash_travel_duration_ms = 0.0
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

    def on_tick(self, entity, dt_ms: int) -> None:
        """Run dash acquisition and its interruptible combat wind-up."""
        if getattr(entity, '_bandit_dashing', False):
            return

        if getattr(entity, '_bandit_charging', False):
            self._update_charge(entity, dt_ms)
            return

        # Check if we should initiate dash.
        is_stunned = getattr(entity, "is_stunned", lambda: False)
        if not is_stunned() and entity.target_id is not None:

            # Check if target is in range for dash
            target = entity.battle_state.entities.get(entity.target_id) if hasattr(entity, 'battle_state') else None
            if target and target.is_alive:
                if self._target_edge_distance(entity, target) is not None:
                    self._start_charge(entity, target)

    def on_movement_tick(self, entity, dt_ms: int) -> None:
        """Advance committed dash travel in component type 1."""
        if getattr(entity, '_bandit_dashing', False):
            self._update_dash(entity, dt_ms)

    def _target_edge_distance(self, entity, target) -> float | None:
        """Return target-edge distance when the native dash band accepts it."""
        return entity.native_dash_range_edge_distance(
            target,
            self.dash_min_range,
            self.dash_max_range,
        )

    def _start_charge(self, entity, target) -> None:
        """Begin the interruptible 0.8-second dash wind-up."""
        entity._bandit_charging = True
        entity._bandit_dash_timer = 0.0
        entity._bandit_dash_target_id = getattr(target, "id", entity.target_id)
        entity._special_move_active = True

    def _current_charge_target(self, entity):
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

    def _update_charge(self, entity, dt_ms: int) -> None:
        target = self._current_charge_target(entity)
        if target is None:
            self._cancel_charge(entity)
            return
        if self._target_edge_distance(entity, target) is None:
            self._cancel_charge(entity)
            return

        entity._bandit_dash_target_id = target.id
        entity._bandit_dash_timer += dt_ms * entity.get_attack_rate_multiplier()
        if entity._bandit_dash_timer + 1e-9 < self.dash_duration_ms:
            return
        self._launch_dash(entity, target)

    def _launch_dash(self, entity, target) -> None:
        """Launch toward the target using the game-data jump speed."""
        entity._bandit_charging = False
        entity._bandit_dashing = True
        origin_x, origin_y = entity.position.x, entity.position.y
        origin_x_units = tiles_to_logic_units(origin_x)
        origin_y_units = tiles_to_logic_units(origin_y)
        dx_units = tiles_to_logic_units(target.position.x) - origin_x_units
        dy_units = tiles_to_logic_units(target.position.y) - origin_y_units
        distance_units = math.isqrt(dx_units * dx_units + dy_units * dy_units)
        target_radius = target.get_collision_radius()
        attack_range = float(getattr(entity, "range", 0.75) or 0.75)
        # Dash travel is a special movement rule: the serialized dash bounds
        # and stopping distance are measured from Bandit's center to the
        # target hitbox, unlike ordinary edge-to-edge attack reach.
        stop_distance_units = tiles_to_logic_units(attack_range + target_radius)
        dash_length_units = max(0, distance_units - stop_distance_units)
        travel_x_units, travel_y_units = normalized_vector_logic_units(
            dx_units,
            dy_units,
            dash_length_units,
        )
        target_x = logic_units_to_tiles(origin_x_units + travel_x_units)
        target_y = logic_units_to_tiles(origin_y_units + travel_y_units)
        entity._bandit_dash_origin = (origin_x, origin_y)
        entity._bandit_dash_target = (target_x, target_y)
        entity._bandit_dash_timer = 0.0
        entity._bandit_dash_target_id = getattr(target, "id", entity.target_id)
        committed_dash_units = math.isqrt(
            tiles_to_logic_units(target_x - origin_x) ** 2
            + tiles_to_logic_units(target_y - origin_y) ** 2
        )
        entity._bandit_dash_travel_duration_ms = max(
            1.0,
            committed_dash_units
            / max(round(self.jump_speed), 1)
            * LOGIC_TICK_SECONDS
            * 1000.0,
        )
        entity._special_move_active = True

        current_time_ms = logic_time_milliseconds(entity.battle_state.time)
        entity._bandit_invulnerable_until = (
            current_time_ms + entity._bandit_dash_travel_duration_ms
        )
        self.last_dash_time = current_time_ms

    def _update_dash(self, entity, dt_ms: int) -> None:
        """Update dash movement"""
        origin = getattr(entity, '_bandit_dash_origin', None)
        target = getattr(entity, '_bandit_dash_target', None)
        if not origin or not target:
            entity._bandit_dashing = False
            return

        target_x, target_y = target
        dx_units = tiles_to_logic_units(target_x - entity.position.x)
        dy_units = tiles_to_logic_units(target_y - entity.position.y)
        remaining_units = math.isqrt(dx_units * dx_units + dy_units * dy_units)
        work_units = speed_work_for_duration(self.jump_speed, dt_ms / 1000.0)
        move_x_units, move_y_units = vector_towards_logic_units(
            dx_units,
            dy_units,
            work_units,
        )
        entity.position.x = logic_units_to_tiles(
            tiles_to_logic_units(entity.position.x) + move_x_units
        )
        entity.position.y = logic_units_to_tiles(
            tiles_to_logic_units(entity.position.y) + move_y_units
        )
        entity._bandit_dash_timer += dt_ms

        if remaining_units <= work_units:
            target_entity = None
            if hasattr(entity, "battle_state"):
                target_entity = entity.battle_state.entities.get(entity._bandit_dash_target_id)
            if target_entity is not None and target_entity.is_alive:
                scaler = getattr(entity.card_stats, "get_scaled_stat", None)
                dash_damage = (
                    float(scaler(self.dash_damage))
                    if self.dash_damage > 0 and callable(scaler)
                    else self.dash_damage
                    if self.dash_damage > 0
                    else entity.damage * 2.0
                )
                entity._deal_attack_damage(
                    target_entity,
                    dash_damage,
                    entity.battle_state,
                    exclude_hit_mechanic=self,
                )
                entity.attack_cooldown = entity.get_base_attack_interval_seconds()
            entity._bandit_dashing = False
            entity._bandit_charging = False
            entity._special_move_active = False
            entity._special_move_consumed_tick = True
            entity._bandit_dash_origin = None
            entity._bandit_dash_target = None
            entity._bandit_dash_target_id = None
            entity._bandit_dash_timer = 0.0
            entity._bandit_dash_travel_duration_ms = 0.0
            # Travel immunity ends here, but native character data supplies a
            # short post-landing tail. It also covers projectiles that tick in
            # the object phase after this movement component.
            entity._bandit_invulnerable_until = (
                logic_time_milliseconds(entity.battle_state.time)
                + self.post_dash_immunity_ms
            )

    def _cancel_charge(self, entity) -> None:
        entity._bandit_charging = False
        entity._bandit_dash_timer = 0.0
        entity._bandit_dash_target_id = None
        entity._special_move_active = False
        entity._special_move_consumed_tick = True

    def handle_stun(self, entity) -> None:
        # Stuns reset Bandit's wind-up, but do not affect an invulnerable dash
        # (the latter is filtered by blocks_status_effect before this hook).
        if getattr(entity, "_bandit_charging", False):
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
        # Any displacement that actually reaches Bandit interrupts the
        # pre-dash anticipation. Once travel begins, ordinary pushes are
        # rejected by the dash's effect guard before this hook.
        if getattr(entity, "_bandit_charging", False):
            self._cancel_charge(entity)
            if source_kind == "Fisherman" and movement_kind == "hook":
                entity._bandit_invulnerable_until = 0
            return

        # Fisherman's hook is the explicit exception that can catch Bandit
        # during committed dash travel.
        if source_kind != "Fisherman" or movement_kind != "hook":
            return
        entity._bandit_dashing = False
        entity._bandit_invulnerable_until = 0
        entity._bandit_dash_timer = 0.0
        entity._bandit_dash_origin = None
        entity._bandit_dash_target = None
        entity._bandit_dash_target_id = None
        entity._bandit_dash_travel_duration_ms = 0.0
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
