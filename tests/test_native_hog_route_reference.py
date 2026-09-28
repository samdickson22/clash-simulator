import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.pathfinding import ground_path_waypoint, native_route_goal_cell


def test_hog_cannon_goal_and_route_match_captured_native_cells():
    # Paused15.535.86 native route captured at tick112; see
    # reports/hog_phase_alignment_20260914/route-inline-first-move.json.
    battle = BattleState()
    battle.players[0].hand = ["HogRider"]
    battle.players[1].hand = ["Cannon"]
    assert battle.deploy_card(0, "HogRider", Position(3.5, 14.5))
    assert battle.deploy_card(1, "Cannon", Position(7.5, 19.5))
    hog = next(e for e in battle.entities.values() if e.card_stats.name == "HogRider")
    cannon = next(e for e in battle.entities.values() if e.card_stats.name == "Cannon")
    assert native_route_goal_cell(hog, cannon) == (14, 36)
    assert ground_path_waypoint(
        battle, hog, cannon.position, target_entity=cannon
    ) == Position(3.75, 14.75)
    # The native sample has already consumed the first node after moving.
    assert hog._native_ground_route_cells[1:] == [
        (8, 30),
        (9, 31),
        (10, 32),
        (11, 33),
        (12, 34),
        (13, 35),
        (14, 36),
    ]


def test_hog_starts_jump_after_second_route_node_before_entering_water():
    battle = BattleState()
    for owner, name, position in (
        (0, "HogRider", Position(3.5, 14.5)),
        (1, "Cannon", Position(7.5, 19.5)),
    ):
        battle.players[owner].hand = [name]
        assert battle.deploy_card(owner, name, position)
    hog = next(e for e in battle.entities.values() if e.card_stats.name == "HogRider")
    for _ in range(21):
        battle.step()
    # Native ticks112..114, aligned to the first ordinary movement frame.
    assert hog.position == Position(3.583, 14.584)
    assert not getattr(hog, "_river_jump_active", False)
    battle.step()
    assert hog.position == Position(3.667, 14.668)
    assert hog._river_jump_active
    assert hog._native_ground_route_cells == [(12, 34)]
    assert hog._river_jump_target == Position(6.25, 17.25)
    battle.step()
    assert hog.position == Position(3.78, 14.78)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("defender", ["Cannon", "Tesla"])
def test_hog_building_movement_matches_100_external_reference_frames(
    fast_path, defender
):
    reference = json.loads(
        (
            Path(__file__).parent
            / "fixtures"
            / f"native_hog_{defender.lower()}_movement_15_535_86.json"
        ).read_text()
    )
    battle = BattleState(fast_path=fast_path)
    for owner, name, position in (
        (0, "HogRider", Position(3.5, 14.5)),
        (1, defender, Position(7.5, 19.5)),
    ):
        battle.players[owner].hand = [name]
        assert battle.deploy_card(owner, name, position)
    hog = next(e for e in battle.entities.values() if e.card_stats.name == "HogRider")
    building = next(
        e for e in battle.entities.values() if e.card_stats.name == defender
    )
    for _ in range(reference["scalar_start_tick"]):
        battle.step()
    for index, expected in enumerate(reference["positions"]):
        assert building.hitpoints == reference["building_health"][index], index
        if "actor_health" in reference:
            assert hog.hitpoints == reference["actor_health"][index], index
        assert [
            round(hog.position.x * 1000),
            round(hog.position.y * 1000),
        ] == expected, index
        if index + 1 < len(reference["positions"]):
            battle.step()


@pytest.mark.parametrize(
    ("goal", "first", "remaining"),
    [
        ((13, 35), (7, 29), [(8, 30), (9, 31), (10, 32), (11, 33), (12, 34), (13, 35)]),
        ((12, 35), (7, 30), [(8, 31), (9, 32), (10, 33), (11, 34), (12, 35)]),
    ],
)
def test_pathfinder_matches_native_hog_tesla_and_prince_cannon_routes(
    goal, first, remaining
):
    from clasher.pathfinding import _cached_standard_grid_route

    # Retained arrays read from paused native movement components at tick112.
    # See hog-tesla-native-route.json and prince-first-route.json in reports.
    route = _cached_standard_grid_route((6, 29), goal, 1, True)
    assert route == ((6, 29), first, *remaining)
