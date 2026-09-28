import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, TargetType, Troop
from clasher.factory.dynamic_factory import building_from_values, troop_from_values


def _make_building(
    entity_id: int,
    x: float,
    y: float,
    *,
    name: str = "Building",
    player_id: int = 1,
) -> Building:
    stats = building_from_values(
        name=name,
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
        player_id=player_id,
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
        speed_logic_units_per_tick=60.0,
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


def _make_normal_troop(x: float, y: float, sight_range: float) -> Troop:
    troop = _make_building_targeting_troop(x, y, sight_range)
    troop.card_stats.targets_only_buildings = False
    return troop


def test_does_not_switch_to_out_of_sight_building_even_if_closer():
    troop = _make_building_targeting_troop(x=14.5, y=17.0, sight_range=5.0)
    current_target = _make_building(entity_id=2, x=14.5, y=29.0)  # farther
    new_target = _make_building(entity_id=3, x=7.4, y=17.0)  # closer but out of sight

    assert troop._should_switch_target(current_target, new_target) is False


def test_switches_to_in_sight_closer_building():
    troop = _make_building_targeting_troop(x=14.5, y=17.0, sight_range=5.0)
    current_target = _make_building(entity_id=2, x=14.5, y=29.0)  # farther
    new_target = _make_building(entity_id=3, x=11.0, y=17.0)  # closer and in sight

    assert troop._should_switch_target(current_target, new_target) is True


def test_building_targeting_troop_ignores_out_of_sight_bridge_cannon():
    troop = _make_building_targeting_troop(x=14.5, y=17.0, sight_range=5.0)
    cannon = _make_building(entity_id=10, x=3.5, y=18.0, name="Cannon", player_id=1)
    king = _make_building(entity_id=11, x=9.0, y=29.5, name="KingTower", player_id=1)

    target = troop.get_nearest_target({10: cannon, 11: king})
    assert target is king


def test_building_targeting_troop_can_still_acquire_in_sight_defensive_building():
    troop = _make_building_targeting_troop(x=14.5, y=17.0, sight_range=5.0)
    cannon = _make_building(entity_id=10, x=12.0, y=18.0, name="Cannon", player_id=1)
    king = _make_building(entity_id=11, x=9.0, y=29.5, name="KingTower", player_id=1)

    target = troop.get_nearest_target({10: cannon, 11: king})
    assert target is cannon


def test_building_targeting_troop_acquires_character_marked_as_building_target():
    attacker = _make_building_targeting_troop(x=9.0, y=10.0, sight_range=6.0)
    objective = _make_normal_troop(x=9.0, y=12.0, sight_range=6.0)
    objective.id = 10
    objective.player_id = 1
    objective.card_stats.building_target = True
    distraction = _make_normal_troop(x=9.0, y=11.0, sight_range=6.0)
    distraction.id = 11
    distraction.player_id = 1

    assert attacker.get_nearest_target({10: objective, 11: distraction}) is objective
    assert attacker._should_switch_target(
        _make_building(entity_id=12, x=9.0, y=14.0),
        objective,
    )


def test_building_only_attack_eligibility_uses_the_serialized_target_category():
    attacker = _make_building_targeting_troop(
        x=9.0,
        y=10.0,
        sight_range=6.0,
    )
    ordinary_troop = _make_normal_troop(
        x=9.0,
        y=10.5,
        sight_range=6.0,
    )
    ordinary_troop.player_id = 1
    physical_building = _make_building(
        entity_id=10,
        x=9.0,
        y=10.5,
    )
    moving_objective = _make_normal_troop(
        x=9.0,
        y=10.5,
        sight_range=6.0,
    )
    moving_objective.player_id = 1
    moving_objective.card_stats.building_target = True

    assert not attacker.can_attack_target(ordinary_troop)
    assert attacker.can_attack_target(physical_building)
    assert attacker.can_attack_target(moving_objective)


def test_fast_targeting_preserves_character_building_target_bit():
    battle = BattleState(fast_path=True)
    attacker = _make_building_targeting_troop(x=9.0, y=10.0, sight_range=6.0)
    attacker.id = 100
    objective = _make_normal_troop(x=9.0, y=12.0, sight_range=6.0)
    objective.id = 101
    objective.player_id = 1
    objective.card_stats.building_target = True
    distraction = _make_normal_troop(x=9.0, y=11.0, sight_range=6.0)
    distraction.id = 102
    distraction.player_id = 1
    for entity in (attacker, objective, distraction):
        entity.battle_state = battle
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        battle.entities[entity.id] = entity
    battle._refresh_fast_path_caches()

    assert attacker.get_nearest_target(battle.entities) is objective


def test_normal_troop_acquires_closest_eligible_target_not_target_category():
    troop = _make_normal_troop(x=9.0, y=10.0, sight_range=6.0)
    closer_building = _make_building(entity_id=10, x=9.0, y=12.0, player_id=1)
    farther_troop = _make_normal_troop(x=9.0, y=14.0, sight_range=6.0)
    farther_troop.id = 11
    farther_troop.player_id = 1

    target = troop.get_nearest_target({10: closer_building, 11: farther_troop})
    assert target is closer_building


def test_normal_troop_switching_uses_distance_not_target_category():
    troop = _make_normal_troop(x=9.0, y=10.0, sight_range=6.0)
    closer_building = _make_building(entity_id=10, x=9.0, y=12.0, player_id=1)
    farther_troop = _make_normal_troop(x=9.0, y=14.0, sight_range=6.0)
    farther_troop.id = 11
    farther_troop.player_id = 1

    assert troop._should_switch_target(farther_troop, closer_building)
    assert not troop._should_switch_target(closer_building, farther_troop)


@pytest.mark.parametrize("princess_y, visible", [(25.5, True), (29.5, False)])
def test_walking_king_target_can_switch_to_nearer_visible_princess(princess_y, visible):
    troop = _make_building_targeting_troop(x=9.0, y=20.0, sight_range=6.0)
    current_target = _make_building(entity_id=20, x=9.0, y=35.0, name="KingTower", player_id=1)
    new_target = _make_building(entity_id=21, x=14.5, y=princess_y, name="Tower", player_id=1)

    assert not troop.is_within_attack_reach(new_target)
    assert troop.native_target_distance_to(new_target) < troop.native_target_distance_to(current_target)
    assert troop.is_within_sight(new_target) is visible
    assert troop._should_switch_target(current_target, new_target) is visible


def test_can_switch_from_king_to_in_sight_defensive_building():
    troop = _make_building_targeting_troop(x=9.0, y=20.0, sight_range=6.0)
    current_target = _make_building(entity_id=20, x=9.0, y=29.5, name="KingTower", player_id=1)
    new_target = _make_building(entity_id=21, x=10.5, y=20.5, name="Cannon", player_id=1)

    assert troop._should_switch_target(current_target, new_target) is True


def test_can_switch_from_king_to_princess_when_attackable():
    troop = _make_building_targeting_troop(x=13.8, y=24.9, sight_range=6.0)
    current_target = _make_building(entity_id=20, x=9.0, y=29.5, name="KingTower", player_id=1)
    new_target = _make_building(entity_id=21, x=14.5, y=25.5, name="Tower", player_id=1)

    assert troop._should_switch_target(current_target, new_target) is True


def test_pathfind_on_bridge_keeps_crossing_toward_locked_target():
    troop = _make_building_targeting_troop(x=3.5, y=16.0, sight_range=6.0)
    troop.player_id = 0
    king = _make_building(entity_id=30, x=9.0, y=29.5, name="KingTower", player_id=1)

    target = troop._get_pathfind_target(king)
    assert target == Position(3.5, 17.5)


def test_building_keeps_attack_lock_when_a_closer_enemy_arrives():
    battle = BattleState()
    building = _make_building(entity_id=100, x=9.0, y=10.0, player_id=0)
    current = _make_normal_troop(x=9.0, y=14.0, sight_range=6.0)
    current.id = 101
    current.player_id = 1
    closer = _make_normal_troop(x=9.0, y=12.0, sight_range=6.0)
    closer.id = 102
    closer.player_id = 1
    for entity in (building, current, closer):
        entity.battle_state = battle
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        battle.entities[entity.id] = entity
    building.target_id = current.id

    building.update(battle.dt, battle)

    assert building.target_id == current.id


def test_building_retargets_when_locked_enemy_leaves_attack_range():
    battle = BattleState()
    building = _make_building(entity_id=100, x=9.0, y=10.0, player_id=0)
    departed = _make_normal_troop(x=9.0, y=18.0, sight_range=6.0)
    departed.id = 101
    departed.player_id = 1
    replacement = _make_normal_troop(x=9.0, y=13.0, sight_range=6.0)
    replacement.id = 102
    replacement.player_id = 1
    for entity in (building, departed, replacement):
        entity.battle_state = battle
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        battle.entities[entity.id] = entity
    building.target_id = departed.id

    building.update(battle.dt, battle)

    assert building.target_id == replacement.id


def test_building_releases_lock_outside_native_range():
    battle = BattleState()
    building = _make_building(entity_id=100, x=9.0, y=10.0, player_id=0)
    current = _make_normal_troop(x=9.0, y=10.0, sight_range=6.0)
    current.id = 101
    current.player_id = 1
    replacement = _make_normal_troop(x=9.0, y=12.0, sight_range=6.0)
    replacement.id = 102
    replacement.player_id = 1
    current.position.y = (
        building.position.y
        + building.reach_distance_to(current, building.range + building.get_collision_radius())
        + 0.024
    )
    for entity in (building, current, replacement):
        entity.battle_state = battle
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        battle.entities[entity.id] = entity
    building.target_id = current.id

    building.update(battle.dt, battle)

    assert not building.is_within_attack_reach(current)
    assert not building.is_within_target_keep_reach(current)
    assert building.target_id == replacement.id


def test_troop_keeps_connected_tower_lock_when_distraction_arrives():
    battle = BattleState()
    attacker = _make_normal_troop(x=9.0, y=12.0, sight_range=6.0)
    attacker.id = 100
    attacker.player_id = 0
    tower = _make_building(entity_id=101, x=9.0, y=13.0, name="Tower", player_id=1)
    distraction = _make_normal_troop(x=9.0, y=12.1, sight_range=6.0)
    distraction.id = 102
    distraction.player_id = 1
    for entity in (attacker, tower, distraction):
        entity.battle_state = battle
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        battle.entities[entity.id] = entity
    attacker.target_id = tower.id

    attacker.update(battle.dt, battle)

    assert attacker.target_id == tower.id


def test_troop_can_retarget_to_closer_distraction_while_pathing():
    battle = BattleState()
    attacker = _make_normal_troop(x=9.0, y=10.0, sight_range=6.0)
    attacker.id = 100
    attacker.player_id = 0
    tower = _make_building(entity_id=101, x=9.0, y=16.0, name="Tower", player_id=1)
    distraction = _make_normal_troop(x=9.0, y=13.0, sight_range=6.0)
    distraction.id = 102
    distraction.player_id = 1
    for entity in (attacker, tower, distraction):
        entity.battle_state = battle
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        battle.entities[entity.id] = entity
    attacker.target_id = tower.id

    attacker.update(battle.dt, battle)

    assert attacker.target_id == distraction.id
