import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop


@pytest.mark.parametrize("fast_path", [False, True])
def test_native_death_frame_retains_static_avoidance_without_collision(fast_path):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_death_frame_avoidance_15_535_86.json")
        .read_text()
    )
    expected = {row["tick"]: row["units"] for row in reference["frames"]}
    battle = BattleState(fast_path=fast_path)
    unit_ids = []
    while battle.tick < max(expected):
        if battle.tick in (0, 30):
            owner = 0 if battle.tick == 0 else 1
            card = "Skeletons" if owner == 0 else "Knight"
            battle.players[owner].hand = [card]
            before = set(battle.entities)
            assert battle.deploy_card(owner, card, Position(3.5, 13.5 if owner == 0 else 18.5))
            unit_ids.extend(sorted(set(battle.entities) - before))
        battle.step()
        if battle.tick in expected:
            actual = [
                {"index": index, "xy": [round(e.position.x * 1000), round(e.position.y * 1000)]}
                for index, identity in enumerate(unit_ids)
                if (e := battle.entities.get(identity)) is not None
            ]
            assert actual == expected[battle.tick], battle.tick


@pytest.mark.parametrize("fast_path", [False, True])
def test_native_deploying_skeleton_facing_preserves_friendly_golem_path(fast_path):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_deploy_facing_15_535_86.json").read_text()
    )
    expected = {row["tick"]: row["positions"] for row in reference["frames"]}
    battle = BattleState(fast_path=fast_path)
    while battle.tick < max(expected):
        if battle.tick in (0, 30):
            card = "IceGolem" if battle.tick == 0 else "Skeletons"
            battle.players[0].hand = [card]
            assert battle.deploy_card(0, card, Position(14.5, 13.5))
        battle.step()
        if battle.tick in expected:
            units = [e for e in battle.entities.values() if isinstance(e, Troop)]
            assert [
                [round(e.position.x * 1000), round(e.position.y * 1000)] for e in units
            ] == expected[battle.tick], battle.tick


@pytest.mark.parametrize("fast_path", [False, True])
def test_native_archer_stagger_preserves_skeleton_target_and_route(fast_path):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_archer_stagger_targeting_15_535_86.json")
        .read_text()
    )
    expected = {row["elapsed_tick"]: row for row in reference["frames"]}
    battle = BattleState(fast_path=fast_path)
    commands = {
        0: (0, "IceGolem", Position(3.5, 13.5)),
        60: (0, "Skeletons", Position(3.5, 13.5)),
        120: (0, "Log", Position(3.5, 13.5)),
        180: (1, "Archers", Position(3.5, 22.5)),
    }
    while battle.tick < max(expected):
        if battle.tick in commands:
            owner, card, position = commands[battle.tick]
            battle.players[owner].hand = [card]
            assert battle.deploy_card(owner, card, position)
        battle.step()
        if battle.tick not in expected:
            continue
        units = [e for e in battle.entities.values() if isinstance(e, Troop)]
        assert len(units) == 6
        assert [
            [round(e.position.x * 1000), round(e.position.y * 1000)] for e in units
        ] == expected[battle.tick]["positions"], battle.tick
        indices = {e.id: index for index, e in enumerate(units)}
        assert [indices.get(e.target_id) for e in units] == expected[battle.tick]["target_indices"]


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("stagger", [0.0, 0.1])
def test_spawn_stagger_delays_own_collision_but_keeps_body_solid(fast_path, stagger):
    battle = BattleState(fast_path=fast_path)
    first_id = battle.next_entity_id
    battle._spawn_unit_at_position(
        Position(9.0, 10.0),
        0,
        battle.card_loader.get_card("Archers"),
        deploy_delay_offset=stagger,
    )
    archer = battle.entities[first_id]
    knight_id = battle.next_entity_id
    battle._spawn_unit_at_position(
        Position(9.0, 10.5), 1, battle.card_loader.get_card("Knight")
    )
    knight = battle.entities[knight_id]
    start = Position(archer.position.x, archer.position.y)
    knight_start = Position(knight.position.x, knight.position.y)

    # Native Archer1501 is in state11 while its first group member is in4.
    # The100ms stagger ends after two object ticks; collision starts on third.
    battle.step()
    assert knight.position != knight_start
    if not stagger:
        assert archer.position != start
        assert archer.placement_pending
        return
    assert archer.position == start
    assert archer.spawn_stagger_remaining == pytest.approx(0.05)
    battle.step()
    assert archer.position == start
    assert archer.spawn_stagger_remaining == 0.0
    battle.step()
    assert archer.position != start
    assert archer.placement_pending
