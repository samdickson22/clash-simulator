"""Zap damage and stun begin only when each group member's stagger expires."""
import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads((Path(__file__).parent / "fixtures/native_stagger_effects_15_535_86.json").read_text())


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["name"])
def test_native_stagger_gates_damage_and_stun(case, fast_path):
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["seed"]))
    for player, elixir in zip(battle.players, case["elixir"]):
        player.elixir = elixir
    expected = {f["tick"]: f["bodies"] for f in case["frames"]}
    names = {26000002: "Goblins", 28000008: "Zap"}
    while battle.tick < max(expected):
        for command in case["commands"]:
            if command["submitted_tick"] != battle.tick:
                continue
            name = names[command["card"]]
            battle.players[command["owner"]].hand = [name]
            assert battle.deploy_card(command["owner"], name, Position(*(v / 1000 for v in command["xy"])))
        battle.step()
        if battle.tick not in expected:
            continue
        bodies = [e for e in battle.entities.values() if e.entity_kind == 0 and e.card_stats.name == "Goblins"]
        assert len(bodies) == len(expected[battle.tick])
        for body, row in zip(bodies, expected[battle.tick]):
            assert body.hitpoints == row["hp"], battle.tick
            assert body.stun_timer * 1000 == pytest.approx(row["stun_ms"]), battle.tick
            assert [round(body.position.x * 1000), round(body.position.y * 1000)] == row["xy"], battle.tick
