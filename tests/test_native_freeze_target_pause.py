import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
def test_freeze_releases_target_until_thaw_without_resetting_active_hit(fast_path):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_freeze_target_pause_15_535_86.json").read_text()
    )
    expected = {row["tick"]: row for row in reference["frames"]}
    battle = BattleState(fast_path=fast_path)
    knight = cannon = None
    commands = {
        0: [(0, "Cannon", Position(3.5, 13.5)), (1, "Knight", Position(3.5, 17.5))],
        60: [(0, "IceSpirit", Position(3.5, 14.5))],
    }
    while battle.tick < max(expected):
        for owner, card, position in commands.get(battle.tick, []):
            battle.players[owner].hand = [card]
            before = set(battle.entities)
            assert battle.deploy_card(owner, card, position)
            entity = battle.entities[(set(battle.entities) - before).pop()]
            if card == "Knight":
                knight = entity
            elif card == "Cannon":
                cannon = entity
        battle.step()
        if battle.tick in expected:
            row = expected[battle.tick]
            assert (knight.target_id is not None) == row["has_target"], battle.tick
            assert (knight._freeze_target_pause_remaining > 0) == row["frozen"], battle.tick
            assert knight.attack_cooldown == pytest.approx(row["remaining"]), battle.tick
            assert (cannon.hitpoints if cannon.id in battle.entities else None) == row["cannon_hp"], battle.tick
