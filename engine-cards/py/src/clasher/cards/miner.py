from dataclasses import dataclass
import math

from ..arena import Position
from ..balance import LOGIC_SPAWN_PATHFIND_REACHED_RADIUS_FROM_SPEED
from ..mechanics.mechanic_base import BaseMechanic
from ..kinematics import (
    LOGIC_TICK_SECONDS,
    logic_units_to_tiles,
    speed_work_for_duration,
    spawn_path_travel_tick_count,
    tiles_to_logic_units,
    vector_towards_logic_units,
)


@dataclass
class UndergroundDeployment(BaseMechanic):
    """Move an untargetable underground deployment from its King Tower.

    The regular character deploy time is the emergence animation after the
    transport reaches its destination. ``travel_speed_logic_units_per_tick``
    uses the same native movement unit as every troop/projectile Speed field.
    """

    # Miner uses a distinct underground transport speed of 650 even though
    # its surfaced movement speed is 90.
    travel_speed_logic_units_per_tick: float = 650.0

    def on_attach(self, entity) -> None:
        raw = getattr(getattr(entity, "card_stats", None), "_raw_entry", {}) or {}
        character = raw.get("summonCharacterData", {}) or {}
        self.travel_speed_logic_units_per_tick = float(
            character.get(
                "spawnPathfindSpeed",
                self.travel_speed_logic_units_per_tick,
            )
        )
        emergence_delay = max(
            0.0,
            float(getattr(entity, "deploy_delay_remaining", 0.0) or 0.0),
        )
        battle = getattr(entity, "battle_state", None)
        destination = Position(entity.position.x, entity.position.y)
        king = (
            battle.arena.BLUE_KING_TOWER
            if entity.player_id == 0
            else battle.arena.RED_KING_TOWER
        )
        origin = Position(king.x, king.y)
        dx_units = tiles_to_logic_units(destination.x - origin.x)
        dy_units = tiles_to_logic_units(destination.y - origin.y)
        distance_units = math.isqrt(dx_units * dx_units + dy_units * dy_units)
        travel_ticks = spawn_path_travel_tick_count(
            distance_units,
            max(1, round(self.travel_speed_logic_units_per_tick)),
            reached_radius_from_speed=(
                LOGIC_SPAWN_PATHFIND_REACHED_RADIUS_FROM_SPEED
            ),
        )
        travel_duration = travel_ticks * LOGIC_TICK_SECONDS

        entity._underground_origin = origin
        entity._underground_destination = destination
        entity._underground_travel_duration = travel_duration
        entity._underground_emergence_delay = emergence_delay
        entity.deploy_delay_remaining = travel_duration + emergence_delay
        entity.placement_delay_total = entity.deploy_delay_remaining
        entity.placement_pending = entity.deploy_delay_remaining > 1e-9
        entity.position = Position(origin.x, origin.y)
        entity._underground_deployment = entity.placement_pending
        if entity._underground_deployment:
            entity._special_move_active = True

    def on_spawn(self, entity) -> None:
        destination = getattr(entity, "_underground_destination", None)
        if destination is not None:
            entity.position = Position(destination.x, destination.y)
        entity._underground_deployment = False
        entity._special_move_active = False

    def on_deploy_tick(self, entity, dt_ms: int) -> None:
        if not getattr(entity, "_underground_deployment", False):
            return
        destination = entity._underground_destination
        travel_duration = float(entity._underground_travel_duration)
        total = float(getattr(entity, "placement_delay_total", 0.0) or 0.0)
        remaining = float(getattr(entity, "deploy_delay_remaining", 0.0) or 0.0)
        elapsed = max(0.0, total - remaining)
        frame_seconds = max(0.0, float(dt_ms)) / 1000.0
        if (
            travel_duration <= 0
            or elapsed + frame_seconds >= travel_duration - 1e-12
        ):
            entity.position = Position(destination.x, destination.y)
            return

        dx_units = tiles_to_logic_units(destination.x - entity.position.x)
        dy_units = tiles_to_logic_units(destination.y - entity.position.y)
        move_x_units, move_y_units = vector_towards_logic_units(
            dx_units,
            dy_units,
            speed_work_for_duration(
                self.travel_speed_logic_units_per_tick,
                frame_seconds,
            ),
        )
        entity.position = Position(
            logic_units_to_tiles(
                tiles_to_logic_units(entity.position.x) + move_x_units
            ),
            logic_units_to_tiles(
                tiles_to_logic_units(entity.position.y) + move_y_units
            ),
        )

    def on_tick(self, entity, dt_ms: int) -> None:
        if getattr(entity, "_underground_deployment", False) and getattr(
            entity, "deploy_delay_remaining", 0.0
        ) <= 0:
            entity._underground_deployment = False
            entity._special_move_active = False

    def take_damage_during_dash(self, entity, damage: float) -> bool:
        return not getattr(entity, "_underground_deployment", False)

    def allows_effect(
        self,
        entity,
        source_kind: str | None,
        *,
        affects_hidden: bool = False,
    ) -> bool:
        """Keep underground travel distinct from ordinary deployment state."""
        del affects_hidden
        return not getattr(entity, "_underground_deployment", False)

    def allows_forced_movement(
        self,
        entity,
        source_kind: str | None,
        movement_kind: str,
    ) -> bool | None:
        if getattr(entity, "_underground_deployment", False):
            return False
        return None

    def blocks_status_effect(self, entity) -> bool:
        return getattr(entity, "_underground_deployment", False)

    def blocks_targeting(self, entity) -> bool:
        return getattr(entity, "_underground_deployment", False)

    def blocks_ground_collision(self, entity) -> bool:
        return getattr(entity, "_underground_deployment", False)


# Compatibility for code importing the old class name.
MinerTunnel = UndergroundDeployment
