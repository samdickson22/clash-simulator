import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_frozen_body_collision_15_535_86.json").read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_native_stun_pauses_travel_but_preserves_collision_displacement(fast_path, case):
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["seed"]))
    for player, elixir in zip(battle.players, case["elixir"]):
        player.elixir = elixir
    names = {case["card"]: case["name"], 26000038: "IceGolem", 28000008: "Zap"}
    units = {}
    expected = {r["tick"]: r["bodies"] for r in case["frames"]}
    while battle.tick < max(expected):
        for submitted, owner, card, x, y in case["commands"]:
            if battle.tick != submitted:
                continue
            name = names[card]
            battle.players[owner].hand = [name]
            before = set(battle.entities)
            assert battle.deploy_card(owner, name, Position(x / 1000, y / 1000))
            if name != "Zap":
                units["golem" if name == "IceGolem" else "target"] = battle.entities[(set(battle.entities) - before).pop()]
        battle.step()
        if battle.tick in expected:
            actual = [
                {"role": role, "xy": [round(e.position.x * 1000), round(e.position.y * 1000)], "hp": e.hitpoints, "stun_ms": round(e.stun_timer * 1000)}
                for role, e in sorted(units.items())
            ]
            assert actual == expected[battle.tick], battle.tick
