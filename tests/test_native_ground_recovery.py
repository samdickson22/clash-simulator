"""Native land and river controls protect recovery ordering and tie breaks."""

import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/native_ground_recovery_15_535_86.json"
    ).read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["name"])
def test_native_log_push_recovers_ground_at_the_next_component_boundary(
    case, fast_path
):
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["seed"]))
    for player, elixir in zip(battle.players, case["elixir"]):
        player.elixir = elixir
    names = {26000003: "Giant", 27000000: "Cannon", 28000011: "Log"}
    expected = {f["tick"]: f for f in case["frames"]}
    giant = None
    while battle.tick < max(expected):
        for command in case["commands"]:
            if command["submitted_tick"] != battle.tick:
                continue
            name = names[command["card"]]
            owner = command["owner"]
            battle.players[owner].hand = [name]
            before = set(battle.entities)
            assert battle.deploy_card(
                owner, name, Position(*(x / 1000 for x in command["xy"]))
            )
            if name == "Giant":
                giant = battle.entities[(set(battle.entities) - before).pop()]
        battle.step()
        if battle.tick in expected:
            row = expected[battle.tick]
            assert [
                round(giant.position.x * 1000),
                round(giant.position.y * 1000),
            ] == row["xy"], battle.tick
            assert giant.hitpoints == row["hp"], battle.tick
