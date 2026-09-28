import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case_index", [0, 1, 2])
def test_native_tesla_finishes_target_killed_by_earlier_knight(fast_path, case_index):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_same_phase_target_death_15_535_86.json").read_text()
    )["cases"][case_index]
    expected = {r["tick"]: r for r in reference["frames"]}
    clocks = {r["tick"]: r["remaining"] for r in reference.get("knight_clocks", [])}
    commands = {
        0: (0, "IceGolem", Position(3.5, 11.5)),
        60: (0, "Skeletons", Position(3.5, 13.5)),
        120: (1, "Knight", Position(3.5, 17.5)),
        reference["tesla_tick"] - 1: (1, "Tesla", Position(3.5, 18.5)),
    }
    battle = BattleState(fast_path=fast_path)
    tesla = None
    knight = None
    for _ in range(max([*expected, *clocks])):
        if battle.tick in commands:
            owner, card, position = commands[battle.tick]
            battle.players[owner].hand = [card]
            before = set(battle.entities)
            assert battle.deploy_card(owner, card, position)
            if card == "Tesla":
                tesla = battle.entities[(set(battle.entities) - before).pop()]
            elif card == "Knight":
                knight = battle.entities[(set(battle.entities) - before).pop()]
        battle.step()
        if battle.tick in expected:
            assert (tesla.target_id is not None) == expected[battle.tick]["has_target"], battle.tick
            if min(expected) < battle.tick < max(expected):
                assert tesla._attack_finish_elapsed_ms > 0, battle.tick
        if battle.tick in clocks:
            assert knight.attack_cooldown == pytest.approx(clocks[battle.tick]), battle.tick
