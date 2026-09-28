import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
def test_skeleton_keeps_position_when_hit_starts_before_loading_finishes(fast_path):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_skeleton_started_hit_15_535_86.json").read_text()
    )
    expected = {row["tick"]: row["xy"] for row in reference["frames"]}
    battle = BattleState(fast_path=fast_path)
    commands = {
        0: (0, "IceGolem", Position(3.5, 11.5)),
        60: (0, "Skeletons", Position(3.5, 13.5)),
        120: (1, "Knight", Position(3.5, 17.5)),
    }
    skeleton = None
    while battle.tick < max(expected):
        if battle.tick in commands:
            owner, card, position = commands[battle.tick]
            battle.players[owner].hand = [card]
            before = set(battle.entities)
            assert battle.deploy_card(owner, card, position)
            if card == "Skeletons":
                skeleton = battle.entities[sorted(set(battle.entities) - before)[2]]
        battle.step()
        if battle.tick in expected:
            assert [round(skeleton.position.x * 1000), round(skeleton.position.y * 1000)] == expected[battle.tick], battle.tick
