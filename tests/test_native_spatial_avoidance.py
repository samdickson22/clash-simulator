"""Protect the native Goblin spawn steering boundary and bucket semantics."""

import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.native_spatial import NativeAvoidanceGrid

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_spatial_avoidance_15_535_86.json")
    .read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
def test_goblin_spawn_matches_native_golem_steering(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle._spawn_unit_at_position(
        Position(*(v / 1000 for v in REFERENCE["xy"])),
        REFERENCE["owner"],
        battle.card_loader.get_card("IceGolem"),
        deploy_delay_override=0,
        snap_to_valid=False,
    )
    golem = next(iter(battle.entities.values()))
    golem._movement_target_id = 2
    golem._facing_x_units, golem._facing_y_units = REFERENCE["facing"]
    golem._native_avoidance = REFERENCE["avoidance"]
    player = battle.players[REFERENCE["owner"]]
    player.hand = [REFERENCE["command"]["name"]]
    player.elixir = 10
    assert battle.deploy_card(
        player.player_id,
        REFERENCE["command"]["name"],
        Position(*REFERENCE["command"]["xy"]),
    )
    battle._native_avoidance_grid = NativeAvoidanceGrid(battle.entities.values())
    golem._update_native_avoidance(battle)
    assert golem._native_avoidance == REFERENCE["expected_avoidance"]


def spawn(battle, x, y):
    battle._spawn_unit_at_position(
        Position(x, y), 0, battle.card_loader.get_card("Knight"),
        deploy_delay_override=0, snap_to_valid=False,
    )
    return battle.entities[max(battle.entities)]


def test_bucket_order_keeps_manager_order_within_first_shared_bucket():
    battle = BattleState()
    battle.entities.clear()
    right = spawn(battle, 5.4, 10)
    left = spawn(battle, 5.2, 10)
    grid = NativeAvoidanceGrid(battle.entities.values())
    # Both extents first intersect the query in the same bucket. Sorting
    # bodies by center would reverse this native append order.
    assert list(grid.query(5300, 10000, 500)) == [right, left]


def test_indexed_extent_survives_movement_and_new_bodies_append():
    battle = BattleState()
    battle.entities.clear()
    first = spawn(battle, 5, 10)
    grid = NativeAvoidanceGrid(battle.entities.values())
    first.position = Position(15, 20)
    second = spawn(battle, 5, 10)
    grid.add(second)
    # Bucket membership is from phase start; precise circle tests later use
    # the live body position. An object spanning buckets appears only once.
    assert list(grid.query(5000, 10000, 500)) == [first, second]
    assert list(grid.query(15000, 20000, 500)) == []
