import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clasher.arena import Position
from clasher.entities import Building, TargetType, Troop
from clasher.factory.dynamic_factory import building_from_values, troop_from_values


def _make_building(entity_id: int, x: float, y: float) -> Building:
    stats = building_from_values(
        name=f"Building{entity_id}",
        hitpoints=1200,
        damage=80,
        range_tiles=6.0,
        sight_range_tiles=6.0,
        hit_speed_ms=1000,
        deploy_time_ms=1000,
        collision_radius_tiles=1.0,
        lifetime_ms=None,
        target_type="TID_TARGETS_AIR_AND_GROUND",
    )
    return Building(
        id=entity_id,
        position=Position(x, y),
        player_id=1,
        card_stats=stats,
        hitpoints=1200,
        max_hitpoints=1200,
        damage=80,
        range=6.0,
        sight_range=6.0,
    )


def _make_building_targeting_troop(x: float, y: float, sight_range: float) -> Troop:
    stats = troop_from_values(
        name="TestGiant",
        hitpoints=2000,
        damage=150,
        speed_tiles_per_min=60.0,
        range_tiles=1.0,
        sight_range_tiles=sight_range,
        target_type="TID_TARGETS_BUILDINGS",
        attacks_ground=True,
        attacks_air=False,
    )
    return Troop(
        id=1,
        position=Position(x, y),
        player_id=0,
        card_stats=stats,
        hitpoints=2000,
        max_hitpoints=2000,
        damage=150,
        range=1.0,
        sight_range=sight_range,
        speed=60.0,
        target_type=TargetType.GROUND,
    )


def test_does_not_switch_to_out_of_sight_building_even_if_closer():
    troop = _make_building_targeting_troop(x=14.5, y=17.0, sight_range=5.0)
    current_target = _make_building(entity_id=2, x=14.5, y=29.0)  # farther
    new_target = _make_building(entity_id=3, x=8.5, y=17.0)  # closer but out of sight

    assert troop._should_switch_target(current_target, new_target) is False


def test_switches_to_in_sight_closer_building():
    troop = _make_building_targeting_troop(x=14.5, y=17.0, sight_range=5.0)
    current_target = _make_building(entity_id=2, x=14.5, y=29.0)  # farther
    new_target = _make_building(entity_id=3, x=11.0, y=17.0)  # closer and in sight

    assert troop._should_switch_target(current_target, new_target) is True

