from dataclasses import dataclass, field
import math
from typing import TYPE_CHECKING, Optional

from ..arena import Position
from ..mechanics.mechanic_base import BaseMechanic
from ..kinematics import (
    LOGIC_TICK_SECONDS,
    logic_speed_to_tiles_per_second,
    logic_units_to_tiles,
    normalized_vector_logic_units,
    speed_work_for_duration,
    tiles_per_second_to_logic_speed,
    tiles_to_logic_units,
    vector_towards_logic_units,
)

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class FishermanHook(BaseMechanic):
    """Fisherman's data-driven wind-up, hook flight, and drag sequence."""

    hook_range: float = 7.0
    hook_min_range: float = 3.5
    hook_windup_ms: float = 1300.0
    projectile_speed: float = logic_speed_to_tiles_per_second(800.0)
    drag_back_speed: float = logic_speed_to_tiles_per_second(850.0)
    drag_self_speed: float = logic_speed_to_tiles_per_second(450.0)
    drag_back_as_attractor: bool = True
    drag_margin: float = 0.2

    state: str = field(init=False, default="idle")
    hook_target_id: Optional[int] = field(init=False, default=None)
    windup_remaining_ms: float = field(init=False, default=0.0)
    hook_position: Optional[Position] = field(init=False, default=None)

    def on_attach(self, entity: 'Entity') -> None:
        stats = entity.card_stats
        self.hook_range = float(getattr(stats, "special_range", 0) or 7000) / 1000.0
        self.hook_min_range = float(
            getattr(stats, "special_min_range", 0) or 3500
        ) / 1000.0
        self.hook_windup_ms = float(
            getattr(stats, "special_load_time", 0) or 1300
        )

        raw = getattr(stats, "_raw_entry", {}) or {}
        character = raw.get("summonCharacterData", {}) or {}
        projectile = character.get("projectileSpecialData", {}) or {}
        self.projectile_speed = logic_speed_to_tiles_per_second(
            float(projectile.get("speed", 800) or 800)
        )
        self.drag_back_speed = logic_speed_to_tiles_per_second(
            float(projectile.get("dragBackSpeed", 850) or 850)
        )
        self.drag_self_speed = logic_speed_to_tiles_per_second(
            float(projectile.get("dragSelfSpeed", 450) or 450)
        )
        self.drag_back_as_attractor = bool(
            projectile.get("dragBackAsAttractor", False)
        )
        self.drag_margin = float(projectile.get("dragMargin", 200) or 200) / 1000.0

    def on_tick(self, entity: 'Entity', dt_ms: int) -> None:
        """Select and wind up the hook in the combat component."""
        battle = getattr(entity, "battle_state", None)
        if battle is None or entity.is_stunned():
            return

        if self.state == "idle":
            target = self._find_hook_target(entity)
            if target is not None:
                self._begin_windup(entity, target)
            return

        target = battle.entities.get(self.hook_target_id)
        if target is None or not target.is_alive:
            self._cancel(entity, target)
            return

        if self.state == "windup":
            if not self._is_hook_target_in_range(entity, target):
                self._cancel(entity, target)
                return
            attack_rate = max(entity.get_attack_rate_multiplier(), 1e-9)
            work = max(0.0, float(dt_ms)) * attack_rate
            if work + 1e-9 < self.windup_remaining_ms:
                self.windup_remaining_ms -= work
                return
            self.windup_remaining_ms = 0.0
            self._launch(entity, target)

    def on_object_tick(self, entity: 'Entity', dt_ms: int) -> None:
        """Advance the hook projectile and attached drag in object phase."""
        if self.state not in {"flight", "drag"}:
            return
        battle = getattr(entity, "battle_state", None)
        if battle is None:
            return
        target = battle.entities.get(self.hook_target_id)
        if target is None or not target.is_alive:
            self._cancel(entity, target)
            return
        if self.state == "flight":
            # Like LogicProjectile::tick, an arrival consumes this object's
            # tick. Attached drag work begins on the following object frame.
            self._advance_flight(entity, target, max(0.0, float(dt_ms)))
            return
        self._advance_drag(entity, target, max(0.0, float(dt_ms)) / 1000.0)

    def handle_stun(self, entity: 'Entity') -> None:
        self._cancel(entity, self._target(entity))

    def on_death(self, entity: 'Entity') -> None:
        self._cancel(entity, self._target(entity))

    def _find_hook_target(self, entity: 'Entity'):
        candidates = []
        for target in entity.battle_state.entities.values():
            if not self._is_hook_target_in_range(entity, target):
                continue
            candidates.append((target, entity.position.distance_to(target.position)))
        return entity._select_nearest_target(candidates)

    def _is_hook_target_in_range(self, entity: 'Entity', target: 'Entity') -> bool:
        if not target.is_targetable_by(entity.player_id):
            return False
        if not entity.can_affect_target_plane(target):
            return False
        distance = entity.position.distance_to(target.position)
        return (
            distance > self.hook_min_range + 1e-9
            and distance
            <= self.hook_range + target.get_collision_radius() + 1e-9
        )

    def _begin_windup(self, entity: 'Entity', target: 'Entity') -> None:
        self.state = "windup"
        self.hook_target_id = target.id
        self.windup_remaining_ms = self.hook_windup_ms
        entity.target_id = target.id
        entity._special_move_active = True

    def _launch(self, entity: 'Entity', target: 'Entity') -> None:
        launch_position, _, _ = entity._projectile_launch_geometry(target)
        self.hook_position = launch_position
        self.state = "flight"

    def _advance_flight(
        self,
        entity: 'Entity',
        target: 'Entity',
        available_ms: float,
    ) -> float:
        if self.hook_position is None:
            self._cancel(entity, target)
            return 0.0
        # River-jumping characters temporarily leave Fisherman's ground-only
        # target plane. A hook already in flight then misses instead of
        # dragging the airborne character out of its committed jump.
        if not entity.can_affect_target_plane(target):
            self._cancel(entity, target)
            return 0.0
        dx_units = tiles_to_logic_units(target.position.x - self.hook_position.x)
        dy_units = tiles_to_logic_units(target.position.y - self.hook_position.y)
        distance_units = max(1, math.isqrt(dx_units * dx_units + dy_units * dy_units))
        native_speed = tiles_per_second_to_logic_speed(self.projectile_speed)
        travel_seconds = (
            distance_units / max(native_speed, 1) * LOGIC_TICK_SECONDS
        )
        available_seconds = available_ms / 1000.0
        if available_seconds + 1e-12 < travel_seconds:
            move_x_units, move_y_units = vector_towards_logic_units(
                dx_units,
                dy_units,
                speed_work_for_duration(native_speed, available_seconds),
            )
            self.hook_position = Position(
                logic_units_to_tiles(
                    tiles_to_logic_units(self.hook_position.x) + move_x_units
                ),
                logic_units_to_tiles(
                    tiles_to_logic_units(self.hook_position.y) + move_y_units
                ),
            )
            return 0.0

        self.hook_position = Position(target.position.x, target.position.y)
        remaining_ms = max(0.0, available_ms - travel_seconds * 1000.0)
        source_kind = getattr(entity.card_stats, "name", None)
        if not target.can_receive_forced_movement(source_kind, "hook"):
            self._cancel(entity, target)
            return 0.0

        from ..entities import Building

        if not isinstance(target, Building):
            target.forced_movement_active = True
            # Hook displacement interrupts attack work and charge state, but
            # does not itself erase the victim's lock. After the drag, normal
            # reach/validity rules decide whether that target is retained.
            target.interrupt_by_forced_movement(
                source_kind=source_kind,
                movement_kind="hook",
            )
        self.state = "drag"
        return remaining_ms

    def _advance_drag(self, entity: 'Entity', target: 'Entity', dt: float) -> None:
        from ..entities import Building

        dx_units = tiles_to_logic_units(entity.position.x - target.position.x)
        dy_units = tiles_to_logic_units(entity.position.y - target.position.y)
        distance_units = math.isqrt(dx_units * dx_units + dy_units * dy_units)
        desired_distance_units = tiles_to_logic_units(
            entity.get_collision_radius()
            + target.get_collision_radius()
            + self.drag_margin
        )
        remaining_units = max(0, distance_units - desired_distance_units)
        if remaining_units <= 0 or distance_units <= 0:
            self._finish(entity, target)
            return

        pulls_self = self.drag_back_as_attractor and isinstance(target, Building)
        drag_speed = tiles_per_second_to_logic_speed(
            self.drag_self_speed if pulls_self else self.drag_back_speed
        )
        movement_units = min(
            remaining_units,
            speed_work_for_duration(drag_speed, max(0.0, dt)),
        )
        if movement_units <= 0:
            return

        moved_target = False
        moved_self = False
        if not pulls_self:
            target_dx_units, target_dy_units = normalized_vector_logic_units(
                dx_units,
                dy_units,
                movement_units,
            )
            target_candidate = Position(
                logic_units_to_tiles(
                    tiles_to_logic_units(target.position.x) + target_dx_units
                ),
                logic_units_to_tiles(
                    tiles_to_logic_units(target.position.y) + target_dy_units
                ),
            )
            if self._can_force_move(target, target_candidate):
                target.position = target_candidate
                moved_target = True
        else:
            self_dx_units, self_dy_units = normalized_vector_logic_units(
                -dx_units,
                -dy_units,
                movement_units,
            )
            self_candidate = Position(
                logic_units_to_tiles(
                    tiles_to_logic_units(entity.position.x) + self_dx_units
                ),
                logic_units_to_tiles(
                    tiles_to_logic_units(entity.position.y) + self_dy_units
                ),
            )
            if self._can_force_move(entity, self_candidate):
                entity.position = self_candidate
                moved_self = True

        battle = entity.battle_state
        if moved_target:
            battle.sync_fast_target_entity(target)
        if moved_self:
            battle.sync_fast_target_entity(entity)
        if not moved_target and not moved_self:
            self._finish(entity, target)
            return

        new_dx_units = tiles_to_logic_units(entity.position.x - target.position.x)
        new_dy_units = tiles_to_logic_units(entity.position.y - target.position.y)
        if math.isqrt(
            new_dx_units * new_dx_units + new_dy_units * new_dy_units
        ) <= desired_distance_units:
            self._finish(entity, target)

    @staticmethod
    def _can_force_move(entity: 'Entity', candidate: Position) -> bool:
        battle = entity.battle_state
        if not battle.is_entity_position_in_bounds(candidate, entity):
            return False
        radius = entity.get_collision_radius()
        return not battle.is_position_occupied_by_building(
            candidate,
            radius,
            movement_collision=True,
        )

    def _finish(self, entity: 'Entity', target: 'Entity') -> None:
        if target is not None:
            target.forced_movement_active = False
        self.state = "idle"
        self.hook_target_id = None
        self.windup_remaining_ms = 0.0
        self.hook_position = None
        entity._special_move_active = False
        entity._special_move_consumed_tick = True

    def _cancel(self, entity: 'Entity', target: Optional['Entity']) -> None:
        self._finish(entity, target)
        entity.target_id = None

    def _target(self, entity: 'Entity'):
        battle = getattr(entity, "battle_state", None)
        if battle is None or self.hook_target_id is None:
            return None
        return battle.entities.get(self.hook_target_id)
