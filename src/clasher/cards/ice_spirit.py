from dataclasses import dataclass, field
import math
from typing import TYPE_CHECKING

from ..arena import Position
from ..mechanics.mechanic_base import BaseMechanic
from ..kinematics import (
    logic_units_to_tiles,
    pending_projectile_duration_ms,
    speed_work_for_duration,
    tiles_to_logic_units,
    vector_towards_logic_units,
)

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class IceSpiritFreeze(BaseMechanic):
    """Freezes and damages nearby enemies when Ice Spirit connects."""
    freeze_radius: float = 1.5
    freeze_duration_ms: int = 1200
    hop_duration_ms: int = 200
    jump_speed_logic_units_per_tick: int = 400
    _pending_target: 'Entity | None' = field(default=None, init=False, repr=False)
    _pending_active: bool = field(default=False, init=False, repr=False)

    def on_attach(self, entity: 'Entity') -> None:
        entity._force_melee_attack = True
        entity._ice_spirit_detonated = False
        entity._ice_spirit_jump_timer = 0.0
        entity._ice_spirit_jump_target = None
        entity._ice_spirit_jump_destination = None
        projectile = getattr(entity.card_stats, "projectile_data", {}) or {}
        if projectile.get("radius") is not None:
            self.freeze_radius = projectile["radius"] / 1000.0
        if projectile.get("buffTime") is not None:
            self.freeze_duration_ms = int(projectile["buffTime"])
        self.jump_speed_logic_units_per_tick = int(
            projectile.get("speed", self.jump_speed_logic_units_per_tick)
            or self.jump_speed_logic_units_per_tick
        )

    def on_movement_tick(self, entity: 'Entity', dt_ms: int) -> None:
        """Advance the committed jump in component type 1."""
        target_id = getattr(entity, '_ice_spirit_jump_target', None)
        if target_id is None:
            return
        target = entity.battle_state.entities.get(target_id)
        entity._ice_spirit_jump_timer += dt_ms
        if target is not None:
            target_x, target_y = target.position.x, target.position.y
            entity._ice_spirit_jump_destination = (target_x, target_y)
        else:
            target_x, target_y = getattr(
                entity,
                '_ice_spirit_jump_destination',
                (entity.position.x, entity.position.y),
            )
        dx_units = tiles_to_logic_units(target_x - entity.position.x)
        dy_units = tiles_to_logic_units(target_y - entity.position.y)
        remaining_units = math.isqrt(
            dx_units * dx_units + dy_units * dy_units
        )
        travel_units = speed_work_for_duration(
            self.jump_speed_logic_units_per_tick,
            dt_ms / 1000.0,
        )
        move_x_units, move_y_units = vector_towards_logic_units(
            dx_units,
            dy_units,
            travel_units,
        )
        entity.position.x = logic_units_to_tiles(
            tiles_to_logic_units(entity.position.x) + move_x_units
        )
        entity.position.y = logic_units_to_tiles(
            tiles_to_logic_units(entity.position.y) + move_y_units
        )
        if remaining_units <= travel_units:
            entity._ice_spirit_jump_target = None
            entity._ice_spirit_jump_destination = None
            entity._special_move_active = False
            entity._special_move_consumed_tick = True
            # Once the Spirit jumps it is an unstoppable area projectile. Its
            # nova resolves at the committed impact point even if the primary
            # target is defeated during flight.
            origin = Position(entity.position.x, entity.position.y)
            self._freeze(entity, origin)
            self._pending_active = False
            self._pending_target = None
            entity._ice_spirit_detonated = True
            entity.take_damage(entity.hitpoints)

    def on_death(self, entity: 'Entity') -> None:
        # Being destroyed before connecting does not trigger the freeze nova.
        return

    def on_attack_start(self, entity: 'Entity', target: 'Entity') -> None:
        # Native replaces the character with a projectile at launch. Keep
        # our flight carrier out of character avoidance through impact.
        entity._self_projectile_launched = True
        entity.entity_kind = 2
        entity._self_projectile_launch_tick = entity.battle_state.tick
        entity._ice_spirit_jump_origin = (entity.position.x, entity.position.y)
        entity._ice_spirit_jump_target = target.id
        entity._ice_spirit_jump_destination = (target.position.x, target.position.y)
        entity._ice_spirit_jump_timer = 0.0
        entity._special_move_active = True
        entity._special_move_consumed_tick = True
        self._pending_target = target
        self._pending_active = False
        if (
            not entity.is_alive
            and entity.id in getattr(entity.battle_state, "_combat_phase_eligible_ids", ())
        ):
            # Native creates a live projectile even when an earlier combat
            # component depleted the launching character this frame. This
            # object now carries that projectile, not the defeated troop.
            entity.hitpoints = 1
            entity.is_alive = True

    def activate_pending_damage(self, entity: 'Entity') -> None:
        """Publish homing damage after the launch frame's character ticks."""
        target = self._pending_target
        if target is None or self._pending_active or not entity.is_alive:
            return
        dx = tiles_to_logic_units(target.position.x - entity.position.x)
        dy = tiles_to_logic_units(target.position.y - entity.position.y)
        duration = pending_projectile_duration_ms(
            math.isqrt(dx * dx + dy * dy), self.jump_speed_logic_units_per_tick,
        )
        target._pending_projectile_max_duration_ms = max(
            target._pending_projectile_max_duration_ms, duration,
        )
        self._pending_active = True

    def pending_damage_against(self, entity: 'Entity', target: 'Entity') -> float:
        """Reserve only the committed primary target, not nearby splash victims."""
        if self._pending_active and entity.is_alive and target is self._pending_target:
            return max(0.0, float(entity.damage))
        return 0.0

    def modify_incoming_damage(self, entity: 'Entity', amount: float) -> float:
        return 0.0 if getattr(entity, "_special_move_active", False) else amount

    def allows_effect(
        self,
        entity: 'Entity',
        source_kind: str | None,
        *,
        affects_hidden: bool = False,
    ) -> bool:
        """Treat the committed self-projectile as absent from effect queries."""
        del source_kind, affects_hidden
        return not getattr(entity, "_special_move_active", False)

    def blocks_status_effect(self, entity: 'Entity') -> bool:
        return bool(getattr(entity, "_special_move_active", False))

    def blocks_targeting(self, entity: 'Entity') -> bool:
        return bool(getattr(entity, "_special_move_active", False))

    def blocks_ground_collision(self, entity: 'Entity') -> bool:
        return getattr(entity, "_ice_spirit_jump_target", None) is not None

    def _freeze(self, entity: 'Entity', origin: Position) -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        projectile = getattr(entity.card_stats, "projectile_data", {}) or {}
        affects_hidden = bool(projectile.get("affectsHidden", False))
        source_kind = getattr(entity.card_stats, "name", None)
        damage_targets = []
        for other in list(battle_state.entities.values()):
            if (
                other.player_id == entity.player_id
                or not other.is_alive
                or getattr(other, "entity_kind", 4) in {2, 3}
                or not entity.can_affect_target_plane(other)
            ):
                continue
            if (
                other.intersects_native_area(origin, self.freeze_radius)
                and other.can_receive_area_damage(
                    source_kind,
                    affects_hidden=affects_hidden,
                    source_entity=entity,
                )
            ):
                damage_targets.append(other)

        # The jump carries ordinary serialized projectile area semantics:
        # commit the full damage footprint first, then ask the manager for
        # buff recipients. The second query can see troops created by lethal
        # damage, but those new troops never receive another copy of damage.
        for other in damage_targets:
            other.take_damage(
                entity.damage,
                source_kind=source_kind,
                affects_hidden=affects_hidden,
            )

        for other in list(battle_state.entities.values()):
            if (
                other.player_id == entity.player_id
                or not other.is_alive
                or getattr(other, "entity_kind", 4) in {2, 3}
                or not entity.can_affect_target_plane(other)
                or not other.intersects_native_area(origin, self.freeze_radius)
                or not other.can_receive_area_damage(
                    source_kind,
                    affects_hidden=affects_hidden,
                    source_entity=entity,
                )
            ):
                continue
            other.apply_stun(
                self.freeze_duration_ms / 1000.0,
                source_kind=source_kind,
                affects_hidden=affects_hidden,
                interrupt_combat=False,
            )
