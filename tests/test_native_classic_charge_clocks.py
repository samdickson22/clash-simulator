import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_classic_charge_clocks_15_535_86.json").read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: str(c["spell"]))
def test_native_classic_charge_clocks_and_interruption_boundaries(fast_path, case):
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["seed"]))
    for player, elixir in zip(battle.players, case["elixir"]):
        player.elixir = elixir
    names = {27000000: "Cannon", 26000016: "Prince", 28000008: "Zap", 28000011: "Log"}
    charger_name = case.get("name", "Prince")
    names[case.get("card", 26000016)] = charger_name
    target_ids = {5000000: 3, 5000001: 1, 5000002: 2, 5000003: 6, 5000004: 4, 5000005: 5}
    expected = {row["tick"]: row for row in case["frames"]}
    prince = cannon = None
    while battle.tick < max(expected):
        for submitted, owner, card, x, y in case["commands"]:
            if battle.tick != submitted:
                continue
            name = names[card]
            battle.players[owner].hand = [name]
            before = set(battle.entities)
            assert battle.deploy_card(owner, name, Position(x / 1000, y / 1000))
            if name == charger_name:
                prince = battle.entities[(set(battle.entities) - before).pop()]
            elif name == "Cannon":
                cannon = battle.entities[(set(battle.entities) - before).pop()]
                target_ids[5000006] = cannon.id
        battle.step()
        if battle.tick not in expected:
            continue
        row = expected[battle.tick]
        assert prince._ordinary_clock is not None
        assert prince._ordinary_clock.hit_timeline_ms == row["timeline"], battle.tick
        assert prince._ordinary_clock.load_remaining_ms == row["load"], battle.tick
        assert prince._native_charge_progress == row["charge"], battle.tick
        assert prince.target_id == target_ids.get(row["target"]), battle.tick
        assert prince.hitpoints == row["hp"], battle.tick
        assert (cannon.hitpoints if cannon.id in battle.entities else None) == row["cannon_hp"], battle.tick
        assert [round(prince.position.x * 1000), round(prince.position.y * 1000)] == row["xy"], battle.tick
