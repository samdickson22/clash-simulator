import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
def test_zap_killed_current_target_finishes_before_knight_reacquires(fast_path):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_command_target_death_15_535_86.json").read_text()
    )
    expected = {r["tick"]: r for r in reference["frames"]}
    battle = BattleState(fast_path=fast_path)
    knight = None
    commands = {
        0: [(0, "Skeletons", Position(3.5, 14.5)), (1, "Knight", Position(3.5, 17.5))],
        30: [(1, "Zap", Position(3.5, 15.5))],
    }
    while battle.tick < max(expected):
        for owner, card, position in commands.get(battle.tick, []):
            battle.players[owner].hand = [card]
            before = set(battle.entities)
            if card == "Zap":
                old_target = battle.entities[knight.target_id]
                assert old_target.is_alive
            assert battle.deploy_card(owner, card, position)
            if card == "Knight":
                knight = battle.entities[(set(battle.entities) - before).pop()]
            if card == "Zap":
                # Acceptance queues the direct effect for the object phase.
                assert old_target.is_alive
                assert battle._pending_spell_casts
        battle.step()
        if battle.tick in expected:
            row = expected[battle.tick]
            assert (knight.target_id is not None) == row["has_target"], battle.tick
            assert [round(knight.position.x * 1000), round(knight.position.y * 1000)] == row["xy"], battle.tick
            assert knight.hitpoints == row["hp"], battle.tick
