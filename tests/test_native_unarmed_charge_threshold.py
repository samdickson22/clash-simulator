import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
def test_reaching_charge_threshold_without_an_arming_movement_does_normal_damage(fast_path):
    case = json.loads(
        (Path(__file__).parent / "fixtures/native_unarmed_charge_threshold_15_535_86.json").read_text()
    )
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["seed"]))
    expected = {r["tick"]: r for r in case["frames"]}
    dark_prince = hog = None
    while battle.tick < max(expected):
        for command in case["commands"]:
            if battle.tick != command["tick"]:
                continue
            owner, name = command["owner"], command["name"]
            battle.players[owner].hand = [name]
            before = set(battle.entities)
            assert battle.deploy_card(owner, name, Position(*command["xy"]))
            if name == "DarkPrince":
                dark_prince = battle.entities[(set(battle.entities) - before).pop()]
            elif name == "HogRider":
                hog = battle.entities[(set(battle.entities) - before).pop()]
        battle.step()
        if battle.tick in expected:
            row = expected[battle.tick]
            assert dark_prince._native_charge_progress == row["charge"], battle.tick
            assert dark_prince._ordinary_clock.hit_timeline_ms == row["timeline"], battle.tick
            assert dark_prince._ordinary_clock.load_remaining_ms == row["load"], battle.tick
            assert (hog.hitpoints if hog.id in battle.entities else None) == row["hog_hp"], battle.tick
            assert battle.entities[1].hitpoints == row["tower_hp"], battle.tick
