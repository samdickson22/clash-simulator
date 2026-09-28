import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.pathfinding import native_building_cost_cells

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/native_friendly_cannon_route_15_535_86.json"
    ).read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
def test_friendly_cannon_overlay_and_initial_route_match_native(fast_path):
    battle = BattleState(fast_path=fast_path)
    for _ in range(221):
        battle.step()
    for name, y in [("HogRider", 8.5), ("Cannon", 11.5)]:
        battle.players[0].hand = [name]
        assert battle.deploy_card(0, name, Position(3.5, y))
    for _ in range(21):
        battle.step()
    assert battle.tick == REFERENCE["tick"]
    assert set(native_building_cost_cells(battle)) == {
        (x, y) for x, y, cost in REFERENCE["overlay_cells"]
    }
    hog = next(e for e in battle.entities.values() if e.card_stats.name == "HogRider")
    assert hog._native_ground_route_cells == [
        tuple(cell) for cell in REFERENCE["route"]
    ]


@pytest.mark.parametrize("fast_path", [False, True])
def test_route_heading_survives_out_of_range_combat_observation(fast_path):
    reference = json.loads(
        (
            Path(__file__).parent
            / "fixtures/native_friendly_cannon_heading_15_535_86.json"
        ).read_text()
    )
    battle = BattleState(fast_path=fast_path)
    for _ in range(221):
        battle.step()
    for name, y in [("HogRider", 8.5), ("Cannon", 11.5)]:
        battle.players[0].hand = [name]
        assert battle.deploy_card(0, name, Position(3.5, y))
    samples = {row["elapsed"]: row for row in reference["samples"]}
    avoidance = {row["elapsed"]: row["value"] for row in reference["avoidance"]}
    for elapsed in range(1, max(samples) + 1):
        battle.step()
        hog = next(
            e for e in battle.entities.values() if e.card_stats.name == "HogRider"
        )
        if elapsed in avoidance:
            assert hog._native_avoidance == avoidance[elapsed]
        if elapsed in samples:
            row = samples[elapsed]
            assert (
                hog.position.distance_to(Position(row["x"] / 1000, row["y"] / 1000))
                <= 0.05
            )
            assert hog.hitpoints == row["hp"]


COMPLETED = json.loads(
    (
        Path(__file__).parent / "fixtures/native_friendly_completed_15_535_86.json"
    ).read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", COMPLETED["cases"])
def test_completed_friendly_obstacle_push_matches_native(case, fast_path):
    battle = BattleState(fast_path=fast_path)
    for _ in range(COMPLETED["decision_tick"]):
        battle.step()
    enemy_towers = {
        e.id: e.hitpoints
        for e in battle.entities.values()
        if e.player_id == 1 - case["owner"]
    }
    for name, x, y in case["placements"]:
        battle.players[case["owner"]].hand = [name]
        assert battle.deploy_card(case["owner"], name, Position(x, y))
    for _ in range(case["end_tick"] - COMPLETED["decision_tick"]):
        battle.step()
    assert not any(
        e.player_id == case["owner"] and e.card_stats.name == case["troop"]
        for e in battle.entities.values()
    )
    damage = sum(enemy_towers.values()) - sum(
        battle.entities[i].hitpoints if i in battle.entities else 0
        for i in enemy_towers
    )
    assert damage == case["native_tower_damage"]
