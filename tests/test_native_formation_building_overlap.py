import json
import random
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_formation_building_overlap_15_535_86.json").read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_native_card_formation_uses_legal_column_boundary(fast_path, case):
    battle = BattleState(fast_path=fast_path, rng=random.Random(case["seed"]))
    for player, elixir in zip(battle.players, case["elixir"]):
        player.elixir = elixir
    names = {26000000: "Knight", 26000001: "Archers", 26000010: "Skeletons"}
    owner = case.get("owner", 0)
    building = case.get("building", "Cannon")
    building_xy = case.get("building_xy", [3500, 13500])
    while battle.tick < 200:
        if battle.tick == 100:
            battle.players[owner].hand = [building]
            assert battle.deploy_card(owner, building, Position(*(v / 1000 for v in building_xy)))
        battle.step()
    name = case["name"] if "name" in case else names[case["card"]]
    battle.players[owner].hand = [name]
    before = set(battle.entities)
    assert battle.deploy_card(owner, name, Position(*(v / 1000 for v in case["requested"])))
    ids = sorted(set(battle.entities) - before)
    battle.step()
    assert [
        [round(battle.entities[i].position.x * 1000), round(battle.entities[i].position.y * 1000)]
        for i in ids
    ] == case["xy"]
