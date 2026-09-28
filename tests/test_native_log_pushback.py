import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_log_pushback_15_535_86.json").read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["name"])
def test_native_log_landing_rolling_and_post_push_movement(fast_path, case):
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["seed"]))
    for player, elixir in zip(battle.players, case["elixir"]):
        player.elixir = elixir
    expected = {row["tick"]: row for row in case["frames"]}
    knight = None
    names = {26000000: "Knight", 28000011: "Log", 27000000: "Cannon"}
    while battle.tick < max(expected):
        for submitted, owner, card, x, y in case["commands"]:
            if submitted != battle.tick:
                continue
            name = names[card]
            battle.players[owner].hand = [name]
            before = set(battle.entities)
            assert battle.deploy_card(owner, name, Position(x / 1000, y / 1000))
            if name == "Knight":
                knight = battle.entities[(set(battle.entities) - before).pop()]
        battle.step()
        if battle.tick in expected:
            row = expected[battle.tick]
            assert [round(knight.position.x * 1000), round(knight.position.y * 1000)] == row["xy"], battle.tick
            assert knight.hitpoints == row["hp"], battle.tick
            assert knight.attack_cooldown == pytest.approx(row["attack_remaining"]), battle.tick
            assert knight._ordinary_clock is not None
            assert knight._ordinary_clock.hit_timeline_ms == row["timeline"], battle.tick
            assert knight._ordinary_clock.load_remaining_ms == row["load"], battle.tick
