import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
def test_native_distant_building_keeps_existing_route_nodes(fast_path):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_route_replacement_15_535_86.json").read_text()
    )
    expected = {row["tick"]: row["units"] for row in reference["frames"]}
    battle = BattleState(fast_path=fast_path)
    tracked = []
    commands = {
        0: (0, "Skeletons", Position(3.5, 13.5)),
        30: (1, "Knight", Position(3.5, 18.5)),
        60: (0, "Cannon", Position(3.5, 13.5)),
    }
    while battle.tick < max(expected):
        if battle.tick in commands:
            owner, card, position = commands[battle.tick]
            battle.players[owner].hand = [card]
            before = set(battle.entities)
            assert battle.deploy_card(owner, card, position)
            if card != "Cannon":
                tracked.extend(sorted(set(battle.entities) - before))
        battle.step()
        if battle.tick in expected:
            actual = [
                {"index": index, "xy": [round(e.position.x * 1000), round(e.position.y * 1000)]}
                for index, identity in enumerate(tracked)
                if (e := battle.entities.get(identity)) is not None
            ]
            assert actual == expected[battle.tick], battle.tick
