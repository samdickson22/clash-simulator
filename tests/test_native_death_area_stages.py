import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import (
    AreaEffect,
    BuffAreaEffect,
    DeathAreaEffectContainer,
    DeathAreaStartAction,
)

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_death_area_stages_15_535_86.json").read_text()
)


def play(battle, owner, card, xy):
    battle.players[owner].hand = [card]
    before = set(battle.entities)
    assert battle.deploy_card(owner, card, Position(*xy))
    return [battle.entities[key] for key in sorted(set(battle.entities) - before)]


@pytest.mark.parametrize("fast_path", [False, True])
def test_native_lumberjack_start_bottle_rage_and_impact_stages(fast_path):
    case = REFERENCE["lumberjack"]
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["config"]["seed"]))
    for player, elixir in zip(battle.players, case["config"]["elixir"]):
        player.elixir = elixir
    expected = {r["tick"]: r for r in case["frames"]}
    knight = pekka = None
    while battle.tick < max(expected):
        if battle.tick == 100:
            play(battle, 0, "Lumberjack", (3.5, 14.5))
            pekka = play(battle, 1, "Pekka", (3.5, 17.5))[0]
        if battle.tick == 110:
            knight = play(battle, 0, "Knight", (2.5, 13.5))[0]
        battle.step()
        if battle.tick not in expected:
            continue
        row = expected[battle.tick]
        roles = {DeathAreaStartAction: "start", DeathAreaEffectContainer: "bottle", BuffAreaEffect: "rage", AreaEffect: "damage"}
        stages = sorted(roles[type(e)] for e in battle.entities.values() if type(e) in roles)
        assert stages == row["stages"], battle.tick
        assert knight.hitpoints == row["knight_hp"], battle.tick
        assert pekka.hitpoints == row["pekka_hp"], battle.tick
        assert round(knight.haste_timer * 1000) == row["rage_ms"], battle.tick


@pytest.mark.parametrize("fast_path", [False, True])
def test_native_ice_golem_combat_death_slow_starts_after_birth(fast_path):
    battle = BattleState(fast_path=fast_path)
    expected = {r["tick"] - 100: r["slow_ms"] for r in REFERENCE["ice_golem"]}
    commands = {0: (0, "IceGolem", (3.5, 11.5)), 60: (0, "Skeletons", (3.5, 13.5)), 120: (1, "Knight", (3.5, 17.5)), 180: (1, "Tesla", (3.5, 18.5))}
    knight = None
    while battle.tick < max(expected):
        if battle.tick in commands:
            owner, card, xy = commands[battle.tick]
            entities = play(battle, owner, card, xy)
            if card == "Knight":
                knight = entities[0]
        battle.step()
        if battle.tick in expected:
            assert round(knight.slow_timer * 1000) == expected[battle.tick], battle.tick
