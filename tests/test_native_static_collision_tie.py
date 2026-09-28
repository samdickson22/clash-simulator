import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_static_collision_tie_15_535_86.json").read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_native_static_collision_exact_and_near_center_positions(fast_path, case):
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["seed"]))
    for player, elixir in zip(battle.players, case["elixir"]):
        player.elixir = elixir
    expected = {r["tick"]: r["positions"] for r in case["frames"]}
    units = {}
    while battle.tick < max(expected):
        for submitted, owner, card, x, y in case["commands"]:
            if battle.tick != submitted:
                continue
            name = "Cannon" if card == 27000000 else case["name"]
            battle.players[owner].hand = [name]
            before = set(battle.entities)
            assert battle.deploy_card(owner, name, Position(x / 1000, y / 1000))
            units["building" if name == "Cannon" else "target"] = battle.entities[(set(battle.entities) - before).pop()]
        battle.step()
        if battle.tick in expected:
            assert {
                role: [round(e.position.x * 1000), round(e.position.y * 1000)]
                for role, e in units.items()
            } == expected[battle.tick], battle.tick
