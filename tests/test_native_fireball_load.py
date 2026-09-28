"""Fireball stops ordinary hit work while preserving and advancing load."""

import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_fireball_load_15_535_86.json")
    .read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["name"])
def test_native_fireball_preserves_load_across_pushback(case, fast_path):
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["seed"]))
    for player, elixir in zip(battle.players, case["elixir"]):
        player.elixir = elixir
    expected = {f["tick"]: f for f in case["frames"]}
    names = {26000000: "Knight", 26000038: "IceGolem", 28000000: "Fireball"}
    knight = None
    while battle.tick < max(expected):
        for command in case["commands"]:
            if command["submitted_tick"] != battle.tick:
                continue
            name = names[command["card"]]
            battle.players[command["owner"]].hand = [name]
            before = set(battle.entities)
            assert battle.deploy_card(
                command["owner"], name,
                Position(*(v / 1000 for v in command["xy"])),
            )
            if name == "Knight":
                knight = battle.entities[(set(battle.entities) - before).pop()]
        battle.step()
        if battle.tick not in expected:
            continue
        row = expected[battle.tick]
        assert [round(knight.position.x * 1000), round(knight.position.y * 1000)] == row["xy"], battle.tick
        assert knight.hitpoints == row["hp"], battle.tick
        clock = knight._ordinary_clock
        assert (clock.hit_timeline_ms if clock else 0) == row["timeline"], battle.tick
        assert (clock.load_remaining_ms if clock else 0) == row["load"], battle.tick
