import copy
import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
def test_native_zap_preserves_ordinary_hit_and_load_after_component_work(fast_path):
    case = json.loads(
        (Path(__file__).parent / "fixtures/native_ordinary_zap_clock_15_535_86.json").read_text()
    )
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["seed"]))
    for player, elixir in zip(battle.players, case["elixir"]):
        player.elixir = elixir
    expected = {row["tick"]: row for row in case["frames"]}
    knight = None
    names = {27000000: "Cannon", 26000000: "Knight", 28000008: "Zap"}
    while battle.tick < max(expected):
        for submitted, owner, card, x, y in case["commands"]:
            if battle.tick != submitted:
                continue
            battle.players[owner].hand = [names[card]]
            before = set(battle.entities)
            assert battle.deploy_card(owner, names[card], Position(x / 1000, y / 1000))
            if names[card] == "Knight":
                knight = battle.entities[(set(battle.entities) - before).pop()]
        battle.step()
        if battle.tick in expected:
            row = expected[battle.tick]
            assert knight._ordinary_clock is not None
            assert knight._ordinary_clock.hit_timeline_ms == row["timeline"], battle.tick
            assert knight._ordinary_clock.load_remaining_ms == row["load"], battle.tick
            assert (knight.target_id is not None) == row["has_target"], battle.tick
            assert round(knight.stun_timer * 1000) == row["stun_ms"], battle.tick
            assert knight.hitpoints == row["hp"], battle.tick
        if battle.tick == 205:
            clone = copy.deepcopy(battle)
            cloned_knight = clone.entities[knight.id]
            assert cloned_knight._ordinary_clock == knight._ordinary_clock
            assert cloned_knight._ordinary_clock is not knight._ordinary_clock
            cloned_knight._ordinary_clock.load_remaining_ms += 1
            assert cloned_knight._ordinary_clock != knight._ordinary_clock
