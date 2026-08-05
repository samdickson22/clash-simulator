from dataclasses import dataclass

from ..mechanic_base import BaseMechanic
from ...arena import Position
from ...unit_traits import is_knockback_immune
from ...kinematics import (
    logic_units_to_tiles,
    normalized_vector_logic_units,
    tiles_to_logic_units,
)


def apply_directional_knockback(
    target,
    battle_state,
    direction_x_units: int,
    direction_y_units: int,
    distance_tiles: float,
    *,
    source_kind: str | None = None,
    ignores_mass: bool = False,
    interrupts_combat: bool = True,
) -> bool:
    """Schedule native pushback along an already-committed direction."""
    from ...entities import Building

    if distance_tiles <= 0 or isinstance(target, Building) or not target.is_alive:
        return False
    if not target.can_receive_forced_movement(source_kind, "knockback"):
        return False
    if not ignores_mass and is_knockback_immune(target.card_stats):
        return False
    if direction_x_units == 0 and direction_y_units == 0:
        return False

    distance_units = min(10_000, tiles_to_logic_units(distance_tiles))
    move_x_units, move_y_units = normalized_vector_logic_units(
        int(direction_x_units),
        int(direction_y_units),
        distance_units,
    )
    current_x_units = tiles_to_logic_units(target.position.x)
    current_y_units = tiles_to_logic_units(target.position.y)
    candidate = Position(
        logic_units_to_tiles(current_x_units + move_x_units),
        logic_units_to_tiles(current_y_units + move_y_units),
    )
    return target.begin_knockback(
        candidate,
        distance_units,
        source_kind=source_kind,
        interrupts_combat=interrupts_combat,
    )


def apply_radial_knockback(
    target,
    battle_state,
    origin: Position,
    distance_tiles: float,
    *,
    source_kind: str | None = None,
    ignores_mass: bool = False,
    fallback_direction: tuple[float, float] | None = None,
    interrupts_combat: bool = True,
) -> bool:
    """Schedule one native movement-component pushback.

    This is shared by projectile splashes, on-hit mechanics, and delayed
    death payloads so all radial pushback uses the same mass, fixed-point
    velocity curve, phase ordering, attack-windup, and charge semantics.
    """
    dx_units = tiles_to_logic_units(target.position.x - origin.x)
    dy_units = tiles_to_logic_units(target.position.y - origin.y)
    if dx_units == 0 and dy_units == 0:
        if fallback_direction is not None:
            dx_units = round(float(fallback_direction[0]) * 1_000_000)
            dy_units = round(float(fallback_direction[1]) * 1_000_000)
        if dx_units == 0 and dy_units == 0:
            # LogicMovementComponent::doPushback resolves an exact-center
            # vector along ownership-rotated X instead of dropping the push.
            dx_units = 1 if target.player_id == 0 else -1
    return apply_directional_knockback(
        target,
        battle_state,
        dx_units,
        dy_units,
        distance_tiles,
        source_kind=source_kind,
        ignores_mass=ignores_mass,
        interrupts_combat=interrupts_combat,
    )


@dataclass
class KnockbackOnHit(BaseMechanic):
    """Mechanic that knocks back targets on attack hit"""
    knockback_distance: float = 1.0  # tiles
    knockback_chance: float = 1.0
    ignores_mass: bool = False

    def on_attack_hit(self, entity, target) -> None:
        """Apply knockback effect to target"""
        source_kind = getattr(getattr(entity, "card_stats", None), "name", None)
        if not target.can_receive_effect(source_kind):
            return
        rng = getattr(getattr(entity, "battle_state", None), "rng", None)
        roll = rng.random() if rng is not None else 0.0
        if roll <= self.knockback_chance:
            battle_state = getattr(entity, "battle_state", None)
            if battle_state is None:
                return
            apply_radial_knockback(
                target,
                battle_state,
                entity.position,
                self.knockback_distance,
                source_kind=source_kind,
                ignores_mass=self.ignores_mass,
            )
