from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.factory.dynamic_factory import building_from_values


def _make_building_stats(name: str, collision_radius: float = 1.0):
    return building_from_values(
        name=name,
        hitpoints=1000,
        damage=80,
        range_tiles=6.0,
        sight_range_tiles=6.0,
        hit_speed_ms=1000,
        deploy_time_ms=1000,
        collision_radius_tiles=collision_radius,
        lifetime_ms=None,
        target_type="TID_TARGETS_AIR_AND_GROUND",
    )


def test_standard_building_uses_3x3_placement_footprint() -> None:
    battle = BattleState()
    cannon = _make_building_stats("Cannon")
    battle._spawn_entity(Building, Position(9.5, 10.5), 0, cannon)

    # 2 tiles apart vertically still overlaps for 3x3 footprints.
    assert battle.is_building_placement_occupied(Position(9.5, 12.5), cannon)
    # 3 tiles apart touches edge but does not overlap.
    assert not battle.is_building_placement_occupied(Position(9.5, 13.5), cannon)


def test_tesla_uses_2x2_placement_footprint() -> None:
    battle = BattleState()
    tesla = _make_building_stats("Tesla", collision_radius=0.5)
    battle._spawn_entity(Building, Position(9.5, 10.5), 0, tesla)

    # 1 tile apart overlaps for 2x2.
    assert battle.is_building_placement_occupied(Position(9.5, 11.5), tesla)
    # 2 tiles apart touches edge but does not overlap.
    assert not battle.is_building_placement_occupied(Position(9.5, 12.5), tesla)


def test_compact_building_footprint_is_data_driven_not_name_driven() -> None:
    battle = BattleState()
    compact = _make_building_stats("CustomCompact", collision_radius=0.5)
    battle._spawn_entity(Building, Position(9.5, 10.5), 0, compact)

    assert battle._building_footprint_size_tiles(compact) == 2
    assert battle.is_building_placement_occupied(Position(9.5, 11.5), compact)
    assert not battle.is_building_placement_occupied(
        Position(9.5, 12.5),
        compact,
    )


def test_destroyed_building_immediately_releases_its_placement_footprint() -> None:
    for fast_path in (False, True):
        battle = BattleState(fast_path=fast_path)
        cannon = _make_building_stats("Cannon")
        building = battle._spawn_entity(
            Building,
            Position(9.5, 10.5),
            0,
            cannon,
        )

        assert battle.is_building_placement_occupied(
            Position(9.5, 10.5),
            cannon,
        )
        building.take_damage(building.hitpoints)
        assert not battle.is_building_placement_occupied(
            Position(9.5, 10.5),
            cannon,
        )
