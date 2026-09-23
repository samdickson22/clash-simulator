from __future__ import annotations

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.kinematics import tiles_to_logic_units


def _reference(
    battle: BattleState,
    position: Position,
    mover_radius: float,
    *,
    ignore_building_id: int | None = None,
    movement_collision: bool = False,
) -> bool:
    effective_radius = (
        min(float(mover_radius), 0.5)
        if movement_collision
        else float(mover_radius)
    )
    buildings = battle._alive_buildings if battle.fast_path else battle.entities.values()
    for entity in buildings:
        if not battle.fast_path and (
            not isinstance(entity, Building) or not entity.is_alive
        ):
            continue
        if ignore_building_id is not None and entity.id == ignore_building_id:
            continue
        radius = getattr(entity.card_stats, "collision_radius", 1.0) or 1.0
        collision = tiles_to_logic_units(float(radius) + effective_radius)
        dx = tiles_to_logic_units(position.x - entity.position.x)
        dy = tiles_to_logic_units(position.y - entity.position.y)
        if dx * dx + dy * dy < collision * collision:
            return True
    return False


def test_inline_building_overlap_matches_helper_geometry() -> None:
    battle = BattleState(fast_path=True)
    card = battle.card_loader.get_card("Tesla")
    assert card is not None
    building = battle._spawn_entity(Building, Position(9.5, 10.5), 0, card)
    battle._refresh_fast_path_caches()

    for position in (
        Position(9.5, 10.5),
        Position(9.5, 11.499499999),
        Position(9.5, 11.4995),
        Position(10.4995, 10.5),
        Position(0.0, 0.0),
    ):
        for mover_radius in (0.0, 0.2, 0.5, 1.0):
            for movement_collision in (False, True):
                expected = _reference(
                    battle,
                    position,
                    mover_radius,
                    movement_collision=movement_collision,
                )
                assert battle.is_position_occupied_by_building(
                    position,
                    mover_radius,
                    movement_collision=movement_collision,
                ) is expected
                assert not battle.is_position_occupied_by_building(
                    position,
                    mover_radius,
                    ignore_building_id=building.id,
                    movement_collision=movement_collision,
                )
